"""Pipeline router run endpoints (2.19).

The module-level in-memory stores are swapped for fresh dicts per test so no
state leaks between tests or into real data. No executor is involved: the run
endpoint only records a run.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import pipeline_router as pr
from api.models.automation import ExecutionLog, ExecutionStatus, Pipeline, PipelineRun


@pytest.fixture(autouse=True)
def fresh_stores(monkeypatch):
    monkeypatch.setattr(pr, "pipelines_db", {})
    monkeypatch.setattr(pr, "paths_db", {})
    monkeypatch.setattr(pr, "runs_db", {})
    return pr


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(pr.router, prefix="/api/pipelines")
    return TestClient(app)


def _add_pipeline(pid="pipe_test", name="Nightly sync"):
    pr.pipelines_db[pid] = Pipeline(
        pipeline_id=pid,
        name=name,
        paths=[],
        trigger={"type": "MANUAL"},
    )
    return pid


class TestTriggerRun:
    def test_unknown_pipeline_returns_404(self, client):
        assert client.post("/api/pipelines/missing/run").status_code == 404

    def test_run_returns_200_and_records_run(self, client):
        pid = _add_pipeline()
        r = client.post(f"/api/pipelines/{pid}/run")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "running"
        assert body["pipeline_id"] == pid
        run_id = body["run_id"]
        assert run_id in pr.runs_db
        run = pr.runs_db[run_id]
        assert run.pipeline_id == pid
        assert run.status == "RUNNING"

    def test_first_log_is_a_valid_execution_log_with_step_id(self, client):
        pid = _add_pipeline()
        run_id = client.post(f"/api/pipelines/{pid}/run").json()["run_id"]
        (log,) = pr.runs_db[run_id].logs
        assert isinstance(log, ExecutionLog)
        assert log.step_id
        assert log.run_id == run_id
        assert log.pipeline_id == pid
        assert log.status == ExecutionStatus.RUNNING

    def test_log_states_it_was_not_executed(self, client):
        pid = _add_pipeline()
        run_id = client.post(f"/api/pipelines/{pid}/run").json()["run_id"]
        (log,) = pr.runs_db[run_id].logs
        assert "not executed" in (log.execution_reason or "")
        assert "Nightly sync" in (log.execution_reason or "")

    def test_run_is_visible_via_runs_listing(self, client):
        pid = _add_pipeline()
        run_id = client.post(f"/api/pipelines/{pid}/run").json()["run_id"]
        listing = client.get(f"/api/pipelines/{pid}/runs").json()
        assert [r["run_id"] for r in listing] == [run_id]
        assert listing[0]["logs"][0]["step_id"]

    def test_run_is_visible_via_detail_endpoint(self, client):
        pid = _add_pipeline()
        run_id = client.post(f"/api/pipelines/{pid}/run").json()["run_id"]
        detail = client.get(f"/api/pipelines/{pid}/runs/{run_id}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "RUNNING"

    def test_each_trigger_creates_a_distinct_run(self, client):
        pid = _add_pipeline()
        ids = {client.post(f"/api/pipelines/{pid}/run").json()["run_id"] for _ in range(5)}
        assert len(ids) == 5
        assert len(pr.runs_db) == 5

    def test_run_does_not_call_any_executor(self, client, monkeypatch):
        import api.execution_engine as ee
        called = []

        def boom(*a, **k):
            called.append(a)
            raise AssertionError("pipeline run must not execute anything")

        monkeypatch.setattr(ee, "ExecutionEngine", boom, raising=False)
        pid = _add_pipeline()
        assert client.post(f"/api/pipelines/{pid}/run").status_code == 200
        assert called == []


class TestCompleteAndLogAfterTrigger:
    def test_complete_appends_log_and_sets_status(self, client):
        pid = _add_pipeline()
        run_id = client.post(f"/api/pipelines/{pid}/run").json()["run_id"]
        r = client.post(f"/api/pipelines/{pid}/runs/{run_id}/complete", params={"status": "SUCCESS"})
        assert r.status_code == 200
        run = client.get(f"/api/pipelines/{pid}/runs/{run_id}").json()
        assert run["status"] == "SUCCESS"
        assert run["duration_ms"] is not None
        assert run["logs"][-1]["message"] == "Pipeline execution success"

    def test_complete_rejects_unknown_status(self, client):
        pid = _add_pipeline()
        run_id = client.post(f"/api/pipelines/{pid}/run").json()["run_id"]
        r = client.post(f"/api/pipelines/{pid}/runs/{run_id}/complete", params={"status": "DONE"})
        assert r.status_code == 400

    def test_add_log_appends_entry(self, client):
        pid = _add_pipeline()
        run_id = client.post(f"/api/pipelines/{pid}/run").json()["run_id"]
        r = client.post(f"/api/pipelines/{pid}/runs/{run_id}/log", params={"level": "INFO", "message": "hi"})
        assert r.status_code == 200
        logs = client.get(f"/api/pipelines/{pid}/runs/{run_id}").json()["logs"]
        assert logs[-1]["message"] == "hi"

    def test_run_wrong_pipeline_is_404(self, client):
        pid = _add_pipeline()
        other = _add_pipeline("pipe_other", "Other")
        run_id = client.post(f"/api/pipelines/{pid}/run").json()["run_id"]
        assert client.get(f"/api/pipelines/{other}/runs/{run_id}").status_code == 404
