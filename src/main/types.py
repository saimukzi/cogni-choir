"""
Defines custom types for the application, primarily focusing on conversation management.
"""

from typing import List, Dict, Optional

class ChatMessage:
    """
    Represents a single message in a conversation.

    Attributes:
        role (str): The role of the entity that produced the message (e.g., "User", "Bot", "System").
        text (str): The textual content of the message.
    """
    def __init__(self, role: str, text: str):
        """
        Initializes a ChatMessage instance.

        Args:
            role: The role of the speaker (e.g., "User", "Bot").
            text: The content of the message.
        """
        self.role = role
        self.text = text

    def to_dict(self) -> Dict[str, str]:
        """
        Converts the ChatMessage instance to a dictionary.

        Returns:
            A dictionary representation of the message with "role" and "text" keys.
        """
        return {"role": self.role, "text": self.text}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'ChatMessage':
        """
        Creates a new ChatMessage instance from a dictionary.

        Args:
            data: A dictionary with "role" and "text" keys.

        Returns:
            A new ChatMessage instance.
        
        Raises:
            KeyError: If "role" or "text" is missing from the input dictionary.
        """
        if "role" not in data or "text" not in data:
            raise KeyError("Input dictionary must contain 'role' and 'text' keys.")
        return cls(role=data["role"], text=data["text"])

    def __str__(self) -> str:
        """
        Returns a user-friendly string representation of the message.

        Formats the message as "Role: Text". The role is capitalized.

        Returns:
            A string representation of the message.
        """
        return f"{self.role.capitalize()}: {self.text}"

    def __repr__(self) -> str:
        """
        Returns an unambiguous string representation of the ChatMessage object.

        Returns:
            A string that can ideally be used to recreate the object.
        """
        return f"ChatMessage(role='{self.role}', text={repr(self.text)})"


class ConversationHistory:
    """
    Manages a history of conversation messages.

    Internally, it stores messages as ChatMessage objects.
    Provides methods to add messages, convert to/from list of dictionaries
    (for external compatibility), and generate a user-friendly string representation.
    """

    def __init__(self, initial_history: Optional[List[Dict[str, str]]] = None):
        """
        Initializes the ConversationHistory.

        Args:
            initial_history: An optional list of message dictionaries to
                             initialize the conversation history. Each dictionary
                             should have "role" (str) and "text" (str) keys.
                             These dictionaries are converted to ChatMessage objects internally.
        """
        self._history: List[ChatMessage] = []
        if initial_history:
            for item in initial_history:
                try:
                    self._history.append(ChatMessage.from_dict(item))
                except KeyError as e:
                    # Handle cases where a dictionary in initial_history might be malformed
                    # For example, log a warning or skip the message
                    print(f"Warning: Skipping message due to missing keys in initial_history: {item} - Error: {e}")


    def add_message(self, role: str, text: str) -> None:
        """
        Adds a new message to the conversation history.

        Args:
            role: The role of the speaker (e.g., "User", "Bot").
            text: The content of the message.
        """
        self._history.append(ChatMessage(role=role, text=text))

    def to_list_dict(self) -> List[Dict[str, str]]:
        """
        Returns a list of message dictionaries from the internal ChatMessage objects.

        This ensures that the internal history (of ChatMessage objects) is not
        exposed directly and provides a serializable format.

        Returns:
            A new list of dictionaries, where each dictionary represents a message
            with "role" and "text" keys.
        """
        return [message.to_dict() for message in self._history]

    @classmethod
    def from_list_dict(cls, data: List[Dict[str, str]]) -> 'ConversationHistory':
        """
        Creates a new ConversationHistory instance from a list of message dictionaries.

        Args:
            data: A list of dictionaries, where each dictionary represents a
                  message with "role" and "text" keys.

        Returns:
            A new ConversationHistory instance populated with the provided data.
        """
        return cls(initial_history=data)

    def __str__(self) -> str:
        """
        Returns a user-friendly string representation of the conversation history.

        Each message is formatted as "Role: Text" on a new line, using the
        __str__ method of ChatMessage.

        Returns:
            A string representing the conversation history.
        """
        if not self._history:
            return "Conversation history is empty."
        
        # Each 'message' in self._history is now a ChatMessage object.
        # We can directly use its __str__() representation or access attributes.
        # Using message.__str__() directly leverages ChatMessage's formatting.
        formatted_messages: List[str] = [str(message) for message in self._history]
        return "\n".join(formatted_messages)

if __name__ == '__main__':
    # Example Usage (for testing purposes)
    print("Starting example usage for custom types...")

    # --- ChatMessage Example Usage ---
    print("\n--- ChatMessage Examples ---")
    msg1 = ChatMessage(role="User", text="Hello there!")
    print(f"Message 1: {msg1}")
    print(f"Message 1 (repr): {repr(msg1)}")
    msg1_dict = msg1.to_dict()
    print(f"Message 1 (dict): {msg1_dict}")

    msg2_data = {"role": "Bot", "text": "Hi User!"}
    msg2 = ChatMessage.from_dict(msg2_data)
    print(f"Message 2 (from dict): {msg2}")
    
    try:
        ChatMessage.from_dict({"role": "System"}) # Missing text
    except KeyError as e:
        print(f"Caught expected error for ChatMessage.from_dict: {e}")

    # --- ConversationHistory Example Usage ---
    print("\n--- ConversationHistory Examples ---")
    # Test initialization
    history1 = ConversationHistory()
    print(f"Empty history: {history1}")

    history1.add_message("User", "Hello")
    history1.add_message("Bot", "Hi there!")
    print(f"\nAfter adding messages:\n{history1}")

    # Test to_list_dict
    list_dict_representation = history1.to_list_dict()
    print(f"\nList dict representation: {list_dict_representation}")

    # Test from_list_dict
    initial_data = [
        {"role": "User", "text": "Good morning"},
        {"role": "Bot", "text": "Good morning! How can I help you today?"}
    ]
    history2 = ConversationHistory.from_list_dict(initial_data)
    print(f"\nHistory created from list_dict:\n{history2}")

    history2.add_message("User", "I need help with my account.")
    print(f"\nAfter adding another message to history2:\n{history2}")

    # Test __str__ with an empty history again (new instance)
    history3 = ConversationHistory()
    print(f"\nString representation of a new empty history: {history3}")
    
    # Test __str__ with one message
    history4 = ConversationHistory()
    history4.add_message("System", "Session started.")
    print(f"\nHistory with one message:\n{history4}")

    print("\nExample usage finished.")
