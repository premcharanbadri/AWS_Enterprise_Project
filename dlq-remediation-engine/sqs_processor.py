import os
import boto3
from backoff_algorithm import calculate_exponential_backoff

class SQSDeadLetterQueueProcessor:
    """
    Enterprise-grade SQS consumer built on OOP principles.
    Handles message pooling from a Dead-Letter Queue and executes
    idempotent remediation workflows with exponential backoff routing.
    """
    def __init__(self, queue_url=None, aws_region="us-east-1"):
        # OOP Design Pattern: Encapsulate infrastructure variables
        self.queue_url = queue_url or os.getenv("AWS_SQS_DLQ_URL")
        self.sqs_client = boto3.client("sqs", region_name=aws_region)

    def fetch_failed_events(self, max_messages=1):
        """Polls SQS for dead events using long-polling to minimize network costs."""
        if not self.queue_url:
            raise ValueError("Infrastructure Error: SQS Queue URL target is completely unconfigured.")
            
        response = self.sqs_client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=20,  # AWS Long-Polling optimization to reduce API overhead costs
            MessageAttributeNames=['All']
        )
        return response.get("Messages", [])

    def process_and_route(self, message):
        """Processes an individual failed transaction message and tracks its retry tier."""
        try:
            # Parse message attributes to find out what attempt number this event is on
            msg_attributes = message.get("MessageAttributes", {})
            retry_count = int(msg_attributes.get("RetryCount", {}).get("StringValue", 1))
            
            # Execute our encapsulated backoff calculation
            calculated_delay = calculate_exponential_backoff(retry_count)
            
            # Business Logic Check: If it has failed over 5 times, escalate to an SRE alert bucket
            if retry_count >= 5:
                return "ESCALATE_TO_SRE_ALERT"
                
            return f"REQUEUE_WITH_DELAY_{calculated_delay}S"
            
        except Exception as e:
            # Pragmatic Programmer: "Crash Early" / Explicit error logging
            print(f"Operational Logging: Failed to decode transaction payload. Error: {str(e)}")
            return "ROUTE_TO_CRITICAL_MALFORMED_LOG"