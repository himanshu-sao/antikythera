"""Integration-record credentials for canonical adapter steps.

A canonical ``jira``/``github`` step now takes its credentials from a
UI-configured integration record whose ``adapter_module`` matches, with the
environment as the fallback. Covers the adapters' ``configure()``
(instance-over-env resolution), the hub's credential extraction (``${env:X}``
resolved, ``*****`` never passed), and the module-matching fallback.
"""

import pytest

from api.adapters.github import GitHubAdapter
from api.adapters.jira import JiraAdapter
from api.integration_hub import IntegrationHub


@pytest.fixture
def hub(tmp_path):
    return IntegrationHub(str(tmp_path))


class TestAdapterConfigure:
    def test_jira_token_prefers_configured_over_env(self, monkeypatch):
        monkeypatch.setenv("JIRA_PAT", "env-token")
        adapter = JiraAdapter(None)
        assert adapter._get_token() == "env-token"
        adapter.configure({"token": "ui-token"})
        assert adapter._get_token() == "ui-token"

    def test_jira_base_url_prefers_configured_over_env(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://env.example.com")
        adapter = JiraAdapter(None)
        adapter.configure({"jira_url": "https://ui.example.com"})
        assert adapter._get_base_url() == "https://ui.example.com"
        adapter.configure({})
        assert adapter._get_base_url() == "https://env.example.com"

    def test_jira_url_key_also_sets_base_url(self):
        adapter = JiraAdapter(None)
        adapter.configure({"url": "https://alt.example.com"})
        assert adapter._get_base_url() == "https://alt.example.com"

    def test_jira_env_fallback_without_configure(self, monkeypatch):
        monkeypatch.delenv("JIRA_PAT", raising=False)
        monkeypatch.delenv("JIRA_TOKEN", raising=False)
        monkeypatch.setenv("JIRA_BASE_URL", "https://env.example.com")
        adapter = JiraAdapter(None)
        assert adapter._get_token() is None
        assert adapter._get_base_url() == "https://env.example.com"

    def test_github_token_prefers_configured_over_env(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        adapter = GitHubAdapter(None)
        assert adapter._get_token() == "env-token"
        adapter.configure({"token": "ui-token"})
        assert adapter._get_token() == "ui-token"

    def test_github_access_token_key(self):
        adapter = GitHubAdapter(None)
        adapter.configure({"access_token": "via-access"})
        assert adapter._get_token() == "via-access"

    def test_github_env_fallback_without_configure(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        assert GitHubAdapter(None)._get_token() is None


class TestHubCredentialExtraction:
    def test_known_keys_extracted(self, hub):
        creds = hub._extract_credentials({
            "config": {"token": "t", "jira_url": "https://x", "command": "echo"},
        })
        assert creds == {"token": "t", "jira_url": "https://x"}

    def test_env_references_resolved(self, hub, monkeypatch):
        monkeypatch.setenv("JIRA_PAT", "resolved-token")
        creds = hub._extract_credentials({
            "config": {"token": "${env:JIRA_PAT}"},
        })
        assert creds == {"token": "resolved-token"}

    def test_unresolvable_env_reference_dropped(self, hub, monkeypatch):
        monkeypatch.delenv("NOPE_MISSING", raising=False)
        assert hub._extract_credentials({"config": {"token": "${env:NOPE_MISSING}"}}) == {}

    def test_masked_values_never_passed(self, hub):
        assert hub._extract_credentials({"config": {"token": "*****"}}) == {}

    def test_non_dict_config_and_missing_config(self, hub):
        assert hub._extract_credentials({"config": "nope"}) == {}
        assert hub._extract_credentials({}) == {}


class _RecordingAdapter:
    """Fake adapter class the hub is directed to via _resolve_adapter_class."""
    configured = None

    def __init__(self, vault=None):
        self.vault = vault

    def configure(self, credentials):
        _RecordingAdapter.configured = dict(credentials)

    async def fetch(self, resource_id, params=None):
        return {"resource_id": resource_id}


@pytest.fixture
def recording_adapter(monkeypatch):
    _RecordingAdapter.configured = None
    monkeypatch.setattr(
        IntegrationHub, "_resolve_adapter_class", classmethod(lambda cls, path: _RecordingAdapter))
    return _RecordingAdapter


class TestCanonicalCredentials:
    def test_canonical_jira_uses_a_matching_integration_record(self, hub, recording_adapter):
        # A UI-configured integration that happens to be named "jira_test"
        # but uses the jira adapter module.
        assert hub.add_integration("jira_test", "native", {
            "adapter_module": "api.adapters.jira",
            "token": "ui-token",
            "jira_url": "https://ui.example.com",
        })
        res = hub.execute_action("jira", "fetch_resource", {"resource_id": "PROJ-1"})
        assert res["status"] == "success"
        assert recording_adapter.configured == {
            "token": "ui-token", "jira_url": "https://ui.example.com"}

    def test_canonical_without_a_record_gets_no_credentials(self, hub, recording_adapter):
        res = hub.execute_action("github", "fetch_resource", {"resource_id": "o/r"})
        assert res["status"] == "success"
        assert recording_adapter.configured is None

    def test_multiple_matching_records_pick_first_by_name_with_warning(
            self, hub, recording_adapter, caplog):
        assert hub.add_integration("zzz-jira", "native", {
            "adapter_module": "api.adapters.jira", "token": "zzz"})
        assert hub.add_integration("aaa-jira", "native", {
            "adapter_module": "api.adapters.jira", "token": "aaa"})
        with caplog.at_level("WARNING", logger="backend"):
            hub.execute_action("jira", "fetch_resource", {"resource_id": "PROJ-1"})
        assert recording_adapter.configured == {"token": "aaa"}
        assert any("using 'aaa-jira'" in r.message for r in caplog.records)

    def test_exact_name_match_still_wins(self, hub, recording_adapter):
        assert hub.add_integration("jira", "native", {
            "adapter_module": "api.adapters.jira", "token": "exact-name"})
        hub.execute_action("jira", "fetch_resource", {"resource_id": "PROJ-1"})
        assert recording_adapter.configured == {"token": "exact-name"}

    def test_masked_record_token_is_not_passed(self, hub, recording_adapter):
        # A stored record whose token was masked by a buggy writer must not
        # inject ***** as a credential.
        assert hub.add_integration("jira_test", "native", {
            "adapter_module": "api.adapters.jira", "token": "*****"})
        hub.execute_action("jira", "fetch_resource", {"resource_id": "PROJ-1"})
        # No extractable credentials -> configure is not called at all.
        assert recording_adapter.configured is None
