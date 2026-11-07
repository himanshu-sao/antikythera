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

# Autouse fixture: every test gets its own ``automation-ideas`` tree under
# tmp_path. Modules that hold the real data path as a module-level constant
# (agents.state, the memory agent, board/studio routers, the integration hub)
# are repointed here too, so no test can touch the real data directory.
@pytest.fixture(autouse=True)
def isolate_data_dir(tmp_path, monkeypatch):
    base = tmp_path / "automation-ideas"
    base.mkdir(parents=True, exist_ok=True)
    (base / "requirements").mkdir(exist_ok=True)
    (base / "brain").mkdir(exist_ok=True)
    (base / "audit").mkdir(exist_ok=True)

    import agents.state as agent_state
    import agents.memory as agent_memory
    import agents.audit as agent_audit
    import agents.architect as agent_architect
    import agents.refiner as agent_refiner
    import agents.tester as agent_tester
    import agents.handlers as agent_handlers
    import api.studio_router as studio_router
    import api.skill_router as skill_router
    import api.pipeline_router as pipeline_router

    # agents.state: point the file, lock and requirements dir at tmp.
    # The lock is rebuilt because FileLock is bound at import time.
    from filelock import FileLock
    monkeypatch.setattr(agent_state, "STATE_FILE", str(base / "pipeline-state.json"))
    monkeypatch.setattr(agent_state, "LOCK_FILE", str(base / "pipeline-state.json.lock"))
    monkeypatch.setattr(agent_state, "_lock", FileLock(str(base / "pipeline-state.json.lock")))
    monkeypatch.setattr(agent_state, "REQUIREMENTS_DIR", str(base / "requirements"))

    monkeypatch.setattr(agent_memory, "AUDIT_DIR", str(base / "audit"))
    monkeypatch.setattr(agent_memory, "PATTERNS_FILE", str(base / "brain" / "patterns.md"))
    monkeypatch.setattr(agent_memory, "PENDING_UPDATES_FILE", str(base / "brain" / "pending-updates.md"))
    monkeypatch.setattr(agent_memory, "HISTORY_DIR", str(base / "brain" / "history"))
    monkeypatch.setattr(agent_audit, "AUDIT_DIR", str(base / "audit"))

    monkeypatch.setattr(agent_architect, "REQUIREMENTS_DIR", str(base / "requirements"))
    monkeypatch.setattr(agent_architect, "BRAIN_PATTERNS", str(base / "brain" / "patterns.md"))
    monkeypatch.setattr(agent_refiner, "REQUIREMENTS_DIR", str(base / "requirements"))
    monkeypatch.setattr(agent_refiner, "BRAIN_PATTERNS", str(base / "brain" / "patterns.md"))
    monkeypatch.setattr(agent_tester, "REQUIREMENTS_DIR", str(base / "requirements"))
    monkeypatch.setattr(agent_handlers, "REQUIREMENTS_DIR", str(base / "requirements"), raising=False)

    # Routers that resolve their data dir from __file__ at call time.
    monkeypatch.setattr(studio_router, "_get_base_dir", lambda: str(base))
    monkeypatch.setattr(skill_router, "BASE_DIR", str(base), raising=False)
    monkeypatch.setattr(pipeline_router, "BASE_DIR", str(base), raising=False)

    import api.board_router as board_router
    monkeypatch.setattr(board_router, "REQUIREMENTS_DIR", str(base / "requirements"))

    # Per-item timeline logs. agents.logger.AgentLogger defaults to the
    # cwd-relative "automation-ideas/logs"; api.utils reads LOG_BASE_DIR.
    import agents.logger as agent_logger
    import api.utils as api_utils
    logs_dir = str(base / "logs")
    monkeypatch.setattr(api_utils, "LOG_BASE_DIR", logs_dir)
    for name in dir(agent_logger):
        cls = getattr(agent_logger, name)
        init = getattr(cls, "__init__", None)
        defaults = getattr(init, "__defaults__", None)
        if isinstance(cls, type) and defaults and "automation-ideas/logs" in defaults:
            monkeypatch.setattr(
                init, "__defaults__",
                tuple(logs_dir if d == "automation-ideas/logs" else d for d in defaults),
            )

    # Integration hub: the app builds one at import time on the real data dir,
    # and tests that POST /api/integrations without their own override would
    # otherwise write the real integrations.json. Tests that set their own
    # app.state.hub still win, because they run after this fixture.
    import api.main as api_main
    from api.integration_hub import IntegrationHub
    test_hub = IntegrationHub(str(base))
    monkeypatch.setattr(api_main, "hub", test_hub)
    monkeypatch.setattr(api_main.app.state, "hub", test_hub)
    monkeypatch.setattr(api_main.engine, "hub", test_hub, raising=False)
    monkeypatch.setattr(api_main.scheduler, "hub", test_hub, raising=False)

    yield base


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
