"""Manages API keys for different services, using keyring if available,
otherwise falling back to a JSON file. Keys are encrypted if an
EncryptionService is provided.

This module provides the `ApiKeyManager` class, responsible for abstracting
the storage and retrieval of API keys for various AI services. It prioritizes
using the system's keyring for secure storage. If keyring access fails,
it defaults to a JSON file (`data/apikeys.json`).

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


class ApiKeyQuery:
    """Represents a query for an API key.

    This class is used to encapsulate the parameters needed to retrieve
    an API key from the `ApiKeyManager`. It includes the slot ID and
    the specific key ID for the service.

    Attributes:
        apikey_slot_id (str): The slot ID for the API key.
        apikey_id (str): The specific ID of the API key within that slot.
    """
    def __init__(self, apikey_slot_id: str, apikey_id: str):
        """Initializes an ApiKeyQuery instance.

        Args:
            apikey_slot_id: The slot ID for the API key.
            apikey_id: The specific ID of the API key within the slot.
        """
        self._apikey_slot_id = apikey_slot_id
        self._apikey_id = apikey_id

    @property
    def apikey_slot_id(self) -> str:
        """Gets the slot ID for the API key.

        Returns:
            str: The slot ID for the API key.
        """
        return self._apikey_slot_id

    @property
    def apikey_id(self) -> str:
        """Gets the specific ID of the API key.

        Returns:
            str: The specific ID of the API key within the slot.
        """
        return self._apikey_id

    def to_dict(self) -> dict:
        """Converts the ApiKeyQuery to a dictionary.

        Returns:
            dict: A dictionary representation of the ApiKeyQuery.
        """
        return {
            "apikey_slot_id": self._apikey_slot_id,
            "apikey_id": self._apikey_id
        }

    @staticmethod
    def from_dict(data: dict) -> 'ApiKeyQuery':
        """Creates an ApiKeyQuery from a dictionary.

        Args:
            data (dict): A dictionary containing the API key query parameters.

        Returns:
            ApiKeyQuery: An instance of ApiKeyQuery initialized with the provided data.
        """
        return ApiKeyQuery(
            apikey_slot_id=data.get("apikey_slot_id", ""),
            apikey_id=data.get("apikey_id", "")
        )


class ApiKeyManager:
    """Manages API keys, using system keyring or an encrypted JSON fallback.

    This manager handles saving, loading, and deleting API keys. It attempts
    to use the system's keyring for secure storage. If keyring is unavailable
    or inaccessible, it falls back to storing keys in an encrypted JSON file
    (`data/apikey_manager.json`), provided an `EncryptionService` is available.

    Attributes:
        encryption_service (EncryptionService): Service used for
            encrypting/decrypting keys. If None, secure operations will fail.
    """
    def __init__(self, encryption_service: EncryptionService, data_path: str = None):
        """Initializes the ApiKeyManager.

        Determines if keyring is available and sets up the fallback storage path.
        Loads keys from the fallback file, which might include a manifest of
        keyring-managed service names.

        Args:
            encryption_service (EncryptionService): The service to use
                for encrypting and decrypting API keys. If not provided,
                saving or loading keys will raise a RuntimeError.
        """

        if not data_path:
            data_path = os.path.join("data", "apikey_manager.json")

        if not encryption_service:
            raise RuntimeError("Encryption service must be provided for ApiKeyManager.")

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
        `apikey_slot_id_to_apikey_id_list_dict` exists.
        """
        if not self._data:
            self._data = {}
        if 'apikey_slot_id_to_apikey_id_list_dict' not in self._data:
            self._data['apikey_slot_id_to_apikey_id_list_dict'] = {}

    def _save_data(self):
        """Saves the current data to the fallback JSON file."""
        if not os.path.exists(os.path.dirname(self.data_path)):
            os.makedirs(os.path.dirname(self.data_path))
        with open(self.data_path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=4)

    def _get_keyring_service_name(self, apikey_slot_id: str) -> str:
        """Generates a unique service name for keyring storage."""
        return f"{ENCRYPTED_SERVICE_NAME_PREFIX}_{apikey_slot_id}"

    def set_apikey(self, apikey_query: ApiKeyQuery, apikey: str):
        """Saves an API key for a given service, encrypting it before storage.

        The API key is encrypted using the configured `EncryptionService`.
        It's then stored in the system keyring if available, or in the
        fallback JSON file. If keyring is used, the `service_name` is added
        to a manifest list in the fallback file for tracking.

        Args:
            service_name (str): The name of the service (e.g., "OpenAI", "Gemini").
            apikey (str): The API key to save.

        Raises:
            RuntimeError: If the `EncryptionService` is not available.
            ValueError: If `service_name` or `apikey` is empty.
        """
        if not self.encryption_service:
            raise RuntimeError("Encryption service not available. Cannot save key.")
        if not apikey_query:
            raise ValueError("Service name and API key cannot be empty.")

        apikey_slot_id = apikey_query.apikey_slot_id
        apikey_id = apikey_query.apikey_id
        encrypted_key = self.encryption_service.encrypt(apikey)

        keyring.set_password(self._get_keyring_service_name(apikey_slot_id), apikey_id, encrypted_key)

        if apikey_slot_id not in self._data['apikey_slot_id_to_apikey_id_list_dict']:
            self._data['apikey_slot_id_to_apikey_id_list_dict'][apikey_slot_id] = []
        if apikey_id not in self._data['apikey_slot_id_to_apikey_id_list_dict'][apikey_slot_id]:
            self._data['apikey_slot_id_to_apikey_id_list_dict'][apikey_slot_id].append(apikey_id)
        self._save_data()

    def get_apikey(self, apikey_query: ApiKeyQuery) -> str | None:
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
        if not apikey_query:
            raise ValueError("Service name and API key ID cannot be empty.")

        apikey_slot_id = apikey_query.apikey_slot_id
        apikey_id = apikey_query.apikey_id
        encrypted_key = keyring.get_password(self._get_keyring_service_name(apikey_slot_id), apikey_id)

        decrypted_key = self.encryption_service.decrypt(encrypted_key)
        if decrypted_key is None:
            print(f"Failed to decrypt key for {apikey_id}. It might be corrupted or an old format.", file=sys.stderr)
            return None
        return decrypted_key

    def delete_apikey(self, apikey_query: ApiKeyQuery):
        """Deletes an API key from keyring and the local data index.

        Args:
            apikey_query: An `ApiKeyQuery` object specifying the key to delete.
        """
        if not apikey_query:
            return
        apikey_slot_id = apikey_query.apikey_slot_id
        apikey_id = apikey_query.apikey_id

        keyring.delete_password(self._get_keyring_service_name(apikey_slot_id), apikey_id)
        if apikey_slot_id in self._data['apikey_slot_id_to_apikey_id_list_dict']:
            if apikey_id in self._data['apikey_slot_id_to_apikey_id_list_dict'][apikey_slot_id]:
                self._data['apikey_slot_id_to_apikey_id_list_dict'][apikey_slot_id].remove(apikey_id)
        self._save_data()

    def get_apikey_list(self, query_list: list[ApiKeyQuery]) -> list[str]:
        """Retrieves a list of API keys for the specified services.

        This method returns a list of decrypted API keys for the provided
        API key queries. If a key cannot be found or decrypted, it is skipped.

        Args:
            query_list (list[ApiKeyQuery]): List of `ApiKeyQuery` objects
                specifying which keys to retrieve.

        Returns:
            list[str]: List of decrypted API keys.
        """
        if not self.encryption_service:
            raise RuntimeError("Encryption service not available. Cannot get keys.")

        ret_apikey_list = []
        for query in query_list:
            apikey = self.get_apikey(query)
            if apikey is not None:
                ret_apikey_list.append(apikey)
        return ret_apikey_list

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

        if 'apikey_slot_id_to_apikey_id_list_dict' not in self._data:
            return # Nothing to re-encrypt if no keys are stored

        apikey_slot_id_to_apikey_id_list_dict = self._data['apikey_slot_id_to_apikey_id_list_dict']
        for apikey_slot_id, apikey_id_list in apikey_slot_id_to_apikey_id_list_dict.items():
            for apikey_id in apikey_id_list:
                try:
                    encrypted_val = keyring.get_password(self._get_keyring_service_name(apikey_slot_id), apikey_id)
                    if not encrypted_val:
                        print(f"No key found in keyring for {apikey_id}, skipping re-encryption.", file=sys.stderr)
                        continue

                    plain_key = old_encryption_service.decrypt(encrypted_val)
                    if not plain_key:
                        print(f"Failed to decrypt key for {apikey_id} using old encryption service. Cannot re-encrypt.", file=sys.stderr)
                        continue

                    new_encrypted_key = new_encryption_service.encrypt(plain_key)
                    keyring.set_password(self._get_keyring_service_name(apikey_slot_id), apikey_id, new_encrypted_key)
                    print(f"Successfully re-encrypted key for {apikey_id} in keyring.")
                except Exception as e:
                    print(f"Error re-encrypting key for {apikey_id} in keyring: {e}", file=sys.stderr)


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
        apikey_slot_id_to_apikey_id_list_dict = self._data['apikey_slot_id_to_apikey_id_list_dict']
        for apikey_slot_id, apikey_id_list in apikey_slot_id_to_apikey_id_list_dict.items():
            for apikey_id in apikey_id_list:
                try:
                    keyring.delete_password(self._get_keyring_service_name(apikey_slot_id), apikey_id)
                    print(f"Deleted key for {apikey_id} from keyring.")
                except Exception as e:
                    print(f"Error deleting key for {apikey_id} from keyring: {e}", file=sys.stderr)

        self._data = None

        if os.path.exists(self.data_path):
            try:
                os.remove(self.data_path)
                print(f"Removed data file: {self.data_path}")
            except OSError as e:
                print(f"Error removing data file {self.data_path}: {e}", file=sys.stderr)

        self._fix_data()  # Reset to empty structure

    def get_available_apikey_query_list(self) -> list[ApiKeyQuery]:
        """Retrieves a list of all available API key queries.

        This method returns a list of `ApiKeyQuery` instances for all
        API keys stored in the system keyring or the fallback JSON file.
        It includes both the slot ID and the specific key ID for each service.

        Returns:
            list[ApiKeyQuery]: A list of ApiKeyQuery instances for all available API keys.
        """
        if not self._data or 'apikey_slot_id_to_apikey_id_list_dict' not in self._data:
            return []

        apikey_query_list = []
        for apikey_slot_id, apikey_id_list in self._data['apikey_slot_id_to_apikey_id_list_dict'].items():
            for apikey_id in apikey_id_list:
                apikey_query_list.append(ApiKeyQuery(apikey_slot_id, apikey_id))
        return apikey_query_list
