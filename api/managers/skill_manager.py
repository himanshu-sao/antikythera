"""
Skill Manager - Persists Skill objects to disk with atomic writes.

Storage: automation-ideas/skills/<skill_id>.json
One file per skill for isolation and concurrent access safety.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from api.managers.base import BaseJSONManager
from api.models.studio import Skill, SKILLS_DIR


class SkillManager:
    """
    Manages Skill persistence.
    Each skill is stored as a separate JSON file.
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.skills_dir = os.path.join(base_dir, SKILLS_DIR)
        os.makedirs(self.skills_dir, exist_ok=True)

    def _skill_path(self, skill_id: str) -> str:
        return os.path.join(self.skills_dir, f"{skill_id}.json")

    def _load_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        path = self._skill_path(skill_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _save_skill(self, skill_id: str, data: Dict[str, Any]) -> bool:
        path = self._skill_path(skill_id)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp_path = path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp_path, path)
            return True
        except Exception:
            return False

    def save_skill(self, skill: Skill) -> bool:
        """Save or update a Skill."""
        skill.updated_at = datetime.utcnow()
        if not skill.created_at:
            skill.created_at = datetime.utcnow()

        # Convert to dict with ISO format dates
        data = skill.model_dump(mode="json")
        return self._save_skill(skill.skill_id, data)

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Load a Skill by ID."""
        data = self._load_skill(skill_id)
        if data is None:
            return None
        return Skill.model_validate(data)

    def delete_skill(self, skill_id: str) -> bool:
        """Delete a skill file."""
        path = self._skill_path(skill_id)
        if os.path.exists(path):
            try:
                os.remove(path)
                return True
            except OSError:
                return False
        return False

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all skills with minimal metadata."""
        skills = []
        for filename in os.listdir(self.skills_dir):
            if filename.endswith(".json"):
                skill_id = filename[:-5]
                data = self._load_skill(skill_id)
                if data:
                    # Return only metadata for listing
                    skills.append({
                        "skill_id": data.get("skill_id", skill_id),
                        "name": data.get("name", skill_id),
                        "description": data.get("description", ""),
                        "version": data.get("version", "1.0.0"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "required_capability": data.get("required_capability", "generate"),
                        "tags": data.get("tags", []),
                    })
        return skills

    def get_skills_by_tag(self, tag: str) -> List[Skill]:
        """Get all skills that have a specific tag."""
        result = []
        for filename in os.listdir(self.skills_dir):
            if filename.endswith(".json"):
                skill_id = filename[:-5]
                skill = self.get_skill(skill_id)
                if skill and tag in skill.tags:
                    result.append(skill)
        return result