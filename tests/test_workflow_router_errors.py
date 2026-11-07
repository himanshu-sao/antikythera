"""P1-6: workflow_router error responses are generic and path-free.

Also pins that 404s raised inside a try are no longer turned into 500s.
"""
import logging

import pytest
from fastapi.testclient import TestClient

from api.main import app

LEAK_MARK = "/nonexistent-leak-probe/"


@pytest.fixture
def client():
    return TestClient(app)


class _Boom:
    """Stand-in manager whose every method raises an error that names a path."""

    def __getattr__(self, name):
        def raiser(*_a, **_k):
            raise RuntimeError(f"disk exploded at {LEAK_MARK}workflow_runs.json")
        return raiser


class _FakeState:
    templates = _Boom()
    runs = _Boom()
    bindings = _Boom()


@pytest.fixture
def broken_state(monkeypatch):
    import api.workflow_router as wr
    monkeypatch.setattr(wr, "get_state_manager", lambda: _FakeState())


def _assert_generic(resp, code):
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert f"error code {code}" in detail
    assert LEAK_MARK not in resp.text
    assert "disk exploded" not in resp.text


class TestGenericErrors:
    def test_delete_template(self, client, broken_state):
        _assert_generic(client.delete("/api/workflows/templates/t"), "TEMPLATE_DELETE_FAILED")

    def test_list_templates(self, client, broken_state):
        _assert_generic(client.get("/api/workflows/templates"), "TEMPLATE_LIST_FAILED")

    def test_get_template(self, client, broken_state):
        _assert_generic(client.get("/api/workflows/templates/t"), "TEMPLATE_GET_FAILED")

    def test_save_template(self, client, broken_state):
        _assert_generic(client.post("/api/workflows/templates", json={"template_id": "t", "steps": []}),
                        "TEMPLATE_SAVE_FAILED")

    def test_run_details(self, client, broken_state):
        _assert_generic(client.get("/api/workflows/runs/r1"), "RUN_GET_FAILED")

    def test_run_timeline(self, client, broken_state):
        _assert_generic(client.get("/api/workflows/runs/r1/timeline"), "RUN_TIMELINE_FAILED")

    def test_item_run(self, client, broken_state):
        _assert_generic(client.get("/api/workflows/items/ID-1/run"), "ITEM_RUN_FAILED")

    def test_trigger(self, client, monkeypatch):
        class Engine:
            def start_run(self, *_a, **_k):
                raise RuntimeError(f"disk exploded at {LEAK_MARK}x")
        monkeypatch.setattr(app.state, "engine", Engine(), raising=False)
        _assert_generic(client.post("/api/workflows/trigger", json={"template_id": "t"}), "WORKFLOW_TRIGGER_FAILED")

    def test_exception_is_logged_server_side(self, client, broken_state, caplog):
        with caplog.at_level(logging.ERROR):
            client.get("/api/workflows/templates")
        assert any("disk exploded" in (r.getMessage() + str(r.exc_info)) for r in caplog.records)


class TestCorruptFileIsPathFree:
    def test_corrupt_state_error_gets_the_fixed_message(self, client, monkeypatch):
        from api.managers.base import CorruptStateError
        import api.workflow_router as wr

        class T:
            def list_templates(self):
                raise CorruptStateError("/real/abs/path/workflow_templates.json",
                                        "/real/abs/path/workflow_templates.json.corrupt-1", ValueError("x"))

        class S:
            templates = T()

        monkeypatch.setattr(wr, "get_state_manager", lambda: S())
        resp = client.get("/api/workflows/templates")
        assert resp.status_code == 500
        assert "/real/abs/path" not in resp.text
        assert "corrupt" in resp.json()["detail"].lower()


class TestNotFoundIsNotA500:
    def test_get_missing_template_is_404(self, client):
        resp = client.get("/api/workflows/templates/definitely_missing_template_xyz")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Template not found"

    def test_delete_missing_template_is_404(self, client):
        resp = client.delete("/api/workflows/templates/definitely_missing_template_xyz")
        assert resp.status_code == 404

    def test_missing_run_is_404(self, client):
        resp = client.get("/api/workflows/runs/definitely_missing_run_xyz")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Run not found"

    def test_trigger_unknown_template_is_404(self, client):
        resp = client.post("/api/workflows/trigger", json={"template_id": "definitely_missing_template_xyz"})
        assert resp.status_code == 404
