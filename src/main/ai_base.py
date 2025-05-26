"""This module defines the abstract base class for AI engines."""
import abc
from src.main.message import Message

class AIEngine(abc.ABC):
    """Abstract base class for AI engines.

    This class defines the interface for AI engines that can be used to generate
    responses to user prompts.
    """
    def __init__(self, api_key: str = None, model_name: str = None):
        """Initializes a new instance of the AIEngine class.

        Args:
            api_key: The API key for the AI engine.
            model_name: The name of the model to use.
        """
        self.api_key = api_key
        self.model_name = model_name

    @abc.abstractmethod
    def generate_response(self, role_name: str, system_prompt: str, conversation_history: list[Message]) -> str:
        """Generates a response from the AI engine.

        Args:
            role_name: The name of the role for the AI.
            system_prompt: The system prompt to use.
            conversation_history: A Message list representing the
                                  current conversation.

        Returns:
            The response from the AI engine.
        """
        pass

    @abc.abstractmethod
    def requires_api_key(self) -> bool:
        """Returns whether the AI engine requires an API key.

        Returns:
            True if the AI engine requires an API key, False otherwise.
        """
        pass
