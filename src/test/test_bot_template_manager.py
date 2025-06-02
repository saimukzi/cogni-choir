import unittest
import os
import json
import shutil
from unittest.mock import patch, MagicMock

# Adjust import path based on your project structure
# This assumes your tests are run from the project root or that src is in PYTHONPATH
from src.main.bot_template_manager import BotTemplateManager, BOT_TEMPLATES_FILE
from src.main.ai_bots import Bot
from src.main.apikey_manager import ApiKeyQuery


# Helper to create a dummy Bot instance for testing
def create_dummy_bot(name="TestBot", aiengine_id="test_engine", model="gpt-test", prompt="Be a test bot.") -> Bot:
    bot = Bot()
    bot.name = name
    bot.aiengine_id = aiengine_id
    bot.aiengine_arg_dict = {"model_name": model, "system_prompt": prompt}
    # Example ApiKeyQuery, adjust if your structure is different
    # Assuming ApiKeyQuery can be instantiated like this and has a to_dict method
    bot.apikey_query_list = [ApiKeyQuery(apikey_slot_id="test_api_key_slot", apikey_id="Test API Key")]
    return bot

class TestBotTemplateManager(unittest.TestCase):

    def setUp(self):
        # Create a temporary test data directory
        self.test_data_dir = os.path.join(os.path.dirname(__file__), "test_data_temp")
        os.makedirs(self.test_data_dir, exist_ok=True)

        # Mock Commons.get_data_dir() to return our temporary directory
        # self.get_data_dir_patch = patch('src.main.commons.Commons.get_data_dir', return_value=self.test_data_dir)
        # self.mock_get_data_dir = self.get_data_dir_patch.start()

        self.manager = BotTemplateManager(data_dir=self.test_data_dir)
        self.templates_file = os.path.join(self.test_data_dir, BOT_TEMPLATES_FILE)

    def tearDown(self):
        # Stop the patcher
        # self.get_data_dir_patch.stop()
        # Clean up the temporary directory and its contents
        if os.path.exists(self.test_data_dir):
            shutil.rmtree(self.test_data_dir)

    def test_01_initialization_no_file(self):
        """Test initialization when the templates file does not exist."""
        if os.path.exists(self.templates_file):
            os.remove(self.templates_file)
        # Re-initialize manager after ensuring file is gone
        # The manager's __init__ calls _load_templates, which might create an empty file if _save_templates is called.
        # For this test, we want to ensure it *starts* empty and doesn't auto-create on init *if* no save happens.
        # The current BotTemplateManager._load_templates does not create the file, only logs.
        # _save_templates *does* create it.
        manager = BotTemplateManager(data_dir=self.test_data_dir)
        self.assertEqual(len(manager.list_templates()), 0)
        # The file might be created by _save_templates if it's called indirectly or if structure changes.
        # For now, if it's empty, it's fine. If it's created empty by _save_templates, that's also acceptable.
        # Let's check if it exists. If it does, it should be empty.
        if os.path.exists(self.templates_file):
            with open(self.templates_file, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertEqual(content.strip(), "{}", "If file is created by init (e.g. via _save_templates), it should represent an empty dict.")
        else:
            # This is also acceptable if _save_templates is not called on init
            self.assertFalse(os.path.exists(self.templates_file), "Templates file should ideally not be created on init if no templates and no save action.")


    def test_02_create_template(self):
        """Test creating a new bot template."""
        bot_config = create_dummy_bot(name="Template1")
        template_id = self.manager.create_template(bot_config)

        self.assertIsNotNone(template_id)
        self.assertEqual(len(self.manager.list_templates()), 1)
        retrieved_template = self.manager.get_template(template_id)
        self.assertIsNotNone(retrieved_template)
        self.assertEqual(retrieved_template.name, "Template1")
        self.assertTrue(os.path.exists(self.templates_file))

        with open(self.templates_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertIn(template_id, data)
        self.assertEqual(data[template_id]['name'], "Template1")

    def test_03_create_multiple_templates(self):
        """Test creating multiple templates."""
        bot1_config = create_dummy_bot(name="AlphaBot")
        bot2_config = create_dummy_bot(name="BetaBot", aiengine_id="another_engine")

        id1 = self.manager.create_template(bot1_config)
        id2 = self.manager.create_template(bot2_config)

        self.assertIsNotNone(id1)
        self.assertIsNotNone(id2)
        self.assertNotEqual(id1, id2)
        self.assertEqual(len(self.manager.list_templates()), 2)

    def test_04_get_template(self):
        """Test retrieving a template by ID."""
        bot_config = create_dummy_bot(name="GammaBot")
        template_id = self.manager.create_template(bot_config)

        retrieved = self.manager.get_template(template_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "GammaBot")

        non_existent = self.manager.get_template("non_existent_id")
        self.assertIsNone(non_existent)

    def test_05_list_templates(self):
        """Test listing all templates."""
        # Manager is reset for each test if setUp creates a new one.
        # self.assertEqual(len(self.manager.list_templates()), 0)

        bot_config1 = create_dummy_bot(name="Delta")
        bot_config2 = create_dummy_bot(name="Epsilon")
        self.manager.create_template(bot_config1)
        self.manager.create_template(bot_config2)

        templates = self.manager.list_templates()
        self.assertEqual(len(templates), 2)
        template_names = [t.name for t in templates]
        self.assertIn("Delta", template_names)
        self.assertIn("Epsilon", template_names)

    def test_06_list_templates_with_ids(self):
        """Test listing all templates with their IDs."""
        # self.assertEqual(len(self.manager.list_templates_with_ids()), 0)

        bot_config = create_dummy_bot(name="Zeta")
        template_id = self.manager.create_template(bot_config)

        templates_with_ids = self.manager.list_templates_with_ids()
        self.assertEqual(len(templates_with_ids), 1)
        self.assertEqual(templates_with_ids[0][0], template_id)
        self.assertEqual(templates_with_ids[0][1].name, "Zeta")


    def test_07_update_template(self):
        """Test updating an existing template."""
        bot_config_orig = create_dummy_bot(name="OriginalName")
        template_id = self.manager.create_template(bot_config_orig)

        bot_config_updated = create_dummy_bot(name="UpdatedName", model="gpt-4-updated")
        bot_config_updated.apikey_query_list = [ApiKeyQuery(apikey_slot_id="updated_slot", apikey_id="Updated Key")]


        update_success = self.manager.update_template(template_id, bot_config_updated)
        self.assertTrue(update_success)

        retrieved_template = self.manager.get_template(template_id)
        self.assertIsNotNone(retrieved_template)
        self.assertEqual(retrieved_template.name, "UpdatedName")
        self.assertEqual(retrieved_template.aiengine_arg_dict.get("model_name"), "gpt-4-updated")

        self.assertEqual(len(retrieved_template.apikey_query_list), 1)
        if retrieved_template.apikey_query_list:
            # Ensure ApiKeyQuery objects are being compared meaningfully or check attributes
            # This assumes ApiKeyQuery has .apikey_slot_id and .apikey_id attributes
            self.assertEqual(retrieved_template.apikey_query_list[0].apikey_slot_id, "updated_slot")
            self.assertEqual(retrieved_template.apikey_query_list[0].apikey_id, "Updated Key")


        update_fail = self.manager.update_template("non_id", bot_config_updated)
        self.assertFalse(update_fail)

    def test_08_delete_template(self):
        """Test deleting a template."""
        bot_config = create_dummy_bot(name="ToDelete")
        template_id = self.manager.create_template(bot_config)
        self.assertEqual(len(self.manager.list_templates()), 1)

        delete_success = self.manager.delete_template(template_id)
        self.assertTrue(delete_success)
        self.assertEqual(len(self.manager.list_templates()), 0)
        self.assertIsNone(self.manager.get_template(template_id))

        delete_fail = self.manager.delete_template("non_id")
        self.assertFalse(delete_fail)

        # After deletion, the file should contain an empty JSON object
        if os.path.exists(self.templates_file):
            with open(self.templates_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.assertEqual(len(data), 0, "File should be an empty JSON object after deleting all templates.")
        else:
            self.fail("Templates file should exist even if empty.")


    def test_09_load_templates_from_file(self):
        """Test loading templates from an existing file."""
        bot1 = create_dummy_bot(name="FileBot1", model="model1", prompt="prompt1")
        bot1.apikey_query_list = [ApiKeyQuery(apikey_slot_id="slot1", apikey_id="key_id1")]
        bot2 = create_dummy_bot(name="FileBot2", model="model2", prompt="prompt2")
        bot2.apikey_query_list = [ApiKeyQuery(apikey_slot_id="slot2", apikey_id="key_id2")]

        # Helper for consistent serialization, matching Bot.to_dict and ApiKeyQuery.to_dict
        def bot_to_savable_dict(bot_instance: Bot) -> dict:
            return bot_instance.to_dict()

        initial_data = {
            "id123": bot_to_savable_dict(bot1),
            "id456": bot_to_savable_dict(bot2)
        }
        with open(self.templates_file, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, indent=4)

        # Create new manager instance to trigger _load_templates
        new_manager = BotTemplateManager(data_dir=self.test_data_dir)
        templates_with_ids = new_manager.list_templates_with_ids()

        self.assertEqual(len(templates_with_ids), 2)
        loaded_names = sorted([t[1].name for t in templates_with_ids]) # Sort for consistent order
        self.assertListEqual(loaded_names, ["FileBot1", "FileBot2"])

        # Check one bot in detail
        bot1_loaded = new_manager.get_template("id123")
        self.assertIsNotNone(bot1_loaded)
        self.assertEqual(bot1_loaded.name, "FileBot1")
        self.assertEqual(bot1_loaded.aiengine_arg_dict.get("model_name"), "model1")
        self.assertEqual(len(bot1_loaded.apikey_query_list), 1)
        if bot1_loaded.apikey_query_list:
            query = bot1_loaded.apikey_query_list[0]
            self.assertTrue(isinstance(query, ApiKeyQuery))
            self.assertEqual(query.apikey_slot_id, "slot1")
            self.assertEqual(query.apikey_id, "key_id1")


    def test_10_load_malformed_json_file(self):
        """Test loading from a malformed JSON file."""
        with open(self.templates_file, 'w', encoding='utf-8') as f:
            f.write("this is not json { malformed") # Malformed JSON

        # Use a new manager instance to trigger _load_templates
        # Patch logger for this specific manager instance if it's already created in setUp,
        # or create a new one and patch its logger.
        # For simplicity, creating a new manager and patching its logger directly.
        manager_for_malformed_test = BotTemplateManager(data_dir=self.test_data_dir) # This will attempt to load
        with patch.object(manager_for_malformed_test.logger, 'error') as mock_log_error:
            # _load_templates is called in __init__. To re-trigger or test it isolated:
            manager_for_malformed_test._load_templates() # Call again to check logging with patched logger
            self.assertEqual(len(manager_for_malformed_test.list_templates()), 0)
            mock_log_error.assert_called()


    def test_11_load_file_with_invalid_template_data(self):
        """Test loading a file where some template data is invalid/incomplete."""
        valid_bot = create_dummy_bot(name="GoodBot")

        def bot_to_savable_dict(bot_instance: Bot) -> dict:
            return bot_instance.to_dict()

        data_with_issues = {
            "good1": bot_to_savable_dict(valid_bot),
            "bad1": {"name": "BadBotMissingEngine"}, # Missing aiengine_id
            "bad2": {"aiengine_id": "some_engine"}  # Missing name
        }
        with open(self.templates_file, 'w', encoding='utf-8') as f:
            json.dump(data_with_issues, f, indent=4)

        # Create new manager to trigger load
        manager_for_invalid_test = BotTemplateManager(data_dir=self.test_data_dir)
        with patch.object(manager_for_invalid_test.logger, 'warning') as mock_log_warning:
            manager_for_invalid_test._load_templates() # Re-call load to ensure warning is logged by patched logger
            templates = manager_for_invalid_test.list_templates()
            self.assertEqual(len(templates), 1)
            if templates:
                self.assertEqual(templates[0].name, "GoodBot")
            # Each invalid entry should log a warning or error
            self.assertGreaterEqual(mock_log_warning.call_count + manager_for_invalid_test.logger.error.call_count, 2)


    def test_12_clear_all_templates(self):
        """Test clearing all templates."""
        self.manager.create_template(create_dummy_bot(name="BotA"))
        self.manager.create_template(create_dummy_bot(name="BotB"))
        self.assertEqual(len(self.manager.list_templates()), 2)
        self.assertTrue(os.path.exists(self.templates_file))

        with open(self.templates_file, 'r', encoding='utf-8') as f:
            data_before_clear = json.load(f)
        self.assertGreater(len(data_before_clear), 0, "File should have content before clear.")

        self.manager.clear_all_templates()
        self.assertEqual(len(self.manager.list_templates()), 0)
        self.assertTrue(os.path.exists(self.templates_file), "File should still exist after clear.")

        with open(self.templates_file, 'r', encoding='utf-8') as f:
            data_after_clear = json.load(f)
        self.assertEqual(len(data_after_clear), 0, "File should be an empty JSON object after clear.")

        # Test clearing when already empty
        self.manager.clear_all_templates()
        self.assertEqual(len(self.manager.list_templates()), 0)
        with open(self.templates_file, 'r', encoding='utf-8') as f:
            data_still_empty = json.load(f)
        self.assertEqual(len(data_still_empty), 0)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
