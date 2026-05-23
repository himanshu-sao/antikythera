import os
import json
import sys
from datetime import datetime

# Setup paths
sys.path.append(os.getcwd())

from agents.orchestrator import get_orchestrator
from agents.state import load_state, save_state

def test_memory_agent_loop():
    print("--- Testing Memory Agent Loop ---")
    
    # 1. Setup: Create a fresh state with an item
    state = {
        "items": {
            "TEST-MEM-001": {
                "title": "Testing Memory Agent",
                "stage": "INTAKE",
                "priority": "high",
                "confidence_score": 0,
                "description": "A task to trigger the audit log and memory agent.",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "comments": [],
                "history": []
            }
        }
    }
    # Save to the actual state file
    from agents.state import STATE_FILE
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    
    print("Created dummy state with TEST-MEM-001.")

    # 2. Run the pipeline
    orchestrator = get_orchestrator()
    print("Starting pipeline...")
    orchestrator.run_pipeline()
    print("Pipeline run complete.")

    # 3. Wait a bit for any async processes (though our current agent is sync)
    # Actually, we need to trigger the Memory Agent manually to simulate the nightly loop
    print("Triggering Memory Agent loop manually...")
    from agents.memory import MemoryAgent
    from agents.llm_client import LLMClient
    import yaml
    
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    memory_agent = MemoryAgent(config_path="config.yaml")
    memory_agent.run_learning_loop()
    print("Memory Agent loop complete.")

    # 4. Verify patterns.md
    patterns_path = os.path.join(os.getcwd(), "automation-ideas", "brain", "patterns.md")
    print(f"Checking {patterns_path}...")
    
    if os.path.exists(patterns_path):
        with open(patterns_path, "r") as f:
            content = f.read()
            print("\n--- Current patterns.md content ---")
            print(content)
            print("------------------------------------\n")
            
            if "Learned on" in content:
                print("SUCCESS: Patterns were updated!")
            else:
                print("FAILED: No new patterns found in patterns.md.")
    else:
        print("FAILED: patterns.md does not exist!")

if __name__ == "__main__":
    test_memory_agent_loop()
