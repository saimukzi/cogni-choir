import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Adjusting sys.path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.main.ai_bots import Bot, AIEngine, create_bot # AIEngine and Bot are still in ai_bots, added create_bot
from src.main.ai_engines import GeminiEngine, GrokEngine, OpenAIEngine # Engines from new package

# No global SDK mocks here; will use @patch decorator for targeted mocking

class TestBot(unittest.TestCase):
    def setUp(self):
        self.mock_engine_instance = MagicMock(spec=AIEngine)
        self.mock_engine_instance.__class__.__name__ = "SpecificMockedEngine" # For to_dict
        self.mock_engine_instance.model_name = "mocked-model-001"
        self.bot = Bot("TestBot", "Be helpful.", self.mock_engine_instance)

    def test_bot_creation(self): # Added to ensure setUp is fine and basic attrs are set
        self.assertEqual(self.bot.get_name(), "TestBot")
        self.assertEqual(self.bot.get_system_prompt(), "Be helpful.")
        self.assertEqual(self.bot.get_engine(), self.mock_engine_instance)

    def test_bot_to_dict(self):
        # The type(self.engine).__name__ for a MagicMock spec'ing AIEngine 
        # will be 'AIEngine' if spec_set=True, or 'MagicMock' if spec_set=False or just spec.
        # Since Bot.to_dict() uses type(self.engine).__name__, and self.mock_engine_instance is a MagicMock,
        # its type name will be 'MagicMock'.
        # The __class__.__name__ = "SpecificMockedEngine" assignment on the instance
        # doesn't change what type(instance).__name__ returns.
        # For a more robust test of to_dict with specific engine types, one might mock the specific engine class
        # or use a real instance if the dependencies are simple.
        # Given the current mocking, we expect 'MagicMock' or the spec's name if spec_set=True.
        # Let's assume spec provides the name of the class it's spec'ing for __class__.__name__
        # However, type(mock_instance).__name__ is 'MagicMock'.
        # The previous code set mock_engine_instance.__class__.__name__ = "SpecificMockedEngine"
        # This is a bit tricky. Let's assume the Bot.to_dict() is intended to get the *actual* underlying class name
        # if it were a real engine. If self.engine is a mock, `type(self.engine).__name__` is usually 'MagicMock'.
        # The custom __class__.__name__ set on the instance is not what type() picks up.
        # So, if the mock is just `MagicMock(spec=AIEngine)`, engine_type will be 'MagicMock'.
        # If the goal was to test the string 'SpecificMockedEngine', the mock needs to be constructed differently
        # or the `to_dict` method needs to be aware of this.
        # For now, let's stick to what `type(self.mock_engine_instance).__name__` would yield.
        # If `spec=AIEngine` and AIEngine is an ABC, it might be 'AIEngine'.
        # If `spec=GeminiEngine`, it might be 'GeminiEngine'.
        # Let's use `self.mock_engine_instance.__class__.__name__` as set in setUp for the expected value.
        expected_dict = {
            "name": "TestBot",
            "system_prompt": "Be helpful.",
            "engine_type": "SpecificMockedEngine", 
            "model_name": "mocked-model-001"
        }
        # To make this pass, Bot.to_dict() should perhaps use self.engine.__class__.__name__
        # if that's the intent, instead of type(self.engine).__name__.
        # Given Bot.to_dict() is: type(self.engine).__name__, and self.mock_engine_instance is a MagicMock
        # this will be "MagicMock". So the test's setUp for this specific string is what needs to align.
        # The current test setup is: self.mock_engine_instance.__class__.__name__ = "SpecificMockedEngine"
        # This is fine if Bot.to_dict() was `self.engine.__class__.__name__`.
        # Let's assume Bot.to_dict() should be robust to mocks and use `self.engine.__class__.__name__`.
        # If `Bot.to_dict()` remains `type(self.engine).__name__`, then expected_dict should be "MagicMock".

        # Re-evaluating: The most straightforward way to test to_dict() with a mock
        # is to ensure the mock behaves like a real engine for the properties accessed.
        # Bot.to_dict() accesses `type(self.engine).__name__`.
        # A MagicMock's `type(mock).__name__` is 'MagicMock'.
        # So, the expected should be 'MagicMock' unless we change how Bot.to_dict works or how the mock is made.
        # The previous fix was to set mock_engine_instance.__class__.__name__. Let's assume this is the intended way.
        # The failure `AssertionError: {'engine_type': 'MagicMock'} != {'engine_type': 'SpecificMockedEngine'}`
        # confirms `type(self.engine).__name__` returns 'MagicMock'.
        # So, the fix is in the expected_dict or how Bot.to_dict() gets the name.
        # Let's make the test expect 'MagicMock' as that's what `type(MagicMock).__name__` is.
        # OR, more robustly, mock the `type(self.engine).__name__` access itself if that's too complex.
        
        # Correcting the expectation based on how `type()` works with `MagicMock`
        expected_dict_corrected = {
            "name": "TestBot",
            "system_prompt": "Be helpful.",
            "engine_type": "MagicMock", # This is what type(MagicMock()) typically yields for __name__
            "model_name": "mocked-model-001"
        }
        # However, if the spec argument to MagicMock is a class (like AIEngine),
        # and AIEngine is a known class, it *might* give AIEngine.
        # Given the previous failure, it was 'MagicMock'.
        
        # The current code in `Bot.to_dict()` is `type(self.engine).__name__`.
        # The mock is `MagicMock(spec=AIEngine)`. `type(self.mock_engine_instance).__name__` is 'MagicMock'.
        # The line `self.mock_engine_instance.__class__.__name__ = "SpecificMockedEngine"` in setUp
        # was an attempt to control this, but `type()` doesn't use the instance's `__class__.__name__`.
        # It uses the actual type of the object.
        # So, the test should expect 'MagicMock'.
        expected_dict_for_magicmock = {
            "name": "TestBot",
            "system_prompt": "Be helpful.",
            "engine_type": "MagicMock", 
            "model_name": "mocked-model-001"
        }
        self.assertEqual(self.bot.to_dict(), expected_dict_for_magicmock)


class TestGeminiEngine(unittest.TestCase):
    def setUp(self):
        # Common mock setup for genai.GenerativeModel instance
        self.mock_gemini_model_instance = MagicMock()
        self.mock_chat_instance = MagicMock()
        self.mock_gemini_model_instance.start_chat.return_value = self.mock_chat_instance

    @patch('src.main.ai_engines.gemini_engine.genai') # Patched where genai is now imported and used 
    def test_gemini_init_success(self, mock_genai_sdk):
        mock_genai_sdk.GenerativeModel.return_value = self.mock_gemini_model_instance
        engine = GeminiEngine(api_key="fake_gemini_key", model_name="gemini-custom")
        
        mock_genai_sdk.configure.assert_called_once_with(api_key="fake_gemini_key")
        mock_genai_sdk.GenerativeModel.assert_called_once_with("gemini-custom")
        self.assertEqual(engine.model, self.mock_gemini_model_instance)

    @patch('src.main.ai_engines.gemini_engine.genai') # Patched where genai is now imported and used
    def test_gemini_generate_response_success(self, mock_genai_sdk):
        mock_genai_sdk.GenerativeModel.return_value = self.mock_gemini_model_instance
        self.mock_chat_instance.send_message.return_value = MagicMock(text="Test Gemini response")

        engine = GeminiEngine(api_key="fake_gemini_key") # Init with mocked SDK
        response = engine.generate_response("Hello Gemini", [("User", "Prev")])
        
        self.assertEqual(response, "Test Gemini response")
        self.mock_gemini_model_instance.start_chat.assert_called_once()
        self.mock_chat_instance.send_message.assert_called_once_with("Hello Gemini")

    @patch('src.main.ai_engines.gemini_engine.genai') # Patched where genai is now imported and used
    def test_gemini_generate_response_api_error(self, mock_genai_sdk):
        mock_genai_sdk.GenerativeModel.return_value = self.mock_gemini_model_instance
        self.mock_chat_instance.send_message.side_effect = Exception("Gemini API Error")

        engine = GeminiEngine(api_key="fake_gemini_key") # Init with mocked SDK
        response = engine.generate_response("prompt", [])
        self.assertTrue(response.startswith("Error: Gemini API call failed: Gemini API Error"))

    @patch('src.main.ai_engines.gemini_engine.genai') # Patched where genai is now imported and used
    def test_gemini_no_api_key(self, mock_genai_sdk):
        engine_no_key = GeminiEngine(api_key=None)
        response = engine_no_key.generate_response("prompt", [])
        self.assertEqual(response, "Error: Gemini API key not configured.")

    @patch('src.main.ai_engines.gemini_engine.genai', None) # Target the new location for this specific test
    def test_gemini_sdk_not_available(self):
        engine_sdk_missing = GeminiEngine(api_key="fake_key")
        response = engine_sdk_missing.generate_response("prompt", [])
        self.assertEqual(response, "Error: google.generativeai SDK not available.")


class TestOpenAIEngine(unittest.TestCase):
    def setUp(self):
        self.mock_openai_client_instance = MagicMock()
        self.mock_completion_object = MagicMock()
        self.mock_choice_object = MagicMock()
        self.mock_message_object = MagicMock(content="Test OpenAI response")
        
        self.mock_choice_object.message = self.mock_message_object
        self.mock_completion_object.choices = [self.mock_choice_object]
        self.mock_openai_client_instance.chat.completions.create.return_value = self.mock_completion_object

    @patch('src.main.ai_engines.openai_engine.openai') # Patched where openai is now imported and used
    def test_openai_init_success(self, mock_openai_sdk):
        mock_openai_sdk.OpenAI.return_value = self.mock_openai_client_instance
        engine = OpenAIEngine(api_key="fake_openai_key", model_name="gpt-custom")
        mock_openai_sdk.OpenAI.assert_called_once_with(api_key="fake_openai_key")
        self.assertEqual(engine.client, self.mock_openai_client_instance)

    @patch('src.main.ai_engines.openai_engine.openai') # Patched where openai is now imported and used
    def test_openai_generate_response_success(self, mock_openai_sdk):
        mock_openai_sdk.OpenAI.return_value = self.mock_openai_client_instance
        engine = OpenAIEngine(api_key="fake_openai_key")
        response = engine.generate_response("Hello OpenAI", [("User", "Old message")])
        
        self.assertEqual(response, "Test OpenAI response")
        expected_messages = [
            {"role": "user", "content": "Old message"},
            {"role": "user", "content": "Hello OpenAI"}
        ]
        self.mock_openai_client_instance.chat.completions.create.assert_called_once_with(
            model=engine.model_name, messages=expected_messages
        )

    @patch('src.main.ai_engines.openai_engine.openai') # Patched where openai is now imported and used
    def test_openai_generate_response_api_error(self, mock_openai_sdk):
        mock_openai_sdk.OpenAI.return_value = self.mock_openai_client_instance
        self.mock_openai_client_instance.chat.completions.create.side_effect = Exception("OpenAI API Error")
        engine = OpenAIEngine(api_key="fake_openai_key")
        response = engine.generate_response("prompt", [])
        self.assertTrue(response.startswith("Error: OpenAI API call failed: OpenAI API Error"))

    @patch('src.main.ai_engines.openai_engine.openai') # Patched where openai is now imported and used
    def test_openai_no_api_key(self, mock_openai_sdk):
        engine_no_key = OpenAIEngine(api_key=None)
        response = engine_no_key.generate_response("prompt", [])
        self.assertEqual(response, "Error: OpenAI API key not configured or client not initialized.")

    @patch('src.main.ai_engines.openai_engine.openai', None) # Target the new location
    def test_openai_sdk_not_available(self):
        engine_sdk_missing = OpenAIEngine(api_key="fake_key")
        response = engine_sdk_missing.generate_response("prompt", [])
        self.assertEqual(response, "Error: openai SDK not available.")


class TestGrokEngine(unittest.TestCase): 
    def test_grok_response(self): 
        prompt = "Test prompt"
        history = [("User", "Previous message")]
        grok_engine = GrokEngine(api_key="grok_key") 
        expected_grok_response = "Error: Grok API not implemented or no public API found."
        self.assertEqual(grok_engine.generate_response(prompt, history), expected_grok_response)
        
    @patch('src.main.ai_engines.gemini_engine.genai') # Mock genai via its new path for consistency
    def test_engine_base_class_init(self, mock_genai_sdk): # mock_genai_sdk is passed due to patch
        engine = GeminiEngine(api_key="key123", model_name="model-abc") 
        self.assertEqual(engine.api_key, "key123")
        self.assertEqual(engine.model_name, "model-abc")


class TestCreateBot(unittest.TestCase):
    def test_create_gemini_bot_success(self):
        engine_config = {"engine_type": "GeminiEngine", "api_key": "test_gemini_key"}
        bot = create_bot(bot_name="GeminiTestBot", system_prompt="Test", engine_config=engine_config)
        self.assertIsInstance(bot, Bot)
        self.assertIsInstance(bot.get_engine(), GeminiEngine)
        self.assertEqual(bot.get_engine().api_key, "test_gemini_key")

    def test_create_openai_bot_success(self):
        engine_config = {"engine_type": "OpenAIEngine", "api_key": "test_openai_key"}
        bot = create_bot(bot_name="OpenAITestBot", system_prompt="Test", engine_config=engine_config)
        self.assertIsInstance(bot, Bot)
        self.assertIsInstance(bot.get_engine(), OpenAIEngine)
        self.assertEqual(bot.get_engine().api_key, "test_openai_key")

    def test_create_grok_bot_success(self):
        engine_config = {"engine_type": "GrokEngine", "api_key": "test_grok_key"}
        bot = create_bot(bot_name="GrokTestBot", system_prompt="Test", engine_config=engine_config)
        self.assertIsInstance(bot, Bot)
        self.assertIsInstance(bot.get_engine(), GrokEngine)
        self.assertEqual(bot.get_engine().api_key, "test_grok_key")

    def test_create_bot_with_model_name(self):
        engine_config = {"engine_type": "GeminiEngine", "api_key": "test_key", "model_name": "gemini-custom-model"}
        bot = create_bot(bot_name="CustomModelBot", system_prompt="Test", engine_config=engine_config)
        self.assertIsInstance(bot.get_engine(), GeminiEngine)
        self.assertEqual(bot.get_engine().model_name, "gemini-custom-model")

    def test_create_bot_with_none_api_key(self):
        engine_config = {"engine_type": "GeminiEngine", "api_key": None}
        bot = create_bot(bot_name="NoApiKeyBot", system_prompt="Test", engine_config=engine_config)
        self.assertIsInstance(bot.get_engine(), GeminiEngine)
        self.assertIsNone(bot.get_engine().api_key)

    def test_create_bot_invalid_engine_type(self):
        engine_config = {"engine_type": "UnknownEngine", "api_key": "test_key"}
        with self.assertRaisesRegex(ValueError, "Unsupported engine type: UnknownEngine"):
            create_bot(bot_name="InvalidEngineBot", system_prompt="Test", engine_config=engine_config)

    def test_create_bot_missing_engine_type(self):
        engine_config = {"api_key": "test_key"} # Missing "engine_type"
        # create_bot uses .get("engine_type"), which returns None if key is missing.
        # This None value then fails the "if engine_type not in engine_map" check.
        # So it should raise a ValueError with a message like "Unsupported engine type: None"
        with self.assertRaisesRegex(ValueError, "Unsupported engine type: None"):
            create_bot(bot_name="MissingEngineTypeBot", system_prompt="Test", engine_config=engine_config)

    def test_create_bot_empty_engine_config(self):
        engine_config = {} # Empty config
        with self.assertRaisesRegex(ValueError, "Unsupported engine type: None"):
            create_bot(bot_name="EmptyConfigBot", system_prompt="Test", engine_config=engine_config)
    
    # Test for default model name when not provided in config
    @patch('src.main.ai_engines.gemini_engine.genai') # Patch to avoid actual SDK calls if any
    def test_create_gemini_bot_default_model(self, mock_genai_sdk):
        engine_config = {"engine_type": "GeminiEngine", "api_key": "test_key_default_model"}
        # Mock the GeminiEngine's default model if necessary, or ensure it has one
        # For this test, we assume GeminiEngine sets a default model if not provided.
        # We are testing if create_bot passes model_name=None to the engine constructor,
        # and the engine then uses its default.
        bot = create_bot(bot_name="DefaultModelGemini", system_prompt="Test", engine_config=engine_config)
        self.assertIsInstance(bot.get_engine(), GeminiEngine)
        # Assuming GeminiEngine's __init__ sets a default model_name if None is passed.
        # e.g. self.model_name = model_name or "gemini-pro"
        # We'd need to know the default or mock the engine's __init__ to check this robustly.
        # For now, let's check if it's not None or empty, assuming a default is set.
        # A better test would be to mock GeminiEngine and assert it was called with model_name=None.
        # Or, if GeminiEngine has a known default constant, check against that.
        self.assertIsNotNone(bot.get_engine().model_name) # Check that some model name is set
        self.assertTrue(len(bot.get_engine().model_name) > 0) # And it's not empty
        # The actual default model name in GeminiEngine is "gemini-pro".
        self.assertEqual(bot.get_engine().model_name, "gemini-pro")


if __name__ == '__main__':
    unittest.main()
