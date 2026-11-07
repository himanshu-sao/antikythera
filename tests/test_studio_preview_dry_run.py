"""S1 / T2: preview_node must never perform a live adapter write.

Defect (verified at HEAD 66340b8): ``PathStepGraphEngine.preview_node`` built
its ephemeral ``ExecutionState`` without ``dry_run`` (default False), so
previewing a ConditionalAction whose matched branch has a configured action
dispatched a real ``update_resource`` through ``OperatorRegistry.execute_step``.
A preview is an authoring aid; it must be side-effect free.

These tests spy on the registry's write path with an ``AsyncMock`` and assert
it is never awaited, while the matched branch is still reported.
"""
import asyncio
import tempfile
import shutil
import unittest
from unittest.mock import AsyncMock, Mock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.models.studio import (
    ConditionalActionNode,
    Condition,
    ConditionType,
    NodeArchetype,
    RoutingStrategy,
)
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _cond_node(true_action="jira_adapter", false_action=None):
    return ConditionalActionNode(
        node_id="c1",
        name="c1",
        archetype=NodeArchetype.CONDITIONAL_ACTION,
        routing_strategy=RoutingStrategy.CONDITION_FIRST,
        condition=Condition(type=ConditionType.EQUALS, field="ticket.severity", value="Critical"),
        true_action=true_action,
        true_action_config={"transition": "escalate"},
        true_output_ref="escalated_id",
        false_action=false_action,
        false_action_config={"transition": "close"} if false_action else {},
        false_output_ref=None,
    )


class TestPreviewNeverWrites(unittest.TestCase):
    def setUp(self):
        vault = Mock(spec=SecretVault)
        vault.get_secret.return_value = {"access_token": "fake_token"}
        self.registry = OperatorRegistry(vault=vault)
        self.spy = AsyncMock(return_value={"result_data": "LIVE-WRITE"})
        self.registry.execute_step = self.spy
        self.base_dir = tempfile.mkdtemp(prefix="studio_preview_dry_")
        self.engine = PathStepGraphEngine(
            base_dir=self.base_dir,
            operator_registry=self.registry,
            studio_graph_manager=None,
            skill_manager=None,
            run_manager=None,
        )

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_preview_true_branch_with_action_does_not_write(self):
        node = _cond_node(true_action="jira_adapter")
        out = _run(self.engine.preview_node(node, {"ticket": {"severity": "Critical"}}))

        self.spy.assert_not_awaited()
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["matched_branch"], "true")
        self.assertTrue(out["result"]["dry_run"])
        self.assertEqual(out["result"]["would_have_run"]["adapter"], "jira_adapter")
        self.assertEqual(out["result"]["would_have_run"]["action"], "update_resource")

    def test_preview_false_branch_with_action_does_not_write(self):
        node = _cond_node(true_action=None, false_action="jira_adapter")
        out = _run(self.engine.preview_node(node, {"ticket": {"severity": "Low"}}))

        self.spy.assert_not_awaited()
        self.assertEqual(out["matched_branch"], "false")
        self.assertEqual(out["result"]["would_have_run"]["branch"], "false")
        self.assertEqual(out["result"]["would_have_run"]["config"], {"transition": "close"})

    def test_preview_branch_without_action_is_noop(self):
        node = _cond_node(true_action=None)
        out = _run(self.engine.preview_node(node, {"ticket": {"severity": "Critical"}}))

        self.spy.assert_not_awaited()
        self.assertEqual(out["matched_branch"], "true")
        self.assertEqual(out["result"]["would_have_run"]["action"], "noop")

    def test_preview_does_not_mutate_caller_state(self):
        node = _cond_node(true_action="jira_adapter")
        state = {"ticket": {"severity": "Critical"}}
        _run(self.engine.preview_node(node, state))
        self.assertEqual(state, {"ticket": {"severity": "Critical"}})

    def test_headless_default_still_writes(self):
        """Regression guard: the headless conditional handler with dry_run=False
        still dispatches the write, so the preview fix is scoped to preview."""
        from api.models.studio import ExecutionState

        node = _cond_node(true_action="jira_adapter")
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state={"ticket": {"severity": "Critical"}}, dry_run=False
        )
        _run(self.engine._execute_conditional_action_node(exec_state, node))
        self.spy.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
