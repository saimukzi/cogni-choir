import unittest
from unittest.mock import patch, MagicMock
import json

# Adjust import paths as necessary
from src.main import api_server
from src.main.ccapikey_manager import CcApiKeyManager
from src.main.encryption_service import EncryptionService # Or your MockEncryptionService if preferred

# If using the MockEncryptionService from the other test file, ensure it's accessible
# from src.test.test_ccapikey_manager import MockEncryptionService
# For simplicity here, we might just use MagicMock for EncryptionService if its methods aren't called.

class TestApiServer(unittest.TestCase):
    """Test suite for the Flask API server endpoints."""

    def setUp(self):
        """Set up for each test case."""
        # Create a test client for the Flask app
        api_server.api_app.testing = True
        self.client = api_server.api_app.test_client()

        # Mock CcApiKeyManager
        self.mock_cc_api_key_manager = MagicMock(spec=CcApiKeyManager)

        # Mock EncryptionService (can be a simple MagicMock if not deeply used by API server itself)
        self.mock_encryption_service = MagicMock(spec=EncryptionService)

        # Store original manager for teardown
        self.original_cc_api_key_manager = api_server.cc_api_key_manager

        # Initialize API server dependencies with mocks
        api_server.initialize_api_server_dependencies(
            cc_manager=self.mock_cc_api_key_manager,
            enc_service=self.mock_encryption_service
        )

    def tearDown(self):
        """Clean up after each test."""
        # Restore original dependencies if they were changed globally
        api_server.cc_api_key_manager = self.original_cc_api_key_manager
        # Reset other global states if necessary

    def test_hello_no_api_key_header(self):
        """Test /hello endpoint without providing an API key header."""
        response = self.client.get('/hello')
        self.assertEqual(response.status_code, 401)
        json_data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(json_data, {"error": "API key required"})

    def test_hello_invalid_api_key(self):
        """Test /hello endpoint with an invalid/unknown API key."""
        # Configure mock CcApiKeyManager:
        # list_key_names returns some names, but get_key for those names
        # will return values that don't match the provided_invalid_key.
        # Or, more simply, make list_key_names return an empty list,
        # or make get_key always return None or a non-matching value.

        self.mock_cc_api_key_manager.list_key_names.return_value = ["valid_key_name_1"]
        self.mock_cc_api_key_manager.get_key.return_value = "actual_stored_valid_key_value"

        provided_invalid_key = "this_is_an_invalid_key"
        headers = {"CcApiKey": provided_invalid_key}
        response = self.client.get('/hello', headers=headers)

        self.assertEqual(response.status_code, 403)
        json_data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(json_data, {"error": "Invalid API key"})

    def test_hello_valid_api_key(self):
        """Test /hello endpoint with a valid API key."""
        valid_key_value = "my_secret_cc_api_key_value"

        # Configure mock CcApiKeyManager:
        # list_key_names should return at least one key name.
        # get_key, when called with that name, should return valid_key_value.
        self.mock_cc_api_key_manager.list_key_names.return_value = ["sample_key_name"]
        self.mock_cc_api_key_manager.get_key.side_effect = lambda name: valid_key_value if name == "sample_key_name" else None

        headers = {"CcApiKey": valid_key_value}
        response = self.client.get('/hello', headers=headers)

        self.assertEqual(response.status_code, 200)
        json_data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(json_data, {"message": "hello, authenticated user!"})

    def test_hello_valid_api_key_lowercase_header(self):
        """Test /hello endpoint with a valid API key using lowercase 'ccapikey' header."""
        valid_key_value = "my_secret_cc_api_key_value_lowercase"
        self.mock_cc_api_key_manager.list_key_names.return_value = ["another_key_name"]
        self.mock_cc_api_key_manager.get_key.side_effect = lambda name: valid_key_value if name == "another_key_name" else None

        headers = {"ccapikey": valid_key_value} # Lowercase header
        response = self.client.get('/hello', headers=headers)

        self.assertEqual(response.status_code, 200)
        json_data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(json_data, {"message": "hello, authenticated user!"})

    def test_hello_api_key_manager_not_initialized(self):
        """Test /hello when cc_api_key_manager is None (not initialized)."""
        # Temporarily set the global manager to None for this test
        original_manager = api_server.cc_api_key_manager
        api_server.cc_api_key_manager = None

        try:
            headers = {"CcApiKey": "any_key_value"}
            response = self.client.get('/hello', headers=headers)
            self.assertEqual(response.status_code, 500)
            json_data = json.loads(response.data.decode('utf-8'))
            self.assertEqual(json_data, {"error": "API key manager not initialized"})
        finally:
            # Restore the original manager to avoid affecting other tests
            api_server.cc_api_key_manager = original_manager
            # Or re-initialize with the mock if that's the general state needed
            # api_server.initialize_api_server_dependencies(self.mock_cc_api_key_manager, self.mock_encryption_service)

    def test_hello_key_validation_raises_exception(self):
        """Test /hello when key validation in API server raises an unexpected exception."""
        self.mock_cc_api_key_manager.list_key_names.side_effect = Exception("Unexpected validation error")

        headers = {"CcApiKey": "any_key_value"}
        response = self.client.get('/hello', headers=headers)

        self.assertEqual(response.status_code, 500)
        json_data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(json_data, {"error": "Server error during key validation"})


if __name__ == '__main__':
    unittest.main()

# To run these tests:
# Ensure this file is in a 'tests' directory (e.g., src/test/)
# From the project root directory:
# python -m unittest src/test/test_api_server.py
