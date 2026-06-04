# [AWS Enterprise Backend & Distributed Systems](https://premcharanbadri.github.io/AWS_Enterprise_Project/)

This repository contains four backend systems built to solve common enterprise infrastructure problems: managing distributed failures, securing internal data access, optimizing database compute costs, and making AI stateful and cost-efficient. The focus across these projects is fault tolerance, security, and algorithmic efficiency.

## Implemented Architecture

To provide the complete logic, infrastructure trade-offs, and business value of this portfolio, I have published detailed architectural reviews for each core system. 

Read the full individual documentation here:

* [System 1: Distributed DLQ Auto-Remediation Engine](https://premcharanbadri.github.io/AWS_Enterprise_Project/dlq-remediation-engine/index_dlq.html)
* [System 2: Zero-Trust Data Mesh Proxy](https://premcharanbadri.github.io/AWS_Enterprise_Project/zero-trust-proxy-java/index_proxy.html)
* [System 3: Cost-Aware Federated Query Router](https://premcharanbadri.github.io/AWS_Enterprise_Project/cost-aware-query-router/index_query_router.html)
* [System 4: AWS Agentic Orchestrator](https://premcharanbadri.github.io/AWS_Enterprise_Project/aws_agentic_orchestrator/index_agent.html)


---

_Here below I explained what steps are needed to run these projects in your local system. To learn about the individual project, click on any of the links above:_

#### These projects I built are not novel, here is one of my colleague's question after reviewing my projects:

#### _Are these "novel" problems?_
_"These problems seem solved, are these novel projects or did you replicate them?"_

To be honest, they are not novel. They are fundamental patterns commonly found in an enterprise. For a start-up, "novel" product features are very significant and encouraged,  but massive tech companies like AWS reward engineers for understanding in-depth on how to implement such foundational, solved problems safely from scratch, while emphasizing the knowledge and skill behind these implementations - network security, payload manipulation, etc., rather than just knowing how to buy a vendor tool that does it for me.

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
    
*   **Partial-Batch Tuning:** The SQS trigger already processes batches of 10 and reports per-message failures (`ReportBatchItemFailures`) so a single bad message doesn't redrive the whole batch. Next, tune `maxReceiveCount` and a true terminal DLQ for poison-pill messages.
    

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

## System 4: Aegis Agentic Orchestrator

A Python-based orchestrator that wraps autonomous AI agents in a stateful, cost-saving infrastructure layer.

### Why I Built This

Deploying AI in an enterprise has two major bottlenecks: volatile execution state and massive API costs from redundant queries.

I built the agent as a LangGraph state machine compiled with a checkpointer, so run state is persisted by `thread_id` and can be resumed after a restart. The local MVP uses an in-memory checkpointer; in production the same interface is backed by a durable store (e.g. DynamoDB) and orchestrated by AWS Step Functions. To cut token costs, I added a local semantic cache using an open-source embedding model and Redis. It intercepts mathematically similar prompts and returns cached answers without making external API calls, keeping corporate data safely inside the firewall.

### Tech Stack

*   **Language:** Python 3.11
    
*   **Infrastructure:** LangGraph, Amazon ElastiCache (Redis), local HuggingFace embeddings
    

### Running It Locally

Ensure you have a local Redis instance running.

#### Bash

    cd aws_agentic_orchestrator
    source venv/bin/activate
    pip install -r requirements.txt
    
    # Execute the local orchestrator as a module (resolves the `src` package)
    python -m src.main
