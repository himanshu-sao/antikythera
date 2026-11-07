"""Tests for scripts/backup_data.sh.

Every test uses tmp_path for both the source and the backup directory, so the real
automation-ideas/ data is never read or written.
"""

import os
import stat
import subprocess
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "backup_data.sh"


def _run(args, backup_dir, env_extra=None):
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(backup_dir.parent),
        "ANTIKYTHERA_BACKUP_DIR": str(backup_dir),
    }
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


@pytest.fixture
def source(tmp_path):
    src = tmp_path / "src-ideas"
    (src / "requirements" / "ID-001").mkdir(parents=True)
    (src / "requirements" / "ID-001" / "spec.md").write_text("spec\n")
    (src / "pipeline-state.json").write_text("{}\n")
    (src / ".vault.key").write_text("not-a-real-key\n")
    (src / "pipeline-state.json.lock").write_text("")
    (src / "brain").mkdir()
    (src / "brain" / "patterns.md.lock").write_text("")
    (src / "pipeline-state.json.corrupt-20260101").write_text("{bad")
    return src


@pytest.fixture
def backup_dir(tmp_path):
    return tmp_path / "backups"


def _archives(backup_dir):
    return sorted(p for p in backup_dir.glob("automation-ideas-*.tar.gz"))


def _names(archive):
    with tarfile.open(archive, "r:gz") as tf:
        return tf.getnames()


def test_writes_archive_with_0600_mode(source, backup_dir):
    result = _run([str(source)], backup_dir)
    assert result.returncode == 0, result.stderr
    archives = _archives(backup_dir)
    assert len(archives) == 1
    mode = stat.S_IMODE(archives[0].stat().st_mode)
    assert mode == 0o600


def test_archive_name_is_utc_timestamped(source, backup_dir):
    _run([str(source)], backup_dir)
    (archive,) = _archives(backup_dir)
    name = archive.name
    assert name.startswith("automation-ideas-")
    assert name.endswith(".tar.gz")
    stamp = name[len("automation-ideas-"):-len(".tar.gz")]
    assert len(stamp) == len("20260101T000000Z")
    assert stamp.endswith("Z") and stamp[8] == "T"


def test_includes_dotfiles(source, backup_dir):
    _run([str(source)], backup_dir)
    (archive,) = _archives(backup_dir)
    names = _names(archive)
    assert any(n.endswith("/.vault.key") for n in names), names


def test_excludes_lock_files(source, backup_dir):
    _run([str(source)], backup_dir)
    (archive,) = _archives(backup_dir)
    names = _names(archive)
    assert not any(n.endswith(".lock") for n in names), names
    # the real data is still there
    assert any(n.endswith("requirements/ID-001/spec.md") for n in names), names
    assert any(n.endswith("pipeline-state.json") for n in names), names


def test_keeps_corrupt_backups(source, backup_dir):
    _run([str(source)], backup_dir)
    (archive,) = _archives(backup_dir)
    assert any(".corrupt-" in n for n in _names(archive))


def test_archive_has_no_macos_metadata_entries(source, backup_dir):
    _run([str(source)], backup_dir)
    (archive,) = _archives(backup_dir)
    names = _names(archive)
    assert not any("/._" in n or n.startswith("._") for n in names), names
    # entries are relative to the source dir, so they restore cleanly with -C DEST
    assert all(n == "." or n.startswith("./") for n in names), names


def test_restore_roundtrip_matches_source(source, backup_dir, tmp_path):
    _run([str(source)], backup_dir)
    (archive,) = _archives(backup_dir)
    dest = tmp_path / "restored"
    dest.mkdir()
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(dest, filter="data")
    assert (dest / ".vault.key").read_text() == "not-a-real-key\n"
    assert (dest / "requirements" / "ID-001" / "spec.md").read_text() == "spec\n"
    assert not (dest / "pipeline-state.json.lock").exists()


def test_rotation_keeps_newest_n(source, backup_dir):
    backup_dir.mkdir(parents=True)
    for i in range(6):
        (backup_dir / f"automation-ideas-2025010{i}T000000Z.tar.gz").write_bytes(b"old")
    result = _run([str(source)], backup_dir, {"ANTIKYTHERA_BACKUP_KEEP": "3"})
    assert result.returncode == 0, result.stderr
    remaining = [p.name for p in _archives(backup_dir)]
    assert len(remaining) == 3
    # the new archive is newest, plus the two newest pre-seeded ones
    assert remaining[-1].startswith("automation-ideas-2026")
    assert remaining[:2] == [
        "automation-ideas-20250104T000000Z.tar.gz",
        "automation-ideas-20250105T000000Z.tar.gz",
    ]


def test_rotation_default_keep_is_14(source, backup_dir):
    backup_dir.mkdir(parents=True)
    for i in range(20):
        (backup_dir / f"automation-ideas-2024{i:02d}01T000000Z.tar.gz").write_bytes(b"old")
    result = _run([str(source)], backup_dir)
    assert result.returncode == 0, result.stderr
    assert len(_archives(backup_dir)) == 14


def test_rotation_ignores_unrelated_files(source, backup_dir):
    backup_dir.mkdir(parents=True)
    other = backup_dir / "notes.txt"
    other.write_text("keep me")
    for i in range(3):
        (backup_dir / f"automation-ideas-2024010{i}T000000Z.tar.gz").write_bytes(b"old")
    result = _run([str(source)], backup_dir, {"ANTIKYTHERA_BACKUP_KEEP": "1"})
    assert result.returncode == 0, result.stderr
    assert other.read_text() == "keep me"
    assert len(_archives(backup_dir)) == 1


def test_missing_source_fails_nonzero(tmp_path, backup_dir):
    missing = tmp_path / "does-not-exist"
    result = _run([str(missing)], backup_dir)
    assert result.returncode == 2
    assert "source directory not found" in result.stderr
    assert not backup_dir.exists() or _archives(backup_dir) == []


def test_too_many_arguments_fails(source, backup_dir):
    result = _run([str(source), "extra"], backup_dir)
    assert result.returncode == 1


@pytest.mark.parametrize("bad", ["abc", "0", "-1", "3.5"])
def test_invalid_keep_value_is_rejected(source, backup_dir, bad):
    result = _run([str(source)], backup_dir, {"ANTIKYTHERA_BACKUP_KEEP": bad})
    assert result.returncode == 1
    assert not backup_dir.exists() or _archives(backup_dir) == []


def test_empty_keep_value_uses_default(source, backup_dir):
    result = _run([str(source)], backup_dir, {"ANTIKYTHERA_BACKUP_KEEP": ""})
    assert result.returncode == 0, result.stderr
    assert len(_archives(backup_dir)) == 1


def test_backup_dir_inside_source_is_rejected(source):
    inside = source / "backups"
    result = _run([str(source)], inside)
    assert result.returncode == 1
    assert "must not be inside the source" in result.stderr


def test_source_is_not_modified(source, backup_dir):
    before = sorted(str(p.relative_to(source)) for p in source.rglob("*"))
    _run([str(source)], backup_dir)
    after = sorted(str(p.relative_to(source)) for p in source.rglob("*"))
    assert before == after
    assert (source / ".vault.key").read_text() == "not-a-real-key\n"


def test_two_runs_in_same_second_keep_the_newer_archive(source, backup_dir):
    # Regression: a same-second collision used to name the second archive
    # "<stamp>-1.tar.gz", which sorts BEFORE "<stamp>.tar.gz", so with KEEP=1 rotation
    # deleted the newer archive. Each run must get a unique, correctly ordered name.
    first = _run([str(source)], backup_dir, {"ANTIKYTHERA_BACKUP_KEEP": "10"})
    second = _run([str(source)], backup_dir, {"ANTIKYTHERA_BACKUP_KEEP": "10"})
    assert first.returncode == 0 and second.returncode == 0
    archives = [p.name for p in _archives(backup_dir)]
    assert len(archives) == 2
    assert len(set(archives)) == 2
    assert all(a.count("Z") == 1 and a.endswith("Z.tar.gz") for a in archives), archives


def test_keep_one_retains_latest_after_back_to_back_runs(source, backup_dir):
    _run([str(source)], backup_dir)
    _run([str(source)], backup_dir)
    result = _run([str(source)], backup_dir, {"ANTIKYTHERA_BACKUP_KEEP": "1"})
    assert result.returncode == 0, result.stderr
    (remaining,) = _archives(backup_dir)
    # the run that just finished must be the survivor
    assert remaining.name == max(p.name for p in backup_dir.glob("automation-ideas-*.tar.gz"))
    assert remaining.name in result.stdout
