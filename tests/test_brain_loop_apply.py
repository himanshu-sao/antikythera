import os
import pytest
from importlib import reload

def test_apply_approved_updates(tmp_path, monkeypatch):
    import agents.brain_loop as bl_mod
    # Redirect the paths used by the module to temporary files
    pending_path = tmp_path / "pending-updates.md"
    patterns_path = tmp_path / "patterns.md"
    history_dir = tmp_path / "history"
    monkeypatch.setattr(bl_mod, "PENDING_UPDATES_FILE", str(pending_path))
    monkeypatch.setattr(bl_mod, "PATTERNS_FILE", str(patterns_path))
    monkeypatch.setattr(bl_mod, "HISTORY_DIR", str(history_dir))
    # Write a pending file with one approved and one unapproved block
    pending_content = (
        "**What to add:** New pattern A\n"
        "---\n"
        "**What to add:** New pattern B\n"
        "**review_status:** APPROVED\n"
        "---\n"
    )
    pending_path.write_text(pending_content)
    # Ensure patterns file exists initially
    patterns_path.write_text("# Existing patterns\n")
    # Run apply_approved_updates
    applied = bl_mod.apply_approved_updates()
    assert applied == 1
    # Verify the new pattern appears in the patterns file
    updated = patterns_path.read_text()
    assert "New pattern B" in updated
    # Verify the pending file was cleared (contains the placeholder header)
    cleared = pending_path.read_text()
    assert "Processed Updates" in cleared
    # Verify a history file was created
    history_files = list(history_dir.iterdir())
    assert len(history_files) == 1
    # Ensure the history file contains the original patterns header
    archive_content = history_files[0].read_text()
    assert "Existing patterns" in archive_content
