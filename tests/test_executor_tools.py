"""Unit tests for ``agents.executor_tools``.

* P3.2.2 — ``get_workspace_files`` returns a *bounded, relevant* file set
  (<= the cap), excludes build/cache/dependency dirs, sorts, and stays
  deterministic under a controlled temp tree.
* P3.2.6 Phase 1 — ``execute_tool`` done-semantics: the executor no longer
  self-verifies.  Only ``write_file``/``patch`` can mark ``is_done``; a
  ``write_file`` of empty/tiny/stub content is rejected; ``terminal`` and
  ``read_file`` are NEVER done.  These guard the live-bug fix (no ``ls``-loop
  false-greens; no ``echo`` completion).
"""
import os

from agents.executor_tools import (
    get_workspace_files,
    WORKSPACE_FILES_CAP,
    execute_tool,
    _is_stub_content,
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
# Exactly 30 bytes stripped would be the boundary; pick comfortably above and below.
_TINY_CONTENT = "hi"  # 2 bytes -> below the _MIN_ARTIFACT_BYTES floor
_STUB_CONTENT = "stub response\n" * 3  # carries the literal stub marker


def test_is_stub_content_flags_empty_tiny_and_markers():
    assert _is_stub_content("") is True
    assert _is_stub_content("   ") is True
    assert _is_stub_content(_TINY_CONTENT) is True
    assert _is_stub_content(_STUB_CONTENT) is True
    assert _is_stub_content("# TODO fill this in") is True
    assert _is_stub_content("placeholder") is True
    assert _is_stub_content(_GOOD_CONTENT) is False


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


def test_write_file_tiny_content_is_not_done(tmp_path):
    """Too-small content (below the artifact byte floor) must not complete."""
    path = str(tmp_path / "tiny.txt")
    done, msg = execute_tool("write_file", {"path": path, "content": _TINY_CONTENT}, "X")
    assert done is False, "tiny content must not complete a task"
    assert not os.path.isfile(path)


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
