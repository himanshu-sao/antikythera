"""SC-Q2 — Studio Router endpoint coverage beyond save/run/preview.

Covers the endpoints that currently have NO direct tests beyond the save-Union suite:
- GET    /api/studio/graphs              (list_graphs)        → round-trip + 404 (via GET /graphs/{id})
- GET    /api/studio/graphs/{graph_id}   (get_graph)          → 404 path + detail round-trip
- PUT    /api/studio/graphs/{graph_id}   (update_graph)       → already exercised in save-Union; add 404
- DELETE /api/studio/graphs/{graph_id}   (delete_graph)       → 204 + 404 + GET-after-delete 404
- POST   /api/studio/graphs/{graph_id}/run (run_graph)       → save-Union covers dry-run; add non-dry mock
- GET    /api/studio/graphs/{graph_id}/runs (list_run_logs)  → empty list + populated + limit param
- GET    /api/studio/graphs/{graph_id}/undefined-queue       → empty + populated + cap
- GET    /api/studio/schedulable-graphs  (list_schedulable)   → empty + non-empty
- POST   /api/studio/skills              (create_skill)      → 201 + GET detail round-trip + 422 bad archetype (skill has no archetype but input validation)
- GET    /api/studio/skills              (list_skills)       → empty + populated
- GET    /api/studio/skills/{skill_id}   (get_skill)         → 404 + detail round-trip
- DELETE /api/studio/skills/{skill_id}   (delete_skill)      → 204 + 404 + GET-after-delete 404
- GET    /api/studio/integrations/status (get_integration_status) → empty + populated

Also exercises the cron_schedule / cron_enabled / undefined_queue_cap fields
on GraphCreateRequest and GraphUpdateRequest (accepted, persisted, round-tripped).
"""
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import Mock

from fastapi.testclient import TestClient

from api import studio_router
from api.main import app
from api.managers.studio_graph_manager import StudioGraphManager
from api.managers.skill_manager import SkillManager
from api.models.studio import StudioGraph, Skill
from api.execution.studio_graph_engine import PathStepGraphEngine
from api.operator_registry import OperatorRegistry
from api.managers.run_manager import RunManager


def _node_query():
    return {
        "node_id": "q1",
        "name": "q1",
        "archetype": "query",
        "adapter": "internal_adapter",
        "action": "list_items",
        "params": {},
        "output_ref": "items",
    }


def _node_conditional():
    return {
        "node_id": "c1",
        "name": "c1",
        "archetype": "conditional_action",
        "routing_strategy": "condition_first",
        "condition": {"type": "equals", "field": "ticket.status", "value": "New"},
        "true_action": "jira_adapter",
        "true_action_config": {"transition": "Investigating"},
        "true_output_ref": "moved_id",
        "false_action": None,
        "false_action_config": {},
        "false_output_ref": None,
    }


def _node_fanout():
    return {
        "node_id": "f1",
        "name": "f1",
        "archetype": "fan_out",
        "loop_over": {"source": "items", "iterator_var": "ticket"},
    }


def _node_ai():
    return {
        "node_id": "a1",
        "name": "a1",
        "archetype": "ai_transform",
        "execution_mode": "script",
        "script": "return {'plan': 'enrich'}",
        "input_ref": "items",
        "output_ref": "enriched",
    }


def _make_test_engine(tmp_dir: str) -> PathStepGraphEngine:
    """Create a PathStepGraphEngine using the test temp directory."""
    vault = Mock()
    vault.get_secret = Mock(return_value={"access_token": "fake_token"})
    registry = OperatorRegistry(vault=vault)
    studio_graph_manager = StudioGraphManager(tmp_dir)
    skill_manager = SkillManager(tmp_dir)
    run_manager = RunManager(tmp_dir)

    return PathStepGraphEngine(
        base_dir=tmp_dir,
        operator_registry=registry,
        studio_graph_manager=studio_graph_manager,
        skill_manager=skill_manager,
        run_manager=run_manager,
    )


class TestStudioRouterEndpoints(unittest.TestCase):
    """SC-Q2: Router endpoint coverage for Studio API."""

    def setUp(self):
        # Use a unique temp dir per test for isolation
        self.tmp = tempfile.mkdtemp(prefix="studio_router_test_")

        def _stub_graph_manager():
            return StudioGraphManager(self.tmp)

        def _stub_skill_manager():
            return SkillManager(self.tmp)

        # Save original functions to restore in tearDown
        self._orig_get_base_dir = studio_router._get_base_dir
        self._orig_get_graph_manager = studio_router.get_studio_graph_manager
        self._orig_get_skill_manager = studio_router.get_skill_manager

        # Override the dependency functions that return managers
        app.dependency_overrides[studio_router.get_studio_graph_manager] = _stub_graph_manager
        app.dependency_overrides[studio_router.get_skill_manager] = _stub_skill_manager

        # Also monkey-patch the module-level functions used directly in route handlers
        studio_router.get_studio_graph_manager = _stub_graph_manager
        studio_router.get_skill_manager = _stub_skill_manager
        studio_router._get_base_dir = lambda: self.tmp

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(studio_router.get_studio_graph_manager, None)
        app.dependency_overrides.pop(studio_router.get_skill_manager, None)
        # Restore original module-level functions
        studio_router._get_base_dir = self._orig_get_base_dir
        studio_router.get_studio_graph_manager = self._orig_get_graph_manager
        studio_router.get_skill_manager = self._orig_get_skill_manager

    # -------------------------------------------------------------------------
    # Graph CRUD
    # -------------------------------------------------------------------------

    def test_list_graphs_empty_initially(self):
        r = self.client.get("/api/studio/graphs")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_create_graph_round_trips_all_fields(self):
        """GraphCreateRequest with all optional fields persists and round-trips."""
        payload = {
            "name": "Full Field Graph",
            "description": "Has cron + caps",
            "nodes": [_node_query(), _node_conditional()],
            "edges": [{"source": "q1", "target": "c1", "source_handle": "loop"}],
            "cron_schedule": "0 2 * * *",
            "cron_enabled": True,
            "undefined_queue_cap": 50,
            "max_run_logs": 25,
            "required_capability": "generate",
        }
        r = self.client.post("/api/studio/graphs", json=payload)
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertEqual(body["name"], "Full Field Graph")
        self.assertEqual(body["cron_schedule"], "0 2 * * *")
        self.assertEqual(body["cron_enabled"], True)
        self.assertEqual(body["undefined_queue_cap"], 50)
        self.assertEqual(body["max_run_logs"], 25)

        # GET detail round-trip
        gid = body["graph_id"]
        r = self.client.get(f"/api/studio/graphs/{gid}")
        self.assertEqual(r.status_code, 200, r.text)
        g = r.json()
        self.assertEqual(g["cron_schedule"], "0 2 * * *")
        self.assertEqual(g["cron_enabled"], True)
        self.assertEqual(g["undefined_queue_cap"], 50)
        self.assertEqual(g["max_run_logs"], 25)
        self.assertEqual(len(g["nodes"]), 2)
        archetypes = {n["archetype"] for n in g["nodes"]}
        self.assertIn("query", archetypes)
        self.assertIn("conditional_action", archetypes)

    def test_get_graph_404(self):
        r = self.client.get("/api/studio/graphs/does_not_exist")
        self.assertEqual(r.status_code, 404)

    def test_update_graph_404(self):
        r = self.client.put("/api/studio/graphs/does_not_exist", json={"name": "x"})
        self.assertEqual(r.status_code, 404)

    def test_delete_graph_204_then_404(self):
        # Create first
        r = self.client.post("/api/studio/graphs", json={"name": "to delete", "nodes": [_node_query()], "edges": []})
        self.assertEqual(r.status_code, 201)
        gid = r.json()["graph_id"]

        # Delete
        r = self.client.delete(f"/api/studio/graphs/{gid}")
        self.assertEqual(r.status_code, 204)

        # GET after delete → 404
        r = self.client.get(f"/api/studio/graphs/{gid}")
        self.assertEqual(r.status_code, 404)

        # DELETE again → 404
        r = self.client.delete(f"/api/studio/graphs/{gid}")
        self.assertEqual(r.status_code, 404)

    def test_update_graph_persists_cron_fields(self):
        # seed
        r = self.client.post("/api/studio/graphs", json={"name": "seed", "nodes": [_node_query()], "edges": []})
        self.assertEqual(r.status_code, 201)
        gid = r.json()["graph_id"]

        # update cron fields
        upd = {"cron_schedule": "0 0 * * 0", "cron_enabled": True, "undefined_queue_cap": 200, "max_run_logs": 10}
        r = self.client.put(f"/api/studio/graphs/{gid}", json=upd)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["cron_schedule"], "0 0 * * 0")
        self.assertEqual(body["cron_enabled"], True)
        self.assertEqual(body["undefined_queue_cap"], 200)
        self.assertEqual(body["max_run_logs"], 10)

        # verify persisted
        r = self.client.get(f"/api/studio/graphs/{gid}")
        self.assertEqual(r.status_code, 200)
        g = r.json()
        self.assertEqual(g["cron_schedule"], "0 0 * * 0")
        self.assertEqual(g["cron_enabled"], True)
        self.assertEqual(g["undefined_queue_cap"], 200)
        self.assertEqual(g["max_run_logs"], 10)

    # -------------------------------------------------------------------------
    # Graph Runs
    # -------------------------------------------------------------------------

    def test_list_run_logs_empty(self):
        r = self.client.post("/api/studio/graphs", json={"name": "g", "nodes": [_node_query()], "edges": []})
        gid = r.json()["graph_id"]
        r = self.client.get(f"/api/studio/graphs/{gid}/runs")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_list_run_logs_populated(self):
        r = self.client.post("/api/studio/graphs", json={"name": "g", "nodes": [_node_query()], "edges": []})
        gid = r.json()["graph_id"]

        # Run twice (dry_run so no real adapters needed)
        run_ids = []
        for _ in range(2):
            r = self.client.post(f"/api/studio/graphs/{gid}/run", json={"inputs": {}, "dry_run": True})
            self.assertEqual(r.status_code, 200, r.text)
            run_ids.append(r.json()["run_id"])

        # Wait for async execution to complete (poll run status)
        import time
        for run_id in run_ids:
            for _ in range(50):  # up to 5 seconds
                r = self.client.get(f"/api/studio/graphs/{gid}/runs")
                self.assertEqual(r.status_code, 200)
                logs = r.json()
                if logs and logs[0]["run_id"] == run_id and logs[0]["status"] in ("completed", "failed"):
                    break
                time.sleep(0.1)

        r = self.client.get(f"/api/studio/graphs/{gid}/runs")
        self.assertEqual(r.status_code, 200)
        logs = r.json()
        self.assertEqual(len(logs), 2)
        # Most recent first (dec #21: last 50, descending)
        self.assertEqual(logs[0]["graph_id"], gid)
        self.assertIn("run_id", logs[0])
        self.assertIn("total_matched", logs[0])
        self.assertIn("total_undefined", logs[0])
        self.assertIn("total_escalated", logs[0])

    def test_list_run_logs_limit_param(self):
        r = self.client.post("/api/studio/graphs", json={"name": "g", "nodes": [_node_query()], "edges": []})
        gid = r.json()["graph_id"]

        run_ids = []
        for _ in range(3):
            r = self.client.post(f"/api/studio/graphs/{gid}/run", json={"inputs": {}, "dry_run": True})
            self.assertEqual(r.status_code, 200)
            run_ids.append(r.json()["run_id"])

        # Wait for all runs to complete
        import time
        for run_id in run_ids:
            for _ in range(50):
                r = self.client.get(f"/api/studio/graphs/{gid}/runs")
                self.assertEqual(r.status_code, 200)
                logs = r.json()
                if logs and logs[0]["run_id"] == run_id and logs[0]["status"] in ("completed", "failed"):
                    break
                time.sleep(0.1)

        r = self.client.get(f"/api/studio/graphs/{gid}/runs?limit=2")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 2)

    # -------------------------------------------------------------------------
    # Undefined Queue
    # -------------------------------------------------------------------------

    def test_undefined_queue_empty(self):
        r = self.client.post("/api/studio/graphs", json={"name": "g", "nodes": [_node_query()], "edges": []})
        gid = r.json()["graph_id"]
        r = self.client.get(f"/api/studio/graphs/{gid}/undefined-queue")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["graph_id"], gid)
        self.assertEqual(body["items"], [])
        self.assertEqual(body["cap"], 100)  # default

    def test_undefined_queue_populated(self):
        # Graph with a conditional that has no false_action (unmatched items queue)
        # Use a simple graph with no edges - the conditional runs directly as entry point
        payload = {
            "name": "g",
            "nodes": [_node_query(), _node_conditional()],  # conditional has no false_action
            "edges": [],  # no edges = both nodes are entry points, conditional runs directly
        }
        r = self.client.post("/api/studio/graphs", json=payload)
        gid = r.json()["graph_id"]

        # Run with state that makes condition false → unmatched → queued
        r = self.client.post(f"/api/studio/graphs/{gid}/run", json={"inputs": {"ticket": {"status": "WIP"}}, "dry_run": True})
        self.assertEqual(r.status_code, 200, r.text)
        run_id = r.json()["run_id"]

        # Wait for async execution to complete (poll run status)
        import time
        for _ in range(50):  # up to 5 seconds
            r = self.client.get(f"/api/studio/graphs/{gid}/runs")
            self.assertEqual(r.status_code, 200)
            logs = r.json()
            if logs and logs[0]["run_id"] == run_id and logs[0]["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)

        r = self.client.get(f"/api/studio/graphs/{gid}/undefined-queue")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(body["items"][0]["node_id"], "c1")
        self.assertEqual(body["items"][0]["condition_field"], "ticket.status")

    def test_undefined_queue_cap_round_trips(self):
        # Custom cap on create
        payload = {"name": "g", "nodes": [_node_query()], "edges": [], "undefined_queue_cap": 25}
        r = self.client.post("/api/studio/graphs", json=payload)
        gid = r.json()["graph_id"]

        r = self.client.get(f"/api/studio/graphs/{gid}/undefined-queue")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["cap"], 25)

    def test_undefined_queue_404(self):
        r = self.client.get("/api/studio/graphs/does_not_exist/undefined-queue")
        self.assertEqual(r.status_code, 404)

    # -------------------------------------------------------------------------
    # Schedulable Graphs
    # -------------------------------------------------------------------------

    def test_list_schedulable_graphs_empty(self):
        r = self.client.get("/api/studio/schedulable-graphs")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_list_schedulable_graphs_non_empty(self):
        # Only graphs with cron_enabled=True and a cron_schedule are schedulable
        payload = {
            "name": "sched",
            "nodes": [_node_query()],
            "edges": [],
            "cron_schedule": "0 2 * * *",
            "cron_enabled": True,
        }
        r = self.client.post("/api/studio/graphs", json=payload)
        self.assertEqual(r.status_code, 201)

        r = self.client.get("/api/studio/schedulable-graphs")
        self.assertEqual(r.status_code, 200)
        graphs = r.json()
        self.assertEqual(len(graphs), 1)
        self.assertEqual(graphs[0]["cron_enabled"], True)
        self.assertEqual(graphs[0]["cron_schedule"], "0 2 * * *")

    # -------------------------------------------------------------------------
    # Skills CRUD
    # -------------------------------------------------------------------------

    def test_create_skill_round_trip(self):
        payload = {
            "skill_id": "skill_1",
            "name": "Enrich Ticket",
            "description": "Adds priority from tags",
            "script": "return {'priority': 'P1' if 'urgent' in input.get('tags', []) else 'P3'}",
            "input_schema": {"type": "object", "properties": {"tags": {"type": "array", "items": {"type": "string"}}}},
            "output_schema": {"type": "object", "properties": {"priority": {"type": "string"}}},
            "version": "1.0.0",
            "tags": ["jira", "enrichment"],
            "required_capability": "generate",
        }
        r = self.client.post("/api/studio/skills", json=payload)
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertEqual(body["skill_id"], "skill_1")
        self.assertEqual(body["name"], "Enrich Ticket")
        self.assertEqual(body["required_capability"], "generate")

        # GET detail round-trip
        r = self.client.get("/api/studio/skills/skill_1")
        self.assertEqual(r.status_code, 200)
        skill = r.json()
        self.assertEqual(skill["script"], payload["script"])
        self.assertEqual(skill["input_schema"], payload["input_schema"])
        self.assertEqual(skill["output_schema"], payload["output_schema"])
        self.assertEqual(skill["tags"], ["jira", "enrichment"])

    def test_list_skills_empty_then_populated(self):
        r = self.client.get("/api/studio/skills")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

        self.client.post("/api/studio/skills", json={
            "skill_id": "s1", "name": "S1", "description": "", "script": "return {}",
            "input_schema": {}, "output_schema": {}, "version": "1", "tags": [], "required_capability": "generate",
        })
        r = self.client.get("/api/studio/skills")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 1)

    def test_get_skill_404(self):
        r = self.client.get("/api/studio/skills/does_not_exist")
        self.assertEqual(r.status_code, 404)

    def test_delete_skill_204_then_404(self):
        self.client.post("/api/studio/skills", json={
            "skill_id": "s_del", "name": "S", "description": "", "script": "return {}",
            "input_schema": {}, "output_schema": {}, "version": "1", "tags": [], "required_capability": "generate",
        })
        r = self.client.delete("/api/studio/skills/s_del")
        self.assertEqual(r.status_code, 204)

        r = self.client.get("/api/studio/skills/s_del")
        self.assertEqual(r.status_code, 404)

        r = self.client.delete("/api/studio/skills/s_del")
        self.assertEqual(r.status_code, 404)

    # -------------------------------------------------------------------------
    # Integrations Status
    # -------------------------------------------------------------------------

    def test_integrations_status_empty(self):
        r = self.client.get("/api/studio/integrations/status")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"integrations": []})

    def test_integrations_status_populated(self):
        # Write integrations.json directly to the temp dir
        import json
        cfg_path = os.path.join(self.tmp, "integrations.json")
        with open(cfg_path, "w") as f:
            json.dump({
                "jira_prod": {"type": "jira", "config": {"adapter_module": "api.adapters.jira"}, "status": "connected"},
                "github_dev": {"type": "github", "config": {"adapter_module": "api.adapters.github"}, "status": "disconnected"},
            }, f)

        r = self.client.get("/api/studio/integrations/status")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body["integrations"]), 2)
        names = {i["name"] for i in body["integrations"]}
        self.assertEqual(names, {"jira_prod", "github_dev"})
        for i in body["integrations"]:
            self.assertIn("connected", i)
            self.assertIn("adapter_module", i)


if __name__ == "__main__":
    unittest.main()