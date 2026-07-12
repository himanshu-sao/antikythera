import unittest
from unittest.mock import Mock, patch, AsyncMock
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault
from api.models.automation import PathStep, ExecutionMode, ExecutionStatus
from api.adapters.jira import JiraAdapter, AuthError
import httpx
import os


class TestAuthRetryFlow(unittest.TestCase):
    # JiraAdapter now resolves tokens from env first (mirroring the GitHub
    # adapter), falling back to the vault. These tests exercise the vault
    # path with a mock vault, so clear any real JIRA_* token env vars to
    # keep the "no token → AUTH_REQUIRED" contract independent of .env.
    _JIRA_ENV_VARS = ("JIRA_PAT", "JIRA_TOKEN")

    def setUp(self):
        self._saved_env = {v: os.environ.pop(v, None) for v in self._JIRA_ENV_VARS}

        # Create a mock vault
        self.vault = Mock(spec=SecretVault)
        # Initially, no token is stored
        self.vault.get_secret.return_value = None

        # Create an OperatorRegistry with the mock vault
        self.registry = OperatorRegistry(vault=self.vault)

        # Sample Jira issue data
        self.sample_issue = {
            "id": "TEST-1",
            "key": "TEST-1",
            "fields": {
                "summary": "Test issue",
                "status": {"name": "Open"}
            }
        }

        # Create a fetch step for Jira
        self.fetch_step = PathStep(
            step_id="fetch_issue",
            operator_id="fetch_resource",
            adapter_id="jira_adapter",
            mode=ExecutionMode.ADAPTER,
            config={},
            input_ref=None,
            output_ref=None
        )

    def tearDown(self):
        # Restore the real JIRA_* env vars so other tests/classes aren't affected
        for var, val in self._saved_env.items():
            if val is not None:
                os.environ[var] = val
            else:
                os.environ.pop(var, None)

    @patch('api.adapters.jira.httpx.AsyncClient')
    def test_auth_error_triggers_auth_required_status(self, mock_client_class):
        """Test that a 401 error from the Jira adapter results in AUTH_REQUIRED status"""
        # Setup mock responses
        mock_response_401 = Mock()
        mock_response_401.status_code = 401

        # Create the mock client object that will be returned by __aenter__
        mock_client_object = Mock()
        mock_client_object.get = Mock(return_value=mock_response_401)

        # Create the mock AsyncClient instance (what AsyncClient() returns)
        mock_client_instance = Mock()
        # When __aenter__ is called on the AsyncClient instance, return our mock client object
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_object)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)

        # Set up the patch to return our mock client instance when AsyncClient() is called
        mock_client_class.return_value = mock_client_instance

        # Execute the step
        import asyncio
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            self.registry._execute_adapter_step(self.fetch_step, {})
        )

        # Check that we get an ExecutionLog with AUTH_REQUIRED status
        self.assertTrue(hasattr(result, 'status') or isinstance(result, dict))
        if hasattr(result, 'status'):
            # It's an ExecutionLog object
            self.assertEqual(result.status, ExecutionStatus.AUTH_REQUIRED)
            # Check that the reason indicates authentication issue
            execution_reason = getattr(result, 'execution_reason', '')
            self.assertTrue(
                'token' in execution_reason.lower() or
                'auth' in execution_reason.lower() or
                'authentication' in execution_reason.lower()
            )
        else:
            # It might be a dict representation
            self.assertEqual(result.get('status'), 'auth_required')

    @patch('api.adapters.jira.httpx.AsyncClient')
    def test_successful_auth_retry(self, mock_client_class):
        """Test that after storing a token, the same step succeeds"""
        # Setup mock responses
        mock_response_401 = Mock()
        mock_response_401.status_code = 401
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json = Mock(return_value=self.sample_issue)
        mock_response_200.raise_for_status = Mock()  # Add this to prevent exception
        
        # Create the mock response objects
        mock_response_401_obj = Mock()
        mock_response_401_obj.status_code = 401
        
        mock_response_200_obj = Mock()
        mock_response_200_obj.status_code = 200
        mock_response_200_obj.json = Mock(return_value=self.sample_issue)
        mock_response_200_obj.raise_for_status = Mock()
        
        # Create the mock client object that will be returned by __aenter__
        mock_client_object = Mock()
        
        # Configure the get method to return different responses on subsequent calls
        call_count = {'count': 0}
        async def mock_get(*args, **kwargs):
            call_count['count'] += 1
            if call_count['count'] == 1:
                return mock_response_401_obj
            else:
                return mock_response_200_obj
        mock_client_object.get = mock_get
        
        # Create the mock AsyncClient instance (what AsyncClient() returns)
        mock_client_instance = Mock()
        # When __aenter__ is called on the AsyncClient instance, return our mock client object
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_object)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        
        # Set up the patch to return our mock client instance when AsyncClient() is called
        mock_client_class.return_value = mock_client_instance
        
        # Execute the step first time (should fail with auth required)
        import asyncio
        loop = asyncio.get_event_loop()
        result1 = loop.run_until_complete(
            self.registry._execute_adapter_step(self.fetch_step, {})
        )
        
        # Verify first attempt resulted in auth required
        if hasattr(result1, 'status'):
            self.assertEqual(result1.status, ExecutionStatus.AUTH_REQUIRED)
        
        # Now simulate storing a token in the vault
        # The Jira adapter calls vault.get_secret("jira")
        # Let's spy on the vault to see what key is being used
        def get_secret_side_effect(key):
            print(f"Vault.get_secret called with key: {key}")
            if key == "jira":
                return {"access_token": "fake_token"}
            return None
        self.vault.get_secret.side_effect = get_secret_side_effect
        
        # Set call count to 1 so that the next call returns the 200 response
        call_count['count'] = 1
        
        # Execute the step again (should succeed)
        result2 = loop.run_until_complete(
            self.registry._execute_adapter_step(self.fetch_step, {})
        )
        
        # Verify second attempt succeeded
        if hasattr(result2, 'status'):
            self.assertEqual(result2.status, ExecutionStatus.SUCCESS)
        else:
            # If it returned raw data, check it's our sample issue
            self.assertEqual(result2, self.sample_issue)


if __name__ == "__main__":
    unittest.main()