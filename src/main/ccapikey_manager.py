# --- Delete an existing key ---
# if manager.delete_key(key_name_to_delete):
# print(f"Key '{key_name_to_delete}' deleted successfully.")
# else:
# print(f"Failed to delete key '{key_name_to_delete}'.")

# --- List all keys after operations ---
# print("Final list of key names:", manager.list_key_names())

# --- Clear all keys (use with caution) ---
# manager.clear()
# print("All keys cleared. Final list:", manager.list_key_names())
"""
Manages CogniChoir API Keys (CcApiKeys).

This module provides the `CcApiKeyManager` class, responsible for handling
the storage, retrieval, and management of API keys specific to the CogniChoir
application. It uses the system's keyring for securely storing the actual API key
values and a local JSON file (`ccapikeys.json`) within a specified data
directory to keep track of the names or identifiers of these keys.

The manager supports operations such as adding, retrieving, deleting, and listing
API keys. It also includes mechanisms for re-encrypting metadata (if any were
encrypted, though currently key names are stored plaintext) and clearing all
stored keys, which are essential during master password changes or full data resets
in the main application.

Typical usage involves initializing the manager with a data directory path and an
instance of `EncryptionService`. While the keyring handles its own encryption for
the keys themselves, the `EncryptionService` is available for any potential
future needs for encrypting metadata stored in the JSON file and is used in the
re-encryption workflow triggered by master password changes.
"""
import keyring
import json
import os
import logging
from typing import List, Optional, Dict

from .encryption_service import EncryptionService # For re-encryption

# Standard library imports
import json
import logging
import os
from typing import List, Optional

# Third-party imports
import keyring
import keyring.errors

# Local application imports
from .encryption_service import EncryptionService

CC_API_KEYS_FILENAME = "ccapikeys.json"
"""Filename for storing the names of managed CcApiKeys."""

KEYRING_SERVICE_NAME_PREFIX = "CogniChoirCcApiKey_"
"""Prefix for service names in the keyring to avoid collisions.
Each key name will be appended to this prefix to form a unique service name.
Example: CogniChoirCcApiKey_MyMainKey"""

class CcApiKeyManager:
    """
    Manages storage and retrieval of CogniChoir API Keys (CcApiKeys).

    This class uses the system's keyring to securely store the actual API key values.
    It maintains a local JSON file (`ccapikeys.json`) in a specified data directory
    to keep track of the user-defined names for these keys. This allows users to
    refer to keys by memorable names rather than their actual values.

    Attributes:
        logger: Logger instance for this class.
        data_dir (str): The directory where `ccapikeys.json` is stored.
        keys_file_path (str): The full path to the `ccapikeys.json` file.
        encryption_service (Optional[EncryptionService]): Service used for cryptographic
            operations if metadata were to be encrypted. Currently, key names are
            stored in plaintext. This service is primarily used to participate in
            the re-encryption process when the master password changes.
        _key_names (List[str]): An internal list of tracked key names, loaded from
            and saved to `ccapikeys.json`.
    """

    def __init__(self, data_dir: str, encryption_service: Optional[EncryptionService]):
        """
        Initializes the CcApiKeyManager.

        Args:
            data_dir (str): The directory path where `ccapikeys.json` (the file
                tracking key names) will be stored. The directory will be
                created if it doesn't exist.
            encryption_service (Optional[EncryptionService]): An instance of
                EncryptionService. While keyring handles the encryption of key
                values themselves, this service is provided for potential future
                use (e.g., encrypting metadata stored in `ccapikeys.json`) and
                is essential for the `re_encrypt_keys` method's consistency
                with other key managers during master password changes.
        """
        self.logger = logging.getLogger(__name__)
        self.data_dir = data_dir
        self.keys_file_path = os.path.join(self.data_dir, CC_API_KEYS_FILENAME)
        self.encryption_service = encryption_service # Store for re-encryption and potential future use
        self._ensure_data_dir_exists()
        self._key_names: List[str] = self._load_key_names_from_file()

    def _ensure_data_dir_exists(self):
        """
        Ensures that the data directory for storing `ccapikeys.json` exists.
        If the directory does not exist, it attempts to create it.
        Logs an error and raises an exception if directory creation fails.
        """
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir, exist_ok=True)
                self.logger.info(f"Created data directory: {self.data_dir}")
            except OSError as e:
                self.logger.error(f"Failed to create data directory {self.data_dir}: {e}", exc_info=True)
                raise # Re-raise to indicate critical failure

    def _load_key_names_from_file(self) -> List[str]:
        """
        Loads the list of CcApiKey names from the `ccapikeys.json` file.

        If the file doesn't exist, is empty, or is corrupted, it returns an empty list.

        Returns:
            List[str]: A list of key names. Returns an empty list if the file
                       cannot be loaded or if no key names are found.
        """
        if not os.path.exists(self.keys_file_path):
            self.logger.debug(f"CcAPIKeys file not found: {self.keys_file_path}. Returning empty list.")
            return []
        try:
            with open(self.keys_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure "key_names" exists and is a list, otherwise default to empty list.
                key_names = data.get("key_names", [])
                if not isinstance(key_names, list):
                    self.logger.warning(f"'key_names' in {self.keys_file_path} is not a list. Treating as empty.")
                    return []
                return key_names
        except (IOError, json.JSONDecodeError) as e:
            self.logger.error(f"Error loading CcAPIKey names from {self.keys_file_path}: {e}", exc_info=True)
            return [] # Return empty list on error to allow application to proceed if possible

    def _save_key_names_to_file(self):
        """
        Saves the current list of CcApiKey names to the `ccapikeys.json` file.
        This method is called internally after any operation that modifies the
        list of key names (add, delete, clear).
        """
        try:
            with open(self.keys_file_path, 'w', encoding='utf-8') as f:
                json.dump({"key_names": self._key_names}, f, indent=4)
            self.logger.debug(f"CcAPIKey names saved to {self.keys_file_path}.")
        except IOError as e:
            self.logger.error(f"Error saving CcAPIKey names to {self.keys_file_path}: {e}", exc_info=True)

    def _get_keyring_service_name(self, key_name: str) -> str:
        """
        Generates a unique service name for storing a CcApiKey in the system keyring.
        This is typically formed by a prefix and the user-defined key name.

        Args:
            key_name (str): The user-defined name of the API key.

        Returns:
            str: The service name to be used with the `keyring` library.
        """
        # Using a fixed prefix + key_name as the service_name and key_name as username
        # This structure is common for keyring usage.
        return f"{KEYRING_SERVICE_NAME_PREFIX}{key_name}"

    def add_key(self, key_name: str, api_key: str) -> bool:
        """
        Adds a new CcApiKey.

        The key's value is stored securely in the system keyring, and its user-defined
        name is added to the list tracked in `ccapikeys.json`.

        Args:
            key_name (str): The user-defined name for the API key. This name must
                            be unique among CcApiKeys.
            api_key (str): The actual API key value to be stored.

        Returns:
            bool: True if the key was successfully added and stored, False otherwise
                  (e.g., if the key name already exists, or a keyring error occurs).
        """
        if not key_name or not api_key: # Basic validation
            self.logger.warning("Attempted to add CcAPIKey with empty name or key value.")
            return False
        if key_name in self._key_names:
            self.logger.warning(f"CcAPIKey with name '{key_name}' already exists. Please use a unique name or delete the existing key first.")
            return False

        try:
            # Store the key in the keyring.
            # The 'service_name' helps categorize the stored secret.
            # The 'username' can be the key_name itself or a generic user identifier.
            # Here, key_name is used for both parts of the keyring identifier for simplicity with the prefix.
            keyring.set_password(self._get_keyring_service_name(key_name), key_name, api_key)
            self._key_names.append(key_name)
            self._save_key_names_to_file()
            self.logger.info(f"CcAPIKey '{key_name}' added and stored in keyring.")
            return True
        except keyring.errors.NoKeyringError:
            self.logger.error("No keyring backend found. CcAPIKey cannot be stored securely. Please install a backend (e.g., python -m pip install keyring-alt).", exc_info=True)
        except Exception as e: # Catch other potential keyring errors
            self.logger.error(f"Error adding CcAPIKey '{key_name}' to keyring: {e}", exc_info=True)
        return False

    def get_key(self, key_name: str) -> Optional[str]:
        """
        Retrieves the value of a CcApiKey from the system keyring.

        Args:
            key_name (str): The user-defined name of the API key to retrieve.

        Returns:
            Optional[str]: The API key value if found and successfully retrieved
                           from the keyring. Returns None if the key name is not
                           tracked, if the key is not found in the keyring, or
                           if a keyring error occurs.
        """
        if key_name not in self._key_names:
            self.logger.warning(f"Attempted to retrieve non-tracked CcAPIKey '{key_name}'.")
            return None
        try:
            return keyring.get_password(self._get_keyring_service_name(key_name), key_name)
        except keyring.errors.NoKeyringError:
            self.logger.error("No keyring backend found. CcAPIKey cannot be retrieved.", exc_info=True)
        except Exception as e: # Catch other potential keyring errors
            self.logger.error(f"Error retrieving CcAPIKey '{key_name}' from keyring: {e}", exc_info=True)
        return None

    def delete_key(self, key_name: str) -> bool:
        """
        Deletes a CcApiKey.

        Removes the key value from the system keyring and its name from the
        list tracked in `ccapikeys.json`.

        Args:
            key_name (str): The user-defined name of the API key to delete.

        Returns:
            bool: True if the key was successfully deleted from both keyring (if it
                  existed there) and the tracked list. False if the key name was
                  not in the tracked list or if a keyring error occurred preventing
                  deletion (though it will still be removed from the tracked list
                  if a keyring error occurs).
        """
        if key_name not in self._key_names:
            self.logger.warning(f"Attempted to delete non-existent CcAPIKey '{key_name}' from tracking list.")
            return False
        try:
            keyring.delete_password(self._get_keyring_service_name(key_name), key_name)
            self.logger.info(f"CcAPIKey '{key_name}' deleted from keyring.")
        except keyring.errors.PasswordDeleteError:
            # This can happen if the key was in our JSON list but not actually in the keyring.
            # This is acceptable; we'll still remove it from our list.
            self.logger.warning(f"CcAPIKey '{key_name}' not found in keyring for deletion, but will be removed from local tracking list.")
        except keyring.errors.NoKeyringError:
            self.logger.error("No keyring backend found. CcAPIKey cannot be deleted from keyring.", exc_info=True)
            # Even if keyring fails, proceed to remove from our list to maintain consistency from app's perspective.
        except Exception as e: # Catch other potential keyring errors
            self.logger.error(f"Error deleting CcAPIKey '{key_name}' from keyring: {e}", exc_info=True)
            # Proceed to remove from our list.

        # Always remove from the list and save if it was tracked.
        self._key_names.remove(key_name)
        self._save_key_names_to_file()
        self.logger.info(f"CcAPIKey '{key_name}' removed from local tracking list.")
        return True # Considered successful from the manager's perspective if removed from list

    def list_key_names(self) -> List[str]:
        """
        Returns a list of all currently tracked CcApiKey names.

        Returns:
            List[str]: A copy of the list of key names.
        """
        return list(self._key_names) # Return a copy

    def has_key(self, key_name: str) -> bool:
        """
        Checks if a CcApiKey with the given name is being tracked.

        Args:
            key_name (str): The name of the key to check.

        Returns:
            bool: True if a key with the given name is in the list of tracked
                  key names, False otherwise.
        """
        return key_name in self._key_names

    def re_encrypt_keys(self, old_encryption_service: EncryptionService, new_encryption_service: EncryptionService):
        """
        Handles logic related to master password changes.

        For CcApiKeyManager, the actual API key values are stored in the system
        keyring, which typically manages its own encryption independently of the
        application's master password. Therefore, this method does not re-encrypt
        the keys themselves via the provided EncryptionService instances.

        Its primary role here is to update the internal `encryption_service`
        reference to the new one. If, in the future, `ccapikeys.json` were to
        store encrypted metadata related to the keys (beyond just their names),
        this method would be responsible for decrypting that metadata with
        `old_encryption_service` and re-encrypting it with `new_encryption_service`.

        Args:
            old_encryption_service (EncryptionService): The encryption service
                instance configured with the old master password.
            new_encryption_service (EncryptionService): The encryption service
                instance configured with the new master password.
        """
        self.logger.info("CcApiKeyManager: re_encrypt_keys called. Keyring values are not directly "
                         "re-encrypted by this method as keyring handles its own encryption. "
                         "Updating internal encryption_service reference.")
        # If ccapikeys.json stored encrypted metadata, this is where it would be
        # decrypted with old_encryption_service and re-encrypted with new_encryption_service.
        # For now, only the internal reference is updated.
        self.encryption_service = new_encryption_service
        # No need to re-save self._key_names as they are not encrypted themselves by this manager.

    def clear(self):
        """
        Clears all managed CcApiKeys.

        This involves deleting each key from the system keyring and removing its
        name from the tracked list in `ccapikeys.json`. Finally, the
        `ccapikeys.json` file itself is deleted.
        This is a destructive operation and should be used with caution (e.g.,
        during a full application data reset).
        """
        self.logger.info("Attempting to clear all CcApiKeys.")
        all_key_names_copy = list(self._key_names) # Iterate over a copy
        for key_name in all_key_names_copy:
            try:
                keyring.delete_password(self._get_keyring_service_name(key_name), key_name)
                self.logger.debug(f"Deleted CcAPIKey '{key_name}' from keyring during clear operation.")
            except keyring.errors.PasswordDeleteError:
                self.logger.warning(f"CcAPIKey '{key_name}' not found in keyring during clear, but will be removed from local list.")
            except keyring.errors.NoKeyringError:
                self.logger.error("No keyring backend found. CcAPIKeys cannot be fully cleared from keyring.", exc_info=True)
                # Still proceed to clear from local tracking.
            except Exception as e: # Catch other potential keyring errors
                self.logger.error(f"Error deleting CcAPIKey '{key_name}' from keyring during clear: {e}", exc_info=True)
                # Proceed to clear from local list.

        self._key_names.clear() # Clear the internal list
        self._save_key_names_to_file() # Save the now empty list (or create empty file if it didn't exist)

        # Attempt to delete the JSON file itself after clearing its contents
        if os.path.exists(self.keys_file_path):
            try:
                os.remove(self.keys_file_path)
                self.logger.info(f"Removed CcAPIKey names tracking file: {self.keys_file_path}")
            except OSError as e:
                self.logger.error(f"Error removing CcAPIKey names file {self.keys_file_path} during clear: {e}", exc_info=True)
        self.logger.info("All CcApiKeys have been cleared from tracking and attempts were made to remove them from keyring.")

    def update_encryption_service(self, encryption_service: EncryptionService):
        """
        Updates the internal reference to the EncryptionService.

        This is typically called after a master password change when a new
        EncryptionService instance (configured with the new password) is created.

        Args:
            encryption_service (EncryptionService): The new EncryptionService instance.
        """
        self.logger.debug("CcApiKeyManager: Encryption service reference updated.")
        self.encryption_service = encryption_service

if __name__ == '__main__':
    # This block provides an example of how to use CcApiKeyManager.
    # It requires a functioning keyring backend to be installed and configured
    # on the system (e.g., Windows Credential Manager, macOS Keychain, or
    # a libsecret-based service on Linux with appropriate Python bindings like keyring-alt).
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
    main_logger = logging.getLogger(__name__) # Use the module's logger for __main__ block

    # Define a dummy EncryptionService for the example, as the real one depends on master passwords.
    class DummyEncryptionService:
        """A simple dummy EncryptionService for example usage."""
        def encrypt(self, data: bytes) -> bytes:
            """Dummy encryption."""
            main_logger.debug("(DummyEncryptionService) Encrypt called (no-op)")
            return data # No actual encryption
        def decrypt(self, data: bytes) -> bytes:
            """Dummy decryption."""
            main_logger.debug("(DummyEncryptionService) Decrypt called (no-op)")
            return data # No actual decryption

    # Create a temporary data directory for the example
    temp_example_data_dir = "temp_cc_api_data_example"
    if not os.path.exists(temp_example_data_dir):
        os.makedirs(temp_example_data_dir)
    main_logger.info(f"Using temporary data directory: {temp_example_data_dir}")

    dummy_es = DummyEncryptionService()
    # Type ignore for encryption_service compatibility with real EncryptionService
    manager = CcApiKeyManager(data_dir=temp_example_data_dir, encryption_service=dummy_es) # type: ignore

    # Define some test keys
    test_key_name_1 = "ExampleKeyAlpha"
    test_key_value_1 = "alpha_secret_123_xyz"
    test_key_name_2 = "ExampleKeyBeta"
    test_key_value_2 = "beta_secure_789_pqr"

    main_logger.info("--- CcApiKeyManager Example Usage ---")

    # Ensure a clean state for the example by deleting keys if they exist from previous runs
    if manager.has_key(test_key_name_1):
        main_logger.info(f"Pre-deleting existing key: {test_key_name_1}")
        manager.delete_key(test_key_name_1)
    if manager.has_key(test_key_name_2):
        main_logger.info(f"Pre-deleting existing key: {test_key_name_2}")
        manager.delete_key(test_key_name_2)

    main_logger.info(f"Initial list of key names: {manager.list_key_names()}")

    # Add keys
    main_logger.info(f"Adding key: {test_key_name_1}")
    if manager.add_key(test_key_name_1, test_key_value_1):
        main_logger.info(f"Key '{test_key_name_1}' added.")
    else:
        main_logger.error(f"Failed to add key '{test_key_name_1}'. This might indicate a keyring backend issue.")

    main_logger.info(f"Adding key: {test_key_name_2}")
    if manager.add_key(test_key_name_2, test_key_value_2):
        main_logger.info(f"Key '{test_key_name_2}' added.")
    else:
        main_logger.error(f"Failed to add key '{test_key_name_2}'.")

    main_logger.info(f"Current list of key names: {manager.list_key_names()}")

    # Retrieve and verify keys
    retrieved_value_1 = manager.get_key(test_key_name_1)
    if retrieved_value_1:
        main_logger.info(f"Retrieved key '{test_key_name_1}': {'*' * len(retrieved_value_1)}")
        assert retrieved_value_1 == test_key_value_1, "Retrieved key value does not match original!"
    else:
        main_logger.warning(f"Could not retrieve key '{test_key_name_1}'.")

    # Delete a key
    main_logger.info(f"Deleting key: {test_key_name_1}")
    if manager.delete_key(test_key_name_1):
        main_logger.info(f"Key '{test_key_name_1}' deleted.")
    else:
        main_logger.error(f"Failed to delete key '{test_key_name_1}'.") # Should not happen if add was successful

    main_logger.info(f"List of key names after deletion: {manager.list_key_names()}")
    assert not manager.has_key(test_key_name_1), "Deleted key should not be present."
    assert manager.has_key(test_key_name_2), "Other key should still be present."

    # Example of how re_encrypt_keys would be called (it's mostly a no-op for keyring values)
    # old_dummy_es = DummyEncryptionService()
    # new_dummy_es = DummyEncryptionService() # Pretend this is a new service instance
    # manager.re_encrypt_keys(old_dummy_es, new_dummy_es) # type: ignore
    # manager.update_encryption_service(new_dummy_es) # type: ignore
    # main_logger.info("Called re_encrypt_keys and update_encryption_service (updates internal service).")

    # Clear all keys as a final step for the example
    main_logger.info("Clearing all remaining keys...")
    manager.clear()
    main_logger.info(f"List of key names after clear: {manager.list_key_names()}")
    assert not manager.list_key_names(), "Key list should be empty after clear."
    retrieved_value_2_after_clear = manager.get_key(test_key_name_2)
    assert retrieved_value_2_after_clear is None, \
        f"Key '{test_key_name_2}' should be None after clear, but was retrieved."

    main_logger.info("--- CcApiKeyManager Example Finished ---")
    main_logger.info(f"Note: To fully clean up, you might need to manually remove keys "
                     f"from your system keyring if the example was interrupted or if "
                     f"keyring.delete_password failed for external reasons. Service names "
                     f"would start with '{KEYRING_SERVICE_NAME_PREFIX}'.")

    # Clean up the temporary directory used by the example
    try:
        import shutil
        shutil.rmtree(temp_example_data_dir)
        main_logger.info(f"Successfully removed temporary data directory: {temp_example_data_dir}")
    except Exception as e:
        main_logger.error(f"Error removing temporary data directory {temp_example_data_dir}: {e}")
