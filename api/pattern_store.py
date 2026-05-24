import json
import os
from typing import Dict, Any, Optional, List
from filelock import FileLock

class PatternStore:
    """
    Stores 'Learned Patterns' from human interventions.
    Used for few-shot prompting to allow the AI to self-learn from blocks.
    """
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.patterns_path = os.path.join(base_dir, "learned_patterns.json")
        self._lock = FileLock(self.patterns_path + ".lock")

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.patterns_path):
            return {}
        try:
            with open(self.patterns_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: Dict[str, Any]):
        with open(self.patterns_path, "w") as f:
            json.dump(data, f, indent=2)

    def add_pattern(self, template_id: str, context: Dict[str, Any], resolution: str):
        """
        Saves a human correction as a pattern.
        context: The state/data that led to the block.
        resolution: The action the human took to resolve it.
        """
        with self._lock:
            patterns = self._load()
            if template_id not in patterns:
                patterns[template_id] = []
            
            patterns[template_id].append({
                "context": context,
                "resolution": resolution,
                "timestamp": os.popen('date -u +"%Y-%m-%dT%H:%M:%SZ"').read().strip()
            })
            self._save(patterns)

    def get_patterns(self, template_id: str) -> List[Dict[str, Any]]:
        """Retrieves all learned patterns for a specific template."""
        with self._lock:
            patterns = self._load()
            return patterns.get(template_id, [])

    def find_similar_patterns(self, template_id: str, current_context: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
        """
        In a production system, this would use vector embeddings.
        For now, we implement a simple keyword-based similarity match.
        """
        patterns = self.get_patterns(template_id)
        if not patterns:
            return []

        # Simple overlap check on keys/values for demo purposes
        scored_patterns = []
        curr_str = json.dumps(current_context).lower()
        
        for p in patterns:
            ctx_str = json.dumps(p["context"]).lower()
            # Count common words/tokens
            score = len(set(curr_str.split()) & set(ctx_str.split()))
            scored_patterns.append((score, p))

        scored_patterns.sort(key=lambda x: x[0], reverse=True)
        return [p for score, p in scored_patterns[:limit]]
