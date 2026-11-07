"""R29 / P2-19: the Jira connection test with no token or URL answers 404, not 500.

The hub has no vault any more (``hub.vault`` is None), so the old vault fallback raised
AttributeError. A missing credential must produce the intended 404 "Missing Jira
credentials" and mark the integration as errored. The success path is unchanged.
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.integration_hub import IntegrationHub
from api.main import app


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


def _status(hub, name):
    return hub.get_integration(name).get("status")


def _fake_httpx(status_code=200, body=None):
    fake = AsyncMock()
    fake.__aenter__.return_value = fake
    fake.__aexit__.return_value = False  # a truthy value would swallow exceptions
    resp = AsyncMock(status_code=status_code)
    resp.json.return_value = body if body is not None else {"self": "u"}
    fake.get.return_value = resp
    return fake


class TestMissingCredentials:
    def test_no_token_no_url_is_404(self, client, hub):
        assert hub.vault is None
        hub.add_integration("jira_a", "native", {"adapter_module": "api.adapters.jira"})
        resp = client.post("/api/integrations/jira_a/test")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Missing Jira credentials"
        assert _status(hub, "jira_a") == "error"

    def test_token_only_is_404(self, client, hub):
        hub.add_integration("jira_b", "native", {"adapter_module": "api.adapters.jira", "token": "fake-tok"})
        resp = client.post("/api/integrations/jira_b/test")
        assert resp.status_code == 404
        assert _status(hub, "jira_b") == "error"

    def test_url_only_is_404(self, client, hub):
        hub.add_integration("jira_c", "native", {"adapter_module": "api.adapters.jira", "jira_url": "https://x.invalid"})
        resp = client.post("/api/integrations/jira_c/test")
        assert resp.status_code == 404

    def test_unset_env_placeholders_are_404(self, client, hub, monkeypatch):
        monkeypatch.delenv("W5_NO_SUCH_TOKEN", raising=False)
        monkeypatch.delenv("W5_NO_SUCH_URL", raising=False)
        hub.add_integration("jira_d", "native", {
            "adapter_module": "api.adapters.jira",
            "jira_url": "${env:W5_NO_SUCH_URL}", "token": "${env:W5_NO_SUCH_TOKEN}"})
        resp = client.post("/api/integrations/jira_d/test")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Missing Jira credentials"

    def test_name_containing_jira_without_adapter_module_is_404(self, client, hub):
        hub.add_integration("my-jira", "native", {})
        resp = client.post("/api/integrations/my-jira/test")
        assert resp.status_code == 404

    def test_access_token_key_is_accepted(self, client, hub):
        hub.add_integration("jira_e", "native", {
            "adapter_module": "api.adapters.jira", "access_token": "fake-tok", "url": "https://x.invalid"})
        with patch("httpx.AsyncClient", return_value=_fake_httpx()):
            resp = client.post("/api/integrations/jira_e/test")
        assert resp.status_code == 200


class TestSuccessAndUpstreamPathsUnchanged:
    def _add(self, hub, name="jira_ok"):
        hub.add_integration(name, "native", {
            "adapter_module": "api.adapters.jira", "jira_url": "https://x.invalid", "token": "fake-tok"})

    def test_success_marks_connected(self, client, hub):
        self._add(hub)
        with patch("httpx.AsyncClient", return_value=_fake_httpx(200, {"self": "me"})):
            resp = client.post("/api/integrations/jira_ok/test")
        assert resp.status_code == 200
        assert resp.json() == {"status": "success", "data": {"principal": {"self": "me"}}}
        assert _status(hub, "jira_ok") == "connected"

    def test_upstream_401_keeps_status_and_marks_error(self, client, hub):
        self._add(hub)
        with patch("httpx.AsyncClient", return_value=_fake_httpx(401)):
            resp = client.post("/api/integrations/jira_ok/test")
        assert resp.status_code == 401
        assert "401" in resp.json()["detail"]
        assert _status(hub, "jira_ok") == "error"

    def test_unreachable_is_502_without_exception_text(self, client, hub):
        import httpx
        self._add(hub)
        fake = _fake_httpx()
        fake.get.side_effect = httpx.ConnectError("connect failed at /nonexistent-leak-probe/sock")
        with patch("httpx.AsyncClient", return_value=fake):
            resp = client.post("/api/integrations/jira_ok/test")
        assert resp.status_code == 502
        assert "/nonexistent-leak-probe/" not in resp.text
        assert _status(hub, "jira_ok") == "error"

    def test_unknown_integration_is_404(self, client, hub):
        assert client.post("/api/integrations/nope/test").status_code == 404

    def test_plain_native_integration_assumed_reachable(self, client, hub):
        hub.add_integration("plain", "native", {"adapter_module": "x"})
        resp = client.post("/api/integrations/plain/test")
        assert resp.status_code == 200
        assert _status(hub, "plain") == "connected"
