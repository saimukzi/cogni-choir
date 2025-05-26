"""This module defines the Bot class and a factory function to create bots."""
import logging # For logging
from .ai_base import AIEngine # Import AIEngine from its new location
from .ai_engines import GeminiEngine, GrokEngine, OpenAIEngine # Import necessary engine classes
from . import ai_engines # Import the ai_engines package to access ENGINE_TYPE_TO_CLASS_MAP
# Removed os, requests, google.generativeai, openai imports as they are now in respective engine files.

# Bot class and create_bot function remain here.
# AIEngine class has been moved to ai_base.py
# Engine-specific classes (GeminiEngine, OpenAIEngine, GrokEngine) are in ai_engines package.

class Bot:
    """Represents an AI bot with a specific name, system prompt, and AI engine."""
    def __init__(self, name: str, system_prompt: str, engine: AIEngine): # engine will be an instance of a class from ai_engines
        """Initializes a new instance of the Bot class.

        Args:
            name: The name of the bot.
            system_prompt: The system prompt for the bot.
            engine: The AI engine to use for generating responses.
        """
        self.logger = logging.getLogger(__name__ + ".Bot")
        self.name = name
        self.system_prompt = system_prompt
        self.engine = engine
        self.logger.debug(f"Bot '{self.name}' created with engine '{type(self.engine).__name__}'.") # DEBUG

    def to_dict(self) -> dict:
        """Converts the bot's configuration to a dictionary.

        Returns:
            A dictionary containing the bot's name, system prompt, engine type, and model name.
        """
        engine_type = self.engine.__class__.__name__
        model_name = self.engine.model_name if hasattr(self.engine, 'model_name') else None
        
        return {
            "name": self.name,
            "system_prompt": self.system_prompt,
            "engine_type": engine_type,
            "model_name": model_name 
        }

    def get_name(self) -> str:
        """Gets the name of the bot.

        Returns:
            The name of the bot.
        """
        return self.name

    def set_name(self, new_name: str):
        """Sets the name of the bot.

        Args:
            new_name: The new name for the bot.
        """
        self.name = new_name

    def get_system_prompt(self) -> str:
        """Gets the system prompt of the bot.

        Returns:
            The system prompt of the bot.
        """
        return self.system_prompt

    def set_system_prompt(self, new_prompt: str):
        """Sets the system prompt of the bot.

        Args:
            new_prompt: The new system prompt for the bot.
        """
        self.system_prompt = new_prompt

    def get_engine(self) -> AIEngine:
        """Gets the AI engine of the bot.

        Returns:
            The AI engine of the bot.
        """
        return self.engine

    def set_engine(self, new_engine: AIEngine):
        """Sets the AI engine of the bot.

        Args:
            new_engine: The new AI engine for the bot.
        """
        self.engine = new_engine

    def generate_response(self, conversation_history: list[dict]) -> str:
        """Generates a response from the bot's AI engine.

        Args:
            conversation_history: The conversation history.

        Returns:
            The response from the AI engine.

        Raises:
            Exception: If an error occurs during response generation.
        """
        self.logger.info(f"Bot '{self.name}' generating response for conversation_history of length {len(conversation_history)}.") # INFO
        try:
            response = self.engine.generate_response(
                role_name=self.name,
                system_prompt=self.system_prompt,
                conversation_history=conversation_history
            )
            self.logger.info(f"Bot '{self.name}' successfully generated response.") # INFO
            return response
        except Exception as e:
            self.logger.error(f"Bot '{self.name}' encountered an error during response generation: {e}", exc_info=True) # ERROR
            raise # Re-raise the exception so it can be handled upstream if necessary

def create_bot(bot_name: str, system_prompt: str, engine_config: dict) -> Bot:
    """Creates a Bot instance with the specified configuration.

    This function acts as a factory for creating Bot objects. It initializes the
    appropriate AI engine based on the provided configuration and then instantiates
    the Bot.

    Args:
        bot_name: The name of the bot.
        system_prompt: The system prompt for the bot.
        engine_config: A dictionary containing engine configuration.
                       Expected keys:
                           "engine_type" (str): The type of the AI engine (e.g., "GeminiEngine", "OpenAIEngine").
                           "api_key" (str, optional): The API key for the AI engine, if required.
                           "model_name" (str, optional): The specific model name for the AI engine.

    Returns:
        A Bot instance configured with the specified parameters.

    Raises:
        ValueError: If the specified `engine_type` is not supported or if
                    required engine parameters are missing.
    """
    engine_map = ai_engines.ENGINE_TYPE_TO_CLASS_MAP

    engine_type = engine_config.get("engine_type")
    api_key = engine_config.get("api_key")

    if engine_type not in engine_map:
        raise ValueError(f"Unsupported engine type: {engine_type}")

    engine_class = engine_map[engine_type]
    
    # Pass model_name if it's in engine_config, otherwise it will use the default in the engine class
    model_name = engine_config.get("model_name")
    if model_name:
        engine = engine_class(api_key=api_key, model_name=model_name)
    else:
        engine = engine_class(api_key=api_key)

    bot = Bot(name=bot_name, system_prompt=system_prompt, engine=engine)
    return bot
