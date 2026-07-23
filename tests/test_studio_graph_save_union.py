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


def _node_fanout():
    return {
        "node_id": "f1",
        "name": "f1",
        "archetype": "fan_out",
        "loop_over": {"source": "items", "iterator_var": "ticket"},
    }


def _node_ai():
    return {
        "node_id": "a1",
        "name": "a1",
        "archetype": "ai_transform",
        "execution_mode": "script",
        "script": "return {'plan': 'enrich'}",
        "input_ref": "items",
        "output_ref": "enriched",
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

    def test_update_rejects_bad_archetype_with_422(self):
        """Gap D — the PUT update path got the same try/except fix as POST
        create, but only create is guard-tested. A bad archetype on update
        must 422 (not 500) and must NOT mutate the already-persisted graph."""
        # seed a good graph
        seed = {"name": "g_upd", "nodes": [_node_query()], "edges": []}
        r = self.client.post("/api/studio/graphs", json=seed)
        self.assertEqual(r.status_code, 201, r.text)
        gid = r.json()["graph_id"]

        bad = _node_query()
        bad["archetype"] = "not_a_real_archetype"
        r = self.client.put(f"/api/studio/graphs/{gid}", json={"nodes": [bad]})
        self.assertEqual(r.status_code, 422, r.text)

        # the persisted graph is untouched: still 1 node, still the valid query archetype
        g = self.client.get(f"/api/studio/graphs/{gid}").json()
        self.assertEqual(len(g["nodes"]), 1)
        self.assertEqual(g["nodes"][0]["archetype"], "query")

    def test_create_422_detail_carries_validation_errors(self):
        """Gap F — the 422 must surface pydantic's structured errors (a list of
        {loc, msg, type, ...}), not a bare string, so a malformed node is
        diagnosable. Covers POST create."""
        bad = _node_query()
        bad["archetype"] = "not_a_real_archetype"
        r = self.client.post("/api/studio/graphs", json={"name": "bad", "nodes": [bad], "edges": []})
        self.assertEqual(r.status_code, 422, r.text)
        detail = r.json().get("detail")
        self.assertIsInstance(detail, list, "422 detail must be a list of validation errors")
        # the offending field is the discriminator (archetype); pydantic tags it literal_error
        locs = [tuple(e.get("loc", ())) for e in detail]
        self.assertTrue(any("archetype" in loc for loc in locs), f"archetype in locs: {locs}")
        self.assertTrue(any(e.get("type") == "literal_error" for e in detail), detail)

    def test_mixed_union_round_trips_all_four_archetypes(self):
        """Gap E — discriminator-matrix round-trip. Persist a graph with all
        four node archetypes and GET it back; each must survive the
        TypeAdapter discrimination + disk serialization. (Today only the
        conditional round-trip is asserted.)"""
        nodes = [_node_query(), _node_fanout(), _node_ai(), _node_conditional()]
        edges = [
            {"source": "q1", "target": "f1", "source_handle": "loop"},
            {"source": "f1", "target": "c1", "source_handle": "loop"},
            {"source": "f1", "target": "a1", "source_handle": "loop"},
        ]
        payload = {
            "name": "matrix",
            "nodes": nodes,
            "edges": edges,
            "cron_enabled": False,
            "undefined_queue_cap": 100,
            "max_run_logs": 50,
        }
        r = self.client.post("/api/studio/graphs", json=payload)
        self.assertEqual(r.status_code, 201, r.text)
        gid = r.json()["graph_id"]

        g = self.client.get(f"/api/studio/graphs/{gid}").json()
        archetypes = {n["archetype"] for n in g["nodes"]}
        self.assertEqual(
            archetypes,
            {"query", "fan_out", "ai_transform", "conditional_action"},
            f"all four archetypes must round-trip; got {archetypes}",
        )
        # fan_out preserves its loop_over spec through serialization
        fan = next(n for n in g["nodes"] if n["archetype"] == "fan_out")
        self.assertEqual(fan["loop_over"], {"source": "items", "iterator_var": "ticket"})
        # ai_transform preserves script + input/output refs
        ai = next(n for n in g["nodes"] if n["archetype"] == "ai_transform")
        self.assertEqual(ai["input_ref"], "items")
        self.assertEqual(ai["output_ref"], "enriched")
        self.assertEqual(ai["execution_mode"], "script")


if __name__ == "__main__":
    unittest.main()
