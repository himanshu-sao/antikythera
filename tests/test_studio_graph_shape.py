"""S6 / P2-10: graph shape validation at save time and at run time.

Defects: nothing checked duplicate node ids, dangling edges or cycles. A cycle
(loop edge back to a FanOut ancestor) made the engine recurse forever.

Fix under test:
- api.models.studio.validate_graph_shape (Kahn's algorithm; loop edges count
  as ordinary edges for cycle detection);
- POST/PUT answer 422 with a clear message; the two real graph shapes still save;
- a run started on an invalid graph ends with status "failed" and never recurses.
"""
import asyncio
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from api import studio_router
from api.execution.studio_graph_engine import PathStepGraphEngine
from api.main import app
from api.managers.run_manager import RunManager
from api.managers.skill_manager import SkillManager
from api.managers.studio_graph_manager import StudioGraphManager
from api.models.studio import (
    ExecutionState,
    GraphEdge,
    StudioGraph,
    validate_graph_shape,
)
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _q(node_id, adapter="internal_adapter", action="list_items"):
    return {"node_id": node_id, "name": node_id, "archetype": "query",
            "adapter": adapter, "action": action, "params": {}, "output_ref": f"out_{node_id}"}


def _c(node_id, field="ticket.status", value="New"):
    return {"node_id": node_id, "name": node_id, "archetype": "conditional_action",
            "routing_strategy": "condition_first",
            "condition": {"type": "equals", "field": field, "value": value}}


def _f(node_id, source="items", iterator_var="ticket"):
    return {"node_id": node_id, "name": node_id, "archetype": "fan_out",
            "loop_over": {"source": source, "iterator_var": iterator_var}}


def _ai(node_id):
    return {"node_id": node_id, "name": node_id, "archetype": "ai_transform",
            "execution_mode": "script", "script": "result = 1",
            "input_ref": "items", "output_ref": f"out_{node_id}"}


def _e(source, target, handle=None):
    d = {"source": source, "target": target}
    if handle is not None:
        d["source_handle"] = handle
    return d


# The two real graph shapes on disk today (automation-ideas/studio_graphs),
# rebuilt here so the tests never read live data.
TWISTLOCK_NODES = [_q("query_twistlock"), _f("fanout_tickets"), _ai("ai_extract"), _c("cond_escalate")]
TWISTLOCK_EDGES = [_e("query_twistlock", "fanout_tickets"),
                   _e("fanout_tickets", "ai_extract", "loop"),
                   _e("ai_extract", "cond_escalate")]
SINGLE_NODE_NODES = [_q("q1")]
SINGLE_NODE_EDGES = []


class TestValidateGraphShape(unittest.TestCase):
    def check(self, nodes, edges):
        return validate_graph_shape(nodes, edges)

    def test_valid_linear_graph(self):
        self.assertEqual(self.check([{"node_id": "a"}, {"node_id": "b"}], [_e("a", "b")]), [])

    def test_real_twistlock_shape_is_valid(self):
        self.assertEqual(self.check(TWISTLOCK_NODES, TWISTLOCK_EDGES), [])

    def test_real_single_node_shape_is_valid(self):
        self.assertEqual(self.check(SINGLE_NODE_NODES, SINGLE_NODE_EDGES), [])

    def test_empty_graph_is_valid(self):
        self.assertEqual(self.check([], []), [])

    def test_duplicate_node_id_reported(self):
        problems = self.check([{"node_id": "a"}, {"node_id": "a"}], [])
        self.assertTrue(any("Duplicate node id 'a'" in p for p in problems), problems)

    def test_dangling_target_reported(self):
        problems = self.check([{"node_id": "a"}], [_e("a", "ghost")])
        self.assertTrue(any("ghost" in p and "does not exist" in p for p in problems), problems)

    def test_dangling_source_reported(self):
        problems = self.check([{"node_id": "a"}], [_e("ghost", "a")])
        self.assertTrue(any("ghost" in p for p in problems), problems)

    def test_two_node_cycle_reported(self):
        problems = self.check([{"node_id": "a"}, {"node_id": "b"}], [_e("a", "b"), _e("b", "a")])
        self.assertTrue(any("cycle" in p and "a" in p and "b" in p for p in problems), problems)

    def test_self_loop_reported(self):
        problems = self.check([{"node_id": "a"}], [_e("a", "a")])
        self.assertTrue(any("cycle" in p for p in problems), problems)

    def test_loop_edge_back_to_fanout_ancestor_is_cycle(self):
        nodes = [_f("f"), _c("c")]
        edges = [_e("f", "c", "loop"), _e("c", "f")]  # c points back to its FanOut ancestor
        problems = self.check(nodes, edges)
        self.assertTrue(any("cycle" in p for p in problems), problems)

    def test_loop_edge_back_to_ancestor_chain_is_cycle(self):
        nodes = [_f("f"), _ai("a"), _c("c")]
        edges = [_e("f", "a", "loop"), _e("a", "c"), _e("c", "a", "true")]
        self.assertTrue(any("cycle" in p for p in self.check(nodes, edges)))

    def test_diamond_is_not_a_cycle(self):
        nodes = [{"node_id": n} for n in "abcd"]
        edges = [_e("a", "b"), _e("a", "c"), _e("b", "d"), _e("c", "d")]
        self.assertEqual(self.check(nodes, edges), [])

    def test_disconnected_components_are_valid(self):
        nodes = [{"node_id": n} for n in "abcd"]
        self.assertEqual(self.check(nodes, [_e("a", "b"), _e("c", "d")]), [])

    def test_accepts_plain_objects_with_attributes(self):
        class N:
            def __init__(self, node_id):
                self.node_id = node_id

        class E:
            def __init__(self, source, target):
                self.source, self.target = source, target

        self.assertEqual(self.check([N("a"), N("b")], [E("a", "b")]), [])
        self.assertTrue(self.check([N("a")], [E("a", "x")]))


class _RouterBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="studio_shape_")
        self._orig_base = studio_router._get_base_dir
        studio_router._get_base_dir = lambda: self.tmp
        self._orig_gm = studio_router.get_studio_graph_manager
        self._orig_sm = studio_router.get_skill_manager
        studio_router.get_studio_graph_manager = lambda: StudioGraphManager(self.tmp)
        studio_router.get_skill_manager = lambda: SkillManager(self.tmp)
        app.dependency_overrides[studio_router.get_studio_graph_manager] = lambda: StudioGraphManager(self.tmp)
        app.dependency_overrides[studio_router.get_skill_manager] = lambda: SkillManager(self.tmp)
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(studio_router.get_studio_graph_manager, None)
        app.dependency_overrides.pop(studio_router.get_skill_manager, None)
        studio_router._get_base_dir = self._orig_base
        studio_router.get_studio_graph_manager = self._orig_gm
        studio_router.get_skill_manager = self._orig_sm
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestGraphShapeOnSave(_RouterBase):
    def post(self, nodes, edges, name="shape"):
        return self.client.post("/api/studio/graphs", json={"name": name, "nodes": nodes, "edges": edges})

    def test_real_twistlock_shape_saves(self):
        r = self.post(TWISTLOCK_NODES, TWISTLOCK_EDGES, name="twistlock")
        self.assertEqual(r.status_code, 201, r.text)

    def test_real_single_node_shape_saves(self):
        r = self.post(SINGLE_NODE_NODES, SINGLE_NODE_EDGES, name="single")
        self.assertEqual(r.status_code, 201, r.text)

    def test_duplicate_ids_rejected_422(self):
        r = self.post([_q("a"), _q("a")], [])
        self.assertEqual(r.status_code, 422)
        self.assertIn("Duplicate node id", r.text)

    def test_dangling_edge_rejected_422(self):
        r = self.post([_q("a")], [_e("a", "missing")])
        self.assertEqual(r.status_code, 422)
        self.assertIn("missing", r.text)

    def test_cycle_rejected_422(self):
        r = self.post([_q("a"), _q("b")], [_e("a", "b"), _e("b", "a")])
        self.assertEqual(r.status_code, 422)
        self.assertIn("cycle", r.text)

    def test_loop_edge_back_to_fanout_rejected_422(self):
        r = self.post([_f("f"), _c("c")], [_e("f", "c", "loop"), _e("c", "f")])
        self.assertEqual(r.status_code, 422)
        self.assertIn("cycle", r.text)

    def test_rejected_graph_is_not_written(self):
        self.post([_q("a"), _q("a")], [], name="never")
        self.assertEqual(StudioGraphManager(self.tmp).list_graphs(), [])

    def test_422_detail_is_structured(self):
        r = self.post([_q("a")], [_e("a", "x")])
        body = r.json()
        self.assertIn("message", body["detail"])
        self.assertTrue(body["detail"]["violations"])


class TestGraphShapeOnUpdate(_RouterBase):
    def setUp(self):
        super().setUp()
        r = self.client.post("/api/studio/graphs", json={
            "name": "base", "nodes": TWISTLOCK_NODES, "edges": TWISTLOCK_EDGES})
        self.assertEqual(r.status_code, 201, r.text)
        self.gid = r.json()["graph_id"]

    def test_update_with_cycle_rejected_and_file_unchanged(self):
        before = StudioGraphManager(self.tmp).get_graph(self.gid).model_dump(mode="json")
        r = self.client.put(f"/api/studio/graphs/{self.gid}", json={
            "edges": [_e("query_twistlock", "fanout_tickets"), _e("fanout_tickets", "query_twistlock")]})
        self.assertEqual(r.status_code, 422)
        after = StudioGraphManager(self.tmp).get_graph(self.gid).model_dump(mode="json")
        self.assertEqual(before["edges"], after["edges"])

    def test_renaming_a_node_without_fixing_edges_is_rejected(self):
        nodes = [dict(n) for n in TWISTLOCK_NODES]
        nodes[3] = _c("cond_renamed")  # edge ai_extract -> cond_escalate now dangles
        r = self.client.put(f"/api/studio/graphs/{self.gid}", json={"nodes": nodes})
        self.assertEqual(r.status_code, 422)
        self.assertIn("cond_escalate", r.text)

    def test_valid_update_succeeds(self):
        r = self.client.put(f"/api/studio/graphs/{self.gid}", json={"name": "renamed"})
        self.assertEqual(r.status_code, 200, r.text)


class TestRunOnInvalidGraph(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="studio_shape_run_")
        self.graphs = StudioGraphManager(self.base)
        self.engine = PathStepGraphEngine(
            base_dir=self.base,
            operator_registry=OperatorRegistry(vault=Mock(spec=SecretVault)),
            studio_graph_manager=self.graphs,
            skill_manager=SkillManager(self.base),
            run_manager=RunManager(self.base),
        )

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _run_bypassing_api(self, graph):
        """Drive _execute_graph directly with a graph built in memory (no validation at save)."""
        es = ExecutionState(graph_id=graph.graph_id, run_id="r_invalid", state={"items": []},
                            run_log=[], undefined_queue=[], loop_stack=[], dry_run=True)
        self.engine._save_run_log(self.engine_log(es))
        asyncio.run(self.engine._execute_graph(es, graph))
        return self.engine.get_run_log("r_invalid")

    def engine_log(self, es):
        from api.models.studio import GraphRunLog
        return GraphRunLog(run_id=es.run_id, graph_id=es.graph_id, started_at=es.started_at, status="running")

    def test_cyclic_graph_fails_run_instead_of_recursing(self):
        g = StudioGraph(graph_id="cyc", name="cyc",
                        nodes=[_f_model("f"), _c_model("c")],
                        edges=[GraphEdge(source="f", target="c", source_handle="loop"),
                               GraphEdge(source="c", target="f")])
        log = self._run_bypassing_api(g)
        self.assertEqual(log.status, "failed")
        self.assertTrue(any("cycle" in (nr.error or "") for nr in log.node_results))

    def test_dangling_edge_graph_fails_run(self):
        g = StudioGraph(graph_id="dangle", name="dangle",
                        nodes=[_q_model("a")], edges=[GraphEdge(source="a", target="ghost")])
        log = self._run_bypassing_api(g)
        self.assertEqual(log.status, "failed")
        self.assertIn("ghost", log.node_results[0].error)

    def test_duplicate_node_graph_fails_run(self):
        g = StudioGraph(graph_id="dup", name="dup", nodes=[_q_model("a"), _q_model("a")], edges=[])
        log = self._run_bypassing_api(g)
        self.assertEqual(log.status, "failed")

    def test_valid_graph_still_runs_to_completion(self):
        g = StudioGraph(graph_id="ok", name="ok", nodes=[_q_model("q1")], edges=[])
        log = self._run_bypassing_api(g)
        self.assertIn(log.status, ("completed", "partial", "failed"))
        self.assertEqual(len(log.node_results), 1)
        self.assertNotIn("Invalid graph", log.node_results[0].error or "")


def _q_model(node_id):
    from api.models.studio import QueryNode, NodeArchetype
    return QueryNode(node_id=node_id, name=node_id, archetype=NodeArchetype.QUERY,
                     adapter="internal_adapter", action="list_items", params={}, output_ref=f"out_{node_id}")


def _f_model(node_id):
    from api.models.studio import FanOutNode, NodeArchetype
    return FanOutNode(node_id=node_id, name=node_id, archetype=NodeArchetype.FAN_OUT,
                      loop_over={"source": "items", "iterator_var": "ticket"})


def _c_model(node_id):
    from api.models.studio import ConditionalActionNode, Condition, ConditionType, NodeArchetype, RoutingStrategy
    return ConditionalActionNode(node_id=node_id, name=node_id, archetype=NodeArchetype.CONDITIONAL_ACTION,
                                 routing_strategy=RoutingStrategy.CONDITION_FIRST,
                                 condition=Condition(type=ConditionType.EQUALS, field="ticket.status", value="New"))


if __name__ == "__main__":
    unittest.main()
