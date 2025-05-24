import logging # For logging
from .ai_base import AIEngine # Import AIEngine from its new location
from .ai_engines import GeminiEngine, GrokEngine, OpenAIEngine # Import necessary engine classes
# Removed os, requests, google.generativeai, openai imports as they are now in respective engine files.

# Bot class and create_bot function remain here.
# AIEngine class has been moved to ai_base.py
# Engine-specific classes (GeminiEngine, OpenAIEngine, GrokEngine) are in ai_engines package.

class Bot:
    def __init__(self, name: str, system_prompt: str, engine: AIEngine): # engine will be an instance of a class from ai_engines
        self.logger = logging.getLogger(__name__ + ".Bot")
        self.name = name
        self.system_prompt = system_prompt
        self.engine = engine
        self.logger.debug(f"Bot '{self.name}' created with engine '{type(self.engine).__name__}'.") # DEBUG

    def to_dict(self) -> dict:
        engine_type = type(self.engine).__name__
        model_name = self.engine.model_name if hasattr(self.engine, 'model_name') else None
        
        return {
            "name": self.name,
            "system_prompt": self.system_prompt,
            "engine_type": engine_type,
            "model_name": model_name 
        }

    def get_name(self) -> str:
        return self.name

    def set_name(self, new_name: str):
        self.name = new_name

    def get_system_prompt(self) -> str:
        return self.system_prompt

    def set_system_prompt(self, new_prompt: str):
        self.system_prompt = new_prompt

    def get_engine(self) -> AIEngine:
        return self.engine

    def set_engine(self, new_engine: AIEngine):
        self.engine = new_engine

    def generate_response(self, prompt: str, history: list) -> str:
        self.logger.info(f"Bot '{self.name}' generating response for prompt of length {len(prompt)}.") # INFO
        try:
            response = self.engine.generate_response(prompt, history)
            self.logger.info(f"Bot '{self.name}' successfully generated response.") # INFO
            return response
        except Exception as e:
            self.logger.error(f"Bot '{self.name}' encountered an error during response generation: {e}", exc_info=True) # ERROR
            raise # Re-raise the exception so it can be handled upstream if necessary

ENGINE_TYPE_TO_CLASS_MAP = {
    "GeminiEngine": GeminiEngine,
    "OpenAIEngine": OpenAIEngine,
    "GrokEngine": GrokEngine,
}

def create_bot(bot_name: str, system_prompt: str, engine_config: dict, engine_map: dict = None) -> Bot:
    """
    Creates a Bot instance with the specified configuration.

    Args:
        bot_name: The name of the bot.
        system_prompt: The system prompt for the bot.
        engine_config: A dictionary containing engine configuration.
                       Expected keys: "engine_type" (str), "api_key" (str | None).

    Returns:
        A Bot instance.

    Raises:
        ValueError: If the specified engine_type is not supported.
    """
    if engine_map is None:
        engine_map = ENGINE_TYPE_TO_CLASS_MAP

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
