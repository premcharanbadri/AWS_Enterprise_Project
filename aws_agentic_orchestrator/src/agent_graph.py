from typing import Optional, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.semantic_cache import PrivacyAwareCache
from src.warehouse import run_revenue_analysis, snowflake_is_configured

# State passed between nodes and persisted by the checkpointer.
class AgentState(TypedDict):
    task: str
    cached_response: Optional[str]
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

def run_data_analysis(state: AgentState) -> AgentState:
    """Node 2: Runs only on a cache miss. Queries Snowflake for the real numbers."""
    print("--- Node: Running Data Analysis on Snowflake ---")

    if snowflake_is_configured():
        try:
            analysis = run_revenue_analysis()
        except Exception as error:
            # Degrade gracefully so a warehouse outage doesn't crash the agent.
            analysis = f"Could not reach Snowflake: {error}"
    else:
        analysis = (
            "Snowflake credentials are not set, so no live query ran. "
            "Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER and SNOWFLAKE_PASSWORD to enable it."
        )

    # Cache the result so a similar question skips the warehouse next time.
    cache_layer.store_cache(state["task"], analysis)

    state["final_output"] = analysis
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
    return "run_analysis"

# Build the Execution Graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("cache_check", check_privacy_cache)
workflow.add_node("run_analysis", run_data_analysis)
workflow.add_node("process_cached", process_cached_result)

# Define the Edges
workflow.set_entry_point("cache_check")
workflow.add_conditional_edges(
    "cache_check",
    determine_routing,
    {
        "run_analysis": "run_analysis",
        "process_cached": "process_cached"
    }
)

# Route everything to END
workflow.add_edge("run_analysis", END)
workflow.add_edge("process_cached", END)

# Compile with a checkpointer so run state is persisted and can be resumed by thread_id after a restart.
checkpointer = MemorySaver()
aws_engine = workflow.compile(checkpointer=checkpointer)