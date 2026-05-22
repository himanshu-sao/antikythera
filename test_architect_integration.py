import os
import sys
from dotenv import load_dotenv

# Load .env at the very beginning so os.getenv works throughout the script
load_dotenv()

# Add current directory to sys.path to allow importing from 'agents'
sys.path.append(os.getcwd())

from agents.llm_client import LLMClient

def test_architect_integration():
    print("--- Architect AI Integration Test ---")
    
    # Check if Google API Key is present in env
    google_key = os.getenv("GOOGLE_API_KEY")
    if not google_key:
        print("ERROR: GOOGLE_API_KEY not found in environment variables.")
        return False
    else:
        print(f"SUCCESS: Found GOOGLE_API_KEY (length: {len(google_key)})")

    # Create a dummy spec for testing
    test_id = "TEST-ARCH-001"
    test_dir = os.path.join(os.getcwd(), "automation-ideas", "requirements", test_id)
    os.makedirs(test_dir, exist_ok=True)
    spec_path = os.path.join(test_dir, "spec.md")
    
    spec_content = f"""# Specification for {test_id}: Test Architecture Idea

## Overview
This is a test specification to verify the Architect Agent.

## Requirements
- Requirement 1
- Requirement 2

## Scope
- In scope: testing the architect.
- Out of scope: production deployment.

## Edge Cases
- Invalid input.

## Constraints
- Must be AI generated.

## PII / Secret Handling Notes
- No PII.
"""
    with open(spec_path, "w") as f:
        f.write(spec_content)

    try:
        print("Initializing LLMClient...")
        config_path = os.path.join(os.getcwd(), "config.yaml")
        client = LLMClient(config_path=config_path)
        client.model = "gemma-4-26b-a4b-it"
        print(f"Client initialized with model: {client.model}")

        from agents.architect import architect_idea
        print(f"Running architect_idea for {test_id}...")
        confidence = architect_idea(test_id)
        
        print(f"Architect confidence: {confidence}")

        # Verify file creation
        arch_path = os.path.join(test_dir, "architecture.md")
        if os.path.exists(arch_path):
            print(f"SUCCESS: architecture.md created at {arch_path}")
            with open(arch_path, "r") as f:
                content = f.read()
                print("\n--- Generated Architecture Content (Preview) ---")
                print(content[:300] + "...")
                
                if "mermaid" in content.lower() or "graph TD" in content:
                    print("SUCCESS: Mermaid diagram found in content.")
                else:
                    print("FAILED: No Mermaid diagram found in content.")
            
            if confidence > 0:
                print("\nTEST RESULT: PASSED ✅")
                return True
            else:
                print("\nTEST RESULT: FAILED ❌ (Low confidence)")
                return False
        else:
            print(f"FAILED: architecture.md NOT found at {arch_path}")
            return False

    except Exception as e:
        print(f"\nTEST RESULT: FAILED ❌ (Exception occurred)")
        print(f"Error details: {str(e)}")
        return False
    finally:
        # Cleanup
        import shutil
        if os.path.exists(os.path.join(os.getcwd(), "automation-ideas", "requirements", "TEST-ARCH-001")):
             shutil.rmtree(os.path.join(os.getcwd(), "automation-ideas", "requirements", "TEST-ARCH-001"))
             print("Cleanup complete.")

if __name__ == "__main__":
    success = test_architect_integration()
    sys.exit(0 if success else 1)
