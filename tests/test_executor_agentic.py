import os
import sys
from unittest.mock import MagicMock
from types import ModuleType

# 1. Add current directory to path FIRST
sys.path.append(os.getcwd())

# 2. Mock antikythera_tools (leaf)
mock_antikythera = ModuleType("antikythera_tools")
mock_antikythera.terminal = MagicMock()
mock_antikythera.write_file = MagicMock()
mock_antikythera.patch = MagicMock()
mock_antikythera.read_file = MagicMock()
sys.modules["antikythera_tools"] = mock_antikythera

# 3. Mock agents.llm_client (leaf)
mock_llm_instance = MagicMock()
mock_llm_module = ModuleType("agents.llm_client")
mock_llm_module.LLMClient = MagicMock(return_value=mock_llm_instance)
sys.modules["agents.llm_client"] = mock_llm_module

# Now import the REAL classes
from agents.executor import ExecutorAgent
from dotenv import load_dotenv
load_dotenv()

def test_executor_agentic_mocked():
    print("--- Executor Agent Mocked Logic Test ---")
    
    # Setup mock return values for the LLM
    # The planner calls .chat() and expects a string
    mock_llm_instance.chat.return_value = '[{"task": "test task", "type": "file_creation"}]'
    # The executor calls .chat() and expects a JSON string for tool call
    # We'll make the second call return the tool call
    mock_llm_instance.chat.side_effect = [
        '[{"task": "test task", "type": "file_creation"}]', # Planner call
        '{"tool": "write_file", "args": {"path": "test_file.txt", "content": "hello"}}' # Executor call
    ]

    # Create a dummy spec and arch for testing
    test_id = "TEST-MOCK-001"
    test_dir = os.path.join(os.getcwd(), "automation-ideas", "requirements", test_id)
    os.makedirs(test_dir, exist_ok=True)
    
    spec_path = os.path.join(test_dir, "spec.md")
    arch_path = os.path.join(test_dir, "architecture.md")
    
    with open(spec_path, "w") as f:
        f.write("# Spec\n\n## Overview\nTest spec.\n\n## Requirements\n- Req 1\n\n## Scope\n- Scope 1\n\n## Edge Cases\n- Edge 1\n\n## Constraints\n- Const 1\n\n## PII / Secret Handling Notes\n- None")
    
    with open(arch_path, "w") as f:
        f.write("# Arch\n\n## Architecture Diagram\n```mermaid\ngraph TD\nA --> B\n```\n\n## Tech Stack Decisions\n- Python\n\n## Risk Flags\n- Low\n\n## Dry-Run Notes\n- None\n\n## Constraints and Assumptions\n- None")

    try:
        print(f"Running executor_idea for {test_id}...")
        from agents.executor import executor_idea
        result = executor_idea(test_id)
        
        if result == 100:
            print("SUCCESS: executor_idea returned 100.")
        else:
            print(f"FAILED: executor_idea returned {result}.")
            return False

        # Verify tool calls
        print(f"Verifying tool calls... (write_file called: {mock_antikythera.write_file.called})")
        if not mock_antikythera.write_file.called:
            print("FAILED: write_file was never called!")
            return False
        
        # Verify the arguments passed to write_file
        args, kwargs = mock_antikythera.write_file.call_args
        print(f"Arguments passed to write_file: {args}")
        
        return True

    except Exception as e:
        print(f"TEST FAILED with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        import shutil
        if os.path.exists(os.path.join(os.getcwd(), "automation-ideas", "requirements", "TEST-MOCK-001")):
             shutil.rmtree(os.path.join(os.getcwd(), "automation-ideas", "requirements", "TEST-MOCK-001"))
             print("Cleanup complete.")

if __name__ == "__main__":
    success = test_executor_agentic_mocked()
    sys.exit(0 if success else 1)
