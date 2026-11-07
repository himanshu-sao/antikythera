"""API hardening for the engine/board/brain/trigger routes.

Covers: webhook run key (R19), facade priority forwarding (P2-16), inline-output
lost update (P0-6), brain approve 409 (R24), safe corrupt-file responses (P1-6
and the shared handler), and engine/board route 500s. Everything runs on
tmp_path state; no LLM, no network.
"""
import json
import os
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.main as api_main
from api import board_router, trigger_router
from api.brain_schemas import CognitiveDelta
from api.workflow_state_manager import WorkflowStateManager


SAFE_FRAGMENTS = ("corrupt", "backup")


def _assert_safe_500(response, tmp_path):
    assert response.status_code == 500, response.text
    detail = response.json()["detail"]
    low = detail.lower()
    assert all(f in low for f in SAFE_FRAGMENTS), detail
    # No absolute path, no file name, no tmp dir in the client-facing text.
    assert str(tmp_path) not in detail
    assert "pipeline-state.json" not in detail
    assert "/" not in detail


@pytest.fixture
def sm():
    return api_main.get_state_manager()


@pytest.fixture
def client():
    # raise_server_exceptions=False so an unhandled exception shows up as a 500
    # response instead of being re-raised into the test.
    return TestClient(api_main.app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# R19 / P2-15: webhook runs use current_step_index
# ---------------------------------------------------------------------------

class TestWebhookRunKey:
    @pytest.fixture
    def wired(self, sm, monkeypatch):
        monkeypatch.setattr(trigger_router, "state_manager", sm)
        monkeypatch.setattr(trigger_router, "hub", object())
        app = FastAPI()
        app.include_router(trigger_router.router)
        return TestClient(app), sm

    def test_webhook_run_has_current_step_index_not_current_step(self, wired):
        client, sm = wired
        r = client.post("/api/triggers/webhook/github", json={"number": 7})
        assert r.status_code == 200, r.text
        run = sm.get_run(r.json()["run_id"])
        assert run["current_step_index"] == 0
        assert "current_step" not in run

    def test_webhook_run_other_fields_unchanged(self, wired):
        client, sm = wired
        payload = {"issue": {"key": "JIRA-9"}}
        r = client.post("/api/triggers/webhook/jira", json=payload)
        run = sm.get_run(r.json()["run_id"])
        assert run["template_id"] == "jira_triage"
        assert run["status"] == "RUNNING"
        assert run["trigger_payload"] == payload
        assert run["retry_count"] == 0
        assert sm.get_run_id_for_item("JIRA-9") == r.json()["run_id"]

    def test_webhook_run_can_be_advanced_by_the_engine(self, wired):
        # The engine indexes run["current_step_index"]; a webhook run used to
        # raise KeyError there. The auto-created template has no steps, so the
        # run completes.
        from api.execution_engine import ExecutionEngine

        class _Esc:
            def escalate_to_orchestrator(self, **kw):
                return None

        client, sm = wired
        run_id = client.post("/api/triggers/webhook/other", json={"number": 1}).json()["run_id"]
        ExecutionEngine(sm, object(), _Esc()).process_next_step(run_id)
        assert sm.get_run(run_id)["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# P2-16 / R20: the facade forwards priority; the route makes one write
# ---------------------------------------------------------------------------

class TestPriorityForwarding:
    def test_facade_create_item_forwards_priority(self, tmp_path):
        sm = WorkflowStateManager(str(tmp_path))
        assert sm.create_item("f-1", "T", priority="HIGH")
        assert sm.create_item("f-2", "T")
        assert sm.kanban.get_item_details("F-1")["priority"] == "high"
        assert sm.kanban.get_item_details("F-2")["priority"] == "medium"

    def test_create_route_makes_no_follow_up_update(self, sm, client, monkeypatch):
        calls = []
        real_update = sm.update_item
        monkeypatch.setattr(sm, "update_item", lambda *a, **k: (calls.append(a), real_update(*a, **k))[1])
        r = client.post("/api/items", json={"item_id": "r-1", "title": "T", "priority": "critical"})
        assert r.status_code == 200, r.text
        assert calls == []
        assert sm.kanban.get_item_details("R-1")["priority"] == "critical"

    def test_create_route_default_priority_is_medium(self, sm, client):
        client.post("/api/items", json={"item_id": "r-2", "title": "T"})
        assert sm.kanban.get_item_details("R-2")["priority"] == "medium"

    def test_create_route_sets_priority_atomically_with_the_item(self, sm, client, monkeypatch):
        # If a second write were still used, failing it would leave the default.
        monkeypatch.setattr(sm.kanban, "update_item", lambda *a, **k: False)
        client.post("/api/items", json={"item_id": "r-3", "title": "T", "priority": "low"})
        assert sm.kanban.get_item_details("R-3")["priority"] == "low"

    def test_board_router_source_has_no_priority_todo(self):
        import inspect
        assert "TODO: forward priority" not in inspect.getsource(board_router)


# ---------------------------------------------------------------------------
# P0-6 / R11: inline output update is one locked read-modify-write
# ---------------------------------------------------------------------------

class TestInlineOutputLock:
    def _seed(self, sm, item_id="IO-1"):
        assert sm.create_item(item_id, "T")
        return item_id

    def test_inline_output_is_saved(self, sm, client):
        self._seed(sm)
        r = client.post("/api/item/io-1/inline-output", params={"content": "hello"})
        assert r.status_code == 200, r.text
        assert sm.get_item_details("IO-1")["inline_output"] == "hello"

    def test_unknown_item_is_404(self, sm, client):
        assert client.post("/api/item/nope/inline-output", params={"content": "x"}).status_code == 404

    def test_interleaved_write_is_not_lost(self, sm, client, monkeypatch):
        """A writer that lands between this route's load and save must survive.

        The route re-reads under the shared lock. A competing writer is simulated
        from another thread that tries to commit during the route's critical
        section; it can only run before or after it, never in the middle, so both
        changes must be present at the end.
        """
        import agents.state as agent_state

        self._seed(sm)
        entered = threading.Event()
        release = threading.Event()
        real_save = agent_state.save_state

        def slow_save(state):
            # Pause inside the route's critical section, after its load.
            entered.set()
            release.wait(timeout=5)
            real_save(state)

        monkeypatch.setattr(agent_state, "save_state", slow_save)

        def competing_writer():
            entered.wait(timeout=5)
            # This update needs the same lock the route holds, so it blocks
            # until the route has saved. Free the route right away.
            threading.Timer(0.2, release.set).start()
            sm.update_item("IO-1", {"title": "changed by writer"})

        t = threading.Thread(target=competing_writer)
        t.start()
        r = client.post("/api/item/io-1/inline-output", params={"content": "mine"})
        t.join(timeout=10)
        assert r.status_code == 200
        item = sm.get_item_details("IO-1")
        assert item["inline_output"] == "mine"
        assert item["title"] == "changed by writer"

    def test_sequential_writers_keep_both_fields(self, sm, client):
        self._seed(sm)
        sm.update_item("IO-1", {"title": "first"})
        client.post("/api/item/io-1/inline-output", params={"content": "second"})
        sm.update_item("IO-1", {"priority": "high"})
        item = sm.get_item_details("IO-1")
        assert (item["title"], item["inline_output"], item["priority"]) == ("first", "second", "high")


# ---------------------------------------------------------------------------
# R24: approving a refused delta is 409, a missing one 404
# ---------------------------------------------------------------------------

class TestApproveDeltaStatus:
    def _write(self, sm, **fields):
        data = {"target_artifact": "memory.md", "change_type": "REVISE", "proposed_content": "",
                "reason": "r", "status": "PENDING", "confidence_score": 50}
        data.update(fields)
        delta = CognitiveDelta(**data)
        with open(os.path.join(sm.brain.deltas_dir, f"{delta.delta_id}.json"), "w") as f:
            f.write(delta.model_dump_json())
        return delta.delta_id

    def test_empty_revise_returns_409_with_clear_message(self, sm, client):
        delta_id = self._write(sm, change_type="REVISE", proposed_content="")
        r = client.post(f"/api/brain/deltas/{delta_id}/approve")
        assert r.status_code == 409, r.text
        detail = r.json()["detail"]
        assert "refused" in detail.lower()
        assert "empty" in detail.lower()
        assert "not found" not in detail.lower()

    def test_empty_replace_returns_409(self, sm, client):
        delta_id = self._write(sm, change_type="REPLACE", proposed_content="   ")
        assert client.post(f"/api/brain/deltas/{delta_id}/approve").status_code == 409

    def test_refused_delta_leaves_artifact_untouched(self, sm, client):
        artifact = os.path.join(sm.brain.knowledge_dir, "memory.md")
        with open(artifact, "w") as f:
            f.write("keep")
        delta_id = self._write(sm, proposed_content="")
        client.post(f"/api/brain/deltas/{delta_id}/approve")
        assert open(artifact).read() == "keep"

    def test_true_not_found_is_still_404(self, client):
        r = client.post("/api/brain/deltas/does-not-exist/approve")
        assert r.status_code == 404
        assert r.json()["detail"] == "Delta not found"

    def test_valid_delta_is_approved(self, sm, client):
        delta_id = self._write(sm, change_type="REVISE", proposed_content="new text")
        r = client.post(f"/api/brain/deltas/{delta_id}/approve")
        assert r.status_code == 200
        assert r.json() == {"success": True}

    def test_delta_exists_helper(self, sm):
        delta_id = self._write(sm, proposed_content="x")
        assert sm.brain.delta_exists(delta_id) is True
        assert sm.brain.delta_exists("nope") is False


# ---------------------------------------------------------------------------
# P1-6 and the shared handler: corrupt state gives a safe 500 on every route
# ---------------------------------------------------------------------------

class TestCorruptStateSafeResponses:
    @pytest.fixture
    def corrupt(self, sm):
        with open(sm.kanban.path, "w") as f:
            f.write("{ this is not json")
        return sm

    def test_get_state_is_safe(self, corrupt, client, tmp_path):
        _assert_safe_500(client.get("/api/state"), tmp_path)

    def test_get_item_route_is_safe(self, corrupt, client, tmp_path):
        _assert_safe_500(client.get("/api/item/x-1"), tmp_path)

    def test_orchestrator_get_is_safe(self, corrupt, client, tmp_path):
        _assert_safe_500(client.get("/api/orchestrator/x-1"), tmp_path)

    def test_orchestrator_transition_is_safe(self, corrupt, client, tmp_path):
        r = client.post("/api/orchestrator/transition", json={"item_id": "x-1", "target_phase": "DISCOVERY"})
        _assert_safe_500(r, tmp_path)

    def test_orchestrator_propose_is_safe(self, corrupt, client, tmp_path):
        r = client.post("/api/orchestrator/propose", json={"item_id": "x-1", "proposal": {}})
        _assert_safe_500(r, tmp_path)

    def test_board_create_is_safe(self, corrupt, client, tmp_path):
        _assert_safe_500(client.post("/api/items", json={"item_id": "n-1", "title": "T"}), tmp_path)

    def test_board_patch_delete_comment_move_reorder_are_safe(self, corrupt, client, tmp_path):
        _assert_safe_500(client.patch("/api/item/x-1", json={"title": "T"}), tmp_path)
        _assert_safe_500(client.delete("/api/item/x-1"), tmp_path)
        _assert_safe_500(client.post("/api/item/x-1/comment", json={"author": "a", "body": "b"}), tmp_path)
        _assert_safe_500(client.post("/api/move", json={"item_id": "x-1", "new_stage": "DONE"}), tmp_path)
        _assert_safe_500(client.post("/api/items/reorder", json={"stage": "INTAKE", "ordered_ids": ["x-1"]}), tmp_path)

    def test_artifact_route_is_safe(self, corrupt, client, tmp_path):
        _assert_safe_500(client.get("/api/item/x-1/artifact/spec.md"), tmp_path)

    def test_engine_get_run_is_safe(self, sm, client, tmp_path):
        with open(sm.runs.path, "w") as f:
            f.write("[1, 2, 3]")  # valid JSON, wrong root: also corrupt
        _assert_safe_500(client.get("/api/engine/run/run_1"), tmp_path)

    def test_engine_start_is_safe(self, sm, client, tmp_path):
        sm.templates.save_template("t", {"name": "t", "steps": []})
        with open(sm.runs.path, "w") as f:
            f.write("{nope")
        r = client.post("/api/engine/start", json={"template_id": "t", "inputs": {}})
        assert r.status_code == 500
        detail = r.json()["detail"]
        assert str(tmp_path) not in detail
        assert "workflow_runs.json" not in detail

    def test_full_message_is_logged_server_side(self, corrupt, client, caplog):
        with caplog.at_level("ERROR"):
            client.get("/api/state")
        assert any("pipeline-state.json" in r.getMessage() for r in caplog.records)

    def test_backup_was_written(self, corrupt, client):
        client.get("/api/state")
        base = os.path.basename(corrupt.kanban.path)
        names = [n for n in os.listdir(os.path.dirname(corrupt.kanban.path)) if n.startswith(base + ".corrupt-")]
        assert len(names) == 1

    def test_healthy_state_is_unaffected(self, sm, client):
        sm.create_item("ok-1", "T")
        r = client.get("/api/state")
        assert r.status_code == 200
        assert "OK-1" in r.json()["items"]

    def test_non_corrupt_errors_keep_their_status(self, client):
        assert client.get("/api/item/missing").status_code == 404


class TestEngineStartCorruptTemplate:
    def test_corrupt_template_file_gives_safe_500_from_engine_start(self, sm, client, tmp_path):
        # The template lookup happens before any run is written, so a corrupt
        # templates file reaches the route's own except clause.
        with open(sm.templates.path, "w") as f:
            f.write("{broken")
        r = client.post("/api/engine/start", json={"template_id": "t", "inputs": {}})
        _assert_safe_500(r, tmp_path)
        assert "workflow_templates.json" not in r.json()["detail"]
