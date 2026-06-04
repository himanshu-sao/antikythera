import unittest
from unittest.mock import Mock, patch
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault
from api.models.automation import PathStep, ExecutionMode

class TestSkillReuse(unittest.TestCase):
    def setUp(self):
        # Create a mock vault
        self.vault = Mock(spec=SecretVault)
        self.vault.get_secret.return_value = {"access_token": "fake_token"}
        
        # Create an OperatorRegistry with the mock vault
        self.registry = OperatorRegistry(vault=self.vault)
        
        # Sample Jira description text
        self.sample_description = """\
This is a sample Jira ticket description.
Image: us.icr.io/my-app/nginx:latest
OS Distro: Red Hat Enterprise Linux 8.4
Java Path: /opt/ibm/java/jre/bin/java
"""
        
        # Define a parsing skill for extracting OS, Image, and Java Path
        self.parsing_skill = {
            "skill_id": "parse_jira_description",
            "name": "Parse Jira Description",
            "category": "PARSING",
            "few_shot_prompt": "Extract the image, OS distro, and Java path from the text.",
            "output_schema": {
                "image": "string",
                "os_distro": "string",
                "java_path": "string"
            },
            "version": "1.0.0",
            "skill_type": "parse",
            "parser_config": {
                "patterns": {
                    "image": r'us\.icr\.io/[^\s]+',
                    "os_distro": r'red hat enterprise linux\s*[0-9]+(?:\.[0-9]+)?',
                    "java_path": r'/opt/ibm/java/jre/bin/java'
                }
            }
        }
        
        # Add the skill to the registry's skill store
        self.registry.add_parsing_skill(self.parsing_skill)

    def test_parsing_skill_extracts_fields(self):
        # Test that the parsing skill can extract fields from the sample description
        extracted = self.registry._execute_parsing_skills(
            self.sample_description, 
            [self.parsing_skill]
        )
        
        # Check that the expected fields are extracted
        self.assertIn("image", extracted)
        self.assertIn("os_distro", extracted)
        self.assertIn("java_path", extracted)
        
        # Check the values (note: the regex might capture the whole match or group 1)
        # Our patterns are set to capture the whole match (group(0)) because we used group(0) when no group exists.
        self.assertEqual(extracted["image"].strip(), "us.icr.io/my-app/nginx:latest")
        self.assertEqual(extracted["os_distro"].strip(), "Red Hat Enterprise Linux 8.4")
        self.assertEqual(extracted["java_path"].strip(), "/opt/ibm/java/jre/bin/java")

    def test_parsing_skill_used_in_loop_step(self):
        # Simulate a loop step that uses the parsing skill to extract fields from multiple items
        # We'll create a mock state that contains a list of Jira tickets (each with a description)
        state = {
            "jira_tickets": [
                {"id": "1", "description": self.sample_description},
                {"id": "2", "description": self.sample_description.replace("8.4", "8.6")}
            ]
        }
        
        # Create a loop step that will iterate over jira_tickets
        loop_step = PathStep(
            step_id="loop_step",
            operator_id="fetch_resource",  # This operator_id is just a placeholder; we won't actually call the adapter
            adapter_id="jira_adapter",
            mode=ExecutionMode.ADAPTER,
            config={},  # Added required config parameter
            loop_over={
                "source": "jira_tickets",
                "iterator_var": "ticket"
            }
        )
        
        # We need to mock the adapter to avoid actual HTTP calls
        # Since we are only testing the skill extraction part, we can mock the adapter's fetch method
        # to return the ticket description (or the whole ticket) so that the raw text can be extracted.
        # However, note that in _execute_loop_step, we extract raw text from the item.
        # We'll mock the jira_adapter's fetch to return the description of the ticket.
        # But note: the loop step doesn't actually call the adapter in our test because we are not executing the step.
        # Instead, we will test the _execute_loop_step method directly.
        
        # We'll call _execute_loop_step and check that the extracted_fields are populated for each child.
        # However, _execute_loop_step is async and we are in a unit test. We'll run it in an event loop.
        # Alternatively, we can test the parsing skill extraction in the context of the loop by mocking the state.
        
        # Since the loop step's logic for extracting fields is inside _execute_loop_step, we can test that method.
        # But note: we are going to test the actual execution of the loop step, which involves creating child states and running the step.
        # We'll mock the _execute_single_step method to avoid executing the adapter step.
        
        with patch.object(self.registry, '_execute_single_step') as mock_execute_single_step:
            # Configure the mock to return a successful ExecutionLog for each child step
            mock_execute_single_step.return_value = Mock(
                status=Mock(value="success"),
                result_data={},
                execution_reason=None
            )
            
            # Run the loop step (this is async, so we need to run it in an event loop)
            import asyncio
            loop = asyncio.get_event_loop()
            child_logs = loop.run_until_complete(
                self.registry._execute_loop_step(loop_step, state)
            )
            
            # We should have 2 child logs (one for each ticket)
            self.assertEqual(len(child_logs), 2)
            
            # Each child log should have extracted_fields populated
            for child_log in child_logs:
                self.assertIn("extracted_fields", child_log.dict())
                extracted = child_log.extracted_fields
                self.assertIn("image", extracted)
                self.assertIn("os_distro", extracted)
                self.assertIn("java_path", extracted)
                
                # Check that the values are extracted correctly (they should be the same for both tickets except os_distro in the second)
                # Since we are using the same sample description for both, but we changed the second one to 8.6
                # We'll check the first ticket
                if child_log.step_id == "loop_step.0":
                    self.assertEqual(extracted["image"].strip(), "us.icr.io/my-app/nginx:latest")
                    self.assertEqual(extracted["os_distro"].strip(), "Red Hat Enterprise Linux 8.4")
                    self.assertEqual(extracted["java_path"].strip(), "/opt/ibm/java/jre/bin/java")
                elif child_log.step_id == "loop_step.1":
                    self.assertEqual(extracted["image"].strip(), "us.icr.io/my-app/nginx:latest")
                    self.assertEqual(extracted["os_distro"].strip(), "Red Hat Enterprise Linux 8.6")
                    self.assertEqual(extracted["java_path"].strip(), "/opt/ibm/java/jre/bin/java")

if __name__ == "__main__":
    unittest.main()