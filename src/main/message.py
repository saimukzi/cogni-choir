"""Defines the Message class used for representing chat messages.

This module contains the `Message` class, which encapsulates the sender,
content, and timestamp of a message within the chat application. It provides
methods for string representation, conversion to dictionary for serialization,
and creation from a dictionary for deserialization.
"""
import datetime
# from dataclasses import dataclass

from pydantic import BaseModel

class MessageData(BaseModel):
    """Represents a single message in a chatroom.

    Attributes:
        sender (str): The name of the entity (user or bot) that sent the message.
        content (str): The textual content of the message.
        timestamp (float): The UNIX timestamp indicating when the message was created.
    """
    sender: str
    content: str
    timestamp: float

    def __str__(self) -> str:
        """Returns a string representation of the message, including timestamp, sender, and content."""
        return f"[{datetime.datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')}] {self.sender}: {self.content}"

    def to_display_string(self) -> str:
        """Returns a string suitable for displaying the message in the UI.

        Currently, this is the same as `__str__`.
        """
        # For now, same as __str__. Can be customized later for UI if needed.
        return str(self)

    def to_dict(self) -> dict:
        """Serializes the message to a dictionary.

        Returns:
            A dictionary containing the sender, content, and timestamp of the message.
        """
        return {"sender": self.sender, "content": self.content, "timestamp": self.timestamp}

    @staticmethod
    def from_dict(data: dict) -> 'MessageData':
        """Deserializes a message from a dictionary.

        Args:
            data: A dictionary containing message data with keys "sender",
                  "content", and "timestamp".

        Returns:
            A `Message` instance created from the provided data.
        """
        return MessageData(sender=data["sender"], content=data["content"], timestamp=data["timestamp"])

    def get_content_for_copy(self) -> str:
        """Returns the raw content of the message, suitable for copying."""
        return self.content
