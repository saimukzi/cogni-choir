import unittest
from src.main.types import ConversationHistory, ChatMessage # Added ChatMessage

class TestChatMessage(unittest.TestCase):
    def test_initialization(self):
        """Test ChatMessage initialization."""
        msg = ChatMessage(role="User", text="Hello")
        self.assertEqual(msg.role, "User")
        self.assertEqual(msg.text, "Hello")

    def test_to_dict(self):
        """Test ChatMessage to_dict method."""
        msg = ChatMessage(role="Bot", text="Hi there")
        expected_dict = {"role": "Bot", "text": "Hi there"}
        self.assertEqual(msg.to_dict(), expected_dict)

    def test_from_dict_success(self):
        """Test ChatMessage from_dict class method for successful creation."""
        data = {"role": "System", "text": "System ready"}
        msg = ChatMessage.from_dict(data)
        self.assertIsInstance(msg, ChatMessage)
        self.assertEqual(msg.role, "System")
        self.assertEqual(msg.text, "System ready")

    def test_from_dict_missing_keys(self):
        """Test ChatMessage from_dict raises KeyError for missing keys."""
        expected_error_msg = "Input dictionary must contain 'role' and 'text' keys."
        with self.assertRaisesRegex(KeyError, expected_error_msg):
            ChatMessage.from_dict({"role": "User"})  # Missing 'text'
        
        with self.assertRaisesRegex(KeyError, expected_error_msg):
            ChatMessage.from_dict({"text": "Hello"})  # Missing 'role'

        with self.assertRaisesRegex(KeyError, expected_error_msg):
            ChatMessage.from_dict({}) # Missing both

    def test_str_representation(self):
        """Test ChatMessage __str__ method."""
        msg = ChatMessage(role="User", text="Test message")
        self.assertEqual(str(msg), "User: Test message")
        
        msg_lower_role = ChatMessage(role="bot", text="Another test")
        self.assertEqual(str(msg_lower_role), "Bot: Another test") # Role should be capitalized

    def test_repr_representation(self):
        """Test ChatMessage __repr__ method."""
        msg = ChatMessage(role="User", text="Hello")
        expected_repr = "ChatMessage(role='User', text='Hello')" # repr of "Hello" is 'Hello'
        self.assertEqual(repr(msg), expected_repr)

        text_with_quotes = "Text with 'quotes'"
        msg_with_quotes = ChatMessage(role="System", text=text_with_quotes)
        # repr(text_with_quotes) will be "'Text with \\'quotes\\''"
        # So the full repr should be ChatMessage(role='System', text='Text with \'quotes\'')
        expected_repr_quotes = f"ChatMessage(role='System', text={repr(text_with_quotes)})"
        self.assertEqual(repr(msg_with_quotes), expected_repr_quotes)


class TestConversationHistory(unittest.TestCase):

    def test_initialization_empty(self):
        """Test empty initialization."""
        ch = ConversationHistory()
        self.assertEqual(ch.to_list_dict(), [])
        self.assertEqual(str(ch), "Conversation history is empty.")

    def test_initialization_with_history(self):
        """Test initialization with a pre-existing history."""
        initial_data = [
            {"role": "User", "text": "Hello"},
            {"role": "Bot", "text": "Hi there!"}
        ]
        ch = ConversationHistory(initial_data)
        self.assertEqual(ch.to_list_dict(), initial_data)
        # Ensure the internal list is a copy, not the same object
        self.assertIsNot(ch.to_list_dict(), initial_data) 

    def test_add_message(self):
        """Test adding messages."""
        ch = ConversationHistory()
        ch.add_message("User", "First message")
        expected_history1 = [{"role": "User", "text": "First message"}]
        self.assertEqual(ch.to_list_dict(), expected_history1)

        ch.add_message("Bot", "Second message")
        expected_history2 = [
            {"role": "User", "text": "First message"},
            {"role": "Bot", "text": "Second message"}
        ]
        self.assertEqual(ch.to_list_dict(), expected_history2)

    def test_to_list_dict_returns_copy(self):
        """Test that to_list_dict returns a copy, not a reference."""
        initial_data = [{"role": "User", "text": "Test"}]
        ch = ConversationHistory(initial_data)
        
        list_dict_1 = ch.to_list_dict()
        list_dict_2 = ch.to_list_dict()
        
        self.assertEqual(list_dict_1, list_dict_2)
        self.assertIsNot(list_dict_1, list_dict_2, "to_list_dict should return a new list object each time.")
        
        # Also check modification of the returned list doesn't affect internal history
        list_dict_1.append({"role": "Attempt", "text": "To Modify"})
        self.assertEqual(ch.to_list_dict(), initial_data, "Modifying returned list should not affect internal history.")

    def test_from_list_dict(self):
        """Test creating an instance using from_list_dict."""
        data = [
            {"role": "System", "text": "System Ready"},
            {"role": "User", "text": "User query"}
        ]
        ch = ConversationHistory.from_list_dict(data)
        self.assertIsInstance(ch, ConversationHistory)
        self.assertEqual(ch.to_list_dict(), data)
        # Ensure the internal list is a copy
        internal_list = ch.to_list_dict()
        self.assertIsNot(internal_list, data)


    def test_str_representation_empty(self):
        """Test string representation for an empty history."""
        ch = ConversationHistory()
        self.assertEqual(str(ch), "Conversation history is empty.")

    def test_str_representation_with_messages(self):
        """Test string representation with messages."""
        ch = ConversationHistory()
        ch.add_message("User", "Hello Bot")
        ch.add_message("Bot", "Hello User")
        ch.add_message("user", "how are you?") # Test lowercase role
        
        expected_str = "User: Hello Bot\nBot: Hello User\nUser: how are you?"
        self.assertEqual(str(ch), expected_str)

    def test_str_representation_missing_keys(self):
        """Test string representation when messages have missing keys."""
        # This scenario should ideally not happen if add_message is used,
        # but from_list_dict could allow it.
        # Since ChatMessage.from_dict now strictly requires 'role' and 'text',
        # ConversationHistory.__init__ will skip messages with missing keys from initial_history.
        
        data_with_missing_role = [{"text": "Just text"}] # 'role' is missing
        ch_missing_role = ConversationHistory.from_list_dict(data_with_missing_role)
        # Expect empty history because the malformed message is skipped.
        self.assertEqual(str(ch_missing_role), "Conversation history is empty.")

        data_with_missing_text = [{"role": "User"}] # 'text' is missing
        ch_missing_text = ConversationHistory.from_list_dict(data_with_missing_text)
        # Expect empty history because the malformed message is skipped.
        self.assertEqual(str(ch_missing_text), "Conversation history is empty.")
        
        data_with_both_missing = [{}] # 'role' and 'text' are missing
        ch_both_missing = ConversationHistory.from_list_dict(data_with_both_missing)
        # Expect empty history because the malformed message is skipped.
        self.assertEqual(str(ch_both_missing), "Conversation history is empty.")

if __name__ == '__main__':
    unittest.main()
