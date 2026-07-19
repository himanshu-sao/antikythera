import pytest
from fastapi.testclient import TestClient

# Import via the assembled app (api.main) to avoid the pre-existing
# api.workflow_router -> api.main -> api.workflow_router circular import,
# which trips only when the router is imported in isolation.
from api.main import app


class _FakeEngine:
    """Minimal stand-in for ExecutionEngine — records calls without touching JSON state."""

    def __init__(self, *, fail_with=None):
        self.fail_with = fail_with
        self.calls = []

    def start_run(self, template_id, inputs):
        self.calls.append((template_id, inputs))
        if self.fail_with is not None:
            raise self.fail_with
        return "run_test_123"


@pytest.fixture
def engine():
    return _FakeEngine()


@pytest.fixture
def client(engine):
    # The real app already mounts workflow_router and binds app.state.engine
    # at main.py:89. Swap in the fake engine for isolation, restore on teardown.
    previous = getattr(app.state, "engine", None)
    app.state.engine = engine
    yield TestClient(app)
    app.state.engine = previous


def test_trigger_workflow_starts_run_and_returns_run_id(client, engine):
    response = client.post(
        "/api/workflows/trigger",
        json={"template_id": "github_pr_release", "inputs": {"repo": "antikythera"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["run_id"] == "run_test_123"
    assert engine.calls == [("github_pr_release", {"repo": "antikythera"})]


def test_trigger_workflow_defaults_inputs_to_empty_dict(client, engine):
    response = client.post(
        "/api/workflows/trigger",
        json={"template_id": "github_pr_release"},
    )
    assert response.status_code == 200
    assert engine.calls == [("github_pr_release", {})]


def test_trigger_workflow_missing_template_returns_404(client, engine):
    engine.fail_with = ValueError("Template missing_tpl not found")
    response = client.post(
        "/api/workflows/trigger",
        json={"template_id": "missing_tpl", "inputs": {}},
    )
    assert response.status_code == 404
    assert "missing_tpl" in response.json()["detail"]


def test_trigger_workflow_engine_error_returns_500(client, engine):
    engine.fail_with = RuntimeError("boom")
    response = client.post(
        "/api/workflows/trigger",
        json={"template_id": "github_pr_release", "inputs": {}},
    )
    assert response.status_code == 500
    assert "boom" in response.json()["detail"]
