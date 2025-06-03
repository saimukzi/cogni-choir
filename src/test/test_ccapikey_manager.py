import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import os
import keyring.errors # Import for keyring exceptions

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
        # Assign actual exception classes for robust error checking if needed by SUT
        self.mock_keyring.errors.PasswordDeleteError = keyring.errors.PasswordDeleteError
        self.mock_keyring.errors.NoKeyringError = keyring.errors.NoKeyringError


        # Mock 'open' for reading/writing the keys_file_path (ccapikeys.json)
        self.mock_file_data_content = {"key_names": []} # Represents the content of ccapikeys.json

        # This mock_open setup is for when the manager *reads* the file (e.g., during __init__)
        # For testing writes, we'll often inspect what was passed to 'write'
        self.patch_open = patch('src.main.ccapikey_manager.open', mock_open(read_data=json.dumps(self.mock_file_data_content)))
        self.mock_open_func = self.patch_open.start()


        # Initialize CcApiKeyManager with mocks
        # When CcApiKeyManager is initialized, _load_key_names_from_file is called.
        # We need mock_os_path_exists to return True for the file if we want to test loading.
        self.mock_os_path_exists.side_effect = lambda path: path == os.path.join(self.test_data_dir, "ccapikeys.json")

        self.manager = CcApiKeyManager(
            data_dir=self.test_data_dir,
            encryption_service=self.mock_encryption_service
        )
        # Ensure manager also starts with fresh list for tests independent of file loading
        self.manager._key_names = []


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
        # Use the manager's internal method to get the expected service name
        service_name_expected = self.manager._get_keyring_service_name(key_name)
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
        # self.manager._save_key_names_to_file() # This call is made by add_key
        self.assertEqual(self.manager._key_names, [key_name]) # internal state

        # Clear mock call list before the explicit save for assertion
        self.mock_open_func.return_value.write.call_args_list.clear()
        self.manager._save_key_names_to_file() # Force the save with current manager state for assertion

        # Now check what was written to the mock file handle
        # Concatenate all arguments from all calls to write
        written_json_data = "".join(call[0][0] for call in self.mock_open_func.return_value.write.call_args_list)
        expected_json_data = json.dumps({"key_names": [key_name]}, indent=4)
        self.assertEqual(written_json_data, expected_json_data)


    def test_delete_key(self):
        """Test adding a key, deleting it, and ensuring it's no longer retrievable."""
        key_name = "delete_me_key"
        api_key = "to_be_deleted_value"

        self.manager.add_key(key_name, api_key)
        self.assertTrue(self.manager.has_key(key_name))

        self.assertTrue(self.manager.delete_key(key_name))
        self.assertFalse(self.manager.has_key(key_name))
        self.assertIsNone(self.manager.get_key(key_name))

        # Use the manager's internal method to get the expected service name
        service_name_expected = self.manager._get_keyring_service_name(key_name)
        self.mock_keyring.delete_password.assert_called_with(service_name_expected, key_name)

        # Clear mock call list before the explicit save for assertion
        self.mock_open_func.return_value.write.call_args_list.clear()
        self.manager._save_key_names_to_file() # to check file content after delete

        # Concatenate all arguments from all calls to write
        written_json_data = "".join(call[0][0] for call in self.mock_open_func.return_value.write.call_args_list)
        expected_json_data = json.dumps({"key_names": []}, indent=4)
        self.assertEqual(written_json_data, expected_json_data)


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


# Import sys for QApplication and other Qt classes
import sys
from PyQt6.QtWidgets import QApplication, QListWidgetItem # QInputDialog, QMessageBox are mocked
from PyQt6.QtCore import Qt # For Qt.MatchFlag
from src.main.ccapikey_dialog import CcApiKeyDialog


# Global QApplication instance for Qt based tests
# Ensure this runs only once
app = None

def setUpModule():
    global app
    # Start QApplication instance if not already running
    app = QApplication.instance()
    if app is None:
        # Create a new QApplication only if running in a headless environment (e.g. CI)
        # or if no other Qt app is running.
        # For local testing with a visible GUI, this might not be strictly necessary
        # if the test runner itself initializes Qt.
        if not os.environ.get("QT_QPA_PLATFORM"):
            os.environ["QT_QPA_PLATFORM"] = "offscreen" # Use offscreen for CI
        app = QApplication(sys.argv)

def tearDownModule():
    global app
    # Clean up the QApplication instance after all tests in the module have run.
    # This can be important in some CI environments or test setups.
    # if app is not None:
        # app.quit() # Quitting can sometimes interfere with test runners or other Qt apps.
        # It's often safer to let the process exit manage this.
        # For now, we'll do nothing explicit here.
    pass


class TestCcApiKeyDialog(unittest.TestCase):
    def setUp(self):
        """Set up for each CcApiKeyDialog test case."""
        self.mock_encryption_service = MockEncryptionService()
        self.test_data_dir = "test_data_ccapikeydialog" # Separate test data directory

        # Mock os file/directory operations
        self.patch_os_makedirs = patch('os.makedirs')
        self.mock_os_makedirs = self.patch_os_makedirs.start()
        self.patch_os_path_exists = patch('os.path.exists', return_value=False)
        self.mock_os_path_exists = self.patch_os_path_exists.start()

        # Mock keyring for CcApiKeyManager
        self.key_store_for_dialog_manager = {} # Separate key store for this manager
        self.patch_keyring_for_dialog = patch('src.main.ccapikey_manager.keyring')
        self.mock_keyring_for_dialog = self.patch_keyring_for_dialog.start()

        def mock_set_password_dialog(service, username, password):
            self.key_store_for_dialog_manager[f"{service}_{username}"] = password
        def mock_get_password_dialog(service, username):
            return self.key_store_for_dialog_manager.get(f"{service}_{username}")
        def mock_delete_password_dialog(service, username):
            key = f"{service}_{username}"
            if key in self.key_store_for_dialog_manager:
                 del self.key_store_for_dialog_manager[key]
            else:
                 raise keyring.errors.PasswordDeleteError("Password not found for dialog manager")

        self.mock_keyring_for_dialog.set_password.side_effect = mock_set_password_dialog
        self.mock_keyring_for_dialog.get_password.side_effect = mock_get_password_dialog
        self.mock_keyring_for_dialog.delete_password.side_effect = mock_delete_password_dialog
        self.mock_keyring_for_dialog.errors = MagicMock()
        self.mock_keyring_for_dialog.errors.PasswordDeleteError = keyring.errors.PasswordDeleteError
        self.mock_keyring_for_dialog.errors.NoKeyringError = keyring.errors.NoKeyringError

        # Mock 'open' for the CcApiKeyManager's JSON file
        self.dialog_manager_file_content = {"key_names": []}
        self.patch_dialog_manager_open = patch('src.main.ccapikey_manager.open', mock_open(read_data=json.dumps(self.dialog_manager_file_content)))
        self.mock_dialog_manager_open_func = self.patch_dialog_manager_open.start()

        # Create a CcApiKeyManager instance specifically for the dialog to use
        self.dialog_ccapikey_manager = CcApiKeyManager(
            data_dir=self.test_data_dir,
            encryption_service=self.mock_encryption_service
        )
        self.dialog_ccapikey_manager._key_names = [] # Ensure clean state for each test

        # Instantiate the dialog
        # No parent needed for these tests.
        self.dialog = CcApiKeyDialog(ccapikey_manager=self.dialog_ccapikey_manager, parent=None)

    def tearDown(self):
        self.patch_os_makedirs.stop()
        self.patch_os_path_exists.stop()
        self.patch_keyring_for_dialog.stop()
        self.patch_dialog_manager_open.stop()
        self.key_store_for_dialog_manager.clear()
        self.dialog.close() # Close the dialog to free resources

    def test_generate_api_key_format(self):
        """Test the _generate_api_key method directly for format and randomness."""
        key1 = self.dialog._generate_api_key()
        self.assertIsInstance(key1, str)
        self.assertEqual(len(key1), 64, "Generated key is not 64 characters long.")
        try:
            int(key1, 16) # Check if it's a valid hex string
        except ValueError:
            self.fail("_generate_api_key did not return a valid hex string.")

        key2 = self.dialog._generate_api_key()
        self.assertNotEqual(key1, key2, "Generated keys are not unique, potential issue with randomness.")

    @patch('PyQt6.QtWidgets.QApplication.clipboard')
    @patch('PyQt6.QtWidgets.QMessageBox.information')
    @patch('PyQt6.QtWidgets.QInputDialog.getText')
    def test_add_key_generates_and_copies_key(self, mock_qinput_gettext, mock_qmessage_info, mock_qapp_clipboard):
        """Test _add_key generates a key, adds it via manager, and copies to clipboard."""
        test_key_name = "my_new_api_key"
        mock_qinput_gettext.return_value = (test_key_name, True) # User enters name, clicks OK

        mock_clipboard_instance = MagicMock()
        mock_qapp_clipboard.return_value = mock_clipboard_instance

        # Spy on the manager's add_key method
        with patch.object(self.dialog_ccapikey_manager, 'add_key', wraps=self.dialog_ccapikey_manager.add_key) as wrapped_add_key:
            self.dialog._add_key()

            wrapped_add_key.assert_called_once()
            call_args = wrapped_add_key.call_args[0]
            self.assertEqual(call_args[0], test_key_name) # Correct name
            self.assertIsInstance(call_args[1], str)    # Key value is a string
            self.assertEqual(len(call_args[1]), 64)     # Key value is 64 chars
            generated_key_value = call_args[1]

            # Verify key is in list widget
            items = self.dialog.keys_list_widget.findItems(test_key_name, Qt.MatchFlag.MatchExactly)
            self.assertEqual(len(items), 1, "Key not found in QListWidget after add.")

            # Verify clipboard interaction
            mock_qapp_clipboard.assert_called_once()
            mock_clipboard_instance.setText.assert_called_once_with(generated_key_value)

            # Verify user notification
            mock_qmessage_info.assert_called_once()
            self.assertIn(test_key_name, mock_qmessage_info.call_args[0][2])
            self.assertIn("copied to your clipboard", mock_qmessage_info.call_args[0][2])

    @patch('PyQt6.QtWidgets.QApplication.clipboard')
    @patch('PyQt6.QtWidgets.QMessageBox.information')
    def test_copy_key_to_clipboard_success(self, mock_qmessage_info, mock_qapp_clipboard):
        """Test successful copy of an existing key's value to clipboard."""
        key_name = "key_to_copy"
        key_value = "abc123xyz789" # Example key value
        self.dialog_ccapikey_manager.add_key(key_name, key_value)
        self.dialog._load_keys_to_list() # Populate dialog list

        # Simulate selecting the key in QListWidget
        list_items = self.dialog.keys_list_widget.findItems(key_name, Qt.MatchFlag.MatchExactly)
        self.assertEqual(len(list_items), 1)
        self.dialog.keys_list_widget.setCurrentItem(list_items[0])

        mock_clipboard_instance = MagicMock()
        mock_qapp_clipboard.return_value = mock_clipboard_instance

        self.dialog._copy_key_to_clipboard()

        mock_qapp_clipboard.assert_called_once()
        mock_clipboard_instance.setText.assert_called_once_with(key_value)
        mock_qmessage_info.assert_called_once()
        self.assertIn(key_name, mock_qmessage_info.call_args[0][2]) # Check name in message
        self.assertIn("has been copied", mock_qmessage_info.call_args[0][2])

    @patch('PyQt6.QtWidgets.QMessageBox.warning')
    def test_copy_key_to_clipboard_no_selection_shows_warning(self, mock_qmessage_warning):
        """Test copy attempt with no key selected shows a warning."""
        self.dialog.keys_list_widget.clearSelection() # Ensure nothing selected
        self.dialog._copy_key_to_clipboard()
        mock_qmessage_warning.assert_called_once_with(
            self.dialog, "No Key Selected", "Please select a key from the list to copy its value."
        )

    @patch('PyQt6.QtWidgets.QApplication.clipboard')
    @patch('PyQt6.QtWidgets.QMessageBox.warning')
    def test_copy_key_to_clipboard_retrieval_fails_shows_warning(self, mock_qmessage_warning, mock_qapp_clipboard):
        """Test copy attempt where key retrieval fails shows a warning."""
        key_name = "unretrievable_key"
        # Add to list widget but simulate failure to retrieve from manager
        item = QListWidgetItem(key_name)
        self.dialog.keys_list_widget.addItem(item)
        self.dialog.keys_list_widget.setCurrentItem(item)

        # Mock manager's get_key to return None for this specific key
        with patch.object(self.dialog_ccapikey_manager, 'get_key', return_value=None) as mock_get_key:
            self.dialog._copy_key_to_clipboard()
            mock_get_key.assert_called_once_with(key_name)
            mock_qapp_clipboard.return_value.setText.assert_not_called()
            mock_qmessage_warning.assert_called_once()
            self.assertIn(f"Could not retrieve the value for API key '{key_name}'", mock_qmessage_warning.call_args[0][2])
