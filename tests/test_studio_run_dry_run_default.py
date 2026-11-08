"""P2-3 — the Studio run endpoint's dry_run default must be True.

Defect (verified at HEAD c58f2e1f): ``RunRequest.dry_run`` defaulted to False,
so an API caller that omitted the flag got a LIVE run — only the UI checkbox
(sending an explicit value) protected against accidental adapter writes.

Fix under test (P2-3):
- omitting ``dry_run`` from POST /graphs/{id}/run starts a DRY run: no
  ``execute_step`` (update_resource) is ever dispatched;
- sending ``"dry_run": false`` explicitly still starts a live run (one
  ``execute_step`` dispatched) — the UI keeps working because it always sends
  an explicit value;
- sending ``"dry_run": true`` explicitly stays dry;
- the response echoes the effective mode;
- the engine-level ``start_run`` default flipped to True as well (any future
  internal caller omitting the flag gets a dry run too).

Preview parity is unchanged (previews were already always dry — pinned by
tests/test_studio_preview_dry_run.py) and is not re-tested here.
"""
import inspect
import shutil
import tempfile
import time
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from api import studio_router
from api.execution.studio_graph_engine import PathStepGraphEngine
from api.main import app
from api.managers.run_manager import RunManager
from api.managers.skill_manager import SkillManager
from api.managers.studio_graph_manager import StudioGraphManager
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault
from api.studio_router import RunRequest


def _cond_node():
    """A conditional whose true branch would fire a live adapter write."""
    return {
        "node_id": "c1",
        "name": "c1",
        "archetype": "conditional_action",
        "routing_strategy": "condition_first",
        "condition": {"type": "equals", "field": "ticket.status", "value": "Critical"},
        "true_action": "jira_adapter",
        "true_action_config": {"transition": "Investigating"},
        "true_output_ref": "moved_id",
        "false_action": None,
        "false_action_config": {},
        "false_output_ref": None,
    }


_MATCHING_INPUTS = {"ticket": {"status": "Critical", "id": "TKT-1"}}


class _RouterBase(unittest.TestCase):
    """TestClient against the real app, with the studio deps pointed at a
    temp dir and the engine's execute_step spied (any call == live write)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="studio_dry_default_")

        vault = Mock(spec=SecretVault)
        vault.get_secret.return_value = {"access_token": "fake_token"}
        self.registry = OperatorRegistry(vault=vault)
        self.execute_calls = []

        async def fake_execute_step(step_config, state):
            self.execute_calls.append(step_config)
            return {"ok": True, "result_data": "LIVE-1"}

        self.registry.execute_step = fake_execute_step

        self.engine = PathStepGraphEngine(
            base_dir=self.tmp,
            operator_registry=self.registry,
            studio_graph_manager=StudioGraphManager(self.tmp),
            skill_manager=SkillManager(self.tmp),
            run_manager=RunManager(self.tmp),
        )

        # Point the router's module-level helpers at the temp dir...
        self._orig_base = studio_router._get_base_dir
        self._orig_graph_mgr = studio_router.get_studio_graph_manager
        studio_router._get_base_dir = lambda: self.tmp
        studio_router.get_studio_graph_manager = lambda: self.engine.studio_graph_manager
        # ...and swap the engine dependency for our spied engine.
        app.dependency_overrides[studio_router.get_graph_engine] = lambda: self.engine
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(studio_router.get_graph_engine, None)
        studio_router._get_base_dir = self._orig_base
        studio_router.get_studio_graph_manager = self._orig_graph_mgr
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_graph(self):
        r = self.client.post(
            "/api/studio/graphs",
            json={"name": "dry default graph", "nodes": [_cond_node()], "edges": []},
        )
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["graph_id"]

    def _run_and_wait(self, gid, body):
        """POST a run, wait for it to finalize, return the response JSON."""
        r = self.client.post(f"/api/studio/graphs/{gid}/run", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        run = r.json()
        run_id = run["run_id"]
        for _ in range(50):  # up to 5s, like test_studio_router_endpoints
            logs = self.client.get(f"/api/studio/graphs/{gid}/runs").json()
            if logs and logs[0]["run_id"] == run_id and logs[0]["status"] in (
                "completed",
                "partial",
                "failed",
            ):
                return run
            time.sleep(0.1)
        self.fail(f"run {run_id} did not finalize within 5s")
        return run


class TestRunRequestDefault(unittest.TestCase):
    """Model-level pin of the P2-3 default."""

    def test_request_defaults_to_dry_run(self):
        self.assertTrue(RunRequest().dry_run, "RunRequest.dry_run must default True (P2-3)")
        self.assertTrue(RunRequest(inputs={"a": 1}).dry_run)

    def test_explicit_false_is_honored(self):
        self.assertFalse(RunRequest(inputs={}, dry_run=False).dry_run)

    def test_engine_start_run_defaults_to_dry_run(self):
        """Consistency (P2-3): the engine-level entry point defaults dry too,
        so a future internal caller that omits the flag cannot start a live run."""
        param = inspect.signature(PathStepGraphEngine.start_run).parameters["dry_run"]
        self.assertIs(param.default, True, "start_run's dry_run default must be True (P2-3)")


class TestRouterDryRunDefault(_RouterBase):
    def test_omitting_the_flag_runs_dry_no_live_writes(self):
        """A caller that omits dry_run must get a dry run: the matched true
        branch never dispatches execute_step, and the response says dry."""
        gid = self._create_graph()
        run = self._run_and_wait(gid, {"inputs": _MATCHING_INPUTS})

        self.assertTrue(run["dry_run"], "response must report dry_run=true when the flag was omitted")
        self.assertEqual(
            self.execute_calls,
            [],
            "omitting dry_run must not dispatch any live adapter write",
        )

    def test_explicit_false_runs_live(self):
        """Sending dry_run=false explicitly still performs the live write —
        the UI (which always sends an explicit value) keeps working."""
        gid = self._create_graph()
        run = self._run_and_wait(gid, {"inputs": _MATCHING_INPUTS, "dry_run": False})

        self.assertFalse(run["dry_run"])
        self.assertEqual(len(self.execute_calls), 1, "explicit dry_run=false must dispatch the live write")
        self.assertEqual(self.execute_calls[0]["operator_id"], "update_resource")
        self.assertEqual(self.execute_calls[0]["adapter_id"], "jira_adapter")

    def test_explicit_true_stays_dry(self):
        """Sending dry_run=true explicitly behaves exactly like the default."""
        gid = self._create_graph()
        run = self._run_and_wait(gid, {"inputs": _MATCHING_INPUTS, "dry_run": True})

        self.assertTrue(run["dry_run"])
        self.assertEqual(self.execute_calls, [], "explicit dry_run=true must not dispatch a live write")


if __name__ == "__main__":
    unittest.main()
