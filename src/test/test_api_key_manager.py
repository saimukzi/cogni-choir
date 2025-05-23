import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json
import io

# Adjusting sys.path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Conditional import for keyring and its errors for environments where it might not be fully functional
try:
    import keyring
    import keyring.errors 
    KEYRING_AVAILABLE = True
except (ImportError, ModuleNotFoundError, OSError) as e: # OSError can happen on some CI environments
    print(f"Keyring not fully available or import failed: {e}. Some keyring-specific tests might be skipped or adapted.", file=sys.stderr)
    KEYRING_AVAILABLE = False
    # Define dummy NoKeyringError if keyring.errors is not available
    class NoKeyringError(Exception): pass
    if 'keyring' in sys.modules and not hasattr(sys.modules['keyring'], 'errors'):
        # Create a dummy errors module on the keyring module
        sys.modules['keyring'].errors = type('keyring_errors_dummy', (object,), {'NoKeyringError': NoKeyringError})
    elif 'keyring' not in sys.modules:
        # Create a dummy keyring module with a dummy errors submodule
        keyring = type('keyring_dummy', (object,), {})
        keyring.errors = type('keyring_errors_dummy', (object,), {'NoKeyringError': NoKeyringError})
        sys.modules['keyring'] = keyring


from src.main.api_key_manager import ApiKeyManager, SERVICE_NAME_PREFIX


class TestApiKeyManager(unittest.TestCase):
    def setUp(self):
        self.test_fallback_dir = os.path.join(os.path.dirname(__file__), "test_data_temp")
        self.test_fallback_file_path = os.path.join(self.test_fallback_dir, "test_api_keys.json")
        
        # Ensure the test fallback directory exists
        os.makedirs(self.test_fallback_dir, exist_ok=True)

        # Clean up any old test file before each test
        if os.path.exists(self.test_fallback_file_path):
            os.remove(self.test_fallback_file_path)

    def tearDown(self):
        # Clean up the test fallback file after each test
        if os.path.exists(self.test_fallback_file_path):
            os.remove(self.test_fallback_file_path)
        # Clean up the test directory
        if os.path.exists(self.test_fallback_dir) and not os.listdir(self.test_fallback_dir):
            os.rmdir(self.test_fallback_dir)
        elif os.path.exists(self.test_fallback_dir) and os.listdir(self.test_fallback_dir):
            # This case should ideally not happen if cleanup is correct
            for f in os.listdir(self.test_fallback_dir): # clean any other potential files created
                os.remove(os.path.join(self.test_fallback_dir, f))
            os.rmdir(self.test_fallback_dir)


    def _get_manager_in_fallback_mode(self) -> ApiKeyManager:
        # This helper method will ensure ApiKeyManager is initialized in fallback mode
        # It patches 'keyring.get_password' to simulate NoKeyringError during __init__
        with patch('keyring.get_password', side_effect=keyring.errors.NoKeyringError if KEYRING_AVAILABLE else NoKeyringError):
            manager = ApiKeyManager()
            manager.fallback_file_path = self.test_fallback_file_path
            # Ensure _ensure_data_dir_exists uses the correct path for tests
            original_data_dir_path = manager.fallback_file_path
            manager.fallback_file_path = self.test_fallback_file_path
            def new_ensure_data_dir_exists():
                if not os.path.exists(os.path.dirname(manager.fallback_file_path)):
                     os.makedirs(os.path.dirname(manager.fallback_file_path))
            manager._ensure_data_dir_exists = new_ensure_data_dir_exists
            manager._keys_cache = manager._load_keys_from_fallback() # Reload with correct path
            return manager

    def test_save_load_delete_key_fallback(self):
        manager = self._get_manager_in_fallback_mode()
        self.assertFalse(manager.use_keyring) # Ensure it's in fallback

        service1 = "TestServiceFallback1"
        key1 = "fallback_key_1"
        service2 = "TestServiceFallback2"
        key2 = "fallback_key_2"

        # Test save and load for service1
        manager.save_key(service1, key1)
        self.assertEqual(manager.load_key(service1), key1)
        self.assertTrue(os.path.exists(self.test_fallback_file_path))
        with open(self.test_fallback_file_path, 'r') as f:
            data = json.load(f)
            self.assertEqual(data[service1], key1)

        # Test save and load for service2
        manager.save_key(service2, key2)
        self.assertEqual(manager.load_key(service2), key2)
        with open(self.test_fallback_file_path, 'r') as f:
            data = json.load(f)
            self.assertEqual(data[service1], key1) # service1 should still be there
            self.assertEqual(data[service2], key2)

        # Test delete for service1
        manager.delete_key(service1)
        self.assertIsNone(manager.load_key(service1))
        with open(self.test_fallback_file_path, 'r') as f:
            data = json.load(f)
            self.assertNotIn(service1, data)
            self.assertEqual(data[service2], key2) # service2 should still be there

        # Test delete for service2
        manager.delete_key(service2)
        self.assertIsNone(manager.load_key(service2))
        # Fallback file might be empty or not exist if all keys deleted, manager doesn't auto-delete file
        if os.path.exists(self.test_fallback_file_path):
            with open(self.test_fallback_file_path, 'r') as f:
                data = json.load(f)
                self.assertNotIn(service2, data)
                self.assertEqual(len(data), 0)


    @unittest.skipIf(not KEYRING_AVAILABLE, "Keyring library not available or functional for this test.")
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('keyring.get_password', side_effect=keyring.errors.NoKeyringError)
    def test_keyring_initialization_message_no_keyring(self, mock_get_password, mock_stderr):
        ApiKeyManager()
        self.assertIn("Failed to initialize keyring. Using fallback JSON file for API keys:", mock_stderr.getvalue())

    @unittest.skipIf(not KEYRING_AVAILABLE, "Keyring library not available or functional for this test.")
    @patch('sys.stderr', new_callable=io.StringIO)
    @patch('keyring.get_password', side_effect=Exception("Some other keyring error")) # Generic Exception
    def test_keyring_initialization_message_other_error(self, mock_get_password, mock_stderr):
        ApiKeyManager()
        self.assertIn("Could not access keyring due to Exception. Using fallback JSON file for API keys:", mock_stderr.getvalue())

    def test_data_directory_creation_fallback(self):
        # Remove the test_fallback_dir to test its creation
        if os.path.exists(self.test_fallback_file_path):
            os.remove(self.test_fallback_file_path)
        if os.path.exists(self.test_fallback_dir):
            os.rmdir(self.test_fallback_dir)
        
        self.assertFalse(os.path.exists(self.test_fallback_dir))

        manager = self._get_manager_in_fallback_mode()
        manager.save_key("TestServiceForDirCreation", "test_key")
        
        self.assertTrue(os.path.exists(self.test_fallback_dir))
        self.assertTrue(os.path.exists(self.test_fallback_file_path))

    @unittest.skipIf(not KEYRING_AVAILABLE, "Keyring library not available or functional for this test.")
    @patch('keyring.set_password')
    @patch('keyring.get_password')
    @patch('keyring.delete_password')
    def test_keyring_mode_operations(self, mock_delete_password, mock_get_password, mock_set_password):
        # Force manager to think keyring is available and working
        with patch.object(ApiKeyManager, '__init__', lambda self: None): # Bypass original __init__
            manager = ApiKeyManager()
            manager.use_keyring = True 
            manager.fallback_file_path = self.test_fallback_file_path # Still set for completeness
            manager._keys_cache = {}


        service_name = "TestKeyringService"
        api_key = "keyring_api_key"
        expected_keyring_servicename = f"{SERVICE_NAME_PREFIX}_{service_name}"

        # Test save_key
        manager.save_key(service_name, api_key)
        mock_set_password.assert_called_once_with(expected_keyring_servicename, service_name, api_key)

        # Test load_key
        mock_get_password.return_value = api_key
        loaded_key = manager.load_key(service_name)
        self.assertEqual(loaded_key, api_key)
        mock_get_password.assert_called_once_with(expected_keyring_servicename, service_name)
        
        # Test delete_key
        manager.delete_key(service_name)
        mock_delete_password.assert_called_once_with(expected_keyring_servicename, service_name)

        # Test load_key after delete (mocking it returns None)
        mock_get_password.reset_mock() # Reset call count
        mock_get_password.return_value = None
        self.assertIsNone(manager.load_key(service_name))
        mock_get_password.assert_called_once_with(expected_keyring_servicename, service_name)

    def test_empty_service_or_key(self):
        manager = self._get_manager_in_fallback_mode() # Fallback mode is fine for this
        with patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            manager.save_key("", "some_key")
            self.assertIn("Service name and API key cannot be empty.", mock_stderr.getvalue())
        
        with patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            manager.save_key("some_service", "")
            self.assertIn("Service name and API key cannot be empty.", mock_stderr.getvalue())

        self.assertIsNone(manager.load_key(""))


if __name__ == '__main__':
    unittest.main()
