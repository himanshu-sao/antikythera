from api.executors.safe_executor import SafeExecutor

def test_safe_executor_no_imports():
    """Test that code without imports works."""
    code = """
data = {"hello": "world"}
result = str(data)
"""
    try:
        output = SafeExecutor.execute(code)
        print(f"No imports test: {output}")
        assert output == "{'hello': 'world'}"
        print("No imports test PASSED")
    except Exception as e:
        print(f"No imports test FAILED: {e}")
        raise

if __name__ == "__main__":
    test_safe_executor_no_imports()