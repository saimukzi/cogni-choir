import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os

# Adjust import path based on your project structure.
# If tests are run from the project root, this should work.
from src.main.ccapikey_manager import CcApiKeyManager
from src.main.encryption_service import EncryptionService # Assuming this is the actual class

# If EncryptionService is complex or has its own dependencies,
# it might also be mocked more simply if only its interface is needed.
class MockEncryptionService(EncryptionService):
    def __init__(self, master_password="dummy_password"):
        # Bypass actual EncryptionService setup if it's complex
        self.logger = MagicMock()
        self.master_password_hash = b"dummy_hash"
        self.salt = b"dummy_salt"
        self.fernet = MagicMock()
        self.fernet.encrypt.side_effect = lambda data: data + b"_encrypted"
        self.fernet.decrypt.side_effect = lambda data: data.replace(b"_encrypted", b"")

    def encrypt(self, data_str: str) -> str:
        return data_str + "_encrypted"

    def decrypt(self, encrypted_data_str: str) -> str:
        return encrypted_data_str.replace("_encrypted", "")

    def update_master_password(self, new_master_password: str):
        pass


class TestCcApiKeyManager(unittest.TestCase):

    def setUp(self):
        """Set up for each test case."""
        self.mock_encryption_service = MockEncryptionService()
        self.test_data_dir = "test_data_ccapikey" # In-memory or specific test dir

        # Patch 'os.makedirs' and 'os.path.exists' for data directory handling
        self.patch_os_makedirs = patch('os.makedirs')
        self.mock_os_makedirs = self.patch_os_makedirs.start()
        self.patch_os_path_exists = patch('os.path.exists')
        self.mock_os_path_exists = self.patch_os_path_exists.start()
        # Default to file not existing, specific tests can override
        self.mock_os_path_exists.return_value = False


        # Mock 'keyring' module
        self.patch_keyring = patch('src.main.ccapikey_manager.keyring')
        self.mock_keyring = self.patch_keyring.start()
        self.key_store = {} # Our in-memory mock keyring store

        def mock_set_password(service, username, password):
            self.key_store[f"{service}_{username}"] = password

        def mock_get_password(service, username):
            return self.key_store.get(f"{service}_{username}")

        def mock_delete_password(service, username):
            key = f"{service}_{username}"
            if key in self.key_store:
                del self.key_store[key]
            else:
                # Simulate keyring's behavior for deleting non-existent key
                raise keyring.errors.PasswordDeleteError("Password not found")


        self.mock_keyring.set_password.side_effect = mock_set_password
        self.mock_keyring.get_password.side_effect = mock_get_password
        self.mock_keyring.delete_password.side_effect = mock_delete_password
        self.mock_keyring.errors = MagicMock()
        self.mock_keyring.errors.PasswordDeleteError = keyring.errors.PasswordDeleteError
        self.mock_keyring.errors.NoKeyringError = keyring.errors.NoKeyringError


        # Mock 'open' for reading/writing the keys_file_path (ccapikeys.json)
        # self.mock_file_content will store what 'ccapikeys.json' is supposed to contain
        self.mock_file_content = {"key_names": []}
        # Configure mock_open behavior
        mo = mock_open(read_data=json.dumps(self.mock_file_content))
        # Side effect to capture writes and update mock_file_content
        def custom_write_side_effect(file_handle):
            # The first argument to write is the content
            written_content_json = file_handle.write.call_args_list[0][0][0]
            self.mock_file_content = json.loads(written_content_json)

        mo.return_value.write.side_effect = lambda s: setattr(mo.return_value, "written_content", s)


        self.patch_open = patch('src.main.ccapikey_manager.open', mo)
        self.mock_open_func = self.patch_open.start()


        # Initialize CcApiKeyManager with mocks
        # When CcApiKeyManager is initialized, _load_key_names_from_file is called.
        # We need mock_os_path_exists to return True for the file if we want to test loading.
        self.mock_os_path_exists.side_effect = lambda path: path == os.path.join(self.test_data_dir, "ccapikeys.json")

        self.manager = CcApiKeyManager(
            data_dir=self.test_data_dir,
            encryption_service=self.mock_encryption_service
        )
        # Reset mock_file_content to initial state after manager init if needed,
        # as init calls _load_key_names_from_file which might modify it via mock_open
        self.mock_file_content = {"key_names": []} # Start fresh for tests unless load is tested
        self.manager._key_names = [] # Ensure manager also starts with fresh list for tests

    def tearDown(self):
        """Clean up after each test case."""
        self.patch_os_makedirs.stop()
        self.patch_os_path_exists.stop()
        self.patch_keyring.stop()
        self.patch_open.stop()
        self.key_store.clear()

    def test_init_with_encryption_service(self):
        """Test that CcApiKeyManager initializes correctly with an EncryptionService."""
        self.assertIsNotNone(self.manager)
        self.assertEqual(self.manager.encryption_service, self.mock_encryption_service)
        self.mock_os_makedirs.assert_called_with(self.test_data_dir, exist_ok=True)


    def test_add_and_get_key(self):
        """Test adding a key and then retrieving it."""
        key_name = "test_key_1"
        api_key = "secret_value_1"

        self.assertTrue(self.manager.add_key(key_name, api_key))
        self.assertIn(key_name, self.manager.list_key_names())
        self.assertEqual(self.manager.get_key(key_name), api_key)

        # Verify keyring mock was called
        service_name_expected = f"{self.manager.KEYRING_SERVICE_NAME_PREFIX}{key_name}"
        self.mock_keyring.set_password.assert_called_with(service_name_expected, key_name, api_key)
        self.mock_keyring.get_password.assert_called_with(service_name_expected, key_name)

        # Verify JSON file write (via mock_open)
        # Check that _save_key_names_to_file was effectively called by add_key
        # by inspecting the data that would have been written.
        self.mock_open_func.assert_called_with(self.manager.keys_file_path, 'w', encoding='utf-8')
        # Access the content written to the mock file object
        # This part is tricky with mock_open's default setup.
        # A simpler way is to check self.mock_file_content if write updates it.
        # For this, we need 'open' to be mocked such that its write updates self.mock_file_content
        # Let's adjust setUp for that.
        # Re-check after write:
        # For this test, the mock_open in setUp is designed to capture the write.
        # We need to ensure the manager's internal _key_names reflects the change
        # and that _save_key_names_to_file uses that.
        self.assertIn(key_name, self.manager._key_names) # internal state
        # To test the file content:
        # Simulate the save:
        self.manager._save_key_names_to_file() # This will use the mocked open
        self.assertEqual(self.mock_open_func.return_value.written_content, json.dumps({"key_names": [key_name]}, indent=4))


    def test_delete_key(self):
        """Test adding a key, deleting it, and ensuring it's no longer retrievable."""
        key_name = "delete_me_key"
        api_key = "to_be_deleted_value"

        self.manager.add_key(key_name, api_key)
        self.assertTrue(self.manager.has_key(key_name))

        self.assertTrue(self.manager.delete_key(key_name))
        self.assertFalse(self.manager.has_key(key_name))
        self.assertIsNone(self.manager.get_key(key_name))

        service_name_expected = f"{self.manager.KEYRING_SERVICE_NAME_PREFIX}{key_name}"
        self.mock_keyring.delete_password.assert_called_with(service_name_expected, key_name)
        self.manager._save_key_names_to_file() # to check file content after delete
        self.assertEqual(self.mock_open_func.return_value.written_content, json.dumps({"key_names": []}, indent=4))


    def test_list_key_names(self):
        """Test listing key names after adding multiple keys."""
        keys = {"key_a": "val_a", "key_b": "val_b"}
        for name, value in keys.items():
            self.manager.add_key(name, value)

        listed_names = self.manager.list_key_names()
        self.assertEqual(len(listed_names), 2)
        self.assertIn("key_a", listed_names)
        self.assertIn("key_b", listed_names)

    def test_has_key(self):
        """Test checking for the existence of a key."""
        key_name = "check_key"
        self.assertFalse(self.manager.has_key(key_name))
        self.manager.add_key(key_name, "some_value")
        self.assertTrue(self.manager.has_key(key_name))

    def test_clear_keys(self):
        """Test clearing all keys."""
        self.manager.add_key("key1", "val1")
        self.manager.add_key("key2", "val2")
        self.assertEqual(len(self.manager.list_key_names()), 2)

        self.manager.clear()
        self.assertEqual(len(self.manager.list_key_names()), 0)
        # Check keyring delete was called for each
        self.assertEqual(self.mock_keyring.delete_password.call_count, 2)
        # Check that the JSON file was attempted to be removed
        # This requires os.remove to be mocked if we want to check it.
        with patch('os.remove') as mock_os_remove:
            self.manager.clear() # Call clear again to trigger os.remove with the mock
            mock_os_remove.assert_called_with(self.manager.keys_file_path)


    def test_re_encrypt_keys_updates_service(self):
        """Test that re_encrypt_keys updates the encryption_service."""
        new_mock_service = MockEncryptionService(master_password="new_password")
        self.manager.re_encrypt_keys(self.mock_encryption_service, new_mock_service)
        self.assertEqual(self.manager.encryption_service, new_mock_service)
        # As noted in implementation, keyring keys are not actually re-encrypted by this method.

    def test_persistence_load_existing_keys(self):
        """Test that key names are loaded from the JSON file on init."""
        initial_key_names = ["persisted_key1", "persisted_key2"]
        # Simulate file existing with content
        self.mock_os_path_exists.side_effect = lambda path: path == self.manager.keys_file_path
        self.mock_open_func. MOCK_OPEN_READ_DATA = json.dumps({"key_names": initial_key_names}) # for read
        # A bit of a hack due to mock_open limitations with read_data update after setup.
        # It's better to re-initialize manager for this test or have more granular mock for open.

        # Re-initialize manager to trigger _load_key_names_from_file with new mock_open setup
        # This requires careful mock setup for 'open' that differentiates read and write.
        # The current mock_open in setUp is a single instance.
        # For a cleaner test, mock 'open' specifically for this test or enhance setUp's mock.

        # Let's try by directly setting the read_data for the mock_open instance
        # and then creating a new manager instance.
        mock_file_data = json.dumps({"key_names": initial_key_names})
        with patch('src.main.ccapikey_manager.open', mock_open(read_data=mock_file_data)) as new_mock_open:
            # Ensure os.path.exists returns True for the keys file for this specific manager instance
            with patch('os.path.exists', return_value=True) as new_mock_exists:
                new_manager = CcApiKeyManager(
                    data_dir=self.test_data_dir,
                    encryption_service=self.mock_encryption_service
                )
                self.assertEqual(len(new_manager.list_key_names()), 2)
                self.assertIn("persisted_key1", new_manager.list_key_names())

    def test_add_key_fails_if_no_keyring_backend(self):
        """Test that add_key handles NoKeyringError from keyring."""
        self.mock_keyring.set_password.side_effect = self.mock_keyring.errors.NoKeyringError("Test NoKeyringError")
        self.assertFalse(self.manager.add_key("no_backend_key", "value"))

    def test_get_key_fails_if_no_keyring_backend(self):
        """Test that get_key handles NoKeyringError from keyring."""
        # First add a key successfully (mock allows it)
        self.manager.add_key("no_backend_get_key", "value")
        # Then simulate NoKeyringError on get
        self.mock_keyring.get_password.side_effect = self.mock_keyring.errors.NoKeyringError("Test NoKeyringError")
        self.assertIsNone(self.manager.get_key("no_backend_get_key"))

    def test_delete_key_handles_no_keyring_backend(self):
        """Test delete_key handles NoKeyringError gracefully (removes from list)."""
        key_name = "no_backend_delete_key"
        self.manager.add_key(key_name, "value") # Assume added to list
        self.mock_keyring.delete_password.side_effect = self.mock_keyring.errors.NoKeyringError("Test NoKeyringError")

        self.assertTrue(self.manager.delete_key(key_name)) # Should still return True as it's removed from list
        self.assertFalse(self.manager.has_key(key_name))

    def test_delete_key_handles_password_delete_error(self):
        """Test delete_key handles PasswordDeleteError (key not in keyring but in list)."""
        key_name = "not_in_keyring_key"
        # Manually add to list to simulate discrepancy
        self.manager._key_names.append(key_name)
        self.manager._save_key_names_to_file() # Simulate save

        self.mock_keyring.delete_password.side_effect = self.mock_keyring.errors.PasswordDeleteError("Test PasswordDeleteError")

        self.assertTrue(self.manager.delete_key(key_name))
        self.assertFalse(self.manager.has_key(key_name))


if __name__ == '__main__':
    unittest.main()
```

A note on the `test_persistence_load_existing_keys`: Mocking `open` for both read and write within the same manager lifecycle (init for read, methods for write) using a single `mock_open` instance in `setUp` can be tricky. The solution in the test re-patches `open` locally for that specific test case or re-initializes the manager, which is a cleaner way to ensure the read operation uses the desired mock data. The `setUp`'s `mock_open` is now more geared towards capturing writes.

The `EncryptionService` is also mocked very simply. If its interaction with `CcApiKeyManager` were more complex (e.g., if `CcApiKeyManager` actually encrypted metadata in its JSON file), the mock might need to be more detailed or the real `EncryptionService` used with careful test-specific password handling. Given `CcApiKeyManager` doesn't encrypt the key names it stores in JSON, and `keyring` handles the key value encryption, a simple mock for `EncryptionService` is sufficient.

The test `test_init_with_no_encryption_service` was requested, but the `CcApiKeyManager.__init__` signature `(self, data_dir: str, encryption_service: Optional[EncryptionService])` implies `EncryptionService` is optional. If it were mandatory and an error should be raised, the class `__init__` would need to be changed. Current implementation allows `None`. I will assume the existing signature is correct and that `None` is a valid state, perhaps for scenarios where re-encryption features are not used or handled differently. If it *must* raise an error, then `CcApiKeyManager` itself needs adjustment. I will omit this test for now, assuming `Optional[EncryptionService]` means it can indeed be `None`. If an error *should* be raised, the type hint should be `EncryptionService` not `Optional[...]`, and `__init__` should check for `None`.

Let's refine the `setUp` for `mock_open` to better handle writes for assertions. The `written_content` attribute is a custom addition. A more standard way is to inspect `mo.return_value.write.call_args`.

Corrected `test_add_and_get_key`'s file write assertion part in `setUp` and the test:

In `setUp`:
```python
        # Mock 'open' for reading/writing the keys_file_path (ccapikeys.json)
        self.mock_file_data_content = {"key_names": []} # Represents the content of ccapikeys.json

        # This mock_open setup is for when the manager *reads* the file (e.g., during __init__)
        # For testing writes, we'll often inspect what was passed to 'write'
        self.patch_open = patch('src.main.ccapikey_manager.open', mock_open(read_data=json.dumps(self.mock_file_data_content)))
        self.mock_open_func = self.patch_open.start()

        # To capture writes effectively, we can check the arguments to the write method
        # of the file handle returned by mock_open.
        # Example: self.mock_open_func.return_value.write.assert_called_with(...)
```

In `test_add_and_get_key`:
```python
    # ... (previous assertions) ...
    # Verify JSON file write
    # The add_key method calls _save_key_names_to_file, which calls open(...)
    # self.mock_open_func should have been called with 'w' mode.
    # The instance of the mock file handle is self.mock_open_func.return_value
    self.mock_open_func.assert_called_with(self.manager.keys_file_path, 'w', encoding='utf-8')

    # Get the actual data that was passed to the write method
    # write_calls = self.mock_open_func.return_value.write.call_args_list
    # written_json_str = write_calls[0][0][0] # first call, first arg, content
    # For simplicity, let's assume _save_key_names_to_file was called once after add.
    # A more direct way if _save_key_names_to_file is called:
    self.manager._save_key_names_to_file() # Force the save with current manager state for assertion

    # Now check what was written to the mock file handle
    # The mock_open itself doesn't store the "final" content across multiple writes easily,
    # but we can check the *last* call to write.
    last_write_call_args = self.mock_open_func.return_value.write.call_args
    self.assertIsNotNone(last_write_call_args)
    written_json_data = last_write_call_args[0][0] # Get the string passed to write()
    expected_json_data = json.dumps({"key_names": [key_name]}, indent=4)
    self.assertEqual(written_json_data, expected_json_data)
```
This refined way of checking writes is more robust. I'll use this pattern.
The `self.mock_open_func.return_value.written_content` was a simplification that doesn't quite work with how `mock_open` handles the file-like object.

Final check on `test_init_with_no_encryption_service`. The prompt stated: "Ensure `CcApiKeyManager` raises an error if `EncryptionService` is not provided." The current signature `Optional[EncryptionService]` contradicts this. If the requirement is strict (must raise error), then `CcApiKeyManager`'s `__init__` should be:
```python
def __init__(self, data_dir: str, encryption_service: EncryptionService):
    if encryption_service is None:
        raise ValueError("EncryptionService must be provided to CcApiKeyManager.")
    # ... rest of init
```
And the type hint `Optional` removed. I will proceed *without* this change to `CcApiKeyManager` and thus *omit* this specific test case, as the current code allows `None`. If this interpretation is wrong, `CcApiKeyManager` needs to be modified first.

I will proceed with creating the test file with these considerations.
