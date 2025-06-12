"""This module defines the Bot class and a factory function to create bots."""
# from .ai_base import AIEngine # Import AIEngine from its new location
# from dataclasses import dataclass, field
from typing import Dict, Any, List

from pydantic import BaseModel, Field

from .thirdpartyapikey_manager import ThirdPartyApiKeyQueryData

# Bot class and create_bot function remain here.
# AIEngine class has been moved to ai_base.py

class BotData(BaseModel):
    """Represents an AI bot with a specific name, AI engine configuration, and API key requirements."""
    name: str = ""
    aiengine_id: str = ""
    aiengine_arg_dict: Dict[str, str] = Field(default_factory=dict)
    thirdpartyapikey_query_list: List['ThirdPartyApiKeyQueryData'] = Field(default_factory=list)

    # def to_dict(self) -> Dict[str, Any]:
    #     """Serializes the Bot instance to a dictionary for JSON storage.

    #     Returns:
    #         A dictionary containing the bot's configuration.
    #     """
    #     return {
    #         "name": self.name,
    #         "aiengine_id": self.aiengine_id,
    #         "aiengine_arg_dict": self.aiengine_arg_dict,
    #         "thirdpartyapikey_query_list": [
    #             query.to_dict()
    #             for query in self.thirdpartyapikey_query_list
    #         ]
    #     }

    # @classmethod
    # def from_dict(cls, data: Dict[str, Any]) -> 'BotData':
    #     """Deserializes a Bot instance from a dictionary.

    #     Args:
    #         data (Dict[str, Any]): A dictionary containing the bot's configuration.

    #     Returns:
    #         Bot: An instance of Bot with the provided configuration.
    #     """
    #     thirdpartyapikey_queries_data = data.get("thirdpartyapikey_query_list", [])
    #     thirdpartyapikey_query_list = []
    #     for query_data in thirdpartyapikey_queries_data:
    #         thirdpartyapikey_query_list.append(ThirdPartyApiKeyQueryData.from_dict(query_data))

    #     return cls(
    #         name=data.get("name", ""),
    #         aiengine_id=data.get("aiengine_id", ""),
    #         aiengine_arg_dict=data.get("aiengine_arg_dict", {}),
    #         thirdpartyapikey_query_list=thirdpartyapikey_query_list
    #     )

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
