import unittest
from unittest.mock import patch, mock_open, MagicMock
import sys
import os
import json
import time # For message timestamp tests

# Adjusting sys.path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.main.chatroom import Chatroom, ChatroomManager, _sanitize_filename, DATA_DIR
from src.main.ai_bots import Bot # Bot is still in ai_bots
from src.main.ai_engines import GeminiEngine, OpenAIEngine # Engines from new package
from src.main.message import Message
from src.main.api_key_manager import ApiKeyManager


class TestChatroom(unittest.TestCase):
    def setUp(self):
        self.mock_manager = MagicMock(spec=ChatroomManager)
        self.mock_manager.api_key_manager = MagicMock(spec=ApiKeyManager) # Mock ApiKeyManager on the mock manager
        
        self.chatroom = Chatroom("Test Room")
        self.chatroom.manager = self.mock_manager # Assign the mock manager
        self.chatroom.filepath = os.path.join(DATA_DIR, "test_room.json") # Dummy filepath for save

        self.dummy_engine = GeminiEngine(api_key="test_key") 

    def test_initialization(self):
        self.assertEqual(self.chatroom.name, "Test Room") # Use property
        self.assertEqual(len(self.chatroom.list_bots()), 0)
        self.assertEqual(len(self.chatroom.get_messages()), 0)

    # Direct set_name is removed, renaming is handled by ChatroomManager
    # def test_set_get_name(self): 
    #     pass 

    def test_add_get_list_remove_bot(self):
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

    def test_chatroom_save_load_cycle(self):
        # Setup chatroom
        bot1 = Bot("BotAlpha", "Prompt Alpha", GeminiEngine(api_key="gemini_test_key", model_name="gemini-alpha"))
        bot2 = Bot("BotBeta", "Prompt Beta", OpenAIEngine(api_key="openai_test_key", model_name="openai-beta"))
        self.chatroom.add_bot(bot1)
        self.chatroom.add_bot(bot2)
        self.chatroom.add_message("User", "Hello Bots")
        self.chatroom.add_message("BotAlpha", "Hello User from Alpha")

        dict_data = self.chatroom.to_dict()

        # Mock ApiKeyManager for from_dict
        mock_api_key_manager_for_load = MagicMock(spec=ApiKeyManager)
        mock_api_key_manager_for_load.load_key.side_effect = lambda service_name: {
            "Gemini": "gemini_test_key", "OpenAI": "openai_test_key"
        }.get(service_name)

        reloaded_chatroom = Chatroom.from_dict(dict_data, 
                                               manager=self.mock_manager, 
                                               filepath="dummy.json", 
                                               api_key_manager=mock_api_key_manager_for_load)

        self.assertEqual(self.chatroom.name, reloaded_chatroom.name)
        self.assertEqual(len(self.chatroom.list_bots()), len(reloaded_chatroom.list_bots()))
        self.assertEqual(len(self.chatroom.get_messages()), len(reloaded_chatroom.get_messages()))

        # Compare bots
        for original_bot in self.chatroom.list_bots():
            reloaded_bot = reloaded_chatroom.get_bot(original_bot.get_name())
            self.assertIsNotNone(reloaded_bot)
            self.assertEqual(original_bot.get_system_prompt(), reloaded_bot.get_system_prompt())
            self.assertEqual(type(original_bot.get_engine()), type(reloaded_bot.get_engine()))
            self.assertEqual(original_bot.get_engine().model_name, reloaded_bot.get_engine().model_name)
            # API key itself is not stored in bot, but engine instance should have it if loaded
            self.assertEqual(original_bot.get_engine().api_key, reloaded_bot.get_engine().api_key)


        # Compare messages
        for i, original_msg in enumerate(self.chatroom.get_messages()):
            reloaded_msg = reloaded_chatroom.get_messages()[i]
            self.assertEqual(original_msg.sender, reloaded_msg.sender)
            self.assertEqual(original_msg.content, reloaded_msg.content)
            self.assertEqual(original_msg.timestamp, reloaded_msg.timestamp)


class TestChatroomManager(unittest.TestCase):
    def setUp(self):
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
        if os.path.exists(self.test_data_dir_path):
            for f in os.listdir(self.test_data_dir_path):
                if f.startswith("test_") and f.endswith(".json"): # Be specific
                    os.remove(os.path.join(self.test_data_dir_path, f))

    @patch('src.main.chatroom.glob.glob')
    @patch('src.main.chatroom.open', new_callable=mock_open)
    @patch('src.main.chatroom.json.load')
    @patch('src.main.chatroom.Chatroom.from_dict') # Mock the class method
    def test_load_chatrooms_from_disk(self, mock_chatroom_from_dict, mock_json_load, mock_open_file, mock_glob_glob):
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
        self.mock_api_key_manager.load_key.assert_called_with("Gemini")
        
        # Check that the cloned chatroom's _save was called (by create_chatroom and add_bot)
        # create_chatroom for clone + add_bot for the cloned bot
        self.assertGreaterEqual(mock_cloned_save.call_count, 1) 


    def test_list_chatrooms_returns_values(self):
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
