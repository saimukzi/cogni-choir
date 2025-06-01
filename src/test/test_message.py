"""Unit tests for the Message class.

This module tests the creation and representation of Message objects,
including timestamp handling (automatic and manual), string formatting
for display, and conversion to different formats like history tuples.
"""
import unittest
import time
import datetime
import sys
import os

# Adjusting sys.path to allow direct imports of modules in src.main
# This is a common pattern for test files located outside the main package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.main.message import Message

class TestMessage(unittest.TestCase):
    """Tests for the Message class."""
    def test_message_creation_auto_timestamp(self):
        """Tests Message creation with an automatically generated timestamp."""
        sender = "User1"
        content = "Hello, world!"
        before_creation = time.time()
        msg = Message(sender, content)
        after_creation = time.time()

        self.assertEqual(msg.sender, sender)
        self.assertEqual(msg.content, content)
        self.assertIsNotNone(msg.timestamp)
        self.assertTrue(before_creation <= msg.timestamp <= after_creation)

    def test_message_creation_manual_timestamp(self):
        """Tests Message creation with a manually provided timestamp."""
        sender = "User2"
        content = "Another message"
        timestamp = time.time() - 1000  # A specific timestamp
        msg = Message(sender, content, timestamp=timestamp)

        self.assertEqual(msg.sender, sender)
        self.assertEqual(msg.content, content)
        self.assertEqual(msg.timestamp, timestamp)

    def test_message_to_display_string(self):
        """Tests the string representation of a Message for display and __str__."""
        sender = "User3"
        content = "Test display string"
        # Use a fixed timestamp for predictable string output
        fixed_timestamp = datetime.datetime(2023, 1, 1, 12, 0, 0).timestamp()
        msg = Message(sender, content, timestamp=fixed_timestamp)
        
        expected_str = f"[{datetime.datetime.fromtimestamp(fixed_timestamp).strftime('%Y-%m-%d %H:%M:%S')}] {sender}: {content}"
        self.assertEqual(msg.to_display_string(), expected_str)
        self.assertEqual(str(msg), expected_str) # Also test __str__

    def test_message_to_history_tuple(self):
        """Tests the conversion of a Message to a (sender, content) tuple."""
        sender = "User4"
        content = "History tuple test"
        msg = Message(sender, content)
        
        expected_tuple = (sender, content)
        self.assertEqual(msg.to_history_tuple(), expected_tuple)

    def test_message_to_dict(self):
        """Tests the serialization of a Message object to a dictionary."""
        sender = "User5"
        content = "Serialization test"
        fixed_timestamp = datetime.datetime(2023, 1, 2, 10, 30, 0).timestamp()
        msg = Message(sender, content, timestamp=fixed_timestamp)

        expected_dict = {
            "sender": sender,
            "content": content,
            "timestamp": fixed_timestamp
        }
        self.assertEqual(msg.to_dict(), expected_dict)

    def test_message_from_dict(self):
        """Tests the deserialization of a Message object from a dictionary."""
        data = {
            "sender": "User6",
            "content": "Deserialization test",
            "timestamp": datetime.datetime(2023, 1, 3, 11, 20, 10).timestamp()
        }
        msg = Message.from_dict(data)

        self.assertEqual(msg.sender, data["sender"])
        self.assertEqual(msg.content, data["content"])
        self.assertEqual(msg.timestamp, data["timestamp"])

if __name__ == '__main__':
    unittest.main()
