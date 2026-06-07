#!/usr/bin/env python3
"""
Comprehensive Unit Tests for Task 3.5.5: Split Logic & Data Extraction
Verifies:
1. Two input tickets create two child records
2. extracted_fields are populated correctly from mock descriptions
3. Parent-child relationships are maintained
4. Conditions and loop_over work together
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

from api.operator_registry import OperatorRegistry
from api.models.automation import PathStep, ExecutionStatus
from api.secret_vault import SecretVault
import json

# Setup
BASE_DIR = os.path.abspath('test_data')
os.makedirs(BASE_DIR, exist_ok=True)
vault = SecretVault(BASE_DIR)

# Mock Jira tickets with rich descriptions
TICKETS = [
    {
        "id": "PROJ-123",
        "key": "PROJ-123",
        "fields": {
            "summary": "RHEL8 Build Failure",
            "description": """
                Critical build failure detected in production pipeline.
                OS: RHEL 8.6
                Image: us.icr.io/analytics-service:v2.1.0
                Java Version: 11.0.15
                Priority: HIGH
                Error Code: BUILD-4521
                Component: docker-builder
                Assignee: dev-team-alpha
            """,
            "priority": {"name": "High"},
            "status": {"name": "Open"}
        }
    },
    {
        "id": "PROJ-124",
        "key": "PROJ-124",
        "fields": {
            "summary": "Ubuntu Test Failure",
            "description": """
                Integration test failed on Ubuntu runner.
                OS: Ubuntu 22.04 LTS
                Image: us.icr.io/test-service:v1.5.3
                Java Version: 17.0.3
                Priority: MEDIUM
                Error Code: TEST-8834
                Component: selenium-runner
                Assignee: qa-team-beta
            """,
            "priority": {"name": "Medium"},
            "status": {"name": "In Progress"}
        }
    }
]

# Parsing skills for extraction
PARSING_SKILLS = [
    {
        "skill_id": "extract_jira_fields",
        "name": "Extract Jira Ticket Fields",
        "skill_type": "parse",
        "parser_config": {
            "patterns": {
                "os_distro": r"OS:\s*([^\n]+)",
                "image_path": r"Image:\s*([^\n]+)",
                "java_version": r"Java Version:\s*([^\n]+)",
                "priority": r"Priority:\s*(HIGH|MEDIUM|LOW)",
                "error_code": r"Error Code:\s*([A-Z0-9-]+)",
                "component": r"Component:\s*([^\n]+)",
                "assignee": r"Assignee:\s*([^\n]+)"
            }
        }
    }
]

def test_two_tickets_create_two_children():
    """Verify that 2 input tickets result in 2 child execution records."""
    print("\n" + "="*70)
    print("TEST 1: Two Input Tickets → Two Child Records")
    print("="*70)
    
    registry = OperatorRegistry(vault, skill_store={"extract_jira_fields": PARSING_SKILLS[0]})
    
    loop_step = {
        "step_id": "process_tickets",
        "operator_id": "fetch_resource",
        "adapter_id": "jira_adapter",
        "config": {},
        "loop_over": {
            "source": "tickets",
            "iterator_var": "ticket"
        }
    }
    
    state = {
        "tickets": TICKETS,
        "parsing_skills": PARSING_SKILLS
    }
    
    # Execute loop step
    import asyncio
    results = asyncio.run(registry.execute_step(loop_step, state))
    
    # Verify we got exactly 2 children
    assert isinstance(results, list), f"Expected list, got {type(results)}"
    assert len(results) == 2, f"Expected 2 children, got {len(results)}"
    print(f"✓ Created {len(results)} child execution records (expected: 2)")
    
    # Verify each has a parent_run_id
    parent_run_id = results[0].parent_run_id
    assert parent_run_id is not None, "First child missing parent_run_id"
    
    for i, child in enumerate(results):
        assert child.parent_run_id == parent_run_id, f"Child {i} has different parent_run_id"
        assert child.step_id.startswith("process_tickets."), f"Child {i} has invalid step_id format"
    
    print(f"✓ All children share same parent_run_id: {parent_run_id}")
    print("✓ Child step IDs follow correct format: process_tickets.{0,1}")
    
    return True

def test_extracted_fields_populated_correctly():
    """Verify extracted_fields contains correct data from ticket descriptions."""
    print("\n" + "="*70)
    print("TEST 2: Extracted Fields Population")
    print("="*70)
    
    registry = OperatorRegistry(vault, skill_store={"extract_jira_fields": PARSING_SKILLS[0]})
    
    loop_step = {
        "step_id": "extract_and_process",
        "operator_id": "fetch_resource",
        "adapter_id": "jira_adapter",
        "config": {},
        "loop_over": {
            "source": "tickets",
            "iterator_var": "ticket"
        }
    }
    
    state = {
        "tickets": TICKETS,
        "parsing_skills": PARSING_SKILLS
    }
    
    import asyncio
    results = asyncio.run(registry.execute_step(loop_step, state))
    
    # Verify first child (RHEL ticket)
    child_0 = results[0]
    print(f"\nChild 0 (PROJ-123) Extracted Fields:")
    print(f"  {json.dumps(child_0.extracted_fields, indent=2)}")
    
    assert "os_distro" in child_0.extracted_fields, "Missing os_distro"
    assert "RHEL" in child_0.extracted_fields["os_distro"], f"Wrong OS: {child_0.extracted_fields['os_distro']}"
    print("  ✓ os_distro: RHEL 8.6")
    
    assert "image_path" in child_0.extracted_fields, "Missing image_path"
    assert "us.icr.io/analytics-service" in child_0.extracted_fields["image_path"]
    print("  ✓ image_path: us.icr.io/analytics-service:v2.1.0")
    
    assert "java_version" in child_0.extracted_fields, "Missing java_version"
    assert "11.0.15" in child_0.extracted_fields["java_version"]
    print("  ✓ java_version: 11.0.15")
    
    assert "priority" in child_0.extracted_fields, "Missing priority"
    assert child_0.extracted_fields["priority"] == "HIGH"
    print("  ✓ priority: HIGH")
    
    assert "error_code" in child_0.extracted_fields, "Missing error_code"
    assert child_0.extracted_fields["error_code"] == "BUILD-4521"
    print("  ✓ error_code: BUILD-4521")
    
    assert "component" in child_0.extracted_fields, "Missing component"
    assert "docker-builder" in child_0.extracted_fields["component"]
    print("  ✓ component: docker-builder")
    
    assert "assignee" in child_0.extracted_fields, "Missing assignee"
    assert "dev-team-alpha" in child_0.extracted_fields["assignee"]
    print("  ✓ assignee: dev-team-alpha")
    
    # Verify second child (Ubuntu ticket)
    child_1 = results[1]
    print(f"\nChild 1 (PROJ-124) Extracted Fields:")
    print(f"  {json.dumps(child_1.extracted_fields, indent=2)}")
    
    assert "os_distro" in child_1.extracted_fields
    assert "Ubuntu" in child_1.extracted_fields["os_distro"]
    print("  ✓ os_distro: Ubuntu 22.04 LTS")
    
    assert child_1.extracted_fields["java_version"] == "17.0.3"
    print("  ✓ java_version: 17.0.3")
    
    assert child_1.extracted_fields["priority"] == "MEDIUM"
    print("  ✓ priority: MEDIUM")
    
    assert child_1.extracted_fields["error_code"] == "TEST-8834"
    print("  ✓ error_code: TEST-8834")
    
    assert "qa-team-beta" in child_1.extracted_fields["assignee"]
    print("  ✓ assignee: qa-team-beta")
    
    print("✓ All extracted fields populated correctly for both tickets")
    return True

def test_parent_execution_log_created():
    """Verify that a parent execution log is created for the loop step."""
    print("\n" + "="*70)
    print("TEST 3: Parent Execution Log Creation")
    print("="*70)
    
    registry = OperatorRegistry(vault, skill_store={"extract_jira_fields": PARSING_SKILLS[0]})
    
    loop_step = {
        "step_id": "parent_loop",
        "operator_id": "fetch_resource",
        "adapter_id": "jira_adapter",
        "config": {},
        "loop_over": {
            "source": "tickets",
            "iterator_var": "ticket"
        }
    }
    
    state = {
        "tickets": TICKETS[:1],  # Just one to keep it simple
        "parsing_skills": PARSING_SKILLS
    }
    
    import asyncio
    results = asyncio.run(registry.execute_step(loop_step, state))
    
    # Check that parent log was created in registry
    parent_run_id = results[0].parent_run_id
    parent_log = registry.get_execution_log("parent_loop")
    
    assert parent_log is not None, "Parent execution log not created"
    assert parent_log.parent_run_id == parent_run_id, "Parent log has wrong parent_run_id"
    assert parent_log.execution_reason is not None, "Parent execution_reason is None"
    assert "Spawned" in parent_log.execution_reason, "Parent execution_reason missing info"
    assert "child execution" in parent_log.execution_reason.lower()
    
    print(f"✓ Parent log created with step_id: parent_loop")
    print(f"✓ Parent execution_reason: {parent_log.execution_reason}")
    print(f"✓ Parent status: {parent_log.status}")
    
    # Verify child retrieval
    children = registry.get_child_executions(parent_run_id)
    assert len(children) == 1, f"Expected 1 child, got {len(children)}"
    print(f"✓ Retrieved {len(children)} child via get_child_executions()")
    
    return True

def test_conditions_with_loop():
    """Verify conditions work correctly within loop iterations."""
    print("\n" + "="*70)
    print("TEST 4: Conditional Execution Within Loop")
    print("="*70)
    
    registry = OperatorRegistry(vault, skill_store={"extract_jira_fields": PARSING_SKILLS[0]})
    
    # Step with condition that only HIGH priority tickets should pass
    conditional_step = {
        "step_id": "high_priority_update",
        "operator_id": "update_resource",
        "adapter_id": "jira_adapter",
        "config": {"status": "IN_PROGRESS"},
        "loop_over": {
            "source": "tickets",
            "iterator_var": "ticket"
        },
        "condition": {
            "type": "equals",
            "field": "ticket.priority.name",
            "value": "High"
        }
    }
    
    state = {
        "tickets": TICKETS,  # One HIGH, one MEDIUM
        "parsing_skills": PARSING_SKILLS
    }
    
    import asyncio
    results = asyncio.run(registry.execute_step(conditional_step, state))
    
    # First ticket is HIGH priority - should execute
    child_0 = results[0]
    print(f"\nChild 0 (HIGH priority):")
    print(f"  Status: {child_0.status}")
    print(f"  Reason: {child_0.execution_reason}")
    
    # Second ticket is MEDIUM priority - should be skipped
    child_1 = results[1]
    print(f"\nChild 1 (MEDIUM priority):")
    print(f"  Status: {child_1.status}")
    print(f"  Reason: {child_1.execution_reason}")
    
    assert child_0.status == ExecutionStatus.SUCCESS or child_0.status == ExecutionStatus.FAILED, \
        f"HIGH priority ticket should execute, got {child_0.status}"
    assert child_1.status == ExecutionStatus.SKIPPED, \
        f"MEDIUM priority ticket should be skipped, got {child_1.status}"
    assert "Condition not met" in child_1.execution_reason, "Skip reason missing"
    
    print("✓ Conditions correctly evaluated per iteration")
    print("✓ HIGH priority ticket executed, MEDIUM priority skipped")
    
    return True

def test_no_parsing_skills_graceful():
    """Verify graceful behavior when no parsing skills are available."""
    print("\n" + "="*70)
    print("TEST 5: Graceful Degradation (No Parsing Skills)")
    print("="*70)
    
    registry = OperatorRegistry(vault, skill_store={})
    
    loop_step = {
        "step_id": "no_parse_loop",
        "operator_id": "fetch_resource",
        "adapter_id": "jira_adapter",
        "config": {},
        "loop_over": {
            "source": "tickets",
            "iterator_var": "ticket"
        }
    }
    
    state = {
        "tickets": TICKETS,
        "parsing_skills": []  # No skills
    }
    
    import asyncio
    results = asyncio.run(registry.execute_step(loop_step, state))
    
    assert len(results) == 2, f"Expected 2 children even without skills, got {len(results)}"
    
    for i, child in enumerate(results):
        assert child.extracted_fields == {}, \
            f"Child {i} should have empty extracted_fields, got {child.extracted_fields}"
        assert child.status == ExecutionStatus.SUCCESS or child.status == ExecutionStatus.FAILED, \
            f"Child should execute (not crash), got {child.status}"
    
    print("✓ Loop completes successfully without parsing skills")
    print("✓ Child records created with empty extracted_fields (no errors)")
    
    return True

def test_regex_edge_cases():
    """Test parsing with edge cases and malformed data."""
    print("\n" + "="*70)
    print("TEST 6: Regex Parsing Edge Cases")
    print("="*70)
    
    registry = OperatorRegistry(vault, skill_store={})
    
    # Test with partial/missing fields
    incomplete_text = """
    Some random text
    OS: Ubuntu
    No other fields here
    """
    
    skills = [{
        "skill_id": "strict_parser",
        "skill_type": "parse",
        "parser_config": {
            "patterns": {
                "os": r"OS:\s*([^\n]+)",
                "missing_field": r"Missing:\s*([^\n]+)",
                "another_missing": r"Another:\s*([^\n]+)"
            }
        }
    }]
    
    extracted = registry._execute_parsing_skills(incomplete_text, skills)
    
    print(f"Extracted from incomplete text: {extracted}")
    
    assert "os" in extracted, "Should extract available field"
    assert "Ubuntu" in extracted["os"]
    assert "missing_field" not in extracted, "Should not create missing fields"
    assert "another_missing" not in extracted
    
    print("✓ Only matching patterns extracted")
    print("✓ Non-matching patterns do not create empty fields")
    
    # Test with multiline values
    multiline_text = """
    Description: This is a
    multiline value that should
    not be matched by [^\n]
    """
    
    skills_multiline = [{
        "skill_id": "multiline_test",
        "skill_type": "parse",
        "parser_config": {
            "patterns": {
                "single_line": r"Description:\s*([^\n]+)"
            }
        }
    }]
    
    extracted = registry._execute_parsing_skills(multiline_text, skills_multiline)
    assert "single_line" in extracted
    assert "multiline" not in extracted["single_line"]  # Should stop at newline
    
    print("✓ Multiline text handled correctly (stops at newline)")
    
    return True

def run_all_tests():
    """Run all unit tests and report results."""
    print("\n" + "="*70)
    print("  UNIT TESTS: Task 3.5.5 - Split Logic & Data Extraction")
    print("="*70)
    
    tests = [
        ("Two Tickets → Two Children", test_two_tickets_create_two_children),
        ("Extracted Fields Population", test_extracted_fields_populated_correctly),
        ("Parent Execution Log", test_parent_execution_log_created),
        ("Conditional Loop Execution", test_conditions_with_loop),
        ("Graceful Degradation", test_no_parsing_skills_graceful),
        ("Regex Edge Cases", test_regex_edge_cases),
    ]
    
    passed = 0
    failed = 0
    errors = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
                print(f"\n✓ PASSED: {test_name}")
            else:
                failed += 1
                errors.append((test_name, "Returned False"))
                print(f"\n✗ FAILED: {test_name} (returned False)")
        except AssertionError as e:
            failed += 1
            errors.append((test_name, str(e)))
            print(f"\n✗ FAILED: {test_name}")
            print(f"  Assertion Error: {e}")
        except Exception as e:
            failed += 1
            errors.append((test_name, f"{type(e).__name__}: {e}"))
            print(f"\n✗ ERROR: {test_name}")
            print(f"  {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print(f"  RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*70)
    
    if errors:
        print("\nFailed Tests:")
        for name, error in errors:
            print(f"  - {name}: {error}")
        return False
    else:
        print("\n✓ ALL TESTS PASSED!")
        print("Task 3.5.5 implementation is correct and complete.")
        return True

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)