"""Manages API keys for different services, using keyring if available,
otherwise falling back to a JSON file. Keys are encrypted if an
EncryptionService is provided.

This module provides the `ThirdPartyApiKeyManager` class, responsible for abstracting
the storage and retrieval of API keys for various AI services. It prioritizes
using the system's keyring for secure storage. If keyring access fails,
it defaults to a JSON file (`data/thirdpartyapikeys.json`).

When an `EncryptionService` instance is provided during initialization, all API
keys are encrypted before being stored and decrypted upon retrieval. This
enhances security, especially for the fallback JSON file.

The `ENCRYPTED_SERVICE_NAME_PREFIX` is used for keyring service names to
prevent conflicts. A manifest key, `_KEYRING_MANAGED_SERVICES_KEY`, is used
within the fallback JSON file to track service names whose keys are stored in
the system keyring, aiding in operations like re-encryption or clearing all data.
"""
import json
import os
import sys

import keyring

from .encryption_service import EncryptionService # Assuming EncryptionService is in encryption_service.py

ENCRYPTED_SERVICE_NAME_PREFIX = "CogniChoir_Encrypted"


class ThirdPartyApiKeyQuery:
    """Represents a query for an API key.

    This class is used to encapsulate the parameters needed to retrieve
    an API key from the `ThirdPartyApiKeyManager`. It includes the slot ID and
    the specific key ID for the service.

    Attributes:
        thirdpartyapikey_slot_id (str): The slot ID for the API key.
        thirdpartyapikey_id (str): The specific ID of the API key within that slot.
    """
    def __init__(self, thirdpartyapikey_slot_id: str, thirdpartyapikey_id: str):
        """Initializes an ThirdPartyApiKeyQuery instance.

        Args:
            thirdpartyapikey_slot_id: The slot ID for the API key.
            thirdpartyapikey_id: The specific ID of the API key within the slot.
        """
        self._thirdpartyapikey_slot_id = thirdpartyapikey_slot_id
        self._thirdpartyapikey_id = thirdpartyapikey_id

    @property
    def thirdpartyapikey_slot_id(self) -> str:
        """Gets the slot ID for the API key.

        Returns:
            str: The slot ID for the API key.
        """
        return self._thirdpartyapikey_slot_id

    @property
    def thirdpartyapikey_id(self) -> str:
        """Gets the specific ID of the API key.

        Returns:
            str: The specific ID of the API key within the slot.
        """
        return self._thirdpartyapikey_id

    def to_dict(self) -> dict:
        """Converts the ThirdPartyApiKeyQuery to a dictionary.

        Returns:
            dict: A dictionary representation of the ThirdPartyApiKeyQuery.
        """
        return {
            "thirdpartyapikey_slot_id": self._thirdpartyapikey_slot_id,
            "thirdpartyapikey_id": self._thirdpartyapikey_id
        }

    @staticmethod
    def from_dict(data: dict) -> 'ThirdPartyApiKeyQuery':
        """Creates an ThirdPartyApiKeyQuery from a dictionary.

        Args:
            data (dict): A dictionary containing the API key query parameters.

        Returns:
            ThirdPartyApiKeyQuery: An instance of ThirdPartyApiKeyQuery initialized with the provided data.
        """
        return ThirdPartyApiKeyQuery(
            thirdpartyapikey_slot_id=data.get("thirdpartyapikey_slot_id", ""),
            thirdpartyapikey_id=data.get("thirdpartyapikey_id", "")
        )


class ThirdPartyApiKeyManager:
    """Manages API keys, using system keyring or an encrypted JSON fallback.

    This manager handles saving, loading, and deleting API keys. It attempts
    to use the system's keyring for secure storage. If keyring is unavailable
    or inaccessible, it falls back to storing keys in an encrypted JSON file
    (`data/thirdpartyapikey_manager.json`), provided an `EncryptionService` is available.

    Attributes:
        encryption_service (EncryptionService): Service used for
            encrypting/decrypting keys. If None, secure operations will fail.
    """
    def __init__(self, encryption_service: EncryptionService, data_path: str = None):
        """Initializes the ThirdPartyApiKeyManager.

        Determines if keyring is available and sets up the fallback storage path.
        Loads keys from the fallback file, which might include a manifest of
        keyring-managed service names.

        Args:
            encryption_service (EncryptionService): The service to use
                for encrypting and decrypting API keys. If not provided,
                saving or loading keys will raise a RuntimeError.
        """

        if not data_path:
            data_path = os.path.join("data", "thirdpartyapikey_manager.json")

        if not encryption_service:
            raise RuntimeError("Encryption service must be provided for ThirdPartyApiKeyManager.")

        self.encryption_service = encryption_service
        self.data_path = data_path

        self._data : dict = {}

        # Test if keyring is accessible
        keyring.get_password(self._get_keyring_service_name("_test_slot_id"), "_test_init_user")

        # self._ensure_data_dir_exists()
        self._load_data()


    # def _ensure_data_dir_exists(self):
    #     """Ensures the data directory for the fallback JSON file exists."""
    #     if not os.path.exists(self.data_folder_path):
    #         try:
    #             os.makedirs(self.data_folder_path)
    #         except OSError as e:
    #             print(f"Error creating data directory {self.data_folder_path}: {e}", file=sys.stderr)

    def _load_data(self):
        """Loads API key data from the JSON file.

        If the data file exists, it's loaded into `self._data`.
        Otherwise, `self._data` is set to None. It then calls `_fix_data`
        to ensure the data structure is initialized.
        """
        if os.path.exists(self.data_path):
            with open(self.data_path, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
        else:
            self._data = None
        self._fix_data()

    def _fix_data(self):
        """Ensures the data structure for API keys is correctly initialized.

        If `self._data` is None (e.g., file didn't exist), it initializes it
        as an empty dictionary. It also ensures that the nested dictionary
        `thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict` exists.
        """
        if not self._data:
            self._data = {}
        if 'thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict' not in self._data:
            self._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'] = {}

    def _save_data(self):
        """Saves the current data to the fallback JSON file."""
        if not os.path.exists(os.path.dirname(self.data_path)):
            os.makedirs(os.path.dirname(self.data_path))
        with open(self.data_path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=4)

    def _get_keyring_service_name(self, thirdpartyapikey_slot_id: str) -> str:
        """Generates a unique service name for keyring storage."""
        return f"{ENCRYPTED_SERVICE_NAME_PREFIX}_{thirdpartyapikey_slot_id}"

    def set_thirdpartyapikey(self, thirdpartyapikey_query: ThirdPartyApiKeyQuery, thirdpartyapikey: str):
        """Saves an API key for a given service, encrypting it before storage.

        The API key is encrypted using the configured `EncryptionService`.
        It's then stored in the system keyring if available, or in the
        fallback JSON file. If keyring is used, the `service_name` is added
        to a manifest list in the fallback file for tracking.

        Args:
            service_name (str): The name of the service (e.g., "OpenAI", "Gemini").
            thirdpartyapikey (str): The API key to save.

        Raises:
            RuntimeError: If the `EncryptionService` is not available.
            ValueError: If `service_name` or `thirdpartyapikey` is empty.
        """
        if not self.encryption_service:
            raise RuntimeError("Encryption service not available. Cannot save key.")
        if not thirdpartyapikey_query: # Checks if the ThirdPartyApiKeyQuery object itself is None
            # This message might need refinement given ThirdPartyApiKeyQuery structure.
            # For now, the critical check is for the thirdpartyapikey string itself.
            raise ValueError("ThirdPartyApiKeyQuery object cannot be None.")
        if not thirdpartyapikey: # Check for empty API key string
            raise ValueError("API key cannot be empty.")

        thirdpartyapikey_slot_id = thirdpartyapikey_query.thirdpartyapikey_slot_id
        thirdpartyapikey_id = thirdpartyapikey_query.thirdpartyapikey_id
        encrypted_key = self.encryption_service.encrypt(thirdpartyapikey)

        keyring.set_password(self._get_keyring_service_name(thirdpartyapikey_slot_id), thirdpartyapikey_id, encrypted_key)

        if thirdpartyapikey_slot_id not in self._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict']:
            self._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'][thirdpartyapikey_slot_id] = []
        if thirdpartyapikey_id not in self._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'][thirdpartyapikey_slot_id]:
            self._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'][thirdpartyapikey_slot_id].append(thirdpartyapikey_id)
        self._save_data()

    def get_thirdpartyapikey(self, thirdpartyapikey_query: ThirdPartyApiKeyQuery) -> str | None:
        """Loads and decrypts an API key for a given service.

        Retrieves the encrypted key from the system keyring or fallback JSON file,
        then decrypts it using the configured `EncryptionService`.

        Args:
            service_name (str): The name of the service whose key is to be loaded.

        Returns:
            Optional[str]: The decrypted API key if found and successfully
                           decrypted, otherwise None.
        """
        if not self.encryption_service:
            raise RuntimeError("Encryption service not available. Cannot load key.")
        if not thirdpartyapikey_query:
            raise ValueError("ThirdPartyApiKeyQuery object cannot be None.")
        if not thirdpartyapikey_query.thirdpartyapikey_slot_id or not thirdpartyapikey_query.thirdpartyapikey_id:
            # Or handle differently, e.g., return None if keyring would fail with empty strings
            print(f"Warning: Attempting to get API key with empty slot_id or key_id in query: {thirdpartyapikey_query.to_dict()}", file=sys.stderr)
            # Keyring might return None or error with empty strings; let it try, or return None early.
            # For now, let keyring handle it, as behavior might vary by backend.
            # Consider raising ValueError here if empty slot/key ID is strictly invalid.

        thirdpartyapikey_slot_id = thirdpartyapikey_query.thirdpartyapikey_slot_id
        thirdpartyapikey_id = thirdpartyapikey_query.thirdpartyapikey_id
        encrypted_key = keyring.get_password(self._get_keyring_service_name(thirdpartyapikey_slot_id), thirdpartyapikey_id)

        decrypted_key = self.encryption_service.decrypt(encrypted_key)
        if decrypted_key is None:
            print(f"Failed to decrypt key for {thirdpartyapikey_id}. It might be corrupted or an old format.", file=sys.stderr)
            return None
        return decrypted_key

    def delete_thirdpartyapikey(self, thirdpartyapikey_query: ThirdPartyApiKeyQuery):
        """Deletes an API key from keyring and the local data index.

        Args:
            thirdpartyapikey_query: An `ThirdPartyApiKeyQuery` object specifying the key to delete.
        """
        if not thirdpartyapikey_query:
            return
        thirdpartyapikey_slot_id = thirdpartyapikey_query.thirdpartyapikey_slot_id
        thirdpartyapikey_id = thirdpartyapikey_query.thirdpartyapikey_id

        keyring.delete_password(self._get_keyring_service_name(thirdpartyapikey_slot_id), thirdpartyapikey_id)
        if thirdpartyapikey_slot_id in self._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict']:
            if thirdpartyapikey_id in self._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'][thirdpartyapikey_slot_id]:
                self._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'][thirdpartyapikey_slot_id].remove(thirdpartyapikey_id)
        self._save_data()

    def get_thirdpartyapikey_list(self, query_list: list[ThirdPartyApiKeyQuery]) -> list[str]:
        """Retrieves a list of API keys for the specified services.

        This method returns a list of decrypted API keys for the provided
        API key queries. If a key cannot be found or decrypted, it is skipped.

        Args:
            query_list (list[ThirdPartyApiKeyQuery]): List of `ThirdPartyApiKeyQuery` objects
                specifying which keys to retrieve.

        Returns:
            list[str]: List of decrypted API keys.
        """
        if not self.encryption_service:
            raise RuntimeError("Encryption service not available. Cannot get keys.")

        ret_thirdpartyapikey_list = []
        for query in query_list:
            thirdpartyapikey = self.get_thirdpartyapikey(query)
            if thirdpartyapikey is not None:
                ret_thirdpartyapikey_list.append(thirdpartyapikey)
        return ret_thirdpartyapikey_list

    def re_encrypt(self, old_encryption_service: EncryptionService, new_encryption_service: EncryptionService):
        """Re-encrypts all stored API keys with a new encryption service.

        This method is crucial when the master password changes, requiring a new
        `EncryptionService` instance. It iterates through all known API keys
        (from keyring via manifest, or directly from fallback cache), decrypts
        them using `old_encryption_service`, re-encrypts them with
        `new_encryption_service`, and saves them back to their original storage
        location (keyring or fallback file).

        After successful re-encryption, `self.encryption_service` is updated
        to `new_encryption_service`.

        Args:
            old_encryption_service (EncryptionService): The encryption service
                that was used for the current encryption of keys.
            new_encryption_service (EncryptionService): The new encryption service
                to use for re-encrypting the keys.
        """
        print("Re-encrypting all API keys...")

        if 'thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict' not in self._data:
            return # Nothing to re-encrypt if no keys are stored

        thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict = self._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict']
        for thirdpartyapikey_slot_id, thirdpartyapikey_id_list in thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict.items():
            for thirdpartyapikey_id in thirdpartyapikey_id_list:
                try:
                    encrypted_val = keyring.get_password(self._get_keyring_service_name(thirdpartyapikey_slot_id), thirdpartyapikey_id)
                    if not encrypted_val:
                        print(f"No key found in keyring for {thirdpartyapikey_id}, skipping re-encryption.", file=sys.stderr)
                        continue

                    plain_key = old_encryption_service.decrypt(encrypted_val)
                    if not plain_key:
                        print(f"Failed to decrypt key for {thirdpartyapikey_id} using old encryption service. Cannot re-encrypt.", file=sys.stderr)
                        continue

                    new_encrypted_key = new_encryption_service.encrypt(plain_key)
                    keyring.set_password(self._get_keyring_service_name(thirdpartyapikey_slot_id), thirdpartyapikey_id, new_encrypted_key)
                    print(f"Successfully re-encrypted key for {thirdpartyapikey_id} in keyring.")
                except Exception as e:
                    print(f"Error re-encrypting key for {thirdpartyapikey_id} in keyring: {e}", file=sys.stderr)


    def clear(self):
        """Clears all stored API keys and associated encryption data.

        This method performs a comprehensive cleanup:
        - If using keyring, it iterates through the service names stored in the
          `_keyring_managed_services` manifest (in the fallback JSON) and
          deletes each corresponding password from the system keyring. It then
          clears this manifest.
        - If using fallback storage, it clears all keys from `_keys_cache`
          (except the manifest key itself, which is emptied).
        - Saves the (now largely empty) `_keys_cache` to the fallback JSON file.
        - If an `encryption_service` is configured, its
          `clear_encryption_salt()` method is called to delete the salt file.
          If no service is configured (e.g., if called after master password
          was cleared), it attempts to remove the default salt file directly.
        """
        print("Clearing all API keys and data...")
        thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict = self._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict']
        for thirdpartyapikey_slot_id, thirdpartyapikey_id_list in thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict.items():
            for thirdpartyapikey_id in thirdpartyapikey_id_list:
                try:
                    keyring.delete_password(self._get_keyring_service_name(thirdpartyapikey_slot_id), thirdpartyapikey_id)
                    print(f"Deleted key for {thirdpartyapikey_id} from keyring.")
                except Exception as e:
                    print(f"Error deleting key for {thirdpartyapikey_id} from keyring: {e}", file=sys.stderr)

        self._data = None

        if os.path.exists(self.data_path):
            try:
                os.remove(self.data_path)
                print(f"Removed data file: {self.data_path}")
            except OSError as e:
                print(f"Error removing data file {self.data_path}: {e}", file=sys.stderr)

        self._fix_data()  # Reset to empty structure

    def get_available_thirdpartyapikey_query_list(self) -> list[ThirdPartyApiKeyQuery]:
        """Retrieves a list of all available API key queries.

        This method returns a list of `ThirdPartyApiKeyQuery` instances for all
        API keys stored in the system keyring or the fallback JSON file.
        It includes both the slot ID and the specific key ID for each service.

        Returns:
            list[ThirdPartyApiKeyQuery]: A list of ThirdPartyApiKeyQuery instances for all available API keys.
        """
        if not self._data or 'thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict' not in self._data:
            return []

        thirdpartyapikey_query_list = []
        for thirdpartyapikey_slot_id, thirdpartyapikey_id_list in self._data['thirdpartyapikey_slot_id_to_thirdpartyapikey_id_list_dict'].items():
            for thirdpartyapikey_id in thirdpartyapikey_id_list:
                thirdpartyapikey_query_list.append(ThirdPartyApiKeyQuery(thirdpartyapikey_slot_id, thirdpartyapikey_id))
        return thirdpartyapikey_query_list
