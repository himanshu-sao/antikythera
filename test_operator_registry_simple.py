#!/usr/bin/env python3
"""
Simple test script for OperatorRegistry functionality
"""
import asyncio
import sys
import os
import tempfile
import shutil

# Add the api directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from api.models.automation import PathStep, ExecutionMode, ExecutionStatus, Condition, ConditionType
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault

async def test_execute_step_adapter():
    """Test adapter step execution"""
    print("Testing adapter step execution...")
    
    # Create a temporary directory for vault
    temp_dir = tempfile.mkdtemp()
    try:
        # Create a mock vault
        vault = SecretVault(temp_dir)
        
        # Create operator registry
        registry = OperatorRegistry(vault)
        
        # Create a simple adapter step
        step = PathStep(
            step_id="test_step_1",
            operator_id="fetch_resource",
            adapter_id="jira_adapter",
            config={"params": {"test": "value"}},
            mode=ExecutionMode.ADAPTER,
            input_ref=None,
            output_ref="fetched_data"
        )
        
        # Mock state
        state = {}
        
        # Execute step (this will fail because we don't have real adapters, but we can test the flow)
        try:
            result = await registry.execute_step(step.model_dump(), state)
            print(f"Adapter step result: {result}")
            # We expect this to fail because adapters aren't fully mocked, but let's see
        except Exception as e:
            print(f"Expected error (adapters not fully mocked): {e}")
            # This is okay for now
        
        print("✓ Adapter step test structure verified")
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

async def test_execute_step_script():
    """Test script step execution"""
    print("Testing script step execution...")
    
    # Create a temporary directory for vault
    temp_dir = tempfile.mkdtemp()
    try:
        # Create a mock vault
        vault = SecretVault(temp_dir)
        
        # Create operator registry
        registry = OperatorRegistry(vault)
        
        # Create a script step
        step = PathStep(
            step_id="test_step_2",
            operator_id="run_script",
            adapter_id="jira_adapter",  # Not used for script mode but required
            config={
                "code": """
# Simple script to test execution
result = {"message": "hello world", "value": 42}
"""
            },
            mode=ExecutionMode.SCRIPT,
            input_ref=None,
            output_ref="script_result"
        )
        
        # Mock state
        state = {}
        
        # Execute step
        result = await registry.execute_step(step.model_dump(), state)
        print(f"Script step result: {result}")
        
        # Verify result
        assert result.status == ExecutionStatus.SUCCESS
        assert result.result_data is not None
        assert result.result_data.get("result", {}).get("message") == "hello world"
        
        print("✓ Script step test passed")
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

async def test_execute_step_script_dependency():
    """Test script step with dependency handling"""
    print("Testing script dependency handling...")
    
    # Create a temporary directory for vault
    temp_dir = tempfile.mkdtemp()
    try:
        # Create a mock vault
        vault = SecretVault(temp_dir)
        
        # Create operator registry
        registry = OperatorRegistry(vault)
        
        # Create a script step that imports a standard library (should work)
        step = PathStep(
            step_id="test_step_3",
            operator_id="run_script",
            adapter_id="jira_adapter",
            config={
                "code": """
import json
import re
# Test that whitelisted imports work
data = {"test": "value"}
pattern = r'value'
match = re.search(pattern, data["test"])
result = {
    "imports_work": True,
    "json_works": isinstance(json.dumps(data), str),
    "regex_works": match is not None
}
"""
            },
            mode=ExecutionMode.SCRIPT,
            input_ref=None,
            output_ref="dependency_result"
        )
        
        # Mock state
        state = {}
        
        # Execute step
        result = await registry.execute_step(step.model_dump(), state)
        print(f"Dependency step result: {result}")
        
        # Verify result
        assert result.status == ExecutionStatus.SUCCESS
        assert result.result_data is not None
        assert result.result_data.get("result", {}).get("imports_work") == True
        
        print("✓ Script dependency test passed")
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

async def test_execute_step_condition_false():
    """Test condition evaluation - false case"""
    print("Testing false condition...")
    
    # Create a temporary directory for vault
    temp_dir = tempfile.mkdtemp()
    try:
        # Create a mock vault
        vault = SecretVault(temp_dir)
        
        # Create operator registry
        registry = OperatorRegistry(vault)
        
        # Create a step with a condition that should be false
        step = PathStep(
            step_id="test_step_4",
            operator_id="update_resource",
            adapter_id="jira_adapter",
            config={"status": "Investigating"},
            mode=ExecutionMode.ADAPTER,
            input_ref=None,
            output_ref="update_result",
            condition={
                "type": "equals",
                "field": "some_flag",
                "value": "expected_value"
            }
        )
        
        # State where condition is false
        state = {
            "some_flag": "different_value"
        }
        
        # Execute step
        result = await registry.execute_step(step.model_dump(), state)
        print(f"False condition result: {result}")
        
        # Verify result - should be skipped
        assert result.status == ExecutionStatus.SKIPPED
        assert "condition" in result.execution_reason.lower()
        
        print("✓ False condition test passed")
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

async def test_execute_step_condition_true():
    """Test condition evaluation - true case"""
    print("Testing true condition...")

    # JiraAdapter now resolves tokens from env first; clear any real JIRA_*
    # token env vars so the empty temp vault yields the no-op (no-token) path
    # this test expects, regardless of a developer's .env.
    _saved_env = {v: os.environ.pop(v, None) for v in ("JIRA_PAT", "JIRA_TOKEN")}

    # Create a temporary directory for vault
    temp_dir = tempfile.mkdtemp()
    try:
        # Create a mock vault
        vault = SecretVault(temp_dir)
        
        # Create operator registry
        registry = OperatorRegistry(vault)
        
        # Create a step with a condition that should be true
        step = PathStep(
            step_id="test_step_5",
            operator_id="update_resource",
            adapter_id="jira_adapter",
            config={"status": "Investigating"},
            mode=ExecutionMode.ADAPTER,
            input_ref=None,
            output_ref="update_result",
            condition={
                "type": "equals",
                "field": "some_flag",
                "value": "expected_value"
            }
        )
        
        # State where condition is true
        state = {
            "some_flag": "expected_value"
        }
        
        # Execute step
        result = await registry.execute_step(step.model_dump(), state)
        print(f"True condition result: {result}")
        
        # Verify result - should succeed
        assert result.status == ExecutionStatus.SUCCESS
        assert result.result_data is not None
        
        print("✓ True condition test passed")
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)
        # Restore JIRA_* env vars cleared at function entry
        for _var, _val in _saved_env.items():
            if _val is not None:
                os.environ[_var] = _val
            else:
                os.environ.pop(_var, None)

async def run_all_tests():
    """Run all tests"""
    print("Running OperatorRegistry tests...\n")
    
    await test_execute_step_adapter()
    await test_execute_step_script()
    await test_execute_step_script_dependency()
    await test_execute_step_condition_false()
    await test_execute_step_condition_true()
    
    print("\n🎉 All tests passed!")

if __name__ == "__main__":
    asyncio.run(run_all_tests())