import os

import agents.refiner as ref_mod


class _EmptyLLM:
    """Fake LLM returning an empty string, forcing the fallback spec template."""

    def __init__(self):
        self.calls = 0

    def generate_structured_content(self, *args, **kwargs):
        self.calls += 1
        return ""


def test_refiner_fallback(isolate_data_dir, monkeypatch):
    """Empty LLM output -> fallback spec written under the redirected tmp dir."""
    fake = _EmptyLLM()
    monkeypatch.setattr(ref_mod, "llm", fake)

    idea_id = "ID-999"
    title = "Test Idea"
    confidence = ref_mod.refine_idea(idea_id, title)

    assert isinstance(confidence, int)
    assert confidence > 0
    assert fake.calls >= 1

    # The conftest redirect must still be in force (no module reload).
    assert ref_mod.REQUIREMENTS_DIR == str(isolate_data_dir / "requirements")
    spec_path = os.path.join(ref_mod.REQUIREMENTS_DIR, idea_id, "spec.md")
    assert os.path.isfile(spec_path)
    with open(spec_path) as f:
        content = f.read()
    assert "Specification for" in content
    assert title in content


def test_refiner_fallback_never_writes_real_data_dir(isolate_data_dir, monkeypatch):
    """The spec path used by refine_idea is under tmp, not the repo's automation-ideas."""
    monkeypatch.setattr(ref_mod, "llm", _EmptyLLM())
    ref_mod.refine_idea("ID-998", "Isolated Idea")
    real_root = os.path.join(ref_mod.PROJECT_ROOT, "automation-ideas")
    assert not os.path.abspath(ref_mod.REQUIREMENTS_DIR).startswith(real_root)
    assert (isolate_data_dir / "requirements" / "ID-998" / "spec.md").is_file()
