"""
Tests for the Audit Agent (agents/audit.py).
"""

import os
import tempfile
import pytest
from unittest.mock import patch

from agents import audit


class TestGetAuditPath:
    def test_get_audit_path_returns_string(self):
        """get_audit_path should return a string path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.audit.AUDIT_DIR", tmpdir):
                path = audit.get_audit_path("2026-05-14")
                assert isinstance(path, str)
                assert path.endswith("2026-05-14.md")

    def test_get_audit_path_creates_directory(self):
        """get_audit_path should create the audit directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_dir = os.path.join(tmpdir, "audit")
            with patch("agents.audit.AUDIT_DIR", audit_dir):
                assert not os.path.exists(audit_dir)
                path = audit.get_audit_path("2026-05-14")
                assert os.path.isdir(audit_dir)
                # The file itself is created by log_action, not get_audit_path
                assert path.endswith("2026-05-14.md")

    def test_get_audit_path_default_date(self):
        """get_audit_path should use today's date when date_str is None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.audit.AUDIT_DIR", tmpdir):
                path = audit.get_audit_path()
                # Should contain today's date
                import datetime
                today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
                assert today in path


class TestLogAction:
    def test_log_action_creates_file(self):
        """log_action should create the audit file if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.audit.AUDIT_DIR", tmpdir):
                audit.log_action(
                    agent_name="architect",
                    idea_id="ID-001",
                    stage="ARCHITECTURE",
                    action="Generated architecture.md",
                )
                # Check file was created
                import datetime
                today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
                file_path = os.path.join(tmpdir, f"{today}.md")
                assert os.path.isfile(file_path)

    def test_log_action_writes_entry(self):
        """log_action should write a structured entry to the audit file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.audit.AUDIT_DIR", tmpdir):
                audit.log_action(
                    agent_name="tester",
                    idea_id="ID-002",
                    stage="TESTING",
                    action="Generated tests.md",
                    inputs="spec.md, architecture.md",
                    outputs="tests.md",
                )
                import datetime
                today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
                file_path = os.path.join(tmpdir, f"{today}.md")
                with open(file_path, "r") as f:
                    content = f.read()

                # Check header
                assert f"Audit Log — {today}" in content
                # Check entry fields
                assert "tester" in content
                assert "ID-002" in content
                assert "TESTING" in content
                assert "Generated tests.md" in content
                assert "spec.md, architecture.md" in content
                assert "tests.md" in content

    def test_log_action_appends_multiple_entries(self):
        """log_action should append multiple entries to the same file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.audit.AUDIT_DIR", tmpdir):
                audit.log_action("architect", "ID-001", "ARCHITECTURE", "Action 1")
                audit.log_action("tester", "ID-002", "TESTING", "Action 2")

                import datetime
                today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
                file_path = os.path.join(tmpdir, f"{today}.md")
                with open(file_path, "r") as f:
                    content = f.read()

                assert content.count("---") == 2  # Two entries
                assert "Action 1" in content
                assert "Action 2" in content

    def test_log_action_handles_none_inputs_outputs(self):
        """log_action should handle None inputs and outputs gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.audit.AUDIT_DIR", tmpdir):
                # Should not raise
                audit.log_action(
                    agent_name="refiner",
                    idea_id="ID-003",
                    stage="REFINEMENT",
                    action="Refined idea",
                )
                import datetime
                today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
                file_path = os.path.join(tmpdir, f"{today}.md")
                with open(file_path, "r") as f:
                    content = f.read()

                assert "None" in content

    def test_log_action_handles_write_error(self):
        """log_action should not raise on write errors."""
        with patch("agents.audit.AUDIT_DIR", "/nonexistent/path"):
            # Should not raise
            audit.log_action(
                agent_name="architect",
                idea_id="ID-001",
                stage="ARCHITECTURE",
                action="Test",
            )


class TestLogStageTransition:
    def test_log_stage_transition_formats_action(self):
        """log_stage_transition should format the action correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.audit.AUDIT_DIR", tmpdir):
                audit.log_stage_transition(
                    agent_name="orchestrator",
                    idea_id="ID-001",
                    from_stage="ARCHITECTURE",
                    to_stage="REVIEW_ARCH",
                )
                import datetime
                today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
                file_path = os.path.join(tmpdir, f"{today}.md")
                with open(file_path, "r") as f:
                    content = f.read()

                assert "Stage transition" in content
                assert "ARCHITECTURE" in content
                assert "REVIEW_ARCH" in content

    def test_log_stage_transition_accepts_inputs_outputs(self):
        """log_stage_transition should accept optional inputs and outputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.audit.AUDIT_DIR", tmpdir):
                audit.log_stage_transition(
                    agent_name="orchestrator",
                    idea_id="ID-001",
                    from_stage="REFINEMENT",
                    to_stage="REVIEW_SPEC",
                    inputs="spec.md",
                    outputs="review.md",
                )
                import datetime
                today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
                file_path = os.path.join(tmpdir, f"{today}.md")
                with open(file_path, "r") as f:
                    content = f.read()

                assert "spec.md" in content
                assert "review.md" in content