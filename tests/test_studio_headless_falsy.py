"""S10: headless runs must keep falsy node results, matching preview.

Defect (verified at HEAD 66340b8): ``_execute_node`` wrote a node's output to
state only when ``if result and output_ref`` held, so ``[]``, ``0``, ``""`` and
``False`` were silently dropped. ``preview_node`` checks ``is not None`` and
keeps them, so the same draft behaved differently in preview and in a run.

Fix under test: headless writes when ``result is not None``, same as preview.
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


def _query(node_id, output_ref, action="list_tickets"):
    return QueryNode(
        node_id=node_id,
        name=node_id,
        archetype=NodeArchetype.QUERY,
        adapter="jira_adapter",
        action=action,
        params={},
        output_ref=output_ref,
    )


class TestHeadlessKeepsFalsyResults(unittest.TestCase):
    def setUp(self):
        vault = Mock(spec=SecretVault)
        vault.get_secret.return_value = {"access_token": "fake_token"}
        self.registry = OperatorRegistry(vault=vault)
        self.base_dir = tempfile.mkdtemp(prefix="studio_falsy_")
        self.engine = PathStepGraphEngine(
            base_dir=self.base_dir,
            operator_registry=self.registry,
            studio_graph_manager=None,
            skill_manager=None,
            run_manager=None,
        )
        self.adapter = self.registry.adapters["jira_adapter"]

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def _run_nodes(self, nodes):
        graph = StudioGraph(graph_id="g_falsy", name="falsy", nodes=nodes, edges=[])
        run_id = f"studio_run_{uuid.uuid4().hex[:12]}"
        exec_state = ExecutionState(
            graph_id=graph.graph_id, run_id=run_id, state={}, run_log=[],
            undefined_queue=[], loop_stack=[], dry_run=True,
        )
        _run(self.engine._execute_graph(exec_state, graph))
        return exec_state, self.engine.get_run_log(run_id)

    def test_empty_list_result_is_written_to_state(self):
        self.adapter.list_tickets = AsyncMock(return_value=[])
        state_after, log = self._run_nodes([_query("q1", "items")])
        self.assertEqual(log.status, "completed")
        self.assertIn("items", state_after.state)
        self.assertEqual(state_after.state["items"], [])

    def test_zero_result_is_written_to_state(self):
        self.adapter.list_tickets = AsyncMock(return_value=0)
        state_after, _ = self._run_nodes([_query("q1", "count")])
        self.assertIn("count", state_after.state)
        self.assertEqual(state_after.state["count"], 0)

    def test_empty_string_and_false_are_written(self):
        self.adapter.list_tickets = AsyncMock(return_value="")
        self.adapter.list_projects = AsyncMock(return_value=False)
        state_after, _ = self._run_nodes([
            _query("q_str", "text"),
            _query("q_bool", "flag", action="list_projects"),
        ])
        self.assertEqual(state_after.state["text"], "")
        self.assertIs(state_after.state["flag"], False)

    def test_none_result_is_not_written(self):
        """Regression guard: None still means 'no output' (no key created)."""
        self.adapter.list_tickets = AsyncMock(return_value=None)
        state_after, _ = self._run_nodes([_query("q1", "items")])
        self.assertNotIn("items", state_after.state)

    def test_headless_matches_preview_for_falsy_results(self):
        """Preview keeps falsy results (is not None); headless must agree."""
        self.adapter.list_tickets = AsyncMock(return_value=[])
        node = _query("q1", "items")

        preview = _run(self.engine.preview_node(node, {}))
        state_after, _ = self._run_nodes([node])

        self.assertEqual(preview["updated_state"]["items"], [])
        self.assertEqual(state_after.state["items"], preview["updated_state"]["items"])


if __name__ == "__main__":
    unittest.main()
