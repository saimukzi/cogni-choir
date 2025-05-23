import time
import datetime

class Message:
    def __init__(self, sender: str, content: str, timestamp: float = None):
        self.sender = sender
        self.content = content
        if timestamp is None:
            self.timestamp = time.time()
        else:
            self.timestamp = timestamp

    def __str__(self) -> str:
        return f"[{datetime.datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')}] {self.sender}: {self.content}"

    def to_display_string(self) -> str:
        # For now, same as __str__. Can be customized later for UI if needed.
        return str(self)

    def to_history_tuple(self) -> tuple[str, str]:
        """Returns a tuple representation for AI history."""
        return (self.sender, self.content)

    def to_dict(self) -> dict:
        return {"sender": self.sender, "content": self.content, "timestamp": self.timestamp}

    @staticmethod
    def from_dict(data: dict) -> 'Message':
        return Message(sender=data["sender"], content=data["content"], timestamp=data["timestamp"])
