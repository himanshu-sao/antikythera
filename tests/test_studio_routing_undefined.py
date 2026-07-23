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
    _condition_snapshot,
    _iterator_var,
)
from api.models.studio import (
    ConditionalActionNode,
    ExecutionState,
    FanOutNode,
    GraphRunLog,
    NodeArchetype,
    Condition,
    ConditionLogic,
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

    def test_queued_item_is_none_without_loop_context(self):
        """When the conditional runs outside a FanOut there is no loop item to
        buffer — the queued item's ``item`` field must be the None sentry
        (the ``_iterator_var`` ternary at the append site), not an AttributeError."""
        node = _cond_node(true_action="jira_adapter", condition_value="New")  # no false_action
        es = self._drive({"ticket": {"status": "WIP"}}, node, loop_context=None)
        self.assertEqual(len(es.undefined_queue), 1)
        self.assertIsNone(es.undefined_queue[0]["item"], "no loop_context → no iterable item to queue")
        # condition_field + state_snapshot still populate for the reviewer
        self.assertEqual(es.undefined_queue[0]["condition_field"], "ticket.status")

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
        self.assertIsNone(_condition_field(ConditionLogic(logic="AND", conditions=[])))

    def test_condition_snapshot_simple_condition(self):
        """The simple-Condition branch resolves the single field from state."""
        engine, _ = _make_engine()
        cond = Condition(type=ConditionType.EQUALS, field="ticket.status", value="New")
        snap = _condition_snapshot(cond, {"ticket": {"status": "WIP"}}, None, engine._get_nested_value)
        self.assertEqual(snap, {"ticket.status": "WIP"})

    def test_condition_snapshot_compound_AND_walks_each_conjunct(self):
        """The ConditionLogic (AND/OR) branch — currently untested — must
        resolve each conjunct's field and merge snapshots. This is the path
        _condition_field returns None for (compound has no single field), so
        only the snapshot carries the diagnostic."""
        engine, _ = _make_engine()
        compound = ConditionLogic(logic="AND", conditions=[
            Condition(type=ConditionType.EQUALS, field="ticket.status", value="New"),
            Condition(type=ConditionType.EQUALS, field="ticket.priority", value="P1"),
        ])
        state = {"ticket": {"status": "WIP", "priority": "P2"}}
        snap = _condition_snapshot(compound, state, None, engine._get_nested_value)
        # both conjunct fields resolved and merged
        self.assertEqual(snap, {"ticket.status": "WIP", "ticket.priority": "P2"})

    def test_condition_snapshot_loop_context_overrides_state(self):
        """loop_context scope must shadow exec state for the resolver (the
        per-item view beats the run-global view inside a FanOut)."""
        engine, _ = _make_engine()
        cond = Condition(type=ConditionType.EQUALS, field="ticket.status", value="New")
        state = {"ticket": {"status": "WIP"}}                       # run-global
        loop = {"ticket": {"status": "Backlog"}}                   # per-item shadows
        snap = _condition_snapshot(cond, state, loop, engine._get_nested_value)
        self.assertEqual(snap, {"ticket.status": "Backlog"}, "loop_context must win over state")


class TestFanOutNoOutputRef(unittest.TestCase):
    """``_execute_node`` reads ``node.output_ref`` defensively via getattr —
    FanOut/ConditionalAction don't declare output_ref. Driving a FanOut must
    NOT AttributeError at the post-handler state-write block, and must NOT
    write a state key (FanOut has no output_ref). The (existing) conditional
    tests exercise this branch implicitly; this test asserts it directly for
    the FanOut archetype."""

    def setUp(self):
        self.engine, _ = _make_engine()

    def test_fan_out_node_does_not_crash_or_write_state(self):
        fanout = FanOutNode(
            node_id="f1", name="f1",
            archetype=NodeArchetype.FAN_OUT,
            loop_over={"source": "items", "iterator_var": "ticket"},
        )
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state={}, run_log=[],
            undefined_queue=[], loop_stack=[], dry_run=True,
        )
        # No AttributeError, no exception => the getattr(node, "output_ref", None)
        # guard held; FanOut has no output_ref so nothing is written to state.
        _run(self.engine._execute_node(
            exec_state, graph=_graph_with(fanout), node_id="f1",
            adjacency={"f1": []}, loop_context=None,
        ))
        self.assertEqual(exec_state.state, {}, "FanOut must not write to state (no output_ref)")
        self.assertEqual(len(exec_state.run_log), 1)
        self.assertEqual(exec_state.run_log[0]["status"], "success")


if __name__ == "__main__":
    unittest.main()
