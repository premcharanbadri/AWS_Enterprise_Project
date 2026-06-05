# AWS Enterprise Backend & Distributed Systems

Read the System documentation here:

* [System 4: AWS Agentic Orchestrator](https://premcharanbadri.github.io/AWS_Enterprise_Project/aws_agentic_orchestrator/index_agent.html)

<img width="430" height="725" alt="image" src="https://github.com/user-attachments/assets/9a1444ed-aabe-48b9-b0ad-7521ec1848d6" />


## System 4: AWS Agentic Orchestrator

A Python-based orchestrator that wraps autonomous AI agents in a stateful, cost-saving infrastructure layer.

### Why I Built This

Deploying AI in an enterprise has two major bottlenecks: volatile execution state and massive API costs from redundant queries.

I built the agent as a LangGraph state machine compiled with a checkpointer, so run state is persisted by `thread_id` and can be resumed after a restart. The local MVP uses an in-memory checkpointer; in production the same interface is backed by a durable store (e.g. DynamoDB) and orchestrated by AWS Step Functions. To cut token costs, I added a local semantic cache using an open-source embedding model and Redis. It intercepts mathematically similar prompts and returns cached answers without making external API calls, keeping corporate data safely inside the firewall.

### Tech Stack

*   **Language:** Python 3.11
    
*   **Infrastructure:** LangGraph, Redis locally (Amazon ElastiCache in production), local HuggingFace embeddings
    

### Running It Locally

Ensure you have a local Redis instance running.

#### Bash

    cd aws_agentic_orchestrator
    source venv/bin/activate
    pip install -r requirements.txt
    
    # Execute the local orchestrator as a module (resolves the `src` package)
    python -m src.main
