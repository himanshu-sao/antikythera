# conftest.py – safe, scoped helpers

import sys
import os
import asyncio
import inspect
import importlib.util
import pytest


# ----------------------------------------------------------------------
# 1. Ensure a default asyncio event loop exists for any code that calls
#    asyncio.get_event_loop() outside of a test context.
# ----------------------------------------------------------------------
try:
    asyncio.get_event_loop()
except RuntimeError:                     # pragma: no cover
    asyncio.set_event_loop(asyncio.new_event_loop())

# Ensure every test has an event loop (some tests manually call asyncio.get_event_loop())
@pytest.fixture(autouse=True)
def ensure_event_loop():
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

# ----------------------------------------------------------------------
# 2. OPTIONAL async‑function wrapper.
#    Only activate it when the pytest‑asyncio plugin is NOT loaded.
#    This avoids overwriting the real test function object and breaking
#    signatures (e.g. the `registry=` kwarg used by many executor tests).
# ----------------------------------------------------------------------
# NOTE: The test suite includes the `pytest_asyncio` plugin, so we do NOT
# need to wrap async test functions.  The original wrapper caused
# ``AttributeError: can't set attribute`` during collection, so it has been
# removed.

# ----------------------------------------------------------------------
# 3. Autouse fixture that safely restores the brain/knowledge paths.
#    The WorkflowStateManager created in api.main stores a `brain`
#    attribute (an instance of BrainManager).  Some tests import the
#    app before this fixture runs, some import only modules – we must be
#    defensive.
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# 4. Teardown hook that only restores the real agents.llm_client module.
#    This is needed for `tests/test_executor_agentic.py` which injects a
#    mock into sys.modules.  Other tests never touch this module.
# ----------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    """Create a global event loop for all async tests.
    The built‑in pytest‑asyncio plugin looks for a fixture named ``event_loop``.
    Providing it here ensures every async test (even those outside the
    ``api/executors`` subpackage) gets a usable loop.
    """
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# Autouse fixture to provide a fresh WorkflowStateManager with isolated directories for each test.
@pytest.fixture(autouse=True)
def reset_state_manager(tmp_path):
    import api.main
    # Build temporary automation-ideas structure
    base = tmp_path / "automation-ideas"
    knowledge = base / "knowledge"
    deltas = knowledge / "deltas"
    knowledge.mkdir(parents=True)
    deltas.mkdir()
    # Create default markdown files
    for name in ["user.md", "skills.md", "memory.md"]:
        (knowledge / name).write_text(f"# {name.split('.')[0].capitalize()}")
    # Replace the global state_manager with a fresh instance
    api.main.state_manager = api.main.WorkflowStateManager(str(base))


def pytest_runtest_teardown(item):
    # Apply the cleanup only for the test that deliberately mocks the client
    if "test_executor_agentic" in item.nodeid:
        mod = sys.modules.get("agents.llm_client")
        if mod and not getattr(mod, "__file__", None):
            # Remove the mock
            del sys.modules["agents.llm_client"]
            # Load the genuine implementation from source
            real_path = os.path.join(os.path.dirname(__file__), "agents", "llm_client.py")
            spec = importlib.util.spec_from_file_location("agents.llm_client", real_path)
            real_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(real_mod)
            sys.modules["agents.llm_client"] = real_mod
