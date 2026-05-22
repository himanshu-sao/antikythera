import os
import sys
from dotenv import load_dotenv

# Load .env at the very beginning so os.getenv works throughout the script
load_dotenv()

# Add current directory to sys.path to allow importing from 'agents'
sys.path.append(os.getcwd())

from agents.llm_client import LLMClient

def test_tester_integration():
    print("--- Tester AI Integration Test ---")
    
    # Check if Google API Key is present in env
    google_key = os.getenv("GOOGLE_API_KEY")
    if not google_key:
        print("ERROR: GOOGLE_API_KEY not found in environment variables.")
        return False
    else:
        print(f"SUCCESS: Found GOOGLE_API_KEY (length: {len(google_key)})")

    # Create a dummy spec and arch for testing
    test_id = "TEST-TEST-001"
    test_dir = os.path.join(os.getcwd(), "automation-ideas", "requirements", test_id)
    os.makedirs(test_dir, exist_ok=True)
    
    spec_path = os.path.join(test_dir, "spec.md")
    arch_path = os.path.join(test_dir, "architecture.md")
    
    with open(spec_path, "w") as f:
        f.write("# Spec\n\n## Overview\nTest spec.\n\n## Requirements\n- Req 1\n\n## Scope\n- Scope 1\n\n## Edge Cases\n- Edge 1\n\n## Constraints\n- Const 1\n\n## PII / Secret Handling Notes\n- None")
    
    with open(arch_path, "w") as f:
        f.write("# Arch\n\n## Architecture Diagram\n```mermaid\ngraph TD\nA --> B\n```\n\n## Tech Stack Decisions\n- Python\n\n## Risk Flags\n- Low\n\n## Dry-Run Notes\n- None\n\n## Constraints and Assumptions\n- None")

    try:
        print("Initializing LLMClient...")
        config_path = os.path.join(os.getcwd(), "config.yaml")
        client = LLMClient(config_path=config_path)
        client.model = "gemma-4-26b-a4b-it"
        print(f"Client initialized with model: {client.model}")

        from agents.tester import tester_idea
        print(f"Running tester_idea for {test_id}...")
        confidence = tester_idea(test_id)
        
        print(f"Tester confidence: {confidence}")

        # Verify file creation
        test_path = os.path.join(test_dir, "tests.md")
        if os.path.exists(test_path):
            print(f"SUCCESS: tests.md created at {test_path}")
            with open(test_path, "r") as f:
                content = f.read()
                print("\n--- Generated Test Plan Content (Preview) ---")
                print(content[:300] + "...")
                
                if "given" in content.lower() and "when" in content.lower() and "then" in content.lower():
                    print("SUCCESS: 'Given/When/Then' format found in content.")
                else:
                    print("FAILED: 'Given/When/Then' format NOT found in content.")
            
            if confidence > 0:
                print("\nTEST RESULT: PASSED ✅")
                return True
            else:
                print("\nTEST RESULT: FAILED ❌ (Low confidence)")
                return False
        else:
            print(f"FAILED: tests.md NOT found at {test_path}")
            return False

    except Exception as e:
        print(f"\nTEST RESULT: FAILED ❌ (Exception occurred)")
        print(f"Error details: {str(e)}")
        return False
    finally:
        # Cleanup
        import shutil
        if os.path.exists(os.path.join(os.getcwd(), "automation-ideas", "requirements", "TEST-TEST-001")):
             shutil.rmtree(os.path.join(os.getcwd(), "automation-ideas", "requirements", "TEST-TEST-001"))
             print("Cleanup complete.")

if __name__ == "__main__":
    success = test_tester_integration()
    sys.exit(0 if success else 1)
