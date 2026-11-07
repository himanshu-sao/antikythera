"""S7: run status must reflect node failures.

Defect (verified at HEAD 66340b8): ``_execute_node`` catches node exceptions and
logs them as ``status="failed"`` entries, so ``_execute_graph`` always reached
``_finalize_run(..., "completed")``. A run where every node failed was reported
as "completed".

Fix under test (derived from the run_log entries):
- no failed entries             -> "completed"
- some failed, some succeeded   -> "partial"
- every executed entry failed   -> "failed"

These tests drive the real ``_execute_graph`` with a jira adapter method that
raises (an AsyncMock spy, no network) and read back the persisted run log.
"""
import asyncio
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.models.studio import (
    ExecutionState,
    GraphEdge,
    GraphRunLog,
    NodeArchetype,
    QueryNode,
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


def _query(node_id, action):
    return QueryNode(
        node_id=node_id,
        name=node_id,
        archetype=NodeArchetype.QUERY,
        adapter="jira_adapter",
        action=action,
        params={},
        output_ref=f"out_{node_id}",
    )


class TestRunStatusFromNodeOutcomes(unittest.TestCase):
    def setUp(self):
        vault = Mock(spec=SecretVault)
        vault.get_secret.return_value = {"access_token": "fake_token"}
        self.registry = OperatorRegistry(vault=vault)
        self.base_dir = tempfile.mkdtemp(prefix="studio_run_status_")
        self.engine = PathStepGraphEngine(
            base_dir=self.base_dir,
            operator_registry=self.registry,
            studio_graph_manager=None,
            skill_manager=None,
            run_manager=None,
        )
        adapter = self.registry.adapters["jira_adapter"]
        # Successful entry-point action.
        self.ok_spy = AsyncMock(return_value={"tickets": [{"id": "T-1"}]})
        adapter.list_tickets = self.ok_spy
        # Failing entry-point action (raises inside the node handler).
        self.bad_spy = AsyncMock(side_effect=RuntimeError("adapter exploded"))
        adapter.list_projects = self.bad_spy

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def _execute(self, nodes, edges=None):
        graph = StudioGraph(
            graph_id="g_status",
            name="status",
            nodes=nodes,
            edges=edges or [],
        )
        run_id = f"studio_run_{uuid.uuid4().hex[:12]}"
        exec_state = ExecutionState(
            graph_id=graph.graph_id,
            run_id=run_id,
            state={},
            run_log=[],
            undefined_queue=[],
            loop_stack=[],
            dry_run=True,
        )
        _run(self.engine._execute_graph(exec_state, graph))
        log = self.engine.get_run_log(run_id)
        self.assertIsNotNone(log, "finalized run log must be persisted")
        return log

    def test_all_nodes_succeed_is_completed(self):
        log = self._execute([_query("q_ok", "list_tickets")])
        self.assertEqual(log.status, "completed")
        self.assertEqual([r.status for r in log.node_results], ["success"])

    def test_no_nodes_is_completed(self):
        log = self._execute([])
        self.assertEqual(log.status, "completed")

    def test_some_failed_some_succeeded_is_partial(self):
        log = self._execute([_query("q_ok", "list_tickets"), _query("q_bad", "list_projects")])
        statuses = sorted(r.status for r in log.node_results)
        self.assertEqual(statuses, ["failed", "success"])
        self.assertEqual(log.status, "partial")
        self.bad_spy.assert_awaited_once()
        self.ok_spy.assert_awaited_once()

    def test_every_executed_node_failed_is_failed(self):
        log = self._execute([_query("q_bad1", "list_projects"), _query("q_bad2", "list_projects")])
        self.assertTrue(all(r.status == "failed" for r in log.node_results))
        self.assertEqual(len(log.node_results), 2)
        self.assertEqual(log.status, "failed")

    def test_failed_node_error_is_recorded(self):
        log = self._execute([_query("q_bad", "list_projects")])
        failed = [r for r in log.node_results if r.status == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertIn("adapter exploded", failed[0].error or "")

    def test_partial_run_keeps_successful_output(self):
        """A partial run still writes the output of the node that succeeded
        (status must not change what was persisted to state)."""
        log = self._execute([_query("q_ok", "list_tickets"), _query("q_bad", "list_projects")])
        ok = next(r for r in log.node_results if r.node_id == "q_ok")
        self.assertEqual(ok.status, "success")
        self.assertEqual(ok.output, {"tickets": [{"id": "T-1"}]})


if __name__ == "__main__":
    unittest.main()
