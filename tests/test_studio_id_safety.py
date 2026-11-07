"""SEC-11 / T3: Studio ids must never be used to build paths outside their dir.

Defects (verified at HEAD 66340b8):
- ``SkillManager._skill_path`` joined ``skill_id`` into a file path unchecked, so
  ``skill_id="../../escape"`` wrote a JSON file outside ``skills/``.
- ``create_graph`` built ``graph_id`` from the name replacing only spaces and
  hyphens, so ``"/"`` and ``".."`` survived into the id and the file path.

Fix under test: ids must match ``^[A-Za-z0-9_-]{1,100}$`` (the router returns 422;
managers refuse to read/write/delete an unsafe id), and the graph-id slug strips
unsafe characters. Normal ids keep working.
"""
import json
import os
import re
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from api import studio_router
from api.main import app
from api.managers.skill_manager import SkillManager
from api.managers.studio_graph_manager import StudioGraphManager
from api.models.studio import Skill, StudioGraph

SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


def _skill_payload(skill_id):
    return {
        "skill_id": skill_id,
        "name": "S",
        "description": "d",
        "script": "result = input",
    }


def _graph_payload(name):
    return {
        "name": name,
        "description": "",
        "nodes": [],
        "edges": [],
        "cron_enabled": False,
        "undefined_queue_cap": 100,
        "max_run_logs": 50,
    }


class _TmpBase(unittest.TestCase):
    """Creates base/ (the studio base dir) under a sandbox tmp root.

    ``sandbox`` is the tmp root; anything written to ``sandbox/<x>`` that is
    outside ``base/skills`` or ``base/studio_graphs`` counts as an escape.
    """

    def setUp(self):
        self.sandbox = tempfile.mkdtemp(prefix="studio_id_safety_")
        self.base = os.path.join(self.sandbox, "base")
        os.makedirs(self.base)
        self.skills_dir = os.path.join(self.base, "skills")
        self.graphs_dir = os.path.join(self.base, "studio_graphs")

    def tearDown(self):
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def _files_outside_managed_dirs(self):
        found = []
        for root, _dirs, files in os.walk(self.sandbox):
            for f in files:
                full = os.path.join(root, f)
                if full.startswith(self.skills_dir + os.sep) or full.startswith(self.graphs_dir + os.sep):
                    continue
                found.append(full)
        return found


class TestManagerRefusesUnsafeIds(_TmpBase):
    """Direct manager-level defence (router validation is bypassed)."""

    def setUp(self):
        super().setUp()
        self.skills = SkillManager(self.base)
        self.graphs = StudioGraphManager(self.base)

    def test_skill_save_with_traversal_id_writes_nothing(self):
        skill = Skill(skill_id="../../escape", name="x", description="", script="result = 1")
        self.assertFalse(self.skills.save_skill(skill))
        self.assertEqual(self._files_outside_managed_dirs(), [])
        self.assertFalse(os.path.exists(os.path.join(self.sandbox, "escape.json")))

    def test_skill_get_delete_with_traversal_id_is_refused(self):
        # A file that a traversal id would reach if unchecked.
        victim = os.path.join(self.sandbox, "victim.json")
        with open(victim, "w") as f:
            json.dump({"skill_id": "v", "name": "v", "description": "", "script": "x"}, f)

        self.assertIsNone(self.skills.get_skill("../../victim"))
        self.assertFalse(self.skills.delete_skill("../../victim"))
        self.assertTrue(os.path.exists(victim), "delete must not remove a file outside skills/")

    def test_skill_ids_with_separators_or_dots_refused(self):
        for bad in ["a/b", "..", ".", "a.b", "", "x" * 101, "a\\b", "a\x00b"]:
            with self.subTest(skill_id=bad):
                self.assertFalse(self.skills.save_skill(
                    Skill(skill_id=bad, name="x", description="", script="r = 1")
                ))
        self.assertEqual(self._files_outside_managed_dirs(), [])

    def test_graph_save_with_traversal_id_writes_nothing(self):
        graph = StudioGraph(graph_id="../../escape", name="x")
        self.assertFalse(self.graphs.save_graph(graph))
        self.assertEqual(self._files_outside_managed_dirs(), [])

    def test_graph_get_delete_with_traversal_id_is_refused(self):
        victim = os.path.join(self.sandbox, "victim.json")
        with open(victim, "w") as f:
            json.dump({"graph_id": "v", "name": "v"}, f)

        self.assertIsNone(self.graphs.get_graph("../../victim"))
        self.assertFalse(self.graphs.delete_graph("../../victim"))
        self.assertTrue(os.path.exists(victim))

    def test_normal_ids_still_round_trip(self):
        skill = Skill(skill_id="skill-123_ok", name="x", description="", script="result = 1")
        self.assertTrue(self.skills.save_skill(skill))
        self.assertEqual(self.skills.get_skill("skill-123_ok").skill_id, "skill-123_ok")
        self.assertTrue(self.skills.delete_skill("skill-123_ok"))

        graph = StudioGraph(graph_id="graph_ok-1", name="x")
        self.assertTrue(self.graphs.save_graph(graph))
        self.assertEqual(self.graphs.get_graph("graph_ok-1").graph_id, "graph_ok-1")


class TestRouterRejectsUnsafeIds(_TmpBase):
    def setUp(self):
        super().setUp()
        self._orig_base = studio_router._get_base_dir
        studio_router._get_base_dir = lambda: self.base
        self._orig_graph_mgr = studio_router.get_studio_graph_manager
        self._orig_skill_mgr = studio_router.get_skill_manager
        base = self.base
        studio_router.get_studio_graph_manager = lambda: StudioGraphManager(base)
        studio_router.get_skill_manager = lambda: SkillManager(base)
        app.dependency_overrides[studio_router.get_studio_graph_manager] = lambda: StudioGraphManager(base)
        app.dependency_overrides[studio_router.get_skill_manager] = lambda: SkillManager(base)
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(studio_router.get_studio_graph_manager, None)
        app.dependency_overrides.pop(studio_router.get_skill_manager, None)
        studio_router._get_base_dir = self._orig_base
        studio_router.get_studio_graph_manager = self._orig_graph_mgr
        studio_router.get_skill_manager = self._orig_skill_mgr
        super().tearDown()

    def test_create_skill_with_traversal_id_is_422_and_writes_nothing(self):
        r = self.client.post("/api/studio/skills", json=_skill_payload("../../escape"))
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(self._files_outside_managed_dirs(), [])
        self.assertFalse(os.path.exists(os.path.join(self.sandbox, "escape.json")))

    def test_create_skill_with_slash_or_dot_ids_is_422(self):
        for bad in ["a/b", "..", "a.b", "a b", ""]:
            with self.subTest(skill_id=bad):
                r = self.client.post("/api/studio/skills", json=_skill_payload(bad))
                self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(self._files_outside_managed_dirs(), [])

    def test_get_and_delete_skill_with_unsafe_id_are_4xx(self):
        victim = os.path.join(self.sandbox, "victim.json")
        with open(victim, "w") as f:
            json.dump({"skill_id": "v", "name": "v", "description": "", "script": "x"}, f)

        r = self.client.get("/api/studio/skills/..%2F..%2Fvictim")
        self.assertGreaterEqual(r.status_code, 400)
        self.assertLess(r.status_code, 500)

        r = self.client.delete("/api/studio/skills/..%2F..%2Fvictim")
        self.assertGreaterEqual(r.status_code, 400)
        self.assertLess(r.status_code, 500)
        self.assertTrue(os.path.exists(victim))

    def test_normal_skill_id_still_created_and_fetched(self):
        r = self.client.post("/api/studio/skills", json=_skill_payload("parse-jira-desc_001"))
        self.assertEqual(r.status_code, 201, r.text)
        r = self.client.get("/api/studio/skills/parse-jira-desc_001")
        self.assertEqual(r.status_code, 200, r.text)


class TestGraphIdSlug(_TmpBase):
    def setUp(self):
        super().setUp()
        self._orig_base = studio_router._get_base_dir
        studio_router._get_base_dir = lambda: self.base
        base = self.base
        app.dependency_overrides[studio_router.get_studio_graph_manager] = lambda: StudioGraphManager(base)
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(studio_router.get_studio_graph_manager, None)
        studio_router._get_base_dir = self._orig_base
        super().tearDown()

    def _create(self, name):
        r = self.client.post("/api/studio/graphs", json=_graph_payload(name))
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["graph_id"]

    def test_slash_and_dotdot_in_name_produce_safe_id(self):
        for name in ["../../escape", "a/b", "team/..\\x", "..", "a/../b"]:
            with self.subTest(name=name):
                gid = self._create(name)
                self.assertRegex(gid, SAFE_ID)
                self.assertTrue(gid.startswith("graph_"))
        self.assertEqual(self._files_outside_managed_dirs(), [])
        # Every saved file is directly under studio_graphs/ (no subdirectories created).
        for entry in os.listdir(self.graphs_dir):
            self.assertTrue(os.path.isfile(os.path.join(self.graphs_dir, entry)), entry)

    def test_slug_strips_unsafe_characters_exactly(self):
        # One underscore per unsafe character: "/" and both "." become "_".
        self.assertEqual(self._create("a/b..c"), "graph_a_b__c")

    def test_normal_names_keep_existing_slug(self):
        self.assertEqual(self._create("Twistlock Slice-1"), "graph_twistlock_slice_1")

    def test_empty_or_symbol_only_name_gets_fallback_id(self):
        gid = self._create("///")
        self.assertRegex(gid, SAFE_ID)
        self.assertNotEqual(gid, "graph_")

    def test_very_long_name_is_truncated_to_safe_length(self):
        gid = self._create("x" * 300)
        self.assertRegex(gid, SAFE_ID)


if __name__ == "__main__":
    unittest.main()
