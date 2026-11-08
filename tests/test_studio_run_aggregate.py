"""P2-4 — the perpetual per-graph run aggregate (Studio plan decision #21).

Defect (verified at HEAD c58f2e1f): only comments mentioned a "perpetual
aggregate"; nothing was stored or served. A graph's history vanished with
run-log pruning (``max_run_logs``, default 50) and the detail response had no
totals.

Fix under test:
- ``_finalize_run`` folds every finalized run into
  ``studio_runs/<graph_id>.aggregate.json`` (atomic write): total_runs,
  total_matched, total_undefined, total_escalated, counts by status
  (completed/partial/failed), last_run_id and last_run_at;
- the aggregate survives run-log pruning and is never pruned itself (the
  pruner and list_run_logs skip ``*.aggregate.json`` by name);
- a corrupt aggregate is quarantined (``<file>.corrupt-<stamp>``, original
  content preserved) and REBUILT from the surviving run logs — the documented
  policy — so the data is recovered, never silently reset to zero, and the
  rebuild is stamped ``recovered_at``;
- GET /api/studio/graphs/{id} carries the aggregate (None when never run).
"""
import asyncio
import glob
import os
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime
from unittest.mock import Mock

from fastapi.testclient import TestClient

from api import studio_router
from api.execution.studio_graph_engine import (
    AGGREGATE_SUFFIX,
    GraphRunAggregate,
    PathStepGraphEngine,
)
from api.main import app
from api.managers.run_manager import RunManager
from api.managers.skill_manager import SkillManager
from api.managers.studio_graph_manager import StudioGraphManager
from api.models.studio import (
    ConditionalActionNode,
    Condition,
    ConditionType,
    ExecutionState,
    GraphRunLog,
    NodeArchetype,
    RoutingStrategy,
    StudioGraph,
)
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _cond_node(node_id="c1"):
    return ConditionalActionNode(
        node_id=node_id,
        name=node_id,
        archetype=NodeArchetype.CONDITIONAL_ACTION,
        routing_strategy=RoutingStrategy.CONDITION_FIRST,
        condition=Condition(type=ConditionType.EQUALS, field="ticket.status", value="Critical"),
        true_action="jira_adapter",
        true_action_config={"transition": "escalate"},
        true_output_ref="escalated_id",
        false_action=None,
        false_action_config={},
        false_output_ref=None,
    )


class _EngineBase(unittest.TestCase):
    """Engine on a temp dir with REAL managers (pruning needs the stored graph)."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="studio_aggregate_")
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

    def _save_graph(self, graph_id, **kwargs):
        graph = StudioGraph(graph_id=graph_id, name=graph_id, nodes=[_cond_node()], **kwargs)
        self.graphs.save_graph(graph)
        return graph

    def _run(self, graph, inputs, dry_run=True):
        """Run a graph to completion by awaiting _execute_graph directly
        (test_studio_run_path pattern: no background task, deterministic)."""
        run_id = f"studio_run_{uuid.uuid4().hex[:12]}"
        exec_state = ExecutionState(
            graph_id=graph.graph_id,
            run_id=run_id,
            state=dict(inputs),
            run_log=[],
            undefined_queue=[],
            loop_stack=[],
            dry_run=dry_run,
        )
        self.engine._save_run_log(GraphRunLog(
            run_id=run_id, graph_id=graph.graph_id,
            started_at=datetime.utcnow(), status="running",
        ))
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.engine._execute_graph(exec_state, graph))
        finally:
            loop.close()
        return run_id

    def _aggregate_path(self, graph_id):
        return os.path.join(self.engine.runs_dir, f"{graph_id}{AGGREGATE_SUFFIX}")

    def _run_log_files(self):
        return [
            n for n in os.listdir(self.engine.runs_dir)
            if n.endswith(".json") and not n.endswith(AGGREGATE_SUFFIX)
        ]


class TestAggregateAccumulation(_EngineBase):
    def test_totals_accumulate_across_runs(self):
        graph = self._save_graph("g_acc")
        r1 = self._run(graph, {"ticket": {"status": "Critical"}})
        r2 = self._run(graph, {"ticket": {"status": "Low"}})  # unmatched -> undefined

        agg = self.engine.get_aggregate("g_acc")
        self.assertIsNotNone(agg)
        self.assertEqual(agg.graph_id, "g_acc")
        self.assertEqual(agg.total_runs, 2)
        # total_matched counts an EVALUATED branch (test_studio_run_path pins
        # this): the true branch of run 1 and the evaluated false branch of
        # run 2 both count; run 2's unmatched item also queues as undefined.
        self.assertEqual(agg.total_matched, 2, "one evaluated branch per run")
        self.assertEqual(agg.total_undefined, 1, "run 2 unmatched with no false action")
        self.assertEqual(agg.total_escalated, 0)
        self.assertEqual(agg.status_counts, {"completed": 2, "partial": 0, "failed": 0})
        self.assertEqual(agg.last_run_id, r2, "last_run_id is the most recent run")
        self.assertEqual(agg.last_run_at, self.engine.get_run_log(r2).started_at)

        # The file is on disk next to the run logs, with the documented name.
        self.assertTrue(os.path.exists(self._aggregate_path("g_acc")))

    def test_status_counts_by_status(self):
        """Unit-level roll-up of the per-status counters via _update_aggregate."""
        for status in ("completed", "partial", "failed", "completed"):
            log = GraphRunLog(
                run_id=f"r_{status}_{uuid.uuid4().hex[:4]}",
                graph_id="g_status",
                started_at=datetime.utcnow(),
                status=status,
                total_matched=1,
            )
            self.engine._update_aggregate("g_status", log)
        agg = self.engine.get_aggregate("g_status")
        self.assertEqual(agg.total_runs, 4)
        self.assertEqual(agg.status_counts, {"completed": 2, "partial": 1, "failed": 1})

    def test_never_run_graph_has_no_aggregate(self):
        self._save_graph("g_never")
        self.assertIsNone(self.engine.get_aggregate("g_never"))
        self.assertFalse(os.path.exists(self._aggregate_path("g_never")))

    def test_other_graphs_aggregates_are_independent(self):
        g1 = self._save_graph("g_one")
        g2 = self._save_graph("g_two")
        self._run(g1, {"ticket": {"status": "Critical"}})
        self._run(g1, {"ticket": {"status": "Critical"}})
        self._run(g2, {"ticket": {"status": "Critical"}})
        self.assertEqual(self.engine.get_aggregate("g_one").total_runs, 2)
        self.assertEqual(self.engine.get_aggregate("g_two").total_runs, 1)


class TestAggregateSurvivesPruning(_EngineBase):
    def test_aggregate_survives_pruning_beyond_max_run_logs(self):
        graph = self._save_graph("g_prune", max_run_logs=2)
        run_ids = [self._run(graph, {"ticket": {"status": "Critical"}}) for _ in range(4)]

        # Pruning did its job: only the newest 2 run logs remain on disk...
        self.assertEqual(len(self._run_log_files()), 2)
        logs = self.engine.list_run_logs("g_prune")
        self.assertEqual(sorted(l.run_id for l in logs), sorted(run_ids[2:]))
        # ...the aggregate is NOT a run log and was never pruned...
        self.assertTrue(os.path.exists(self._aggregate_path("g_prune")))
        # ...and the totals remember all 4 runs.
        agg = self.engine.get_aggregate("g_prune")
        self.assertEqual(agg.total_runs, 4, "total_runs must count pruned runs too")
        self.assertEqual(agg.total_matched, 4)
        self.assertEqual(agg.status_counts["completed"], 4)
        self.assertEqual(agg.last_run_id, run_ids[3])

    def test_list_run_logs_never_returns_the_aggregate(self):
        graph = self._save_graph("g_list")
        self._run(graph, {"ticket": {"status": "Critical"}})
        # Even if the aggregate file were handed to the walker, it must not
        # appear as a run log.
        names = os.listdir(self.engine.runs_dir)
        self.assertIn(f"g_list{AGGREGATE_SUFFIX}", names)
        logs = self.engine.list_run_logs("g_list")
        self.assertEqual([l.run_id for l in logs], [l.run_id for l in logs])
        self.assertTrue(all(not l.run_id.endswith("aggregate") for l in logs))
        self.assertEqual(len(logs), 1)


class TestCorruptAggregate(_EngineBase):
    def test_corrupt_aggregate_is_quarantined_and_rebuilt_not_silently_zeroed(self):
        graph = self._save_graph("g_corrupt")
        self._run(graph, {"ticket": {"status": "Critical"}})
        self._run(graph, {"ticket": {"status": "Critical"}})
        self.assertEqual(self.engine.get_aggregate("g_corrupt").total_runs, 2)

        # Corrupt the aggregate on disk.
        path = self._aggregate_path("g_corrupt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{broken")

        # One more run: the write path must quarantine + rebuild + count this run.
        r3 = self._run(graph, {"ticket": {"status": "Critical"}})

        agg = self.engine.get_aggregate("g_corrupt")
        self.assertIsNotNone(agg)
        self.assertEqual(agg.total_runs, 3, "rebuilt from the 2 surviving logs + this run")
        self.assertEqual(agg.total_matched, 3)
        self.assertIsNotNone(agg.recovered_at, "the rebuild must be stamped recovered_at")

        # The corrupt original was quarantined, not deleted, and not overwritten.
        quarantined = glob.glob(path + ".corrupt-*")
        self.assertEqual(len(quarantined), 1, "exactly one quarantine copy")
        with open(quarantined[0], "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "{broken", "quarantine must preserve the corrupt content")

        # The live file is valid JSON again.
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
        self.assertIn('"total_runs": 3', data)
        self.assertEqual(agg.last_run_id, r3)

    def test_read_path_also_recovers_a_corrupt_aggregate(self):
        """get_aggregate (the detail response's read path) repairs a corrupt
        aggregate instead of reporting zeros — even before the next run."""
        graph = self._save_graph("g_read")
        self._run(graph, {"ticket": {"status": "Critical"}})
        self._run(graph, {"ticket": {"status": "Critical"}})

        path = self._aggregate_path("g_read")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not json at all")

        agg = self.engine.get_aggregate("g_read")
        self.assertEqual(agg.total_runs, 2, "recovered from the surviving run logs")
        self.assertIsNotNone(agg.recovered_at)
        self.assertTrue(glob.glob(path + ".corrupt-*"), "quarantine copy kept")
        # The recovery is persisted (the on-disk file is valid again).
        agg2 = self.engine.get_aggregate("g_read")
        self.assertEqual(agg2.total_runs, 2)

    def test_aggregate_with_wrong_graph_id_is_treated_as_corrupt(self):
        graph = self._save_graph("g_mismatch")
        self._run(graph, {"ticket": {"status": "Critical"}})
        path = self._aggregate_path("g_mismatch")
        with open(path, "w", encoding="utf-8") as f:
            import json as _json
            _json.dump(GraphRunAggregate(graph_id="somebody_else", total_runs=99).model_dump(mode="json"), f)

        agg = self.engine.get_aggregate("g_mismatch")
        self.assertEqual(agg.graph_id, "g_mismatch")
        self.assertEqual(agg.total_runs, 1, "rebuilt from this graph's logs, not the mismatched file")
        self.assertIsNotNone(agg.recovered_at)


class TestRouterDetailAggregate(unittest.TestCase):
    """GET /api/studio/graphs/{id} carries the aggregate (P2-4)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="studio_agg_router_")
        self.graphs = StudioGraphManager(self.tmp)
        self.engine = PathStepGraphEngine(
            base_dir=self.tmp,
            operator_registry=OperatorRegistry(vault=Mock(spec=SecretVault)),
            studio_graph_manager=self.graphs,
            skill_manager=SkillManager(self.tmp),
            run_manager=RunManager(self.tmp),
        )
        self._orig_base = studio_router._get_base_dir
        self._orig_gm = studio_router.get_studio_graph_manager
        studio_router._get_base_dir = lambda: self.tmp
        studio_router.get_studio_graph_manager = lambda: self.graphs
        app.dependency_overrides[studio_router.get_studio_graph_manager] = lambda: self.graphs
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(studio_router.get_studio_graph_manager, None)
        studio_router._get_base_dir = self._orig_base
        studio_router.get_studio_graph_manager = self._orig_gm
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_detail_response_carries_the_aggregate(self):
        graph = StudioGraph(graph_id="g_detail", name="detail", nodes=[_cond_node()])
        self.graphs.save_graph(graph)

        # Never run: aggregate is null.
        r = self.client.get("/api/studio/graphs/g_detail")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(r.json()["aggregate"])

        # One dry run through the engine (same base dir the router reads).
        run_id = f"studio_run_{uuid.uuid4().hex[:12]}"
        exec_state = ExecutionState(
            graph_id="g_detail", run_id=run_id,
            state={"ticket": {"status": "Critical"}},
            run_log=[], undefined_queue=[], loop_stack=[], dry_run=True,
        )
        self.engine._save_run_log(GraphRunLog(
            run_id=run_id, graph_id="g_detail",
            started_at=datetime.utcnow(), status="running",
        ))
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.engine._execute_graph(exec_state, graph))
        finally:
            loop.close()

        r = self.client.get("/api/studio/graphs/g_detail")
        self.assertEqual(r.status_code, 200, r.text)
        agg = r.json()["aggregate"]
        self.assertIsNotNone(agg)
        self.assertEqual(agg["graph_id"], "g_detail")
        self.assertEqual(agg["total_runs"], 1)
        self.assertEqual(agg["total_matched"], 1)
        self.assertEqual(agg["status_counts"], {"completed": 1, "partial": 0, "failed": 0})
        self.assertEqual(agg["last_run_id"], run_id)
        self.assertIn("last_run_at", agg)

    def test_detail_response_of_unknown_graph_still_404(self):
        r = self.client.get("/api/studio/graphs/does_not_exist")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
