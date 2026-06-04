import pytest
from unittest.mock import Mock
from typing import Any, Dict, Optional
from api.executors.safe_executor import SafeExecutor
from api.models.automation import PathStep, ExecutionMode, ExecutionStatus, Condition, ConditionType
from api.operator_registry import OperatorRegistry
from api.adapters.base import BaseAdapter

# Mock Vault
class MockVault:
    def get_secret(self, key):
        return "test-value"

# Mock Adapter that properly inherits from BaseAdapter
class MockAdapter(BaseAdapter):
    def __init__(self, vault):
        super().__init__(vault)
    
    async def fetch(self, resource_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        # Ignore resource_id for mock, return a list of issues
        return [{"id": 1, "title": "Test Issue"}]
    
    async def update(self, resource_id: str, payload: Dict[str, Any]) -> Any:
        # Ignore resource_id for mock
        return {"status": "updated"}
    
    async def create(self, payload: Dict[str, Any]) -> Any:
        return {"id": 2}
    
    async def delete(self, resource_id: str) -> Any:
        return {"deleted": True}

@pytest.fixture
def mock_vault():
    return MockVault()

@pytest.fixture
def mock_adapter():
    return MockAdapter(MockVault())

@pytest.fixture
def registry(mock_vault):
    # We'll replace the adapters with mocks
    reg = OperatorRegistry(mock_vault)
    reg.adapters = {
        "jira_adapter": MockAdapter(mock_vault),
        "github_adapter": MockAdapter(mock_vault)
    }
    return reg

@pytest.mark.asyncio
async def test_execute_step_adapter(registry):
    """Test executing a simple adapter step."""
    step_config = {
        "step_id": "step_1",
        "operator_id": "fetch_resource",
        "adapter_id": "jira_adapter",
        "mode": "adapter",
        "config": {"params": {}},
        "input_ref": None,
        "output_ref": "fetched_data",
        "condition": None,
        "loop_over": None
    }
    state = {}
    
    result = await registry.execute_step(step_config, state)
    
    # Check that we got a successful ExecutionLog
    assert hasattr(result, 'status')
    assert result.status == ExecutionStatus.SUCCESS
    assert result.step_id == "step_1"
    # The fetch should return a list of issues
    assert result.result_data is not None

@pytest.mark.asyncio
async def test_execute_step_script_success(registry):
    """Test executing a successful script step."""
    step_config = {
        "step_id": "step_2",
        "operator_id": "run_script",  # This operator_id doesn't matter for script mode
        "adapter_id": "jira_adapter",  # adapter_id is required but not used in script mode
        "mode": "script",
        "config": {
            "code": """
import json
data = {"test": 123}
result = json.dumps(data)
"""
        },
        "input_ref": None,
        "output_ref": "script_result",
        "condition": None,
        "loop_over": None
    }
    state = {}
    
    result = await registry.execute_step(step_config, state)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.step_id == "step_2"
    assert result.result_data is not None
    assert result.result_data.get("result") == '{"test": 123}'

@pytest.mark.asyncio
async def test_execute_step_script_dependency(registry):
    """Test that a script requiring a dependency raises DependencyRequiredError."""
    step_config = {
        "step_id": "step_3",
        "operator_id": "run_script",
        "adapter_id": "jira_adapter",
        "mode": "script",
        "config": {
            "code": """
import pandas
result = "pandas available"
"""
        },
        "input_ref": None,
        "output_ref": None,
        "condition": None,
        "loop_over": None
    }
    state = {}
    
    # This should raise DependencyRequiredError for pandas
    with pytest.raises(Exception) as exc_info:
        await registry.execute_step(step_config, state)
    
    # Check that it's the right kind of error
    assert "pandas" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_execute_step_condition_false(registry):
    """Test that a step with a false condition is skipped."""
    step_config = {
        "step_id": "step_4",
        "operator_id": "fetch_resource",
        "adapter_id": "jira_adapter",
        "mode": "adapter",
        "config": {"params": {}},
        "input_ref": None,
        "output_ref": "fetched_data",
        "condition": {
            "type": "equals",
            "field": "some_flag",
            "value": True
        },
        "loop_over": None
    }
    # State where the condition is false
    state = {"some_flag": False}
    
    result = await registry.execute_step(step_config, state)
    
    assert result.status == ExecutionStatus.SKIPPED
    assert result.execution_reason is not None
    assert "Condition not met" in result.execution_reason

@pytest.mark.asyncio
async def test_execute_step_condition_true(registry):
    """Test that a step with a true condition runs."""
    step_config = {
        "step_id": "step_5",
        "operator_id": "fetch_resource",
        "adapter_id": "jira_adapter",
        "mode": "adapter",
        "config": {"params": {}},
        "input_ref": None,
        "output_ref": "fetched_data",
        "condition": {
            "type": "equals",
            "field": "some_flag",
            "value": True
        },
        "loop_over": None
    }
    # State where the condition is true
    state = {"some_flag": True}
    
    result = await registry.execute_step(step_config, state)
    
    assert result.status == ExecutionStatus.SUCCESS

@pytest.mark.asyncio
async def test_execute_step_loop(registry):
    """Test executing a step with loop_over (fan-out)."""
    step_config = {
        "step_id": "step_6",
        "operator_id": "fetch_resource",
        "adapter_id": "jira_adapter",
        "mode": "adapter",
        "config": {"params": {}},
        "input_ref": None,
        "output_ref": "item_result",
        "condition": None,
        "loop_over": {
            "source": "items_list",
            "iterator_var": "item"
        }
    }
    # State with a list of items
    state = {
        "items_list": [
            {"id": 1, "name": "Item 1"},
            {"id": 2, "name": "Item 2"},
            {"id": 3, "name": "Item 3"}
        ]
    }
    
    result = await registry.execute_step(step_config, state)
    
    # Should return a list of ExecutionLog objects (one per item)
    assert isinstance(result, list)
    assert len(result) == 3
    
    # Check each child log
    for i, log in enumerate(result):
        assert log.step_id == f"step_6.{i}"
        assert log.parent_run_id is not None  # Should have a parent run ID
        assert log.status == ExecutionStatus.SUCCESS
        # The input_ref would have been resolved to the item, but we don't check the exact result here
    
    # Check that the logs are stored in the registry
    parent_run_id = result[0].parent_run_id
    child_logs = registry.get_child_executions(parent_run_id)
    assert len(child_logs) == 3

if __name__ == "__main__":
    pytest.main([__file__, "-v"])