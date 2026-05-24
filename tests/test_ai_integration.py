import os
import sys
from dotenv import load_dotenv

# Load .env at the very beginning so os.getenv works throughout the script
load_dotenv()

# Add current directory to sys.path to allow importing from 'agents'
sys.path.append(os.getcwd())

from agents.llm_client import LLMClient

def test_llm_with_gemma_4():
    print("--- AI Integration Test (Gemma 4) ---")
    
    # Check if Google API Key is present in env
    google_key = os.getenv("GOOGLE_API_KEY_KANBAN")
    if not google_key:
        print("ERROR: GOOGLE_API_KEY_KANBAN not found in environment variables.")
        return False
    else:
        print(f"SUCCESS: Found GOOGLE_API_KEY_KANBAN (length: {len(google_key)})")
    
    # Try both 26B and 31B if the first one fails
    models_to_try = ["gemma-4-26b-a4b-it", "gemma-4-31b-it"]
    
    for model_name in models_to_try:
        print(f"\n>>> Attempting with model: {model_name}")
        try:
            print("Initializing LLMClient...")
            config_path = os.path.join(os.getcwd(), "config.yaml")
            client = LLMClient(config_path=config_path)
            client.model = model_name
            print(f"Client initialized with model: {client.model}")

            print("Sending test prompt: 'What is 2 + 2?'")
            response = client.chat(
                system_prompt="You are a helpful assistant. Answer very briefly.",
                user_prompt="What is 2 + 2?"
            )
            
            print(f"AI Response: {response}")
            
            if "4" in response:
                print(f"TEST RESULT: PASSED ✅ for {model_name}")
                return True
            else:
                print(f"TEST RESULT: FAILED ❌ for {model_name} (Unexpected response)")
        
        except Exception as e:
            print(f"TEST RESULT: FAILED ❌ for {model_name}")
            print(f"Error details: {str(e)}")
            # If it's a quota error (429), we probably won't succeed with the next one either
            if "429" in str(e):
                print("Detected 429 (Quota Exceeded). Stopping tests.")
                break
            print("Moving to next model...")

    print("\nALL ATTEMPTS FAILED.")
    return False

if __name__ == "__main__":
    success = test_llm_with_gemma_4()
    sys.exit(0 if success else 1)
