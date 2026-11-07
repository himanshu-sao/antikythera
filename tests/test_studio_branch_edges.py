"""S3 / P2-9 (plan T16): a ConditionalAction follows only the edges of the branch that matched.

Defect: after a ConditionalAction succeeded the engine followed every non-loop
edge, so both the true and the false targets ran. Now:
- edges with source_handle "true"/"false" run only when that branch matched;
- edges with no handle (None or "") still run on both branches (back-compat);
- loop edges are untouched; non-conditional nodes follow all non-loop edges;
- the exception path still follows the "false" edge.
"""
import asyncio
import shutil
import tempfile
import unittest
from unittest.mock import Mock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.models.studio import (
    AITransformNode,
    Condition,
    ConditionalActionNode,
    ConditionType,
    ExecutionState,
    FanOutNode,
    GraphEdge,
    NodeArchetype,
    RoutingStrategy,
    StudioGraph,
)
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _cond(node_id, field="flag", value=True, false_action=None):
    return ConditionalActionNode(
        node_id=node_id, name=node_id, archetype=NodeArchetype.CONDITIONAL_ACTION,
        routing_strategy=RoutingStrategy.CONDITION_FIRST,
        condition=Condition(type=ConditionType.EQUALS, field=field, value=value),
        false_action=false_action,
    )


def _ai(node_id):
    return AITransformNode(
        node_id=node_id, name=node_id, archetype=NodeArchetype.AI_TRANSFORM,
        input_ref="flag", script="result = 1", output_ref=f"out_{node_id}",
    )


class _Base(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="studio_branch_")
        self.engine = PathStepGraphEngine(
            base_dir=self.base,
            operator_registry=OperatorRegistry(vault=Mock(spec=SecretVault)),
            studio_graph_manager=None, skill_manager=None, run_manager=None,
        )

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def drive(self, nodes, edges, state, start="c"):
        graph = StudioGraph(graph_id="g", name="g", nodes=nodes, edges=edges)
        es = ExecutionState(graph_id="g", run_id="r", state=state, run_log=[],
                            undefined_queue=[], loop_stack=[], dry_run=True)
        adj = self.engine._build_adjacency(graph)
        _run(self.engine._execute_node(es, graph, start, adj, None))
        return es

    @staticmethod
    def ran(es):
        return [e["node_id"] for e in es.run_log]


class TestBranchEdges(_Base):
    def nodes(self):
        return [_cond("c"), _cond("t_target", field="x", value=1), _cond("f_target", field="x", value=1)]

    def test_true_branch_only_runs_true_target(self):
        edges = [GraphEdge(source="c", target="t_target", source_handle="true"),
                 GraphEdge(source="c", target="f_target", source_handle="false")]
        es = self.drive(self.nodes(), edges, {"flag": True})
        self.assertEqual(self.ran(es), ["c", "t_target"])

    def test_false_branch_only_runs_false_target(self):
        edges = [GraphEdge(source="c", target="t_target", source_handle="true"),
                 GraphEdge(source="c", target="f_target", source_handle="false")]
        es = self.drive(self.nodes(), edges, {"flag": False})
        self.assertEqual(self.ran(es), ["c", "f_target"])

    def test_no_handle_edges_run_on_both_branches(self):
        for flag in (True, False):
            edges = [GraphEdge(source="c", target="t_target"),
                     GraphEdge(source="c", target="f_target", source_handle="")]
            es = self.drive(self.nodes(), edges, {"flag": flag})
            self.assertEqual(self.ran(es), ["c", "t_target", "f_target"], f"flag={flag}")

    def test_mixed_handle_and_no_handle(self):
        edges = [GraphEdge(source="c", target="t_target", source_handle="true"),
                 GraphEdge(source="c", target="f_target")]
        es = self.drive(self.nodes(), edges, {"flag": False})
        self.assertEqual(self.ran(es), ["c", "f_target"])

    def test_true_edge_alone_does_nothing_on_false(self):
        edges = [GraphEdge(source="c", target="t_target", source_handle="true")]
        es = self.drive(self.nodes(), edges, {"flag": False})
        self.assertEqual(self.ran(es), ["c"])

    def test_exception_path_still_follows_false_edge(self):
        edges = [GraphEdge(source="c", target="t_target", source_handle="true"),
                 GraphEdge(source="c", target="f_target", source_handle="false")]
        # The source conditional raises; the targets succeed.
        calls = []

        async def handler(es, node, lc=None):
            calls.append(node.node_id)
            if node.node_id == "c":
                raise RuntimeError("boom")
            return {"matched": True}

        self.engine._execute_conditional_action_node = handler
        es = self.drive(self.nodes(), edges, {"flag": True})
        self.assertEqual(calls, ["c", "f_target"])
        self.assertEqual(es.run_log[0]["status"], "failed")
        self.assertNotIn("t_target", self.ran(es))

    def test_non_conditional_node_follows_all_non_loop_edges(self):
        nodes = [_ai("a"), _cond("x1", field="x", value=1), _cond("x2", field="x", value=1)]
        edges = [GraphEdge(source="a", target="x1", source_handle="true"),
                 GraphEdge(source="a", target="x2", source_handle="false")]
        es = self.drive(nodes, edges, {"flag": 1}, start="a")
        self.assertEqual(self.ran(es), ["a", "x1", "x2"])

    def test_loop_edges_unchanged(self):
        fan = FanOutNode(node_id="f", name="f", archetype=NodeArchetype.FAN_OUT,
                         loop_over={"source": "items", "iterator_var": "it"})
        nodes = [fan, _cond("c", field="it", value=1), _cond("t_target", field="x", value=1),
                 _cond("f_target", field="x", value=1)]
        edges = [GraphEdge(source="f", target="c", source_handle="loop"),
                 GraphEdge(source="c", target="t_target", source_handle="true"),
                 GraphEdge(source="c", target="f_target", source_handle="false")]
        es = self.drive(nodes, edges, {"items": [1, 2]}, start="f")
        # item 1 -> true branch, item 2 -> false branch; FanOut logs itself last.
        self.assertEqual(self.ran(es), ["c", "t_target", "c", "f_target", "f"])

    def test_unmatched_without_false_action_still_queues_undefined(self):
        edges = [GraphEdge(source="c", target="t_target", source_handle="true")]
        es = self.drive(self.nodes(), edges, {"flag": False})
        self.assertEqual(len(es.undefined_queue), 1)


if __name__ == "__main__":
    unittest.main()
