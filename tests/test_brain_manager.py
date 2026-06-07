import pytest
from api.brain_managers import BrainManager
import os
import json
import shutil
import tempfile
from api.brain_schemas import CognitiveDelta
from datetime import datetime

@pytest.fixture
def brain_setup():
    temp_dir = tempfile.mkdtemp()
    knowledge_dir = os.path.join(temp_dir, "knowledge")
    deltas_dir = os.path.join(temp_dir, "deltas")
    os.makedirs(knowledge_dir)
    os.makedirs(deltas_dir)
    
    # Create initial artifacts
    with open(os.path.join(knowledge_dir, "user.md"), "w") as f:
        f.write("# User Profile\nInitial content")
    with open(os.path.join(knowledge_dir, "skills.md"), "w") as f:
        f.write("# Skills\nInitial skills")
    with open(os.path.join(knowledge_dir, "memory.md"), "w") as f:
        f.write("# Memory\nInitial memory")
        
    manager = BrainManager(knowledge_dir, deltas_dir)
    
    yield manager, knowledge_dir, deltas_dir
    
    shutil.rmtree(temp_dir)

def test_get_all_artifacts(brain_setup):
    manager, _, _ = brain_setup
    artifacts = manager.get_all_artifacts()
    assert "user.md" in artifacts
    assert "# User Profile" in artifacts["user.md"]

def test_commit_add_delta(brain_setup):
    manager, knowledge_dir, deltas_dir = brain_setup
    
    # Create a pending delta
    delta = CognitiveDelta(
        target_artifact="user.md",
        change_type="ADD",
        proposed_content="New preference: likes concise responses.",
        reason="User explicitly stated preference.",
        status="PENDING"
    )
    
    delta_path = os.path.join(deltas_dir, f"{delta.delta_id}.json")
    with open(delta_path, "w") as f:
        f.write(delta.json())
        
    # Verify it's pending
    pending = manager.get_pending_deltas()
    assert len(pending) == 1
    assert pending[0].delta_id == delta.delta_id
    
    # Commit it
    success = manager.commit_delta(delta.delta_id)
    assert success is True
    
    # Verify artifact updated
    with open(os.path.join(knowledge_dir, "user.md"), "r") as f:
        content = f.read()
        assert "New preference: likes concise responses." in content
        
    # Verify delta is no longer pending
    assert len(manager.get_pending_deltas()) == 0

def test_refine_delta(brain_setup):
    manager, _, deltas_dir = brain_setup
    
    delta = CognitiveDelta(
        target_artifact="skills.md",
        change_type="REPLACE",
        proposed_content="Original Skill",
        reason="Initial skill",
        status="PENDING"
    )
    
    delta_path = os.path.join(deltas_dir, f"{delta.delta_id}.json")
    with open(delta_path, "w") as f:
        f.write(delta.json())
        
    # Refine it
    refined_delta = manager.refine_delta(delta.delta_id, "Make it more technical")
    
    assert refined_delta.status == "REFINED"
    assert "Make it more technical" in refined_delta.refined_by_comment
    assert "Refined via user comment" in refined_delta.proposed_content
    
    # Verify status in file
    with open(delta_path, "r") as f:
        data = json.load(f)
        assert data["status"] == "REFINED"

def test_reject_delta(brain_setup):
    manager, _, deltas_dir = brain_setup
    
    delta = CognitiveDelta(
        target_artifact="memory.md",
        change_type="REMOVE",
        original_content="Old Fact",
        proposed_content="",
        reason="Irrelevant",
        status="PENDING"
    )
    
    delta_path = os.path.join(deltas_dir, f"{delta.delta_id}.json")
    with open(delta_path, "w") as f:
        f.write(delta.json())
        
    success = manager.reject_delta(delta.delta_id)
    assert success is True
    
    # Verify status
    with open(delta_path, "r") as f:
        data = json.load(f)
        assert data["status"] == "REJECTED"
