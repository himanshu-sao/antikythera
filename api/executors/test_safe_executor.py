import pytest
from api.executors.safe_executor import SafeExecutor, SafeExecutorError, SecurityError, DependencyRequiredError

def test_safe_executor_whitelisted_import():
    """Test that whitelisted imports work."""
    code = """
import json
import re
data = {"hello": "world"}
result = json.dumps(data)
"""
    output = SafeExecutor.execute(code)
    assert output == '{"hello": "world"}'

def test_safe_executor_blocked_import():
    """Test that blocked imports raise SecurityError."""
    code = """
import os
result = os.listdir('.')
"""
    with pytest.raises(SecurityError, match="Blocked import due to security policy: os"):
        SafeExecutor.execute(code)

def test_safe_executor_dangerous_builtin():
    """Test that dangerous builtins are blocked."""
    code = """
result = eval("1+1")
"""
    with pytest.raises(SafeExecutorError): # Will raise SafeExecutorError during exec
        SafeExecutor.execute(code)

def test_safe_executor_syntax_error():
    """Test that syntax errors are caught."""
    code = """
import json
data = {"test": 
"""
    with pytest.raises(SafeExecutorError, match="Invalid Python syntax"):
        SafeExecutor.execute(code)

def test_safe_executor_context():
    """Test that context variables are available."""
    code = """
result = input_data * 2
"""
    context = {"input_data": 21}
    output = SafeExecutor.execute(code, context)
    assert output == 42

if __name__ == "__main__":
    pytest.main([__file__, "-v"])