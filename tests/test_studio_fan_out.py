"""SC-Q1b: _execute_fan_out_node direct coverage tests.

Target lines: studio_graph_engine.py:561-608

These tests cover the FanOut node handler:
- Iterate N items via a source_handle="loop" edge to a child ConditionalAction
- Assert one child exec per item + child_loop_context merge + child_results == [{iterator_var: item}, ...]
- Source None -> [], non-list source -> [], empty list -> []
- No loop-edge, loop_stack push-then-pop
"""
import asyncio
import tempfile
import unittest
from unittest.mock import Mock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.models.studio import (
    ExecutionState,
    FanOutNode,
    ConditionalActionNode,
    StudioGraph,
    GraphEdge,
    NodeArchetype,
    Condition,
    ConditionType,
    RoutingStrategy,
)
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _make_engine():
    vault = Mock(spec=SecretVault)
    vault.get_secret.return_value = {"access_token": "fake_token"}
    registry = OperatorRegistry(vault=vault)
    base_dir = tempfile.mkdtemp(prefix="studio_fanout_test_")
    engine = PathStepGraphEngine(
        base_dir=base_dir,
        operator_registry=registry,
        studio_graph_manager=None,
        skill_manager=None,
        run_manager=None,
    )
    return engine, registry


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _cond_node(action="jira_adapter", condition_field="ticket.status", condition_value="New", node_id="cond1"):
    return ConditionalActionNode(
        node_id=node_id,
        name=node_id,
        archetype=NodeArchetype.CONDITIONAL_ACTION,
        routing_strategy=RoutingStrategy.CONDITION_FIRST,
        condition=Condition(type=ConditionType.EQUALS, field=condition_field, value=condition_value),
        true_action=action,
        true_action_config={},
        true_output_ref=None,
        false_action=None,
        false_action_config={},
        false_output_ref=None,
    )


def _fanout_node(node_id="f1", source="tickets", iterator_var="ticket"):
    return FanOutNode(
        node_id=node_id,
        name=node_id,
        archetype=NodeArchetype.FAN_OUT,
        loop_over={"source": source, "iterator_var": iterator_var},
    )


def _graph_with_nodes(nodes, edges):
    return StudioGraph(graph_id="g", name="g", nodes=nodes, edges=edges)


class TestFanOutNodeExecution(unittest.TestCase):
    """Tests for _execute_fan_out_node covering lines 561-608."""

    def setUp(self):
        self.engine, _ = _make_engine()

    def _drive(self, state, fanout_node, cond_node, edges, loop_context=None):
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state=state,
            run_log=[], undefined_queue=[], loop_stack=[], dry_run=True,
        )
        graph = _graph_with_nodes([fanout_node, cond_node], edges)
        adjacency = self.engine._build_adjacency(graph)
        _run(self.engine._execute_node(
            exec_state, graph=graph, node_id=fanout_node.node_id,
            adjacency=adjacency, loop_context=loop_context,
        ))
        return exec_state

    def test_fanout_iterates_over_items_and_executes_child_per_item(self):
        """FanOut with 3 items + loop edge to ConditionalAction:
        - child executed 3 times (once per item)
        - child_loop_context merged per iteration (iterator_var bound)
        - child_results accumulates [{iterator_var: item}, ...]"""
        fanout = _fanout_node(node_id="f1", source="tickets", iterator_var="ticket")
        cond = _cond_node(condition_field="ticket.status", condition_value="New")

        # Loop edge: f1 --loop--> cond1
        edges = [GraphEdge(source="f1", target="cond1", source_handle="loop", target_handle=None)]

        state = {"tickets": [
            {"key": "T-1", "status": "New"},
            {"key": "T-2", "status": "WIP"},
            {"key": "T-3", "status": "New"},
        ]}

        exec_state = self._drive(state, fanout, cond, edges)

        # run_log: children execute first (3), then fanout logs itself (1) = 4 total
        self.assertEqual(len(exec_state.run_log), 4, "3 children + 1 FanOut")

        # Children execute first in run_log (they're called during fanout handler)
        cond_entries = exec_state.run_log[:3]
        self.assertEqual(len(cond_entries), 3)
        for i, entry in enumerate(cond_entries):
            self.assertEqual(entry["node_id"], "cond1")
            # The matched_branch reflects whether ticket.status == "New"
            expected = "true" if state["tickets"][i]["status"] == "New" else "false"
            self.assertEqual(entry.get("matched_branch"), expected)

        # FanOut entry logs last
        fanout_entry = exec_state.run_log[3]
        self.assertEqual(fanout_entry["node_id"], "f1")
        self.assertEqual(fanout_entry["status"], "success")
        self.assertEqual(fanout_entry["output"], [
            {"ticket": {"key": "T-1", "status": "New"}},
            {"ticket": {"key": "T-2", "status": "WIP"}},
            {"ticket": {"key": "T-3", "status": "New"}},
        ])

    def test_fanout_source_none_returns_empty_list(self):
        """Source path resolves to None -> returns [], no child execution."""
        fanout = _fanout_node(source="missing_path")
        cond = _cond_node()
        edges = [GraphEdge(source="f1", target="cond1", source_handle="loop")]

        exec_state = self._drive({}, fanout, cond, edges)

        self.assertEqual(len(exec_state.run_log), 1, "Only FanOut runs, no children")
        self.assertEqual(exec_state.run_log[0]["output"], [])
        self.assertEqual(exec_state.run_log[0]["status"], "success")

    def test_fanout_source_non_list_returns_empty_list(self):
        """Source path resolves to a non-list (e.g., dict) -> returns [], no children."""
        fanout = _fanout_node(source="data")
        cond = _cond_node()
        edges = [GraphEdge(source="f1", target="cond1", source_handle="loop")]

        state = {"data": {"items": [1, 2, 3]}}  # dict, not list
        exec_state = self._drive(state, fanout, cond, edges)

        self.assertEqual(len(exec_state.run_log), 1)
        self.assertEqual(exec_state.run_log[0]["output"], [])

    def test_fanout_source_empty_list_returns_empty_list(self):
        """Source is an empty list -> returns [], no children executed."""
        fanout = _fanout_node(source="items")
        cond = _cond_node()
        edges = [GraphEdge(source="f1", target="cond1", source_handle="loop")]

        state = {"items": []}
        exec_state = self._drive(state, fanout, cond, edges)

        self.assertEqual(len(exec_state.run_log), 1)
        self.assertEqual(exec_state.run_log[0]["output"], [])

    def test_fanout_no_loop_edge_no_children_executed(self):
        """FanOut with NO loop edge: iterates but has no children to execute.
        Returns child_results for each item but no child log entries."""
        fanout = _fanout_node(source="tickets", iterator_var="ticket")
        cond = _cond_node()
        # No edges from fanout
        edges = []

        state = {"tickets": [{"key": "A"}, {"key": "B"}]}
        exec_state = self._drive(state, fanout, cond, edges)

        self.assertEqual(len(exec_state.run_log), 1, "Only FanOut log entry")
        self.assertEqual(exec_state.run_log[0]["output"], [
            {"ticket": {"key": "A"}},
            {"ticket": {"key": "B"}},
        ])

    def test_fanout_loop_stack_push_pop(self):
        """loop_stack is pushed before iteration and popped after (even on exception)."""
        fanout = _fanout_node(source="items", iterator_var="item")
        cond = _cond_node()
        edges = [GraphEdge(source="f1", target="cond1", source_handle="loop")]

        state = {"items": [{"id": 1}, {"id": 2}]}
        exec_state = self._drive(state, fanout, cond, edges)

        # After execution, loop_stack should be empty (pushed then popped)
        self.assertEqual(exec_state.loop_stack, [])

    def test_fanout_loop_stack_popped_on_exception(self):
        """If child execution raises, loop_stack is still popped (finally block).
        The exception is caught and logged in _execute_node, not propagated."""
        fanout = _fanout_node(source="items", iterator_var="item")
        cond = _cond_node()
        edges = [GraphEdge(source="f1", target="cond1", source_handle="loop")]

        state = {"items": [{"id": 1}]}

        # Patch the conditional handler to raise
        original_execute = self.engine._execute_conditional_action_node

        async def raising_execute(*args, **kwargs):
            raise RuntimeError("child failed")

        self.engine._execute_conditional_action_node = raising_execute

        exec_state = ExecutionState(
            graph_id="g", run_id="r", state=state,
            run_log=[], undefined_queue=[], loop_stack=[], dry_run=True,
        )
        graph = _graph_with_nodes([fanout, cond], edges)
        adjacency = self.engine._build_adjacency(graph)

        # Exception is caught in _execute_node, not propagated
        _run(self.engine._execute_node(
            exec_state, graph=graph, node_id="f1",
            adjacency=adjacency, loop_context=None,
        ))

        # loop_stack must be empty even after exception
        self.assertEqual(exec_state.loop_stack, [], "loop_stack must be popped in finally")
        # The child failure should be logged
        failed_entries = [e for e in exec_state.run_log if e["status"] == "failed"]
        self.assertEqual(len(failed_entries), 1)
        self.assertIn("child failed", failed_entries[0]["error"])

    def test_fanout_child_loop_context_merges_with_parent(self):
        """child_loop_context = {**parent_loop_context, iterator_var: item}.
        Parent loop_context values should be preserved."""
        fanout = _fanout_node(source="tickets", iterator_var="ticket")
        cond = _cond_node(condition_field="parent.value", condition_value="PARENT")
        edges = [GraphEdge(source="f1", target="cond1", source_handle="loop")]

        state = {"tickets": [{"key": "T-1"}]}
        parent_loop = {"parent": {"value": "PARENT"}}

        exec_state = self._drive(state, fanout, cond, edges, loop_context=parent_loop)

        # The conditional should see parent.value from loop_context
        # Children execute first in run_log
        cond_entry = exec_state.run_log[0]
        self.assertEqual(cond_entry.get("matched_branch"), "true")

    def test_fanout_multiple_loop_edges_all_executed(self):
        """Multiple loop edges from FanOut -> each target executed per item."""
        fanout = _fanout_node(source="items", iterator_var="item")
        cond1 = _cond_node(node_id="cond1", condition_field="item.id", condition_value=1)
        cond2 = _cond_node(node_id="cond2", condition_field="item.id", condition_value=1)
        edges = [
            GraphEdge(source="f1", target="cond1", source_handle="loop"),
            GraphEdge(source="f1", target="cond2", source_handle="loop"),
        ]

        state = {"items": [{"id": 1}, {"id": 2}]}
        graph = _graph_with_nodes([fanout, cond1, cond2], edges)
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state=state,
            run_log=[], undefined_queue=[], loop_stack=[], dry_run=True,
        )
        adjacency = self.engine._build_adjacency(graph)
        _run(self.engine._execute_node(
            exec_state, graph=graph, node_id="f1",
            adjacency=adjacency, loop_context=None,
        ))

        # Children execute first: 2 children * 2 items = 4 entries, then FanOut = 1 = 5 total
        self.assertEqual(len(exec_state.run_log), 5)
        cond_entries = [e for e in exec_state.run_log if e["node_id"] in ("cond1", "cond2")]
        self.assertEqual(len(cond_entries), 4, "2 children * 2 items")

    def test_fanout_iterator_var_name_custom(self):
        """Custom iterator_var name is used in child_loop_context and output."""
        fanout = _fanout_node(source="items", iterator_var="my_item")
        cond = _cond_node(condition_field="my_item.value", condition_value=42)
        edges = [GraphEdge(source="f1", target="cond1", source_handle="loop")]

        state = {"items": [{"value": 42}, {"value": 99}]}
        exec_state = self._drive(state, fanout, cond, edges)

        # Children execute first
        cond_entries = exec_state.run_log[:2]
        self.assertEqual(cond_entries[0].get("matched_branch"), "true")
        self.assertEqual(cond_entries[1].get("matched_branch"), "false")

        # FanOut entry logs last
        fanout_output = exec_state.run_log[2]["output"]
        self.assertEqual(fanout_output[0]["my_item"], {"value": 42})
        self.assertEqual(fanout_output[1]["my_item"], {"value": 99})

    def test_fanout_state_write_no_output_ref(self):
        """FanOut has no output_ref, so nothing is written to state."""
        fanout = _fanout_node(source="items")
        cond = _cond_node()
        edges = [GraphEdge(source="f1", target="cond1", source_handle="loop")]

        state = {"items": [1, 2]}
        exec_state = self._drive(state, fanout, cond, edges)

        # State should be unchanged (no output_ref on FanOut)
        self.assertEqual(exec_state.state, state)


if __name__ == "__main__":
    unittest.main()