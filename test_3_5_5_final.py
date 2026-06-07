#!/usr/bin/env python3
"""Task 3.5.5: Split Logic & Data Extraction Tests"""
import sys, os, asyncio
sys.path.insert(0, os.getcwd())

from api.operator_registry import OperatorRegistry
from api.models.automation import ExecutionStatus
from api.secret_vault import SecretVault

BASE_DIR = os.path.abspath('test_data')
os.makedirs(BASE_DIR, exist_ok=True)
vault = SecretVault(BASE_DIR)

def create_registry():
    return OperatorRegistry(vault, skill_store={})

TICKETS = [
    {"id": "T1", "fields": {"description": "OS: RHEL 8.6\nPriority: HIGH\nError: E1\nComponent: c1", "priority": {"name": "High"}}},
    {"id": "T2", "fields": {"description": "OS: Ubuntu\nPriority: MEDIUM\nError: E2\nComponent: c2", "priority": {"name": "Medium"}}}
]

SKILLS = [{
    "skill_id": "s1", 
    "skill_type": "parse", 
    "parser_config": {
        "patterns": {
            "os": r"OS:\s*([^\n]+)", 
            "priority": r"Priority:\s*(HIGH|MEDIUM|LOW)", 
            "error_code": r"Error:\s*([A-Z0-9]+)"
        }
    }
}]

def test_1():
    print("\n=== TEST 1: Two Tickets → Two Children ===")
    reg = create_registry()
    step = {
        "step_id": "p1", 
        "operator_id": "fetch_resource", 
        "adapter_id": "jira_adapter",
        "config": {}, 
        "loop_over": {"source": "items", "iterator_var": "item"}
    }
    results = asyncio.run(reg.execute_step(step, {"items": TICKETS, "parsing_skills": SKILLS}))
    assert len(results) == 2
    assert all(r.parent_run_id == results[0].parent_run_id for r in results)
    print(f"✓ 2 children, parent: {results[0].parent_run_id[:8]}...")
    return True

def test_2():
    print("\n=== TEST 2: Extracted Fields ===")
    reg = create_registry()
    step = {
        "step_id": "p2", 
        "operator_id": "fetch_resource", 
        "adapter_id": "jira_adapter",
        "config": {}, 
        "loop_over": {"source": "items", "iterator_var": "item"}
    }
    results = asyncio.run(reg.execute_step(step, {"items": TICKETS, "parsing_skills": SKILLS}))
    assert "RHEL" in results[0].extracted_fields["os"]
    assert results[0].extracted_fields["priority"] == "HIGH"
    assert "Ubuntu" in results[1].extracted_fields["os"]
    assert results[1].extracted_fields["priority"] == "MEDIUM"
    print(f"✓ Child 0: {results[0].extracted_fields}")
    print(f"✓ Child 1: {results[1].extracted_fields}")
    return True

def test_3():
    print("\n=== TEST 3: Parent-Child Relationship ===")
    reg = create_registry()
    single = [{"id": "X", "fields": {"description": "OS: Test\nPriority: LOW", "priority": {"name": "Low"}}}]
    step = {
        "step_id": "p3", 
        "operator_id": "fetch_resource", 
        "adapter_id": "jira_adapter",
        "config": {}, 
        "loop_over": {"source": "items", "iterator_var": "item"}
    }
    results = asyncio.run(reg.execute_step(step, {"items": single, "parsing_skills": SKILLS}))
    # Should have exactly 1 result since we sent 1 item
    assert len(results) == 1, f"Expected 1 result for 1 item, got {len(results)}"
    # Result should have parent_run_id set
    assert results[0].parent_run_id is not None, "Missing parent_run_id"
    # Parent run ID should be different from step_id
    assert results[0].parent_run_id != "p3"
    print(f"✓ Single item created 1 child with parent_run_id: {results[0].parent_run_id[:8]}...")
    return True

def test_4():
    print("\n=== TEST 4: Conditional Loop ===")
    reg = create_registry()
    step = {
        "step_id": "cond", 
        "operator_id": "fetch_resource", 
        "adapter_id": "jira_adapter",
        "config": {}, 
        "loop_over": {"source": "items", "iterator_var": "item"},
        "condition": {"type": "equals", "field": "item.fields.priority.name", "value": "High"}
    }
    # 1st item has "High", 2nd has "Medium" - only 1st should execute
    results = asyncio.run(reg.execute_step(step, {"items": TICKETS, "parsing_skills": SKILLS}))
    assert len(results) == 2
    # First item should execute (not skipped)
    assert results[0].status != ExecutionStatus.SKIPPED, f"First should execute, got {results[0].status}"
    # Second should be skipped
    assert results[1].status == ExecutionStatus.SKIPPED, f"Second should skip, got {results[1].status}"
    assert "Condition not met" in results[1].execution_reason
    print(f"✓ Child 0: {results[0].status}, Child 1: {results[1].status} (skipped)")
    return True

def test_5():
    print("\n=== TEST 5: Graceful Without Skills ===")
    reg = create_registry()
    step = {
        "step_id": "ns", 
        "operator_id": "fetch_resource", 
        "adapter_id": "jira_adapter",
        "config": {}, 
        "loop_over": {"source": "items", "iterator_var": "item"}
    }
    results = asyncio.run(reg.execute_step(step, {"items": TICKETS, "parsing_skills": []}))
    assert len(results) == 2
    assert all(r.extracted_fields == {} for r in results)
    print("✓ 2 children, empty extracted_fields (no crash)")
    return True

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Task 3.5.5: Split Logic & Data Extraction")
    print("="*60)
    
    tests = [test_1, test_2, test_3, test_4, test_5]
    passed = failed = 0
    
    for t in tests:
        try:
            if t():
                passed += 1
                print(f"✓ PASSED: {t.__name__}")
            else:
                failed += 1
                print(f"✗ FAILED: {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"✗ ERROR: {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60} -> {passed}/{len(tests)} passed")
    sys.exit(0 if failed == 0 else 1)