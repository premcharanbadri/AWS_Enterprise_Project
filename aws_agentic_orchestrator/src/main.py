from src.agent_graph import aegis_engine

if __name__ == "__main__":
    print("=== Booting Aegis Orchestrator ===")
    
    # Test 1: First time asking the question (Cache Miss)
    task_1 = {"task": "Analyze Q3 revenue projections for European markets."}
    print("\n[Executing Run 1]")
    result_1 = aegis_engine.invoke(task_1)
    print(f"Final Output: {result_1['final_output']}")
    
    # Test 2: Asking a semantically similar question (Cache Hit)
    # Notice the wording is different, but the mathematical meaning is the same.
    task_2 = {"task": "Examine the third quarter revenue forecasts for Europe."}
    print("\n[Executing Run 2]")
    result_2 = aegis_engine.invoke(task_2)
    print(f"Final Output: {result_2['final_output']}")