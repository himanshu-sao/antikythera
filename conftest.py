# conftest.py – safe, scoped helpers

import sys
import os
import asyncio
import pytest


# ----------------------------------------------------------------------
# 0. Stub the ``ibm_bob`` (``bob`` CLI) path for the whole test session by
#    default, so the suite never shells out to the real ``bob`` binary
#    (8–15s per call, can hang, spends bob quota).  ``LLMClient._chat_bob``
#    checks ``ANTIKYTHERA_BOB_STUB`` and short-circuits to a deterministic
#    response when it's truthy (see agents/llm_client.py).  We only set it
#    if the user did NOT already export it, so:
#      * default ``pytest``        -> bob stubbed on (no bob tokens spent)
#      * ``ANTIKYTHERA_BOB_STUB=0 pytest ...`` -> real bob (for the P3.2.6
#        live-bob proof / any test that needs the genuine binary)
#    Non-bob providers (OpenAI/Google/etc.) are NOT mocked here — only the
#    ``ibm_bob`` subprocess path.
# ----------------------------------------------------------------------
if "ANTIKYTHERA_BOB_STUB" not in os.environ:
    os.environ["ANTIKYTHERA_BOB_STUB"] = "1"


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

# Session-scoped event loop for pytest-asyncio (every async test, even those
# outside the api/executors subpackage, gets a usable loop).
@pytest.fixture(scope="session")
def event_loop():
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
