import pytest
from unittest.mock import MagicMock, patch
from sqs_processor import SQSDeadLetterQueueProcessor

@patch("boto3.client")
def test_sqs_long_polling_handshake(mock_boto_client):
    """
    Validates that our microservice executes optimal long-polling configuration 
    to manage AWS infrastructure costs efficiently.
    """
    # 1. Create a fake SQS client mock
    mock_sqs = MagicMock()
    mock_boto_client.return_value = mock_sqs
    mock_sqs.receive_message.return_value = {"Messages": [{"MessageId": "1", "Body": "Fake Transaction"}]}
    
    # 2. Instantiate our system under test passing a mock URL
    processor = SQSDeadLetterQueueProcessor(queue_url="https://sqs.us-east-1.amazonaws.com/1234/mock-dlq")
    messages = processor.fetch_failed_events()
    
    # 3. Structural Assertions: Prove that the code used AWS best practices (WaitTimeSeconds=20)
    mock_sqs.receive_message.assert_called_once_with(
        QueueUrl="https://sqs.us-east-1.amazonaws.com/1234/mock-dlq",
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20,
        MessageAttributeNames=['All']
    )
    assert len(messages) == 1

def test_critical_retry_escalation_logic():
    """Validates that a message failing 5 times breaks execution containment and flags an SRE."""
    processor = SQSDeadLetterQueueProcessor(queue_url="https://fake-url")
    
    # Inject a mock message that has already hit a heavy failure cycle
    mock_high_failure_msg = {
        "MessageId": "999",
        "MessageAttributes": {
            "RetryCount": {"DataType": "Number", "StringValue": "5"}
        }
    }
    
    route_action = processor.process_and_route(mock_high_failure_msg)
    assert route_action == "ESCALATE_TO_SRE_ALERT"