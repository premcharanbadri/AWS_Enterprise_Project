# AWS Enterprise Backend & Distributed Systems

Read the deployed documentation here:

* [System 2: Zero-Trust Data Mesh Proxy](https://premcharanbadri.github.io/AWS_Enterprise_Project/zero-trust-proxy-java/index_proxy.html)


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
    