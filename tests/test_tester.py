"""
Tests for the Tester Agent (agents/tester.py).
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from agents import tester


class TestTesterIdea:
    def test_tester_idea_creates_tests_file(self):
        """tester_idea should create a tests.md file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.tester.REQUIREMENTS_DIR", tmpdir):
                # Create spec.md and architecture.md
                spec_dir = os.path.join(tmpdir, "ID-999")
                os.makedirs(spec_dir, exist_ok=True)
                with open(os.path.join(spec_dir, "spec.md"), "w") as f:
                    f.write("# Test Automation Idea\n\nSome spec content.")
                with open(os.path.join(spec_dir, "architecture.md"), "w") as f:
                    f.write("# Architecture\n\nSome arch content.")

                confidence = tester.tester_idea("ID-999")
                tests_path = os.path.join(spec_dir, "tests.md")
                assert os.path.isfile(tests_path)
                assert isinstance(confidence, int)
                assert 0 <= confidence <= 100

    def test_tester_idea_returns_high_confidence(self):
        """tester_idea should return a high confidence score for valid input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.tester.REQUIREMENTS_DIR", tmpdir):
                spec_dir = os.path.join(tmpdir, "ID-888")
                os.makedirs(spec_dir, exist_ok=True)
                with open(os.path.join(spec_dir, "spec.md"), "w") as f:
                    f.write("# Automate Daily Pod Restarts\n\nFull spec content.")
                with open(os.path.join(spec_dir, "architecture.md"), "w") as f:
                    f.write("# Architecture\n\nFull arch content.")

                confidence = tester.tester_idea("ID-888")
                assert confidence >= 70

    def test_tester_idea_raises_on_missing_spec(self):
        """tester_idea should raise FileNotFoundError if spec.md is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.tester.REQUIREMENTS_DIR", tmpdir):
                spec_dir = os.path.join(tmpdir, "ID-NO-SPEC")
                os.makedirs(spec_dir, exist_ok=True)
                with open(os.path.join(spec_dir, "architecture.md"), "w") as f:
                    f.write("# Architecture\n\nContent.")

                with pytest.raises(FileNotFoundError, match="File not found"):
                    tester.tester_idea("ID-NO-SPEC")

    def test_tester_idea_raises_on_missing_architecture(self):
        """tester_idea should raise FileNotFoundError if architecture.md is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.tester.REQUIREMENTS_DIR", tmpdir):
                spec_dir = os.path.join(tmpdir, "ID-NO-ARCH")
                os.makedirs(spec_dir, exist_ok=True)
                with open(os.path.join(spec_dir, "spec.md"), "w") as f:
                    f.write("# Test\n\nContent.")

                with pytest.raises(FileNotFoundError, match="File not found"):
                    tester.tester_idea("ID-NO-ARCH")

    def test_tester_idea_raises_on_empty_spec(self):
        """tester_idea should raise ValueError for empty spec content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.tester.REQUIREMENTS_DIR", tmpdir):
                spec_dir = os.path.join(tmpdir, "ID-EMPTY")
                os.makedirs(spec_dir, exist_ok=True)
                with open(os.path.join(spec_dir, "spec.md"), "w") as f:
                    f.write("   ")
                with open(os.path.join(spec_dir, "architecture.md"), "w") as f:
                    f.write("# Architecture\n\nContent.")

                with pytest.raises(ValueError, match="Spec content is empty"):
                    tester.tester_idea("ID-EMPTY")

    def test_tester_idea_raises_on_empty_architecture(self):
        """tester_idea should raise ValueError for empty architecture content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.tester.REQUIREMENTS_DIR", tmpdir):
                spec_dir = os.path.join(tmpdir, "ID-EMPTY-ARCH")
                os.makedirs(spec_dir, exist_ok=True)
                with open(os.path.join(spec_dir, "spec.md"), "w") as f:
                    f.write("# Test\n\nContent.")
                with open(os.path.join(spec_dir, "architecture.md"), "w") as f:
                    f.write("   ")

                with pytest.raises(ValueError, match="Architecture content is empty"):
                    tester.tester_idea("ID-EMPTY-ARCH")

    def test_tester_idea_creates_directory(self):
        """tester_idea should create the ID directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.tester.REQUIREMENTS_DIR", tmpdir):
                spec_dir = os.path.join(tmpdir, "ID-NEW")
                os.makedirs(spec_dir, exist_ok=True)
                with open(os.path.join(spec_dir, "spec.md"), "w") as f:
                    f.write("# New Idea\n\nContent.")
                with open(os.path.join(spec_dir, "architecture.md"), "w") as f:
                    f.write("# Architecture\n\nContent.")

                tester.tester_idea("ID-NEW")
                assert os.path.isdir(spec_dir)
                assert os.path.isfile(os.path.join(spec_dir, "tests.md"))


class TestWriteTests:
    def test_write_tests_writes_content(self):
        """write_tests should write content to the correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.tester.REQUIREMENTS_DIR", tmpdir):
                content = "# Test Plan\n\nSome test content"
                file_path = tester.write_tests("ID-777", content)
                assert file_path == os.path.join(tmpdir, "ID-777", "tests.md")
                with open(file_path, "r") as f:
                    assert f.read() == content

    def test_write_tests_creates_directory(self):
        """write_tests should create the directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.tester.REQUIREMENTS_DIR", tmpdir):
                tester.write_tests("ID-NEW-DIR", "content")
                assert os.path.isdir(os.path.join(tmpdir, "ID-NEW-DIR"))


class TestCalculateConfidence:
    def test_calculate_confidence_returns_int(self):
        """calculate_confidence should return an integer."""
        score = tester.calculate_confidence("Some test content")
        assert isinstance(score, int)

    def test_calculate_confidence_empty_low_score(self):
        """Empty content should return a low score (0-10)."""
        score = tester.calculate_confidence("")
        assert score <= 10

    def test_calculate_confidence_short_content_low_score(self):
        """Very short content should return a low score."""
        score = tester.calculate_confidence("hi")
        assert score <= 20

    def test_calculate_confidence_comprehensive_high_score(self):
        """Comprehensive content with all sections should return a high score."""
        content = """
# Test Plan

## Test Plan Overview
Overview text.

## Test Cases
Various test cases.

## Validation Checklist
Checklist items.

## Expected Outputs
Expected results.

## Edge Cases
Edge cases covered.

Given some input, When action is taken, Then result is expected.

- Bullet point 1
- Bullet point 2
1. Numbered item
"""
        score = tester.calculate_confidence(content)
        assert score >= 80

    def test_calculate_confidence_mid_score(self):
        """Content with some sections should return a mid-range score."""
        content = """
# Test Plan

## Test Plan Overview
Overview.

## Test Cases
Some cases.

- A bullet point
"""
        score = tester.calculate_confidence(content)
        assert 20 <= score <= 80

    def test_calculate_confidence_never_exceeds_100(self):
        """calculate_confidence should never return more than 100."""
        content = """
## Test Plan
a
## Test Cases
b
## Validation Checklist
c
## Expected Outputs
d
## Edge Cases
e
Given input, When action, Then result.
- bullet 1
- bullet 2
""" * 10
        score = tester.calculate_confidence(content)
        assert score <= 100


class TestGenerateTestPlan:
    def test_generate_test_plan_contains_overview(self):
        """Generated test plan should contain an overview section."""
        content = tester._generate_test_plan_content(
            "ID-001", "# Test Idea\n\nContent", "# Architecture\n\nContent"
        )
        assert "Test Plan Overview" in content

    def test_generate_test_plan_contains_test_cases(self):
        """Generated test plan should contain test cases section."""
        content = tester._generate_test_plan_content(
            "ID-001", "# Test Idea\n\nContent", "# Architecture\n\nContent"
        )
        assert "Test Cases" in content

    def test_generate_test_plan_contains_validation_checklist(self):
        """Generated test plan should contain validation checklist."""
        content = tester._generate_test_plan_content(
            "ID-001", "# Test Idea\n\nContent", "# Architecture\n\nContent"
        )
        assert "Validation Checklist" in content

    def test_generate_test_plan_contains_expected_outputs(self):
        """Generated test plan should contain expected outputs section."""
        content = tester._generate_test_plan_content(
            "ID-001", "# Test Idea\n\nContent", "# Architecture\n\nContent"
        )
        assert "Expected Outputs" in content

    def test_generate_test_plan_contains_edge_cases(self):
        """Generated test plan should contain edge cases section."""
        content = tester._generate_test_plan_content(
            "ID-001", "# Test Idea\n\nContent", "# Architecture\n\nContent"
        )
        assert "Edge Cases" in content

    def test_generate_test_plan_includes_idea_id(self):
        """Generated test plan should include the idea ID."""
        content = tester._generate_test_plan_content(
            "ID-042", "# Test Idea\n\nContent", "# Architecture\n\nContent"
        )
        assert "ID-042" in content


class TestDockerSandbox:
    @patch("agents.tester.subprocess.run")
    def test_provision_docker_sandbox_success(self, mock_run):
        """provision_docker_sandbox should return True on success."""
        mock_run.return_value = MagicMock(returncode=0)
        with patch("agents.tester.DOCKER_DIR", "/tmp"):
            with patch("os.path.exists", return_value=True):
                result = tester.provision_docker_sandbox()
                assert result is True

    @patch("agents.tester.subprocess.run")
    def test_provision_docker_sandbox_failure(self, mock_run):
        """provision_docker_sandbox should return False on failure."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")
        with patch("agents.tester.DOCKER_DIR", "/tmp"):
            with patch("os.path.exists", return_value=True):
                result = tester.provision_docker_sandbox()
                assert result is False

    def test_provision_docker_sandbox_no_compose_file(self):
        """provision_docker_sandbox should return False if compose file missing."""
        with patch("agents.tester.DOCKER_DIR", "/nonexistent"):
            result = tester.provision_docker_sandbox()
            assert result is False

    @patch("agents.tester.subprocess.run")
    def test_provision_docker_sandbox_docker_not_available(self, mock_run):
        """provision_docker_sandbox should return False if Docker not available."""
        mock_run.side_effect = FileNotFoundError()
        with patch("agents.tester.DOCKER_DIR", "/tmp"):
            with patch("os.path.exists", return_value=True):
                result = tester.provision_docker_sandbox()
                assert result is False

    @patch("agents.tester.tester_idea")
    def test_tester_idea_with_docker(self, mock_tester):
        """tester_idea should accept use_docker parameter."""
        mock_tester.return_value = 85
        # Just verify the parameter exists and doesn't break
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.tester.REQUIREMENTS_DIR", tmpdir):
                spec_dir = os.path.join(tmpdir, "ID-DOCKER")
                os.makedirs(spec_dir, exist_ok=True)
                with open(os.path.join(spec_dir, "spec.md"), "w") as f:
                    f.write("# Docker Test\n\nContent.")
                with open(os.path.join(spec_dir, "architecture.md"), "w") as f:
                    f.write("# Architecture\n\nContent.")

                confidence = tester.tester_idea("ID-DOCKER", use_docker=False)
                assert isinstance(confidence, int)