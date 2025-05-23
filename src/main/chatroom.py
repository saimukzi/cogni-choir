from __future__ import annotations # For forward references in type hints like 'ChatroomManager'
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
        self._name: str = name 
        self.bots: dict[str, Bot] = {}
        self.messages: list[Message] = []
        self.manager: Optional[ChatroomManager] = None # Will be set by ChatroomManager
        self.filepath: Optional[str] = None             # Will be set by ChatroomManager

    @property
    def name(self) -> str:
        return self._name

    # No direct set_name; managed by ChatroomManager.rename_chatroom

    def add_bot(self, bot: Bot):
        self.bots[bot.get_name()] = bot
        if self.manager:
            self.manager._notify_chatroom_updated(self)

    def remove_bot(self, bot_name: str):
        if bot_name in self.bots:
            del self.bots[bot_name]
            if self.manager:
                self.manager._notify_chatroom_updated(self)
        else:
            # Consider logging a warning or raising an error
            pass

    def get_bot(self, bot_name: str) -> Bot | None:
        return self.bots.get(bot_name)

    def list_bots(self) -> list[Bot]:
        return list(self.bots.values())

    def add_message(self, sender: str, content: str) -> Message:
        message = Message(sender=sender, content=content)
        self.messages.append(message)
        if self.manager:
            self.manager._notify_chatroom_updated(self)
        return message

    def get_messages(self) -> list[Message]:
        return self.messages

    def get_formatted_history(self) -> list[str]:
        return [msg.to_display_string() for msg in self.messages]

    def delete_message(self, message_timestamp: float) -> bool:
        original_length = len(self.messages)
        self.messages = [msg for msg in self.messages if msg.timestamp != message_timestamp]
        if len(self.messages) < original_length:
            if self.manager:
                self.manager._notify_chatroom_updated(self)
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "name": self.name, # Uses the property
            "bots": [bot.to_dict() for bot in self.bots.values()],
            "messages": [msg.to_dict() for msg in self.messages]
        }

    def _save(self):
        if not self.filepath:
            print(f"Warning: Chatroom '{self.name}' cannot be saved without a filepath.")
            return

        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving chatroom {self.name} to {self.filepath}: {e}")

    @staticmethod
    def from_dict(data: dict, manager: ChatroomManager, filepath: str, api_key_manager) -> Chatroom:
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
                
                if not api_key and engine_type_name in ["GeminiEngine", "GrokEngine", "OpenAIEngine"]: # Assuming these definitely need keys
                     print(f"Warning: API key for {service_name_for_key} not found for bot '{bot_data.get('name', 'UnknownBot')}' in chatroom '{chatroom.name}'. Bot may not function.")
                
                engine_instance = engine_class(api_key=api_key) 
                bot = Bot(name=bot_data.get("name","UnnamedBot"), system_prompt=bot_data.get("system_prompt",""), engine=engine_instance)
                chatroom.bots[bot.get_name()] = bot
            else:
                print(f"Warning: Unknown or missing engine type '{engine_type_name}' for bot '{bot_data.get('name', 'UnknownBot')}' in chatroom '{chatroom.name}'.")
        
        for msg_data in data.get("messages", []):
            try:
                message = Message.from_dict(msg_data)
                chatroom.messages.append(message)
            except Exception as e:
                print(f"Error loading message from data in {chatroom.name}: {msg_data}, error: {e}")
        
        return chatroom


class ChatroomManager:
    def __init__(self, api_key_manager): # api_key_manager is now required
        self.chatrooms: dict[str, Chatroom] = {}
        self.api_key_manager = api_key_manager # Store it
        self._load_chatrooms_from_disk()

    def _load_chatrooms_from_disk(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        for filepath in glob.glob(os.path.join(DATA_DIR, "*.json")):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Pass self.api_key_manager to from_dict
                chatroom = Chatroom.from_dict(data, self, filepath, self.api_key_manager)
                self.chatrooms[chatroom.name] = chatroom 
            except Exception as e:
                print(f"Error loading chatroom from {filepath}: {e}")

    def _notify_chatroom_updated(self, chatroom: Chatroom):
        chatroom._save()

    def create_chatroom(self, name: str) -> Optional[Chatroom]:
        if name in self.chatrooms:
            return None
        
        chatroom = Chatroom(name=name) # Chatroom._name is set here
        chatroom.manager = self
        chatroom_filename = _sanitize_filename(name)
        chatroom.filepath = os.path.join(DATA_DIR, chatroom_filename)
        
        self.chatrooms[name] = chatroom # Use the original name for the dictionary key
        chatroom._save() 
        return chatroom

    def delete_chatroom(self, name: str):
        chatroom = self.chatrooms.pop(name, None)
        if chatroom and chatroom.filepath and os.path.exists(chatroom.filepath):
            try:
                os.remove(chatroom.filepath)
            except Exception as e:
                print(f"Error deleting file {chatroom.filepath}: {e}")
        # If chatroom was not found in self.chatrooms, it's already "deleted" from manager's perspective

    def get_chatroom(self, name: str) -> Optional[Chatroom]:
        return self.chatrooms.get(name)

    def list_chatrooms(self) -> list[Chatroom]: # Changed return type
        return list(self.chatrooms.values())

    def rename_chatroom(self, old_name: str, new_name: str) -> bool:
        if new_name == old_name:
            return True # No change needed, considered success
        if new_name in self.chatrooms:
            print(f"Error: Cannot rename chatroom. New name '{new_name}' already exists.")
            return False
        
        chatroom = self.chatrooms.pop(old_name, None)
        if not chatroom:
            print(f"Error: Chatroom '{old_name}' not found for renaming.")
            return False

        old_filepath = chatroom.filepath
        
        chatroom._name = new_name # Update internal name
        new_filename = _sanitize_filename(new_name)
        chatroom.filepath = os.path.join(DATA_DIR, new_filename)
        
        self.chatrooms[new_name] = chatroom # Re-add with new name as key
        chatroom._save() # Save to new path

        if old_filepath and old_filepath != chatroom.filepath and os.path.exists(old_filepath):
            try:
                os.remove(old_filepath)
            except Exception as e:
                print(f"Error deleting old file {old_filepath}: {e}")
        return True

    def clone_chatroom(self, original_chatroom_name: str) -> Optional[Chatroom]:
        original_chatroom = self.get_chatroom(original_chatroom_name)
        if not original_chatroom:
            return None

        # Generate a unique name for the clone
        base_clone_name = f"{original_chatroom.name} (copy)"
        clone_name = base_clone_name
        count = 1
        while clone_name in self.chatrooms:
            clone_name = f"{base_clone_name} {count}"
            count += 1
        
        # Create the new chatroom (this will also set up its filepath and save it)
        cloned_chatroom = self.create_chatroom(clone_name)
        if not cloned_chatroom: # Should not happen if name generation is correct
            return None

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
                cloned_chatroom.add_bot(cloned_bot) # add_bot will trigger save for the cloned_chatroom
            else:
                print(f"Warning: Could not determine engine class for {engine_type_name} while cloning bot {original_bot.get_name()} into {cloned_chatroom.name}")

        # Message history is NOT copied.
        # cloned_chatroom is already saved by create_chatroom and subsequent add_bot calls.
        # No explicit save needed here unless add_bot's auto-save is removed.
        
        return cloned_chatroom
