import os
import yaml
import pytest
from importlib import reload

def test_refiner_fallback(tmp_path, monkeypatch):
    # Prepare a minimal config.yaml for LLMClient stub
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump({"llm": {"provider": "google", "model": "test-model"}}, f)
    # Monkey-patch the PROJECT_ROOT used by refiner so that it resolves paths under tmp_path
    import agents.refiner as ref_mod
    monkeypatch.setattr(ref_mod, "PROJECT_ROOT", str(tmp_path))
    # Reload module to reinitialize the global LLM client with the temp config
    reload(ref_mod)
    # Mock the LLM client to return an empty string, forcing the fallback template
    class DummyClient:
        def generate_structured_content(self, *args, **kwargs):
            return ""
    monkeypatch.setattr(ref_mod, "llm", DummyClient())
    # Execute refine_idea – should write a spec file and return a confidence > 0
    idea_id = "ID-999"
    title = "Test Idea"
    confidence = ref_mod.refine_idea(idea_id, title)
    assert isinstance(confidence, int)
    assert confidence > 0
    # Verify spec file exists and contains expected markers
    spec_path = os.path.join(ref_mod.REQUIREMENTS_DIR, idea_id, "spec.md")
    assert os.path.isfile(spec_path)
    with open(spec_path) as f:
        content = f.read()
    assert "Specification for" in content
    assert title in content
