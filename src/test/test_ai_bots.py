"""Unit tests for AI bot functionalities and AI engine interactions.

This module contains test suites for:
- The `Bot` class itself (creation, serialization).
- Specific AI engine implementations like `GeminiEngine` and `GrokEngine`,
  focusing on initialization, response generation, and error handling with mocks.
- The `create_bot` factory function, ensuring correct bot and engine instantiation.
"""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Adjusting sys.path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import openai # Import the openai module itself for error types
from src.main.ai_bots import Bot
from src.main.third_party import ThirdPartyBase
from src.main.third_parties.google import Google # Updated import for Google/Gemini
from src.main.third_parties.xai import XAI # Updated import for XAI/Grok
from src.main.third_parties.azure_openai import AzureOpenAI
from src.main.message import Message

# No global SDK mocks here; will use @patch decorator for targeted mocking

class TestBot(unittest.TestCase):
    """Tests for the Bot class."""
    def setUp(self):
        """Sets up a mock AI engine and a Bot instance for testing."""
        # AIEngine is no longer directly used by Bot. Bot stores aiengine_id and aiengine_arg_dict.
        # For testing Bot class in isolation, we might not need a full mock engine instance here,
        # or we can use ThirdPartyBase as a generic spec if some methods still expect an engine-like object.
        self.mock_engine_instance = MagicMock(spec=ThirdPartyBase)
        self.mock_engine_instance.__class__.__name__ = "SpecificMockedEngine" # For old to_dict if it used type name
        self.mock_engine_instance.model_name = "mocked-model-001" # If any part of Bot still needs this from a mock

        self.bot = Bot()
        self.bot.name = "TestBot"
        self.bot.aiengine_id = "mock_engine_id_001"
        self.bot.aiengine_arg_dict = {
            "system_prompt": "Be helpful.", # System prompt is now an engine argument
            "model_name": "mocked-model-001"  # Model name is also an engine argument
        }
        # apikeey_query_list is initialized to None by Bot.__init__

    def test_bot_creation(self): # Ensure basic attributes are set
        """Tests basic Bot attributes after creation."""
        self.assertEqual(self.bot.name, "TestBot")
        self.assertEqual(self.bot.aiengine_id, "mock_engine_id_001")
        self.assertEqual(self.bot.get_aiengine_arg("system_prompt"), "Be helpful.")
        self.assertEqual(self.bot.get_aiengine_arg("model_name"), "mocked-model-001")
        self.assertListEqual(self.bot.apikeey_query_list, []) # Ensure it's an empty list if not set

    def test_bot_to_dict(self):
        """Tests the serialization of a Bot instance to a dictionary."""
        expected_dict = {
            "name": "TestBot",
            "aiengine_id": "mock_engine_id_001",
            "aiengine_arg_dict": {
                "system_prompt": "Be helpful.",
                "model_name": "mocked-model-001"
            },
            "apikeey_query_list": []
        }
        self.assertEqual(self.bot.to_dict(), expected_dict)


class TestGoogleEngine(unittest.TestCase): # Renamed from TestGeminiEngine
    """Tests for the Google (Gemini) AI engine implementation."""
    def setUp(self):
        """Sets up a mock for the `google.genai.Client` instance."""
        self.mock_genai_client_instance = MagicMock()

    @patch('src.main.third_parties.google.genai') # Patched to new location
    def test_google_init_success(self, mock_genai_sdk): # Renamed
        """Tests successful initialization of Google engine with a mock SDK."""
        mock_genai_sdk.Client.return_value = self.mock_genai_client_instance
        # Google class __init__ takes no apikeey or model_name. These are passed to generate_response.
        engine = Google()
        # To test _get_client behavior, we'd call generate_response.
        # For an "init_success" test, we mostly ensure it can be instantiated.
        self.assertIsInstance(engine, Google)
        # We can also test that the internal client dict is empty initially.
        self.assertEqual(len(engine._apikeey_to_client_dict), 0)


    @patch('src.main.third_parties.google.genai') # Patched to new location
    def test_google_generate_response_success(self, mock_genai_sdk): # Renamed
        """Tests successful response generation from Google engine."""
        mock_genai_sdk.Client.return_value = self.mock_genai_client_instance
        # Mock the specific generate_content call path
        self.mock_genai_client_instance.models.generate_content.return_value = MagicMock(text="Test Google response")

        engine = Google()
        aiengine_arg_dict = {"model_name": "gemini-custom", "system_prompt": "System prompt ASFWDYPWYL"}
        apikeey_list = ["fake_google_key"]
        conversation_history = [Message(sender='user', content='Test message OETMTOCXPR')]

        response = engine.generate_response(
            _aiengine_id="google_gemini", # Matches AIEngineInfo
            aiengine_arg_dict=aiengine_arg_dict,
            apikeey_list=apikeey_list,
            role_name='FakeGoogleBot',
            conversation_history=conversation_history
        )
        self.assertEqual(response, "Test Google response")
        mock_genai_sdk.Client.assert_called_once_with(api_key="fake_google_key")
        self.mock_genai_client_instance.models.generate_content.assert_called_once()


    @patch('src.main.third_parties.google.genai') # Patched to new location
    def test_google_generate_response_api_error(self, mock_genai_sdk): # Renamed
        """Tests Google engine's error handling for an API error."""
        mock_genai_sdk.Client.return_value = self.mock_genai_client_instance
        self.mock_genai_client_instance.models.generate_content.side_effect = Exception("Google API Error")

        engine = Google()
        aiengine_arg_dict = {"model_name": "gemini-error", "system_prompt": "System Prompt for API Error Test"}
        apikeey_list = ["fake_google_key_error"]
        conversation_history = [Message(sender='user', content='Test message')]

        response = engine.generate_response(
            _aiengine_id="google_gemini",
            aiengine_arg_dict=aiengine_arg_dict,
            apikeey_list=apikeey_list,
            role_name="TestRole",
            conversation_history=conversation_history
        )
        self.assertTrue(response.startswith("Error: Gemini API call failed: Google API Error"))

    @patch('src.main.third_parties.google.genai') # Patched to new location
    def test_google_no_apikeey(self, mock_genai_sdk): # Renamed
        """Tests Google engine's behavior when an API key is not provided in list."""
        engine = Google()
        aiengine_arg_dict = {"model_name": "gemini-no-key"}
        # generate_response in Google class asserts `len(apikeey_list) == 1`.
        with self.assertRaises(AssertionError):
            engine.generate_response("google_gemini", aiengine_arg_dict, [], "TestRole", [])


class TestAzureOpenAIEngine(unittest.TestCase):
    """Tests for the AzureOpenAI AI engine implementation."""
    def setUp(self):
        self.mock_openai_client_instance = MagicMock()
        # Configure self.mock_completion_object for the chat.completions.create API
        # The AzureOpenAI client's chat.completions.create returns an object
        # that has a .choices list, and each choice has a .message object,
        # which in turn has a .content attribute.
        self.mock_completion_response_object = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Test OpenAI response"
        mock_choice.message = mock_message
        self.mock_completion_response_object.choices = [mock_choice]

        # The AzureOpenAI's generate_response method calls self.client.chat.completions.create
        self.mock_openai_client_instance.chat.completions.create.return_value = self.mock_completion_response_object

    @patch('src.main.third_parties.azure_openai.openai.AzureOpenAI') # Mock the actual SDK client
    def test_openai_init_and_client_retrieval(self, mock_sdk_azure_openai_class):
        # This test checks if our AzureOpenAI wrapper class correctly initializes
        # and uses the underlying openai.AzureOpenAI SDK client.
        mock_sdk_azure_openai_class.return_value = self.mock_openai_client_instance

        engine = AzureOpenAI() # Instantiate our engine wrapper

        # Define arguments for generate_response, which triggers _get_client
        aiengine_arg_dict = {"model_name": "test_deployment", "system_prompt": "Test system prompt"}
        apikeey_list = ["test_api_key"]

        # Mock commons.read_str as it's used in _get_client via generate_response
        with patch('src.main.third_parties.azure_openai.commons.read_str', return_value="fake_endpoint_init"):
            # Calling generate_response will trigger _get_client if client not cached
            engine.generate_response(
                _aiengine_id="azure_openai",
                aiengine_arg_dict=aiengine_arg_dict,
                apikeey_list=apikeey_list,
                role_name="TestRoleInit",
                conversation_history=[]
            )

        # Assert that the underlying SDK client was initialized by _get_client
        mock_sdk_azure_openai_class.assert_called_once_with(
            api_key=apikeey_list[0],
            azure_endpoint="fake_endpoint_init",
            api_version='2024-12-01-preview' # As hardcoded in azure_openai.py
        )
        # Check if the client instance is cached (optional, depends on desired test depth)
        # self.assertIn((apikeey_list[0], "fake_endpoint_init", '2024-12-01-preview'), engine._client_dict)
        # self.assertEqual(engine._client_dict[(apikeey_list[0], "fake_endpoint_init", '2024-12-01-preview')], self.mock_openai_client_instance)


    @patch('src.main.third_parties.azure_openai.openai.AzureOpenAI') # Mock the actual SDK client
    def test_openai_generate_response_success(self, mock_sdk_azure_openai_class):
        mock_sdk_azure_openai_class.return_value = self.mock_openai_client_instance
        
        engine = AzureOpenAI()
        
        aiengine_arg_dict_for_test = {
            "model_name": "gpt-custom-deployment",
            "system_prompt": "System instructions for AI."
        }
        apikeey_list_for_test = ["fake_azure_openai_key"]
        role_name_for_test = "TestBot"
        conversation_history_for_test = [Message(sender='User1', content='Hello AI, this is my first message.')]
        
        with patch('src.main.third_parties.azure_openai.commons.read_str', return_value="fake_endpoint_success"):
            response = engine.generate_response(
                _aiengine_id="azure_openai",
                aiengine_arg_dict=aiengine_arg_dict_for_test,
                apikeey_list=apikeey_list_for_test,
                role_name=role_name_for_test,
                conversation_history=conversation_history_for_test
            )
        
        self.assertEqual(response, "Test OpenAI response")
        
        expected_api_messages = [
            {'role': 'system', 'content': "System instructions for AI."},
            {'role': 'user', 'content': 'User1 said:\nHello AI, this is my first message.'}
        ]
        
        self.mock_openai_client_instance.chat.completions.create.assert_called_once_with(
            model=aiengine_arg_dict_for_test["model_name"],
            messages=expected_api_messages
        )
        mock_sdk_azure_openai_class.assert_called_once_with(
            api_key=apikeey_list_for_test[0],
            azure_endpoint="fake_endpoint_success",
            api_version='2024-12-01-preview'
        )

    @patch('src.main.third_parties.azure_openai.openai.AzureOpenAI') # Patch the constructor
    def test_openai_generate_response_api_error(self, mock_azure_openai_constructor): # Renamed arg
        mock_client_instance = MagicMock()
        # Make the mocked client's method raise APIConnectionError to test that specific block
        mock_client_instance.chat.completions.create.side_effect = openai.APIConnectionError(request=MagicMock())
        mock_azure_openai_constructor.return_value = mock_client_instance # Constructor returns our mock client
        
        engine = AzureOpenAI()
        aiengine_arg_dict_for_test = {"model_name": "deployment-error", "system_prompt": "SysPrompt"}
        apikeey_list_for_test = ["fake_key_error"]
        conversation_history_for_test = [Message(sender='user', content='Test message')]

        with patch('src.main.third_parties.azure_openai.commons.read_str', return_value="fake_endpoint_error"):
            response = engine.generate_response(
                _aiengine_id="azure_openai",
                aiengine_arg_dict=aiengine_arg_dict_for_test,
                apikeey_list=apikeey_list_for_test,
                role_name="TestRole",
                conversation_history=conversation_history_for_test
            )
        self.assertTrue(response.startswith("Error: Could not connect to Azure OpenAI API. Details:"))

    @patch('src.main.third_parties.azure_openai.openai.AzureOpenAI')
    def test_openai_generate_response_rate_limit_error(self, mock_azure_openai_constructor):
        """Tests AzureOpenAI's error handling for openai.RateLimitError."""
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.side_effect = openai.RateLimitError("Rate limit hit", response=MagicMock(), body=None)
        mock_azure_openai_constructor.return_value = mock_client_instance

        engine = AzureOpenAI()
        aiengine_arg_dict = {"model_name": "deployment-rl-error", "system_prompt": "SysPrompt"}
        apikeey_list = ["fake_key_rl_error"]
        with patch('src.main.third_parties.azure_openai.commons.read_str', return_value="fake_endpoint_rl_error"):
            response = engine.generate_response("azure_openai", aiengine_arg_dict, apikeey_list, "TestRoleRL", [])
        self.assertTrue(response.startswith("Error: Azure OpenAI API rate limit exceeded. Details:"))

    @patch('src.main.third_parties.azure_openai.openai.AzureOpenAI')
    def test_openai_generate_response_authentication_error(self, mock_azure_openai_constructor):
        """Tests AzureOpenAI's error handling for openai.AuthenticationError."""
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.side_effect = openai.AuthenticationError("Auth error", response=MagicMock(), body=None)
        mock_azure_openai_constructor.return_value = mock_client_instance

        engine = AzureOpenAI()
        aiengine_arg_dict = {"model_name": "deployment-auth-error", "system_prompt": "SysPrompt"}
        apikeey_list = ["fake_key_auth_error"]
        with patch('src.main.third_parties.azure_openai.commons.read_str', return_value="fake_endpoint_auth_error"):
            response = engine.generate_response("azure_openai", aiengine_arg_dict, apikeey_list, "TestRoleAuth", [])
        self.assertTrue(response.startswith("Error: Azure OpenAI API authentication failed."))

    @patch('src.main.third_parties.azure_openai.openai.AzureOpenAI')
    def test_openai_generate_response_generic_api_error(self, mock_azure_openai_constructor):
        """Tests AzureOpenAI's error handling for a generic openai.APIError."""
        mock_client_instance = MagicMock()
        # Note: openai.APIError requires 'request' argument.
        mock_client_instance.chat.completions.create.side_effect = openai.APIError("Generic API Error", request=MagicMock(), body=None)
        mock_azure_openai_constructor.return_value = mock_client_instance

        engine = AzureOpenAI()
        aiengine_arg_dict = {"model_name": "deployment-generic-api-error", "system_prompt": "SysPrompt"}
        apikeey_list = ["fake_key_generic_api_error"]
        with patch('src.main.third_parties.azure_openai.commons.read_str', return_value="fake_endpoint_generic_api_error"):
            response = engine.generate_response("azure_openai", aiengine_arg_dict, apikeey_list, "TestRoleGenericAPI", [])
        self.assertTrue(response.startswith("Error: An unexpected error occurred with the Azure OpenAI API. Details:"))

    def test_openai_no_apikeey_or_improper_config(self):
        """
        Tests AzureOpenAI's behavior when no API key is provided or if the configuration is improper.
        """
        engine = AzureOpenAI()
        aiengine_arg_dict = {"model_name": "deployment-no-key", "system_prompt": ""}

        with patch('src.main.third_parties.azure_openai.commons.read_str', return_value="fake_endpoint_no_key"):
            # Test with empty apikeey list (AssertionError)
            with self.assertRaisesRegex(AssertionError, "Azure OpenAI requires exactly one API key."):
                 engine.generate_response("azure_openai", aiengine_arg_dict, [], "TestRole", [])

            with self.assertRaisesRegex(AssertionError, "Azure OpenAI API key cannot be None."):
                engine.generate_response("azure_openai", aiengine_arg_dict, [None], "TestRole", [])
            # This will be caught by the generic "except Exception" in SUT's generate_response
            # self.assertTrue(response.startswith("Error: An unexpected error occurred. Details: API key cannot be None"))


class TestXAIEngine(unittest.TestCase): # Renamed from TestGrokEngine
    """Tests for the XAI (Grok) AI engine implementation."""
    @patch('src.main.third_parties.xai.openai.OpenAI') # Patched to new location
    def test_xai_response_success(self, mock_openai_class): # Renamed
        """Tests successful response generation from XAI engine."""
        # Configure the mock client and its methods
        mock_client_instance = MagicMock()
        mock_chat_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Successful Grok response"
        mock_choice.message = mock_message
        mock_chat_completion.choices = [mock_choice]
        mock_client_instance.chat.completions.create.return_value = mock_chat_completion
        mock_openai_class.return_value = mock_client_instance

        mock_client_instance = MagicMock()
        mock_chat_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Successful XAI response" # Updated text
        mock_choice.message = mock_message
        mock_chat_completion.choices = [mock_choice]
        mock_client_instance.chat.completions.create.return_value = mock_chat_completion
        mock_openai_class.return_value = mock_client_instance

        engine = XAI() # Renamed, XAI takes no args in __init__
        aiengine_arg_dict = {"model_name": "grok-test-model", "system_prompt": "System prompt for XAI."}
        apikeey_list = ["fake_xai_key"]
        role_name = "TestXAIBot"
        conversation_history = [
            Message(sender='User', content='Hello XAI!'),
            Message(sender=role_name, content='Hello User!'),
            Message(sender='User', content='How are you?')
        ]
        
        response = engine.generate_response( # Call with full args
            _aiengine_id="xai_grok", # Matches AIEngineInfo
            aiengine_arg_dict=aiengine_arg_dict,
            apikeey_list=apikeey_list,
            role_name=role_name,
            conversation_history=conversation_history
        )

        self.assertEqual(response, "Successful XAI response") # Updated text
        
        expected_messages = [
            {"role": "system", "content": aiengine_arg_dict["system_prompt"]},
            {"role": "user", "content": "User said:\nHello XAI!"}, # Updated text
            {"role": "assistant", "content": "Hello User!"},
            {"role": "user", "content": "User said:\nHow are you?"}
        ]
        
        mock_client_instance.chat.completions.create.assert_called_once_with(
            model=aiengine_arg_dict["model_name"],
            messages=expected_messages
        )
        mock_openai_class.assert_called_once_with(api_key="fake_xai_key", base_url="https://api.x.ai/v1")

    @patch('src.main.third_parties.xai.openai.OpenAI') # Patched to new location
    def test_xai_init_success(self, mock_openai_class): # Renamed
        """Tests successful initialization of XAI engine."""
        engine = XAI()
        self.assertIsInstance(engine, XAI)
        self.assertEqual(len(engine._apikeey_to_client_dict), 0)
        # _get_client is tested via generate_response, checking mock_openai_class call there.

    def test_xai_init_no_apikeey(self): # Renamed
        """XAI class takes no apikeey in __init__. This test might be obsolete or test generate_response."""
        # This test as-is for __init__ is not applicable.
        # Testing no apikeey for generate_response:
        engine = XAI()
        aiengine_arg_dict = {"model_name": "grok-no-key"}
        with self.assertRaises(AssertionError): # XAI asserts len(apikeey_list) == 1
            engine.generate_response("xai_grok", aiengine_arg_dict, [], "TestRole", [])

    # Test for APIConnectionError
    @patch('src.main.third_parties.xai.logging.error')
    @patch('src.main.third_parties.xai.openai.OpenAI') # Patch the OpenAI client constructor used by XAI
    def test_xai_response_api_connection_error(self, mock_openai_constructor, mock_logging_error):
        """Tests XAI engine's error handling for APIConnectionError."""
        mock_client_instance = MagicMock()
        # Make the mocked client's method raise the real exception from the globally imported openai
        mock_client_instance.chat.completions.create.side_effect = openai.APIConnectionError(request=MagicMock())
        mock_openai_constructor.return_value = mock_client_instance # The constructor returns our mock client

        engine = XAI()
        aiengine_arg_dict = {"model_name": "grok-conn-error"}
        apikeey_list = ["fake_xai_key_conn_error"]
        response = engine.generate_response("xai_grok", aiengine_arg_dict, apikeey_list, "TestRole", [])
        
        self.assertTrue(response.startswith("Error: Could not connect to Grok API."))
        mock_logging_error.assert_called_once()

    @patch('src.main.third_parties.xai.logging.error')
    @patch('src.main.third_parties.xai.openai.OpenAI')
    def test_xai_response_rate_limit_error(self, mock_openai_constructor, mock_logging_error):
        """Tests XAI engine's error handling for RateLimitError."""
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.side_effect = openai.RateLimitError("Rate limit exceeded", response=MagicMock(), body=None)
        mock_openai_constructor.return_value = mock_client_instance

        engine = XAI()
        aiengine_arg_dict = {"model_name": "grok-rate-limit"}
        apikeey_list = ["fake_xai_key_rate_limit"]
        response = engine.generate_response("xai_grok", aiengine_arg_dict, apikeey_list, "TestRole", [])

        self.assertTrue(response.startswith("Error: Grok API rate limit exceeded."))
        mock_logging_error.assert_called_once()

    @patch('src.main.third_parties.xai.logging.error')
    @patch('src.main.third_parties.xai.openai.OpenAI')
    def test_xai_response_authentication_error(self, mock_openai_constructor, mock_logging_error):
        """Tests XAI engine's error handling for AuthenticationError."""
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.side_effect = openai.AuthenticationError("Auth error", response=MagicMock(), body=None)
        mock_openai_constructor.return_value = mock_client_instance
        
        engine = XAI()
        aiengine_arg_dict = {"model_name": "grok-auth-error"}
        apikeey_list = ["fake_xai_key_auth_error"]
        response = engine.generate_response("xai_grok", aiengine_arg_dict, apikeey_list, "TestRole", [])

        self.assertTrue(response.startswith("Error: Grok API authentication failed."))
        mock_logging_error.assert_called_once()

    @patch('src.main.third_parties.xai.logging.error')
    @patch('src.main.third_parties.xai.openai.OpenAI')
    def test_xai_response_api_error(self, mock_openai_constructor, mock_logging_error):
        """Tests XAI engine's error handling for a generic APIError."""
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.side_effect = openai.APIError("Generic API error", request=MagicMock(), body=None)
        mock_openai_constructor.return_value = mock_client_instance

        engine = XAI()
        aiengine_arg_dict = {"model_name": "grok-api-error"}
        apikeey_list = ["fake_xai_key_api_error"]
        response = engine.generate_response("xai_grok", aiengine_arg_dict, apikeey_list, "TestRole", [])

        self.assertTrue(response.startswith("Error: An unexpected error occurred with the Grok API."))
        mock_logging_error.assert_called_once()

    @patch('src.main.third_parties.xai.logging.error')
    @patch('src.main.third_parties.xai.openai.OpenAI') # Patch only the OpenAI class
    def test_xai_response_unexpected_exception(self, mock_openai_constructor, mock_logging_error):
        """Tests XAI engine's error handling for an unexpected exception."""
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.side_effect = Exception("Something totally unexpected happened")
        mock_openai_constructor.return_value = mock_client_instance # The constructor returns our mock

        engine = XAI()
        aiengine_arg_dict = {"model_name": "grok-unexpected-error"}
        apikeey_list = ["fake_xai_key_unexpected_error"]
        response = engine.generate_response("xai_grok", aiengine_arg_dict, apikeey_list, "TestRole", [])

        self.assertTrue(response.startswith("Error: An unexpected error occurred. Details: Something totally unexpected happened"))
        mock_logging_error.assert_called_once()

    # This test seems to be misplaced as it was testing AIEngine/GrokEngine base class behavior.
    # For XAI (which inherits ThirdPartyBase), the apikeey and model_name are not direct __init__ args.
    # We can remove this or adapt it to test ThirdPartyBase if a generic test for it is needed.
    # For now, removing as XAI's specific init is tested in test_xai_init_success.
    # @patch('src.main.third_parties.google.genai')
    # def test_engine_base_class_init(self, mock_genai_sdk):
    #     """Tests that XAI correctly initializes attributes from AIEngine."""
    #     with patch('src.main.third_parties.xai.openai.OpenAI'):
    #         engine = XAI() # XAI init takes no args
    #         # Attributes like apikeey, model_name are not stored on XAI instance from __init__
    #         # self.assertEqual(engine.apikeey, "key123")
    #         # self.assertEqual(engine.model_name, "model-abc")
    #         pass # Test can be removed or re-purposed for ThirdPartyBase if needed.


# The TestCreateBot class was commented out as create_bot function seems to be removed.
# If bot creation logic is found elsewhere, new tests should be written.
# For now, the old TestCreateBot structure with updated engine names would look like:
#
# class TestCreateBot(unittest.TestCase):
#     """Tests for the `create_bot` factory function."""
#     @patch('src.main.third_parties.google.genai') # Example, if create_bot calls this
#     def test_create_google_bot_success(self, mock_genai_sdk): # Renamed
#         """Tests successful creation of a Bot with Google engine."""
#         # This test would need to be completely rewritten based on how bots are now created.
#         # Assuming create_bot still exists and works similarly for demonstration:
#         # engine_config = {"engine_type": "Google", "apikeey": "test_google_key"}
#         # bot = create_bot(bot_name="GoogleTestBot", system_prompt="Test", engine_config=engine_config)
#         # self.assertIsInstance(bot, Bot)
#         # self.assertIsInstance(bot.get_engine(), Google) # Check for Google instance
#         # self.assertEqual(bot.get_engine().apikeey, "test_google_key") # If apikeey is stored on engine
#         pass

#     def test_create_azure_openai_bot_success(self): # Renamed from test_create_openai_bot_success
#         # engine_config = {"engine_type": "AzureOpenAI", "apikeey": "test_openai_key"}
#         # bot = create_bot(bot_name="OpenAITestBot", system_prompt="Test", engine_config=engine_config)
#         # self.assertIsInstance(bot, Bot)
#         # self.assertIsInstance(bot.get_engine(), AzureOpenAI)
#         # self.assertEqual(bot.get_engine().apikeey, "test_openai_key")
#         pass

#     @patch('src.main.third_parties.xai.openai.OpenAI') # Example
#     def test_create_xai_bot_success(self, mock_xai_sdk): # Renamed
#         # engine_config = {"engine_type": "XAI", "apikeey": "test_xai_key"}
#         # bot = create_bot(bot_name="XAITestBot", system_prompt="Test", engine_config=engine_config)
#         # self.assertIsInstance(bot, Bot)
#         # self.assertIsInstance(bot.get_engine(), XAI)
#         # self.assertEqual(bot.get_engine().apikeey, "test_xai_key")
#         pass
#
#    # ... other create_bot tests would also need similar renaming and logic updates ...
#
#    @patch('src.main.third_parties.google.genai') # Example patch for the Google/Gemini engine
#    def test_create_google_bot_default_model(self, mock_genai_sdk): # Renamed
#        # engine_config = {"engine_type": "Google", "apikeey": "test_key_default_model"}
#        # bot = create_bot(bot_name="DefaultModelGoogle", system_prompt="Test", engine_config=engine_config)
#        # self.assertIsInstance(bot.get_engine(), Google)
#        # Assuming Google class sets a default model_name if not provided.
#        # This depends on the actual implementation of Google class and create_bot.
#        # For instance, if Google class has a DEFAULT_MODEL_NAME constant:
#        # self.assertEqual(bot.get_engine().model_name, Google.DEFAULT_MODEL_NAME)
#        pass


if __name__ == '__main__':
    unittest.main()
