import os
import time
import logging
import boto3
from botocore.exceptions import ClientError
from backoff_algorithm import calculate_exponential_backoff

# Safely extract the region from the environment, defaulting to us-east-1
AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')

# Initialize clients with an explicit region fallback
sqs_client = boto3.client('sqs', region_name=AWS_REGION)
dynamodb_client = boto3.client('dynamodb', region_name=AWS_REGION)
sns_client = boto3.client('sns', region_name=AWS_REGION)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables mapping to the SAM template
TABLE_NAME = os.environ.get('IDEMPOTENCY_TABLE', 'DLQIdempotencyTable')
DLQ_URL = os.environ.get('DLQ_URL')
SNS_TOPIC_ARN = os.environ.get('ALERT_TOPIC_ARN')
MAX_RETRIES = 5

class EnterpriseDLQProcessor:
    def __init__(self, sqs, dynamodb, sns, table_name):
        self.sqs = sqs
        self.dynamodb = dynamodb
        self.sns = sns
        self.table_name = table_name

    def _acquire_idempotency_lock(self, message_id):
        """
        Attempts to acquire a distributed lock in DynamoDB via conditional writes.
        Returns True if the lock is successfully acquired, False if it is a duplicate.
        """
        # BUG 3 FIX: Calculate TTL (24 hours from current epoch) to ensure locks naturally expire
        ttl_timestamp = int(time.time()) + 86400
        
        try:
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    'MessageId': {'S': message_id},
                    'Status': {'S': 'PROCESSING'},
                    'ExpirationTime': {'N': str(ttl_timestamp)}
                },
                ConditionExpression='attribute_not_exists(MessageId)'
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Duplicate message detected and ignored: {message_id}")
                return False
            raise e

    def _mark_processed(self, message_id):
        """Updates the lock status to prevent future retries of completed work."""
        try:
            self.dynamodb.update_item(
                TableName=self.table_name,
                Key={'MessageId': {'S': message_id}},
                UpdateExpression='SET #st = :status',
                ExpressionAttributeNames={'#st': 'Status'},
                ExpressionAttributeValues={':status': {'S': 'PROCESSED'}}
            )
        except ClientError as e:
            logger.error(f"Failed to update idempotency status for {message_id}: {e}")

    def process_sqs_event(self, event):
        """Main processing loop for incoming SQS batches."""
        for record in event.get('Records', []):
            # BUG 1 FIX: Use standard camelCase keys provided by AWS Lambda SQS triggers
            message_id = record.get('messageId')
            receipt_handle = record.get('receiptHandle')
            message_attributes = record.get('messageAttributes', {})
            
            if not message_id or not receipt_handle:
                logger.error("Invalid SQS record received: missing messageId or receiptHandle")
                continue

            # Safely extract custom retry count from message attributes
            try:
                retry_count = int(message_attributes.get('RetryCount', {}).get('stringValue', '1'))
            except (ValueError, TypeError):
                retry_count = 1

            # 1. Idempotency Check
            if not self._acquire_idempotency_lock(message_id):
                continue  # Skip duplicate execution

            try:
                # 2. Business Logic Execution
                self._execute_business_logic(record.get('body'))
                
                # 3. Success Cleanup
                self._mark_processed(message_id)
                self.sqs.delete_message(
                    QueueUrl=DLQ_URL,
                    ReceiptHandle=receipt_handle
                )
                logger.info(f"Successfully processed message {message_id}")

            except Exception as e:
                logger.error(f"Processing failed for {message_id}: {str(e)}")
                
                # 4. Escalation or Backoff
                if retry_count >= MAX_RETRIES:
                    logger.critical(f"Message {message_id} breached max retries. Escalating to SNS.")
                    self.sns.publish(
                        TopicArn=SNS_TOPIC_ARN,
                        Message=f"DLQ Remediation Failed permanently for message: {message_id}",
                        Subject="DLQ Max Retries Breached"
                    )
                    # Delete from queue to prevent an infinite loop after SNS escalation
                    self.sqs.delete_message(QueueUrl=DLQ_URL, ReceiptHandle=receipt_handle)
                else:
                    # BUG 4 FIX: Ensure delay_seconds never truncates to 0 by enforcing a minimum floor
                    raw_delay = calculate_exponential_backoff(retry_count)
                    delay_seconds = max(1, int(raw_delay))
                    
                    logger.info(f"Applying backoff of {delay_seconds} seconds for {message_id}")
                    
                    # Note: Ensure `sqs:ChangeMessageVisibility` is added to the IAM template policy
                    self.sqs.change_message_visibility(
                        QueueUrl=DLQ_URL,
                        ReceiptHandle=receipt_handle,
                        VisibilityTimeout=delay_seconds
                    )

    def _execute_business_logic(self, payload):
        """Simulates the downstream operation that might fail during an outage."""
        logger.info("Executing remediation logic against downstream systems...")
        # Add actual database or API logic here.
        pass

# Instantiate the processor globally so it is maintained across warm starts
processor = EnterpriseDLQProcessor(
    sqs=sqs_client,
    dynamodb=dynamodb_client,
    sns=sns_client,
    table_name=TABLE_NAME
)

def lambda_handler(event, context):
    """Standard AWS Lambda entry point."""
    logger.info(f"Received batch of {len(event.get('Records', []))} messages")
    processor.process_sqs_event(event)
    return {"statusCode": 200, "body": "Batch processed successfully"}