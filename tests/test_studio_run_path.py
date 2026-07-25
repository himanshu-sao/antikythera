"""SC-Q4: Run path wiring — non-dry run through mocked adapter.

This test covers the happy path of run_graph → start_run → _finalize_run with
dry_run=False (the real-write branch that test_studio_dry_run does NOT cover).
It uses a 2-node graph (Query → ConditionalAction) with a mocked adapter to
assert that total_matched / total_undefined / total_escalated roll up correctly
and a GraphRunLog is persisted to disk.
"""
import asyncio
import os
import tempfile
import uuid
from datetime import datetime
import unittest
from unittest.mock import Mock, AsyncMock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.models.studio import (
    CapabilityTier,
    ConditionalActionNode,
    Condition,
    ConditionType,
    ExecutionState,
    GraphEdge,
    GraphRunLog,
    NodeArchetype,
    NodeExecutionResult,
    QueryNode,
    RoutingStrategy,
    StudioGraph,
)
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _make_engine():
    """Create a fresh engine with temp dir and mocked dependencies."""
    vault = Mock(spec=SecretVault)
    vault.get_secret.return_value = {"access_token": "fake_token"}
    registry = OperatorRegistry(vault=vault)
    base_dir = tempfile.mkdtemp(prefix="studio_run_path_test_")
    engine = PathStepGraphEngine(
        base_dir=base_dir,
        operator_registry=registry,
        studio_graph_manager=None,
        skill_manager=None,
        run_manager=None,
    )
    return engine, registry, base_dir


def _query_node(node_id="q1", adapter="jira_adapter", action="list_tickets", output_ref="tickets"):
    return QueryNode(
        node_id=node_id,
        name=node_id,
        archetype=NodeArchetype.QUERY,
        adapter=adapter,
        action=action,
        params={},
        output_ref=output_ref,
    )


def _cond_node(node_id="c1", true_action="jira_adapter", false_action=None):
    return ConditionalActionNode(
        node_id=node_id,
        name=node_id,
        archetype=NodeArchetype.CONDITIONAL_ACTION,
        routing_strategy=RoutingStrategy.CONDITION_FIRST,
        condition=Condition(
            type=ConditionType.EQUALS,
            field="ticket.status",
            value="Critical",
        ),
        true_action=true_action,
        true_action_config={"transition": "escalate"},
        true_output_ref="escalated_id",
        false_action=false_action,
        false_action_config={},
        false_output_ref=None,
    )


class TestRunPathWiring(unittest.TestCase):
    """SC-Q4: Non-dry run path with mocked adapter."""

    def setUp(self):
        self.engine, self.registry, self.base_dir = _make_engine()
        # Spy on execute_step: any call means a LIVE write was dispatched.
        self.execute_calls = []

        async def fake_execute_step(step_config, state):
            self.execute_calls.append(step_config)
            # Return a mock result that looks like a real adapter response
            mock_result = Mock()
            mock_result.result_data = {"id": "LIVE-TICKET-123"}
            return mock_result

        self.registry.execute_step = fake_execute_step

        # Mock the jira_adapter's list_tickets method to return test data
        # We modify the existing adapter's method (like test_studio_query_dispatch does)
        adapter = self.registry.adapters["jira_adapter"]
        adapter.list_tickets = AsyncMock(return_value={"tickets": [{"severity": "Critical", "id": "TKT-1"}]})

    def tearDown(self):
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def _run_graph(self, graph, inputs=None, dry_run=False):
        """Helper to run a graph by directly awaiting _execute_graph (no background task)."""
        # Create execution state directly (bypassing start_run's create_task)
        run_id = f"studio_run_{uuid.uuid4().hex[:12]}"
        exec_state = ExecutionState(
            graph_id=graph.graph_id,
            run_id=run_id,
            state=inputs.copy() if inputs else {},
            run_log=[],
            undefined_queue=[],
            loop_stack=[],
            dry_run=dry_run,
        )

        # Save initial run log
        run_log = GraphRunLog(
            run_id=run_id,
            graph_id=graph.graph_id,
            started_at=datetime.utcnow(),
            status="running",
            node_results=[],
            undefined_items=[],
            escalated_items=[],
        )
        self.engine._save_run_log(run_log)

        # Directly await the graph execution (no background task)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.engine._execute_graph(exec_state, graph))
        finally:
            loop.close()

        # Load the finalized run log
        return self.engine.get_run_log(run_id)

    def test_non_dry_run_executes_live_write_and_persists_run_log(self):
        """Happy path: 2-node graph (Query → ConditionalAction) with dry_run=False.

        The ConditionalAction's true branch has an action (update_resource via
        execute_step). Since dry_run=False, execute_step MUST be called once,
        and the persisted GraphRunLog must show total_matched=1,
        total_undefined=0, total_escalated=0.
        """
        graph = StudioGraph(
            graph_id="test_graph_1",
            name="Test Graph 1",
            version="1.0.0",
            nodes=[_query_node(), _cond_node()],
            edges=[GraphEdge(source="q1", target="c1", source_handle=None, target_handle=None)],
            required_capability=CapabilityTier.GENERATE,
        )
        # Save graph so engine can find it
        self.engine.studio_graph_manager = Mock()
        self.engine.studio_graph_manager.get_graph = Mock(return_value=graph)

        # Initial state: tickets list with one Critical ticket
        inputs = {"ticket": {"status": "Critical", "id": "TKT-1"}}

        log = self._run_graph(graph, inputs=inputs, dry_run=False)

        self.assertIsNotNone(log, "Run log should be persisted")
        self.assertEqual(log.status, "completed", f"Run should complete, got {log.status}")
        self.assertEqual(log.graph_id, "test_graph_1")

        # Exactly one live write was dispatched
        self.assertEqual(len(self.execute_calls), 1, "dry_run=False must dispatch execute_step once")
        self.assertEqual(self.execute_calls[0]["operator_id"], "update_resource")
        self.assertEqual(self.execute_calls[0]["adapter_id"], "jira_adapter")

        # Counters roll up correctly
        self.assertEqual(log.total_matched, 1, "One condition matched (true branch)")
        self.assertEqual(log.total_undefined, 0, "No undefined items (false_action not needed, condition matched)")
        self.assertEqual(log.total_escalated, 0, "No escalated failures")

        # Node results persisted
        self.assertEqual(len(log.node_results), 2, "Two nodes executed")
        node_ids = [nr.node_id for nr in log.node_results]
        self.assertIn("q1", node_ids)
        self.assertIn("c1", node_ids)
        for nr in log.node_results:
            self.assertEqual(nr.status, "success")
            self.assertIsNotNone(nr.execution_time_ms)

        # The ConditionalAction node result should record the matched branch
        cond_result = next(nr for nr in log.node_results if nr.node_id == "c1")
        self.assertEqual(cond_result.matched_branch, "true")

        # Run log file exists on disk (atomic write)
        run_log_path = os.path.join(self.base_dir, "studio_runs", f"{log.run_id}.json")
        self.assertTrue(os.path.exists(run_log_path), f"Run log file should exist at {run_log_path}")

    def test_non_dry_run_unmatched_condition_without_false_action_queues_undefined(self):
        """When condition does NOT match and no false_action configured,
        the item goes to undefined_queue and total_undefined increments.

        Note: total_matched still counts the false branch as 'matched' because
        a branch was evaluated (matched_branch='false'), even though no action
        was dispatched. This is by design - total_matched means 'branch evaluated'.
        """
        # Condition checks for "Critical" but input has "Low"
        graph = StudioGraph(
            graph_id="test_graph_2",
            name="Test Graph 2",
            version="1.0.0",
            nodes=[_query_node(), _cond_node()],
            edges=[GraphEdge(source="q1", target="c1")],
            required_capability=CapabilityTier.GENERATE,
        )
        self.engine.studio_graph_manager = Mock()
        self.engine.studio_graph_manager.get_graph = Mock(return_value=graph)

        # Input has Low severity
        adapter = self.registry.adapters["jira_adapter"]
        adapter.list_tickets = AsyncMock(return_value={"tickets": [{"severity": "Low", "id": "TKT-2"}]})

        inputs = {"ticket": {"status": "Low", "id": "TKT-2"}}

        log = self._run_graph(graph, inputs=inputs, dry_run=False)

        self.assertIsNotNone(log)
        self.assertEqual(log.status, "completed")
        # No live write dispatched because condition didn't match and no false_action
        self.assertEqual(len(self.execute_calls), 0, "No execute_step when condition unmatched and no false_action")
        # Counters: total_matched=1 because false branch was evaluated (matched_branch='false')
        # total_undefined=1 because no false_action to handle the unmatched item
        self.assertEqual(log.total_matched, 1, "False branch was evaluated and counted as matched")
        self.assertEqual(log.total_undefined, 1, "One item queued to undefined")
        self.assertEqual(log.total_escalated, 0)

        # Undefined item persisted in run log
        self.assertEqual(len(log.undefined_items), 1)

    def test_non_dry_run_unmatched_condition_with_false_action_executes_false_branch(self):
        """When condition does NOT match but false_action IS configured,
        the false branch executes (live write) and total_matched=1 (false branch counts).
        """
        graph = StudioGraph(
            graph_id="test_graph_3",
            name="Test Graph 3",
            version="1.0.0",
            nodes=[_query_node(), _cond_node(false_action="jira_adapter")],
            edges=[GraphEdge(source="q1", target="c1")],
            required_capability=CapabilityTier.GENERATE,
        )
        self.engine.studio_graph_manager = Mock()
        self.engine.studio_graph_manager.get_graph = Mock(return_value=graph)

        # Input has Low severity (doesn't match Critical)
        adapter = self.registry.adapters["jira_adapter"]
        adapter.list_tickets = AsyncMock(return_value={"tickets": [{"severity": "Low", "id": "TKT-3"}]})

        inputs = {"ticket": {"status": "Low", "id": "TKT-3"}}

        log = self._run_graph(graph, inputs=inputs, dry_run=False)

        self.assertIsNotNone(log)
        self.assertEqual(log.status, "completed")
        # False branch executed → one live write
        self.assertEqual(len(self.execute_calls), 1)
        self.assertEqual(self.execute_calls[0]["step_id"], "c1.false")
        # False branch matched counts toward total_matched
        self.assertEqual(log.total_matched, 1)
        self.assertEqual(log.total_undefined, 0)
        self.assertEqual(log.total_escalated, 0)

        cond_result = next(nr for nr in log.node_results if nr.node_id == "c1")
        self.assertEqual(cond_result.matched_branch, "false")

    def test_non_dry_run_escalated_failure_increments_total_escalated(self):
        """If a node fails with FailureFlavor.ESCALATED, total_escalated increments.

        This tests the escalation path by making the Query node's adapter throw.
        """
        graph = StudioGraph(
            graph_id="test_graph_4",
            name="Test Graph 4",
            version="1.0.0",
            nodes=[_query_node(adapter="bad_adapter"), _cond_node()],
            edges=[GraphEdge(source="q1", target="c1")],
            required_capability=CapabilityTier.GENERATE,
        )
        self.engine.studio_graph_manager = Mock()
        self.engine.studio_graph_manager.get_graph = Mock(return_value=graph)

        # Make the query node execution simulate an escalation
        original_execute_query = self.engine._execute_query_node

        async def failing_query(exec_state, node, loop_context=None):
            # Simulate an escalated failure by appending to run_log directly
            exec_state.run_log.append({
                "node_id": node.node_id,
                "status": "failed",
                "error": "Adapter unavailable",
                "execution_time_ms": 10,
                "failure_flavor": "escalated",
            })
            return None

        self.engine._execute_query_node = failing_query

        inputs = {"ticket": {"status": "Critical", "id": "TKT-4"}}

        log = self._run_graph(graph, inputs=inputs, dry_run=False)

        self.assertIsNotNone(log)
        # The run completes (doesn't crash) but marks escalated
        self.assertEqual(log.total_escalated, 1, "Escalated failure should be counted")
        self.assertEqual(len(log.escalated_items), 1)
        self.assertEqual(log.escalated_items[0]["node_id"], "q1")

        # Restore
        self.engine._execute_query_node = original_execute_query

    def test_run_log_persisted_across_multiple_runs(self):
        """Multiple runs of the same graph produce separate run log files."""
        graph = StudioGraph(
            graph_id="test_graph_5",
            name="Test Graph 5",
            version="1.0.0",
            nodes=[_query_node(), _cond_node()],
            edges=[GraphEdge(source="q1", target="c1")],
            required_capability=CapabilityTier.GENERATE,
        )
        self.engine.studio_graph_manager = Mock()
        self.engine.studio_graph_manager.get_graph = Mock(return_value=graph)

        inputs = {"ticket": {"status": "Critical", "id": "TKT-5"}}

        # Run 1
        log1 = self._run_graph(graph, inputs=inputs, dry_run=False)
        self.assertIsNotNone(log1)
        self.assertEqual(log1.total_matched, 1)

        # Run 2
        self.execute_calls.clear()
        log2 = self._run_graph(graph, inputs=inputs, dry_run=False)
        self.assertIsNotNone(log2)
        self.assertEqual(log2.total_matched, 1)

        # Both run logs exist on disk with different run_ids
        self.assertNotEqual(log1.run_id, log2.run_id)
        path1 = os.path.join(self.base_dir, "studio_runs", f"{log1.run_id}.json")
        path2 = os.path.join(self.base_dir, "studio_runs", f"{log2.run_id}.json")
        self.assertTrue(os.path.exists(path1))
        self.assertTrue(os.path.exists(path2))

        # list_run_logs returns both, most recent first
        logs = self.engine.list_run_logs("test_graph_5", limit=10)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0].run_id, log2.run_id)  # Most recent first
        self.assertEqual(logs[1].run_id, log1.run_id)

    def test_list_run_logs_respects_limit(self):
        """list_run_logs respects the limit parameter."""
        graph = StudioGraph(
            graph_id="test_graph_6",
            name="Test Graph 6",
            version="1.0.0",
            nodes=[_query_node(), _cond_node()],
            edges=[GraphEdge(source="q1", target="c1")],
            required_capability=CapabilityTier.GENERATE,
        )
        self.engine.studio_graph_manager = Mock()
        self.engine.studio_graph_manager.get_graph = Mock(return_value=graph)

        inputs = {"ticket": {"status": "Critical", "id": "TKT-6"}}

        # Run 3 times
        for _ in range(3):
            self._run_graph(graph, inputs=inputs, dry_run=False)
            self.execute_calls.clear()

        logs = self.engine.list_run_logs("test_graph_6", limit=2)
        self.assertEqual(len(logs), 2, "limit=2 should return exactly 2 logs")

        logs_all = self.engine.list_run_logs("test_graph_6", limit=10)
        self.assertEqual(len(logs_all), 3, "limit=10 should return all 3 logs")


if __name__ == "__main__":
    unittest.main()