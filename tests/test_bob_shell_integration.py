import unittest
import os
import shutil
from unittest.mock import patch, MagicMock

from api.workflow_state_manager import WorkflowStateManager
from api.workflow_engine import WorkflowEngine

class TestBobShellIntegration(unittest.TestCase):
    def setUp(self):
        # Temporary directory for state and templates
        self.test_dir = "./automation-ideas/test_bob_shell"
        os.makedirs(self.test_dir, exist_ok=True)
        self.wf_mgr = WorkflowStateManager(self.test_dir)
        self.engine = WorkflowEngine(self.test_dir)
        # Set a dummy API key for Bob Shell
        os.environ["IBM_BOB_SHELL_DEFAULT_KEY"] = "dummy_key"

    def tearDown(self):
        # Clean up temporary directory and env var
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.environ.pop("IBM_BOB_SHELL_DEFAULT_KEY", None)

    @patch("api.adapters.bob_shell.subprocess.run")
    def test_bob_shell_step_success(self, mock_run):
        # Mock subprocess.run to simulate Bob Shell output
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "Bob analysis result"
        mock_process.stderr = ""
        mock_run.return_value = mock_process

        # Define the AI integration template using Bob Shell
        template_id = "AI_INTEGRATION_BOB"
        template_data = {
            "name": "AI Integration via Bob Shell",
            "version": "1.0.0",
            "trigger": {"type": "MANUAL"},
            "steps": [
                {
                    "step_id": "S1",
                    "name": "Run Bob Shell Analysis",
                    "category": "ACTION",
                    "config": {
                        "adapter": "BOB_SHELL",
                        "prompt": "Analyze recent changes",
                        "args": ["--yolo"],
                        "api_key_env": "IBM_BOB_SHELL_DEFAULT_KEY"
                    },
                    "next_step": None
                }
            ]
        }

        # Save the template into the test state manager
        self.wf_mgr.save_template(template_id, template_data)

        # Trigger the workflow run
        run_id = self.engine.trigger_run(template_id, {})
        run = self.wf_mgr.get_run(run_id)

        # Verify the run completed successfully
        self.assertEqual(run["status"], "COMPLETED")

        # Verify the timeline contains a STEP_END event with the mocked output
        timeline = self.wf_mgr.get_run_timeline(run_id)
        step_end_events = [e for e in timeline if e["event_type"] == "STEP_END"]
        self.assertTrue(step_end_events, "STEP_END event not found in timeline")
        payload = step_end_events[0]["payload"]
        result = payload.get("result", {})
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(result.get("output"), "Bob analysis result")

if __name__ == "__main__":
    unittest.main()
