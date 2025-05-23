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
    def test_message_creation_auto_timestamp(self):
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
        sender = "User2"
        content = "Another message"
        timestamp = time.time() - 1000  # A specific timestamp
        msg = Message(sender, content, timestamp=timestamp)

        self.assertEqual(msg.sender, sender)
        self.assertEqual(msg.content, content)
        self.assertEqual(msg.timestamp, timestamp)

    def test_message_to_display_string(self):
        sender = "User3"
        content = "Test display string"
        # Use a fixed timestamp for predictable string output
        fixed_timestamp = datetime.datetime(2023, 1, 1, 12, 0, 0).timestamp()
        msg = Message(sender, content, timestamp=fixed_timestamp)
        
        expected_str = f"[{datetime.datetime.fromtimestamp(fixed_timestamp).strftime('%Y-%m-%d %H:%M:%S')}] {sender}: {content}"
        self.assertEqual(msg.to_display_string(), expected_str)
        self.assertEqual(str(msg), expected_str) # Also test __str__

    def test_message_to_history_tuple(self):
        sender = "User4"
        content = "History tuple test"
        msg = Message(sender, content)
        
        expected_tuple = (sender, content)
        self.assertEqual(msg.to_history_tuple(), expected_tuple)

if __name__ == '__main__':
    unittest.main()
