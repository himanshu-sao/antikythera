"""
Simple synchronous tests for Task 3.5.2: Execution Engine Updates
Tests the parsing skills and field extraction logic.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault

# Setup
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "test_data"))
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

def test_parsing_skill_regex_extraction():
    """Test the parsing skill regex extraction directly."""
    print("\n=== Test: Parsing Skill Regex Extraction ===")
    registry = OperatorRegistry(vault, skill_store={})
    
    text = """
    Build failed.
    OS: RHEL 8.6
    Image: us.icr.io/myapp:v1.2.3
    Java: 11.0.15
    Priority: HIGH
    """
    
    extracted = registry._execute_parsing_skills(text, MOCK_SKILLS)
    
    print(f"Extracted fields: {extracted}")
    
    assert "os_distro" in extracted, "Missing os_distro field"
    assert "RHEL" in extracted["os_distro"], f"Expected 'RHEL' in os_distro, got: {extracted['os_distro']}"
    
    assert "image_path" in extracted, "Missing image_path field"
    assert "us.icr.io" in extracted["image_path"], f"Expected 'us.icr.io' in image_path"
    
    assert "java_version" in extracted, "Missing java_version field"
    assert "11.0.15" in extracted["java_version"], f"Expected '11.0.15' in java_version"
    
    assert "priority" in extracted, "Missing priority field"
    assert extracted["priority"] == "HIGH", f"Expected 'HIGH' priority"
    
    print("✓ All parsing extractions passed!")
    return True

def test_nested_field_access():
    """Test _get_nested_value with nested dictionaries."""
    print("\n=== Test: Nested Field Access ===")
    registry = OperatorRegistry(vault, skill_store={})
    
    data = {
        "user": {
            "profile": {
                "name": "John",
                "settings": {
                    "theme": "dark"
                }
            }
        },
        "items": [
            {"id": "1", "value": "first"},
            {"id": "2", "value": "second"}
        ]
    }
    
    # Test basic nested access
    result = registry._get_nested_value(data, "user.profile.name")
    assert result == "John", f"Expected 'John', got: {result}"
    print(f"✓ Nested access 'user.profile.name' = {result}")
    
    # Test deeper nested access
    result = registry._get_nested_value(data, "user.profile.settings.theme")
    assert result == "dark", f"Expected 'dark', got: {result}"
    print(f"✓ Nested access 'user.profile.settings.theme' = {result}")
    
    # Test non-existent path
    result = registry._get_nested_value(data, "nonexistent.path")
    assert result is None, f"Expected None, got: {result}"
    print(f"✓ Non-existent path returns None")
    
    # Test empty path returns full data
    result = registry._get_nested_value(data, "")
    assert result == data, "Empty path should return full data"
    print(f"✓ Empty path returns full data object")
    
    print("✓ All nested field access tests passed!")
    return True

def test_multiple_skills():
    """Test applying multiple parsing skills to the same text."""
    print("\n=== Test: Multiple Parsing Skills ===")
    registry = OperatorRegistry(vault, skill_store={})
    
    text = """
    Error: BUILD-4521
    Component: docker-builder
    OS: Ubuntu 22.04
    """
    
    skills = [
        {
            "skill_id": "skill1",
            "skill_type": "parse",
            "parser_config": {
                "patterns": {
                    "error_code": r"Error:\s*([A-Z0-9-]+)"
                }
            }
        },
        {
            "skill_id": "skill2",
            "skill_type": "parse",
            "parser_config": {
                "patterns": {
                    "component": r"Component:\s*([^\n]+)",
                    "os": r"OS:\s*([^\n]+)"
                }
            }
        }
    ]
    
    extracted = registry._execute_parsing_skills(text, skills)
    
    print(f"Extracted fields: {extracted}")
    
    assert "error_code" in extracted
    assert extracted["error_code"] == "BUILD-4521"
    
    assert "component" in extracted
    assert extracted["component"].strip() == "docker-builder"
    
    assert "os" in extracted
    assert "Ubuntu" in extracted["os"]
    
    print("✓ Multiple skills applied successfully!")
    return True

def test_graceful_degradation_no_skills():
    """Test that execution works without parsing skills."""
    print("\n=== Test: Graceful Degradation (No Skills) ===")
    registry = OperatorRegistry(vault, skill_store={})
    
    text = "Some random text with OS: RHEL but no skills to parse it"
    
    extracted = registry._execute_parsing_skills(text, [])
    
    # Should return empty dict, not error
    assert extracted == {}, f"Expected empty dict, got: {extracted}"
    print("✓ Empty skill list returns empty extraction (no error)")
    
    # Also test with empty list
    extracted = registry._execute_parsing_skills(text, [])
    assert extracted == {}, f"Expected empty dict with empty skills, got: {extracted}"
    print("✓ Empty skill list returns empty extraction (no error)")
    
    return True

def test_non_matching_patterns():
    """Test that non-matching patterns don't cause errors."""
    print("\n=== Test: Non-Matching Patterns ===")
    registry = OperatorRegistry(vault, skill_store={})
    
    text = "This text has no structured data at all"
    
    skills = [
        {
            "skill_id": "strict_skill",
            "skill_type": "parse",
            "parser_config": {
                "patterns": {
                    "required_field": r"REQUIRED:\s*([^\n]+)"
                }
            }
        }
    ]
    
    extracted = registry._execute_parsing_skills(text, skills)
    
    # Should return empty dict when nothing matches
    assert "required_field" not in extracted
    print("✓ Non-matching patterns result in empty field (no error)")
    
    return True

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Running Execution Engine Unit Tests (Task 3.5.2)")
    print("="*60)
    
    tests = [
        test_nested_field_access,
        test_parsing_skill_regex_extraction,
        test_multiple_skills,
        test_graceful_degradation_no_skills,
        test_non_matching_patterns
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {test_func.__name__}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {test_func.__name__}")
            print(f"  {type(e).__name__}: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\n✓ All tests passed! Task 3.5.2 implementation verified.")
        sys.exit(0)