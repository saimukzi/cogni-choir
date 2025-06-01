import unittest
import os
import json
import base64
from cryptography.fernet import Fernet, InvalidToken

# Adjust import path
from src.main.encryption_service import EncryptionService, ENCRYPTION_SALT_FILE as MODULE_SALT_FILE_CONSTANT

TEST_ENCRYPTION_SALT_FILE = os.path.join("data", "test_encryption_salt.json")
DATA_DIR = "data"

class TestEncryptionService(unittest.TestCase):

    def setUp(self):
        self.master_password = "testmasterpass"

        # Store original module-level constant and patch it for tests
        self.original_module_salt_file_path = MODULE_SALT_FILE_CONSTANT
        # This direct assignment changes the global variable in the imported module
        # For EncryptionService instances created AFTER this patch.
        # If EncryptionService was imported as `from src.main import encryption_service`
        # then `encryption_service.ENCRYPTION_SALT_FILE = TEST_ENCRYPTION_SALT_FILE` would be the way.
        # Since we did `from src.main.encryption_service import ENCRYPTION_SALT_FILE as MODULE_SALT_FILE_CONSTANT`
        # patching the module directly is a bit more involved if we want new instances to see it.
        # The simplest way for instance-based test is to ensure instances use the test path,
        # but EncryptionService loads its salt path at module level.
        # A common pattern is to make the path configurable per instance, or use a class variable that can be patched.
        # For now, we'll rely on patching the module's global that it uses to find the salt file.
        # This requires careful handling if tests run in parallel.
        # The current EncryptionService always uses its module-level ENCRYPTION_SALT_FILE.
        # So, we need to patch that module's variable.
        import src.main.encryption_service as es_module # Import the module itself to patch
        self.es_module_ref = es_module
        self.es_module_ref.ENCRYPTION_SALT_FILE = TEST_ENCRYPTION_SALT_FILE

        self._ensure_data_dir_exists()
        self._cleanup() # Clean up before creating the service instance

        self.es = EncryptionService(self.master_password)

    def tearDown(self):
        self._cleanup()
        # Restore original module-level constant
        self.es_module_ref.ENCRYPTION_SALT_FILE = self.original_module_salt_file_path


    def _ensure_data_dir_exists(self):
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)

    def _cleanup(self):
        if os.path.exists(TEST_ENCRYPTION_SALT_FILE):
            os.remove(TEST_ENCRYPTION_SALT_FILE)
        if os.path.exists(DATA_DIR) and not os.listdir(DATA_DIR):
            try:
                os.rmdir(DATA_DIR)
            except OSError:
                pass

    def test_init_creates_salt_and_key(self):
        self.assertTrue(os.path.exists(TEST_ENCRYPTION_SALT_FILE), "Salt file should be created on init.")
        self.assertIsNotNone(self.es.fernet_key, "Fernet key should be initialized.")
        self.assertIsInstance(self.es.fernet, Fernet, "Fernet instance should be created.")

    def test_encrypt_decrypt(self):
        data = "secret data"
        encrypted = self.es.encrypt(data)
        self.assertNotEqual(encrypted, data, "Encrypted data should not be same as original.")

        decrypted = self.es.decrypt(encrypted)
        self.assertEqual(decrypted, data, "Decrypted data should match original.")

    def test_decrypt_invalid_token(self):
        # Test with something that's not even valid base64 for Fernet
        self.assertIsNone(self.es.decrypt("invalid-token-not-b64"), "Decrypting invalid token should return None.")

        # Test with valid base64 but not a valid Fernet token for this key
        random_fernet_key = Fernet.generate_key()
        other_fernet = Fernet(random_fernet_key)
        random_encrypted_data = other_fernet.encrypt(b"other data")

        self.assertIsNone(self.es.decrypt(random_encrypted_data.decode('utf-8')), "Decrypting with wrong key should return None.")

    def test_persistence_salt_reuse(self):
        salt_before_hex = ""
        with open(TEST_ENCRYPTION_SALT_FILE, 'r') as f:
            salt_data = json.load(f)
            salt_before_hex = salt_data['salt']

        self.assertIsNotNone(self.es.encryption_salt, "Initial salt should not be None.")

        es2 = EncryptionService(self.master_password) # Should load existing salt

        salt_after_hex = ""
        with open(TEST_ENCRYPTION_SALT_FILE, 'r') as f:
            salt_data_after = json.load(f)
            salt_after_hex = salt_data_after['salt']

        self.assertEqual(salt_after_hex, salt_before_hex, "Salt file content should remain the same.")
        self.assertEqual(es2.encryption_salt, self.es.encryption_salt, "Loaded salt should be the same as the first instance's salt.")
        self.assertEqual(es2.fernet_key, self.es.fernet_key, "Fernet key derived from same password and salt should be identical.")

        data = "shared secret"
        encrypted_by_es1 = self.es.encrypt(data)
        self.assertEqual(es2.decrypt(encrypted_by_es1), data, "ES2 should decrypt data encrypted by ES1 if salt/key are same.")

    def test_update_master_password(self):
        old_fernet_key = self.es.fernet_key
        data = "my data"
        encrypted_with_old_key = self.es.encrypt(data)

        new_master_pass = "newmasterpassword"
        self.es.update_master_password(new_master_pass)

        self.assertNotEqual(self.es.fernet_key, old_fernet_key, "Fernet key should change after master password update.")
        # Salt should ideally remain the same unless explicitly managed to change
        self.assertTrue(os.path.exists(TEST_ENCRYPTION_SALT_FILE), "Salt file should still exist.")

        self.assertIsNone(self.es.decrypt(encrypted_with_old_key), "Data encrypted with old key should not be decryptable with new key.")

        encrypted_with_new_key = self.es.encrypt(data) # Encrypt again with new key
        self.assertEqual(self.es.decrypt(encrypted_with_new_key), data, "Data should be decryptable with the new key after re-encryption.")

    def test_clear_encryption_salt(self):
        self.assertTrue(os.path.exists(TEST_ENCRYPTION_SALT_FILE), "Salt file should exist before clearing.")
        self.es.clear_encryption_salt()
        self.assertFalse(os.path.exists(TEST_ENCRYPTION_SALT_FILE), "Salt file should not exist after clearing.")
        self.assertIsNone(self.es.encryption_salt, "encryption_salt attribute should be None after clearing.")

    def test_init_with_empty_master_password(self):
        with self.assertRaisesRegex(ValueError, "Master password cannot be empty"):
            EncryptionService("")

    def test_decrypt_none_input(self):
        """Tests that decrypting a None input returns None gracefully."""
        # This addresses the AttributeError: 'NoneType' object has no attribute 'encode'
        # that would occur if None is passed to decrypt.
        self.assertIsNone(self.es.decrypt(None), "Decrypting None should return None.")


if __name__ == '__main__':
    unittest.main()
