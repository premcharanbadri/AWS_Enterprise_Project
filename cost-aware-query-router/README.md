# AWS Enterprise Backend & Distributed Systems

Read the deployed documentation here:

* [System 3: Cost-Aware Federated Query Router](https://premcharanbadri.github.io/AWS_Enterprise_Project/cost-aware-query-router/index_query_router.html)


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