"""Unit tests for ``agents.executor_tools``.

* P3.2.2 — ``get_workspace_files`` returns a *bounded, relevant* file set
  (<= the cap), excludes build/cache/dependency dirs, sorts, and stays
  deterministic under a controlled temp tree.
* P3.2.6 Phase 1 — ``execute_tool`` done-semantics: the executor no longer
  self-verifies.  Only ``write_file``/``patch`` can mark ``is_done``; a
  ``write_file`` of empty/stub-marker content is rejected; ``terminal`` and
  ``read_file`` are NEVER done.  These guard the live-bug fix (no ``ls``-loop
  false-greens; no ``echo`` completion).
* P3.2.6 Fix #1 — a small-but-real artifact (e.g. a 6-byte ``VERSION`` file)
  now completes; the old byte floor that wrongly rejected it is dropped, and
  ``write_file`` self-verifies via a read-back.  See
  ``test_write_file_small_real_content_is_done``.
"""
import os

from agents.executor_tools import (
    get_workspace_files,
    WORKSPACE_FILES_CAP,
    execute_tool,
    _is_stub_content,
    _resolve_item_path,
)


def _make_tree(base) -> None:
    """Build a deterministic fixture tree under ``base`` (a pathlib Path)."""
    (base / "VERSION").write_text("1\n")
    (base / "README.md").write_text("# x\n")
    (base / "api").mkdir()
    (base / "api" / "main.py").write_text("# m\n")
    (base / "api" / "models").mkdir()
    (base / "api" / "models" / "config.py").write_text("# c\n")
    (base / "api" / "__pycache__").mkdir()
    (base / "api" / "__pycache__" / "junk.pyc").write_text("x")
    for d in ("venv", "node_modules", ".git", ".ui", "dist", "build"):
        (base / d).mkdir(parents=True, exist_ok=True)
    (base / "venv" / "lib").mkdir(parents=True, exist_ok=True)
    (base / "venv" / "bin").mkdir()
    (base / "venv" / "bin" / "python").write_text("x")
    (base / "venv" / "lib" / "x.py").write_text("x")
    (base / "node_modules" / "pkg").mkdir()
    (base / "node_modules" / "pkg" / "index.js").write_text("x")
    (base / ".git" / "config").write_text("x")
    (base / ".ui" / "cache.dat").write_text("x")
    (base / "dist" / "build.js").write_text("x")


def test_get_workspace_files_under_cap(tmp_path):
    _make_tree(tmp_path)
    result = get_workspace_files(root=str(tmp_path))
    assert len(result) <= WORKSPACE_FILES_CAP, f"{len(result)} > cap {WORKSPACE_FILES_CAP}"


def test_get_workspace_files_sorted_and_unique(tmp_path):
    _make_tree(tmp_path)
    result = get_workspace_files(root=str(tmp_path))
    assert result == sorted(result), "result must be sorted"
    assert len(result) == len(set(result)), "result must be deduped"


def test_get_workspace_files_excludes_build_cache_dirs(tmp_path):
    _make_tree(tmp_path)
    result = set(get_workspace_files(root=str(tmp_path)))
    # None of these excluded dirs may appear in any returned path.
    forbidden_prefixes = (
        "venv/", "node_modules/", ".git/", ".ui/",
        "dist/", "build/", "__pycache__/",
    )
    for p in result:
        assert not p.startswith(forbidden_prefixes), f"excluded dir leaked: {p}"
    # positive: the api/ source files and top-level files ARE present
    assert "api/main.py" in result
    assert "api/models/config.py" in result
    assert "VERSION" in result
    assert "README.md" in result


def test_get_workspace_files_no_pycache_anywhere(tmp_path):
    """Excluded dirs must be pruned mid-walk, not just at the top level."""
    _make_tree(tmp_path)
    result = get_workspace_files(root=str(tmp_path))
    assert not any("__pycache__" in p for p in result)
    assert not any(".pyc" in p for p in result)


def test_get_workspace_files_cap_is_a_real_bound(tmp_path):
    """Plant ``cap + 20`` files under api/ and prove the cap truncates.

    A fixture that naturally stays under 60 would pass even if the
    truncation logic were stripped out; this one forces an overflow so the
    cap must actually clamp.
    """
    over = WORKSPACE_FILES_CAP + 20
    api = tmp_path / "api"
    api.mkdir()
    for i in range(over):
        (api / f"f{i:03d}.py").write_text("# x\n")
    result = get_workspace_files(root=str(tmp_path))
    assert len(result) == WORKSPACE_FILES_CAP, (
        f"cap not enforced: got {len(result)}, expected {WORKSPACE_FILES_CAP}"
    )
    # the kept slice must be the sorted prefix (first ``cap`` files)
    all_sorted = sorted(f.name for f in api.iterdir())
    kept_names = [os.path.basename(p) for p in result]
    assert kept_names == all_sorted[:WORKSPACE_FILES_CAP]


# ---------------------------------------------------------------------------
# P3.2.6 Phase 1 — execute_tool done-semantics (no self-verify)
# ---------------------------------------------------------------------------

_GOOD_CONTENT = "def health():\n    return {'status': 'ok'}\n# real handler\n"
# P3.2.6 Fix #1 dropped the byte floor.  A small-but-real artifact is now a
# legitimate file, NOT a stub — this was the exact cause of the live gate's
# "Create VERSION file" loop (the old 30-byte floor rejected "0.1.0\n").
_SMALL_REAL_CONTENT = "0.1.0\n"  # 6 bytes — a legitimate single-line VERSION file
_STUB_CONTENT = "stub response\n" * 3  # carries the literal stub marker


def test_is_stub_content_flags_empty_and_markers():
    # Empty / whitespace-only content is a stub.
    assert _is_stub_content("") is True
    assert _is_stub_content("   ") is True
    # Stub-marker content is a stub.
    assert _is_stub_content(_STUB_CONTENT) is True
    assert _is_stub_content("# TODO fill this in") is True
    assert _is_stub_content("placeholder") is True
    # Fix #1: a small-but-real artifact is NOT a stub anymore.
    assert _is_stub_content(_SMALL_REAL_CONTENT) is False
    assert _is_stub_content(_GOOD_CONTENT) is False


def test_write_file_small_real_content_is_done(tmp_path):
    """Fix #1: a legitimate small artefact (a VERSION file) completes the
    task.  The old byte floor wrongly rejected this and made the live gate's
    "Create VERSION file" task loop to exhaustion."""
    path = str(tmp_path / "VERSION")
    done, msg = execute_tool("write_file", {"path": path, "content": _SMALL_REAL_CONTENT}, "X")
    assert done is True, msg
    assert os.path.isfile(path)
    assert open(path).read() == _SMALL_REAL_CONTENT


def test_write_file_good_content_is_done(tmp_path):
    """A write of full, non-stub content completes the task."""
    path = str(tmp_path / "out.py")
    done, msg = execute_tool("write_file", {"path": path, "content": _GOOD_CONTENT}, "X")
    assert done is True, msg
    assert os.path.isfile(path)
    assert open(path).read() == _GOOD_CONTENT


def test_write_file_stub_content_is_not_done(tmp_path):
    """The live-bug guard: writing a stub/placeholder must NOT mark done."""
    path = str(tmp_path / "stub.py")
    done, msg = execute_tool("write_file", {"path": path, "content": _STUB_CONTENT}, "X")
    assert done is False, "stub content must not complete a task"
    assert "stub" in msg.lower() or "stub" in msg
    # And the file must NOT be left on disk as a fake artifact.
    assert not os.path.isfile(path), "stub content was written to disk despite rejection"


def test_terminal_exit_zero_is_never_done():
    """The Phase 1 core change: a successful shell command is recon, not
    proof of completion.  (Old behaviour credited pytest-shape commands and
    looped 20× on unrecognised ``ls``.)  Even ``true`` (exit 0) must not
    mark done — if it did, a model could false-green with a vacuous command.
    """
    done, _ = execute_tool("terminal", {"command": "true"}, "X")
    assert done is False, "terminal must never assert is_done (Phase 1)"


def test_terminal_failing_command_reports_error_not_done():
    """A non-zero exit returns an ERROR result, still not done."""
    done, msg = execute_tool("terminal", {"command": "false"}, "X")
    assert done is False
    assert "ERROR" in msg


def test_read_file_is_never_done(tmp_path):
    """``read_file`` is information-gathering; it never completes a task."""
    path = str(tmp_path / "f.py")
    with open(path, "w") as f:
        f.write(_GOOD_CONTENT)
    done, msg = execute_tool("read_file", {"path": path}, "X")
    assert done is False
    assert "FILE CONTENT" in msg


def test_patch_lands_is_done(tmp_path):
    """``patch`` of an existing file that finds old_string is done (unchanged
    Phase 1 contract)."""
    path = str(tmp_path / "p.py")
    with open(path, "w") as f:
        f.write("a = 1\n")
    done, msg = execute_tool(
        "patch",
        {"path": path, "old_string": "a = 1", "new_string": "a = 2"},
        "X",
    )
    assert done is True, msg
    assert open(path).read() == "a = 2\n"


def test_patch_missing_old_string_is_not_done(tmp_path):
    path = str(tmp_path / "p.py")
    with open(path, "w") as f:
        f.write("a = 1\n")
    done, msg = execute_tool(
        "patch",
        {"path": path, "old_string": "not-here", "new_string": "x"},
        "X",
    )
    assert done is False
    assert "not found" in msg.lower() or "ERROR" in msg


# ---------------------------------------------------------------------------
# P3.2.7 follow-up — relative tool paths anchor at requirements/<item_id>/
# ---------------------------------------------------------------------------

def test_resolve_item_path_absolute_is_unchanged():
    """An ABSOLUTE path is returned verbatim — the executor must still be able
    to write a real repo-root source file when an absolute path is emitted
    (the CI fixture deliberately feeds absolute paths)."""
    abs_path = os.path.join(os.sep, "tmp", "whatever", "VERSION")
    assert _resolve_item_path(abs_path, "SCRIPT-01") == abs_path


def test_resolve_item_path_relative_anchors_to_item_dir(tmp_path, monkeypatch):
    """A RELATIVE path resolves under ``automation-ideas/requirements/<id>/`` —
    NOT against the process cwd.  This is the core fix for the P3.2.7
    relative-path defect (artifacts were escaping to the repo root)."""
    monkeypatch.chdir(str(tmp_path))
    item_id = "SCRIPT-01"
    resolved = _resolve_item_path("system_health_utility.sh", item_id)
    expected = os.path.join(
        str(tmp_path), "automation-ideas", "requirements", item_id, "system_health_utility.sh"
    )
    assert resolved == expected
    # And it must NOT be anchored at bare cwd.
    assert resolved != os.path.join(str(tmp_path), "system_health_utility.sh")


def test_resolve_item_path_empty_is_returned_unchanged():
    """An empty/None path is a caller error, not a path to anchor — return it
    so the existing ``if not path`` guards (write_file/read_file) still fire."""
    assert _resolve_item_path("", "ID-1") == ""
    assert _resolve_item_path(None, "ID-1") is None


def test_write_file_relative_lands_in_item_dir_not_cwd(tmp_path, monkeypatch):
    """The defect, end-to-end: a RELATIVE ``write_file`` path must land under
    ``requirements/<id>/``, never at the process cwd (repo root).

    Mirrors the SCRIPT-01 failure where ``system_health_utility.sh`` appeared
    untracked at the repo root.  Run from a throwaway cwd that is NOT the item
    dir; assert the file is under the item dir and NOT at cwd.
    """
    monkeypatch.chdir(str(tmp_path))
    item_id = "X"
    item_dir = os.path.join(str(tmp_path), "automation-ideas", "requirements", item_id)
    os.makedirs(item_dir, exist_ok=True)

    done, msg = execute_tool(
        "write_file",
        {"path": "script.sh", "content": _GOOD_CONTENT},
        item_id,
    )
    assert done is True, msg

    # Landed in the ITEM dir …
    expected = os.path.join(item_dir, "script.sh")
    assert os.path.isfile(expected), f"expected {expected} to exist"
    assert open(expected).read() == _GOOD_CONTENT
    # … and NOT at the bare cwd (the old defect symptom).
    assert not os.path.isfile(os.path.join(str(tmp_path), "script.sh")), (
        "relative write_file escaped to cwd — the P3.2.7 defect regressed"
    )
