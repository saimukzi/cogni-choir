"""Unit tests for the ApiKeyManager class with encryption."""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json
import io

# Adjusting sys.path for direct imports from src.main
# This assumes tests are run from the root of the project or src/test is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.main.api_key_manager import ApiKeyManager, ENCRYPTED_SERVICE_NAME_PREFIX, _KEYRING_MANAGED_SERVICES_KEY
from src.main.encryption_service import EncryptionService
# Import the module itself to patch its global constant for salt file path
import src.main.encryption_service as encryption_service_module

# Test file paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data_temp_akm") # Unique data dir for these tests
TEST_API_KEYS_FILE = os.path.join(DATA_DIR, "test_api_keys.json")
TEST_ENCRYPTION_SALT_FILE_FOR_AKM = os.path.join(DATA_DIR, "test_akm_encryption_salt.json")


class TestApiKeyManagerWithEncryption(unittest.TestCase):
    """Tests for the ApiKeyManager class with encryption in fallback mode."""

    @classmethod
    def setUpClass(cls):
        # Store original EncryptionService salt file path to restore later
        cls.original_es_salt_file_path = encryption_service_module.ENCRYPTION_SALT_FILE
        # Patch the EncryptionService module's global salt file path for all tests in this class
        encryption_service_module.ENCRYPTION_SALT_FILE = TEST_ENCRYPTION_SALT_FILE_FOR_AKM

    @classmethod
    def tearDownClass(cls):
        # Restore original EncryptionService salt file path
        encryption_service_module.ENCRYPTION_SALT_FILE = cls.original_es_salt_file_path

    def setUp(self):
        """Sets up a temporary directory, file paths, and EncryptionService for tests."""
        os.makedirs(DATA_DIR, exist_ok=True)
        self._cleanup_test_files() # Clean up before each test

        self.master_password = "akm_master_password_!@#"
        # EncryptionService will use the patched TEST_ENCRYPTION_SALT_FILE_FOR_AKM
        self.encryption_service = EncryptionService(self.master_password)
        
        # Initialize ApiKeyManager, forcing fallback mode and using test paths
        # We patch keyring.get_password during __init__ to ensure fallback mode
        with patch('keyring.get_password', side_effect=Exception("Simulate no keyring")):
            self.api_manager = ApiKeyManager(encryption_service=self.encryption_service)
        
        self.api_manager.fallback_file_path = TEST_API_KEYS_FILE
        self.api_manager.use_keyring = False # Explicitly force fallback mode for all tests
        # Manually reload cache after setting new path if __init__ loaded with different one.
        # In this setup, ApiKeyManager's __init__ already loads based on the patched path if ES is passed.
        # However, if ES wasn't passed, it would init its own fallback.
        # Forcing use_keyring=False means it will rely on _keys_cache and fallback_file_path.
        # If _load_keys_from_fallback wasn't called with the correct path in init, call it now.
        self.api_manager._keys_cache = self.api_manager._load_keys_from_fallback()


    def tearDown(self):
        """Cleans up test files after each test."""
        self._cleanup_test_files()
        if os.path.exists(DATA_DIR) and not os.listdir(DATA_DIR):
            os.rmdir(DATA_DIR)


    def _cleanup_test_files(self):
        """Removes test-specific files."""
        if os.path.exists(TEST_API_KEYS_FILE):
            os.remove(TEST_API_KEYS_FILE)
        if os.path.exists(TEST_ENCRYPTION_SALT_FILE_FOR_AKM):
            os.remove(TEST_ENCRYPTION_SALT_FILE_FOR_AKM)
        # Do not remove DATA_DIR itself here if it might contain .gitkeep from project structure
        # It will be removed in tearDown if empty.

    def test_initial_state_fallback_mode(self):
        """Test that the manager is correctly initialized in fallback mode."""
        self.assertFalse(self.api_manager.use_keyring, "ApiKeyManager should be in fallback mode.")
        self.assertIsNotNone(self.api_manager.encryption_service, "Encryption service should be set.")

    def test_save_load_key_encrypted_fallback(self):
        """Tests saving and loading an encrypted key in fallback mode."""
        service_name = "TestServiceEnc"
        api_key = "secret_key_123_fallback"

        self.api_manager.save_key(service_name, api_key)
        loaded_key = self.api_manager.load_key(service_name)
        self.assertEqual(loaded_key, api_key, "Loaded key should match original after decryption.")

        # Verify raw storage
        self.assertTrue(os.path.exists(TEST_API_KEYS_FILE))
        with open(TEST_API_KEYS_FILE, 'r') as f:
            raw_data = json.load(f)

        self.assertIn(service_name, raw_data, "Service name should be in raw data.")
        self.assertNotEqual(raw_data[service_name], api_key, "Stored key should be encrypted.")

        # Decrypt raw data directly to confirm it's the original key
        decrypted_raw = self.encryption_service.decrypt(raw_data[service_name])
        self.assertEqual(decrypted_raw, api_key, "Manually decrypted raw key should match original.")

    def test_delete_key_fallback_encrypted(self):
        """Tests deleting an encrypted key in fallback mode."""
        service_name = "ToDeleteService"
        api_key = "key_to_delete"
        self.api_manager.save_key(service_name, api_key)
        self.assertIsNotNone(self.api_manager.load_key(service_name), "Key should be loadable before delete.")

        self.api_manager.delete_key(service_name)
        self.assertIsNone(self.api_manager.load_key(service_name), "Key should be None after delete.")
        
        if os.path.exists(TEST_API_KEYS_FILE):
            with open(TEST_API_KEYS_FILE, 'r') as f:
                raw_data = json.load(f)
            self.assertNotIn(service_name, raw_data, "Deleted service should not be in raw data.")

    def test_load_key_decryption_failure(self):
        """Tests that loading a key returns None if decryption fails."""
        service_name = "CorruptService"
        # Manually save a non-decryptable (or wrongly encrypted) key
        self.api_manager._keys_cache[service_name] = "this is not properly encrypted by this ES"
        self.api_manager._save_keys_to_fallback(self.api_manager._keys_cache)
        
        with patch('sys.stderr', new_callable=io.StringIO) as mock_stderr: # To catch print statements from decrypt
            loaded_key = self.api_manager.load_key(service_name)
            self.assertIsNone(loaded_key, "Loading a corrupt key should return None.")
            self.assertIn("Failed to decrypt key", mock_stderr.getvalue())


    def test_re_encrypt_all_keys_fallback(self):
        """Tests re-encrypting all keys in fallback mode."""
        service1, key1 = "ServiceR1", "re_encrypt_key1"
        service2, key2 = "ServiceR2", "re_encrypt_key2"
        self.api_manager.save_key(service1, key1)
        self.api_manager.save_key(service2, key2)

        old_es = self.encryption_service
        
        # To truly simulate a new encryption key, we need a new password or new salt.
        # Since EncryptionService uses a global path for its salt file, changing just the password
        # for a new EncryptionService instance (while the salt file remains) will result in a new Fernet key.
        new_master_pass = "new_akm_master_password_$%^"
        new_es = EncryptionService(new_master_pass) # This will use the same salt file but derive a new Fernet key
        
        self.assertNotEqual(old_es.fernet_key, new_es.fernet_key, "New ES should have a different Fernet key.")

        self.api_manager.re_encrypt_all_keys(old_encryption_service=old_es, new_encryption_service=new_es)
        
        self.assertEqual(self.api_manager.encryption_service, new_es, "ApiKeyManager should now use the new ES.")
        self.assertEqual(self.api_manager.load_key(service1), key1, "Key1 should be decryptable with new ES.")
        self.assertEqual(self.api_manager.load_key(service2), key2, "Key2 should be decryptable with new ES.")

        # Verify raw data is now encrypted with new_es
        with open(TEST_API_KEYS_FILE, 'r') as f:
            raw_data = json.load(f)
        
        self.assertEqual(new_es.decrypt(raw_data[service1]), key1, "Raw key1 should be decryptable by new_es.")
        self.assertIsNone(old_es.decrypt(raw_data[service1]), "Raw key1 should NOT be decryptable by old_es.")
        self.assertEqual(new_es.decrypt(raw_data[service2]), key2, "Raw key2 should be decryptable by new_es.")
        self.assertIsNone(old_es.decrypt(raw_data[service2]), "Raw key2 should NOT be decryptable by old_es.")


    def test_clear_all_keys_and_data_fallback(self):
        """Tests clearing all keys and data in fallback mode."""
        service_name = "ServiceToClear"
        api_key = "key_to_clear"
        self.api_manager.save_key(service_name, api_key)

        self.assertTrue(os.path.exists(TEST_API_KEYS_FILE), "API keys file should exist before clear.")
        self.assertTrue(os.path.exists(TEST_ENCRYPTION_SALT_FILE_FOR_AKM), "Salt file should exist before clear.")

        self.api_manager.clear_all_keys_and_data()

        self.api_manager.load_key(service_name)

        # Fallback file should exist but be empty (or contain empty manifest)
        self.assertTrue(os.path.exists(TEST_API_KEYS_FILE), "Fallback file should still exist.")
        with open(TEST_API_KEYS_FILE, 'r') as f:
            content = json.load(f)
        self.assertEqual(content, {_KEYRING_MANAGED_SERVICES_KEY: []}, "Fallback file should be an empty manifest.")

        self.assertFalse(os.path.exists(TEST_ENCRYPTION_SALT_FILE_FOR_AKM), "Salt file should be deleted.")


    def test_save_key_requires_encryption_service(self):
        """Tests that save_key raises RuntimeError if encryption_service is None."""
        self.api_manager.encryption_service = None # Simulate no ES
        with self.assertRaisesRegex(RuntimeError, "Encryption service not available"):
            self.api_manager.save_key("Test", "key")

    def test_load_key_requires_encryption_service(self):
        """Tests that load_key raises RuntimeError if encryption_service is None."""
        # First save a key normally
        self.api_manager.save_key("Test", "key")
        # Then simulate ES becoming unavailable
        self.api_manager.encryption_service = None
        with self.assertRaisesRegex(RuntimeError, "Encryption service not available"):
            self.api_manager.load_key("Test")

    def test_empty_service_or_key_with_encryption(self):
        """Tests handling of empty service or key names with encryption enabled."""
        with self.assertRaisesRegex(ValueError, "Service name and API key cannot be empty"):
            self.api_manager.save_key("", "some_key")

        with self.assertRaisesRegex(ValueError, "Service name and API key cannot be empty"):
            self.api_manager.save_key("some_service", "")

        self.assertIsNone(self.api_manager.load_key(""), "Loading an empty service name should return None.")

    def test_keyring_manifest_management_in_fallback_mode(self):
        """Ensure keyring manifest is NOT populated when use_keyring is False."""
        # This test is mostly to confirm assumptions about _KEYRING_MANAGED_SERVICES_KEY
        # when use_keyring is False.
        self.assertFalse(self.api_manager.use_keyring) # Double check forced fallback

        service_name = "ServiceFallbackManifestTest"
        api_key = "key_for_fallback_manifest"
        self.api_manager.save_key(service_name, api_key)

        # In pure fallback mode, _KEYRING_MANAGED_SERVICES_KEY should remain empty or not primary storage key
        self.assertNotIn(service_name, self.api_manager._keys_cache.get(_KEYRING_MANAGED_SERVICES_KEY, []),
                         "Service name should not be in keyring manifest when in fallback mode.")
        self.assertIn(service_name, self.api_manager._keys_cache,
                      "Service name should be a direct key in cache for fallback mode.")


if __name__ == '__main__':
    unittest.main()
