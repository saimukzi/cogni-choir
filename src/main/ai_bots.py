"""This module defines the Bot class and a factory function to create bots."""
# from .ai_base import AIEngine # Import AIEngine from its new location

from .apikey_manager import ApiKeyQuery

# Bot class and create_bot function remain here.
# AIEngine class has been moved to ai_base.py
from typing import Dict, Any, List

class Bot:
    """Represents an AI bot with a specific name, AI engine configuration, and API key requirements."""
    def __init__(self, name: str = "", aiengine_id: str = "",
                 aiengine_arg_dict: Dict[str, Any] = None,
                 apikey_query_list: List[Any] = None): # Replace Any with ApiKeyQuery if available/needed
        """Initializes a new instance of the Bot class.

        Args:
            name (str): The name of the bot.
            aiengine_id (str): The ID of the AI engine to be used.
            aiengine_arg_dict (Dict[str, Any], optional): Arguments for the AI engine. Defaults to None, then {}.
            apikey_query_list (List[Any], optional): List of API key queries. Defaults to None, then [].
                                                       Each item can be an ApiKeyQuery object or a dict.
        """
        self.name: str = name
        self.aiengine_id: str = aiengine_id
        self.aiengine_arg_dict: Dict[str, Any] = aiengine_arg_dict if aiengine_arg_dict is not None else {}
        # Ensure apikey_query_list is a list of dicts or appropriate objects for JSON serialization
        self.apikey_query_list: List[Any] = apikey_query_list if apikey_query_list is not None else []
        # Add other attributes like system_prompt if they are part of aiengine_arg_dict or separate

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the Bot instance to a dictionary for JSON storage.

        Returns:
            A dictionary containing the bot's configuration.
        """
        return {
            "name": self.name,
            "aiengine_id": self.aiengine_id,
            "aiengine_arg_dict": self.aiengine_arg_dict,
            # Ensure ApiKeyQuery can be serialized. If ApiKeyQuery has to_dict, use it.
            # If apikey_query_list already stores dicts (e.g., from BotInfoDialog), this is fine.
            "apikey_query_list": [
                query.to_dict() if hasattr(query, 'to_dict') and callable(getattr(query, 'to_dict'))
                else query
                for query in self.apikey_query_list if query is not None
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Bot':
        """Deserializes a Bot instance from a dictionary.

        Args:
            data (Dict[str, Any]): A dictionary containing the bot's configuration.

        Returns:
            Bot: An instance of Bot with the provided configuration.
        """
        apikey_queries_data = data.get("apikey_query_list", [])
        deserialized_queries = []
        for query_data in apikey_queries_data:
            if isinstance(query_data, dict) and ApiKeyQuery and hasattr(ApiKeyQuery, 'from_dict'):
                # Attempt to deserialize if ApiKeyQuery.from_dict exists and query_data is a dict
                try:
                    deserialized_queries.append(ApiKeyQuery.from_dict(query_data))
                except Exception: # Broad exception if from_dict fails, fallback to raw data
                    deserialized_queries.append(query_data)
            else:
                # If it's not a dict or ApiKeyQuery.from_dict is not available, store as is
                deserialized_queries.append(query_data)

        return cls(
            name=data.get("name", ""),
            aiengine_id=data.get("aiengine_id", ""),
            aiengine_arg_dict=data.get("aiengine_arg_dict", {}),
            apikey_query_list=deserialized_queries
        )

    def get_aiengine_arg(self, arg_id: str, default: Any = None) -> Any:
        """Retrieves the value of a specific AI engine argument.

        Args:
            arg_id: The ID of the argument to retrieve.
            default: The default value to return if the argument is not found.

        Returns:
            The value of the argument if it exists, otherwise returns the default value.
        """
        if self.aiengine_arg_dict and arg_id in self.aiengine_arg_dict:
            return self.aiengine_arg_dict[arg_id]
        return default
