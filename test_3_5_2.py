#!/usr/bin/env python3
"""
Quick verification test for Task 3.5.2: Execution Engine Updates
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault

# Setup
BASE_DIR = os.path.abspath('test_data')
os.makedirs(BASE_DIR, exist_ok=True)
vault = SecretVault(BASE_DIR)

# Mock parsing skills
MOCK_SKILLS = [
    {
        "skill_id": "parse_jira_desc",
        "name": "Parse Jira Description",
        "skill_type": "parse",
        "parser_config": {
            "patterns": {
                "os_distro": r"OS:\s*([^\n]+)",
                "image_path": r"Image:\s*([^\n]+)",
                "java_version": r"Java:\s*([^\n]+)",
                "priority": r"Priority:\s*(HIGH|MEDIUM|LOW)"
            }
        }
    }
]

def main():
    print("\n=== Testing Task 3.5.2: Execution Engine Updates ===\n")
    
    registry = OperatorRegistry(vault, skill_store={})
    
    # Test 1: Basic parsing
    print("Test 1: Basic parsing skill extraction")
    text = """
    Build failed.
    OS: RHEL 8.6
    Image: us.icr.io/myapp:v1.2.3
    Java: 11.0.15
    Priority: HIGH
    """
    
    extracted = registry._execute_parsing_skills(text, MOCK_SKILLS)
    print(f"  Extracted: {extracted}")
    
    assert "os_distro" in extracted, "Missing os_distro"
    assert "RHEL" in extracted["os_distro"], f"Wrong os_distro: {extracted['os_distro']}"
    print("  ✓ os_distro extracted correctly")
    
    assert "image_path" in extracted, "Missing image_path"
    assert "us.icr.io" in extracted["image_path"]
    print("  ✓ image_path extracted correctly")
    
    assert "java_version" in extracted
    assert "11.0.15" in extracted["java_version"]
    print("  ✓ java_version extracted correctly")
    
    # Test 2: Nested field access
    print("\nTest 2: Nested field access")
    data = {
        "user": {
            "profile": {
                "name": "John",
                "settings": {
                    "theme": "dark"
                }
            }
        }
    }
    
    result = registry._get_nested_value(data, "user.profile.name")
    assert result == "John", f"Expected 'John', got {result}"
    print(f"  ✓ user.profile.name = {result}")
    
    result = registry._get_nested_value(data, "user.profile.settings.theme")
    assert result == "dark"
    print(f"  ✓ user.profile.settings.theme = {result}")
    
    result = registry._get_nested_value(data, "nonexistent.path")
    assert result is None
    print(f"  ✓ nonexistent.path = None (graceful)")
    
    # Test 3: Empty skills
    print("\nTest 3: Graceful degradation (no skills)")
    extracted = registry._execute_parsing_skills(text, [])
    assert extracted == {}
    print("  ✓ Empty skill list returns empty dict (no error)")
    
    print("\n=== All Tests Passed! ===")
    print("Task 3.5.2 implementation is working correctly.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)