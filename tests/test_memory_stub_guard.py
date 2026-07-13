"""P3.1 regression tests: the memory loop must never persist a degraded LLM
``stub response`` (or an empty "no patterns" reply) into ``patterns.md``.

Before P3.1, ``LLMClient.chat()`` silently returned ``"[stub response — …]"``
when no real provider was reachable, and ``memory.py`` wrote that string
verbatim under a ``## Learned on …`` heading — so patterns.md accumulated
~20 ``stub response`` bodies and the loop "learned nothing" every run.

These tests inject a fake LLM (no live call, no key) into a ``MemoryAgent``
and drive the three write-paths (the periodic loop's
``_analyze_patterns``/``_update_patterns_file`` pair, and the on-completion
``extract_pattern_from_content``) to assert the stub-guard contract:

  * stub   → skipped, nothing appended to patterns.md, failure reason logged;
  * empty  → skipped (the prompt explicitly allows an empty "no patterns"
             reply, and it must never become a Learned-on section);
  * real   → appended verbatim.

All stub-detection now flows through ``LLMClient.is_stub()`` — the single source of
truth shared by ``automation_router``, ``skill_router``, ``ai_adapter``, and here.
"""
import importlib
import os

import pytest

import agents.memory as memory_mod
from agents.memory import (
    MemoryAgent,
    _is_stub_response,
    extract_pattern_from_content,
)


class _FakeChat:
    """Stand-in for ``LLMClient``. ``chat`` returns a canned string (or raises
    if ``response`` is an ``Exception``), matching the seam used by the P2.4
    router tests in ``tests/test_automation_skill_routers.py``."""

    def __init__(self, response):
        self._response = response
        self.calls = 0

    def chat(self, system_prompt, user_prompt, temperature=0.7):
        self.calls += 1
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


# ---------------------------------------------------------------------------
# Unit-level: the detector itself (LLMClient.is_stub is the single source of truth)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ("stub response", True),
    ("[stub response — google LLM call failed: No module named 'google.genai']", True),
    ("[STUB RESPONSE — OLLAMA LLM call failed: connection refused]", True),
    ("", True),
    ("   \n\n  \t ", True),
    (None, True),
    (123, True),
    (["not", "a", "string"], True),
    # Real model output must NOT be flagged as a stub.
    ("## Agent Workflow\n- **Pattern**: Sequential Pipeline\n- **Context**: x", False),
    ("Some genuinely fuzzy but non-empty prose with no s-t-u-b substring.", False),
])
def test_is_stub_response_matches_routers_contract(text, expected):
    # All detection flows through LLMClient.is_stub; _is_stub_response delegates.
    # We assert on the helper (not the class method directly) so this contract
    # stays robust even if another test has globally mocked LLMClient.is_stub.
    assert _is_stub_response(text) is expected


def _fresh_real_llm_client():
    """Reload the genuine ``agents.llm_client`` module from source.

    Another test (``tests/test_executor_agentic.py``) replaces
    ``sys.modules['agents.llm_client']`` with a ``MagicMock``-filled
    ``ModuleType`` and never restores it — a latent isolation leak. The
    ``agents/__init__.py`` guard reloads the real module once at package import
    time, but that runs *before* the offending test pollutes ``sys.modules``.
    Tests that need to exercise the *real* ``LLMClient.is_stub`` must reload it
    fresh so they don't observe the leaked mock.
    """
    import importlib.util
    file_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "agents", "llm_client.py"
    )
    spec = importlib.util.spec_from_file_location("_real_llm_client", file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.LLMClient


def test_llm_client_is_stub_is_the_source_of_truth():
    """LLMClient.is_stub is the real detector; the helper just delegates to it.
    Anyone calling LLMClient.is_stub directly (routers, ai_adapter) gets the
    same answer as the memory helper."""
    RealLLMClient = _fresh_real_llm_client()
    # Synthetic inputs that don't depend on any ambient provider state.
    assert RealLLMClient.is_stub("[stub response — anything]") is True
    assert RealLLMClient.is_stub("") is True
    assert RealLLMClient.is_stub("A real learned pattern line.") is False


def test_is_stub_response_delegates_to_llm_client(monkeypatch):
    """_is_stub_response must call LLMClient.is_stub, not own its own check.

    We patch ``is_stub`` on the *real* LLMClient (reloaded fresh so we don't
    observe a leaked MagicMock from another test) and then point
    ``agents.memory``'s view of the module at it, so the helper's delegation
    hits our spy.
    """
    import agents.memory as mem_mod
    from unittest.mock import MagicMock

    RealLLMClient = _fresh_real_llm_client()
    spy = MagicMock(return_value=False)
    monkeypatch.setattr(RealLLMClient, "is_stub", spy)
    monkeypatch.setattr(mem_mod, "LLMClient", RealLLMClient)

    result = mem_mod._is_stub_response("any text")
    assert spy.called is True
    assert result is False


# ---------------------------------------------------------------------------
# _analyze_patterns (periodic loop): stub → None, real → body returned
# ---------------------------------------------------------------------------
def _make_agent(response):
    agent = MemoryAgent.__new__(MemoryAgent)        # bypass __init__ (no LLMClient)
    agent.llm = _FakeChat(response)
    return agent


def test_analyze_patterns_skips_stub_response():
    agent = _make_agent(
        "[stub response — ollama LLM call failed: connection refused]",
    )
    assert agent._analyze_patterns(["audit entry one", "audit entry two"]) is None


def test_analyze_patterns_skips_empty_response():
    agent = _make_agent("   ")
    assert agent._analyze_patterns(["e1", "e2"]) is None


def test_analyze_patterns_returns_real_body():
    real = "## Agent Workflow\n- **Pattern**: Sequential Pipeline\n- **Context**: x"
    agent = _make_agent(real)
    assert agent._analyze_patterns(["e1"]) == real.strip()


# ---------------------------------------------------------------------------
# _update_patterns_file end-to-end: stub round => no write; real => written
# ---------------------------------------------------------------------------
def test_run_learning_loop_does_not_persist_stub(tmp_path, monkeypatch):
    patterns_file = tmp_path / "patterns.md"
    patterns_file.write_text("# Learned Patterns\n\nseed\n")

    # Point the module at our temp patterns file + an audit dir we control.
    monkeypatch.setattr(memory_mod, "PATTERNS_FILE", str(patterns_file))
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    (audit_dir / "today.md").write_text(
        "## entry-1\n- an audit line about the refiner agent\n"
    )
    monkeypatch.setattr(memory_mod, "AUDIT_DIR", str(audit_dir))

    # Force the LLM to return a stub.
    agent = MemoryAgent.__new__(MemoryAgent)
    agent.llm = _FakeChat("[stub response — ollama LLM call failed: connection refused]")

    agent.run_learning_loop()

    after = patterns_file.read_text()
    assert after == "# Learned Patterns\n\nseed\n", (
        "stub LLM output leaked into patterns.md:\n" + after
    )
    assert "stub response" not in after
    assert "## Learned on" not in after


def test_run_learning_loop_persists_real_patterns(tmp_path, monkeypatch):
    patterns_file = tmp_path / "patterns.md"
    patterns_file.write_text("# Learned Patterns\n\nseed\n")

    monkeypatch.setattr(memory_mod, "PATTERNS_FILE", str(patterns_file))
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    (audit_dir / "today.md").write_text(
        "## entry-1\n- an audit line about the refiner agent\n"
    )
    monkeypatch.setattr(memory_mod, "AUDIT_DIR", str(audit_dir))

    real = "## Agent Workflow\n- **Pattern**: Sequential Pipeline\n- **Context**: when refining"
    agent = MemoryAgent.__new__(MemoryAgent)
    agent.llm = _FakeChat(real)

    agent.run_learning_loop()

    after = patterns_file.read_text()
    assert "## Learned on" in after, "real patterns should be appended under a Learned-on heading"
    assert "Sequential Pipeline" in after
    assert "stub response" not in after


# ---------------------------------------------------------------------------
# extract_pattern_from_content (on-completion promotion): same contract
# ---------------------------------------------------------------------------
def test_extract_pattern_skips_stub(tmp_path, monkeypatch):
    patterns_file = tmp_path / "patterns.md"
    patterns_file.write_text("# Learned Patterns\n\nseed\n")
    monkeypatch.setattr(memory_mod, "PATTERNS_FILE", str(patterns_file))

    # extract_pattern_from_content imports LLMClient locally, then constructs
    # it. Patch the LLMClient symbol on the llm_client module so the local
    # import yields our fake.
    import agents.llm_client as llm_client_mod
    fake = _FakeChat("[stub response — google LLM call failed: No module named 'google.genai']")
    monkeypatch.setattr(llm_client_mod, "LLMClient", lambda *a, **k: fake)

    result = extract_pattern_from_content("ID-9", "spec.md", "some artifact content")
    assert result is False
    assert patterns_file.read_text() == "# Learned Patterns\n\nseed\n"
    assert "stub response" not in patterns_file.read_text()


def test_extract_pattern_persists_real(tmp_path, monkeypatch):
    patterns_file = tmp_path / "patterns.md"
    patterns_file.write_text("# Learned Patterns\n\nseed\n")
    monkeypatch.setattr(memory_mod, "PATTERNS_FILE", str(patterns_file))

    real = (
        "## Naming Conventions\n"
        "- **Pattern**: Uppercase ID normalization\n"
        "- **Context**: All Idea IDs MUST be uppercase to avoid lookups miss.\n"
    )
    import agents.llm_client as llm_client_mod
    monkeypatch.setattr(llm_client_mod, "LLMClient", lambda *a, **k: _FakeChat(real))

    result = extract_pattern_from_content("ID-9", "spec.md", "some artifact content")
    assert result is True
    after = patterns_file.read_text()
    assert "Uppercase ID normalization" in after
    assert "stub response" not in after
