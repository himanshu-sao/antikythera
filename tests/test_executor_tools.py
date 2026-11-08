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
import ast
import os

import pytest

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
    "Create VERSION file" task loop to exhaustion.  D7: paths are relative to
    the item directory, so the file lands there."""
    item_dir = _item_dir(tmp_path, "X")
    done, msg = execute_tool("write_file", {"path": "VERSION", "content": _SMALL_REAL_CONTENT}, "X")
    assert done is True, msg
    path = os.path.join(item_dir, "VERSION")
    assert os.path.isfile(path)
    assert open(path).read() == _SMALL_REAL_CONTENT


def test_write_file_good_content_is_done(tmp_path):
    """A write of full, non-stub content completes the task."""
    item_dir = _item_dir(tmp_path, "X")
    done, msg = execute_tool("write_file", {"path": "out.py", "content": _GOOD_CONTENT}, "X")
    assert done is True, msg
    path = os.path.join(item_dir, "out.py")
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
    """The Phase 1 core change: a successful command is recon, not proof of
    completion.  Even ``echo`` (exit 0) must not mark done."""
    done, msg = execute_tool("terminal", {"command": "echo ok"}, "X")
    assert done is False, "terminal must never assert is_done (Phase 1)"
    assert "ok" in msg


def test_terminal_failing_command_reports_error_not_done():
    """A non-zero exit returns an ERROR result, still not done."""
    done, msg = execute_tool(
        "terminal", {"command": "python -c 'raise SystemExit(3)'"}, "X",
    )
    assert done is False
    assert "ERROR" in msg


def test_read_file_is_never_done(tmp_path):
    """``read_file`` is information-gathering; it never completes a task."""
    item_dir = _item_dir(tmp_path, "X")
    with open(os.path.join(item_dir, "f.py"), "w") as f:
        f.write(_GOOD_CONTENT)
    done, msg = execute_tool("read_file", {"path": "f.py"}, "X")
    assert done is False
    assert "FILE CONTENT" in msg


def test_patch_lands_is_done(tmp_path):
    """``patch`` of an existing file that finds old_string is done (unchanged
    Phase 1 contract)."""
    item_dir = _item_dir(tmp_path, "X")
    path = os.path.join(item_dir, "p.py")
    with open(path, "w") as f:
        f.write("a = 1\n")
    done, msg = execute_tool(
        "patch",
        {"path": "p.py", "old_string": "a = 1", "new_string": "a = 2"},
        "X",
    )
    assert done is True, msg
    assert open(path).read() == "a = 2\n"


def test_patch_missing_old_string_is_not_done(tmp_path):
    item_dir = _item_dir(tmp_path, "X")
    with open(os.path.join(item_dir, "p.py"), "w") as f:
        f.write("a = 1\n")
    done, msg = execute_tool(
        "patch",
        {"path": "p.py", "old_string": "not-here", "new_string": "x"},
        "X",
    )
    assert done is False
    assert "not found" in msg.lower() or "ERROR" in msg


# ---------------------------------------------------------------------------
# P3.2.7 follow-up — relative tool paths anchor at requirements/<item_id>/
# ---------------------------------------------------------------------------

def test_resolve_item_path_absolute_is_rejected():
    """D7: an ABSOLUTE path is rejected outright (it used to pass through)."""
    abs_path = os.path.join(os.sep, "tmp", "whatever", "VERSION")
    with pytest.raises(ValueError, match="absolute path"):
        _resolve_item_path(abs_path, "SCRIPT-01")


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


# ---------------------------------------------------------------------------
# SEC-7 — relative tool paths must not escape requirements/<item_id>/.
# Absolute-path behaviour is deliberately unchanged (policy pending).
# ---------------------------------------------------------------------------

def _item_dir(tmp_path, item_id):
    d = os.path.join(str(tmp_path), "automation-ideas", "requirements", item_id)
    os.makedirs(d, exist_ok=True)
    return d


def test_resolve_item_path_nested_relative_stays_in_item_dir(tmp_path, monkeypatch):
    """A normal nested relative path resolves under the item dir."""
    monkeypatch.chdir(str(tmp_path))
    item_dir = os.path.join(str(tmp_path), "automation-ideas", "requirements", "SEC-1")
    resolved = _resolve_item_path(os.path.join("scripts", "run.sh"), "SEC-1")
    assert resolved == os.path.join(item_dir, "scripts", "run.sh")


def test_resolve_item_path_dotdot_that_stays_inside_is_allowed(tmp_path, monkeypatch):
    """``a/../b`` normalises to ``a``-sibling ``b`` inside the item dir — allowed."""
    monkeypatch.chdir(str(tmp_path))
    item_dir = os.path.join(str(tmp_path), "automation-ideas", "requirements", "SEC-1")
    resolved = _resolve_item_path(os.path.join("a", "..", "b.txt"), "SEC-1")
    assert resolved == os.path.join(item_dir, "b.txt")


def test_resolve_item_path_rejects_parent_escape(tmp_path, monkeypatch):
    """``../x`` would land in requirements/<x> (a sibling item dir) — reject."""
    monkeypatch.chdir(str(tmp_path))
    with pytest.raises(ValueError):
        _resolve_item_path("../x", "SEC-1")


def test_resolve_item_path_rejects_double_parent_escape(tmp_path, monkeypatch):
    """``a/../../x`` normalises to requirements/x — outside the item dir — reject."""
    monkeypatch.chdir(str(tmp_path))
    with pytest.raises(ValueError):
        _resolve_item_path(os.path.join("a", "..", "..", "x"), "SEC-1")


def test_resolve_item_path_absolute_with_dotdot_is_rejected(tmp_path):
    """D7: an absolute path is rejected even when it looks like it stays inside."""
    p = os.path.join(str(tmp_path), "..", "elsewhere.txt")
    with pytest.raises(ValueError, match="absolute path"):
        _resolve_item_path(p, "SEC-1")


def test_write_file_dotdot_escape_is_rejected_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(str(tmp_path))
    item_dir = _item_dir(tmp_path, "SEC-1")
    requirements = os.path.dirname(item_dir)

    done, msg = execute_tool(
        "write_file", {"path": "../escaped.sh", "content": _GOOD_CONTENT}, "SEC-1",
    )
    assert done is False
    assert msg.startswith("ERROR")
    assert not os.path.exists(os.path.join(requirements, "escaped.sh"))
    assert os.listdir(item_dir) == []


def test_write_file_double_dotdot_escape_is_rejected_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(str(tmp_path))
    item_dir = _item_dir(tmp_path, "SEC-1")
    requirements = os.path.dirname(item_dir)

    done, msg = execute_tool(
        "write_file",
        {"path": os.path.join("a", "..", "..", "escaped.sh"), "content": _GOOD_CONTENT},
        "SEC-1",
    )
    assert done is False
    assert msg.startswith("ERROR")
    assert not os.path.exists(os.path.join(requirements, "escaped.sh"))
    assert not os.path.exists(os.path.join(item_dir, "a"))


def test_write_file_nested_relative_still_lands_in_item_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(str(tmp_path))
    item_dir = _item_dir(tmp_path, "SEC-1")
    done, msg = execute_tool(
        "write_file", {"path": "src/tool.sh", "content": _GOOD_CONTENT}, "SEC-1",
    )
    assert done is True, msg
    assert open(os.path.join(item_dir, "src", "tool.sh")).read() == _GOOD_CONTENT


def test_read_file_dotdot_escape_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(str(tmp_path))
    item_dir = _item_dir(tmp_path, "SEC-1")
    secret = os.path.join(os.path.dirname(item_dir), "other.txt")
    with open(secret, "w") as f:
        f.write("not yours")

    done, msg = execute_tool("read_file", {"path": "../other.txt"}, "SEC-1")
    assert done is False
    assert msg.startswith("ERROR")
    assert "not yours" not in msg


def test_patch_dotdot_escape_is_rejected_and_target_untouched(tmp_path, monkeypatch):
    monkeypatch.chdir(str(tmp_path))
    item_dir = _item_dir(tmp_path, "SEC-1")
    victim = os.path.join(os.path.dirname(item_dir), "victim.txt")
    with open(victim, "w") as f:
        f.write("original")

    done, msg = execute_tool(
        "patch",
        {"path": "../victim.txt", "old_string": "original", "new_string": "pwned"},
        "SEC-1",
    )
    assert done is False
    assert msg.startswith("ERROR")
    assert open(victim).read() == "original"


# ---------------------------------------------------------------------------
# D7 / T4 — file tools are confined to requirements/<item_id>/ (realpath).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool,extra", [
    ("write_file", {"content": _GOOD_CONTENT}),
    ("read_file", {}),
    ("patch", {"old_string": "a", "new_string": "b"}),
])
def test_every_file_tool_rejects_absolute_path(tmp_path, tool, extra):
    """T4: an absolute path outside the item dir is rejected by each tool and
    nothing is written or read."""
    _item_dir(tmp_path, "T4")
    outside = tmp_path / "outside.txt"
    outside.write_text("a original secret")
    done, msg = execute_tool(tool, {"path": str(outside), **extra}, "T4")
    assert done is False
    assert msg.startswith("ERROR")
    assert "absolute path" in msg
    assert "secret" not in msg.split("not allowed")[-1]
    assert outside.read_text() == "a original secret"


def test_write_file_absolute_path_inside_item_dir_is_still_rejected(tmp_path):
    """Absolute paths are refused outright, even ones pointing into the item dir."""
    item_dir = _item_dir(tmp_path, "T4")
    target = os.path.join(item_dir, "inside.txt")
    done, msg = execute_tool("write_file", {"path": target, "content": _GOOD_CONTENT}, "T4")
    assert done is False
    assert "absolute path" in msg
    assert not os.path.exists(target)


def test_write_file_relative_in_bounds_still_works(tmp_path):
    item_dir = _item_dir(tmp_path, "T4")
    done, msg = execute_tool(
        "write_file", {"path": "nested/deeper/out.txt", "content": _GOOD_CONTENT}, "T4",
    )
    assert done is True, msg
    assert open(os.path.join(item_dir, "nested", "deeper", "out.txt")).read() == _GOOD_CONTENT


def test_symlinked_dir_in_item_dir_cannot_escape(tmp_path):
    """T4: a symlink inside the item dir that points outside it cannot be used
    to write, read or patch a file outside (realpath-based containment)."""
    item_dir = _item_dir(tmp_path, "T4")
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    (outside / "victim.txt").write_text("original")
    os.symlink(str(outside), os.path.join(item_dir, "link"))

    done, msg = execute_tool(
        "write_file", {"path": "link/new.txt", "content": _GOOD_CONTENT}, "T4",
    )
    assert done is False and msg.startswith("ERROR"), msg
    assert "escapes" in msg
    assert not (outside / "new.txt").exists()

    done, msg = execute_tool("read_file", {"path": "link/victim.txt"}, "T4")
    assert done is False and msg.startswith("ERROR")
    assert "original" not in msg

    done, msg = execute_tool(
        "patch", {"path": "link/victim.txt", "old_string": "original", "new_string": "pwned"}, "T4",
    )
    assert done is False and msg.startswith("ERROR")
    assert (outside / "victim.txt").read_text() == "original"


def test_symlinked_file_in_item_dir_cannot_escape(tmp_path):
    """A file symlink (including a dangling one) pointing outside is refused,
    so write_file cannot create or overwrite the link target."""
    item_dir = _item_dir(tmp_path, "T4")
    target = tmp_path / "victim.txt"
    target.write_text("original")
    os.symlink(str(target), os.path.join(item_dir, "f.txt"))
    dangling_target = tmp_path / "created_by_link.txt"
    os.symlink(str(dangling_target), os.path.join(item_dir, "dangling.txt"))

    done, msg = execute_tool("write_file", {"path": "f.txt", "content": _GOOD_CONTENT}, "T4")
    assert done is False and "escapes" in msg
    assert target.read_text() == "original"

    done, msg = execute_tool("write_file", {"path": "dangling.txt", "content": _GOOD_CONTENT}, "T4")
    assert done is False and "escapes" in msg
    assert not dangling_target.exists()


def test_symlink_that_stays_inside_item_dir_is_allowed(tmp_path):
    """A symlink whose real target is inside the item dir is fine."""
    item_dir = _item_dir(tmp_path, "T4")
    os.makedirs(os.path.join(item_dir, "real"))
    os.symlink(os.path.join(item_dir, "real"), os.path.join(item_dir, "alias"))
    done, msg = execute_tool("write_file", {"path": "alias/x.txt", "content": _GOOD_CONTENT}, "T4")
    assert done is True, msg
    assert os.path.isfile(os.path.join(item_dir, "real", "x.txt"))


def test_symlinked_item_dir_cannot_widen_the_sandbox(tmp_path):
    """If requirements/<id> itself is a symlink to somewhere else, refuse."""
    root = tmp_path / "automation-ideas" / "requirements"
    root.mkdir(parents=True, exist_ok=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    os.symlink(str(elsewhere), str(root / "T4LINK"))
    done, msg = execute_tool("write_file", {"path": "x.txt", "content": _GOOD_CONTENT}, "T4LINK")
    assert done is False and msg.startswith("ERROR")
    assert not (elsewhere / "x.txt").exists()


@pytest.mark.parametrize("bad_id", ["..", ".", "", "a/b", "../SEC-1"])
def test_hostile_item_id_is_rejected(tmp_path, bad_id):
    _item_dir(tmp_path, "SEC-1")
    with pytest.raises(ValueError):
        _resolve_item_path("x.txt", bad_id)


def test_dotdot_back_into_item_dir_is_allowed(tmp_path):
    """``../<same id>/x`` resolves inside the item dir, so it is allowed."""
    item_dir = _item_dir(tmp_path, "T4")
    resolved = _resolve_item_path(os.path.join("..", "T4", "x.txt"), "T4")
    assert resolved == os.path.join(os.path.realpath(item_dir), "x.txt")


def test_dotdot_to_item_dir_itself_then_write_fails_cleanly(tmp_path):
    """Writing to the item dir itself (``.``) is inside, but it is a
    directory, so write_file returns an ERROR rather than raising."""
    _item_dir(tmp_path, "T4")
    done, msg = execute_tool("write_file", {"path": ".", "content": _GOOD_CONTENT}, "T4")
    assert done is False and msg.startswith("ERROR")


# ---------------------------------------------------------------------------
# D7 — terminal: no shell, program allowlist.
# ---------------------------------------------------------------------------

from agents import executor_tools as _et  # noqa: E402


def test_terminal_allowed_program_runs():
    done, msg = execute_tool("terminal", {"command": "echo hello world"}, "X")
    assert done is False
    assert msg.startswith("TOOL RESULT (terminal):")
    assert "hello world" in msg


def test_terminal_python_runs():
    done, msg = execute_tool("terminal", {"command": "python3 -c 'print(6*7)'"}, "X")
    assert "42" in msg and not msg.startswith("ERROR"), msg


def test_terminal_git_status_runs():
    """``git status`` is allowed; it runs from the process cwd (the repo)."""
    done, msg = execute_tool("terminal", {"command": "git status --short"}, "X")
    assert done is False
    assert "rejected" not in msg, msg


@pytest.mark.parametrize("cmd", ["git log -1 --oneline", "git diff --stat"])
def test_terminal_git_read_only_subcommands_are_accepted(cmd):
    argv, reason = _et._terminal_argv(cmd)
    assert argv and reason == ""


@pytest.mark.parametrize("cmd", [
    "git push",
    "git push origin main",
    "git commit -m x",
    "git reset --hard",
    "git",
    "git -c core.pager=sh status",
    "git diff --output=/tmp/x",
    "git diff --ext-diff",
    "git log --exec=sh",
])
def test_terminal_git_disallowed_forms_are_rejected(cmd):
    done, msg = execute_tool("terminal", {"command": cmd}, "X")
    assert done is False
    assert msg.startswith("ERROR: terminal command rejected"), msg


@pytest.mark.parametrize("cmd", [
    "rm -rf /tmp/nothing-here",
    "sh -c 'echo hi'",
    "bash -c 'echo hi'",
    "curl http://example.com",
    "/bin/echo hi",
    "./echo hi",
    "env echo hi",
    "sudo ls",
])
def test_terminal_disallowed_program_is_rejected(cmd):
    done, msg = execute_tool("terminal", {"command": cmd}, "X")
    assert done is False
    assert msg.startswith("ERROR: terminal command rejected"), msg
    assert "not allowed" in msg


def test_terminal_rm_is_rejected_and_not_run(tmp_path):
    victim = tmp_path / "keep.txt"
    victim.write_text("x")
    done, msg = execute_tool("terminal", {"command": f"rm {victim}"}, "X")
    assert msg.startswith("ERROR: terminal command rejected")
    assert victim.exists()


@pytest.mark.parametrize("cmd", ["echo 'unterminated", 'echo "half', "echo trailing\\"])
def test_terminal_parse_error_is_rejected(cmd):
    done, msg = execute_tool("terminal", {"command": cmd}, "X")
    assert done is False
    assert msg.startswith("ERROR: terminal command rejected: could not parse"), msg


@pytest.mark.parametrize("cmd", ["", "   ", None, 123, ["echo", "hi"]])
def test_terminal_empty_or_non_string_is_rejected(cmd):
    done, msg = execute_tool("terminal", {"command": cmd}, "X")
    assert done is False
    assert msg.startswith("ERROR: terminal command rejected"), msg


@pytest.mark.parametrize("cmd", [
    "echo hi | cat",
    "echo hi || echo no",
    "echo hi ; rm -rf x",
    "echo hi && rm -rf x",
    "echo hi > out.txt",
    "echo hi >> out.txt",
    "cat < /etc/hosts",
    "echo hi 2>&1",
    "echo hi &",
])
def test_terminal_shell_operator_tokens_are_rejected(cmd, tmp_path, monkeypatch):
    monkeypatch.chdir(str(tmp_path))
    done, msg = execute_tool("terminal", {"command": cmd}, "X")
    assert done is False
    assert msg.startswith("ERROR: terminal command rejected: shell operator"), msg
    assert not (tmp_path / "out.txt").exists()


@pytest.mark.parametrize("cmd,literal", [
    ("echo a;rm", "a;rm"),
    ("echo $(whoami)", "$(whoami)"),
    ("echo `whoami`", "`whoami`"),
    ("echo $HOME", "$HOME"),
    ("echo hi>out.txt", "hi>out.txt"),
    ("echo 'a | b'", "a | b"),
])
def test_terminal_metacharacters_never_reach_a_shell(cmd, literal, tmp_path, monkeypatch):
    """Glued metacharacters are not split out as operators; with no shell they
    are passed to the program verbatim and have no effect."""
    monkeypatch.chdir(str(tmp_path))
    done, msg = execute_tool("terminal", {"command": cmd}, "X")
    assert not msg.startswith("ERROR"), msg
    assert literal in msg
    assert not (tmp_path / "out.txt").exists()


def test_terminal_uses_argv_and_no_shell(monkeypatch):
    """Pin the subprocess call: argv list, shell=False, 300 s timeout."""
    seen = {}

    class _P:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(argv, **kw):
        seen["argv"] = argv
        seen.update(kw)
        return _P()

    monkeypatch.setattr(_et.subprocess, "run", fake_run)
    execute_tool("terminal", {"command": "pytest -q 'tests/a b.py'"}, "X")
    assert seen["argv"] == ["pytest", "-q", "tests/a b.py"]
    assert seen["shell"] is False
    assert seen["timeout"] == 300


def test_terminal_rejected_command_never_calls_subprocess(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("subprocess.run must not be called for a rejected command")

    monkeypatch.setattr(_et.subprocess, "run", boom)
    done, msg = execute_tool("terminal", {"command": "rm -rf /"}, "X")
    assert msg.startswith("ERROR: terminal command rejected")


def test_terminal_timeout_returns_error(monkeypatch):
    import subprocess as _sp

    def fake_run(argv, **kw):
        raise _sp.TimeoutExpired(argv, kw.get("timeout"))

    monkeypatch.setattr(_et.subprocess, "run", fake_run)
    done, msg = execute_tool("terminal", {"command": "python -c 'while True: pass'"}, "X")
    assert done is False and msg.startswith("ERROR")


def test_tools_description_mentions_no_shell_and_relative_paths():
    desc = _et.get_tools_description()
    assert "no shell" in desc
    assert "RELATIVE" in desc


# ---------------------------------------------------------------------------
# P1-2 — the terminal tool runs with a minimal environment (no secrets).
# ---------------------------------------------------------------------------

def test_terminal_subprocess_env_has_path_but_not_secrets(monkeypatch):
    """P1-2: model-chosen ``python -c`` code must not be able to read the API
    token or provider keys from the subprocess environment.  The child gets
    PATH (and the other safe vars) but nothing secret, and not HOME."""
    monkeypatch.setenv("FAKE_SECRET_TOKEN", "not-a-real-secret")
    monkeypatch.setenv("FAKE_PROVIDER_API_KEY", "not-a-real-key")
    done, msg = execute_tool(
        "terminal",
        {"command": "python3 -c 'import os; print(sorted(os.environ))'"},
        "X",
    )
    assert not msg.startswith("ERROR"), msg
    body = msg.split("TOOL RESULT (terminal):\n", 1)[1].strip()
    names = set(ast.literal_eval(body))
    assert "PATH" in names, f"PATH missing from terminal env: {sorted(names)}"
    assert "FAKE_SECRET_TOKEN" not in names
    assert "FAKE_PROVIDER_API_KEY" not in names
    assert "HOME" not in names


def test_terminal_env_is_minimal_and_resolved_at_call_time(monkeypatch):
    """Only PATH / LANG / LC_ALL / TMPDIR cross the boundary, values resolved
    from ``os.environ`` at call time (PATH set here, after module import)."""
    monkeypatch.setenv("FAKE_SECRET_TOKEN", "not-a-real-secret")
    monkeypatch.setenv("PATH", "/fake/bin")
    monkeypatch.setenv("LANG", "C")
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("TMPDIR", raising=False)
    env = _et._terminal_env()
    assert set(env) == {"PATH", "LANG"}
    assert env["PATH"] == "/fake/bin"
    assert env["LANG"] == "C"


def test_terminal_passes_minimal_env_to_subprocess(monkeypatch):
    """The subprocess.run call itself carries the minimal env."""
    seen = {}

    class _P:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(argv, **kw):
        seen.update(kw)
        return _P()

    monkeypatch.setattr(_et.subprocess, "run", fake_run)
    monkeypatch.setenv("FAKE_SECRET_TOKEN", "not-a-real-secret")
    execute_tool("terminal", {"command": "echo hi"}, "X")
    assert "FAKE_SECRET_TOKEN" not in seen["env"]
    assert "PATH" in seen["env"]


def test_terminal_allowed_commands_still_run_with_minimal_env():
    """P1-2 must not break the allowlisted programs themselves."""
    done, msg = execute_tool("terminal", {"command": "python3 -c 'print(6*7)'"}, "X")
    assert not msg.startswith("ERROR"), msg
    assert "42" in msg
    done, msg = execute_tool("terminal", {"command": "echo still works"}, "X")
    assert "still works" in msg and not msg.startswith("ERROR"), msg
