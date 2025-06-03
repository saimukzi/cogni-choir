"""Unit tests for the ThirdPartyApiKeyManager class with encryption."""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json
import io

from src.main.thirdpartyapikey_manager import ThirdPartyApiKeyManager, ThirdPartyApiKeyQuery, ENCRYPTED_SERVICE_NAME_PREFIX # Removed _KEYRING_MANAGED_SERVICES_KEY, Added ThirdPartyApiKeyQuery
from src.main.encryption_service import EncryptionService
# Import the module itself to patch its global constant for salt file path
import src.main.encryption_service as encryption_service_module

# Test file paths
DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data_temp_akm") # Unique data dir for these tests
TEST_API_KEYS_FILE = os.path.join(DATA_DIR, "test_thirdpartyapikeys.json")
TEST_ENCRYPTION_SALT_FILE_FOR_AKM = os.path.join(DATA_DIR, "test_akm_encryption_salt.json")


class TestThirdPartyApiKeyManagerWithEncryption(unittest.TestCase):
    """Tests for the ThirdPartyApiKeyManager class, assuming keyring usage with encryption."""

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
        
        # ThirdPartyApiKeyManager now requires encryption_service and data_path.
        # It will attempt to use keyring. We'll mock keyring functions per test.
        # The initial keyring.get_password in __init__ is for a _test_slot_id.
        # We can let it pass or mock it here if its failure affects setup.
        with patch('keyring.get_password') as mock_init_keyring_get:
            mock_init_keyring_get.return_value = None # Simulate test key not found, which is fine
            self.api_manager = ThirdPartyApiKeyManager(
                encryption_service=self.encryption_service,
                data_path=TEST_API_KEYS_FILE
            )

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

    def test_initial_state(self):
        """Test that the manager is correctly initialized."""
        self.assertIsNotNone(self.api_manager.encryption_service, "Encryption service should be set.")
        self.assertEqual(self.api_manager.data_path, TEST_API_KEYS_FILE)
        self.assertEqual(self.api_manager._data, {'thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict': {}}, "Initial data should be empty manifest.")

    @patch('keyring.set_password')
    @patch('keyring.get_password')
    def test_save_load_key_encrypted(self, mock_keyring_get_password, mock_keyring_set_password):
        """Tests saving and loading an encrypted key using keyring."""
        slot_id = "TestSlot"
        key_id = "TestKeyID"
        thirdpartyapikey = "secret_key_123"
        api_query = ThirdPartyApiKeyQuery(slot_id, key_id)

        # Simulate key not found initially for get_thirdpartyapikey if it tries to read before setting mock
        mock_keyring_get_password.return_value = None

        # Action: Save key
        self.api_manager.set_thirdpartyapikey(api_query, thirdpartyapikey)

        # Verify keyring.set_password was called
        # The first argument to set_password is the keyring service name
        expected_keyring_service = self.api_manager._get_keyring_service_name(slot_id)
        encrypted_key_arg = mock_keyring_set_password.call_args[0][2] # Get the encrypted key passed to set_password
        mock_keyring_set_password.assert_called_once_with(expected_keyring_service, key_id, encrypted_key_arg)
        self.assertNotEqual(encrypted_key_arg, thirdpartyapikey) # Ensure it's not plaintext

        # Setup mock for keyring.get_password to return the encrypted key for subsequent load
        mock_keyring_get_password.return_value = encrypted_key_arg

        # Action: Load key
        loaded_key = self.api_manager.get_thirdpartyapikey(api_query)
        self.assertEqual(loaded_key, thirdpartyapikey, "Loaded key should match original after decryption.")
        mock_keyring_get_password.assert_called_with(expected_keyring_service, key_id) # Called by get_thirdpartyapikey

        # Verify manifest file
        self.assertTrue(os.path.exists(TEST_API_KEYS_FILE))
        with open(TEST_API_KEYS_FILE, 'r') as f:
            manifest_data = json.load(f)
        self.assertIn(slot_id, manifest_data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'])
        self.assertIn(key_id, manifest_data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'][slot_id])

    @patch('keyring.delete_password')
    @patch('keyring.set_password')
    @patch('keyring.get_password') # Mock get_password for the initial set
    def test_delete_key_encrypted(self, mock_get_password, mock_set_password, mock_delete_password):
        """Tests deleting an encrypted key using keyring."""
        slot_id = "ToDeleteSlot"
        key_id = "ToDeleteKeyID"
        thirdpartyapikey = "key_to_delete"
        api_query = ThirdPartyApiKeyQuery(slot_id, key_id)

        # Save a key first
        encrypted_key_placeholder = self.encryption_service.encrypt(thirdpartyapikey)
        mock_get_password.return_value = None # For initial check if any
        self.api_manager.set_thirdpartyapikey(api_query, thirdpartyapikey)
        mock_set_password.assert_called_once() # Ensure it was "saved"

        # Configure get_password to "find" it for deletion check, then not find it
        mock_get_password.side_effect = [encrypted_key_placeholder, None]
        self.assertIsNotNone(self.api_manager.get_thirdpartyapikey(api_query), "Key should be loadable before delete.")
        
        # Action: Delete key
        self.api_manager.delete_thirdpartyapikey(api_query)

        # Verify keyring.delete_password was called
        expected_keyring_service = self.api_manager._get_keyring_service_name(slot_id)
        mock_delete_password.assert_called_once_with(expected_keyring_service, key_id)

        # Verify key is gone from manager's perspective
        mock_get_password.return_value = None # Ensure get_thirdpartyapikey now finds nothing
        self.assertIsNone(self.api_manager.get_thirdpartyapikey(api_query), "Key should be None after delete.")

        # Verify manifest file updated
        with open(TEST_API_KEYS_FILE, 'r') as f:
            manifest_data = json.load(f)
        self.assertNotIn(key_id, manifest_data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'].get(slot_id, []),
                         "Deleted key_id should not be in manifest for slot_id.")

    # test_load_key_decryption_failure needs to be adapted for keyring
    @patch('keyring.get_password')
    def test_load_key_decryption_failure_keyring(self, mock_keyring_get_password):
        """Tests that loading a key returns None if decryption fails (from keyring)."""
        slot_id = "CorruptSlot"
        key_id = "CorruptKeyID"
        api_query = ThirdPartyApiKeyQuery(slot_id, key_id)

        # Simulate keyring returning a corrupted (non-decryptable by current ES) string
        mock_keyring_get_password.return_value = "this is not properly encrypted by this ES"

        # Pre-populate manifest so that get_thirdpartyapikey attempts to load this
        self.api_manager._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'][slot_id] = [key_id]
        # No need to save manifest here as get_thirdpartyapikey doesn't write it

        with patch('sys.stderr', new_callable=io.StringIO) as mock_stderr:
            loaded_key = self.api_manager.get_thirdpartyapikey(api_query)
            self.assertIsNone(loaded_key, "Loading a corrupt key from keyring should return None.")
            self.assertIn("Failed to decrypt key", mock_stderr.getvalue())
        mock_keyring_get_password.assert_called_once_with(self.api_manager._get_keyring_service_name(slot_id), key_id)

    # test_re_encrypt_all_keys needs significant changes for keyring
    @patch('keyring.get_password')
    @patch('keyring.set_password')
    def test_re_encrypt_all_keys_keyring(self, mock_keyring_set_password, mock_keyring_get_password):
        """Tests re-encrypting all keys stored in keyring."""
        slot1, id1, key1 = "SlotR1", "IDR1", "re_encrypt_key1"
        slot2, id2, key2 = "SlotR2", "IDR2", "re_encrypt_key2"
        query1, query2 = ThirdPartyApiKeyQuery(slot1, id1), ThirdPartyApiKeyQuery(slot2, id2)

        old_es = self.encryption_service
        encrypted_key1_old_es = old_es.encrypt(key1)
        encrypted_key2_old_es = old_es.encrypt(key2)

        # Populate manifest
        self.api_manager._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'] = {
            slot1: [id1],
            slot2: [id2]
        }
        # No need to save manifest to file, re_encrypt reads from self._data

        # Mock keyring.get_password to return keys encrypted with old_es
        def mock_get_password_side_effect(service_name, username):
            if username == id1: return encrypted_key1_old_es
            if username == id2: return encrypted_key2_old_es
            return None
        mock_keyring_get_password.side_effect = mock_get_password_side_effect
        
        new_master_pass = "new_akm_master_password_$%^"
        new_es = EncryptionService(new_master_pass)
        self.assertNotEqual(old_es.fernet_key, new_es.fernet_key)

        # Action: Re-encrypt. This will use the new ThirdPartyApiKeyManager.re_encrypt logic
        self.api_manager.re_encrypt(old_encryption_service=old_es, new_encryption_service=new_es)
        
        # Verify manager's ES is updated (re_encrypt in SUT needs to do this)
        # Assuming re_encrypt updates self.api_manager.encryption_service
        # --> The SUT's re_encrypt does NOT update self.encryption_service. This should be done by caller.
        # So, we'll test decryption with new_es directly.
        
        # Check that keyring.set_password was called with new encrypted keys
        self.assertEqual(mock_keyring_set_password.call_count, 2)
        calls = mock_keyring_set_password.call_args_list

        # Call 1 (order might vary depending on dict iteration)
        found_key1 = False
        found_key2 = False
        for call in calls:
            called_service, called_id, new_encrypted_val = call[0]
            if called_id == id1:
                self.assertEqual(new_es.decrypt(new_encrypted_val), key1)
                self.assertNotEqual(new_encrypted_val, encrypted_key1_old_es)
                found_key1 = True
            elif called_id == id2:
                self.assertEqual(new_es.decrypt(new_encrypted_val), key2)
                self.assertNotEqual(new_encrypted_val, encrypted_key2_old_es)
                found_key2 = True
        self.assertTrue(found_key1 and found_key2, "Both keys should have been re-encrypted and set in keyring.")


    @patch('keyring.delete_password')
    def test_clear_all_keys_and_data_keyring(self, mock_keyring_delete_password):
        """Tests clearing all keys from keyring and associated data files."""
        slot1, id1 = "SlotC1", "IDC1"
        # Simulate some keys in the manifest
        self.api_manager._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'] = {
            slot1: [id1, "IDC2"],
            "SlotC2": ["IDC3"]
        }
        self.api_manager._save_data() # Save manifest to be cleared

        self.assertTrue(os.path.exists(TEST_API_KEYS_FILE))
        # Salt file is managed by EncryptionService, ThirdPartyApiKeyManager.clear() does not directly delete it.
        # EncryptionService.clear_encryption_salt() would, but AKM.clear() no longer calls it.
        # The new AKM.clear() removes its own data file and keyring entries.

        self.api_manager.clear()

        self.assertEqual(mock_keyring_delete_password.call_count, 3) # IDC1, IDC2, IDC3

        # Data file should be removed by ThirdPartyApiKeyManager.clear()
        self.assertFalse(os.path.exists(TEST_API_KEYS_FILE), "Data file (manifest) should be deleted.")

        # Check internal state
        self.assertEqual(self.api_manager._data, {'thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict': {}},
                         "Internal data should be reset to empty manifest after clear.")


    def test_set_thirdpartyapikey_requires_encryption_service(self):
        """Tests that set_thirdpartyapikey raises RuntimeError if encryption_service is (somehow) None."""
        # ThirdPartyApiKeyManager __init__ now requires encryption_service.
        # This test might be less relevant unless we test modifying it post-init.
        # For robustness, let's assume it could be set to None post-init by mistake.
        original_es = self.api_manager.encryption_service
        self.api_manager.encryption_service = None
        with self.assertRaisesRegex(RuntimeError, "Encryption service not available"):
            self.api_manager.set_thirdpartyapikey(ThirdPartyApiKeyQuery("Test", "TestID"), "key")
        self.api_manager.encryption_service = original_es # Restore

    def test_get_thirdpartyapikey_requires_encryption_service(self):
        """Tests that get_thirdpartyapikey raises RuntimeError if encryption_service is (somehow) None."""
        original_es = self.api_manager.encryption_service
        self.api_manager.encryption_service = None
        with self.assertRaisesRegex(RuntimeError, "Encryption service not available"):
            self.api_manager.get_thirdpartyapikey(ThirdPartyApiKeyQuery("Test", "TestID"))
        self.api_manager.encryption_service = original_es # Restore

    def test_empty_service_or_key_with_encryption(self):
        """Tests handling of empty ThirdPartyApiKeyQuery fields with encryption enabled."""
        # ThirdPartyApiKeyManager.set_thirdpartyapikey now takes ThirdPartyApiKeyQuery.
        # The ValueError "Service name and API key cannot be empty" was for key string.
        # ThirdPartyApiKeyQuery itself doesn't prevent empty strings for slot_id/thirdpartyapikey_id in constructor.
        # The actual keyring.set_password might fail with empty username/password.
        # Let's test that ThirdPartyApiKeyManager.set_thirdpartyapikey raises ValueError for empty thirdpartyapikey string.

        with self.assertRaisesRegex(ValueError, "API key cannot be empty"): # Assuming SUT checks this for thirdpartyapikey
            self.api_manager.set_thirdpartyapikey(ThirdPartyApiKeyQuery("some_slot", "some_id"), "")

        # Test with empty slot_id or key_id in ThirdPartyApiKeyQuery - depends on how SUT handles this for keyring.
        # Keyring might allow empty service/username but it's bad practice.
        # For now, assume ThirdPartyApiKeyQuery itself can be created with empty strings.
        # The SUT's set_thirdpartyapikey has `if not thirdpartyapikey_query: raise ValueError(...)`
        # but this checks if the ThirdPartyApiKeyQuery object itself is None, not its content.
        # The original test was `self.api_manager.set_thirdpartyapikey("", "some_key")`.
        # Let's assume an ThirdPartyApiKeyQuery with empty parts is passed.
        # The ValueError for empty thirdpartyapikey string is the main part to keep.

        # What about get_thirdpartyapikey with empty ThirdPartyApiKeyQuery fields?
        # `if not thirdpartyapikey_query: raise ValueError(...)`
        with self.assertRaisesRegex(ValueError, "ThirdPartyApiKeyQuery object cannot be None."): # Updated expected message
            self.api_manager.get_thirdpartyapikey(None) # Test None query

        # Test query with empty strings - keyring might handle this, or SUT should.
        # The SUT now prints a warning for empty slot/key ID and proceeds to call keyring.
        # Mock keyring.get_password for this specific call to avoid NoKeyringError
        # and simulate keyring returning None for such a query.
        with patch('keyring.get_password') as mock_keyring_get_empty:
            mock_keyring_get_empty.return_value = None
            self.assertIsNone(self.api_manager.get_thirdpartyapikey(ThirdPartyApiKeyQuery("", "")),
                              "Loading with empty query fields should return None after keyring call.")


if __name__ == '__main__':
    unittest.main()
