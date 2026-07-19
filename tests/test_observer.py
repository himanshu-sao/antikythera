import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.brain_api import router as brain_router
from api.brain_schemas import ObserverEvent
import os
import json

@pytest.fixture
def client():
    # The dead module-level `app` in brain_api.py was removed (P3.5); build a
    # throwaway app here that mounts just the brain router for isolation.
    app = FastAPI()
    app.include_router(brain_router)
    return TestClient(app)

def test_ingest_event_triggers_delta(client):
    # Test Rule 1: Preference Detection
    event_payload = {
        "event_type": "USER_INTERVENTION",
        "event_data": {
            "user_comment": "I prefer concise responses."
        }
    }
    response = client.post("/api/observer/event", json=event_payload)
    assert response.status_code == 200
    
    # Verify delta was created
    delta_res = client.get("/api/brain/deltas/pending")
    assert delta_res.status_code == 200
    deltas = delta_res.json()
    assert len(deltas) > 0
    assert deltas[0]["target_artifact"] == "user.md"
    assert "concise responses" in deltas[0]["proposed_content"]

    # Test Rule 2: Error Detection
    error_payload = {
        "event_type": "TOOL_ERROR",
        "event_data": {
            "error_msg": "Permission denied: cannot write to /root"
        }
    }
    response = client.post("/api/observer/event", json=error_payload)
    assert response.status_code == 200
    
    delta_res = client.get("/api/brain/deltas/pending")
    deltas = delta_res.json()
    # Should have the preference delta + the error delta
    assert len(deltas) >= 2
    # IMPORTANT: The error detection rule in ObserverManager uses "error_msg" from event_data
    # In the test payload, we provided it.
    assert any("Permission denied" in d["proposed_content"] for d in deltas)

    # Test Rule 3: Success Workflow
    success_payload = {
        "event_type": "TASK_SUCCESS",
        "event_data": {
            "workflow_summary": "Successfully deployed the microservice using Docker."
        }
    }
    response = client.post("/api/observer/event", json=success_payload)
    assert response.status_code == 200
    
    delta_res = client.get("/api/brain/deltas/pending")
    deltas = delta_res.json()
    assert len(deltas) >= 3
    assert any("deployed the microservice" in d["proposed_content"] for d in deltas)
