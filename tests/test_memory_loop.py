"""Memory agent learning loop, run end to end against an isolated data dir.

This used to be a manual script that wrote a dummy item straight into the
real ``automation-ideas/pipeline-state.json``, ran the real orchestrator and
LLM, and asserted nothing. It now relies on the root ``conftest.py``
``isolate_data_dir`` fixture (every agent path points at ``tmp_path``) and a
fake LLM, so it is deterministic, offline, and cannot touch real data.
"""

import os

import agents.audit as audit
import agents.memory as memory
import agents.state as state_module
from agents.memory import MemoryAgent


class _FakeLLM:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def chat(self, system_prompt, user_prompt, **kwargs):
        self.calls.append(user_prompt)
        return self.reply


def _agent_with(monkeypatch, reply):
    # Swap only the instance's client. memory.LLMClient itself stays real,
    # because the stub guard calls LLMClient.is_stub().
    fake = _FakeLLM(reply)
    agent = MemoryAgent(config_path="config.yaml")
    monkeypatch.setattr(agent, "llm", fake)
    return agent, fake


def _write_audit_entry():
    audit.log_action(
        "refiner", "TEST-MEM-001", "REFINEMENT", "refined idea",
        inputs="title: Testing Memory Agent", outputs="confidence: 85",
    )


def test_fixture_isolates_every_real_data_path(isolate_data_dir):
    real_root = os.path.dirname(os.path.dirname(os.path.abspath(memory.__file__)))
    real_data = os.path.join(real_root, "automation-ideas")
    for path in (state_module.STATE_FILE, memory.PATTERNS_FILE, memory.AUDIT_DIR, audit.AUDIT_DIR):
        assert os.path.commonpath([path, str(isolate_data_dir)]) == str(isolate_data_dir), path
        assert not path.startswith(real_data + os.sep), path


def test_state_round_trip_stays_in_tmp(isolate_data_dir):
    state = {"items": {"TEST-MEM-001": {"title": "Testing Memory Agent", "stage": "INTAKE"}}}
    state_module.save_state(state)
    assert (isolate_data_dir / "pipeline-state.json").exists()
    assert state_module.load_state()["items"]["TEST-MEM-001"]["stage"] == "INTAKE"


def test_learning_loop_appends_patterns_from_audit_entries(isolate_data_dir, monkeypatch):
    _write_audit_entry()
    reply = "## Refinement\n- **Pattern**: Refine short ideas into full specs.\n- **Context**: INTAKE items."
    agent, fake = _agent_with(monkeypatch, reply)

    agent.run_learning_loop()

    assert len(fake.calls) == 1
    assert "TEST-MEM-001" in fake.calls[0]
    patterns = (isolate_data_dir / "brain" / "patterns.md").read_text()
    assert "## Learned on" in patterns
    assert "Refine short ideas into full specs." in patterns


def test_learning_loop_skips_write_on_stub_reply(isolate_data_dir, monkeypatch):
    _write_audit_entry()
    agent, _ = _agent_with(monkeypatch, "[stub response — google LLM call failed: offline]")

    agent.run_learning_loop()

    assert not (isolate_data_dir / "brain" / "patterns.md").exists()


def test_learning_loop_no_audit_entries_makes_no_llm_call(isolate_data_dir, monkeypatch):
    agent, fake = _agent_with(monkeypatch, "## Unused\n- **Pattern**: never written")

    agent.run_learning_loop()

    assert fake.calls == []
    assert not (isolate_data_dir / "brain" / "patterns.md").exists()
