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
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Environment variables mapping to the SAM template
TABLE_NAME = os.environ.get('IDEMPOTENCY_TABLE', 'DLQIdempotencyTable')
DLQ_URL = os.environ.get('DLQ_URL')
SNS_TOPIC_ARN = os.environ.get('ALERT_TOPIC_ARN')

if not all([DLQ_URL, SNS_TOPIC_ARN]):
    raise RuntimeError("DLQ_URL and ALERT_TOPIC_ARN must be set")

MAX_RETRIES = 5
LOCK_TTL_SECONDS = 86400  # Idempotency records self-expire after 24h via DynamoDB TTL


class EnterpriseDLQProcessor:
    def __init__(self, sqs, dynamodb, sns, table_name, dlq_url, alert_topic_arn):
        self.sqs = sqs
        self.dynamodb = dynamodb
        self.sns = sns
        self.table_name = table_name
        self.dlq_url = dlq_url
        self.alert_topic_arn = alert_topic_arn

    def _acquire_idempotency_lock(self, message_id):
        """
        Attempts to acquire a distributed lock in DynamoDB via a conditional write.
        Returns True if the lock is acquired, False if the message is already
        being processed or has already completed (a duplicate delivery).
        """
        ttl_timestamp = int(time.time()) + LOCK_TTL_SECONDS
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
            raise

    def _release_idempotency_lock(self, message_id):
        """
        Releases the lock after a processing failure so the next redelivery can
        re-acquire it and retry. Only deletes records still in the PROCESSING
        state, so a concurrently-completed record is never clobbered.
        """
        try:
            self.dynamodb.delete_item(
                TableName=self.table_name,
                Key={'MessageId': {'S': message_id}},
                ConditionExpression='#st = :processing',
                ExpressionAttributeNames={'#st': 'Status'},
                ExpressionAttributeValues={':processing': {'S': 'PROCESSING'}}
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                logger.error(f"Failed to release idempotency lock for {message_id}: {e}")

    def _mark_processed(self, message_id):
        """Transitions the lock to PROCESSED so genuine duplicates are rejected."""
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
        """
        Processes an SQS batch delivered by the Lambda event source mapping.

        Returns a partial-batch response ({"batchItemFailures": [...]}). The event
        source mapping deletes succeeded messages automatically and redrives only
        the reported failures, so this handler never deletes messages itself.
        """
        batch_item_failures = []

        for record in event.get('Records', []):
            message_id = record.get('messageId')
            receipt_handle = record.get('receiptHandle')

            if not message_id or not receipt_handle:
                logger.error("Invalid SQS record received: missing messageId or receiptHandle")
                continue

            # SQS maintains the authoritative redelivery counter; a custom message
            # attribute would never increment across redeliveries.
            try:
                receive_count = int(record.get('attributes', {}).get('ApproximateReceiveCount', '1'))
            except (ValueError, TypeError):
                receive_count = 1

            # 1. Idempotency guard: skip duplicates already in flight or completed.
            if not self._acquire_idempotency_lock(message_id):
                continue

            try:
                # 2. Business logic.
                self._execute_business_logic(record.get('body'))

                # 3. Success: mark processed. The event source mapping deletes the message.
                self._mark_processed(message_id)
                logger.info(f"Successfully processed message {message_id}")

            except Exception as e:
                logger.error(f"Processing failed for {message_id} (receive #{receive_count}): {e}")

                # Release the lock so the redelivery is retried rather than dropped.
                self._release_idempotency_lock(message_id)

                if receive_count >= MAX_RETRIES:
                    # Terminal failure: page on-call and let the mapping delete the
                    # message (omit it from failures) to stop the redrive loop.
                    logger.critical(f"Message {message_id} breached max retries. Escalating to SNS.")
                    try:
                        self.sns.publish(
                            TopicArn=self.alert_topic_arn,
                            Message=f"DLQ Remediation Failed permanently for message: {message_id}",
                            Subject="DLQ Max Retries Breached"
                        )
                    except ClientError as se:
                        # Keep the message in the queue if the alert can't be sent, so the
                        # escalation is retried once SNS recovers rather than silently lost.
                        logger.error(f"Failed to publish max-retry alert for {message_id}: {se}")
                        batch_item_failures.append({"itemIdentifier": message_id})
                else:
                    # Apply full-jitter exponential backoff via the message's
                    # visibility timeout, then report it as a batch failure so the
                    # mapping redrives only this message after the backoff window.
                    delay_seconds = max(1, int(calculate_exponential_backoff(receive_count)))
                    logger.info(f"Applying backoff of {delay_seconds}s for {message_id}")
                    try:
                        self.sqs.change_message_visibility(
                            QueueUrl=self.dlq_url,
                            ReceiptHandle=receipt_handle,
                            VisibilityTimeout=delay_seconds
                        )
                    except ClientError as ce:
                        logger.error(f"Failed to set backoff visibility for {message_id}: {ce}")

                    batch_item_failures.append({"itemIdentifier": message_id})

        return {"batchItemFailures": batch_item_failures}

    def _execute_business_logic(self, payload):
        """Simulates the downstream operation that might fail during an outage."""
        logger.info("Executing remediation logic against downstream systems...")
        # Add actual database or API logic here.
        pass


# Instantiate the processor globally so it is reused across warm starts
processor = EnterpriseDLQProcessor(
    sqs=sqs_client,
    dynamodb=dynamodb_client,
    sns=sns_client,
    table_name=TABLE_NAME,
    dlq_url=DLQ_URL,
    alert_topic_arn=SNS_TOPIC_ARN
)


def lambda_handler(event, context):
    """
    AWS Lambda entry point. Returns a partial-batch response so the SQS event
    source mapping (configured with ReportBatchItemFailures) only redrives the
    messages that actually failed.
    """
    logger.info(f"Received batch of {len(event.get('Records', []))} messages")
    return processor.process_sqs_event(event)
