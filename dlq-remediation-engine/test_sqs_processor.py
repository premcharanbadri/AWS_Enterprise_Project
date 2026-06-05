import os
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

# Ensure required configuration is present before the module instantiates its
# boto3 clients and runs its startup validation.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("DLQ_URL", "https://mock-queue")
os.environ.setdefault("ALERT_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:mock-topic")

from sqs_processor import EnterpriseDLQProcessor

DLQ_URL = "https://mock-queue"
TOPIC_ARN = "arn:aws:sns:us-east-1:123456789012:mock-topic"


def make_processor(sqs=None, dynamodb=None, sns=None):
    return EnterpriseDLQProcessor(
        sqs=sqs or MagicMock(),
        dynamodb=dynamodb or MagicMock(),
        sns=sns or MagicMock(),
        table_name="mock-idempotency-table",
        dlq_url=DLQ_URL,
        alert_topic_arn=TOPIC_ARN,
    )


def sqs_event(message_id, receipt_handle, receive_count):
    """Builds a Lambda SQS event record using the keys AWS actually delivers."""
    return {
        "Records": [
            {
                "messageId": message_id,
                "receiptHandle": receipt_handle,
                "body": "{}",
                "attributes": {"ApproximateReceiveCount": str(receive_count)},
                "messageAttributes": {},
            }
        ]
    }


def conditional_check_failed():
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
    )


def test_idempotency_duplicate_rejection():
    """A duplicate delivery fails the conditional write and is skipped silently."""
    dynamo = MagicMock()
    dynamo.put_item.side_effect = conditional_check_failed()
    sqs = MagicMock()

    processor = make_processor(sqs=sqs, dynamodb=dynamo)
    result = processor.process_sqs_event(sqs_event("123", "abc", 1))

    # No failure reported -> the event source mapping deletes the duplicate.
    assert result == {"batchItemFailures": []}
    sqs.delete_message.assert_not_called()
    sqs.change_message_visibility.assert_not_called()


def test_successful_processing_marks_idempotent():
    """Happy path: lock acquired, work done, record marked PROCESSED, no redrive."""
    dynamo = MagicMock()
    sqs = MagicMock()

    processor = make_processor(sqs=sqs, dynamodb=dynamo)
    result = processor.process_sqs_event(sqs_event("777", "ghi", 1))

    assert result == {"batchItemFailures": []}
    dynamo.update_item.assert_called_once()  # marked PROCESSED
    sqs.delete_message.assert_not_called()  # mapping handles deletion


def test_transient_failure_applies_backoff_and_reports_failure():
    """A retryable failure releases the lock, sets a backoff, and is redriven."""
    dynamo = MagicMock()
    sqs = MagicMock()

    processor = make_processor(sqs=sqs, dynamodb=dynamo)
    processor._execute_business_logic = MagicMock(side_effect=RuntimeError("downstream down"))

    result = processor.process_sqs_event(sqs_event("444", "def", 2))

    assert result == {"batchItemFailures": [{"itemIdentifier": "444"}]}
    dynamo.delete_item.assert_called_once()  # lock released for retry
    sqs.change_message_visibility.assert_called_once()
    _, kwargs = sqs.change_message_visibility.call_args
    assert kwargs["QueueUrl"] == DLQ_URL
    assert kwargs["ReceiptHandle"] == "def"
    assert kwargs["VisibilityTimeout"] >= 1


def test_critical_sre_escalation():
    """At MAX_RETRIES the message is escalated to SNS and not redriven."""
    dynamo = MagicMock()
    sqs = MagicMock()
    sns = MagicMock()

    processor = make_processor(sqs=sqs, dynamodb=dynamo, sns=sns)
    processor._execute_business_logic = MagicMock(side_effect=RuntimeError("downstream down"))

    result = processor.process_sqs_event(sqs_event("999", "xyz", 5))

    # Escalated terminal failures are omitted from failures so the mapping deletes them.
    assert result == {"batchItemFailures": []}
    sns.publish.assert_called_once()
    sqs.change_message_visibility.assert_not_called()
    dynamo.delete_item.assert_called_once()  # lock released


def test_escalation_failure_is_redriven():
    """If the SNS alert can't be published, the message is reported as a failure."""
    dynamo = MagicMock()
    sqs = MagicMock()
    sns = MagicMock()
    sns.publish.side_effect = ClientError(
        {"Error": {"Code": "Throttling"}}, "Publish"
    )

    processor = make_processor(sqs=sqs, dynamodb=dynamo, sns=sns)
    processor._execute_business_logic = MagicMock(side_effect=RuntimeError("downstream down"))

    result = processor.process_sqs_event(sqs_event("888", "uvw", 5))

    # Reported as a failure so the mapping redrives it once SNS recovers.
    assert result == {"batchItemFailures": [{"itemIdentifier": "888"}]}
    sns.publish.assert_called_once()


def test_invalid_record_is_skipped():
    """A malformed record without ids is logged and skipped without raising."""
    processor = make_processor()
    result = processor.process_sqs_event({"Records": [{"body": "{}"}]})
    assert result == {"batchItemFailures": []}
