import unittest
import os
import shutil
import json
import time
from api.secret_vault import SecretVault
from api.integration_hub import IntegrationHub
from api.workflow_state_manager import WorkflowStateManager
from api.workflow_context import RunContext
from api.retry_manager import RetryManager
from api.ai_adapter import AIAdapter
from api.scheduler import AntikytheraScheduler

class AntikytheraComprehensiveAudit(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tests/audit_dir"
        os.makedirs(self.test_dir, exist_ok=True)
        
        # Initialize all components
        self.vault = SecretVault(self.test_dir)
        self.hub = IntegrationHub(self.test_dir, self.vault)
        self.state_mgr = WorkflowStateManager(self.test_dir)
        self.retry_mgr = RetryManager(self.state_mgr)
        self.ai = AIAdapter(api_key="audit_key")
        self.scheduler = AntikytheraScheduler(self.test_dir, self.state_mgr, self.hub)
        self.scheduler.start()

    def tearDown(self):
        self.scheduler.stop()
        shutil.rmtree(self.test_dir)

    def test_01_governance_layer(self):
        """Audit SecretVault and IntegrationHub」"""
        print("\n[1/6] Auditing Governance Layer...")
        profile = "jira_prod"
        secrets = {"api_token": "tok_123", "user": "admin"}
        
        # Vault Test
        self.assertTrue(self.vault.store_secret(profile, secrets))
        self.assertEqual(self.vault.get_secret(profile), secrets)
        
        # Hub Test
        self.assertTrue(self.hub.add_integration(profile, "native", {"adapter_module": "api.adapters.jira"}))
        self.assertEqual(self.hub.get_integration(profile)["type"], "native")
        
        # Execution Dispatch Test (Mocked)
        res = self.hub.execute_action(profile, "update_status", {"status": "DONE"})
        self.assertEqual(res["status"], "success")
        print("✅ Governance Layer: OK")

    def test_02_cognitive_engine(self):
        """Audit AIAdapter and RunContext」"""
        print("\n[2/6] Auditing Cognitive Engine...")
        run_id = "audit_run_001"
        context = RunContext(self.test_dir, run_id)
        
        # Context Test
        context.set("user_id", "user_123")
        self.assertEqual(context.get("user_id"), "user_123")
        
        # AI Reasoning Test
        analysis = self.ai.analyze(
            prompt="Check vulnerability",
            context_data={"text": "vulnerability found and fix not available"}
        )
        self.assertEqual(analysis["decision"], "SENSITIVE_BLOCK")
        
        # Data flow simulation
        context.set("ai_decision", analysis["decision"])
        self.assertEqual(context.get("ai_decision"), "SENSITIVE_BLOCK")
        print("✅ Cognitive Engine: OK")

    def test_03_failure_handling(self):
        """Audit RetryManager and State transitions」"""
        print("\n[3/6] Auditing Failure Handling...")
        run_id = "fail_run_001"
        self.state_mgr.create_run(run_id, {"status": "RUNNING", "retry_count": 0})
        
        # Retry 1
        self.retry_mgr.record_failure(run_id, "Error 1")
        self.assertEqual(self.state_mgr.get_run(run_id)["retry_count"], 1)
        self.assertEqual(self.state_mgr.get_run(run_id)["status"], "RUNNING")
        
        # Exhaust retries (3 retries + 1 final failure = 4 failures to block)
        for i in range(4):
            self.retry_mgr.record_failure(run_id, f"Error {i+2}")
            
        self.assertEqual(self.state_mgr.get_run(run_id)["status"], "BLOCKED")
        print("✅ Failure Handling: OK")

    def test_04_scheduling_and_triggers(self):
        """Audit BackgroundScheduler」"""
        print("\n[4/6] Auditing Scheduling...")
        template_id = "sched_test"
        
        def mock_poll(tid):
            print(f"Polling template {tid}...")
            
        job_id = self.scheduler.schedule_polling(template_id, 1, mock_poll)
        self.assertIn(job_id, self.scheduler.get_active_jobs())
        
        self.scheduler.cancel_polling(template_id)
        self.assertNotIn(job_id, self.scheduler.get_active_jobs())
        print("✅ Scheduling: OK")

    def test_05_self_learning_loop(self):
        """Audit PatternStore and Learning」"""
        print("\n[5/6] Auditing Self-Learning Loop...")
        from api.pattern_store import PatternStore
        store = PatternStore(self.test_dir)
        
        template_id = "learn_tpl"
        context = {"issue": "vulnerability", "status": "no_fix"}
        resolution = "Assign to Security Lead"
        
        store.add_pattern(template_id, context, resolution)
        patterns = store.get_patterns(template_id)
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["resolution"], resolution)
        
        # Test similarity search
        similar = store.find_similar_patterns(template_id, {"issue": "vulnerability", "status": "unknown"})
        self.assertTrue(len(similar) > 0)
        print("✅ Self-Learning: OK")

    def test_06_end_to_end_integration(self):
        """Full chain: Vault -> Hub -> Engine -> State -> Timeline」"""
        print("\n[6/6] Auditing E2E Integration...")
        # 1. Profile Setup
        self.vault.store_secret("github", {"token": "abc"})
        self.hub.add_integration("github", "native", {"adapter_module": "github"})
        
        # 2. Template & Run
        tid = "e2e_tpl"
        self.state_mgr.save_template(tid, {"name": "E2E", "steps": []})
        rid = "e2e_run"
        self.state_mgr.create_run(rid, {"template_id": tid, "status": "RUNNING"})
        self.state_mgr.bind_run_to_item(rid, "ITEM-E2E")
        
        # 3. Execution & Logging
        self.state_mgr.log_event(rid, "START", {"msg": "Beginning run"})
        self.state_mgr.log_event(rid, "STEP_COMPLETE", {"step": 1, "result": "OK"})
        
        timeline = self.state_mgr.get_run_timeline(rid)
        self.assertEqual(len(timeline), 2)
        self.assertEqual(timeline[0]["event_type"], "START")
        print("✅ E2E Integration: OK")

if __name__ == "__main__":
    unittest.main()
