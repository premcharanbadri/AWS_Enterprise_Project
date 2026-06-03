# AWS Backend & Distributed Systems Project

This repository contains three backend projects I built to handle common infrastructure challenges: managing message queue failures, securing internal data access, and optimizing database query routing. The main focus across these systems is fault tolerance, security, and algorithmic efficiency.

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
    
*   **Batch Processing:** Update the SQS trigger to process messages in batches of 10. This drastically cuts down on AWS API calls during major outages.
    

## System 2: Zero-Trust Data Mesh Proxy System

A Java proxy that sits between users and the database to enforce role-based access control and automatically mask sensitive information like PII.

### Why I Built This

Data analysts need to query production tables to do their jobs, but handing over direct database access usually means exposing highly sensitive PII to people who shouldn't see it.

I built this proxy to sit in the middle. It uses a Spring `OncePerRequestFilter` to check the user's JWT before the request goes anywhere near the business logic. If the user is an analyst, an in-memory Data Loss Prevention (DLP) service uses compiled regex to scrub things like SSNs out of the JSON response. If the user is a system admin, the security logic bypasses the filter and returns the raw data.

### Tech Stack

*   **Language/Framework:** Java 21, Spring Boot 3.2
    
*   **Infrastructure:** Maven, Docker, Tomcat
    

### Running It Locally

You will need Java 21 and Maven installed.

#### Bash

    cd zero-trust-proxy-java
    
    # Run the unit tests for the DLP masking engine
    mvn clean test
    
    # Start the local Tomcat server
    mvn spring-boot:run

To test the routing and masking, open another terminal and send a few curl requests:

#### Bash

    # Test 1: No token (Should be rejected with 401 Unauthorized)
    curl -X POST http://localhost:8080/api/v1/mesh/query \
      -H "Content-Type: application/json" \
      -d '{"targetTable": "customers", "sqlStatement": "SELECT * FROM customers"}'
    
    # Test 2: Analyst token (Should return 200 OK, but SSNs will be masked)
    curl -X POST http://localhost:8080/api/v1/mesh/query \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer MOCK_ANALYST_TOKEN" \
      -d '{"targetTable": "customers", "sqlStatement": "SELECT name, ssn FROM customers"}'

### Next Steps for Scaling to Production

*   **Containerization:** Deploy the included Dockerfile to AWS ECS (Fargate) so it runs as a serverless container.
    
*   **Real Auth:** Swap out the dummy JWT decoder for real RS256 cryptographic validation tied to an AWS Cognito JWKS endpoint.
    

## System 3: Cost-Aware Federated Query Router

A C++ routing engine that reads incoming SQL queries, estimates how heavy they are, and sends them to the right database to save on compute costs.

### Why I Built This

Running massive analytical joins (OLAP) on standard transactional databases (OLTP) like Postgres usually locks up tables and degrades performance for everyone else. On the flip side, sending basic single-row lookups to an expensive data warehouse wastes premium compute credits.

I built this interceptor to look at the raw SQL string and search for analytical keywords. It uses a mathematical heuristic to assign a compute weight to the query. Based on that score, it routes lightweight row lookups to Amazon RDS (PostgreSQL), standard aggregations to AWS Athena, and the heaviest columnar joins to Snowflake.

### Tech Stack

*   **Language:** C++17
    
*   **Architecture:** Strategy Pattern, memory management via `std::unique_ptr`, heuristic cost calculation
    

### Running It Locally

Make sure `g++` and `make` are installed on your machine.

#### Bash

    cd cost-aware-query-router
    
    # Compile the project
    make
    
    # Run the local routing simulation
    ./query_router

### Next Steps for Scaling to Production

*   **AST Parsing:** We can eliminate the regex parser and use a real Abstract Syntax Tree (AST) parser to build out actual execution plans before making routing decisions.
    
*   **gRPC Integration:** Convert the router into a gRPC microservice so other applications can ping it for routing decisions with microsecond latency.