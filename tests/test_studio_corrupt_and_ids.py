"""R8 / P0-5 and R26.

R8 / P0-5 (defect): _load_graph / _load_skill returned None on bad JSON, so
create_graph saw the id as free and overwrote the corrupt file. /integrations/status
swallowed a corrupt integrations.json and showed an empty list.
Fix under test: the managers quarantine the corrupt file the way
api/managers/base.py does (copy to <file>.corrupt-<UTC>, reuse identical backups,
leave the original), raise CorruptStudioFileError (409 at the router, path-free
message); a missing file is still "not found"; /integrations/status returns an
`error` field for a corrupt or non-object integrations.json.

R26 (defect): same-name graph creates used a seconds timestamp suffix, so rapid
creates overwrote each other. Fix under test: a short uuid suffix that still
passes the safe-id pattern.
"""
import glob
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
from api.models.studio import (
    SAFE_STUDIO_ID_PATTERN,
    CorruptStudioFileError,
    Skill,
    StudioGraph,
)

SAFE = re.compile(SAFE_STUDIO_ID_PATTERN)


def _q(node_id):
    return {"node_id": node_id, "name": node_id, "archetype": "query",
            "adapter": "internal_adapter", "action": "list_items", "params": {}, "output_ref": "o"}


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="studio_corrupt_")
        self.graphs_dir = os.path.join(self.tmp, "studio_graphs")
        self.skills_dir = os.path.join(self.tmp, "skills")
        self._orig_base = studio_router._get_base_dir
        self._orig_gm = studio_router.get_studio_graph_manager
        self._orig_sm = studio_router.get_skill_manager
        studio_router._get_base_dir = lambda: self.tmp
        studio_router.get_studio_graph_manager = lambda: StudioGraphManager(self.tmp)
        studio_router.get_skill_manager = lambda: SkillManager(self.tmp)
        app.dependency_overrides[studio_router.get_studio_graph_manager] = lambda: StudioGraphManager(self.tmp)
        app.dependency_overrides[studio_router.get_skill_manager] = lambda: SkillManager(self.tmp)
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.pop(studio_router.get_studio_graph_manager, None)
        app.dependency_overrides.pop(studio_router.get_skill_manager, None)
        studio_router._get_base_dir = self._orig_base
        studio_router.get_studio_graph_manager = self._orig_gm
        studio_router.get_skill_manager = self._orig_sm
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, directory, name, text):
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def _backups(self, original):
        return sorted(glob.glob(original + ".corrupt-*"))


class TestManagerQuarantine(_Base):
    def test_corrupt_graph_raises_and_is_backed_up_original_untouched(self):
        path = self._write(self.graphs_dir, "g1.json", "{not json")
        mgr = StudioGraphManager(self.tmp)
        with self.assertRaises(CorruptStudioFileError) as ctx:
            mgr.get_graph("g1")
        self.assertEqual(len(self._backups(path)), 1)
        with open(path) as f:
            self.assertEqual(f.read(), "{not json", "original must be left in place")
        self.assertNotIn(self.tmp, str(ctx.exception), "message must not contain a path")

    def test_identical_corrupt_content_reuses_the_backup(self):
        path = self._write(self.graphs_dir, "g1.json", "{broken")
        mgr = StudioGraphManager(self.tmp)
        for _ in range(3):
            with self.assertRaises(CorruptStudioFileError):
                mgr.get_graph("g1")
        self.assertEqual(len(self._backups(path)), 1)

    def test_non_dict_root_is_corrupt(self):
        path = self._write(self.graphs_dir, "g1.json", "[1, 2, 3]")
        with self.assertRaises(CorruptStudioFileError):
            StudioGraphManager(self.tmp).get_graph("g1")
        self.assertEqual(len(self._backups(path)), 1)

    def test_bad_utf8_is_corrupt(self):
        os.makedirs(self.graphs_dir, exist_ok=True)
        path = os.path.join(self.graphs_dir, "g1.json")
        with open(path, "wb") as f:
            f.write(b"\xff\xfe\x00bad")
        with self.assertRaises(CorruptStudioFileError):
            StudioGraphManager(self.tmp).get_graph("g1")
        self.assertEqual(len(self._backups(path)), 1)

    def test_missing_graph_is_still_not_found_none(self):
        self.assertIsNone(StudioGraphManager(self.tmp).get_graph("absent"))

    def test_corrupt_skill_raises_and_is_backed_up(self):
        path = self._write(self.skills_dir, "s1.json", "{oops")
        mgr = SkillManager(self.tmp)
        with self.assertRaises(CorruptStudioFileError):
            mgr.get_skill("s1")
        self.assertEqual(len(self._backups(path)), 1)
        with open(path) as f:
            self.assertEqual(f.read(), "{oops")

    def test_missing_skill_is_still_not_found_none(self):
        self.assertIsNone(SkillManager(self.tmp).get_skill("absent"))

    def test_listing_skips_corrupt_file_but_keeps_others(self):
        self._write(self.graphs_dir, "bad.json", "{x")
        mgr = StudioGraphManager(self.tmp)
        mgr.save_graph(StudioGraph(graph_id="good", name="good"))
        ids = [g["graph_id"] for g in mgr.list_graphs()]
        self.assertEqual(ids, ["good"])

    def test_skill_listing_skips_corrupt_file_but_keeps_others(self):
        self._write(self.skills_dir, "bad.json", "{x")
        mgr = SkillManager(self.tmp)
        mgr.save_skill(Skill(skill_id="ok", name="ok", description="", script="result = 1"))
        self.assertEqual([s["skill_id"] for s in mgr.list_skills()], ["ok"])


class TestRouterCorruptHandling(_Base):
    def test_create_graph_over_corrupt_same_name_file_is_409_and_not_overwritten(self):
        # Same slug as the name "Corrupt Me" -> graph_corrupt_me
        path = self._write(self.graphs_dir, "graph_corrupt_me.json", "{broken")
        r = self.client.post("/api/studio/graphs", json={"name": "Corrupt Me", "nodes": [_q("a")], "edges": []})
        self.assertEqual(r.status_code, 409, r.text)
        self.assertNotIn(self.tmp, r.text, "409 message must not expose the filesystem path")
        with open(path) as f:
            self.assertEqual(f.read(), "{broken", "corrupt file must not be replaced")

    def test_get_corrupt_graph_is_409_path_free(self):
        self._write(self.graphs_dir, "graph_bad.json", "{broken")
        r = self.client.get("/api/studio/graphs/graph_bad")
        self.assertEqual(r.status_code, 409)
        self.assertNotIn(self.tmp, r.text)
        self.assertIn("corrupt", r.json()["detail"])

    def test_run_corrupt_graph_is_409(self):
        self._write(self.graphs_dir, "graph_bad.json", "{broken")
        r = self.client.post("/api/studio/graphs/graph_bad/run", json={"inputs": {}})
        self.assertEqual(r.status_code, 409)
        self.assertNotIn(self.tmp, r.text)

    def test_get_corrupt_skill_is_409_path_free(self):
        self._write(self.skills_dir, "skill_bad.json", "{broken")
        r = self.client.get("/api/studio/skills/skill_bad")
        self.assertEqual(r.status_code, 409)
        self.assertNotIn(self.tmp, r.text)

    def test_create_skill_over_corrupt_file_is_409_and_not_overwritten(self):
        path = self._write(self.skills_dir, "dup.json", "{broken")
        r = self.client.post("/api/studio/skills", json={
            "skill_id": "dup", "name": "n", "description": "d", "script": "result = 1"})
        self.assertEqual(r.status_code, 409, r.text)
        with open(path) as f:
            self.assertEqual(f.read(), "{broken")

    def test_missing_graph_still_404(self):
        self.assertEqual(self.client.get("/api/studio/graphs/nope").status_code, 404)


class TestIntegrationsStatus(_Base):
    def _status(self):
        return self.client.get("/api/studio/integrations/status").json()

    def test_missing_file_is_empty_without_error(self):
        body = self._status()
        self.assertEqual(body, {"integrations": []})

    def test_valid_file_lists_integrations_without_error(self):
        self._write(self.tmp, "integrations.json", json.dumps({
            "jira_test": {"type": "native", "status": "connected", "config": {"adapter_module": "x"}},
        }))
        body = self._status()
        self.assertNotIn("error", body)
        self.assertEqual(body["integrations"][0]["name"], "jira_test")
        self.assertTrue(body["integrations"][0]["connected"])

    def test_corrupt_file_returns_error_field_not_empty_list(self):
        self._write(self.tmp, "integrations.json", "{broken")
        body = self._status()
        self.assertIn("error", body)
        self.assertIn("corrupt", body["error"])
        self.assertNotIn(self.tmp, body["error"])
        self.assertEqual(body["integrations"], [])

    def test_non_dict_root_is_treated_as_corrupt(self):
        self._write(self.tmp, "integrations.json", "[1, 2]")
        body = self._status()
        self.assertIn("error", body)
        self.assertEqual(body["integrations"], [])

    def test_bad_utf8_is_treated_as_corrupt(self):
        with open(os.path.join(self.tmp, "integrations.json"), "wb") as f:
            f.write(b"\xff\xfe\x00")
        self.assertIn("error", self._status())

    def test_non_dict_entry_does_not_crash_listing(self):
        self._write(self.tmp, "integrations.json", json.dumps({"weird": "string", "ok": {"status": "connected"}}))
        body = self._status()
        names = {i["name"]: i for i in body["integrations"]}
        self.assertEqual(names["weird"]["status"], "invalid")
        self.assertTrue(names["ok"]["connected"])


class TestRapidSameNameCreates(_Base):
    def test_rapid_creates_with_same_name_do_not_overwrite(self):
        ids = set()
        for i in range(5):
            r = self.client.post("/api/studio/graphs", json={
                "name": "Same Name", "nodes": [_q(f"n{i}")], "edges": []})
            self.assertEqual(r.status_code, 201, r.text)
            ids.add(r.json()["graph_id"])
        self.assertEqual(len(ids), 5, "each create must get its own id")
        for gid in ids:
            self.assertRegex(gid, SAFE, f"{gid} must pass the safe-id pattern")
        self.assertEqual(len(StudioGraphManager(self.tmp).list_graphs()), 5)

    def test_collision_suffix_is_short_random_not_timestamp(self):
        self.client.post("/api/studio/graphs", json={"name": "Dup", "nodes": [_q("a")], "edges": []})
        r = self.client.post("/api/studio/graphs", json={"name": "Dup", "nodes": [_q("b")], "edges": []})
        gid = r.json()["graph_id"]
        self.assertTrue(gid.startswith("graph_dup_"), gid)
        suffix = gid[len("graph_dup_"):]
        self.assertRegex(suffix, r"^[0-9a-f]{8}$", "suffix must be 8 hex chars from uuid4")

    def test_first_create_keeps_plain_slug_id(self):
        r = self.client.post("/api/studio/graphs", json={"name": "Plain", "nodes": [_q("a")], "edges": []})
        self.assertEqual(r.json()["graph_id"], "graph_plain")

    def test_long_name_with_suffix_stays_safe(self):
        name = "x" * 200
        self.client.post("/api/studio/graphs", json={"name": name, "nodes": [_q("a")], "edges": []})
        r = self.client.post("/api/studio/graphs", json={"name": name, "nodes": [_q("b")], "edges": []})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertRegex(r.json()["graph_id"], SAFE)


if __name__ == "__main__":
    unittest.main()
