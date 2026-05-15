"""
Tests for the Architect Agent (agents/architect.py).
"""

import os
import tempfile
import pytest
from unittest.mock import patch

from agents import architect


class TestArchitectIdea:
    def test_architect_idea_creates_architecture_file(self):
        """architect_idea should create an architecture.md file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.architect.REQUIREMENTS_DIR", tmpdir):
                # Create a spec.md first
                spec_dir = os.path.join(tmpdir, "ID-999")
                os.makedirs(spec_dir, exist_ok=True)
                with open(os.path.join(spec_dir, "spec.md"), "w") as f:
                    f.write("# Test Automation Idea\n\nSome spec content.")

                confidence = architect.architect_idea("ID-999")
                arch_path = os.path.join(spec_dir, "architecture.md")
                assert os.path.isfile(arch_path)
                assert isinstance(confidence, int)
                assert 0 <= confidence <= 100

    def test_architect_idea_returns_high_confidence(self):
        """architect_idea should return a high confidence score for valid input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.architect.REQUIREMENTS_DIR", tmpdir):
                spec_dir = os.path.join(tmpdir, "ID-888")
                os.makedirs(spec_dir, exist_ok=True)
                with open(os.path.join(spec_dir, "spec.md"), "w") as f:
                    f.write("# Automate Daily Pod Restarts\n\nFull spec content here.")

                confidence = architect.architect_idea("ID-888")
                assert confidence >= 70

    def test_architect_idea_raises_on_missing_spec(self):
        """architect_idea should raise FileNotFoundError if spec.md is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.architect.REQUIREMENTS_DIR", tmpdir):
                with pytest.raises(FileNotFoundError, match="File not found"):
                    architect.architect_idea("ID-NONEXIST")

    def test_architect_idea_raises_on_empty_spec(self):
        """architect_idea should raise ValueError for empty spec content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.architect.REQUIREMENTS_DIR", tmpdir):
                spec_dir = os.path.join(tmpdir, "ID-EMPTY")
                os.makedirs(spec_dir, exist_ok=True)
                with open(os.path.join(spec_dir, "spec.md"), "w") as f:
                    f.write("   ")

                with pytest.raises(ValueError, match="Spec content is empty"):
                    architect.architect_idea("ID-EMPTY")

    def test_architect_idea_creates_directory(self):
        """architect_idea should create the ID directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.architect.REQUIREMENTS_DIR", tmpdir):
                # Create spec in a subdirectory
                spec_dir = os.path.join(tmpdir, "ID-NEW")
                os.makedirs(spec_dir, exist_ok=True)
                with open(os.path.join(spec_dir, "spec.md"), "w") as f:
                    f.write("# New Idea\n\nContent.")

                architect.architect_idea("ID-NEW")
                assert os.path.isdir(spec_dir)
                assert os.path.isfile(os.path.join(spec_dir, "architecture.md"))


class TestWriteArchitecture:
    def test_write_architecture_writes_content(self):
        """write_architecture should write content to the correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.architect.REQUIREMENTS_DIR", tmpdir):
                content = "# Architecture Test\n\nSome architecture content"
                file_path = architect.write_architecture("ID-777", content)
                assert file_path == os.path.join(tmpdir, "ID-777", "architecture.md")
                with open(file_path, "r") as f:
                    assert f.read() == content

    def test_write_architecture_creates_directory(self):
        """write_architecture should create the directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.architect.REQUIREMENTS_DIR", tmpdir):
                architect.write_architecture("ID-NEW-DIR", "content")
                assert os.path.isdir(os.path.join(tmpdir, "ID-NEW-DIR"))


class TestCalculateConfidence:
    def test_calculate_confidence_returns_int(self):
        """calculate_confidence should return an integer."""
        score = architect.calculate_confidence("Some architecture content")
        assert isinstance(score, int)

    def test_calculate_confidence_empty_low_score(self):
        """Empty content should return a low score (0-10)."""
        score = architect.calculate_confidence("")
        assert score <= 10

    def test_calculate_confidence_short_content_low_score(self):
        """Very short content should return a low score."""
        score = architect.calculate_confidence("hi")
        assert score <= 20

    def test_calculate_confidence_comprehensive_high_score(self):
        """Comprehensive content with all sections should return a high score."""
        content = """
# Architecture

## Architecture Diagram
Some diagram description.

## Tech Stack
Python, Docker, etc.

## Risk Flags
Low risk.

## Dry-Run Notes
Read-only operations.

## Constraints
Various constraints.

## Patterns
Following established patterns.

- Bullet point 1
- Bullet point 2
1. Numbered item
"""
        score = architect.calculate_confidence(content)
        assert score >= 80

    def test_calculate_confidence_mid_score(self):
        """Content with some sections should return a mid-range score."""
        content = """
# Architecture

## Architecture Diagram
Some diagram.

## Tech Stack
Python.

- A bullet point
"""
        score = architect.calculate_confidence(content)
        assert 20 <= score <= 80

    def test_calculate_confidence_never_exceeds_100(self):
        """calculate_confidence should never return more than 100."""
        content = """
## Architecture Diagram
a
## Tech Stack
b
## Risk Flags
c
## Dry-Run Notes
d
## Constraints
e
## Patterns
f
- bullet 1
- bullet 2
- bullet 3
- bullet 4
- bullet 5
""" * 10
        score = architect.calculate_confidence(content)
        assert score <= 100


class TestGenerateArchitecture:
    def test_generate_architecture_contains_mermaid(self):
        """Generated architecture should contain a Mermaid diagram."""
        content = architect._generate_architecture_content("ID-001", "# Test Idea\n\nContent")
        assert "mermaid" in content.lower()

    def test_generate_architecture_contains_tech_stack(self):
        """Generated architecture should contain tech stack section."""
        content = architect._generate_architecture_content("ID-001", "# Test Idea\n\nContent")
        assert "Tech Stack" in content

    def test_generate_architecture_contains_risk_flags(self):
        """Generated architecture should contain risk flags section."""
        content = architect._generate_architecture_content("ID-001", "# Test Idea\n\nContent")
        assert "Risk Flag" in content

    def test_generate_architecture_contains_dry_run_notes(self):
        """Generated architecture should contain dry-run notes section."""
        content = architect._generate_architecture_content("ID-001", "# Test Idea\n\nContent")
        assert "Dry-Run" in content

    def test_generate_architecture_contains_constraints(self):
        """Generated architecture should contain constraints section."""
        content = architect._generate_architecture_content("ID-001", "# Test Idea\n\nContent")
        assert "Constraint" in content

    def test_generate_architecture_includes_patterns(self):
        """Generated architecture should include patterns when provided."""
        content = architect._generate_architecture_content(
            "ID-001", "# Test Idea\n\nContent", patterns_content="Some pattern content"
        )
        assert "Patterns Referenced" in content

    def test_generate_architecture_skips_patterns_when_none(self):
        """Generated architecture should skip patterns section when not provided."""
        content = architect._generate_architecture_content("ID-001", "# Test Idea\n\nContent")
        assert "Patterns Referenced" not in content

    def test_extract_title_from_spec(self):
        """_extract_title should extract the title from spec content."""
        title = architect._extract_title("# My Custom Title\n\nSome content")
        assert title == "My Custom Title"

    def test_extract_title_default(self):
        """_extract_title should return 'Untitled' when no heading found."""
        title = architect._extract_title("No heading here")
        assert title == "Untitled"