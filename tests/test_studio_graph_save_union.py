"""T5-pre3 / Gap 6: POST /api/studio/graphs (and PUT update) must accept a
discriminated-Union ``StudioNode``, not crash with AttributeError.

Gap (verified live at HEAD 878966f): ``create_graph`` and ``update_graph`` did
``StudioNode.model_validate(n)``. ``StudioNode`` is a ``Union[QueryNode,
FanOutNode, AITransformNode, ConditionalActionNode]`` — Union has no
``model_validate`` → ``AttributeError: model_validate`` → every save returned
HTTP 500. The preview-node path was already fixed with ``TypeAdapter``
(commit a2e2529); the save path had the identical latent bug. Without saving,
plan §6 "save persists; runGraph replays" is unreachable — you can't headlessly
replay a graph that can't be persisted.

Fix: use ``TypeAdapter(StudioNode).validate_python(n)`` in both create and
update (same fix as preview-node). These tests pin it via FastAPI TestClient
pointed at a temp data dir (no real ``automation-ideas/studio_graphs`` writes).
"""
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from api import studio_router
from api.main import app
from api.managers.studio_graph_manager import StudioGraphManager


def _node_conditional():
    return {
        "node_id": "c1",
        "name": "c1",
        "archetype": "conditional_action",
        "routing_strategy": "condition_first",
        "condition": {"type": "equals", "field": "ticket.status", "value": "New"},
        "true_action": "jira_adapter",
        "true_action_config": {"transition": "Investigating"},
        "true_output_ref": "moved_id",
        "false_action": None,
        "false_action_config": {},
        "false_output_ref": None,
    }


def _node_query():
    return {
        "node_id": "q1",
        "name": "q1",
        "archetype": "query",
        "adapter": "internal_adapter",
        "action": "list_items",
        "params": {},
        "output_ref": "items",
    }


class TestGraphSaveUnion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="studio_save_test_")

        def _stub_manager():
            return StudioGraphManager(self.tmp)

        app.dependency_overrides[studio_router.get_studio_graph_manager] = _stub_manager
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(studio_router.get_studio_graph_manager, None)

    def test_create_graph_with_conditional_node_returns_201(self):
        """The discriminated-Union conditional node must persist (Gap 6)."""
        payload = {
            "name": "twistlock_slice1",
            "description": "§0 replay",
            "nodes": [_node_query(), _node_conditional()],
            "edges": [{"source": "q1", "target": "c1", "source_handle": "loop"}],
            "cron_enabled": False,
            "undefined_queue_cap": 100,
            "max_run_logs": 50,
        }
        r = self.client.post("/api/studio/graphs", json=payload)
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertEqual(body["graph_id"], "graph_twistlock_slice1")
        # Persisted to disk
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "studio_graphs", "graph_twistlock_slice1.json")))
        # GET detail round-trips the union node back as a conditional_action
        g = self.client.get(f"/api/studio/graphs/{body['graph_id']}").json()
        archetypes = {n["archetype"] for n in g["nodes"]}
        self.assertIn("conditional_action", archetypes)
        self.assertIn("query", archetypes)

    def test_update_graph_nodes_with_union(self):
        payload = {
            "name": "g2",
            "nodes": [_node_query()],
            "edges": [],
        }
        r = self.client.post("/api/studio/graphs", json=payload)
        self.assertEqual(r.status_code, 201, r.text)
        gid = r.json()["graph_id"]

        # PUT with a Union conditional node in the nodes array
        upd = {"nodes": [_node_query(), _node_conditional()]}
        r = self.client.put(f"/api/studio/graphs/{gid}", json=upd)
        self.assertEqual(r.status_code, 200, r.text)
        g = self.client.get(f"/api/studio/graphs/{gid}").json()
        self.assertEqual(len(g["nodes"]), 2)
        self.assertIn("conditional_action", {n["archetype"] for n in g["nodes"]})

    def test_create_rejects_bad_archetype_with_422(self):
        """Guard: a node with an unknown archetype must 422 (TypeAdapter raises
        ValidationError → FastAPI turns it into 422), not 500."""
        bad = _node_query()
        bad["archetype"] = "not_a_real_archetype"
        r = self.client.post("/api/studio/graphs", json={"name": "bad", "nodes": [bad], "edges": []})
        self.assertEqual(r.status_code, 422, r.text)


if __name__ == "__main__":
    unittest.main()
