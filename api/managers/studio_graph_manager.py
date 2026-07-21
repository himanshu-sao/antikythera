"""
Studio Graph Manager - Persists StudioGraph objects to disk with atomic writes.

Storage: automation-ideas/studio_graphs/<graph_id>.json
One file per graph for isolation and concurrent access safety.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from api.managers.base import BaseJSONManager
from api.models.studio import StudioGraph, STUDIO_GRAPHS_DIR


class StudioGraphManager:
    """
    Manages Studio Graph persistence.
    Each graph is stored as a separate JSON file for isolation.
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.graphs_dir = os.path.join(base_dir, STUDIO_GRAPHS_DIR)
        os.makedirs(self.graphs_dir, exist_ok=True)

    def _graph_path(self, graph_id: str) -> str:
        return os.path.join(self.graphs_dir, f"{graph_id}.json")

    def _load_graph(self, graph_id: str) -> Optional[Dict[str, Any]]:
        path = self._graph_path(graph_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _save_graph(self, graph_id: str, data: Dict[str, Any]) -> bool:
        path = self._graph_path(graph_id)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp_path = path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp_path, path)
            return True
        except Exception:
            return False

    def save_graph(self, graph: StudioGraph) -> bool:
        """Save or update a StudioGraph."""
        graph.updated_at = datetime.utcnow()
        if not graph.created_at:
            graph.created_at = datetime.utcnow()

        # Convert to dict with ISO format dates
        data = graph.model_dump(mode="json")
        return self._save_graph(graph.graph_id, data)

    def get_graph(self, graph_id: str) -> Optional[StudioGraph]:
        """Load a StudioGraph by ID."""
        data = self._load_graph(graph_id)
        if data is None:
            return None
        return StudioGraph.model_validate(data)

    def delete_graph(self, graph_id: str) -> bool:
        """Delete a graph file."""
        path = self._graph_path(graph_id)
        if os.path.exists(path):
            try:
                os.remove(path)
                return True
            except OSError:
                return False
        return False

    def list_graphs(self) -> List[Dict[str, Any]]:
        """List all graphs with minimal metadata (no full node/edge data)."""
        graphs = []
        for filename in os.listdir(self.graphs_dir):
            if filename.endswith(".json"):
                graph_id = filename[:-5]
                data = self._load_graph(graph_id)
                if data:
                    # Return only metadata for listing
                    graphs.append({
                        "graph_id": data.get("graph_id", graph_id),
                        "name": data.get("name", graph_id),
                        "description": data.get("description", ""),
                        "version": data.get("version", "1.0.0"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "required_capability": data.get("required_capability", "generate"),
                        "cron_enabled": data.get("cron_enabled", False),
                        "cron_schedule": data.get("cron_schedule"),
                        "node_count": len(data.get("nodes", [])),
                    })
        return graphs

    def list_graphs_full(self) -> List[StudioGraph]:
        """Load all graphs fully (for migration/debug)."""
        graphs = []
        for filename in os.listdir(self.graphs_dir):
            if filename.endswith(".json"):
                graph_id = filename[:-5]
                graph = self.get_graph(graph_id)
                if graph:
                    graphs.append(graph)
        return graphs