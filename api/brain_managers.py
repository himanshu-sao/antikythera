import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
from api.brain_schemas import CognitiveDelta, ObserverEvent
from api.brain_interfaces import BrainManagerInterface, ObserverManagerInterface

class BrainManager(BrainManagerInterface):
    def __init__(self, knowledge_dir: str, deltas_dir: str):
        self.knowledge_dir = knowledge_dir
        self.deltas_dir = deltas_dir

    def _get_artifact_path(self, filename: str) -> str:
        return os.path.join(self.knowledge_dir, filename)

    def _get_delta_path(self, delta_id: str) -> str:
        return os.path.join(self.deltas_dir, f"{delta_id}.json")

    def get_artifact_content(self, filename: str) -> str:
        path = self._get_artifact_path(filename)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read()
        return ""

    def get_all_artifacts(self) -> Dict[str, str]:
        """Returns all brain artifacts and their contents."""
        artifacts = {}
        for filename in ["user.md", "skills.md", "memory.md"]:
            artifacts[filename] = self.get_artifact_content(filename)
        return artifacts

    def commit_delta(self, delta_id: str) -> bool:
        delta_path = self._get_delta_path(delta_id)
        if not os.path.exists(delta_path):
            return False

        with open(delta_path, 'r') as f:
            delta_data = json.load(f)
            delta = CognitiveDelta(**delta_data)

        target_path = self._get_artifact_path(delta.target_artifact)
        
        if delta.change_type == "ADD":
            with open(target_path, 'a') as f:
                f.write(f"\n{delta.proposed_content}")
        elif delta.change_type in ["REPLACE", "REVISE"]:
            with open(target_path, 'w') as f:
                f.write(delta.proposed_content)
        elif delta.change_type == "REMOVE":
            content = self.get_artifact_content(delta.target_artifact)
            original = delta.original_content if delta.original_content is not None else ""
            new_content = content.replace(original, "")
            with open(target_path, 'w') as f:
                f.write(new_content)

        delta.status = "APPROVED"
        with open(delta_path, 'w') as f:
            f.write(delta.model_dump_json())
            
        return True

    def get_pending_deltas(self) -> List[CognitiveDelta]:
        deltas = []
        if not os.path.exists(self.deltas_dir):
            return []
        for filename in os.listdir(self.deltas_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.deltas_dir, filename)
                with open(path, 'r') as f:
                    try:
                        data = json.load(f)
                        delta = CognitiveDelta(**data)
                        if delta.status in ["PENDING", "REFINED"]:
                            deltas.append(delta)
                    except Exception as e:
                        print(f"Error loading delta {filename}: {e}")
        return sorted(deltas, key=lambda x: x.created_at, reverse=True)

    def refine_delta(self, delta_id: str, comment: str) -> CognitiveDelta:
        delta_path = self._get_delta_path(delta_id)
        with open(delta_path, 'r') as f:
            data = json.load(f)
            delta = CognitiveDelta(**data)

        delta.status = "REFINED"
        delta.refined_by_comment = comment
        
        # Simulation: Append the comment to the end of the proposed content
        delta.proposed_content += f"\n\n(Refined via user comment: {comment})"
        
        with open(delta_path, 'w') as f:
            f.write(delta.model_dump_json())
        
        return delta

    def reject_delta(self, delta_id: str) -> bool:
        delta_path = self._get_delta_path(delta_id)
        if os.path.exists(delta_path):
            with open(delta_path, 'r') as f:
                data = json.load(f)
                delta = CognitiveDelta(**data)
            delta.status = "REJECTED"
            with open(delta_path, 'w') as f:
                f.write(delta.model_dump_json())
            return True
        return False

class ObserverManager(ObserverManagerInterface):
    def __init__(self, brain_manager: BrainManager, run_manager: Any):
        self.brain_manager = brain_manager
        self.run_manager = run_manager

    def process_event(self, event: ObserverEvent) -> List[CognitiveDelta]:
        """
        Simulates the 'Cognitive Observer' using rule-based pattern recognition.
        In a production system, this would use an LLM to reason about the event.
        """
        new_deltas = []
        event_data = event.event_data
        
        # Rule 1: Preference Detection (User.md)
        if event.event_type == "USER_INTERVENTION":
            user_text = event_data.get("user_comment", "").lower()
            if any(kw in user_text for kw in ["prefer", "like", "always", "never", "should", "don't like"]):
                new_deltas.append(CognitiveDelta(
                    target_artifact="user.md",
                    change_type="ADD",
                    proposed_content=f"- User preference detected: {event_data.get('user_comment')}",
                    reason=f"Direct user feedback in {event.event_type}",
                    status="PENDING",
                    confidence_score=90
                ))

        # Rule 2: Troubleshooting/Environment Fact Detection (Memory.md)
        if event.event_type == "TOOL_ERROR" or (event.event_type == "KANBAN_TRANSITION" and ("error" in event_data.get("error_msg", "").lower() or "fail" in event_data.get("error_msg", "").lower())):
            error_msg = event_data.get("error_msg") or event_data.get("body", "")
            new_deltas.append(CognitiveDelta(
                target_artifact="memory.md",
                change_type="ADD",
                proposed_content=f"- Observation: {error_msg}",
                reason=f"System failure or error detected during {event.event_type}",
                status="PENDING",
                confidence_score=70
            ))

        # Rule 3: Skill/Workflow Extraction (Skills.md)
        if event.event_type == "TASK_SUCCESS":
            workflow_desc = event_data.get("workflow_summary", "")
            if workflow_desc:
                new_deltas.append(CognitiveDelta(
                    target_artifact="skills.md",
                    change_type="ADD",
                    proposed_content=f"## {workflow_desc.split('.')[0]}\n- {workflow_desc}",
                    reason="Successful completion of a complex task with a clear workflow.",
                    status="PENDING",
                    confidence_score=60,
                    original_content=None,
                    source_event_id=None,
                    refined_by_comment=None
                ))

        # Rule 4: Artifact Commentary (User comments on files)
        if event.event_type == "ARTIFACT_COMMENT":
            target = event_data.get("target_artifact")
            comment = event_data.get("comment")
            if target and comment:
                new_deltas.append(CognitiveDelta(
                    target_artifact=target, # type: ignore
                    change_type="REVISE",
                    proposed_content="", # Placeholder, real system would fetch current content
                    reason=f"User provided feedback on {target}: {comment}",
                    status="PENDING",
                    confidence_score=80
                ))

        # Write the new deltas to the filesystem
        for delta in new_deltas:
            delta_path = self.brain_manager._get_delta_path(delta.delta_id)
            os.makedirs(os.path.dirname(delta_path), exist_ok=True)
            with open(delta_path, 'w') as f:
                f.write(delta.model_dump_json())

        return new_deltas

    def analyze_kanban_logs(self, kanban_id: str) -> List[CognitiveDelta]:
        """
        Scans the run timeline for a given Kanban item to extract patterns.
        """
        # For simplicity, we assume kanban_id is a run_id in the runs timeline
        timeline = self.run_manager.get_run_timeline(kanban_id)
        new_deltas = []
        
        for event in timeline:
            e_type = event["event_type"]
            payload = event["payload"]
            
            # Detect repetitive task failures
            if e_type == "TASK_FAILURE":
                new_deltas.append(CognitiveDelta(
                    target_artifact="memory.md",
                    change_type="ADD",
                    proposed_content=f"- Repeated failure in {payload.get('task_name', 'unknown task')}: {payload.get('error', 'No error provided')}",
                    reason="Observed repeated task failure in run timeline.",
                    status="PENDING",
                    confidence_score=65
                ))
            
            # Detect successful workflow patterns
            elif e_type == "TASK_COMPLETED":
                workflow_desc = payload.get("summary", "")
            if workflow_desc:
                new_deltas.append(CognitiveDelta(
                    target_artifact="skills.md",
                    change_type="ADD",
                    proposed_content=f"## {workflow_desc.split('.')[0]}\n- {workflow_desc}",
                    reason="Extracted pattern from successful task completion in timeline.",
                    status="PENDING",
                    confidence_score=55,
                    original_content=None,
                    source_event_id=None,
                    refined_by_comment=None
                ))

        return new_deltas
