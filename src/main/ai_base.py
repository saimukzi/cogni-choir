import abc

class AIEngine(abc.ABC):
    def __init__(self, api_key: str = None, model_name: str = None):
        self.api_key = api_key
        self.model_name = model_name

    @abc.abstractmethod
    def generate_response(self, current_user_prompt: str, conversation_history: list[tuple[str, str]]) -> str:
        pass

    @abc.abstractmethod
    def requires_api_key(self) -> bool:
        pass
