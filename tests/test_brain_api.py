import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.brain_schemas import ObserverEvent
import os
import json
import shutil

@pytest.fixture(autouse=True)
def cleanup_knowledge():
    # Cleanup knowledge and deltas before each test to ensure isolation
    base_dir = os.path.abspath("./knowledge")
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
    
    # Recreate clean structure
    os.makedirs(os.path.join(base_dir, "deltas"), exist_ok=True)
    with open(os.path.join(base_dir, "user.md"), "w") as f: f.write("# User Profile")
    with open(os.path.join(base_dir, "skills.md"), "w") as f: f.write("# Skills")
    with open(os.path.join(base_dir, "memory.md"), "w") as f: f.write("# Memory")
    
    yield
    
    # Cleanup after test
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)

@pytest.fixture
def client():
    return TestClient(app)

def test_get_artifacts(client):
    response = client.get("/api/brain/artifacts")
    assert response.status_code == 200
    data = response.json()
    assert "user.md" in data
    assert "skills.md" in data

def test_update_artifact(client):
    response = client.put("/api/brain/artifacts/user.md", json={"content": "# New User Profile\nUpdated via API"})
    assert response.status_code == 200
    
    # Verify
    response = client.get("/api/brain/artifacts")
    assert "New User Profile" in response.json()["user.md"]

def test_pending_deltas_empty(client):
    response = client.get("/api/brain/deltas/pending")
    assert response.status_code == 200
    assert response.json() == []

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
