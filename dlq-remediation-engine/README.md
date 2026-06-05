# AWS Enterprise Backend & Distributed Systems

Read the system documentation here:

* [System 1: Distributed DLQ Auto-Remediation Engine](https://premcharanbadri.github.io/AWS_Enterprise_Project/dlq-remediation-engine/index_dlq.html)

<img width="430" height="725" alt="image" src="https://github.com/user-attachments/assets/dc93f0be-08cb-4413-ba4e-22502bdbe311" />


## System 1: Distributed DLQ Auto-Remediation System

An event-driven serverless pipeline that handles distributed system failures, prevents retry spikes, and ensures messages are processed exactly once.

### Why I Built This

When a downstream database goes offline, you usually have thousands of failing microservices trying to retry their requests. If they all retry at the exact same time when the database comes back, they can accidentally take it down again. On top of that, network blips can cause AWS to deliver the same message twice, which breaks transactional data.

To handle this, I wrote a Python system that uses a Full Jitter exponential backoff algorithm to randomize retry delays and smooth out the traffic spikes. To prevent duplicate processing, it uses DynamoDB conditional writes as a distributed lock (idempotency guard). Finally, to keep compute costs at zero during wait states, it relies on SQS visibility timeouts instead of keeping threads paused.

### Tech Stack

*   **Language:** Python 3.10
    
*   **Infrastructure:** AWS SAM, Amazon SQS, AWS Lambda, Amazon DynamoDB, Amazon SNS
    

### Running It Locally

Make sure you have an active Python virtual environment and `pytest` installed.

#### Bash

    cd dlq-remediation-engine
    source venv/bin/activate
    pip install -r requirements.txt
    
    # Run the mocked AWS integration tests
    pytest test_sqs_processor.py -v

### Next Steps for Scaling to Production

*   **Network Isolation:** Move the Lambda function into a private VPC using AWS PrivateLink so the payloads never hit the public internet.
    
*   **Partial-Batch Tuning:** The SQS trigger already processes batches of 10 and reports per-message failures (`ReportBatchItemFailures`) so a single bad message doesn't redrive the whole batch. Next, tune `maxReceiveCount` and a true 
