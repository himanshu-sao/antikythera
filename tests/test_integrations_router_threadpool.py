"""R12 / P2-5: synchronous hub calls run off the event loop.

Blocking hub work (MCP subprocess, file I/O) must run in the threadpool so other
requests on the loop keep being served. Response shapes stay the same.
"""
import threading
import time

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


def _on_event_loop_thread() -> bool:
    """True when called from the thread that is running an asyncio loop (a blocked loop)."""
    import asyncio
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


class TestRunsInThreadpool:
    @pytest.mark.parametrize("path, method, body", [
        ("/api/integrations/a/call", "post", {"name": "t", "arguments": {}}),
        ("/api/integrations/a/tools", "get", None),
    ])
    def test_execute_action_called_off_the_loop_thread(self, client, hub, monkeypatch, path, method, body):
        seen = {}

        def record(*_a, **_k):
            seen["on_loop"] = _on_event_loop_thread()
            return {"result": {}, "logs": ""}

        monkeypatch.setattr(hub, "execute_action", record)
        kwargs = {"json": body} if body is not None else {}
        resp = getattr(client, method)(path, **kwargs)
        assert resp.status_code == 200
        assert seen["on_loop"] is False, "hub call ran on the event loop thread"

    def test_list_and_delete_and_patch_run_in_threadpool(self, client, hub, monkeypatch):
        on_loop = {}
        real = {n: getattr(hub, n) for n in ("list_integrations", "delete_integration", "update_integration",
                                              "add_integration")}

        def wrap(name):
            def inner(*a, **k):
                on_loop[name] = _on_event_loop_thread()
                return real[name](*a, **k)
            return inner

        for n in real:
            monkeypatch.setattr(hub, n, wrap(n))
        hub.add_integration("svc", "native", {"adapter_module": "x"})
        assert client.get("/api/integrations/").status_code == 200
        assert client.patch("/api/integrations/svc", json={"config": {"a": 1}}).status_code == 200
        assert client.delete("/api/integrations/svc").status_code == 200
        for n in ("list_integrations", "update_integration", "delete_integration"):
            assert on_loop[n] is False, f"{n} ran on the event loop thread"

    def test_event_loop_stays_responsive_during_blocking_call(self, client, hub, monkeypatch):
        """A slow hub call must not stall a concurrent cheap request."""
        started = threading.Event()
        release = threading.Event()

        def slow(*_a, **_k):
            started.set()
            release.wait(5)
            return {"result": {}, "logs": ""}

        monkeypatch.setattr(hub, "execute_action", slow)
        result = {}

        def call_slow():
            result["resp"] = client.post("/api/integrations/a/call", json={"name": "t", "arguments": {}})

        worker = threading.Thread(target=call_slow)
        worker.start()
        try:
            assert started.wait(5)
            # A second request is served while the first is still blocked in the hub.
            other = client.get("/api/integrations/")
            assert other.status_code == 200
        finally:
            release.set()
            worker.join(10)
        assert result["resp"].status_code == 200

    def test_response_shapes_unchanged(self, client, hub, monkeypatch):
        monkeypatch.setattr(hub, "execute_action", lambda *a, **k: {"result": {"x": 1}, "logs": "l"})
        resp = client.post("/api/integrations/a/call", json={"name": "t", "arguments": {}})
        assert resp.json() == {"status": "success", "data": {"result": {"x": 1}, "logs": "l"}}
        hub.add_integration("svc", "native", {"adapter_module": "x"})
        assert client.post("/api/integrations/", json={"name": "b", "type": "native", "config": {}}).json() == {
            "status": "success", "message": "Integration b added"}
