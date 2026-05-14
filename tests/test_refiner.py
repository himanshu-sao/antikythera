"""
Tests for the Refiner Agent (agents/refiner.py).
"""

import os
import tempfile
import pytest
from unittest.mock import patch, mock_open

from agents import refiner


class TestRefineIdea:
    def test_refine_idea_creates_spec_file(self):
        """refine_idea should create a spec.md file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.refiner.REQUIREMENTS_DIR", tmpdir):
                confidence = refiner.refine_idea("ID-999", "Test automation idea")
                spec_path = os.path.join(tmpdir, "ID-999", "spec.md")
                assert os.path.isfile(spec_path)
                assert isinstance(confidence, int)
                assert 0 <= confidence <= 100

    def test_refine_idea_returns_high_confidence(self):
        """refine_idea should return a high confidence score for valid input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.refiner.REQUIREMENTS_DIR", tmpdir):
                confidence = refiner.refine_idea("ID-888", "Automate daily pod restarts")
                assert confidence >= 70  # Should be high due to comprehensive template

    def test_refine_idea_raises_on_empty_title(self):
        """refine_idea should raise ValueError for empty title."""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            refiner.refine_idea("ID-001", "")

    def test_refine_idea_raises_on_none_title(self):
        """refine_idea should raise ValueError for None title."""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            refiner.refine_idea("ID-001", None)

    def test_refine_idea_creates_directory(self):
        """refine_idea should create the ID directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.refiner.REQUIREMENTS_DIR", tmpdir):
                refiner.refine_idea("ID-NEW", "New idea")
                assert os.path.isdir(os.path.join(tmpdir, "ID-NEW"))


class TestWriteSpec:
    def test_write_spec_writes_content(self):
        """write_spec should write the spec content to the correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.refiner.REQUIREMENTS_DIR", tmpdir):
                content = "# Test Spec\n\nSome content"
                file_path = refiner.write_spec("ID-777", content)
                assert file_path == os.path.join(tmpdir, "ID-777", "spec.md")
                with open(file_path, "r") as f:
                    assert f.read() == content

    def test_write_spec_creates_directory(self):
        """write_spec should create the directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("agents.refiner.REQUIREMENTS_DIR", tmpdir):
                refiner.write_spec("ID-NEW-DIR", "content")
                assert os.path.isdir(os.path.join(tmpdir, "ID-NEW-DIR"))


class TestCalculateConfidence:
    def test_calculate_confidence_returns_int(self):
        """calculate_confidence should return an integer."""
        score = refiner.calculate_confidence("Some spec content")
        assert isinstance(score, int)

    def test_calculate_confidence_empty_low_score(self):
        """Empty content should return a low score (0-10)."""
        score = refiner.calculate_confidence("")
        assert score <= 10

    def test_calculate_confidence_short_content_low_score(self):
        """Very short content should return a low score."""
        score = refiner.calculate_confidence("hi")
        assert score <= 20

    def test_calculate_confidence_comprehensive_high_score(self):
        """Comprehensive content with all sections should return a high score."""
        content = """
# Spec

## Requirements
Lots of requirements here with details.

## Scope
In scope and out of scope items.

## Edge Cases
Many edge cases to consider.

## Constraints
Various constraints apply.

## PII
PII handling notes here.

## Patterns
Following established patterns.

- Bullet point 1
- Bullet point 2
1. Numbered item
"""
        score = refiner.calculate_confidence(content)
        assert score >= 80

    def test_calculate_confidence_mid_score(self):
        """Content with some sections should return a mid-range score."""
        content = """
# Spec

## Requirements
Some requirements.

## Scope
Some scope items.

- A bullet point
"""
        score = refiner.calculate_confidence(content)
        assert 20 <= score <= 80

    def test_calculate_confidence_never_exceeds_100(self):
        """calculate_confidence should never return more than 100."""
        content = """
## Requirements
a
## Scope
b
## Edge Cases
c
## Constraints
d
## PII
e
## Patterns
f
- bullet 1
- bullet 2
- bullet 3
- bullet 4
- bullet 5
""" * 10  # Repeat to make it very long
        score = refiner.calculate_confidence(content)
        assert score <= 100