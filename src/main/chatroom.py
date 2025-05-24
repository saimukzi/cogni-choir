from __future__ import annotations # For forward references in type hints like 'ChatroomManager'
import logging
import os
import json
import re
import glob
from typing import Optional, Union # For type hints

from .ai_bots import Bot # Keep this for type hinting and Bot.to_dict()
from .message import Message

DATA_DIR = os.path.join("data", "chatrooms")

def _sanitize_filename(name: str) -> str:
    name = re.sub(r'[^\w\s-]', '', name).strip() # Remove non-alphanumeric (excluding _, -, space)
    name = re.sub(r'[-\s]+', '_', name)      # Replace spaces/hyphens with underscore
    return name + ".json"

class Chatroom:
    def __init__(self, name: str): # name here is the initial name
        self.logger = logging.getLogger(__name__ + ".Chatroom")
        self._name: str = name 
        self.logger.debug(f"Chatroom '{name}' initialized.") # DEBUG
        self.bots: dict[str, Bot] = {}
        self.messages: list[Message] = []
        self.manager: Optional[ChatroomManager] = None # Will be set by ChatroomManager
        self.filepath: Optional[str] = None             # Will be set by ChatroomManager

    @property
    def name(self) -> str:
        return self._name

    # No direct set_name; managed by ChatroomManager.rename_chatroom


    def add_bot(self, bot: Bot) -> bool:
        """
        Adds a bot to the chatroom. If a bot with the same name already exists, it will be replaced.

        Args:
            bot (Bot): The bot to add.
        Returns:
            bool: True if the bot was added successfully, False if the bot name is invalid.
        """
        bot_name = bot.get_name()
        self.bots[bot_name] = bot
        self.logger.info(f"Bot '{bot_name}' added to chatroom '{self.name}'.") # INFO
        if self.manager:
            self.manager._notify_chatroom_updated(self)
        return True

    def remove_bot(self, bot_name: str):
        if bot_name in self.bots:
            del self.bots[bot_name]
            self.logger.info(f"Bot '{bot_name}' removed from chatroom '{self.name}'.") # INFO
            if self.manager:
                self.manager._notify_chatroom_updated(self)
        else:
            self.logger.warning(f"Attempted to remove non-existent bot '{bot_name}' from chatroom '{self.name}'.") # WARNING

    def get_bot(self, bot_name: str) -> Bot | None:
        bot = self.bots.get(bot_name)
        if bot:
            self.logger.debug(f"Bot '{bot_name}' retrieved from chatroom '{self.name}'.") # DEBUG
        else:
            self.logger.debug(f"Bot '{bot_name}' not found in chatroom '{self.name}'.") # DEBUG
        return bot

    def list_bots(self) -> list[Bot]:
        self.logger.debug(f"Listing {len(self.bots)} bot(s) for chatroom '{self.name}'.") # DEBUG
        return list(self.bots.values())

    def add_message(self, sender: str, content: str) -> Message:
        message = Message(sender=sender, content=content)
        self.messages.append(message)
        self.logger.info(f"Message from '{sender}' (length: {len(content)}) added to chatroom '{self.name}'.") # INFO
        if self.manager:
            self.manager._notify_chatroom_updated(self)
        return message

    def get_messages(self) -> list[Message]:
        self.logger.debug(f"Retrieving {len(self.messages)} message(s) for chatroom '{self.name}'.") # DEBUG
        return self.messages

    def get_formatted_history(self) -> list[str]:
        return [msg.to_display_string() for msg in self.messages]

    def delete_message(self, message_timestamp: float) -> bool:
        original_length = len(self.messages)
        self.messages = [msg for msg in self.messages if msg.timestamp != message_timestamp]
        deleted = len(self.messages) < original_length
        if deleted:
            self.logger.info(f"Message with timestamp {message_timestamp} deleted from chatroom '{self.name}'.") # INFO
            if self.manager:
                self.manager._notify_chatroom_updated(self)
        else:
            self.logger.warning(f"Failed to delete message with timestamp {message_timestamp} from chatroom '{self.name}': not found.") # WARNING
        return deleted

    def to_dict(self) -> dict:
        self.logger.debug(f"Serializing chatroom '{self.name}' to dictionary.") # DEBUG
        return {
            "name": self.name, # Uses the property
            "bots": [bot.to_dict() for bot in self.bots.values()],
            "messages": [msg.to_dict() for msg in self.messages]
        }

    def _save(self):
        if not self.filepath:
            self.logger.warning(f"Chatroom '{self.name}' cannot be saved: filepath is not set.") # WARNING
            return

        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=4)
            self.logger.debug(f"Chatroom '{self.name}' saved successfully to '{self.filepath}'.") # DEBUG
        except Exception as e:
            self.logger.error(f"Error saving chatroom '{self.name}' to '{self.filepath}': {e}", exc_info=True) # ERROR

    @staticmethod
    def from_dict(data: dict, manager: ChatroomManager, filepath: str, api_key_manager) -> Chatroom:
        logger = logging.getLogger(__name__ + ".Chatroom") # Static method, so get logger instance
        chatroom_name = data.get("name", "UnknownChatroom")
        logger.debug(f"Deserializing chatroom '{chatroom_name}' from dictionary. File: {filepath}") # DEBUG
        # Import AI engine classes locally to avoid circular dependency at module level
        from .ai_engines import GeminiEngine, GrokEngine, OpenAIEngine # Updated import
        from .ai_bots import Bot # Bot import remains the same
        
        engine_map = {
            "GeminiEngine": GeminiEngine, "GrokEngine": GrokEngine, "OpenAIEngine": OpenAIEngine
        }
        
        chatroom = Chatroom(name=data["name"]) # Initializes _name
        chatroom.manager = manager
        chatroom.filepath = filepath
        # chatroom._name is already set by Chatroom(name=data["name"])

        for bot_data in data.get("bots", []):
            engine_type_name = bot_data.get("engine_type") # Use .get for safety
            engine_class = engine_map.get(engine_type_name)
            if engine_class:
                service_name_for_key = engine_type_name.replace("Engine", "")
                api_key = None # Default to None
                if api_key_manager: # Check if api_key_manager is provided
                    api_key = api_key_manager.load_key(service_name_for_key)
                
                engine_instance = engine_class(api_key=api_key, model_name=bot_data.get("model_name", ""))
                
                if not api_key and engine_instance.requires_api_key():
                     print(f"Warning: API key for {service_name_for_key} not found for bot '{bot_data.get('name', 'UnknownBot')}' in chatroom '{chatroom.name}'. Bot may not function as it requires an API key.")
                
                bot = Bot(name=bot_data.get("name","UnnamedBot"), system_prompt=bot_data.get("system_prompt",""), engine=engine_instance)
                chatroom.bots[bot.get_name()] = bot
            else:
                logger.warning(f"Unknown or missing engine type '{engine_type_name}' for bot '{bot_data.get('name', 'UnknownBot')}' in chatroom '{chatroom.name}'.")
        
        for msg_data in data.get("messages", []):
            try:
                message = Message.from_dict(msg_data)
                chatroom.messages.append(message)
            except Exception as e:
                logger.error(f"Error loading message from data in {chatroom.name}: {msg_data}, error: {e}", exc_info=True) # ERROR
        
        logger.debug(f"Chatroom '{chatroom_name}' deserialized successfully.") # DEBUG
        return chatroom


class ChatroomManager:
    def __init__(self, api_key_manager): # api_key_manager is now required
        self.logger = logging.getLogger(__name__ + ".ChatroomManager")
        self.chatrooms: dict[str, Chatroom] = {}
        self.api_key_manager = api_key_manager # Store it
        self.logger.info(f"ChatroomManager initialized. Data directory: {os.path.abspath(DATA_DIR)}") # INFO
        self._load_chatrooms_from_disk()

    def _load_chatrooms_from_disk(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        loaded_count = 0
        file_list = glob.glob(os.path.join(DATA_DIR, "*.json"))
        if not file_list:
            self.logger.info("No chatroom files found to load.") # INFO
            return

        for filepath in file_list:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Pass self.api_key_manager to from_dict
                chatroom = Chatroom.from_dict(data, self, filepath, self.api_key_manager)
                self.chatrooms[chatroom.name] = chatroom 
                loaded_count +=1
            except Exception as e:
                self.logger.error(f"Error loading chatroom from {filepath}: {e}", exc_info=True) # ERROR
        self.logger.info(f"Loaded {loaded_count} chatroom(s) from disk.") # INFO


    def _notify_chatroom_updated(self, chatroom: Chatroom):
        self.logger.debug(f"Chatroom '{chatroom.name}' updated, triggering save.") # DEBUG
        chatroom._save()

    def create_chatroom(self, name: str) -> Optional[Chatroom]:
        if name in self.chatrooms:
            self.logger.warning(f"Failed to create chatroom '{name}': already exists.") # WARNING
            return None
        
        chatroom = Chatroom(name=name) 
        chatroom.manager = self
        chatroom_filename = _sanitize_filename(name)
        chatroom.filepath = os.path.join(DATA_DIR, chatroom_filename)
        
        self.chatrooms[name] = chatroom 
        chatroom._save() 
        self.logger.info(f"Chatroom '{name}' created successfully. File: {chatroom.filepath}") # INFO
        return chatroom

    def delete_chatroom(self, name: str):
        chatroom = self.chatrooms.pop(name, None)
        if chatroom and chatroom.filepath and os.path.exists(chatroom.filepath):
            try:
                os.remove(chatroom.filepath)
                self.logger.info(f"Chatroom '{name}' and its file '{chatroom.filepath}' deleted successfully.") # INFO
            except Exception as e:
                self.logger.error(f"Error deleting file {chatroom.filepath} for chatroom '{name}': {e}", exc_info=True) # ERROR
        elif chatroom: 
             self.logger.info(f"Chatroom '{name}' removed from manager (file not found or path missing).") # INFO
        else: 
            self.logger.warning(f"Attempted to delete non-existent chatroom '{name}'.") # WARNING


    def get_chatroom(self, name: str) -> Optional[Chatroom]:
        chatroom = self.chatrooms.get(name)
        if not chatroom:
            self.logger.debug(f"Chatroom '{name}' not found.") # DEBUG
        return chatroom

    def list_chatrooms(self) -> list[Chatroom]: 
        return list(self.chatrooms.values())

    def rename_chatroom(self, old_name: str, new_name: str) -> bool:
        if new_name == old_name:
            self.logger.info(f"Chatroom rename requested from '{old_name}' to '{new_name}', but names are identical. No action taken.") # INFO
            return True 
        if new_name in self.chatrooms:
            self.logger.warning(f"Failed to rename chatroom '{old_name}' to '{new_name}': new name already exists.") # WARNING
            return False
        
        chatroom = self.chatrooms.pop(old_name, None)
        if not chatroom:
            self.logger.warning(f"Failed to rename chatroom '{old_name}': not found.") # WARNING
            return False

        old_filepath = chatroom.filepath
        
        chatroom._name = new_name 
        new_filename = _sanitize_filename(new_name)
        chatroom.filepath = os.path.join(DATA_DIR, new_filename)
        
        self.chatrooms[new_name] = chatroom 
        chatroom._save() 
        self.logger.info(f"Chatroom '{old_name}' renamed to '{new_name}' successfully. New file: {chatroom.filepath}") # INFO

        if old_filepath and old_filepath != chatroom.filepath and os.path.exists(old_filepath):
            try:
                os.remove(old_filepath)
                self.logger.info(f"Old chatroom file '{old_filepath}' deleted successfully after rename.") # INFO
            except Exception as e:
                self.logger.error(f"Error deleting old file {old_filepath} after renaming chatroom '{old_name}': {e}", exc_info=True) # ERROR
        return True

    def clone_chatroom(self, original_chatroom_name: str) -> Optional[Chatroom]:
        original_chatroom = self.get_chatroom(original_chatroom_name) 
        if not original_chatroom:
            self.logger.warning(f"Failed to clone chatroom '{original_chatroom_name}': original not found.") # WARNING
            return None

        self.logger.info(f"Attempting to clone chatroom '{original_chatroom_name}'.") # INFO
        base_clone_name = f"{original_chatroom.name} (copy)"
        clone_name = base_clone_name
        count = 1
        while clone_name in self.chatrooms:
            clone_name = f"{base_clone_name} {count}"
            count += 1
        
        # Create the new chatroom (this will also set up its filepath and save it)
        cloned_chatroom = self.create_chatroom(clone_name) 
        if not cloned_chatroom: 
            self.logger.error(f"Failed to clone chatroom '{original_chatroom_name}': could not create new chatroom '{clone_name}'.") # ERROR
            return None

        self.logger.info(f"Chatroom '{original_chatroom_name}' cloned as '{cloned_chatroom.name}'. Now copying bots.") # INFO
        # Copy bots from the original chatroom
        # Local import to avoid potential circular dependency issues at module level if any
        from .ai_engines import GeminiEngine, GrokEngine, OpenAIEngine # Updated import
        from .ai_bots import Bot # Bot import remains the same

        engine_map = {
            "GeminiEngine": GeminiEngine, "GrokEngine": GrokEngine, "OpenAIEngine": OpenAIEngine
        }

        for original_bot in original_chatroom.list_bots():
            original_engine = original_bot.get_engine()
            engine_type_name = type(original_engine).__name__
            service_name_for_key = engine_type_name.replace("Engine", "")
            
            api_key = self.api_key_manager.load_key(service_name_for_key)
            model_name = original_engine.model_name # Get model_name from original engine
            
            engine_class = engine_map.get(engine_type_name)

            if engine_class:
                # If API key is None, engine should handle it (e.g. operate in a limited mode or error on use)
                new_engine_instance = engine_class(api_key=api_key, model_name=model_name)
                
                cloned_bot = Bot(name=original_bot.get_name(),
                                 system_prompt=original_bot.get_system_prompt(),
                                 engine=new_engine_instance)
                cloned_chatroom.add_bot(cloned_bot) 
            else:
                self.logger.warning(f"Could not determine engine class for {engine_type_name} while cloning bot '{original_bot.get_name()}' from '{original_chatroom_name}' into '{cloned_chatroom.name}'. Bot not copied.") # WARNING

        self.logger.info(f"Finished cloning chatroom '{original_chatroom_name}' as '{cloned_chatroom.name}'. Message history was not copied.") # INFO
        # cloned_chatroom is already saved by create_chatroom and subsequent add_bot calls.
        return cloned_chatroom
