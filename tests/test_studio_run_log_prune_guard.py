"""R25: _prune_run_logs must not parse logs it does not need, and must not crash
on mixed naive/aware timestamps.

Defects (reported, verified by reading the code):
- every save parsed every run log in the runs dir, even when the directory
  could not exceed max_run_logs;
- the sort compared naive and aware datetimes and sat outside any try, so one
  odd timestamp aborted the save path.

Fix under test:
- the directory file count is checked first; logs are parsed only when the
  count is above the limit;
- ordering normalises to UTC (naive treated as UTC) and falls back to the file
  mtime when started_at cannot be used; the sort key never raises.
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.managers.run_manager import RunManager
from api.managers.skill_manager import SkillManager
from api.managers.studio_graph_manager import StudioGraphManager
from api.models.studio import GraphRunLog, StudioGraph
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _log(run_id, graph_id, started):
    return GraphRunLog(run_id=run_id, graph_id=graph_id, started_at=started, status="completed")


class _Base(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="studio_prune_guard_")
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

    def _ids(self, graph_id):
        out = []
        for name in os.listdir(self.engine.runs_dir):
            if name.endswith(".json"):
                log = self.engine.get_run_log(name[:-5])
                if log and log.graph_id == graph_id:
                    out.append(log.run_id)
        return sorted(out)


class TestCountFirst(_Base):
    def test_no_log_parsed_when_directory_within_limit(self):
        self.graphs.save_graph(StudioGraph(graph_id="g1", name="g1", max_run_logs=10))
        for i in range(3):
            self.engine._save_run_log(_log(f"r{i}", "g1", self.t0 + timedelta(minutes=i)))
        with patch.object(self.engine, "get_run_log", wraps=self.engine.get_run_log) as spy:
            self.engine._prune_run_logs("g1")
        self.assertEqual(spy.call_count, 0, "no run log may be parsed while within the limit")

    def test_logs_parsed_only_once_count_exceeds_limit(self):
        self.graphs.save_graph(StudioGraph(graph_id="g1", name="g1", max_run_logs=2))
        for i in range(2):
            self.engine._save_run_log(_log(f"r{i}", "g1", self.t0 + timedelta(minutes=i)))
        # Third file pushes the directory above the limit.
        self.engine._save_run_log(_log("r2", "g1", self.t0 + timedelta(minutes=2)))
        self.assertEqual(self._ids("g1"), ["r1", "r2"])

    def test_file_count_check_skips_other_files_too(self):
        self.graphs.save_graph(StudioGraph(graph_id="g1", name="g1", max_run_logs=5))
        with patch.object(self.engine, "get_run_log") as spy:
            self.engine._prune_run_logs("g1")
        spy.assert_not_called()

    def test_missing_graph_definition_parses_nothing(self):
        with patch.object(self.engine, "get_run_log") as spy:
            self.engine._prune_run_logs("no_such_graph")
        spy.assert_not_called()


class TestTimestampOrdering(_Base):
    def test_mixed_naive_and_aware_timestamps_do_not_raise_and_order_in_utc(self):
        self.graphs.save_graph(StudioGraph(graph_id="g1", name="g1", max_run_logs=2))
        # 10:00 UTC (aware, written as 12:00+02:00): the oldest.
        aware_old = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
        # 11:00 UTC naive: newer than the aware-old one.
        naive_mid = datetime(2026, 1, 1, 11, 0, 0)
        # 12:00 UTC naive: newest.
        naive_new = datetime(2026, 1, 1, 12, 0, 0)
        self.engine._save_run_log(_log("old_aware", "g1", aware_old))
        self.engine._save_run_log(_log("mid_naive", "g1", naive_mid))
        self.engine._save_run_log(_log("new_naive", "g1", naive_new))
        self.assertEqual(self._ids("g1"), ["mid_naive", "new_naive"])

    def test_sort_key_normalises_aware_to_utc(self):
        log = _log("r", "g1", datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=2))))
        key = self.engine._run_log_sort_key(log, "r.json")
        expected = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp()
        self.assertEqual(key, expected)

    def test_sort_key_treats_naive_as_utc(self):
        log = _log("r", "g1", datetime(2026, 1, 1, 10, 0, 0))
        expected = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp()
        self.assertEqual(self.engine._run_log_sort_key(log, "r.json"), expected)

    def test_sort_key_falls_back_to_mtime_when_started_at_unusable(self):
        path = os.path.join(self.engine.runs_dir, "odd.json")
        with open(path, "w") as f:
            f.write("{}")
        os.utime(path, (1_700_000_000, 1_700_000_000))
        broken = Mock()
        broken.started_at = None  # not a datetime: cannot be normalised
        self.assertEqual(self.engine._run_log_sort_key(broken, "odd.json"), 1_700_000_000.0)

    def test_sort_key_never_raises_when_file_missing(self):
        broken = Mock()
        broken.started_at = None
        self.assertEqual(self.engine._run_log_sort_key(broken, "missing.json"), 0.0)

    def test_prune_survives_one_unusable_log(self):
        self.graphs.save_graph(StudioGraph(graph_id="g1", name="g1", max_run_logs=1))
        self.engine._save_run_log(_log("a", "g1", self.t0))
        real_get = self.engine.get_run_log

        def flaky(run_id):
            log = real_get(run_id)
            if run_id == "a" and log is not None:
                log.started_at = None  # simulate an unusable timestamp
            return log

        with patch.object(self.engine, "get_run_log", side_effect=flaky):
            self.engine._save_run_log(_log("b", "g1", self.t0 + timedelta(minutes=1)))
        self.assertIn("b", self._ids("g1"), "the log just written must survive")


if __name__ == "__main__":
    unittest.main()
