"""P1-6: integration route error responses leak no absolute paths.

Corrupt-file errors return a fixed message that names no path (the full text is logged).
Unexpected exceptions return a generic message with a short error code (the exception is logged).
Known client errors (not found, 400 validation) keep their existing text.
"""
import logging

import pytest
from fastapi.testclient import TestClient

from api.integration_hub import (
    IntegrationConfigCorruptError,
    IntegrationHub,
    PUBLIC_INTEGRATION_CORRUPT_MESSAGE,
)
from api.main import app

LEAK_MARK = "/nonexistent-leak-probe/"


@pytest.fixture
def hub(tmp_path):
    hub = IntegrationHub(str(tmp_path))
    original = app.state.hub
    app.state.hub = hub
    yield hub
    app.state.hub = original


@pytest.fixture
def client():
    return TestClient(app)


def _corrupt(hub):
    with open(hub.config_path, "w") as f:
        f.write("{ not json")


def _assert_path_free(resp, hub):
    text = resp.text
    assert str(hub.base_dir) not in text
    assert hub.config_path not in text
    assert ".corrupt-" not in text
    assert "/" not in resp.json()["detail"]


class TestCorruptFileIsPathFree:
    def test_list_returns_fixed_message(self, client, hub):
        _corrupt(hub)
        resp = client.get("/api/integrations/")
        assert resp.status_code == 500
        assert resp.json()["detail"] == PUBLIC_INTEGRATION_CORRUPT_MESSAGE
        _assert_path_free(resp, hub)

    def test_add_returns_fixed_message(self, client, hub):
        _corrupt(hub)
        resp = client.post("/api/integrations/", json={"name": "a", "type": "native", "config": {}})
        assert resp.status_code == 500
        _assert_path_free(resp, hub)

    def test_patch_returns_fixed_message(self, client, hub):
        _corrupt(hub)
        resp = client.patch("/api/integrations/a", json={"config": {"x": 1}})
        assert resp.status_code == 500
        _assert_path_free(resp, hub)

    def test_delete_returns_fixed_message(self, client, hub):
        _corrupt(hub)
        resp = client.delete("/api/integrations/a")
        assert resp.status_code == 500
        _assert_path_free(resp, hub)

    def test_test_route_returns_fixed_message_before_its_try(self, client, hub):
        _corrupt(hub)
        resp = client.post("/api/integrations/a/test")
        assert resp.status_code == 500
        _assert_path_free(resp, hub)

    def test_tools_route_returns_fixed_message(self, client, hub, monkeypatch):
        monkeypatch.setattr(hub, "execute_action",
                            lambda *a, **k: (_ for _ in ()).throw(IntegrationConfigCorruptError(
                                f"integrations.json is not valid JSON; preserved at {hub.config_path}.corrupt-x")))
        resp = client.get("/api/integrations/a/tools")
        assert resp.status_code == 500
        _assert_path_free(resp, hub)

    def test_corrupt_message_is_logged_with_full_text(self, client, hub, caplog):
        _corrupt(hub)
        with caplog.at_level(logging.ERROR):
            client.get("/api/integrations/")
        logged = " ".join(r.getMessage() for r in caplog.records)
        assert ".corrupt-" in logged


class TestGenericErrorsAreGeneric:
    def _boom(self, *_a, **_k):
        raise RuntimeError(f"secret detail at {LEAK_MARK}db.json")

    def test_call_tool(self, client, hub, monkeypatch, caplog):
        monkeypatch.setattr(hub, "execute_action", self._boom)
        with caplog.at_level(logging.ERROR):
            resp = client.post("/api/integrations/a/call", json={"name": "t", "arguments": {}})
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "error code" in detail
        assert LEAK_MARK not in resp.text and "secret detail" not in resp.text
        assert any("secret detail" in r.getMessage() or "secret detail" in str(r.exc_info and r.exc_info[1])
                   for r in caplog.records)

    def test_list_tools(self, client, hub, monkeypatch):
        monkeypatch.setattr(hub, "execute_action", self._boom)
        resp = client.get("/api/integrations/a/tools")
        assert resp.status_code == 500
        assert "error code" in resp.json()["detail"]
        assert LEAK_MARK not in resp.text

    def test_add(self, client, hub, monkeypatch):
        monkeypatch.setattr(hub, "add_integration", self._boom)
        resp = client.post("/api/integrations/", json={"name": "a", "type": "native", "config": {}})
        assert resp.status_code == 500
        assert "error code" in resp.json()["detail"]
        assert LEAK_MARK not in resp.text

    def test_patch(self, client, hub, monkeypatch):
        monkeypatch.setattr(hub, "update_integration", self._boom)
        resp = client.patch("/api/integrations/a", json={"config": {}})
        assert resp.status_code == 500
        assert "error code" in resp.json()["detail"]
        assert LEAK_MARK not in resp.text

    def test_jira_test_route(self, client, hub, monkeypatch):
        # Fake HTTP: the Jira call succeeds, then recording the status fails.
        from unittest.mock import AsyncMock, patch
        hub.add_integration("jira_x", "native", {
            "adapter_module": "api.adapters.jira", "jira_url": "https://x.invalid", "token": "fake-tok"})
        fake = AsyncMock()
        fake.__aenter__.return_value = fake
        fake.__aexit__.return_value = AsyncMock()
        ok = AsyncMock(status_code=200)
        ok.json.return_value = {"self": "u"}
        fake.get.return_value = ok
        real_update = hub.update_status

        def fail_on_connected(name, status):
            if status == "connected":
                raise RuntimeError(f"secret detail at {LEAK_MARK}db.json")
            return real_update(name, status)

        monkeypatch.setattr(hub, "update_status", fail_on_connected)
        with patch("httpx.AsyncClient", return_value=fake):
            resp = client.post("/api/integrations/jira_x/test")
        assert resp.status_code == 500
        assert "error code" in resp.json()["detail"]
        assert LEAK_MARK not in resp.text

    def test_error_codes_are_distinct_per_route(self, client, hub, monkeypatch):
        monkeypatch.setattr(hub, "execute_action", self._boom)
        monkeypatch.setattr(hub, "add_integration", self._boom)
        a = client.post("/api/integrations/a/call", json={"name": "t", "arguments": {}}).json()["detail"]
        b = client.post("/api/integrations/", json={"name": "a", "type": "native", "config": {}}).json()["detail"]
        assert a != b


class TestKnownClientErrorsUnchanged:
    def test_patch_missing_integration_keeps_not_found_text(self, client, hub):
        resp = client.patch("/api/integrations/nope", json={"config": {}})
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_add_value_error_is_400(self, client, hub, monkeypatch):
        def bad(*_a, **_k):
            raise ValueError("bad name given")
        monkeypatch.setattr(hub, "add_integration", bad)
        resp = client.post("/api/integrations/", json={"name": "a", "type": "native", "config": {}})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "bad name given"

    def test_delete_missing_is_404(self, client, hub):
        resp = client.delete("/api/integrations/nope")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Integration not found"

    def test_tool_call_success_shape_unchanged(self, client, hub, monkeypatch):
        monkeypatch.setattr(hub, "execute_action", lambda *a, **k: {"result": {"ok": True}, "logs": ""})
        resp = client.post("/api/integrations/a/call", json={"name": "t", "arguments": {}})
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "data": {"result": {"ok": True}, "logs": ""}}
