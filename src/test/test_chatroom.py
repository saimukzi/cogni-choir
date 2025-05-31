"""Unit tests for Chatroom and ChatroomManager classes.

This module tests the core functionalities of chatrooms, including managing
bots and messages, serialization (to_dict, from_dict), and persistence.
It also tests the ChatroomManager for operations like creating, loading,
deleting, renaming, and cloning chatrooms, often using mocks for file
operations and API key management.
"""
import unittest
from unittest.mock import patch, mock_open, MagicMock
import sys
import logging # Added import for logging
import os
# import json # json.load is patched directly where used
import time # For message timestamp tests

# Adjusting sys.path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.main.chatroom import Chatroom, ChatroomManager, _sanitize_filename, DATA_DIR
from src.main.ai_bots import Bot # Bot is still in ai_bots
from src.main.ai_base import AIEngine # Import AIEngine from ai_base for spec
from src.main.ai_engines import GeminiEngine, AzureOpenAIEngine, GrokEngine
from src.main.message import Message
from src.main.api_key_manager import ApiKeyManager


class TestChatroom(unittest.TestCase):
    """Tests for the Chatroom class."""
    def setUp(self):
        """Sets up a Chatroom instance with a mock manager for each test."""
        self.mock_manager = MagicMock(spec=ChatroomManager)
        self.mock_manager.api_key_manager = MagicMock(spec=ApiKeyManager) # Mock ApiKeyManager on the mock manager
        
        self.chatroom = Chatroom("Test Room")
        self.chatroom.manager = self.mock_manager # Assign the mock manager
        self.chatroom.filepath = os.path.join(DATA_DIR, "test_room.json") # Dummy filepath for save

        self.dummy_engine = GeminiEngine(api_key="test_key") 

    def test_initialization(self):
        """Tests the initial state of a newly created Chatroom."""
        self.assertEqual(self.chatroom.name, "Test Room") # Use property
        self.assertEqual(len(self.chatroom.list_bots()), 0)
        self.assertEqual(len(self.chatroom.get_messages()), 0)

    # Direct set_name is removed, renaming is handled by ChatroomManager
    # def test_set_get_name(self): 
    #     pass 

    def test_add_get_list_remove_bot(self):
        """Tests adding, retrieving, listing, and removing bots from a chatroom."""
        bot1 = Bot("Bot1", "System prompt 1", self.dummy_engine)
        bot2 = Bot("Bot2", "System prompt 2", self.dummy_engine)

        self.chatroom.add_bot(bot1)
        self.assertEqual(len(self.chatroom.list_bots()), 1)
        self.assertIn(bot1, self.chatroom.list_bots())
        self.assertEqual(self.chatroom.get_bot("Bot1"), bot1)
        self.mock_manager._notify_chatroom_updated.assert_called_with(self.chatroom)
        self.mock_manager._notify_chatroom_updated.reset_mock() # Reset for next call

        self.chatroom.add_bot(bot2)
        self.assertEqual(len(self.chatroom.list_bots()), 2)
        self.mock_manager._notify_chatroom_updated.assert_called_with(self.chatroom)
        self.mock_manager._notify_chatroom_updated.reset_mock()

        self.chatroom.remove_bot("Bot1")
        self.assertEqual(len(self.chatroom.list_bots()), 1)
        self.assertNotIn(bot1, self.chatroom.list_bots())
        self.mock_manager._notify_chatroom_updated.assert_called_with(self.chatroom)
        self.mock_manager._notify_chatroom_updated.reset_mock()

        self.chatroom.remove_bot("NonExistentBot")
        self.mock_manager._notify_chatroom_updated.assert_not_called() # Should not be called if bot not found

        self.chatroom.remove_bot("Bot2")
        self.assertEqual(len(self.chatroom.list_bots()), 0)
        self.mock_manager._notify_chatroom_updated.assert_called_with(self.chatroom)

    def test_add_get_messages(self):
        """Tests adding messages to the chatroom and retrieving them."""
        msg1 = self.chatroom.add_message("User1", "Hello")
        self.assertIsInstance(msg1, Message)
        self.assertEqual(len(self.chatroom.get_messages()), 1)
        self.mock_manager._notify_chatroom_updated.assert_called_with(self.chatroom)
        self.mock_manager._notify_chatroom_updated.reset_mock()

        self.chatroom.add_message("Bot1", "Hi there!")
        self.assertEqual(len(self.chatroom.get_messages()), 2)
        self.mock_manager._notify_chatroom_updated.assert_called_with(self.chatroom)

    def test_delete_message(self):
        msg1_ts = self.chatroom.add_message("User1", "Msg1").timestamp
        self.mock_manager._notify_chatroom_updated.reset_mock()
        msg2_ts = self.chatroom.add_message("User2", "Msg2").timestamp
        self.mock_manager._notify_chatroom_updated.reset_mock()
        self.assertEqual(len(self.chatroom.get_messages()), 2)

        self.assertTrue(self.chatroom.delete_message(msg1_ts))
        self.assertEqual(len(self.chatroom.get_messages()), 1)
        self.assertEqual(self.chatroom.get_messages()[0].timestamp, msg2_ts)
        self.mock_manager._notify_chatroom_updated.assert_called_with(self.chatroom)
        self.mock_manager._notify_chatroom_updated.reset_mock()

        self.assertFalse(self.chatroom.delete_message(time.time())) # Non-existent timestamp
        self.assertEqual(len(self.chatroom.get_messages()), 1)
        self.mock_manager._notify_chatroom_updated.assert_not_called()

        self.assertTrue(self.chatroom.delete_message(msg2_ts))
        self.assertEqual(len(self.chatroom.get_messages()), 0)
        self.mock_manager._notify_chatroom_updated.assert_called_with(self.chatroom)

    @patch.object(logging.getLogger('src.main.chatroom.Chatroom'), 'warning')
    def test_chatroom_save_load_cycle(self, mock_logger_warning):
        """Tests the Chatroom to_dict and from_dict methods (serialization/deserialization).
        
        This comprehensive test covers scenarios including:
        - Bots with different AI engine types (Gemini, AzureOpenAI, and a custom NoKeyEngine).
        - Correct serialization of bot details (name, prompt, engine type, model name).
        - Deserialization (`from_dict`) behavior when API keys are available, partially
          available, or missing for bots that require them, verifying that appropriate
          warnings are logged.
        - Ensures messages are correctly serialized and deserialized.
        - Verifies that bots with unsupported engine types (like the test's NoKeyEngine
          which isn't in the main application's engine map) are not loaded and
          trigger appropriate warnings.
        """
        # Define NoKeyEngine (can be an inner class or defined in the test module)
        class NoKeyEngine(AIEngine): # Make sure AIEngine is imported
            def __init__(self, api_key: str = None, model_name: str = "no-key-model"):
                super().__init__(api_key, model_name)
            def generate_response(self, role_name: str, system_prompt: str, conversation_history: list[Message]) -> str:
                return "NoKeyEngine response"
            def requires_api_key(self) -> bool:
                return False

        # Setup chatroom
        bot1 = Bot("BotAlpha", "Prompt Alpha", GeminiEngine(api_key="gemini_test_key", model_name="gemini-alpha"))
        bot2 = Bot("BotBeta", "Prompt Beta", AzureOpenAIEngine(api_key="azureopenai_test_key", model_name="azureopenai-beta"))
        bot3 = Bot("BotGamma", "Prompt Gamma", NoKeyEngine(model_name="no-key-gamma")) # Add this bot

        self.chatroom.add_bot(bot1)
        self.chatroom.add_bot(bot2)
        self.chatroom.add_bot(bot3) # Add this bot
        self.chatroom.add_message("User", "Hello Bots")
        self.chatroom.add_message("BotAlpha", "Hello User from Alpha") # Keep one message for original tests
        
        dict_data = self.chatroom.to_dict()
        # Ensure engine_type for NoKeyEngine is 'NoKeyEngine'
        for bot_d in dict_data["bots"]:
            if bot_d["name"] == "BotGamma":
                self.assertEqual(bot_d["engine_type"], "NoKeyEngine")


        # --- Scenario 1: Key required, not provided (Gemini) ---
        mock_api_key_manager_missing_gemini = MagicMock(spec=ApiKeyManager)
        mock_api_key_manager_missing_gemini.load_key.side_effect = lambda service_name: {
            "AzureOpenAIEngine": "azureopenai_test_key" # No Gemini key, NoKey key also missing (but not needed)
        }.get(service_name)
        
        # Bot data for this specific test scenario
        # Note: engine_type must match what Bot.to_dict() produces (i.e., class name)
        bot_data_gemini_for_test = {
            "name": "BotAlpha", "system_prompt": "Prompt Alpha Sys", 
            "engine_type": "GeminiEngine", "model_name": "gemini-alpha"
        }
        bot_data_azureopenai_for_test = {
            "name": "BotBeta", "system_prompt": "Prompt Beta Sys",
            "engine_type": "AzureOpenAIEngine", "model_name": "azureopenai-beta"
        }
        bot_data_nokey_for_test = { # This is BotGamma
            "name": "BotGamma", "system_prompt": "Prompt Gamma Sys",
            "engine_type": "NoKeyEngine", "model_name": "no-key-gamma"
        }
            
        # Use this as an instance variable for the side effect function to access
        self.test_data_missing_keys_scen1 = { 
            "name": "TestRoomMissingKeys", # Chatroom name for warnings
            "bots": [bot_data_gemini_for_test, bot_data_azureopenai_for_test, bot_data_nokey_for_test],
            "messages": []
        }

        # Mock engine instances to be returned by the mocked create_bot
        mock_engine_alpha = MagicMock(spec=AIEngine)
        mock_engine_alpha.api_key = None # API key is None because mock_api_key_manager_missing_gemini returns None for Gemini
        mock_engine_alpha.model_name = bot_data_gemini_for_test['model_name']
        mock_engine_alpha.requires_api_key.return_value = True # GeminiEngine requires a key

        mock_engine_beta = MagicMock(spec=AIEngine)
        mock_engine_beta.api_key = "azureopenai_test_key" # API key is provided for AzureOpenAI by mock_api_key_manager_missing_gemini
        mock_engine_beta.model_name = bot_data_azureopenai_for_test['model_name']
        mock_engine_beta.requires_api_key.return_value = True # AzureOpenAIEngine requires a key

        def mock_create_bot_side_effect(bot_name, system_prompt, engine_config):
            # Find the bot_data from self.test_data_missing_keys_scen1 to ensure prompts match
            current_bot_data = next((b for b in self.test_data_missing_keys_scen1['bots'] if b['name'] == bot_name), None)
            if not current_bot_data:
                 raise AssertionError(f"Bot data not found in self.test_data_missing_keys_scen1 for {bot_name}")
            
            expected_system_prompt = current_bot_data['system_prompt']
            self.assertEqual(system_prompt, expected_system_prompt, f"System prompt mismatch for {bot_name}")

            if engine_config['engine_type'] == "GeminiEngine" and bot_name == "BotAlpha":
                return Bot(name="BotAlpha", system_prompt=system_prompt, engine=mock_engine_alpha)
            elif engine_config['engine_type'] == "AzureOpenAIEngine" and bot_name == "BotBeta":
                return Bot(name="BotBeta", system_prompt=system_prompt, engine=mock_engine_beta)
            elif engine_config['engine_type'] == "NoKeyEngine" and bot_name == "BotGamma":
                raise ValueError("Unsupported engine type: NoKeyEngine")
            raise AssertionError(f"Unexpected call to mock_create_bot with: {bot_name}, {engine_config}")

        with patch('src.main.ai_bots.create_bot') as mock_create_bot:
            mock_create_bot.side_effect = mock_create_bot_side_effect
            reloaded_chatroom_missing_gemini = Chatroom.from_dict(
                self.test_data_missing_keys_scen1, 
                manager=self.mock_manager,
                filepath="dummy_missing.json",
                api_key_manager=mock_api_key_manager_missing_gemini
            )

        # Assertions for Scenario 1
        self.assertEqual(len(reloaded_chatroom_missing_gemini.list_bots()), 2, "Should load 2 bots (Alpha, Beta), Gamma fails.")

        reloaded_bot_alpha_scen1 = reloaded_chatroom_missing_gemini.get_bot("BotAlpha")
        self.assertIsNotNone(reloaded_bot_alpha_scen1, "BotAlpha should be loaded in Scenario 1")
        self.assertIs(reloaded_bot_alpha_scen1.get_engine(), mock_engine_alpha, "Engine for BotAlpha (scen1) should be mock_engine_alpha")
        
        reloaded_bot_beta_scen1 = reloaded_chatroom_missing_gemini.get_bot("BotBeta")
        self.assertIsNotNone(reloaded_bot_beta_scen1, "BotBeta should be loaded in Scenario 1")
        self.assertIs(reloaded_bot_beta_scen1.get_engine(), mock_engine_beta, "Engine for BotBeta (scen1) should be mock_engine_beta")

        self.assertIsNone(reloaded_chatroom_missing_gemini.get_bot("BotGamma"), "BotGamma (NoKeyEngine) should not be loaded.")

        # Warning assertions
        expected_gemini_warning = f"API key for Gemini not found for bot 'BotAlpha' in chatroom '{self.test_data_missing_keys_scen1['name']}'. Bot may not function as it requires an API key."
        mock_logger_warning.assert_any_call(expected_gemini_warning)
        
        expected_nokey_warning_scen1 = f"Failed to create bot 'BotGamma' from data in chatroom '{self.test_data_missing_keys_scen1['name']}' due to: Unsupported engine type: NoKeyEngine"
        mock_logger_warning.assert_any_call(expected_nokey_warning_scen1)
        
        # Verify no warning for BotBeta as its key is provided by mock_api_key_manager_missing_gemini
        unexpected_azureopenai_warning_fragment = "API key for AzureOpenAI not found for bot 'BotBeta'"
        for call in mock_logger_warning.call_args_list:
            logged_message = call[0][0]
            if "BotBeta" in logged_message: # Only check calls related to BotBeta
                self.assertNotIn(unexpected_azureopenai_warning_fragment, logged_message, "Warning for BotBeta (AzureOpenAI) was logged but should not have been as key was provided.")
        
        mock_logger_warning.reset_mock()

        # --- Scenario 2: All Keys provided / Not Required (original test logic adapted) ---
        mock_api_key_manager_all_keys = MagicMock(spec=ApiKeyManager)
        mock_api_key_manager_all_keys.load_key.side_effect = lambda service_name: {
            "GeminiEngine": "gemini_test_key_loaded",
            "AzureOpenAIEngine": "azureopenai_test_key_loaded",
            # NoKeyEngine doesn't need a key, so it doesn't matter if "NoKey" is here or not
        }.get(service_name)

        # Patch sys.modules to ensure from_dict can find the *actual* NoKeyEngine class
        with patch.dict(sys.modules['src.main.ai_engines'].__dict__, {
            'GeminiEngine': GeminiEngine, # Real engine
            'GrokEngine': GrokEngine,     # Real engine
            'NoKeyEngine': NoKeyEngine    # The test's actual NoKeyEngine class
        }, clear=False):
            reloaded_chatroom_all_keys = Chatroom.from_dict(
                dict_data, # Use the original dict_data, which now includes BotGamma with NoKeyEngine
                manager=self.mock_manager,
                filepath="dummy_all_keys.json", # Original self.chatroom.filepath is "test_room.json"
                api_key_manager=mock_api_key_manager_all_keys
            )

        # Assert no warnings were logged for missing keys in this scenario
        for call_args in mock_logger_warning.call_args_list:
            arg_str = call_args[0][0]
            self.assertNotIn("API key for Gemini not found", arg_str, f"Unexpected warning: {arg_str}")
            self.assertNotIn("API key for AzureOpenAI not found", arg_str, f"Unexpected warning: {arg_str}")
            self.assertNotIn("API key for NoKey not found", arg_str, f"Unexpected warning: {arg_str}") # Assuming NoKeyEngine doesn't trigger this
        
        # Original assertions from the test
        self.assertEqual(self.chatroom.name, reloaded_chatroom_all_keys.name) # Name is "Test Room"
        # BotGamma (NoKeyEngine) will not be loaded by create_bot, so only 2 bots are expected.
        self.assertEqual(len(reloaded_chatroom_all_keys.list_bots()), 2, "Should reload 2 out of 3 bots, skipping NoKeyEngine bot")
        self.assertEqual(len(self.chatroom.get_messages()), len(reloaded_chatroom_all_keys.get_messages()))

        # Verify Missing BotGamma and Reloaded BotAlpha, BotBeta in reloaded_chatroom_all_keys (Scenario 2)
        # BotGamma (NoKeyEngine) will fail to load because NoKeyEngine is not in create_bot's map.
        # This assertion was already present and correct for Scenario 2.
        self.assertIsNone(reloaded_chatroom_all_keys.get_bot("BotGamma"), "BotGamma (NoKeyEngine) should not have been loaded in Scenario 2.") # This line remains from previous version.

        # BotAlpha (GeminiEngine) - key is "gemini_test_key_loaded" - uses REAL GeminiEngine
        reloaded_bot_alpha_s2 = reloaded_chatroom_all_keys.get_bot("BotAlpha")
        self.assertIsNotNone(reloaded_bot_alpha_s2)
        self.assertIsInstance(reloaded_bot_alpha_s2.get_engine(), GeminiEngine)
        self.assertEqual(reloaded_bot_alpha_s2.get_engine().api_key, "gemini_test_key_loaded")
        self.assertEqual(reloaded_bot_alpha_s2.get_engine().model_name, "gemini-alpha")
        
        # BotBeta (AzureOpenAIEngine) - key is "azureopenai_test_key_loaded"
        reloaded_bot_beta_s2 = reloaded_chatroom_all_keys.get_bot("BotBeta")
        self.assertIsNotNone(reloaded_bot_beta_s2)
        self.assertIsInstance(reloaded_bot_beta_s2.get_engine(), AzureOpenAIEngine)
        self.assertEqual(reloaded_bot_beta_s2.get_engine().api_key, "azureopenai_test_key_loaded")
        self.assertEqual(reloaded_bot_beta_s2.get_engine().model_name, "azureopenai-beta")

        # Add warning assertion for BotGamma failing to load in Scenario 2
        # The engine_type for BotGamma is "NoKeyEngine"
        expected_nokey_warning_scen2 = f"Failed to create bot 'BotGamma' from data in chatroom 'Test Room' due to: Unsupported engine type: NoKeyEngine"
        # This warning occurs during the creation of `reloaded_chatroom_missing_gemini`
        # So, mock_logger_warning.assert_any_call for this should be checked after that object's creation.
        # The current structure checks mock_logger_warning calls after `reloaded_chatroom_missing_gemini` is created.
        mock_logger_warning.assert_any_call(expected_nokey_warning_scen2)
        
        # Assertions for messages in reloaded_chatroom_all_keys (Scenario 2)
        for i, original_msg in enumerate(self.chatroom.get_messages()):
            reloaded_msg = reloaded_chatroom_all_keys.get_messages()[i]
            self.assertEqual(original_msg.sender, reloaded_msg.sender)
            self.assertEqual(original_msg.content, reloaded_msg.content)
            self.assertEqual(original_msg.timestamp, reloaded_msg.timestamp)


class TestChatroomManager(unittest.TestCase):
    """Tests for the ChatroomManager class."""
    def setUp(self):
        """Sets up a ChatroomManager instance with a mock ApiKeyManager.
        
        Also ensures the test data directory for chatroom files is clean.
        The _load_chatrooms_from_disk method is patched during manager
        initialization for most tests to prevent actual file system access unless
        specifically testing that method.
        """
        self.mock_api_key_manager = MagicMock(spec=ApiKeyManager)
        # Prevent _load_chatrooms_from_disk from running in __init__ for most tests
        with patch.object(ChatroomManager, '_load_chatrooms_from_disk', lambda self: None):
            self.manager = ChatroomManager(api_key_manager=self.mock_api_key_manager)

        # Clean up test data directory before and after tests if it exists
        self.test_data_dir_path = DATA_DIR 
        if os.path.exists(self.test_data_dir_path):
            for f in os.listdir(self.test_data_dir_path):
                 if f.startswith("test_") and f.endswith(".json"): # Be specific
                    os.remove(os.path.join(self.test_data_dir_path, f))
    
    def tearDown(self):
        """Cleans up any test chatroom files created during tests."""
        if os.path.exists(self.test_data_dir_path):
            for f in os.listdir(self.test_data_dir_path):
                if f.startswith("test_") and f.endswith(".json"): # Be specific
                    os.remove(os.path.join(self.test_data_dir_path, f))

    @patch('src.main.chatroom.glob.glob')
    @patch('src.main.chatroom.open', new_callable=mock_open)
    @patch('src.main.chatroom.json.load')
    @patch('src.main.chatroom.Chatroom.from_dict') # Mock the class method
    def test_load_chatrooms_from_disk(self, mock_chatroom_from_dict, mock_json_load, mock_open_file, mock_glob_glob):
        """Tests the loading of chatrooms from disk (using mocks for file operations)."""
        # Setup mocks
        dummy_filepath1 = os.path.join(DATA_DIR, "test_room1.json")
        dummy_filepath2 = os.path.join(DATA_DIR, "test_room2.json")
        mock_glob_glob.return_value = [dummy_filepath1, dummy_filepath2]
        
        mock_room_data1 = {'name': 'test_room1', 'bots': [], 'messages': []}
        mock_room_data2 = {'name': 'test_room2', 'bots': [], 'messages': []}
        mock_json_load.side_effect = [mock_room_data1, mock_room_data2]

        mock_chatroom_instance1 = MagicMock(spec=Chatroom)
        mock_chatroom_instance1.name = "test_room1" # Set name property
        mock_chatroom_instance2 = MagicMock(spec=Chatroom)
        mock_chatroom_instance2.name = "test_room2" # Set name property
        mock_chatroom_from_dict.side_effect = [mock_chatroom_instance1, mock_chatroom_instance2]

        # Re-initialize manager to trigger actual _load_chatrooms_from_disk
        manager = ChatroomManager(api_key_manager=self.mock_api_key_manager)

        # Assertions
        self.assertEqual(len(manager.chatrooms), 2)
        self.assertIn("test_room1", manager.chatrooms)
        self.assertIn("test_room2", manager.chatrooms)
        mock_glob_glob.assert_called_once_with(os.path.join(DATA_DIR, "*.json"))
        self.assertEqual(mock_open_file.call_count, 2)
        self.assertEqual(mock_json_load.call_count, 2)
        mock_chatroom_from_dict.assert_any_call(mock_room_data1, manager, dummy_filepath1, self.mock_api_key_manager)
        mock_chatroom_from_dict.assert_any_call(mock_room_data2, manager, dummy_filepath2, self.mock_api_key_manager)


    @patch('src.main.chatroom.Chatroom._save')
    def test_create_chatroom_saves_and_notifies(self, mock_chatroom_save):
        """Tests that creating a chatroom correctly initializes it, saves it, and notifies."""
        room_name = "test_new_room_save"
        chatroom = self.manager.create_chatroom(room_name)
        
        self.assertIsNotNone(chatroom)
        self.assertEqual(chatroom.name, room_name)
        self.assertIn(room_name, self.manager.chatrooms)
        expected_filepath = os.path.join(DATA_DIR, _sanitize_filename(room_name))
        self.assertEqual(chatroom.filepath, expected_filepath)
        mock_chatroom_save.assert_called_once() # create_chatroom calls _save internally

    @patch('src.main.chatroom.os.remove')
    @patch('src.main.chatroom.os.path.exists', return_value=True) # Assume file exists
    def test_delete_chatroom_removes_file(self, mock_path_exists, mock_os_remove):
        """Tests that deleting a chatroom also removes its corresponding file."""
        room_name = "test_room_to_delete"
        # Create a dummy chatroom and add to manager for deletion
        dummy_chatroom = Chatroom(room_name)
        dummy_chatroom.filepath = os.path.join(DATA_DIR, _sanitize_filename(room_name))
        self.manager.chatrooms[room_name] = dummy_chatroom

        self.manager.delete_chatroom(room_name)
        
        self.assertNotIn(room_name, self.manager.chatrooms)
        mock_os_remove.assert_called_once_with(dummy_chatroom.filepath)

    @patch('src.main.chatroom.os.remove')
    @patch('src.main.chatroom.Chatroom._save')
    @patch('src.main.chatroom.os.path.exists', return_value=True) # Assume old file exists
    def test_rename_chatroom_moves_file_and_saves(self, mock_path_exists, mock_chatroom_save, mock_os_remove):
        """Tests that renaming a chatroom updates its name, filepath, saves the new file, and deletes the old file."""
        old_name = "test_old_room_name"
        new_name = "test_new_room_name"
        
        # Create and add original chatroom
        original_chatroom = Chatroom(old_name)
        original_chatroom.filepath = os.path.join(DATA_DIR, _sanitize_filename(old_name))
        original_chatroom.manager = self.manager
        self.manager.chatrooms[old_name] = original_chatroom
        
        self.assertTrue(self.manager.rename_chatroom(old_name, new_name))
        
        self.assertNotIn(old_name, self.manager.chatrooms)
        self.assertIn(new_name, self.manager.chatrooms)
        renamed_chatroom = self.manager.get_chatroom(new_name)
        self.assertEqual(renamed_chatroom.name, new_name)
        self.assertEqual(renamed_chatroom.filepath, os.path.join(DATA_DIR, _sanitize_filename(new_name)))
        
        # The rename_chatroom method stores the old filepath before changing it.
        # We need to assert that os.remove was called with that specific old path.
        # The 'original_chatroom.filepath' at this point in the test would be the *new* path
        # if we were inspecting the object after the rename.
        # However, the mock_os_remove should have been called with the path that
        # original_chatroom.filepath had *before* it was updated.
        # The implementation of rename_chatroom captures `old_filepath` correctly.
        # The key is that the `os.remove` call inside `rename_chatroom` used the `old_filepath` variable.
        # We need to ensure our mock captured that call correctly.
        # If `original_chatroom.filepath` was the argument to `os.remove` *after* it was updated, this test would be tricky.
        # But `ChatroomManager.rename_chatroom` saves `old_filepath = chatroom.filepath` first.
        
        # To be absolutely sure, let's get the expected old path string:
        expected_old_filepath_str = os.path.join(DATA_DIR, _sanitize_filename(old_name))
        mock_os_remove.assert_called_once_with(expected_old_filepath_str)
        mock_chatroom_save.assert_called_once() # Chatroom._save on the renamed chatroom object

    def test_clone_chatroom(self):
        """Tests cloning a chatroom, ensuring bots are copied but messages are not."""
        original_room_name = "test_original_clone"
        
        # Setup original chatroom
        # We need to patch ._save on the Chatroom instance returned by create_chatroom
        # or patch open/json.dump if testing the save mechanism itself.
        # For this test, focusing on clone logic, so patching _save is fine.
        with patch('src.main.chatroom.Chatroom._save') as mock_original_save:
            original_chatroom = self.manager.create_chatroom(original_room_name)
            self.assertIsNotNone(original_chatroom) # Ensure original_chatroom is created
            original_bot = Bot("OrigBot", "Prompt", GeminiEngine(api_key="key", model_name="gemini-orig"))
            original_chatroom.add_bot(original_bot) 
            original_chatroom.add_message("User", "Hello clone test") 

        # Mock load_key for ApiKeyManager
        self.mock_api_key_manager.load_key.return_value = "loaded_api_key"

        # Patch Chatroom._save for the cloned chatroom to avoid actual file operations
        with patch('src.main.chatroom.Chatroom._save') as mock_cloned_save:
            cloned_chatroom = self.manager.clone_chatroom(original_room_name)

        self.assertIsNotNone(cloned_chatroom)
        expected_clone_name = f"{original_room_name} (copy)"
        self.assertEqual(cloned_chatroom.name, expected_clone_name)
        self.assertIn(expected_clone_name, self.manager.chatrooms)
        
        # Assert bots are copied
        self.assertEqual(len(cloned_chatroom.list_bots()), 1)
        cloned_bot = cloned_chatroom.get_bot("OrigBot")
        self.assertIsNotNone(cloned_bot)
        self.assertEqual(cloned_bot.get_system_prompt(), "Prompt")
        self.assertIsInstance(cloned_bot.get_engine(), GeminiEngine)
        self.assertEqual(cloned_bot.get_engine().api_key, "loaded_api_key")
        self.assertEqual(cloned_bot.get_engine().model_name, "gemini-orig")

        # Assert message history is NOT copied
        self.assertEqual(len(cloned_chatroom.get_messages()), 0)
        
        # Check that ApiKeyManager.load_key was called for the bot's engine type
        self.mock_api_key_manager.load_key.assert_called_with("GeminiEngine")
        
        # Check that the cloned chatroom's _save was called (by create_chatroom and add_bot)
        # create_chatroom for clone + add_bot for the cloned bot
        self.assertGreaterEqual(mock_cloned_save.call_count, 1) 


    def test_list_chatrooms_returns_values(self):
        """Tests that list_chatrooms returns a list of Chatroom objects, not just names."""
        # This test is adjusted because the original test_list_chatrooms
        # was based on list_chatrooms returning names, now it returns Chatroom objects.
        self.assertEqual(len(self.manager.list_chatrooms()), 0) 
        
        room_names = ["Dev", "QA", "Support"]
        created_rooms = []
        for name in room_names:
            # Patch _save to avoid file ops during this setup
            with patch('src.main.chatroom.Chatroom._save'):
                room = self.manager.create_chatroom(name)
                created_rooms.append(room)
        
        listed_rooms_objects = self.manager.list_chatrooms()
        self.assertEqual(len(listed_rooms_objects), len(room_names))
        
        # Check if the returned list contains the Chatroom objects we created
        for room_obj in created_rooms:
            self.assertIn(room_obj, listed_rooms_objects)


if __name__ == '__main__':
    unittest.main()
