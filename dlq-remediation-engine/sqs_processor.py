import os
import json
import logging
import boto3
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
from backoff_algorithm import calculate_exponential_backoff

# Enterprise habit: Always use structured logging rather than basic print() statements
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class EnterpriseDLQProcessor:
    """
    AWS DLQ Processor built with enterprise transaction rigor.
    Utilizes DynamoDB for idempotency locks to prevent race conditions.
    """
    def __init__(self) -> None:
        # Initialize AWS Clients
        self.sqs = boto3.client("sqs")
        self.dynamodb = boto3.client("dynamodb")
        self.sns = boto3.client("sns")
        
        # Load Infrastructure Variables with fail-safes
        self.queue_url = os.environ.get("AWS_SQS_DLQ_URL")
        self.table_name = os.environ.get("DYNAMODB_IDEMPOTENCY_TABLE")
        self.sns_topic_arn = os.environ.get("SNS_ALERT_TOPIC_ARN")
        
        if not all([self.queue_url, self.table_name, self.sns_topic_arn]):
            logger.error("CRITICAL: Missing required infrastructure environment variables.")
            raise RuntimeError("Infrastructure misconfiguration.")

    def _acquire_idempotency_lock(self, message_id: str) -> bool:
        """
        Idempotency Guard: Ensures a transaction is processed exactly once.
        Analogous to an SAP ENQUEUE lock, but distributed via DynamoDB.
        """
        try:
            self.dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    'MessageId': {'S': message_id}, 
                    'Status': {'S': 'PROCESSING'}
                },
                ConditionExpression='attribute_not_exists(MessageId)'
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.warning(f"Lock Collision: Message {message_id} is already in flight. Aborting.")
                return False
            logger.error(f"DynamoDB connection fault: {str(e)}")
            raise e

    def process_failed_event(self, message: Dict[str, Any]) -> str:
        """Core business logic for routing and remediating failed events."""
        message_id = message.get('MessageId', 'UNKNOWN_ID')
        receipt_handle = message.get('ReceiptHandle')
        
        logger.info(f"Initiating remediation sequence for event: {message_id}")

        # 1. Enforce Idempotency (Prevent double-processing)
        if not self._acquire_idempotency_lock(message_id):
            return "DUPLICATE_IGNORED"

        # 2. Defensive Data Parsing (Analytics habit: never trust the payload)
        try:
            attributes = message.get('MessageAttributes', {})
            retry_count_str = attributes.get('RetryCount', {}).get('StringValue', '1')
            retry_count = int(retry_count_str)
        except (ValueError, TypeError) as e:
            logger.error(f"Payload Corruption: Invalid RetryCount for {message_id}. Err: {e}")
            return "FAULT_INVALID_PAYLOAD"

        # 3. Handle Critical Escalation (SRE Paging)
        if retry_count >= 5:
            logger.error(f"Max retries breached for {message_id}. Paging SRE team via SNS.")
            self.sns.publish(
                TopicArn=self.sns_topic_arn,
                Subject="CRITICAL: DLQ Event Remediation Failed",
                Message=f"Transaction {message_id} failed 5 times. Manual SRE intervention required."
            )
            self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt_handle)
            return "ESCALATED_TO_SNS"

        # 4. Zero-Cost Exponential Backoff
        delay_seconds = int(calculate_exponential_backoff(retry_count))
        
        try:
            self.sqs.change_message_visibility(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=delay_seconds
            )
            logger.info(f"Success: Delayed {message_id} for {delay_seconds}s at zero compute cost.")
            return f"DELAYED_{delay_seconds}S"
            
        except ClientError as e:
            logger.error(f"AWS API Fault: Failed to modify visibility timeout: {str(e)}")
            return "FAULT_AWS_API"
        
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Standard AWS Lambda Entry Point.
    Instantiates the Enterprise processor and iterates through the SQS event batch.
    """
    processor = EnterpriseDLQProcessor()
    results = []
    
    # AWS SQS batches messages inside a 'Records' array
    for record in event.get('Records', []):
        status = processor.process_failed_event(record)
        results.append({"MessageId": record.get('messageId', 'UNKNOWN'), "Status": status})
        
    logger.info(f"Batch processing complete. Results: {results}")
    return {"statusCode": 200, "body": json.dumps(results)}