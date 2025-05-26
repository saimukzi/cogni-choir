import os # Import os module
import unittest
from unittest.mock import patch, MagicMock

# Assuming AzureOpenAIEngine is in src.main.ai_engines.azure_openai_engine
# from src.main.ai_engines.azure_openai_engine import AzureOpenAIEngine
from src.main.ai_engines.azure_openai_engine import AzureOpenAIEngine
from src.main.ai_base import AIEngine
import openai # openai is still needed for the exception types
import logging


class TestAzureOpenAIEngine(unittest.TestCase):

    @patch('src.main.ai_engines.azure_openai_engine.openai.AzureOpenAI')
    def setUp(self, MockAzureOpenAI):
        # It's good practice to disable logging during tests unless specifically testing log output
        logging.disable(logging.CRITICAL)
        self.api_key = "test_api_key"
        self.model_name = "test_model"
        # self.azure_endpoint is removed as it's read internally by the engine
        self.api_version = "2024-12-01-preview" # This is hardcoded in the engine

        # Common test inputs for generate_response
        self.role_name = "TestAssistant"
        self.system_prompt = "You are a helpful test assistant."
        self.conversation_history_simple = [{"role": "TestUser", "text": "Hello there, assistant!"}]
        self.expected_messages_simple = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": "TestUser said:\nHello there, assistant!"} 
        ]
        self.conversation_history_mixed = [
            {"role": "TestUser", "text": "First message from user."},
            {"role": self.role_name, "text": "First response from assistant."}, # self.role_name is "TestAssistant"
            {"role": "AnotherUser", "text": "Second message from another user."}
        ]
        self.expected_messages_mixed = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": "TestUser said:\nFirst message from user."},
            {"role": "assistant", "content": "First response from assistant."},
            {"role": "user", "content": "AnotherUser said:\nSecond message from another user."}
        ]
        
        # Mock the AzureOpenAI client instance
        self.mock_openai_client = MagicMock()
        MockAzureOpenAI.return_value = self.mock_openai_client

        # Values that commons.read_str will be mocked to return
        self.mocked_azure_endpoint_val = "https://mocked.openai.azure.com/"
        self.mocked_deployment_name_val = "mocked-deployment-model"

        # Patch commons.read_str used by AzureOpenAIEngine
        # It's called twice: once for azure_endpoint, once for deployment_name (model)
        with patch('src.main.commons.read_str') as mock_read_str:
            # Configure the mock to return different values on consecutive calls
            # The first call in AzureOpenAIEngine is for azure_endpoint, second for deployment_name
            mock_read_str.side_effect = [
                self.mocked_azure_endpoint_val,  # For azure_endpoint
                self.mocked_deployment_name_val  # For deployment_name (model)
            ]
            
            self.engine = AzureOpenAIEngine(
                api_key=self.api_key,
                model_name=self.model_name # This model_name is for AIEngine base, not deployment name
            )
            
            # Ensure commons.read_str was called correctly
            self.assertEqual(mock_read_str.call_count, 2)
            mock_read_str.assert_any_call(os.path.join('tmp','azure_endpoint.txt'))
            mock_read_str.assert_any_call(os.path.join('tmp','azure_model.txt'))

        # Ensure the AzureOpenAI client was initialized with mocked/hardcoded values
        MockAzureOpenAI.assert_called_once_with(
            api_key=self.api_key,
            azure_endpoint=self.mocked_azure_endpoint_val, # From mocked commons.read_str
            api_version=self.api_version # Hardcoded in AzureOpenAIEngine
        )
        
        # The engine's model_name (deployment_name) should now be from the mocked commons.read_str
        # and it's stored in self.engine.deployment_name by the engine.
        # The model_name passed to the constructor is for the base class and might not be the deployment name.
        # Let's verify the deployment_name used in API calls is the one from mocking.
        # This is implicitly tested by `test_generate_response_success` checking `model=self.engine.model_name`
        # if we ensure `self.engine.model_name` (or rather self.engine.deployment_name) is set correctly.
        # The AzureOpenAIEngine sets self.deployment_name from commons.read_str.
        # The generate_response method uses self.deployment_name.
        self.assertEqual(self.engine.deployment_name, self.mocked_deployment_name_val)


    def tearDown(self):
        logging.disable(logging.NOTSET) # Re-enable logging
        patch.stopall() # Stop any patches started with patch.object or in setUp

    def test_requires_api_key(self):
        self.assertTrue(self.engine.requires_api_key())

    def test_generate_response_success(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = " Test response "
        self.mock_openai_client.chat.completions.create.return_value = mock_response
        
        response = self.engine.generate_response(
            role_name=self.role_name,
            system_prompt=self.system_prompt,
            conversation_history=self.conversation_history_simple
        )
        
        self.assertEqual(response, "Test response")
        self.mock_openai_client.chat.completions.create.assert_called_once_with(
            model=self.engine.deployment_name, # Should use deployment_name
            messages=self.expected_messages_simple
        )

    def test_generate_response_no_choices(self):
        mock_response = MagicMock()
        mock_response.choices = [] # Simulate no choices
        self.mock_openai_client.chat.completions.create.return_value = mock_response
        
        response = self.engine.generate_response(
            role_name=self.role_name,
            system_prompt=self.system_prompt,
            conversation_history=self.conversation_history_mixed # Using mixed for variety
        )
        
        self.assertEqual(response, "Error: No response generated.")
        self.mock_openai_client.chat.completions.create.assert_called_once_with(
            model=self.engine.deployment_name, # Should use deployment_name
            messages=self.expected_messages_mixed
        )

    def test_generate_response_api_connection_error(self):
        self.mock_openai_client.chat.completions.create.side_effect = openai.APIConnectionError(request=MagicMock())
        
        response = self.engine.generate_response(
            self.role_name, self.system_prompt, self.conversation_history_simple
        )
        self.assertIn("Error: Could not connect to Azure OpenAI API.", response)

    def test_generate_response_rate_limit_error(self):
        self.mock_openai_client.chat.completions.create.side_effect = openai.RateLimitError(message="Rate limit exceeded", response=MagicMock(), body=None)
        
        response = self.engine.generate_response(
            self.role_name, self.system_prompt, self.conversation_history_simple
        )
        self.assertIn("Error: Azure OpenAI API rate limit exceeded.", response)

    def test_generate_response_authentication_error(self):
        self.mock_openai_client.chat.completions.create.side_effect = openai.AuthenticationError(message="Authentication failed", response=MagicMock(), body=None)
        
        response = self.engine.generate_response(
            self.role_name, self.system_prompt, self.conversation_history_simple
        )
        self.assertIn("Error: Azure OpenAI API authentication failed.", response)

    def test_generate_response_api_error(self):
        # Updated APIError instantiation to include 'body'
        self.mock_openai_client.chat.completions.create.side_effect = openai.APIError("Test API Error", request=MagicMock(), body={})
        
        response = self.engine.generate_response(
            self.role_name, self.system_prompt, self.conversation_history_simple
        )
        self.assertIn("Error: An unexpected error occurred with the Azure OpenAI API.", response)

    def test_generate_response_unexpected_error(self):
        self.mock_openai_client.chat.completions.create.side_effect = Exception("Some unexpected error")
        
        response = self.engine.generate_response(
            self.role_name, self.system_prompt, self.conversation_history_simple
        )
        self.assertIn("Error: An unexpected error occurred. Details: Some unexpected error", response)


if __name__ == '__main__':
    unittest.main()
