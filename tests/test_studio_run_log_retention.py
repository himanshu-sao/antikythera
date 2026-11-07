"""S9: max_run_logs must be enforced, and graph list metadata must be real.

Defects (verified at HEAD 66340b8):
- ``StudioGraph.max_run_logs`` (default 50, dec #21) was never enforced: run logs
  for a graph accumulated without bound.
- ``StudioGraphManager.list_graphs`` omitted ``undefined_queue_cap``,
  ``max_run_logs`` and ``edge_count``, so the router's listing reported the
  hard-coded defaults (100 / 50 / 0) instead of the graph's real values.

Fix under test:
- after each run log is saved, the oldest logs for that graph beyond
  ``max_run_logs`` are removed (by ``started_at``, then filename). Other graphs'
  logs and the log just written are never pruned.
- list metadata carries the graph's real caps and edge count.
"""
import asyncio
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock

from fastapi.testclient import TestClient

from api import studio_router
from api.execution.studio_graph_engine import PathStepGraphEngine
from api.main import app
from api.managers.run_manager import RunManager
from api.managers.skill_manager import SkillManager
from api.managers.studio_graph_manager import StudioGraphManager
from api.models.studio import GraphEdge, GraphRunLog, StudioGraph
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _log(run_id, graph_id, started):
    return GraphRunLog(run_id=run_id, graph_id=graph_id, started_at=started, status="completed")


class _EngineBase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="studio_runlog_")
        self.graphs = StudioGraphManager(self.base)
        self.engine = PathStepGraphEngine(
            base_dir=self.base,
            operator_registry=OperatorRegistry(vault=Mock(spec=SecretVault)),
            studio_graph_manager=self.graphs,
            skill_manager=SkillManager(self.base),
            run_manager=RunManager(self.base),
        )
        self.t0 = datetime(2026, 1, 1, 12, 0, 0)

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def _saved_run_ids(self, graph_id=None):
        ids = []
        for name in os.listdir(self.engine.runs_dir):
            if not name.endswith(".json"):
                continue
            log = self.engine.get_run_log(name[:-5])
            if log and (graph_id is None or log.graph_id == graph_id):
                ids.append(log.run_id)
        return sorted(ids)


class TestMaxRunLogsRetention(_EngineBase):
    def test_oldest_logs_pruned_beyond_limit(self):
        self.graphs.save_graph(StudioGraph(graph_id="g1", name="g1", max_run_logs=3))
        for i in range(6):
            self.engine._save_run_log(_log(f"r{i}", "g1", self.t0 + timedelta(minutes=i)))
        self.assertEqual(self._saved_run_ids("g1"), ["r3", "r4", "r5"])

    def test_limit_is_per_graph_and_other_graphs_untouched(self):
        self.graphs.save_graph(StudioGraph(graph_id="g1", name="g1", max_run_logs=2))
        self.graphs.save_graph(StudioGraph(graph_id="g2", name="g2", max_run_logs=10))
        for i in range(4):
            self.engine._save_run_log(_log(f"a{i}", "g2", self.t0 + timedelta(minutes=i)))
        for i in range(4):
            self.engine._save_run_log(_log(f"b{i}", "g1", self.t0 + timedelta(minutes=i)))
        self.assertEqual(self._saved_run_ids("g2"), ["a0", "a1", "a2", "a3"])
        self.assertEqual(self._saved_run_ids("g1"), ["b2", "b3"])

    def test_pruning_uses_started_at_not_save_order(self):
        """Pruning picks the oldest by started_at, not the first-saved log.

        The just-saved log is always kept, so when "oldest_saved_last" (saved last,
        but oldest by started_at) arrives, the next-oldest "middle" is pruned.
        """
        self.graphs.save_graph(StudioGraph(graph_id="g1", name="g1", max_run_logs=2))
        self.engine._save_run_log(_log("newest", "g1", self.t0 + timedelta(hours=2)))
        self.engine._save_run_log(_log("middle", "g1", self.t0 + timedelta(hours=1)))
        self.engine._save_run_log(_log("oldest_saved_last", "g1", self.t0))
        self.assertEqual(self._saved_run_ids("g1"), ["newest", "oldest_saved_last"])

    def test_ties_broken_by_filename(self):
        self.graphs.save_graph(StudioGraph(graph_id="g1", name="g1", max_run_logs=1))
        same = self.t0
        self.engine._save_run_log(_log("run_a", "g1", same))
        self.engine._save_run_log(_log("run_b", "g1", same))
        self.assertEqual(self._saved_run_ids("g1"), ["run_b"])

    def test_just_saved_log_is_never_pruned(self):
        self.graphs.save_graph(StudioGraph(graph_id="g1", name="g1", max_run_logs=1))
        self.engine._save_run_log(_log("only_old", "g1", self.t0 + timedelta(hours=5)))
        self.engine._save_run_log(_log("fresh_but_older", "g1", self.t0))
        # The just-saved log is kept even if it sorts oldest; the newer one is pruned.
        self.assertIn("fresh_but_older", self._saved_run_ids("g1"))
        self.assertEqual(len(self._saved_run_ids("g1")), 1)

    def test_under_limit_nothing_pruned(self):
        self.graphs.save_graph(StudioGraph(graph_id="g1", name="g1", max_run_logs=50))
        for i in range(5):
            self.engine._save_run_log(_log(f"r{i}", "g1", self.t0 + timedelta(minutes=i)))
        self.assertEqual(len(self._saved_run_ids("g1")), 5)

    def test_missing_graph_does_not_crash_save(self):
        """No stored graph -> no limit known -> log saved, nothing pruned."""
        self.engine._save_run_log(_log("orphan", "g_missing", self.t0))
        self.assertEqual(self._saved_run_ids("g_missing"), ["orphan"])


class TestGraphListMetadata(_EngineBase):
    def test_list_metadata_reports_real_values(self):
        self.graphs.save_graph(StudioGraph(
            graph_id="g_meta",
            name="meta",
            undefined_queue_cap=7,
            max_run_logs=3,
            nodes=[],
            edges=[GraphEdge(source="a", target="b"), GraphEdge(source="b", target="c")],
        ))
        meta = next(m for m in self.graphs.list_graphs() if m["graph_id"] == "g_meta")
        self.assertEqual(meta["undefined_queue_cap"], 7)
        self.assertEqual(meta["max_run_logs"], 3)
        self.assertEqual(meta["edge_count"], 2)

    def test_router_listing_does_not_report_defaults_for_custom_values(self):
        self._orig_base = studio_router._get_base_dir
        studio_router._get_base_dir = lambda: self.base
        base = self.base
        app.dependency_overrides[studio_router.get_studio_graph_manager] = lambda: StudioGraphManager(base)
        try:
            self.graphs.save_graph(StudioGraph(
                graph_id="g_list",
                name="list",
                undefined_queue_cap=7,
                max_run_logs=3,
                edges=[GraphEdge(source="a", target="b")],
            ))
            body = TestClient(app).get("/api/studio/graphs").json()
            row = next(r for r in body if r["graph_id"] == "g_list")
            self.assertEqual(row["undefined_queue_cap"], 7)
            self.assertEqual(row["max_run_logs"], 3)
            self.assertEqual(row["edge_count"], 1)
        finally:
            app.dependency_overrides.pop(studio_router.get_studio_graph_manager, None)
            studio_router._get_base_dir = self._orig_base


if __name__ == "__main__":
    unittest.main()
