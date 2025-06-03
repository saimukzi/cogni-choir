"""Abstract base classes and data classes for third-party integrations.

This module defines the structure for integrating various third-party AI services.
It includes:
- `ApiKeeySlotInfo`: Describes an API key slot required by a third-party service.
- `AIEngineArgInfo`: Describes an argument for a specific AI engine.
- `AIEngineInfo`: Describes a specific AI engine provided by a third-party.
- `ThirdPartyBase`: An abstract base class that all third-party integration
  classes must inherit from. It defines the interface for providing API key
  information, AI engine details, and response generation.
- `ThirdPartyGroup`: Manages a collection of `ThirdPartyBase` instances.
"""
import abc
import logging
from enum import Enum

from .message import Message

class ApiKeeySlotInfo:
    """Information about an API key slot for a third-party service.

    Attributes:
        apikeey_slot_id (str): A unique identifier for this API key slot (e.g., "OPENAI_API_KEY").
        name (str): A user-friendly name for this API key slot (e.g., "OpenAI API Key").
    """
    def __init__(self, apikeey_slot_id: str, name: str):
        """Initializes ApiKeeySlotInfo.

        Args:
            apikeey_slot_id (str): Unique identifier for the API key slot.
            name (str): Name of the API key slot.
        """
        self.apikeey_slot_id = apikeey_slot_id
        self.name = name

    def __repr__(self):
        """Returns a string representation of the ApiKeeySlotInfo instance."""
        return f"ApiKeeySlotInfo(apikeey_slot_id={self.apikeey_slot_id}, name={self.name})"


class AIEngineArgType(Enum):
    """Enumeration for different types of AI engine arguments."""

    SINGLE_LINE = "single_line" # Represents a single line of text input.
    MULTI_LINE = "multi_line"   # Represents multiple lines of text input.
    SELECTION = "selection"     # Represents a selection from a predefined list of options.
    SUGGESTION = "suggestion"   # Represents a suggestion input, where the user can type and receive suggestions.

    def __str__(self):
        """Returns the string representation of the enum value."""
        return self.value


class AIEngineArgInfo:
    """Information about an argument for an AI engine.

    Attributes:
        arg_id (str): The unique identifier for the argument (e.g., "model_name").
        name (str): A user-friendly name for the argument (e.g., "Model Name").
        required (bool): True if the argument is required, False otherwise.
        default_value (Optional[str]): The default value for the argument, if any.
        value_options (Optional[list[str]]): A list of possible valid string
            values for the argument, if applicable.
    """
    def __init__(self, arg_id: str, name:str, required: bool, arg_type:AIEngineArgType = AIEngineArgType.SINGLE_LINE, default_value: str = None, value_option_list: list[str] = None):
        """Initializes AIEngineArgInfo.

        Args:
            arg_id (str): The id of the argument.
            name (str): The display name of the argument.
            required (bool): Indicates whether the argument is required.
            default_value (str, optional): The default value for the argument. Defaults to None.
            arg_type (AIEngineArgType, optional): The type of the argument.
            value_option_list (list[str], optional): A list of valid options for the argument, if applicable.
        """
        self.arg_id = arg_id
        self.name = name
        self.required = required
        self.arg_type = arg_type
        self.default_value = default_value
        self.value_option_list = value_option_list


class AIEngineInfo:
    """Information about a specific AI engine provided by a third party.

    Attributes:
        aiengine_id (str): A unique identifier for this AI engine (e.g., "OPENAI_GPT4").
        name (str): A user-friendly name for the AI engine (e.g., "OpenAI GPT-4").
        apikeey_slot_id_list (list[str]): A list of `apikeey_slot_id` strings
            that this engine requires. These IDs should correspond to `ApiKeeySlotInfo`
            instances.
        arg_list (list[AIEngineArgInfo]): A list of `AIEngineArgInfo` objects
            describing the arguments this engine accepts or requires.
    """
    def __init__(self, aiengine_id: str, name: str, apikeey_slot_id_list: list[str], arg_list: list[AIEngineArgInfo]):
        """Initializes AIEngineInfo.

        Args:
            aiengine_id (str): Unique identifier for the AI engine.
            name (str): Name of the AI engine.
            apikeey_slot_id_list (list[str]): List of API key slot IDs associated with this engine.
            arg_list (list[AIEngineArgInfo]): List of additional arguments or configurations for the engine.
        """
        self.aiengine_id = aiengine_id
        self.name = name
        self.apikeey_slot_id_list = apikeey_slot_id_list
        self.arg_list = arg_list

    def get_aiengine_arg_info(self, arg_id: str) -> AIEngineArgInfo | None:
        """Retrieves the AIEngineArgInfo for a given argument ID.

        Args:
            arg_id (str): The ID of the argument to retrieve.

        Returns:
            Optional[AIEngineArgInfo]: The argument information if found,
                otherwise None.
        """
        for arg_info in self.arg_list:
            if arg_info.arg_id == arg_id:
                return arg_info
        return None


class ThirdPartyBase(abc.ABC):
    """Abstract base class for third-party AI service integrations.

    Subclasses must implement methods to provide information about required API
    keys, available AI engines, and to generate responses from those engines.

    Attributes:
        thirdparty_id (str): A unique identifier for the third-party service
                             (e.g., "OPENAI", "ANTHROPIC").
    """
    def __init__(self, thirdparty_id: str):
        """Initializes ThirdPartyBase.

        Args:
            thirdparty_id (str): Unique identifier for the third-party service.
        """
        self.thirdparty_id = thirdparty_id

    @abc.abstractmethod
    def get_apikeey_slot_info_list(self) -> list[ApiKeeySlotInfo]:
        """
        Returns a list of API key information for the third-party service.

        This method should be overridden by subclasses to provide specific
        API key details.

        Returns:
            list: A list of API key information strings.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    @abc.abstractmethod
    def get_aiengine_info_list(self) -> list[AIEngineInfo]:
        """
        Returns a list of AI engine information for the third-party service.

        This method should be overridden by subclasses to provide specific
        AI engine details.

        Returns:
            list: A list of AI engine information strings.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    @abc.abstractmethod
    def generate_response(self, aiengine_id:str, aiengine_arg_dict:dict[str,str], apikeey_list:list[str], role_name: str, conversation_history: list[Message]) -> str:
        """
        Generates a response from the AI engine.

        Args:
            aiengine_id (str): The ID of the AI engine to use.
            aiengine_args (dict[str,str]): Arguments for the AI engine.
            apikeey_list (list[str]): List of API keys to use for authentication.
            role_name (str): The name of the role for the AI.
            conversation_history (list[Message]): A list of Message objects representing the current conversation.

        Returns:
            str: The response from the AI engine.
        """
        raise NotImplementedError("Subclasses must implement this method.")


class ThirdPartyGroup:
    """
    A group of third-party services.

    This class is used to manage a collection of third-party services, allowing
    for easy access and management of their API keys and AI engine information.
    """

    def __init__(self, third_party_classes: list[type[ThirdPartyBase]]):
        """
        Initializes a new instance of the ThirdPartyGroup class.

        Args:
            third_party_classes (list[type[ThirdPartyBase]]): A list of classes that extend ThirdPartyBase.
        """
        self._logger = logging.getLogger(__name__)

        self.third_party_classes = third_party_classes

        self._third_party_list:list[ThirdPartyBase] = [cls() for cls in self.third_party_classes]

        self.apikeey_slot_info_list: list[ApiKeeySlotInfo] = []
        for third_party in self._third_party_list:
            self._logger.info(f"Loading API key slot info from {third_party.thirdparty_id}.")
            self.apikeey_slot_info_list.extend(third_party.get_apikeey_slot_info_list())

        # self.aiengine_id_to_apikeey_slot_info_dict: dict[str,ApiKeeySlotInfo] = {}
        # for third_party in self._third_party_list:
        #     for apikeey_slot_info in third_party.get_apikeey_slot_info_list():
        #         assert(apikeey_slot_info.apikeey_slot_id not in self.aiengine_id_to_apikeey_slot_info_dict), \
        #             f"Duplicate API key slot ID found: {apikeey_slot_info.apikeey_slot_id} in {third_party.thirdparty_id}."
        #         self.aiengine_id_to_apikeey_slot_info_dict[apikeey_slot_info.apikeey_slot_id] = apikeey_slot_info

        self.aiengine_info_list: list[AIEngineInfo] = []
        for third_party in self._third_party_list:
            self._logger.info(f"Loading AI engines from {third_party.thirdparty_id}.")
            self.aiengine_info_list.extend(third_party.get_aiengine_info_list())

        # self.aiengine_id_to_aiengine_info_dict: dict[str, AIEngineInfo] = {}
        # for third_party in self._third_party_list:
        #     for aiengine_info in third_party.get_aiengine_info_list():
        #         assert(aiengine_info.aiengine_id not in self.aiengine_id_to_aiengine_info_dict), \
        #             f"Duplicate AI engine ID found: {aiengine_info.aiengine_id} in {third_party.thirdparty_id}."
        #         self.aiengine_id_to_aiengine_info_dict[aiengine_info.aiengine_id] = aiengine_info

        self.aiengine_id_to_thirdparty_dict: dict[str, ThirdPartyBase] = {}
        for third_party in self._third_party_list:
            for aiengine_info in third_party.get_aiengine_info_list():
                self.aiengine_id_to_thirdparty_dict[aiengine_info.aiengine_id] = third_party

    def generate_response(self,
                          aiengine_id:str,
                          aiengine_arg_dict:dict[str,str],
                          apikeey_list:list[str],
                          role_name: str,
                          conversation_history: list[Message]
                          ) -> str:
        """
        Generates a response from the specified AI engine.
        Args:
            aiengine_id (str): The ID of the AI engine to use.
            aiengine_arg_dict (dict[str,str]): Arguments for the AI engine.
            apikeey_list (list[str]): List of API keys to use for authentication.
            role_name (str): The name of the role for the AI.
            conversation_history (list[Message]): A list of Message objects representing the current conversation.
        Returns:
            str: The response from the AI engine.
        """
        if aiengine_id not in self.aiengine_id_to_thirdparty_dict:
            raise ValueError(f"AI engine ID {aiengine_id} not found in third-party services.")
        third_party = self.aiengine_id_to_thirdparty_dict[aiengine_id]
        self._logger.info(f"Generating response using AI engine {aiengine_id} from {third_party.thirdparty_id}.")
        return third_party.generate_response(aiengine_id, aiengine_arg_dict, apikeey_list, role_name, conversation_history)
