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

# ----------------------------------------------------------------------
# Network guard (autouse). Any TCP connect to a non-loopback host is refused
# with OSError and recorded; the test fails at teardown if one was attempted,
# even when the code under test swallowed the OSError. Tests marked ``network``
# or ``live_llm`` are not guarded (they opt in to real network use).
# ----------------------------------------------------------------------
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_GUARD_FLAG = "_antikythera_network_guard"
_UNGUARDED_MARKERS = ("network", "live_llm")


def _is_loopback_host(host):
    """True for ``localhost`` (matched by name, never resolved) and for numeric
    loopback addresses (127.0.0.0/8, ::1, ::ffff:127.x). Anything else, including
    other host names, is not loopback."""
    import ipaddress

    if isinstance(host, bytes):
        host = host.decode("ascii", "ignore")
    host = str(host).strip().lower()
    if host in _LOOPBACK_HOSTS:
        return True
    host = host.split("%", 1)[0]  # drop an IPv6 zone id such as ::1%lo0
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    return (mapped or ip).is_loopback


def _connect_host(address):
    """Host of an AF_INET/AF_INET6 address tuple, or None for non-IP addresses
    (AF_UNIX paths are strings and are not network traffic)."""
    if isinstance(address, tuple) and address:
        return str(address[0])
    return None


def _is_allowed_connect(address):
    host = _connect_host(address)
    return host is None or _is_loopback_host(host)


def _is_allowed_lookup(host):
    """getaddrinfo host argument: None/empty (wildcard bind) and loopback pass."""
    if host is None or host == "" or host == b"":
        return True
    return _is_loopback_host(host)


def _guard_applies(node):
    """False when the node carries a marker that opts out of the guard."""
    return not any(node.get_closest_marker(m) for m in _UNGUARDED_MARKERS)


@pytest.fixture(autouse=True)
def network_guard(request, monkeypatch):
    import errno
    import socket

    attempts = []
    if not _guard_applies(request.node):
        yield attempts
        return

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_sendto = socket.socket.sendto
    real_getaddrinfo = socket.getaddrinfo

    def _block(what, host):
        attempts.append(host)
        return OSError(f"network blocked in tests: {what} {host!r}")

    def guarded_connect(self, address):
        if _is_allowed_connect(address):
            return real_connect(self, address)
        raise _block("connect to", _connect_host(address))

    def guarded_connect_ex(self, address):
        if _is_allowed_connect(address):
            return real_connect_ex(self, address)
        _block("connect_ex to", _connect_host(address))
        # connect_ex reports failure by return value, not by raising.
        return errno.ENETUNREACH

    def guarded_sendto(self, data, *args):
        # sendto(data, address) or sendto(data, flags, address)
        address = args[-1] if args else None
        if _is_allowed_connect(address):
            return real_sendto(self, data, *args)
        raise _block("sendto", _connect_host(address))

    def guarded_getaddrinfo(host, *args, **kwargs):
        if _is_allowed_lookup(host):
            return real_getaddrinfo(host, *args, **kwargs)
        raise _block("DNS lookup of", host if isinstance(host, str) else str(host))

    for fn in (guarded_connect, guarded_connect_ex, guarded_sendto, guarded_getaddrinfo):
        setattr(fn, _GUARD_FLAG, True)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", guarded_sendto)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)

    # asyncio's selector loop resolves and connects through the socket calls
    # above, but guard sock_connect itself so a loop whose internals change
    # still cannot reach a remote host.
    try:
        from asyncio import selector_events
        real_sock_connect = selector_events.BaseSelectorEventLoop.sock_connect

        async def guarded_sock_connect(self, sock, address):
            if not _is_allowed_connect(address):
                raise _block("sock_connect to", _connect_host(address))
            return await real_sock_connect(self, sock, address)

        setattr(guarded_sock_connect, _GUARD_FLAG, True)
        monkeypatch.setattr(
            selector_events.BaseSelectorEventLoop, "sock_connect", guarded_sock_connect
        )
    except (ImportError, AttributeError):  # pragma: no cover
        pass

    yield attempts
    if attempts:
        pytest.fail(
            "test attempted non-loopback network access to "
            f"{sorted(set(map(str, attempts)))}; mark the test 'network' if this is intended",
            pytrace=False,
        )


# ----------------------------------------------------------------------
# Provider / credential isolation (autouse). A test must never pick up the
# developer's real keys, project ``.env`` or ``~/.antikythera`` config:
#   * ``agents.llm_client.load_dotenv`` (LLMClient() calls it) is a no-op;
#   * provider and credential variables are removed from os.environ;
#   * the AI engine config service reads/writes a per-test home under tmp_path
#     (config file and persisted ``.ai_env``), and its process-wide singleton is
#     replaced by an instance on that tmp home.
# ``live_llm`` tests need their explicit environment and are left alone.
# ----------------------------------------------------------------------
_CREDENTIAL_ENV_VARS = (
    "GOOGLE_API_KEY",
    "GOOGLE_API_KEY_KANBAN",
    "NVIDIA_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "JIRA_PAT",
    "JIRA_TOKEN",
    "GITHUB_TOKEN",
    "IBM_BOB_SHELL_DEFAULT_KEY",
)


@pytest.fixture(autouse=True)
def isolate_provider_env(request, tmp_path, monkeypatch):
    if request.node.get_closest_marker("live_llm"):
        yield None
        return

    import agents.llm_client as llm_client
    import api.services.ai_engine_config as aec

    monkeypatch.setattr(llm_client, "load_dotenv", lambda *a, **k: False)

    for name in _CREDENTIAL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    home = tmp_path / "antikythera-home"
    home.mkdir(parents=True, exist_ok=True)
    config_path = str(home / "ai_config.json")
    env_path = str(home / ".ai_env")
    monkeypatch.setattr(
        aec.AIEngineConfigService, "_get_default_config_path", lambda self: config_path
    )
    monkeypatch.setattr(
        aec.AIEngineConfigService, "_persistent_env_path", lambda self: env_path
    )
    # A fresh singleton on the tmp home (built after the patches above, so its
    # constructor reads nothing from the real ~/.antikythera). Deep-copied so a
    # test that mutates the config cannot change the module-wide default.
    svc = aec.AIEngineConfigService()
    svc.config = svc.config.model_copy(deep=True)
    monkeypatch.setattr(aec, "_ai_engine_config_service", svc)
    yield svc


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

    # Per-item timeline logs. agents.logger resolves DEFAULT_LOG_DIR at call
    # time and keys its cache by directory, so a logger requested after this
    # point writes under tmp even if one was created earlier. api.utils reads
    # LOG_BASE_DIR.
    import agents.logger as agent_logger
    import api.utils as api_utils
    logs_dir = str(base / "logs")
    monkeypatch.setattr(api_utils, "LOG_BASE_DIR", logs_dir)
    monkeypatch.setattr(agent_logger, "DEFAULT_LOG_DIR", logs_dir)

    # P4-1: data paths held as module constants that the lines above did not
    # cover. agents.handlers builds a WorkflowStateManager on DATA_DIR; the
    # brain loop reads/writes patterns and pending updates; the executor derives
    # item directories from cwd unless REQUIREMENTS_ROOT is set. The cwd is NOT
    # changed (config.yaml lookups depend on it), so the executor constant is
    # the redirect.
    import agents.brain_loop as agent_brain_loop
    import agents.executor_tools as agent_executor_tools
    monkeypatch.setattr(agent_handlers, "DATA_DIR", str(base))
    monkeypatch.setattr(agent_brain_loop, "BRAIN_DIR", str(base / "brain"), raising=False)
    monkeypatch.setattr(agent_brain_loop, "PATTERNS_FILE", str(base / "brain" / "patterns.md"), raising=False)
    monkeypatch.setattr(agent_brain_loop, "PENDING_UPDATES_FILE", str(base / "brain" / "pending-updates.md"), raising=False)
    monkeypatch.setattr(agent_brain_loop, "HISTORY_DIR", str(base / "brain" / "history"), raising=False)
    monkeypatch.setattr(agent_executor_tools, "REQUIREMENTS_ROOT", str(base / "requirements"))

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

    # Workflow state: one WorkflowStateManager rooted at tmp, shared by every
    # holder of state (see _redirect_state_holders). Replaces the former
    # separate reset_state_manager fixture so there is a single isolation point.
    from api.workflow_state_manager import WorkflowStateManager
    knowledge = base / "knowledge"
    deltas = knowledge / "deltas"
    knowledge.mkdir(exist_ok=True)
    deltas.mkdir(exist_ok=True)
    for name in ["user.md", "skills.md", "memory.md"]:
        (knowledge / name).write_text(f"# {name.split('.')[0].capitalize()}")
    _redirect_state_holders(monkeypatch, api_main, WorkflowStateManager(str(base)))

    yield base


def _redirect_state_holders(monkeypatch, api_main, sm):
    """Point every holder of workflow state at the same tmp manager.

    Holders: the module global read by get_state_manager(), the app.state
    copy, the engine (and its run_manager), the escalator, the retry manager
    and the scheduler. Each is restored at teardown by monkeypatch. Attributes
    that may not exist use raising=False.
    """
    monkeypatch.setattr(api_main, "state_manager", sm)
    monkeypatch.setattr(api_main.app.state, "state_manager", sm, raising=False)
    monkeypatch.setattr(api_main.engine, "state_manager", sm, raising=False)
    monkeypatch.setattr(api_main.engine, "run_manager", sm.runs, raising=False)
    monkeypatch.setattr(api_main.escalator, "state_manager", sm, raising=False)
    monkeypatch.setattr(api_main.retry_manager, "state_manager", sm, raising=False)
    monkeypatch.setattr(api_main.scheduler, "state_manager", sm, raising=False)
