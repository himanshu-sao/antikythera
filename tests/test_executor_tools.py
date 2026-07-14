"""Unit tests for ``agents.executor_tools.get_workspace_files`` (P3.2.2).

Verifies the function returns a *bounded, relevant* file set (<= the cap),
excludes build/cache/dependency dirs, is sorted, and stays deterministic
under a controlled temp tree instead of depending on the real repo layout.
"""
import os

from agents.executor_tools import get_workspace_files, WORKSPACE_FILES_CAP


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
