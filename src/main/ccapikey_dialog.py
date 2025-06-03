"""
Dialog for managing CogniChoir API Keys (CcApiKeys).

This module defines the `CcApiKeyDialog` class, which provides a graphical
user interface for users to manage their CogniChoir-specific API keys.
These keys are distinct from third-party API keys and are used for features
like authenticating to the application's own API server.

The dialog allows users to:
- List currently stored CcApiKeys by their user-defined names.
- Add a new CcApiKey by providing a name and its value.
- View a masked representation of a stored CcApiKey's value.
- Delete an existing CcApiKey.

It interacts with an instance of `CcApiKeyManager` (from `ccapikey_manager.py`)
to perform the actual storage and retrieval operations, leveraging the system
keyring for secure storage of key values.
"""
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QLabel, QLineEdit, QMessageBox, QInputDialog, QListWidgetItem, QApplication
    # QSizePolicy was imported but not used, so removed.
)
from PyQt6.QtCore import Qt
import secrets

# Assuming CcApiKeyManager is in the same package/directory.
from .ccapikey_manager import CcApiKeyManager

class CcApiKeyDialog(QDialog):
    """
    A dialog window for managing CogniChoir API Keys (CcApiKeys).

    This dialog provides a user interface to interact with a `CcApiKeyManager`
    instance, allowing for the listing, addition, viewing (masked), copying,
    and deletion of CcApiKeys.

    Attributes:
        logger: Logger instance for this class.
        ccapikey_manager (CcApiKeyManager): The manager instance responsible for
            handling the storage and retrieval of CcApiKeys.
        keys_list_widget (QListWidget): Widget to display the list of key names.
        add_key_button (QPushButton): Button to trigger the add key workflow.
        view_key_button (QPushButton): Button to view details of a selected key.
        delete_key_button (QPushButton): Button to delete a selected key.
        close_button (QPushButton): Button to close the dialog.
    """

    def __init__(self, ccapikey_manager: CcApiKeyManager, parent=None):
        """
        Initializes the CcApiKeyDialog.

        Args:
            ccapikey_manager (CcApiKeyManager): An instance of `CcApiKeyManager`
                that will be used for all key management operations.
            parent (QWidget, optional): The parent widget of this dialog.
                Defaults to None.
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.ccapikey_manager = ccapikey_manager

        self.setWindowTitle(self.tr("Manage CogniChoir API Keys"))
        self.setMinimumSize(500, 300) # Set a reasonable minimum size

        self._init_ui()
        self._load_keys_to_list()

    def _init_ui(self):
        """
        Initializes the user interface components and layout of the dialog.

        Sets up the list widget for displaying key names and buttons for
        actions like add, view, delete, and close.
        """
        main_layout = QVBoxLayout(self)

        # Label for the list of API keys
        list_label = QLabel(self.tr("Stored CogniChoir API Keys:"))
        main_layout.addWidget(list_label)

        # List widget to display key names
        self.keys_list_widget = QListWidget()
        self.keys_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        # Connect selection change to update button states (e.g., enable delete/view only when item selected)
        self.keys_list_widget.itemSelectionChanged.connect(self._update_button_states)
        main_layout.addWidget(self.keys_list_widget)

        # Layout for action buttons
        buttons_layout = QHBoxLayout()

        self.add_key_button = QPushButton(self.tr("Add Key..."))
        self.add_key_button.clicked.connect(self._add_key)
        buttons_layout.addWidget(self.add_key_button)

        self.view_key_button = QPushButton(self.tr("View Key..."))
        self.view_key_button.clicked.connect(self._view_key)
        buttons_layout.addWidget(self.view_key_button)

        self.copy_key_button = QPushButton(self.tr("Copy Key"))
        self.copy_key_button.clicked.connect(self._copy_key_to_clipboard)
        buttons_layout.addWidget(self.copy_key_button)

        self.delete_key_button = QPushButton(self.tr("Delete Key"))
        self.delete_key_button.clicked.connect(self._delete_key)
        buttons_layout.addWidget(self.delete_key_button)

        buttons_layout.addStretch() # Pushes subsequent buttons to the right or fills space

        self.close_button = QPushButton(self.tr("Close"))
        self.close_button.clicked.connect(self.accept) # Use accept() for standard dialog closing
        buttons_layout.addWidget(self.close_button)

        main_layout.addLayout(buttons_layout)
        self._update_button_states() # Set initial enabled state of buttons

    def _load_keys_to_list(self):
        """
        Loads API key names from the `CcApiKeyManager` and populates the list widget.

        Clears any existing items in the list and reloads them. Key names are
        sorted alphabetically for consistent display. After loading, button
        states are updated.
        """
        self.keys_list_widget.clear()
        key_names = self.ccapikey_manager.list_key_names()
        for name in sorted(key_names): # Sort names for consistent UI
            item = QListWidgetItem(name)
            self.keys_list_widget.addItem(item)
        self._update_button_states() # Refresh button states based on new list content

    def _update_button_states(self):
        """
        Updates the enabled state of the 'View Key' and 'Delete Key' buttons.

        These buttons are enabled only if an item is selected in the
        `keys_list_widget`.
        """
        has_selection = bool(self.keys_list_widget.selectedItems())
        self.view_key_button.setEnabled(has_selection)
        self.copy_key_button.setEnabled(has_selection)
        self.delete_key_button.setEnabled(has_selection)

    def _generate_api_key(self) -> str:
        """Generates a cryptographically secure random API key.

        The key is 64 characters long, generated using secrets.token_hex(32).

        Returns:
            str: The generated API key.
        """
        return secrets.token_hex(32)

    def _add_key(self):
        """
        Handles the process of adding a new CcApiKey.

        Prompts the user for a name for the new key. Generates a secure key
        value automatically. Validates that the name is not empty and does not
        already exist. If validations pass, it calls the `CcApiKeyManager`
        to add the key. Shows success or error messages to the user.
        The newly generated key is copied to the clipboard.
        """
        # Prompt for key name
        key_name, ok_name = QInputDialog.getText(self,
                                                 self.tr("Add CogniChoir API Key"),
                                                 self.tr("Enter a unique name for the new API key:"))
        if not ok_name or not key_name.strip():
            if ok_name:  # User pressed OK but input was empty or spaces
                QMessageBox.warning(self, self.tr("Invalid Name"), self.tr("API key name cannot be empty."))
            return  # User cancelled or entered empty name

        key_name = key_name.strip()  # Clean up whitespace

        if self.ccapikey_manager.has_key(key_name):
            QMessageBox.warning(self, self.tr("Name Exists"),
                                self.tr("An API key with the name '{0}' already exists.").format(key_name))
            return

        # Generate key value
        api_key_value = self._generate_api_key()

        # Attempt to add the key via the manager
        if self.ccapikey_manager.add_key(key_name, api_key_value):
            self.logger.info(f"CcAPIKey '{key_name}' added successfully via dialog.")
            self._load_keys_to_list()  # Refresh the list
            # Try to select the newly added key for user convenience
            items = self.keys_list_widget.findItems(key_name, Qt.MatchFlag.MatchExactly)
            if items:
                self.keys_list_widget.setCurrentItem(items[0])

            # Inform user and copy to clipboard
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(api_key_value)
                QMessageBox.information(self, self.tr("Success"),
                                        self.tr("CogniChoir API key '{0}' was added successfully and copied to your clipboard.").format(key_name))
            else:
                # Fallback if clipboard is not available, though rare in GUI apps
                QMessageBox.information(self, self.tr("Success"),
                                        self.tr("CogniChoir API key '{0}' was added successfully. Please copy it manually if needed.").format(key_name))
                self.logger.warning("QApplication.clipboard() returned None. Cannot copy new API key.")

        else:
            self.logger.error(f"Failed to add CcAPIKey '{key_name}' via dialog (manager returned false).")
            QMessageBox.critical(self, self.tr("Error Adding Key"),
                                 self.tr("Could not add the API key. This might be due to an issue with the system keyring. Please check the application logs for more details."))

    def _copy_key_to_clipboard(self):
        """Copies the selected API key's value to the clipboard.

        If a key is selected in the list, its value is retrieved from the
        CcApiKeyManager and copied to the system clipboard. Confirmation or
        error messages are displayed to the user.
        """
        selected_items = self.keys_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, self.tr("No Key Selected"),
                                self.tr("Please select a key from the list to copy its value."))
            return

        key_name = selected_items[0].text()
        api_key_value = self.ccapikey_manager.get_key(key_name)

        if api_key_value is not None:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(api_key_value)
                self.logger.info(f"Copied value of CcAPIKey '{key_name}' to clipboard.")
                QMessageBox.information(self, self.tr("Key Copied"),
                                        self.tr("The value of API key '{0}' has been copied to your clipboard.").format(key_name))
            else:
                self.logger.warning("QApplication.clipboard() returned None. Cannot copy API key.")
                QMessageBox.warning(self, self.tr("Clipboard Error"),
                                    self.tr("Could not access the system clipboard to copy the key."))
        else:
            self.logger.warning(f"Attempted to copy CcAPIKey '{key_name}', but its value could not be retrieved.")
            QMessageBox.warning(self, self.tr("Key Value Not Found"),
                                self.tr("Could not retrieve the value for API key '{0}'. It might have been deleted or an error occurred.").format(key_name))

    def _view_key(self):
        """
        Handles viewing the selected CcApiKey.

        Retrieves the selected key's name from the list. For security, this
        implementation does not display the actual key value. Instead, it shows
        a message box with the key's name and a masked representation of its
        value (e.g., a series of asterisks). This confirms the key's existence
        and length without exposing the secret.
        """
        selected_items = self.keys_list_widget.selectedItems()
        if not selected_items:
            # This should not happen if button state is managed correctly
            self.logger.warning("_view_key called with no item selected.")
            return
        key_name = selected_items[0].text()

        # Retrieve the key value from the manager to get its length for masking
        api_key_value = self.ccapikey_manager.get_key(key_name)

        if api_key_value is not None: # Key exists in keyring
            # Create a masked representation (e.g., "************")
            masked_key = "*" * len(api_key_value) if api_key_value else self.tr("(empty key value)")
            QMessageBox.information(self, self.tr("View CogniChoir API Key"),
                                    self.tr("Key Name: {0}\nKey Value (masked): {1}").format(key_name, masked_key))
        else:
            # This might occur if the key is in the JSON list but missing from keyring (e.g., external modification)
            self.logger.warning(f"CcAPIKey '{key_name}' is listed but its value could not be retrieved from keyring.")
            QMessageBox.warning(self, self.tr("Key Value Not Found"),
                                self.tr("Could not retrieve the value for API key '{0}' from secure storage. It might have been deleted or corrupted externally.").format(key_name))

    def _delete_key(self):
        """
        Handles deleting the selected CcApiKey.

        Prompts the user for confirmation before proceeding with the deletion.
        If confirmed, it calls the `CcApiKeyManager` to delete the key and then
        refreshes the list of keys displayed in the dialog. Shows success or
        error messages to the user.
        """
        selected_items = self.keys_list_widget.selectedItems()
        if not selected_items:
            # This should not happen if button state is managed correctly
            self.logger.warning("_delete_key called with no item selected.")
            return
        key_name = selected_items[0].text()

        # Confirm deletion with the user
        reply = QMessageBox.question(self, self.tr("Confirm Deletion"),
                                     self.tr("Are you sure you want to permanently delete the CogniChoir API key '{0}'? This action cannot be undone.").format(key_name),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No) # Default to No

        if reply == QMessageBox.StandardButton.Yes:
            if self.ccapikey_manager.delete_key(key_name):
                self.logger.info(f"CcAPIKey '{key_name}' deleted successfully via dialog.")
                self._load_keys_to_list() # Refresh the list
                QMessageBox.information(self, self.tr("Deletion Successful"),
                                        self.tr("CogniChoir API key '{0}' was deleted successfully.").format(key_name))
            else:
                self.logger.error(f"Failed to delete CcAPIKey '{key_name}' via dialog (manager returned false).")
                QMessageBox.critical(self, self.tr("Error Deleting Key"),
                                     self.tr("Could not delete the API key. This might be due to an issue with the system keyring or the key was already removed. Please check the application logs."))

    def accept(self):
        """
        Overrides `QDialog.accept()` to handle the dialog's "Close" action.
        Logs the closure of the dialog.
        """
        self.logger.debug("CcApiKeyDialog accepted (closed by user).")
        super().accept()

# Example Usage (for testing the dialog independently if run as a script)
if __name__ == '__main__':
    # Standard library imports for example
    from PyQt6.QtWidgets import QApplication
    import sys

    # Dummy EncryptionService and CcApiKeyManager for testing dialog
    class DummyEncryptionService:
        def encrypt(self, data: bytes) -> bytes: return data
        def decrypt(self, data: bytes) -> bytes: return data

    # Need to create a dummy CcApiKeyManager that works without a real keyring for basic UI testing.
    # The provided CcApiKeyManager will try to use keyring.
    # For a simple UI test, we can mock CcApiKeyManager or use a simplified version.
    # For now, this example will require a keyring backend.

    logging.basicConfig(level=logging.DEBUG)
    app = QApplication(sys.argv)

    # Ensure the test data directory exists
    test_data_dir = "test_ccapikey_data"
    if not os.path.exists(test_data_dir):
        os.makedirs(test_data_dir)

    # Dummy encryption service for the manager
    dummy_es = DummyEncryptionService()
    manager = CcApiKeyManager(data_dir=test_data_dir, encryption_service=dummy_es) #type: ignore

    # Pre-populate with some keys for testing, if keyring is available
    try:
        if not manager.has_key("testkey1"): manager.add_key("testkey1", "value1")
        if not manager.has_key("testkey2"): manager.add_key("testkey2", "value2")
    except Exception as e:
        print(f"Could not pre-populate keys for dialog test (keyring issue?): {e}")


    dialog = CcApiKeyDialog(ccapikey_manager=manager)
    dialog.exec()

    # Cleanup after dialog test
    # manager.clear() # This would also delete from keyring
    # if os.path.exists(test_data_dir):
    #     import shutil
    #     shutil.rmtree(test_data_dir)

    sys.exit(app.exec())
