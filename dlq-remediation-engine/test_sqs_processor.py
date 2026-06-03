import os
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

# 1. We must mock the environment variables BEFORE importing the processor,
# otherwise the __init__ fail-safe will crash the test.
os.environ["AWS_SQS_DLQ_URL"] = "https://mock-queue"
os.environ["DYNAMODB_IDEMPOTENCY_TABLE"] = "mock-idempotency-table"
os.environ["SNS_ALERT_TOPIC_ARN"] = "arn:aws:sns:mock-region:1234:mock-topic"

from sqs_processor import EnterpriseDLQProcessor

@patch("boto3.client")
def test_idempotency_duplicate_rejection(mock_boto):
    """Proves the system safely ignores duplicate events using DynamoDB conditional checks."""
    # Setup the mock DynamoDB to simulate a "ConditionalCheckFailedException" (Lock already exists)
    mock_dynamo = MagicMock()
    mock_dynamo.put_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException"}}, 
        "PutItem"
    )
    
    # Configure boto3.client to return our rigged DynamoDB mock
    mock_boto.side_effect = lambda service_name: mock_dynamo if service_name == "dynamodb" else MagicMock()
    
    processor = EnterpriseDLQProcessor()
    mock_message = {"MessageId": "123", "ReceiptHandle": "abc"}
    
    # Execute
    result = processor.process_failed_event(mock_message)
    
    # Assert
    assert result == "DUPLICATE_IGNORED"

@patch("boto3.client")
def test_critical_sre_escalation(mock_boto):
    """Proves that a message failing 5 times triggers an SRE page and deletes the message."""
    mock_sns = MagicMock()
    mock_sqs = MagicMock()
    mock_dynamo = MagicMock()
    
    def boto_router(service_name):
        if service_name == "sns": return mock_sns
        if service_name == "sqs": return mock_sqs
        if service_name == "dynamodb": return mock_dynamo
    
    mock_boto.side_effect = boto_router
    
    processor = EnterpriseDLQProcessor()
    
    # Inject a message that has failed 5 times
    mock_message = {
        "MessageId": "999", 
        "ReceiptHandle": "xyz",
        "MessageAttributes": {"RetryCount": {"StringValue": "5"}}
    }
    
    result = processor.process_failed_event(mock_message)
    
    # Assertions
    assert result == "ESCALATED_TO_SNS"
    mock_sns.publish.assert_called_once()
    mock_sqs.delete_message.assert_called_once_with(QueueUrl="https://mock-queue", ReceiptHandle="xyz")

@patch("boto3.client")
def test_zero_cost_visibility_delay(mock_boto):
    """Proves standard failed messages are delayed using visibility timeouts."""
    mock_sqs = MagicMock()
    mock_dynamo = MagicMock()
    
    # Ensure DynamoDB allows the lock (no exception raised)
    mock_dynamo.put_item.return_value = {}
    
    mock_boto.side_effect = lambda service: mock_sqs if service == "sqs" else mock_dynamo
    
    processor = EnterpriseDLQProcessor()
    
    # Message failing for the 2nd time
    mock_message = {
        "MessageId": "444", 
        "ReceiptHandle": "def",
        "MessageAttributes": {"RetryCount": {"StringValue": "2"}}
    }
    
    result = processor.process_failed_event(mock_message)
    
    assert "DELAYED_" in result
    mock_sqs.change_message_visibility.assert_called_once()