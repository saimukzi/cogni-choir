import abc
# Removed os, requests, google.generativeai, openai imports as they are now in respective engine files.

# AIEngine and Bot classes remain here.
# Engine-specific classes (GeminiEngine, OpenAIEngine, GrokEngine) have been moved.

class AIEngine(abc.ABC):
    def __init__(self, api_key: str = None, model_name: str = None):
        self.api_key = api_key
        self.model_name = model_name

    @abc.abstractmethod
    def generate_response(self, current_user_prompt: str, conversation_history: list[tuple[str, str]]) -> str:
        pass

class Bot:
    def __init__(self, name: str, system_prompt: str, engine: AIEngine): # engine will be an instance of a class from ai_engines
        self.name = name
        self.system_prompt = system_prompt
        self.engine = engine

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
        return self.engine.generate_response(prompt, history)
