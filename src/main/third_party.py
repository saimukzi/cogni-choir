import abc
import logging

from .message import Message

class ApiKeySlotInfo:

    def __init__(self, apikey_slot_id: str, name: str):
        """
        Initializes a new instance of the ApiKeySlot class.
        Args:
            apikey_slot_id (str): Unique identifier for the API key slot.
            name (str): Name of the API key slot.
        """
        self.apikey_slot_id = apikey_slot_id
        self.name = name

    def __repr__(self):
        return f"ApiKeySlotInfo(apikey_slot_id={self.apikey_slot_id}, name={self.name})"


class AIEngineArgInfo:
    def __init__(self, arg_id: str, name:str, required: bool, default_value: str = None, value_options: list[str] = None):
        """
        Initializes a new instance of the AIEngineArgInfo class.

        Args:
            arg_id (str): The id of the argument.
            name (str): The display name of the argument.
            required (bool): Indicates whether the argument is required.
            default_value (str, optional): The default value for the argument. Defaults to None.
            value_options (list[str], optional): A list of valid options for the argument value. Defaults to None.
        """
        self.arg_id = arg_id
        self.name = name
        self.required = required
        self.default_value = default_value
        self.value_options = value_options


class AIEngineInfo:

    def __init__(self, aiengine_id: str, name: str, apikey_slot_id_list: list[str], arg_list: list[AIEngineArgInfo]):
        """
        Initializes a new instance of the AIEngineInfo class.
        Args:
            aiengine_id (str): Unique identifier for the AI engine.
            name (str): Name of the AI engine.
            apikey_slot_id_list (list[str]): List of API key slot IDs associated with this engine.
            arg_list (list[AIEngineArgInfo]): List of additional arguments or configurations for the engine.
        """
        self.aiengine_id = aiengine_id
        self.name = name
        self.apikey_slot_id_list = apikey_slot_id_list
        self.arg_list = arg_list

    def get_aiengine_arg_info(self, arg_id: str) -> AIEngineArgInfo | None:
        """
        Retrieves the AI engine argument information by its ID.

        Args:
            arg_id (str): The ID of the argument to retrieve.

        Returns:
            AIEngineArgInfo | None: The argument information if found, otherwise None.
        """
        for arg_info in self.arg_list:
            if arg_info.arg_id == arg_id:
                return arg_info
        return None


class ThirdPartyBase(abc.ABC):

    def __init__(self, thirdparty_id: str):
        self.thirdparty_id = thirdparty_id

    @abc.abstractmethod
    def get_apikey_slot_info_list(self) -> list[ApiKeySlotInfo]:
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
    def generate_response(self, aiengine_id:str, aiengine_arg_dict:dict[str,str], apikey_list:list[str], role_name: str, conversation_history: list[Message]) -> str:
        """
        Generates a response from the AI engine.

        Args:
            aiengine_id (str): The ID of the AI engine to use.
            aiengine_args (dict[str,str]): Arguments for the AI engine.
            apikey_list (list[str]): List of API keys to use for authentication.
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

        self.apikey_slot_info_list: list[ApiKeySlotInfo] = []
        for third_party in self._third_party_list:
            self._logger.info(f"Loading API key slot info from {third_party.thirdparty_id}.")
            self.apikey_slot_info_list.extend(third_party.get_apikey_slot_info_list())

        # self.aiengine_id_to_apikey_slot_info_dict: dict[str,ApiKeySlotInfo] = {}
        # for third_party in self._third_party_list:
        #     for apikey_slot_info in third_party.get_apikey_slot_info_list():
        #         assert(apikey_slot_info.apikey_slot_id not in self.aiengine_id_to_apikey_slot_info_dict), \
        #             f"Duplicate API key slot ID found: {apikey_slot_info.apikey_slot_id} in {third_party.thirdparty_id}."
        #         self.aiengine_id_to_apikey_slot_info_dict[apikey_slot_info.apikey_slot_id] = apikey_slot_info

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
                          apikey_list:list[str],
                          role_name: str,
                          conversation_history: list[Message]
                          ) -> str:
        """
        Generates a response from the specified AI engine.
        Args:
            aiengine_id (str): The ID of the AI engine to use.
            aiengine_arg_dict (dict[str,str]): Arguments for the AI engine.
            apikey_list (list[str]): List of API keys to use for authentication.
            role_name (str): The name of the role for the AI.
            conversation_history (list[Message]): A list of Message objects representing the current conversation.
        Returns:
            str: The response from the AI engine.
        """
        if aiengine_id not in self.aiengine_id_to_thirdparty_dict:
            raise ValueError(f"AI engine ID {aiengine_id} not found in third-party services.")
        third_party = self.aiengine_id_to_thirdparty_dict[aiengine_id]
        self._logger.info(f"Generating response using AI engine {aiengine_id} from {third_party.thirdparty_id}.")
        return third_party.generate_response(aiengine_id, aiengine_arg_dict, apikey_list, role_name, conversation_history)
