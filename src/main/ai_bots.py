"""This module defines the Bot class and a factory function to create bots."""
# from .ai_base import AIEngine # Import AIEngine from its new location

from .apikey_manager import ApiKeyQuery

# Bot class and create_bot function remain here.
# AIEngine class has been moved to ai_base.py

class Bot:
    """Represents an AI bot with a specific name, system prompt, and AI engine."""
    def __init__(self):
        """Initializes a new instance of the Bot class."""
        self.name : str|None = None
        self.aiengine_id : str|None = None
        self.aiengine_arg_dict : dict|None = None
        self.apikey_query_list : list[ApiKeyQuery] | None = None

    def to_dict(self) -> dict:
        """Converts the bot's configuration to a dictionary.

        Returns:
            A dictionary containing the bot's name, system prompt,
            engine type (class name of the engine), and model name.
        """
        ret_apikey_query_list = None
        if self.apikey_query_list is not None:
            ret_apikey_query_list = self.apikey_query_list
            ret_apikey_query_list = filter(lambda x: x is not None, ret_apikey_query_list)
            ret_apikey_query_list = map(lambda x: x.to_dict(), ret_apikey_query_list)
            ret_apikey_query_list = list(ret_apikey_query_list)
        return {
            'name': self.name,
            'aiengine_id': self.aiengine_id,
            'aiengine_arg_dict': self.aiengine_arg_dict,
            'apikey_query_list': ret_apikey_query_list,
        }

    @staticmethod
    def from_dict(data: dict) -> 'Bot':
        """Creates a Bot instance from a dictionary.

        Args:
            data: A dictionary containing the bot's configuration.

        Returns:
            An instance of Bot with the provided configuration.
        """
        bot = Bot()
        bot.name = data.get('name')
        bot.aiengine_id = data.get('aiengine_id')
        bot.aiengine_arg_dict = data.get('aiengine_arg_dict', {})
        bot_apikey_query_list = data.get('apikey_query_list', None)
        if bot_apikey_query_list is not None:
            bot_apikey_query_list = list(map(ApiKeyQuery.from_dict, bot_apikey_query_list))
        bot.apikey_query_list = bot_apikey_query_list
        return bot

    def get_aiengine_arg(self, arg_id: str, default: str=None) -> str | None:
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
