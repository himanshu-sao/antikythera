import requests
import time
import json

BASE_URL = "http://localhost:8080"

def test_full_api_stack():
    print("🚀 Starting Full API Stack Integration Test...")
    
    # 1. Health Check
    try:
        r = requests.get(f"{BASE_URL}/health")
        print(f"Health Check: {'✅' if r.status_code == 200 else '❌'} ({r.status_code})")
    except Exception as e:
        print(f"Health Check: ❌ Exception: {e}")
        return

    # 2. Integrations Hub Test
    print("\nTesting Integration Hub...")
    try:
        # Add Integration
        res = requests.post(f"{BASE_URL}/api/integrations/", json={
            "name": "audit_github",
            "type": "native",
            "config": {"adapter_module": "api.adapters.github"}
        })
        print(f"Add Integration: {'✅' if res.status_code == 200 else '❌'} ({res.status_code})")
        
        # Store Secret
        res = requests.post(f"{BASE_URL}/api/integrations/secrets", json={
            "profile_id": "audit_github",
            "secrets": {"token": "audit_token_123"}
        })
        print(f"Store Secret: {'✅' if res.status_code == 200 else '❌'} ({res.status_code})")
        
        # List Integrations
        res = requests.get(f"{BASE_URL}/api/integrations/")
        print(f"List Integrations: {'✅' if res.status_code == 200 else '❌'} ({res.status_code})")
    except Exception as e:
        print(f"Integration Hub: ❌ Exception: {e}")

    # 3. Workflow Builder Test
    print("\nTesting Workflow Builder...")
    try:
        res = requests.post(f"{BASE_URL}/api/builder/generate", json={
            "prompt": "I want a github workflow that triggers on merge and runs a build",
            "template_name": "Audit Template"
        })
        print(f"AI Generation: {'✅' if res.status_code == 200 else '❌'} ({res.status_code})")
        template_data = res.json()
        
        # Validate generated template
        res = requests.post(f"{BASE_URL}/api/builder/validate", json={"template_data": template_data})
        print(f"Template Validation: {'✅' if res.status_code == 200 else '❌'} ({res.status_code})")
    except Exception as e:
        print(f"Workflow Builder: ❌ Exception: {e}")

    # 4. Board Virtualization Test
    print("\nTesting Virtual Boards...")
    try:
        # We need a template to test virtual board. Let's use the one we generated.
        # Mocking save template
        template_id = "audit_test_tpl"
        requests.post(f"{BASE_URL}/api/workflows/templates", json={
            "template_id": template_id,
            **template_data
        })
        
        res = requests.get(f"{BASE_URL}/api/boards/virtual/{template_id}")
        print(f"Virtual Board Fetch: {'✅' if res.status_code == 200 else '❌'} ({res.status_code})")
    except Exception as e:
        print(f"Virtual Board: ❌ Exception: {e}")

    # 5. Trigger System Test
    print("\nTesting Trigger System...")
    try:
        res = requests.post(f"{BASE_URL}/api/triggers/webhook/github", json={
            "number": 123,
            "action": "closed",
            "merged": True
        })
        print(f"Webhook Trigger: {'✅' if res.status_code == 200 else '❌'} ({res.status_code})")
    except Exception as e:
        print(f"Trigger System: ❌ Exception: {e}")

    print("\n--- Audit Complete ---")

if __name__ == "__main__":
    test_full_api_stack()
