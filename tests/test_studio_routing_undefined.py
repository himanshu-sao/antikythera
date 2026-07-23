"""T5-pre3 / Gap 3 + Gap 4: ConditionalAction routing + undefined-queue accounting.

Gaps (verified at HEAD 878966f, against plan §6 acceptance items):
- **Gap 3 — `matched_branch` never recorded → `total_matched` always 0.**
  `_execute_conditional_action_node` returns ``{"matched": bool, ...}`` but
  `_execute_node`'s success run-log append ignored that, so
  ``NodeExecutionResult.matched_branch`` was always None and
  ``_finalize_run``'s ``total_matched`` branch (guarded on
  ``log_entry.get("matched_branch") in ("true","false")``) never fired. Plan §6
  "condition-match routing dispatches" + the perpetual aggregate both broke.
- **Gap 4 — `undefined_queue` populated nowhere.** ``exec_state.undefined_queue``
  was initialised ``[]`` and never appended to, so unmatched items never landed in
  the undefined-queue and ``/undefined-queue`` always returned ``[]`` — directly
  failing plan §6 "un-matched items land in the undefined-queue (cap 100)".

Fix (dec #11/#20): in ``_execute_node``, when the node is a ConditionalAction
whose result carries ``matched``, record ``matched_branch`` on the log entry
(true/false) so the aggregate counts; and when the condition did NOT match AND
no ``false_action`` is configured, buffer the unmatched item into
``exec_state.undefined_queue`` (the cap-100 clip happens later in
``_finalize_run``) with a diagnostic snapshot of the condition fields, and tag
the log entry ``failure_flavor=undefined``. Matched conditionals never queue.

These tests pin the fix at the engine-handler level (mirroring the
test_studio_dry_run conventions), no live adapter.
"""
import asyncio
import tempfile
import unittest
from unittest.mock import Mock

from api.execution.studio_graph_engine import (
    PathStepGraphEngine,
    _condition_field,
    _iterator_var,
)
from api.models.studio import (
    ConditionalActionNode,
    ExecutionState,
    GraphRunLog,
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
    base_dir = tempfile.mkdtemp(prefix="studio_routing_test_")
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


def _cond_node(true_action=None, condition_field="ticket.status", condition_value="New", false_action=None):
    return ConditionalActionNode(
        node_id="c1",
        name="c1",
        archetype=NodeArchetype.CONDITIONAL_ACTION,
        routing_strategy=RoutingStrategy.CONDITION_FIRST,
        condition=Condition(type=ConditionType.EQUALS, field=condition_field, value=condition_value),
        true_action=true_action,          # None → matched branch has no action (noop)
        true_action_config={},
        true_output_ref=None,
        false_action=false_action,        # None → unmatched items queue (dec #11)
        false_action_config={},
        false_output_ref=None,
    )


def _graph_with(node):
    """Minimal StudioGraph carrying one node, no edges (adjacency {node_id: []})."""
    from api.models.studio import StudioGraph
    return StudioGraph(graph_id="g", name="g", nodes=[node], edges=[])


class TestMatchedBranchRecorded(unittest.TestCase):
    """Gap 3: matched_branch must land on the run-log entry so total_matched
    counts in _finalize_run."""

    def setUp(self):
        self.engine, _ = _make_engine()

    def _drive(self, state, node, loop_context=None):
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state=state,
            run_log=[], undefined_queue=[], loop_stack=[], dry_run=True,
        )
        _run(self.engine._execute_node(
            exec_state,
            graph=_graph_with(node),
            node_id="c1",
            adjacency={"c1": []},
            loop_context=loop_context,
        ))
        return exec_state

    def test_matched_true_records_true_branch(self):
        node = _cond_node(true_action="jira_adapter", condition_value="New")
        es = self._drive({"ticket": {"status": "New"}}, node)
        entry = es.run_log[-1]
        self.assertEqual(entry["matched_branch"], "true")
        self.assertNotIn("failure_flavor", entry, "a matched conditional is not undefined")

    def test_matched_false_records_false_branch_when_false_action_present(self):
        node = _cond_node(true_action="jira_adapter", condition_value="New", false_action="jira_adapter")
        es = self._drive({"ticket": {"status": "Closed"}}, node)   # != New
        entry = es.run_log[-1]
        self.assertEqual(entry["matched_branch"], "false")
        self.assertEqual(es.undefined_queue, [], "false_action present → not undefined")

    def test_finalize_counts_matched(self):
        node = _cond_node(true_action="jira_adapter", condition_value="New")
        es = self._drive({"ticket": {"status": "New"}}, node)
        # _finalize_run runs on a graph; total_matched derives from run_log matched_branch.
        _run(self.engine._finalize_run(es, _graph_with(node), "completed"))
        log = self.engine.get_run_log("r")
        self.assertIsInstance(log, GraphRunLog)
        self.assertEqual(log.total_matched, 1, "matched_branch must roll up into total_matched")


class TestUndefinedQueue(unittest.TestCase):
    """Gap 4: an unmatched conditional with no false_action buffers the item."""

    def setUp(self):
        self.engine, _ = _make_engine()

    def _drive(self, state, node, loop_context=None):
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state=state,
            run_log=[], undefined_queue=[], loop_stack=[], dry_run=True,
        )
        _run(self.engine._execute_node(
            exec_state, graph=_graph_with(node), node_id="c1", adjacency={"c1": []}, loop_context=loop_context,
        ))
        return exec_state

    def test_unmatched_no_false_action_queues_item(self):
        node = _cond_node(true_action="jira_adapter", condition_value="New")  # no false_action
        es = self._drive({"ticket": {"status": "WIP"}}, node)  # status != New
        self.assertEqual(len(es.undefined_queue), 1)
        queued = es.undefined_queue[0]
        self.assertEqual(queued["node_id"], "c1")
        self.assertEqual(queued["condition_field"], "ticket.status")
        self.assertEqual(queued["state_snapshot"], {"ticket.status": "WIP"})
        entry = es.run_log[-1]
        self.assertEqual(entry["failure_flavor"], "undefined")

    def test_matched_never_queues(self):
        node = _cond_node(true_action="jira_adapter", condition_value="New")
        es = self._drive({"ticket": {"status": "New"}}, node)
        self.assertEqual(es.undefined_queue, [])

    def test_unmatched_with_false_action_does_not_queue(self):
        node = _cond_node(
            true_action="jira_adapter", condition_value="New",
            false_action="jira_adapter",
        )
        es = self._drive({"ticket": {"status": "WIP"}}, node)
        self.assertEqual(es.undefined_queue, [], "false_action present → routed, not undefined")

    def test_queue_item_captures_loop_item(self):
        """Inside a FanOut, the queued undefined item should carry the loop item."""
        node = _cond_node(true_action="jira_adapter", condition_field="ticket.fields.status", condition_value="New")
        loop_item = {"key": "TLOCK-99", "fields": {"status": "Backlog"}}
        es = self._drive({}, node, loop_context={"ticket": loop_item})
        self.assertEqual(len(es.undefined_queue), 1)
        queued = es.undefined_queue[0]
        self.assertEqual(queued["item"], loop_item)
        # Jira fields-fallback: _get_nested_value resolves ticket.fields.status
        self.assertEqual(queued["state_snapshot"], {"ticket.fields.status": "Backlog"})

    def test_finalize_undefined_count_rolls_up(self):
        node = _cond_node(true_action="jira_adapter", condition_value="New")
        es = self._drive({"ticket": {"status": "WIP"}}, node)
        _run(self.engine._finalize_run(es, _graph_with(node), "completed"))
        log = self.engine.get_run_log("r")
        self.assertEqual(log.total_undefined, 1)
        self.assertEqual(len(log.undefined_items), 1)


class TestUndefinedQueueCap(unittest.TestCase):
    """Cap 100 (dec #20) is enforced in _finalize_run, not at append time —
    appending the 101st item must not raise; only the first 100 persist."""

    def setUp(self):
        self.engine, _ = _make_engine()

    def test_cap_100_enforced_in_finalize(self):
        node = _cond_node(true_action="jira_adapter", condition_value="New")
        es = ExecutionState(
            graph_id="g", run_id="r", state={"ticket": {"status": "WIP"}},
            run_log=[], undefined_queue=[], loop_stack=[], dry_run=True,
        )
        graph = _graph_with(node)
        # Drive the same unmatched conditional 120 times in one run.
        for _ in range(120):
            _run(self.engine._execute_node(
                es, graph=graph, node_id="c1", adjacency={"c1": []}, loop_context=None,
            ))
        _run(self.engine._finalize_run(es, graph, "completed"))
        log = self.engine.get_run_log("r")
        self.assertLessEqual(len(log.undefined_items), 100)
        self.assertEqual(log.total_undefined, 100, "total_undefined clipped at the cap")


class TestHelpersPure(unittest.TestCase):
    """The free helpers are pure + testable without the engine."""

    def test_iterator_var_picks_first_public_key(self):
        node = _cond_node()
        self.assertEqual(_iterator_var(node, {"ticket": {"status": "New"}}), "ticket")

    def test_iterator_var_none_without_loop_context(self):
        self.assertIsNone(_iterator_var(_cond_node(), None))

    def test_condition_field_simple_vs_compound(self):
        self.assertEqual(
            _condition_field(Condition(type=ConditionType.EQUALS, field="t.s", value="x")),
            "t.s",
        )
        from api.models.studio import ConditionLogic
        self.assertIsNone(_condition_field(ConditionLogic(logic="AND", conditions=[])))


if __name__ == "__main__":
    unittest.main()
