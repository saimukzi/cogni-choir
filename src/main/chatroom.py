"""Manages chatrooms, including their creation, persistence, and interactions.

This module defines the `Chatroom` class, representing a single chat session
with its associated bots and message history, and the `ChatroomManager` class,
which handles the loading, saving, and overall management of multiple chatrooms.

Chatrooms are persisted as JSON files in the `data/chatrooms` directory.
Filename sanitization is handled by the `_sanitize_filename` function.
"""
from __future__ import annotations # For forward references in type hints like 'ChatroomManager'
import logging
import os
import json
import re
import time
import glob
from typing import Optional # For type hints
import copy
from dataclasses import dataclass, asdict

from .ai_bots import BotData
# create_bot is imported locally in methods that use it.
from .message import MessageData

from . import commons

DATA_DIR = os.path.join("data", "chatrooms")

def _sanitize_filename(name: str) -> str:
    """Sanitizes a string to be suitable as a filename.

    Removes characters that are generally problematic in filenames,
    replaces spaces and hyphens with underscores, and appends ".json".

    Args:
        name: The string to sanitize.

    Returns:
        A sanitized string suitable for use as a filename.
    """
    name = re.sub(r'[^\w\s-]', '', name).strip() # Remove non-alphanumeric (excluding _, -, space)
    name = re.sub(r'[-\s]+', '_', name)      # Replace spaces/hyphens with underscore
    return name + ".json"

@dataclass
class ChatroomData:
    """Represents a chatroom's data for serialization.

    Attributes:
        name (str): The name of the chatroom.
        bots (dict[str, BotData]): A dictionary of bots in the chatroom, keyed by bot name.
        messages (list[MessageData]): A list of messages exchanged in the chatroom.
    """
    name: str
    bots: dict[str, BotData]
    messages: list[MessageData]

class Chatroom:
    """Represents a single chatroom, containing messages and associated bots.

    Attributes:
        logger: Logger instance for this chatroom.
        _data (ChatroomData): The data structure containing chatroom information.
        manager (Optional[ChatroomManager]): A reference to the ChatroomManager, if any.
        filepath (Optional[str]): The filesystem path where this chatroom is saved.
    """
    def __init__(self, data: ChatroomData, manager: Optional[ChatroomManager], filepath: Optional[str]): # name here is the initial name
        """Initializes a new Chatroom instance.

        Args:
            name: The initial name for the chatroom.
        """
        self.logger = logging.getLogger(__name__ + ".Chatroom")

        # self._name: str = name
        # self._data = ChatroomData(name=name, bots={}, messages=[]) # Initialize with empty bots and messages
        # self.logger.debug(f"Chatroom '{name}' initialized.") # DEBUG
        # # self.bots: dict[str, BotData] = {}
        # # self.messages: list[MessageData] = []
        # self.manager: Optional[ChatroomManager] = None # Will be set by ChatroomManager
        # self.filepath: Optional[str] = None             # Will be set by ChatroomManager

        self._data = data
        self.manager: Optional[ChatroomManager] = manager
        self.filepath: Optional[str] = filepath
        self.logger.debug(f"Chatroom '{self.name}' initialized with {len(self._data.bots)} bot(s) and {len(self._data.messages)} message(s).")

    @property
    def name(self) -> str:
        """The name of the chatroom."""
        return self._data.name

    # No direct set_name; managed by ChatroomManager.rename_chatroom


    def add_bot(self, bot: BotData) -> bool:
        """Adds a bot to the chatroom.

        If a bot with the same name already exists, it will be replaced.
        Notifies the manager (if any) that the chatroom has been updated.

        Args:
            bot: The `Bot` instance to add.

        Returns:
            True if the bot was added (currently always True).
        """
        bot_name = bot.name
        self._data.bots[bot_name] = bot
        self.logger.info(f"Bot '{bot_name}' added to chatroom '{self.name}'.") # INFO
        if self.manager:
            self.manager.notify_chatroom_updated(self)
        return True

    def remove_bot(self, bot_name: str) -> bool:
        """Removes a bot from the chatroom.

        Notifies the manager (if any) if a bot was successfully removed.

        Args:
            bot_name: The name of the bot to remove.

        Returns:
            True if the bot was removed, False otherwise.
        """
        if bot_name in self._data.bots:
            del self._data.bots[bot_name]
            self.logger.info(f"Bot '{bot_name}' removed from chatroom '{self.name}'.") # INFO
            if self.manager:
                self.manager.notify_chatroom_updated(self)
            return True
        else:
            self.logger.warning(f"Attempted to remove non-existent bot '{bot_name}' from chatroom '{self.name}'.") # WARNING
        return False

    def get_bot(self, bot_name: str) -> BotData | None:
        """Retrieves a bot from the chatroom by its name.

        Args:
            bot_name: The name of the bot to retrieve.

        Returns:
            The `Bot` instance if found, otherwise None.
        """
        bot = self._data.bots.get(bot_name)
        if bot:
            self.logger.debug(f"Bot '{bot_name}' retrieved from chatroom '{self.name}'.") # DEBUG
        else:
            self.logger.debug(f"Bot '{bot_name}' not found in chatroom '{self.name}'.") # DEBUG
        return bot

    def list_bots(self) -> list[BotData]:
        """Lists all bots currently in the chatroom.

        Returns:
            A list of `Bot` instances.
        """
        self.logger.debug(f"Listing {len(self._data.bots)} bot(s) for chatroom '{self.name}'.") # DEBUG
        return list(self._data.bots.values())

    def add_message(self, sender: str, content: str) -> MessageData:
        """Adds a new message to the chatroom's history.

        Notifies the manager (if any) that the chatroom has been updated.

        Args:
            sender: The name of the sender (user or bot).
            content: The content of the message.

        Returns:
            The created `Message` object.
        """
        message = MessageData(sender=sender, content=content, timestamp=time.time())
        self._data.messages.append(message)
        self.logger.info(f"Message from '{sender}' (length: {len(content)}) added to chatroom '{self.name}'.") # INFO
        if self.manager:
            self.manager.notify_chatroom_updated(self)
        return message

    def get_messages(self) -> list[MessageData]:
        """Retrieves all messages from the chatroom's history.

        Returns:
            A list of `Message` objects.
        """
        self.logger.debug(f"Retrieving {len(self._data.messages)} message(s) for chatroom '{self.name}'.") # DEBUG
        return self._data.messages

    def get_formatted_history(self) -> list[str]:
        """Gets the chat history formatted for display.

        Returns:
            A list of strings, where each string is a display-formatted message.
        """
        return [msg.to_display_string() for msg in self._data.messages]

    def delete_message(self, message_timestamp: float) -> bool:
        """Deletes a message from the chatroom based on its timestamp.

        Notifies the manager (if any) if a message was successfully deleted.

        Args:
            message_timestamp: The timestamp of the message to delete.

        Returns:
            True if a message was deleted, False otherwise.
        """
        original_length = len(self._data.messages)
        self._data.messages = [msg for msg in self._data.messages if msg.timestamp != message_timestamp]
        deleted = len(self._data.messages) < original_length
        if deleted:
            self.logger.info(f"Message with timestamp {message_timestamp} deleted from chatroom '{self.name}'.") # INFO
            if self.manager:
                self.manager.notify_chatroom_updated(self)
        else:
            self.logger.warning(f"Failed to delete message with timestamp {message_timestamp} from chatroom '{self.name}': not found.") # WARNING
        return deleted

    def to_dict(self) -> dict:
        """Serializes the chatroom to a dictionary.

        Returns:
            A dictionary representation of the chatroom, including its name,
            bots, and messages.
        """
        self.logger.debug(f"Serializing chatroom '{self.name}' to dictionary.") # DEBUG
        # return {
        #     "name": self.name, # Uses the property
        #     "bots": [bot.to_dict() for bot in self._data.bots.values()],
        #     "messages": [msg.to_dict() for msg in self._data.messages]
        # }
        return asdict(self._data)

    def save(self):
        """Saves the chatroom to its associated JSON file.

        The chatroom must have a `filepath` set. This is typically handled
        by the `ChatroomManager`.
        """
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
    def from_dict(data: dict, manager: ChatroomManager, filepath: str) -> Chatroom:
        """Deserializes a chatroom from a dictionary (typically from a JSON file).

        Args:
            data: The dictionary containing chatroom data.
            manager: The `ChatroomManager` instance that will manage this chatroom.
            filepath: The path to the file from which the chatroom was loaded.

        Returns:
            A `Chatroom` instance populated with data from the dictionary.
        """
        logger = logging.getLogger(__name__ + ".Chatroom") # Static method, so get logger instance

        # chatroom_name = data.get("name", "UnknownChatroom")
        # logger.debug(f"Deserializing chatroom '{chatroom_name}' from dictionary. File: {filepath}") # DEBUG
        # # Import create_bot and Bot (Bot is still needed for type hints if not for instantiation here)
        # # from .ai_bots import Bot
        # # Removed local imports for GeminiEngine, GrokEngine as create_bot handles engine instantiation

        # chatroom = Chatroom(name=data["name"]) # Initializes _name
        # chatroom._data = ChatroomData(
        #     name=data["name"],
        #     bots={},  # Will be populated below
        #     messages=[]  # Will be populated below
        # )
        # chatroom.manager = manager
        # chatroom.filepath = filepath
        # # chatroom._name is already set by Chatroom(name=data["name"])

        # for bot_data in data.get("bots", []):
        #     # engine_type_name = bot_data.get("engine_type")
        #     # thirdpartyapikey = None # Default to None
        #     # if engine_type_name and thirdpartyapikey_manager: # Ensure engine_type_name exists before trying to use it
        #     #     service_name_for_key = engine_type_name
        #     #     thirdpartyapikey = thirdpartyapikey_manager.load_key(service_name_for_key)

        #     # engine_config = {
        #     #     "engine_type": engine_type_name,
        #     #     "thirdpartyapikey": thirdpartyapikey,
        #     #     "model_name": bot_data.get("model_name")
        #     # }

        #     # try:
        #     #     bot = create_bot(
        #     #         bot_name=bot_data.get("name", "UnnamedBot"),
        #     #         system_prompt=bot_data.get("system_prompt", ""),
        #     #         engine_config=engine_config,
        #     #     )
        #     #     # Check for API key warning after bot creation, if engine requires it.
        #     #     # This logic might be slightly different as the engine instance is now inside create_bot
        #     #     # However, create_bot itself doesn't have visibility to print this warning directly.
        #     #     # For now, we rely on the existing warning mechanism if a bot fails to operate later.
        #     #     # A more sophisticated approach might involve create_bot returning a status or the engine instance for checks.
        #     #     if not thirdpartyapikey and bot.get_engine().requires_thirdpartyapikey():
        #     #          logger.warning(f"API key for {engine_type_name.replace('Engine','')} not found for bot '{bot.get_name()}' in chatroom '{chatroom.name}'. Bot may not function as it requires an API key.")

        #     #     chatroom.bots[bot.get_name()] = bot
        #     # except ValueError as e:
        #     #     logger.warning(f"Failed to create bot '{bot_data.get('name', 'UnknownBot')}' from data in chatroom '{chatroom_name}' due to: {e}")

        #     bot = BotData.from_dict(bot_data) # Use Bot.from_dict if available
        #     chatroom._data.bots[bot.name] = bot

        # for msg_data in data.get("messages", []):
        #     try:
        #         message = MessageData.from_dict(msg_data)
        #         chatroom._data.messages.append(message)
        #     except Exception as e:
        #         logger.error(f"Error loading message from data in {chatroom.name}: {msg_data}, error: {e}", exc_info=True) # ERROR

        # logger.debug(f"Chatroom '{chatroom_name}' deserialized successfully.") # DEBUG
        # return chatroom

        logger.debug(f"Deserializing chatroom from dictionary. File: {filepath}") # DEBUG
        chatroom_data = commons.to_obj(data, cls=ChatroomData) # Deserialize using jsons
        chatroom = Chatroom(chatroom_data, manager, filepath) # Initializes _name

        return chatroom

    @staticmethod
    def create_by_name(name: str, manager: Optional[ChatroomManager] = None, filepath: Optional[str] = None) -> Chatroom:
        """Creates a new chatroom with the given name.

        Args:
            name: The desired name for the new chatroom.
            manager: An optional `ChatroomManager` instance to manage this chatroom.

        Returns:
            A new `Chatroom` instance with the specified name.
        """
        logger = logging.getLogger(__name__ + ".Chatroom")
        logger.debug(f"Creating new chatroom with name '{name}'.")
        chatroom_data = ChatroomData(name=name, bots={}, messages=[])
        chatroom = Chatroom(data=chatroom_data, manager=manager, filepath=filepath)
        return chatroom

class ChatroomManager:
    """Manages a collection of chatrooms, handling their persistence and lifecycle.

    Attributes:
        logger: Logger instance for the manager.
        chatrooms (dict[str, Chatroom]): A dictionary of chatrooms, keyed by chatroom name.
        thirdpartyapikey_manager: An instance of `ThirdPartyApiKeyManager` for handling API keys for bots.
    """
    def __init__(self): # thirdpartyapikey_manager is now required
        """Initializes the ChatroomManager.

        Loads existing chatrooms from disk.
        """
        self.logger = logging.getLogger(__name__ + ".ChatroomManager")
        self.chatrooms: dict[str, Chatroom] = {}
        self.logger.info(f"ChatroomManager initialized. Data directory: {os.path.abspath(DATA_DIR)}") # INFO
        self._load_chatrooms_from_disk()

    def _load_chatrooms_from_disk(self):
        """Loads all chatroom JSON files from the `DATA_DIR`.

        Populates the `chatrooms` dictionary. Errors during loading of
        individual files are logged but do not stop the process.
        """
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
                chatroom = Chatroom.from_dict(data, self, filepath)
                self.chatrooms[chatroom.name] = chatroom
                loaded_count +=1
            except Exception as e:
                self.logger.error(f"Error loading chatroom from {filepath}: {e}", exc_info=True) # ERROR
        self.logger.info(f"Loaded {loaded_count} chatroom(s) from disk.") # INFO


    def notify_chatroom_updated(self, chatroom: Chatroom):
        """Callback for Chatroom instances to notify the manager of updates.

        Triggers a save operation for the specified chatroom.

        Args:
            chatroom: The `Chatroom` instance that has been updated.
        """
        self.logger.debug(f"Chatroom '{chatroom.name}' updated, triggering save.") # DEBUG
        chatroom.save()

    def create_chatroom(self, name: str) -> Optional[Chatroom]:
        """Creates a new chatroom with the given name.

        If a chatroom with the same name already exists, creation fails.
        The new chatroom is immediately saved to disk.

        Args:
            name: The desired name for the new chatroom.

        Returns:
            The created `Chatroom` instance, or None if a chatroom with that
            name already exists.
        """
        if name in self.chatrooms:
            self.logger.warning(f"Failed to create chatroom '{name}': already exists.") # WARNING
            return None

        chatroom_filename = _sanitize_filename(name)
        chatroom_filepath = os.path.join(DATA_DIR, chatroom_filename)
        chatroom = Chatroom.create_by_name(name, manager=self, filepath=chatroom_filepath)

        self.chatrooms[name] = chatroom
        chatroom.save()
        self.logger.info(f"Chatroom '{name}' created successfully. File: {chatroom.filepath}") # INFO
        return chatroom

    def delete_chatroom(self, name: str) -> bool:
        """Deletes a chatroom and its corresponding file from disk.

        Args:
            name: The name of the chatroom to delete.

        Returns:
            Returns True if the chatroom was successfully deleted, False otherwise.
        """
        chatroom = self.chatrooms.pop(name, None)
        if chatroom and chatroom.filepath and os.path.exists(chatroom.filepath):
            try:
                os.remove(chatroom.filepath)
                self.logger.info(f"Chatroom '{name}' and its file '{chatroom.filepath}' deleted successfully.") # INFO
                return True
            except Exception as e:
                self.logger.error(f"Error deleting file {chatroom.filepath} for chatroom '{name}': {e}", exc_info=True) # ERROR
        elif chatroom:
            self.logger.info(f"Chatroom '{name}' removed from manager (file not found or path missing).") # INFO
        else:
            self.logger.warning(f"Attempted to delete non-existent chatroom '{name}'.") # WARNING
        return False


    def get_chatroom(self, name: str) -> Optional[Chatroom]:
        """Retrieves a chatroom by its name.

        Args:
            name: The name of the chatroom to retrieve.

        Returns:
            The `Chatroom` instance if found, otherwise None.
        """
        chatroom = self.chatrooms.get(name)
        if not chatroom:
            self.logger.debug(f"Chatroom '{name}' not found.") # DEBUG
        return chatroom

    def list_chatrooms(self) -> list[Chatroom]:
        """Lists all currently managed chatrooms.

        Returns:
            A list of `Chatroom` instances.
        """
        return list(self.chatrooms.values())

    def rename_chatroom(self, old_name: str, new_name: str) -> bool:
        """Renames a chatroom.

        This involves updating the chatroom's internal name, its entry in the
        manager's dictionary, its filepath, and saving the chatroom under the
        new filename. The old chatroom file is then deleted.

        Args:
            old_name: The current name of the chatroom.
            new_name: The desired new name for the chatroom.

        Returns:
            True if renaming was successful, False otherwise (e.g., new name
            already exists, or old chatroom not found).
        """
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

        # pylint: disable=protected-access
        chatroom._data.name = new_name # Update the internal name
        new_filename = _sanitize_filename(new_name)
        chatroom.filepath = os.path.join(DATA_DIR, new_filename)

        self.chatrooms[new_name] = chatroom
        chatroom.save()
        self.logger.info(f"Chatroom '{old_name}' renamed to '{new_name}' successfully. New file: {chatroom.filepath}") # INFO

        if old_filepath and old_filepath != chatroom.filepath and os.path.exists(old_filepath):
            try:
                os.remove(old_filepath)
                self.logger.info(f"Old chatroom file '{old_filepath}' deleted successfully after rename.") # INFO
            except Exception as e:
                self.logger.error(f"Error deleting old file {old_filepath} after renaming chatroom '{old_name}': {e}", exc_info=True) # ERROR
        return True

    def clone_chatroom(self, original_chatroom_name: str) -> Optional[Chatroom]:
        """Creates a copy of an existing chatroom.

        The cloned chatroom will have "(copy)" appended to its name (or
        "(copy N)" if necessary to ensure uniqueness).

        Args:
            original_chatroom_name: The name of the chatroom to clone.

        Returns:
            The newly created (cloned) `Chatroom` instance, or None if the
            original chatroom was not found or cloning failed.
        """
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
        # Local imports for engines are removed here as well if create_bot handles instantiation.
        # Bot import is still needed for type hinting and direct instantiation if used.

        # engine_map is removed as create_bot handles this logic.

        for original_bot in original_chatroom.list_bots():
            # original_engine = original_bot.get_engine()
            # engine_type_name = type(original_engine).__name__
            # service_name_for_key = engine_type_name

            # thirdpartyapikey = self.thirdpartyapikey_manager.load_key(service_name_for_key)
            # model_name = original_engine.model_name # Get model_name from original engine

            # engine_config = {
            #     "engine_type": engine_type_name,
            #     "thirdpartyapikey": thirdpartyapikey,
            #     "model_name": model_name
            # }

            # try:
            #     # cloned_bot = create_bot(
            #     #     bot_name=original_bot.get_name(),
            #     #     system_prompt=original_bot.get_system_prompt(),
            #     #     engine_config=engine_config
            #     # )
            #     cloned_bot = original_bot.clone() # Use the clone method of Bot
            #     # Similar to from_dict, API key warning logic after bot creation
            #     if not thirdpartyapikey and cloned_bot.get_engine().requires_thirdpartyapikey():
            #         self.logger.warning(f"API key for {service_name_for_key} not found for cloned bot '{cloned_bot.get_name()}' in chatroom '{cloned_chatroom.name}'. Bot may not function as it requires an API key.")

            #     cloned_chatroom.add_bot(cloned_bot)
            # except ValueError as e:
            #     self.logger.warning(f"Failed to clone bot '{original_bot.get_name()}' into chatroom '{cloned_chatroom.name}' due to: {e}")

            cloned_bot = copy.deepcopy(original_bot) # Use the clone method of Bot
            cloned_chatroom.add_bot(cloned_bot)

        for message in original_chatroom.get_messages():
            cloned_chatroom._data.messages.append(copy.deepcopy(message)) # Copy messages

        self.logger.info(f"Finished cloning chatroom '{original_chatroom_name}' as '{cloned_chatroom.name}'. Message history was not copied.") # INFO
        # cloned_chatroom is already saved by create_chatroom and subsequent add_bot calls.
        return cloned_chatroom
