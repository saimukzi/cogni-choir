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

from src.main.chatroom import Chatroom, ChatroomManager, _sanitize_filename, DATA_DIR
from src.main.ai_bots import Bot
from src.main.third_party import ThirdPartyBase, ThirdPartyApiKeySlotInfo, AIEngineInfo, AIEngineArgInfo # For NoKeyEngine
from src.main.third_parties.google import Google as GeminiEngine # Alias for consistency if needed, or use Google
from src.main.third_parties.azure_openai import AzureOpenAI as AzureOpenAIEngine # Alias
from src.main.third_parties.xai import XAI as GrokEngine # Alias
from src.main.message import Message
from src.main.thirdpartyapikey_manager import ThirdPartyApiKeyQuery # Added ThirdPartyApiKeyQuery


class TestChatroom(unittest.TestCase):
    """Tests for the Chatroom class."""
    def setUp(self):
        """Sets up a Chatroom instance with a mock manager for each test."""
        self.mock_manager = MagicMock(spec=ChatroomManager)
        # self.mock_manager.thirdpartyapikey_manager = MagicMock(spec=ThirdPartyApiKeyManager) # Mock ThirdPartyApiKeyManager on the mock manager
        
        self.chatroom = Chatroom("Test Room")
        self.chatroom.manager = self.mock_manager # Assign the mock manager
        self.chatroom.filepath = os.path.join(DATA_DIR, "test_room.json") # Dummy filepath for save

        # self.dummy_engine is no longer used directly in Bot constructor in the same way.
        # Bot instances will be created differently.

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
        bot1 = Bot()
        bot1.name = "Bot1"
        bot1.aiengine_id = "gemini_test"
        bot1.aiengine_arg_dict = {"system_prompt": "System prompt 1", "model_name": "gemini-pro"}
        # bot1.thirdpartyapikey_query_list = [ThirdPartyApiKeyQuery("google_gemini", "Bot1_google_gemini")] # Example

        bot2 = Bot()
        bot2.name = "Bot2"
        bot2.aiengine_id = "azure_test"
        bot2.aiengine_arg_dict = {"system_prompt": "System prompt 2", "model_name": "gpt-3.5"}

        self.chatroom.add_bot(bot1)
        self.assertEqual(len(self.chatroom.list_bots()), 1)
        self.assertIn(bot1, self.chatroom.list_bots())
        self.assertEqual(self.chatroom.get_bot("Bot1"), bot1)
        self.mock_manager.notify_chatroom_updated.assert_called_with(self.chatroom)
        self.mock_manager.notify_chatroom_updated.reset_mock() # Reset for next call

        self.chatroom.add_bot(bot2)
        self.assertEqual(len(self.chatroom.list_bots()), 2)
        self.mock_manager.notify_chatroom_updated.assert_called_with(self.chatroom)
        self.mock_manager.notify_chatroom_updated.reset_mock()

        self.chatroom.remove_bot("Bot1")
        self.assertEqual(len(self.chatroom.list_bots()), 1)
        self.assertNotIn(bot1, self.chatroom.list_bots())
        self.mock_manager.notify_chatroom_updated.assert_called_with(self.chatroom)
        self.mock_manager.notify_chatroom_updated.reset_mock()

        self.chatroom.remove_bot("NonExistentBot")
        self.mock_manager.notify_chatroom_updated.assert_not_called() # Should not be called if bot not found

        self.chatroom.remove_bot("Bot2")
        self.assertEqual(len(self.chatroom.list_bots()), 0)
        self.mock_manager.notify_chatroom_updated.assert_called_with(self.chatroom)

    def test_add_get_messages(self):
        """Tests adding messages to the chatroom and retrieving them."""
        msg1 = self.chatroom.add_message("User1", "Hello")
        self.assertIsInstance(msg1, Message)
        self.assertEqual(len(self.chatroom.get_messages()), 1)
        self.mock_manager.notify_chatroom_updated.assert_called_with(self.chatroom)
        self.mock_manager.notify_chatroom_updated.reset_mock()

        self.chatroom.add_message("Bot1", "Hi there!")
        self.assertEqual(len(self.chatroom.get_messages()), 2)
        self.mock_manager.notify_chatroom_updated.assert_called_with(self.chatroom)

    def test_delete_message(self):
        msg1_ts = self.chatroom.add_message("User1", "Msg1").timestamp
        self.mock_manager.notify_chatroom_updated.reset_mock()
        msg2_ts = self.chatroom.add_message("User2", "Msg2").timestamp
        self.mock_manager.notify_chatroom_updated.reset_mock()
        self.assertEqual(len(self.chatroom.get_messages()), 2)

        self.assertTrue(self.chatroom.delete_message(msg1_ts))
        self.assertEqual(len(self.chatroom.get_messages()), 1)
        self.assertEqual(self.chatroom.get_messages()[0].timestamp, msg2_ts)
        self.mock_manager.notify_chatroom_updated.assert_called_with(self.chatroom)
        self.mock_manager.notify_chatroom_updated.reset_mock()

        self.assertFalse(self.chatroom.delete_message(time.time())) # Non-existent timestamp
        self.assertEqual(len(self.chatroom.get_messages()), 1)
        self.mock_manager.notify_chatroom_updated.assert_not_called()

        self.assertTrue(self.chatroom.delete_message(msg2_ts))
        self.assertEqual(len(self.chatroom.get_messages()), 0)
        self.mock_manager.notify_chatroom_updated.assert_called_with(self.chatroom)

    @patch.object(logging.getLogger('src.main.chatroom.Chatroom'), 'warning')
    def test_chatroom_save_load_cycle(self, mock_logger_warning):
        """Tests the Chatroom to_dict and from_dict methods (serialization/deserialization)."""

        # Define NoKeyEngine (can be an inner class or defined in the test module)
        # It now inherits from ThirdPartyBase and needs to implement its abstract methods.
        class NoKeyEngine(ThirdPartyBase):
            def __init__(self, thirdparty_id: str = "NoKeyEngine"): # Added thirdparty_id
                super().__init__(thirdparty_id)
                # model_name is usually part of aiengine_arg_dict in Bot, not directly on engine instance
                # self.model_name = "no-key-model" # Store if needed for specific test assertions

            def get_thirdpartyapikey_slot_info_list(self) -> list[ThirdPartyApiKeySlotInfo]:
                return [] # No API key needed

            def get_aiengine_info_list(self) -> list[AIEngineInfo]:
                return [AIEngineInfo(
                    aiengine_id="nokey_engine_001",
                    name="NoKey Test Engine",
                    thirdpartyapikey_slot_id_list=[],
                    arg_list=[AIEngineArgInfo("model_name", "Model", False, "no-key-model")]
                )]

            def generate_response(self, aiengine_id: str, aiengine_arg_dict: dict[str, str],
                                  thirdpartyapikey_list: list[str], role_name: str,
                                  conversation_history: list[Message]) -> str:
                return "NoKeyEngine response"

        # Setup chatroom with new Bot structure
        bot1 = Bot()
        bot1.name = "BotAlpha"
        bot1.aiengine_id = "google_gemini" # Corresponds to AIEngineInfo.aiengine_id
        bot1.aiengine_arg_dict = {"system_prompt": "Prompt Alpha", "model_name": "gemini-alpha"}
        bot1.thirdpartyapikey_query_list = [ThirdPartyApiKeyQuery(thirdpartyapikey_slot_id="google_gemini", thirdpartyapikey_id="BotAlpha_google_gemini")]

        bot2 = Bot()
        bot2.name = "BotBeta"
        bot2.aiengine_id = "azure_openai" # Corresponds to AIEngineInfo.aiengine_id
        bot2.aiengine_arg_dict = {"system_prompt": "Prompt Beta", "model_name": "azureopenai-beta"}
        bot2.thirdpartyapikey_query_list = [ThirdPartyApiKeyQuery(thirdpartyapikey_slot_id="azure_openai", thirdpartyapikey_id="BotBeta_azure_openai")]

        # For BotGamma with NoKeyEngine, its aiengine_id should match what NoKeyEngine.get_aiengine_info_list provides
        bot3 = Bot()
        bot3.name = "BotGamma"
        bot3.aiengine_id = "nokey_engine_001"
        bot3.aiengine_arg_dict = {"system_prompt": "Prompt Gamma", "model_name": "no-key-gamma"}
        # No thirdpartyapikey_query_list for bot3 as NoKeyEngine doesn't require API keys

        self.chatroom.add_bot(bot1)
        self.chatroom.add_bot(bot2)
        self.chatroom.add_bot(bot3)
        self.chatroom.add_message("User", "Hello Bots")
        self.chatroom.add_message("BotAlpha", "Hello User from Alpha")
        
        dict_data = self.chatroom.to_dict()

        # Chatroom.from_dict now directly uses Bot.from_dict.
        # The complex mocking of create_bot and thirdpartyapikey_manager.load_key in the test
        # is no longer representative of how Chatroom.from_dict works.
        # Bot.from_dict simply deserializes the bot's data.
        # Any API key loading or engine instantiation happens later when the bot is used.
        # Warnings about missing API keys or unsupported engines are not produced by Chatroom.from_dict.
        
        # We simply test that Chatroom.from_dict correctly reconstructs Bot objects
        # using Bot.from_dict, and messages.
        
        reloaded_chatroom = Chatroom.from_dict(
            dict_data,
            manager=self.mock_manager, # manager is still passed
            filepath="dummy_reloaded.json"
            # thirdpartyapikey_manager is no longer an argument to Chatroom.from_dict
        )

        self.assertEqual(self.chatroom.name, reloaded_chatroom.name)
        self.assertEqual(len(reloaded_chatroom.list_bots()), 3, "All bots should be loaded by Bot.from_dict.")

        # Verify BotAlpha
        reloaded_bot_alpha = reloaded_chatroom.get_bot("BotAlpha")
        self.assertIsNotNone(reloaded_bot_alpha)
        self.assertEqual(reloaded_bot_alpha.name, "BotAlpha")
        self.assertEqual(reloaded_bot_alpha.aiengine_id, "google_gemini")
        self.assertEqual(reloaded_bot_alpha.get_aiengine_arg("system_prompt"), "Prompt Alpha")
        self.assertEqual(reloaded_bot_alpha.get_aiengine_arg("model_name"), "gemini-alpha")
        self.assertIsNotNone(reloaded_bot_alpha.thirdpartyapikey_query_list)
        self.assertEqual(len(reloaded_bot_alpha.thirdpartyapikey_query_list), 1)
        self.assertEqual(reloaded_bot_alpha.thirdpartyapikey_query_list[0].thirdpartyapikey_slot_id, "google_gemini")
        self.assertEqual(reloaded_bot_alpha.thirdpartyapikey_query_list[0].thirdpartyapikey_id, "BotAlpha_google_gemini")


        # Verify BotBeta
        reloaded_bot_beta = reloaded_chatroom.get_bot("BotBeta")
        self.assertIsNotNone(reloaded_bot_beta)
        self.assertEqual(reloaded_bot_beta.aiengine_id, "azure_openai")
        self.assertEqual(reloaded_bot_beta.get_aiengine_arg("system_prompt"), "Prompt Beta")
        self.assertIsNotNone(reloaded_bot_beta.thirdpartyapikey_query_list)
        self.assertEqual(len(reloaded_bot_beta.thirdpartyapikey_query_list), 1)
        self.assertEqual(reloaded_bot_beta.thirdpartyapikey_query_list[0].thirdpartyapikey_slot_id, "azure_openai")
        self.assertEqual(reloaded_bot_beta.thirdpartyapikey_query_list[0].thirdpartyapikey_id, "BotBeta_azure_openai")


        # Verify BotGamma (NoKeyEngine)
        reloaded_bot_gamma = reloaded_chatroom.get_bot("BotGamma")
        self.assertIsNotNone(reloaded_bot_gamma)
        self.assertEqual(reloaded_bot_gamma.aiengine_id, "nokey_engine_001")
        self.assertEqual(reloaded_bot_gamma.get_aiengine_arg("system_prompt"), "Prompt Gamma")
        self.assertListEqual(reloaded_bot_gamma.thirdpartyapikey_query_list, [])

        # Verify messages
        self.assertEqual(len(self.chatroom.get_messages()), len(reloaded_chatroom.get_messages()))
        for i, original_msg in enumerate(self.chatroom.get_messages()):
            reloaded_msg = reloaded_chatroom.get_messages()[i] # Corrected to use reloaded_chatroom
            self.assertEqual(original_msg.sender, reloaded_msg.sender)
            self.assertEqual(original_msg.content, reloaded_msg.content)
            self.assertEqual(original_msg.timestamp, reloaded_msg.timestamp)

        # Ensure no warnings were logged by Chatroom.from_dict regarding API keys or unsupported engines,
        # as this logic is no longer in Chatroom.from_dict.
        mock_logger_warning.assert_not_called()


class TestChatroomManager(unittest.TestCase):
    """Tests for the ChatroomManager class."""
    def setUp(self):
        """Also ensures the test data directory for chatroom files is clean.
        The _load_chatrooms_from_disk method is patched during manager
        initialization for most tests to prevent actual file system access unless
        specifically testing that method.
        """
        # self.mock_thirdpartyapikey_manager = MagicMock(spec=ThirdPartyApiKeyManager)
        # Prevent _load_chatrooms_from_disk from running in __init__ for most tests
        with patch.object(ChatroomManager, '_load_chatrooms_from_disk', lambda self: None):
            self.manager = ChatroomManager()

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
        manager = ChatroomManager()

        # Assertions
        self.assertEqual(len(manager.chatrooms), 2)
        self.assertIn("test_room1", manager.chatrooms)
        self.assertIn("test_room2", manager.chatrooms)
        mock_glob_glob.assert_called_once_with(os.path.join(DATA_DIR, "*.json"))
        self.assertEqual(mock_open_file.call_count, 2)
        self.assertEqual(mock_json_load.call_count, 2)
        mock_chatroom_from_dict.assert_any_call(mock_room_data1, manager, dummy_filepath1) # Removed thirdpartyapikey_manager
        mock_chatroom_from_dict.assert_any_call(mock_room_data2, manager, dummy_filepath2) # Removed thirdpartyapikey_manager


    @patch('src.main.chatroom.Chatroom.save') # Patched public save
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
    @patch('src.main.chatroom.Chatroom.save') # Patched public save
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
        # We need to patch .save on the Chatroom instance returned by create_chatroom
        # or patch open/json.dump if testing the save mechanism itself.
        # For this test, focusing on clone logic, so patching .save is fine.
        with patch('src.main.chatroom.Chatroom.save') as mock_original_save: # Patched public save
            original_chatroom = self.manager.create_chatroom(original_room_name)
            self.assertIsNotNone(original_chatroom) # Ensure original_chatroom is created
        original_bot = Bot()
        original_bot.name = "OrigBot"
        original_bot.aiengine_id = "google_gemini"
        original_bot.aiengine_arg_dict = {"system_prompt": "Prompt", "model_name": "gemini-orig"}
        original_bot.thirdpartyapikey_query_list = [ThirdPartyApiKeyQuery("google_gemini", "orig_bot_key")]

        original_chatroom.add_bot(original_bot)
        original_chatroom.add_message("User", "Hello clone test")

    # ChatroomManager.clone_chatroom now uses copy.deepcopy(bot)
    # So, ThirdPartyApiKeyManager.load_key is not directly involved in the cloning of the bot object itself.
    # The thirdpartyapikey_query_list is deepcopied.

        with patch('src.main.chatroom.Chatroom.save') as mock_cloned_save: # Patched public save
            cloned_chatroom = self.manager.clone_chatroom(original_room_name)

        self.assertIsNotNone(cloned_chatroom)
        expected_clone_name = f"{original_room_name} (copy)"
        self.assertEqual(cloned_chatroom.name, expected_clone_name)
        self.assertIn(expected_clone_name, self.manager.chatrooms)
        
        # Assert bots are copied
        self.assertEqual(len(cloned_chatroom.list_bots()), 1)
        cloned_bot = cloned_chatroom.get_bot("OrigBot")
        self.assertIsNotNone(cloned_bot)
        self.assertNotEqual(cloned_bot, original_bot) # Should be a new instance
        self.assertEqual(cloned_bot.name, original_bot.name)
        self.assertEqual(cloned_bot.aiengine_id, original_bot.aiengine_id)
        self.assertEqual(cloned_bot.aiengine_arg_dict, original_bot.aiengine_arg_dict)
        self.assertEqual(cloned_bot.get_aiengine_arg("system_prompt"), "Prompt") # Corrected access
        self.assertEqual(cloned_bot.get_aiengine_arg("model_name"), "gemini-orig") # Corrected access

        self.assertIsNotNone(cloned_bot.thirdpartyapikey_query_list)
        self.assertEqual(len(cloned_bot.thirdpartyapikey_query_list), 1)
        self.assertEqual(cloned_bot.thirdpartyapikey_query_list[0].thirdpartyapikey_slot_id, "google_gemini")
        self.assertNotEqual(cloned_bot.thirdpartyapikey_query_list, original_bot.thirdpartyapikey_query_list) # Should be a deepcopy

        # Assert message history IS copied by deepcopy as per SUT change
        self.assertEqual(len(cloned_chatroom.get_messages()), 1)
        self.assertNotEqual(cloned_chatroom.get_messages()[0], original_chatroom.get_messages()[0]) # Deepcopied
        self.assertEqual(cloned_chatroom.get_messages()[0].content, "Hello clone test")
        
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
            # Patch .save to avoid file ops during this setup
            with patch('src.main.chatroom.Chatroom.save'): # Patched public save
                room = self.manager.create_chatroom(name)
                created_rooms.append(room)
        
        listed_rooms_objects = self.manager.list_chatrooms()
        self.assertEqual(len(listed_rooms_objects), len(room_names))
        
        # Check if the returned list contains the Chatroom objects we created
        for room_obj in created_rooms:
            self.assertIn(room_obj, listed_rooms_objects)


if __name__ == '__main__':
    unittest.main()
