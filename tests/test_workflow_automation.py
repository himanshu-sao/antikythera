import unittest
import os
import shutil
from api.workflow_state_manager import WorkflowStateManager
from api.workflow_engine import WorkflowEngine
from api.state_manager import StateManager

class TestAntikytheraAutomation(unittest.TestCase):
    def setUp(self):
        self.test_dir = "./automation-ideas/test_suite"
        # Isolate the "main_state_mgr" from the live pipeline-state.json —
        # pointing it at the checkout's data file leaks test items (e.g.
        # FAIL-ITEM) into the real state and breaks backfill guards. Use a
        # dedicated tmp state file inside the test_dir, cleaned in tearDown.
        self.test_state_dir = "./automation-ideas/test_suite_state"
        self.state_file = os.path.join(self.test_state_dir, "pipeline-state.json")
        os.makedirs(self.test_dir, exist_ok=True)
        os.makedirs(self.test_state_dir, exist_ok=True)
        self.wf_mgr = WorkflowStateManager(self.test_dir)
        self.engine = WorkflowEngine(self.test_dir)
        self.main_state_mgr = StateManager(self.test_state_dir)

    def tearDown(self):
        for d in (self.test_dir, self.test_state_dir):
            if os.path.exists(d):
                shutil.rmtree(d)

    def test_end_to_end_multi_integration_success(self):
        """Verify that a run using multiple adapters completes and updates the board."""
        # Setup
        template_id = "E2E-SUCCESS"
        template_data = {
            "name": "E2E Success Test",
            "version": "1.0.0",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "step_id": "S1",
                    "name": "GitHub Step",
                    "category": "ACTION",
                    "config": {"adapter": "GITHUB", "action": "create_comment", "repo": "test/repo", "issue_id": "1", "body": "Hello"},
                    "next_step": "S2"
                },
                {
                    "step_id": "S2",
                    "name": "Jira Step",
                    "category": "ACTION",
                    "config": {"adapter": "JIRA", "action": "create_issue", "site": "test.atlassian.net", "summary": "Issue"},
                    "next_step": "S3"
                },
                {
                    "step_id": "S3",
                    "name": "Kanban Step",
                    "category": "ACTION",
                    "config": {"adapter": "INTERNAL", "action": "move_item", "new_stage": "DONE", "item_id": "E2E-ITEM"},
                    "next_step": None
                }
            ]
        }
        self.wf_mgr.save_template(template_id, template_data)
        # P1.5: InternalKanbanAdapter now mutates state through the shared
        # api.main.state_manager (reset by the autouse conftest fixture to a
        # tmp-backed WorkflowStateManager).  Create and read the item through
        # that same manager so the adapter's write is observable here.
        import api.main
        shared_state = api.main.get_state_manager()
        shared_state.create_item("E2E-ITEM", "E2E Test Item")

        # Execute
        run_id = self.engine.trigger_run(template_id, {})

        # Verify
        run = self.wf_mgr.get_run(run_id)
        item = shared_state.get_item_details("E2E-ITEM")

        self.assertEqual(run["status"], "COMPLETED")
        self.assertEqual(item["stage"], "DONE")
        
        timeline = self.wf_mgr.get_run_timeline(run_id)
        self.assertTrue(any(e["event_type"] == "RUN_COMPLETED" for e in timeline))

    def test_adapter_failure_blocks_run(self):
        """Verify that a failing adapter puts the run into BLOCKED state."""
        template_id = "E2E-FAIL"
        template_data = {
            "name": "Fail Test",
            "version": "1.0.0",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "step_id": "S1",
                    "name": "Fail Step",
                    "category": "ACTION",
                    "config": {"adapter": "INTERNAL", "action": "invalid_action", "item_id": "FAIL-ITEM"},
                    "next_step": None
                }
            ]
        }
        self.wf_mgr.save_template(template_id, template_data)
        self.main_state_mgr.create_item("FAIL-ITEM", "Fail Item")

        run_id = self.engine.trigger_run(template_id, {})
        run = self.wf_mgr.get_run(run_id)
        
        self.assertEqual(run["status"], "BLOCKED")
        timeline = self.wf_mgr.get_run_timeline(run_id)
        self.assertTrue(any(e["event_type"] == "ERROR" for e in timeline))

    def test_missing_adapter_fails_run(self):
        """Verify that a missing adapter leads to a FAILED state."""
        template_id = "MISSING-ADAPTER"
        template_data = {
            "name": "Missing Adapter Test",
            "version": "1.0.0",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "step_id": "S1",
                    "name": "Unknown Adapter Step",
                    "category": "ACTION",
                    "config": {"adapter": "UNKNOWN_CLOUD", "action": "do_something"},
                    "next_step": None
                }
            ]
        }
        self.wf_mgr.save_template(template_id, template_data)

        run_id = self.engine.trigger_run(template_id, {})
        run = self.wf_mgr.get_run(run_id)
        
        self.assertEqual(run["status"], "FAILED")

if __name__ == "__main__":
    unittest.main()
