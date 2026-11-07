"""S8: get_undefined_queue must honour the graph's undefined_queue_cap.

Defect (verified at HEAD 66340b8): ``PathStepGraphEngine.get_undefined_queue``
returned ``logs[0].undefined_items[:100]``. The per-graph cap
(``StudioGraph.undefined_queue_cap``, dec #20) was ignored: a graph with cap 5
still returned 100 items, and a graph with cap 150 was clipped to 100.

Fix under test: the read path clips to the graph's own cap. Cross-run
retention (whether the queue should accumulate over runs) is intentionally
unchanged here and is reported as a needs-decision item.

Driven with the real engine and a real StudioGraphManager on a temp dir. No
network, no adapters.
"""
import asyncio
import shutil
import tempfile
import unittest
from unittest.mock import Mock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.managers.studio_graph_manager import StudioGraphManager
from api.managers.skill_manager import SkillManager
from api.managers.run_manager import RunManager
from api.models.studio import (
    Condition,
    ConditionalActionNode,
    ConditionType,
    ExecutionState,
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


def _unmatched_node():
    # Unmatched (state has status WIP, condition wants New) and no false_action
    # -> every drive lands in the undefined queue (dec #11).
    return ConditionalActionNode(
        node_id="c1",
        name="c1",
        archetype=NodeArchetype.CONDITIONAL_ACTION,
        routing_strategy=RoutingStrategy.CONDITION_FIRST,
        condition=Condition(type=ConditionType.EQUALS, field="ticket.status", value="New"),
        true_action=None,
        true_action_config={},
        true_output_ref=None,
        false_action=None,
        false_action_config={},
        false_output_ref=None,
    )


class TestUndefinedQueueCap(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="studio_uq_cap_")
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

    def _seed_run(self, graph_id, drives, cap):
        """Persist a graph with ``cap`` and one finalized run with ``drives``
        undefined items."""
        graph = StudioGraph(
            graph_id=graph_id,
            name=graph_id,
            nodes=[_unmatched_node()],
            edges=[],
            undefined_queue_cap=cap,
        )
        self.graphs.save_graph(graph)
        es = ExecutionState(
            graph_id=graph_id, run_id=f"run_{graph_id}", state={"ticket": {"status": "WIP"}},
            run_log=[], undefined_queue=[], loop_stack=[], dry_run=True,
        )
        for _ in range(drives):
            _run(self.engine._execute_node(es, graph, "c1", {"c1": []}, None))
        _run(self.engine._finalize_run(es, graph, "completed"))
        return graph

    def test_small_graph_cap_clips_read(self):
        self._seed_run("g_small", drives=8, cap=5)
        items = self.engine.get_undefined_queue("g_small")
        self.assertEqual(len(items), 5)

    def test_queue_under_cap_returns_everything(self):
        self._seed_run("g_under", drives=3, cap=10)
        self.assertEqual(len(self.engine.get_undefined_queue("g_under")), 3)

    def test_default_cap_is_100(self):
        self._seed_run("g_default", drives=120, cap=100)
        self.assertEqual(len(self.engine.get_undefined_queue("g_default")), 100)

    def test_cap_above_100_is_not_clipped_to_100(self):
        """The hard-coded [:100] used to clip a graph whose cap is 150."""
        self._seed_run("g_big", drives=120, cap=150)
        items = self.engine.get_undefined_queue("g_big")
        self.assertEqual(len(items), 120, "read must honour the graph cap, not a constant")

    def test_unknown_graph_still_returns_items_from_latest_run(self):
        """Without a stored graph there is no cap to read; behaviour falls back to
        the default (100) rather than raising."""
        graph = self._seed_run("g_gone", drives=4, cap=5)
        self.graphs.delete_graph("g_gone")
        items = self.engine.get_undefined_queue("g_gone")
        self.assertEqual(len(items), 4)
        self.assertLessEqual(len(items), 100)

    def test_no_runs_returns_empty(self):
        self.graphs.save_graph(StudioGraph(graph_id="g_none", name="g", undefined_queue_cap=5))
        self.assertEqual(self.engine.get_undefined_queue("g_none"), [])


if __name__ == "__main__":
    unittest.main()
