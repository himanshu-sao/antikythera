import unittest
import os
import shutil
import json
from unittest.mock import patch
import agents.llm_client as _llm_mod  # bound module obj; patch.object uses it directly
from api.secret_vault import SecretVault
from api.integration_hub import IntegrationHub
from api.workflow_state_manager import WorkflowStateManager
from api.workflow_context import RunContext
from api.retry_manager import RetryManager
from api.ai_adapter import AIAdapter

class TestAntikytheraE2E(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tests/e2e_test_dir"
        os.makedirs(self.test_dir, exist_ok=True)

        # Force the LLM to the deterministic stub path regardless of the ambient
        # ~/.antikythera/ai_config.json default — this test asserts the
        # SENSITIVE_BLOCK keyword fallback in AIAdapter.analyze(), which only
        # fires when the LLM is unreachable (stub response). Without this,
        # switching the AI Engine default to a real, keyed provider makes the
        # LLM call succeed and the deterministic decision never triggers.
        # We patch the bound module object directly because ``agents/__init__``
        # doesn't re-export ``llm_client`` — so ``patch("agents.llm_client.…")``
        # (string path) and ``patch.object(agents, …)`` both fail to resolve.
        self._resolver_patch = patch.object(
            _llm_mod, "_resolve_from_config_service", lambda: None
        )
        self._resolver_patch.start()
        self.addCleanup(self._resolver_patch.stop)

        # Init all core components
        self.vault = SecretVault(self.test_dir)
        self.hub = IntegrationHub(self.test_dir, self.vault)
        self.state_mgr = WorkflowStateManager(self.test_dir)
        self.retry_mgr = RetryManager(self.state_mgr)
        self.ai = AIAdapter(api_key="test_key")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_full_workflow_lifecycle(self):
        # 1. Setup Integration & Secret
        profile_id = "github_test"
        self.vault.store_secret(profile_id, {"token": "ghp_test123"})
        self.hub.add_integration(profile_id, "native", {"adapter_module": "api.adapters.github"})

        # 2. Setup Template
        template_id = "e2e_test_tpl"
        template_data = {
            "name": "E2E Test Workflow",
            "trigger": {"type": "webhook", "provider": "github"},
            "steps": [
                {"id": 1, "type": "action", "adapter": "ai", "action": "analyze", "board_stage": "INTAKE"},
                {"id": 2, "type": "action", "adapter": "native", "action": "update_jira", "board_stage": "EXECUTING"},
            ]
        }
        self.state_mgr.save_template(template_id, template_data)

        # 3. Simulate Trigger & Run Creation
        run_id = "run_e2e_001"
        run_data = {
            "template_id": template_id,
            "status": "RUNNING",
            "current_step": 0,
            "retry_count": 0
        }
        self.state_mgr.create_run(run_id, run_data)
        self.state_mgr.bind_run_to_item(run_id, "ITEM-123")

        # 4. Execute Step 1 (AI Analysis)
        context = RunContext(self.test_dir, run_id)
        ai_result = self.ai.analyze(
            prompt="Analyze ticket", 
            context_data={"text": "vulnerability found and fix not available"},
            patterns=[]
        )
        context.set("ai_decision", ai_result["decision"])
        self.state_mgr.log_event(run_id, "STEP_COMPLETE", {"step": 1, "result": ai_result["decision"]})
        
        self.assertEqual(ai_result["decision"], "SENSITIVE_BLOCK")

        # 5. Simulate Failure & Retry Logic
        # Record a failure to trigger RetryManager
        self.retry_mgr.record_failure(run_id, "API Timeout")
        run = self.state_mgr.get_run(run_id)
        self.assertEqual(run["retry_count"], 1)
        
        # Simulate exhausting retries
        for _ in range(4):
            self.retry_mgr.record_failure(run_id, "Still failing")
            
        run_final = self.state_mgr.get_run(run_id)
        self.assertEqual(run_final["status"], "BLOCKED")

        # 6. Verify Timeline
        timeline = self.state_mgr.get_run_timeline(run_id)
        self.assertTrue(any(e["event_type"] == "FAILURE" for e in timeline))
        self.assertTrue(any(e["event_type"] == "STATE_TRANSITION" and e["payload"]["to"] == "BLOCKED" for e in timeline))

if __name__ == "__main__":
    unittest.main()
