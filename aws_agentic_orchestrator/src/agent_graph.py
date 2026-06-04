from typing import Dict, TypedDict
from langgraph.graph import StateGraph, END
from src.semantic_cache import PrivacyAwareCache

# Define the state that will be passed between nodes (and saved to DynamoDB later)
class AgentState(TypedDict):
    task: str
    cached_response: str
    final_output: str
    status: str

# Initialize our local cache
cache_layer = PrivacyAwareCache()

def check_privacy_cache(state: AgentState) -> AgentState:
    """Node 1: Intercept the task and check local memory."""
    print(f"\n--- Node: Checking Cache for '{state['task']}' ---")
    
    cached_result = cache_layer.check_cache(state["task"])
    
    if cached_result:
        state["cached_response"] = cached_result
        state["status"] = "CACHE_HIT"
    else:
        state["cached_response"] = None
        state["status"] = "CACHE_MISS"
        
    return state

def external_llm_execution(state: AgentState) -> AgentState:
    """Node 2: Only executes if cache misses. Simulates external API call."""
    print("--- Node: Executing External LLM (Simulated) ---")
    
    # In reality, this is where you call an external model.
    simulated_response = f"Simulated complex analysis for: {state['task']}"
    
    # Store the new result in our local cache to protect future queries
    cache_layer.store_cache(state["task"], simulated_response)
    
    state["final_output"] = simulated_response
    return state

def process_cached_result(state: AgentState) -> AgentState:
    """Node 3: Formats the output immediately if cache was hit."""
    print("--- Node: Processing Cached Result ---")
    state["final_output"] = state["cached_response"]
    return state

def determine_routing(state: AgentState) -> str:
    """Conditional Edge: Determines where to route based on cache status."""
    if state["status"] == "CACHE_HIT":
        return "process_cached"
    return "execute_external"

# Build the Execution Graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("cache_check", check_privacy_cache)
workflow.add_node("external_execution", external_llm_execution)
workflow.add_node("process_cached", process_cached_result)

# Define the Edges
workflow.set_entry_point("cache_check")
workflow.add_conditional_edges(
    "cache_check",
    determine_routing,
    {
        "execute_external": "external_execution",
        "process_cached": "process_cached"
    }
)

# Route everything to END
workflow.add_edge("external_execution", END)
workflow.add_edge("process_cached", END)

# Compile the engine
aegis_engine = workflow.compile()