"""
bot_template_manager.py
========================
This module manages bot templates, including loading, saving, and CRUD operations.
"""

import time
import json
import logging
import os
from typing import List, Dict, Optional
import uuid
from .ai_bots import BotData # Assuming Bot class is in ai_bots.py
# from .commons import Commons # For file paths or other common utilities

BOT_TEMPLATES_FILE = "bot_templates.json"

class BotTemplateManager:
    """Manages bot templates, including loading, saving, and CRUD operations."""

    def __init__(self, data_dir: str):
        """
        Initializes the BotTemplateManager.

        Args:
            data_dir (str): The directory where bot templates data is stored.
        """
        self.logger = logging.getLogger(__name__)

        if not data_dir:
            raise ValueError("data_dir must be provided and cannot be empty.")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        if not os.path.isdir(data_dir):
            raise ValueError(f"The provided data_dir '{data_dir}' is not a directory.")

        self.templates_file_path = os.path.join(data_dir, BOT_TEMPLATES_FILE)
        self.templates: Dict[str, BotData] = {} # Store templates by ID
        self._load_templates()

    def _load_templates(self):
        """Loads bot templates from the JSON file."""
        if not os.path.exists(self.templates_file_path):
            self.logger.info(f"Bot templates file not found at {self.templates_file_path}. Starting with an empty list.")
            self.templates = {}
            return

        try:
            with open(self.templates_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.templates = {}
                for template_id, template_data in data.items():
                    # Assuming Bot class has a from_dict method or similar
                    try:
                        # Use Bot.from_dict for deserialization
                        bot = BotData.model_validate(template_data)
                        # Basic validation after deserialization
                        if bot.name and bot.aiengine_id:
                            self.templates[template_id] = bot
                        else:
                            self.logger.warning(f"Skipping invalid template data for ID {template_id}: Missing name or aiengine_id after deserialization.")
                    except Exception as e:
                        self.logger.error(f"Error loading bot from template data for ID {template_id}: {e}", exc_info=True)
            self.logger.info(f"Successfully loaded {len(self.templates)} bot templates from {self.templates_file_path}.")
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON from {self.templates_file_path}. Starting with an empty list of templates.", exc_info=True)
            self.templates = {}
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while loading bot templates: {e}", exc_info=True)
            self.templates = {}

    def _save_templates(self):
        """Saves the current bot templates to the JSON file."""
        try:
            data_to_save = {}
            for template_id, bot_instance in self.templates.items():
                data_to_save[template_id] = bot_instance.model_dump(mode='json')

            os.makedirs(os.path.dirname(self.templates_file_path), exist_ok=True)
            with open(self.templates_file_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            self.logger.info(f"Successfully saved {len(self.templates)} bot templates to {self.templates_file_path}.")
        except Exception as e:
            self.logger.error(f"Error saving bot templates to {self.templates_file_path}: {e}", exc_info=True)

    def _generate_id(self) -> str:
        """Generates a unique ID for a new template."""
        # Simple approach: use timestamp. More robust: UUID.
        # return str(int(time.time() * 1000))
        return str(uuid.uuid4())

    def create_template(self, bot_config: BotData) -> Optional[str]:
        """
        Creates a new bot template.

        Args:
            bot_config (Bot): The Bot object containing the configuration for the template.

        Returns:
            Optional[str]: The ID of the newly created template, or None if creation failed.
        """
        if not isinstance(bot_config, BotData):
            self.logger.error("Invalid bot_config provided for template creation.")
            return None

        template_id = self._generate_id()
        self.templates[template_id] = bot_config
        self._save_templates()
        self.logger.info(f"Bot template '{bot_config.name}' created with ID {template_id}.")
        return template_id

    def get_template(self, template_id: str) -> Optional[BotData]:
        """
        Retrieves a bot template by its ID.

        Args:
            template_id (str): The ID of the template to retrieve.

        Returns:
            Optional[Bot]: The Bot object for the template, or None if not found.
        """
        return self.templates.get(template_id)

    def list_templates(self) -> List[BotData]:
        """
        Lists all bot templates.

        Returns:
            List[Bot]: A list of all bot templates.
        """
        return list(self.templates.values())

    def list_templates_with_ids(self) -> List[tuple[str, BotData]]:
        """
        Lists all bot templates along with their IDs.

        Returns:
            List[tuple[str, Bot]]: A list of tuples, where each tuple contains (template_id, Bot object).
        """
        return list(self.templates.items())

    def update_template(self, template_id: str, bot_config: BotData) -> bool:
        """
        Updates an existing bot template.

        Args:
            template_id (str): The ID of the template to update.
            bot_config (Bot): The Bot object with the updated configuration.

        Returns:
            bool: True if update was successful, False otherwise.
        """
        if template_id not in self.templates:
            self.logger.warning(f"Template with ID {template_id} not found for update.")
            return False

        if not isinstance(bot_config, BotData):
            self.logger.error("Invalid bot_config provided for template update.")
            return False

        self.templates[template_id] = bot_config
        self._save_templates()
        self.logger.info(f"Bot template with ID {template_id} updated to '{bot_config.name}'.")
        return True

    def delete_template(self, template_id: str) -> bool:
        """
        Deletes a bot template.

        Args:
            template_id (str): The ID of the template to delete.

        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        if template_id in self.templates:
            deleted_name = self.templates[template_id].name
            del self.templates[template_id]
            self._save_templates()
            self.logger.info(f"Bot template '{deleted_name}' with ID {template_id} deleted.")
            return True
        self.logger.warning(f"Template with ID {template_id} not found for deletion.")
        return False

    def clear_all_templates(self):
        """Removes all bot templates and clears the storage file."""
        self.templates = {}
        self._save_templates() # This will write an empty dict to the file
        self.logger.info("All bot templates have been cleared.")
