"""T5-pre2 / Gap 1: dry_run flag must short-circuit the live conditional write.

Gap (verified at HEAD 772b9c2): no ``dry_run``/``log_mode``/``simulate`` field
existed anywhere in the Studio backend. So running a graph whose conditional
true/false branch calls ``JiraAdapter.update`` fired a LIVE network write
(``asyncio.create_task(self._execute_graph(...))`` is fire-and-forget with no
gate). Plan §6 requires exercising a graph dry *before* the single real Jira
write at slice-1 end ("after dry-run logging").

These tests pin the fix (dec #16): when ``ExecutionState.dry_run`` is True,
``_execute_conditional_action_node`` must NOT dispatch ``execute_step`` (the
``update_resource`` operator — the only side-effecting surface in slice 1);
instead it returns a ``{"matched", "dry_run": True, "would_have_run": ...}``
summary describing the suppressed write. Reads (Query) are unaffected and keep
running, so routing/queue/condition-match still populate.
"""
import asyncio
import unittest
from unittest.mock import Mock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.models.studio import (
    ExecutionState,
    ConditionalActionNode,
    NodeArchetype,
    ConditionType,
    Condition,
    RoutingStrategy,
)
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _make_engine():
    vault = Mock(spec=SecretVault)
    vault.get_secret.return_value = {"access_token": "fake_token"}
    registry = OperatorRegistry(vault=vault)
    import tempfile

    base_dir = tempfile.mkdtemp(prefix="studio_dry_run_test_")
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


def _cond_node(true_action="jira_adapter", false_action=None):
    """A conditional node whose true-branch would fire a jira update."""
    return ConditionalActionNode(
        node_id="c1",
        name="c1",
        archetype=NodeArchetype.CONDITIONAL_ACTION,
        routing_strategy=RoutingStrategy.CONDITION_FIRST,
        condition=Condition(
            type=ConditionType.EQUALS,
            field="ticket.severity",
            value="Critical",
        ),
        true_action=true_action,
        true_action_config={"transition": "escalate"},
        true_output_ref="escalated_id",
        false_action=false_action,
        false_action_config={},
        false_output_ref=None,
    )


class TestDryRunShortCircuit(unittest.TestCase):
    def setUp(self):
        self.engine, self.registry = _make_engine()
        # Spy on execute_step: any call means a LIVE write was dispatched.
        self.execute_calls = []

        async def fake_execute_step(step_config, state):
            self.execute_calls.append(step_config)
            return {"ok": True, "result_data": "LIVE-"}

        self.registry.execute_step = fake_execute_step

    def test_dry_run_true_does_not_dispatch_write(self):
        """dry_run=True + matched true-branch with an action: execute_step
        must NOT be called; handler returns a would-have-run summary."""
        node = _cond_node(true_action="jira_adapter")
        exec_state = ExecutionState(
            graph_id="g", run_id="r",
            state={"ticket": {"severity": "Critical"}},
            run_log=[], undefined_queue=[], loop_stack=[],
            dry_run=True,
        )

        result = _run(self.engine._execute_conditional_action_node(exec_state, node))

        self.assertEqual(self.execute_calls, [], "dry_run must suppress execute_step (no live write)")
        self.assertTrue(result["matched"], "condition still evaluated")
        self.assertTrue(result["dry_run"], "dry_run marker present in result")
        summary = result["would_have_run"]
        self.assertEqual(summary["branch"], "true")
        self.assertEqual(summary["adapter"], "jira_adapter")
        self.assertEqual(summary["action"], "update_resource")
        self.assertEqual(summary["config"], {"transition": "escalate"})
        self.assertEqual(summary["output_ref"], "escalated_id")

    def test_dry_run_false_still_dispatches_live_write(self):
        """Regression guard: with dry_run=False (default), the matched true
        branch still dispatches execute_step exactly as before."""
        node = _cond_node(true_action="jira_adapter")
        exec_state = ExecutionState(
            graph_id="g", run_id="r",
            state={"ticket": {"severity": "Critical"}},
            run_log=[], undefined_queue=[], loop_stack=[],
            dry_run=False,
        )

        result = _run(self.engine._execute_conditional_action_node(exec_state, node))

        self.assertEqual(len(self.execute_calls), 1, "dry_run=False must dispatch the live write")
        self.assertEqual(self.execute_calls[0]["operator_id"], "update_resource")
        self.assertEqual(self.execute_calls[0]["adapter_id"], "jira_adapter")
        self.assertTrue(result["matched"])
        self.assertNotIn("dry_run", result, "non-dry-run result keeps the legacy shape")

    def test_dry_run_true_noop_branch(self):
        """dry_run=True + a matched condition whose true-branch has NO action:
        summary is an explicit ‘noop’ marker, not the suppressed-write shape."""
        node = _cond_node(true_action=None)  # matched branch has no action
        exec_state = ExecutionState(
            graph_id="g", run_id="r",
            state={"ticket": {"severity": "Critical"}},
            run_log=[], undefined_queue=[], loop_stack=[],
            dry_run=True,
        )

        result = _run(self.engine._execute_conditional_action_node(exec_state, node))

        self.assertEqual(self.execute_calls, [], "noop branch never dispatched")
        self.assertTrue(result["matched"])
        summary = result["would_have_run"]
        self.assertEqual(summary["branch"], "true")
        self.assertEqual(summary["action"], "noop")
        self.assertIsNone(summary["adapter"])

    def test_dry_run_state_defaults_false(self):
        """ExecutionState.dry_run defaults to False, so existing callers that
        never set it keep live-write semantics (no silent behavior change)."""
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state={}, run_log=[], undefined_queue=[], loop_stack=[]
        )
        self.assertFalse(exec_state.dry_run, "dry_run must default False")


if __name__ == "__main__":
    unittest.main()
