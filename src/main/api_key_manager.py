"""Manages API keys for different services, using keyring if available,
otherwise falling back to a JSON file. Keys are encrypted if an
EncryptionService is provided.

This module provides the `ApiKeyManager` class, responsible for abstracting
the storage and retrieval of API keys for various AI services. It prioritizes
using the system's keyring for secure storage. If keyring access fails,
it defaults to a JSON file (`data/api_keys.json`).

When an `EncryptionService` instance is provided during initialization, all API
keys are encrypted before being stored and decrypted upon retrieval. This
enhances security, especially for the fallback JSON file.

The `ENCRYPTED_SERVICE_NAME_PREFIX` is used for keyring service names to
prevent conflicts. A manifest key, `_KEYRING_MANAGED_SERVICES_KEY`, is used
within the fallback JSON file to track service names whose keys are stored in
the system keyring, aiding in operations like re-encryption or clearing all data.
"""
import keyring
import json
import os
import sys
from .encryption_service import EncryptionService, ENCRYPTION_SALT_FILE # Assuming EncryptionService is in encryption_service.py

ENCRYPTED_SERVICE_NAME_PREFIX = "CogniChoir_Encrypted"
_KEYRING_MANAGED_SERVICES_KEY = "_keyring_managed_services"


class ApiKeyManager:
    """Manages API keys, using system keyring or an encrypted JSON fallback.

    This manager handles saving, loading, and deleting API keys. It attempts
    to use the system's keyring for secure storage. If keyring is unavailable
    or inaccessible, it falls back to storing keys in an encrypted JSON file
    (`data/api_keys.json`), provided an `EncryptionService` is available.

    Attributes:
        encryption_service (Optional[EncryptionService]): Service used for
            encrypting/decrypting keys. If None, secure operations will fail.
        use_keyring (bool): True if keyring is accessible and used, False otherwise.
        fallback_file_path (str): Path to the JSON file used for fallback storage.
        _keys_cache (dict): In-memory cache for fallback keys and keyring manifest.
    """
    def __init__(self, encryption_service: EncryptionService | None = None):
        """Initializes the ApiKeyManager.

        Determines if keyring is available and sets up the fallback storage path.
        Loads keys from the fallback file, which might include a manifest of
        keyring-managed service names.

        Args:
            encryption_service (Optional[EncryptionService]): The service to use
                for encrypting and decrypting API keys. If not provided,
                saving or loading keys will raise a RuntimeError.
        """
        self.encryption_service = encryption_service
        self.use_keyring = True
        self.fallback_file_path = os.path.join("data", "api_keys.json")

        try:
            # Test if keyring is accessible
            keyring.get_password(self._get_service_key_name("_test_init"), "_test_init_user")
        except keyring.errors.NoKeyringError:
            self.use_keyring = False
            # print(f"Failed to initialize keyring. Using fallback JSON file for API keys: {self.fallback_file_path}", file=sys.stderr)
        except Exception as e: # Other potential keyring errors
            self.use_keyring = False
            # print(f"Could not access keyring due to {type(e).__name__}. Using fallback JSON file for API keys: {self.fallback_file_path}", file=sys.stderr)

        self._ensure_data_dir_exists()
        # _keys_cache always loaded, as it might contain the manifest for keyring services
        self._keys_cache = self._load_keys_from_fallback()


    def _ensure_data_dir_exists(self):
        """Ensures the data directory for the fallback JSON file exists."""
        data_dir = os.path.dirname(self.fallback_file_path)
        if not os.path.exists(data_dir):
            try:
                os.makedirs(data_dir)
            except OSError as e:
                print(f"Error creating data directory {data_dir}: {e}", file=sys.stderr)

    def _get_service_key_name(self, service_name: str) -> str:
        """Generates a unique service name for keyring storage."""
        return f"{ENCRYPTED_SERVICE_NAME_PREFIX}_{service_name}"

    def _load_keys_from_fallback(self) -> dict:
        """Loads data from the fallback JSON file."""
        if not os.path.exists(self.fallback_file_path):
            return {_KEYRING_MANAGED_SERVICES_KEY: []} # Initialize manifest if file doesn't exist
        try:
            with open(self.fallback_file_path, 'r') as f:
                data = json.load(f)
                if not isinstance(data, dict): # Ensure it's a dict
                    print("Fallback file is not a valid JSON dictionary. Initializing.", file=sys.stderr)
                    return {_KEYRING_MANAGED_SERVICES_KEY: []}
                if _KEYRING_MANAGED_SERVICES_KEY not in data: # Ensure manifest key exists
                    data[_KEYRING_MANAGED_SERVICES_KEY] = []
                return data
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading API keys from fallback file: {e}. Initializing with empty cache.", file=sys.stderr)
            return {_KEYRING_MANAGED_SERVICES_KEY: []} # Return initialized manifest on error

    def _save_keys_to_fallback(self, keys_data: dict):
        """Saves data (including manifest) to the fallback JSON file."""
        self._ensure_data_dir_exists()
        try:
            with open(self.fallback_file_path, 'w') as f:
                json.dump(keys_data, f, indent=4)
        except IOError as e:
            print(f"Error saving API keys to fallback file: {e}", file=sys.stderr)

    def save_key(self, service_name: str, api_key: str):
        """Saves an API key for a given service, encrypting it before storage.

        The API key is encrypted using the configured `EncryptionService`.
        It's then stored in the system keyring if available, or in the
        fallback JSON file. If keyring is used, the `service_name` is added
        to a manifest list in the fallback file for tracking.

        Args:
            service_name (str): The name of the service (e.g., "OpenAI", "Gemini").
            api_key (str): The API key to save.

        Raises:
            RuntimeError: If the `EncryptionService` is not available.
            ValueError: If `service_name` or `api_key` is empty.
        """
        if not self.encryption_service:
            raise RuntimeError("Encryption service not available. Cannot save key.")
        if not service_name or not api_key:
            raise ValueError("Service name and API key cannot be empty.")

        encrypted_key = self.encryption_service.encrypt(api_key)

        if self.use_keyring:
            try:
                keyring.set_password(self._get_service_key_name(service_name), service_name, encrypted_key)
                # Add to manifest and save
                if service_name not in self._keys_cache.get(_KEYRING_MANAGED_SERVICES_KEY, []):
                    self._keys_cache.setdefault(_KEYRING_MANAGED_SERVICES_KEY, []).append(service_name)
                    self._save_keys_to_fallback(self._keys_cache)
            except Exception as e:
                print(f"Error setting key in keyring for {service_name}: {e}", file=sys.stderr)
                # Fallback to JSON if keyring fails? For now, no. Let it fail.
        else:
            self._keys_cache[service_name] = encrypted_key
            self._save_keys_to_fallback(self._keys_cache)

    def load_key(self, service_name: str) -> str | None:
        """Loads and decrypts an API key for a given service.

        Retrieves the encrypted key from the system keyring or fallback JSON file,
        then decrypts it using the configured `EncryptionService`.

        Args:
            service_name (str): The name of the service whose key is to be loaded.

        Returns:
            Optional[str]: The decrypted API key if found and successfully
                           decrypted, otherwise None.

        Raises:
            RuntimeError: If the `EncryptionService` is not available.
        """
        if not self.encryption_service:
            raise RuntimeError("Encryption service not available. Cannot load key.")
        if not service_name:
            return None

        encrypted_key = None
        if self.use_keyring:
            try:
                encrypted_key = keyring.get_password(self._get_service_key_name(service_name), service_name)
            except Exception as e:
                print(f"Error getting key from keyring for {service_name}: {e}", file=sys.stderr)
                return None
        else:
            encrypted_key = self._keys_cache.get(service_name)

        if encrypted_key:
            decrypted_key = self.encryption_service.decrypt(encrypted_key)
            if decrypted_key is None:
                print(f"Failed to decrypt key for {service_name}. It might be corrupted or an old format.", file=sys.stderr)
            return decrypted_key
        return None

    def delete_key(self, service_name: str):
        """Deletes an API key for a given service."""
        if not service_name:
            return

        if self.use_keyring:
            try:
                keyring.delete_password(self._get_service_key_name(service_name), service_name)
                # Remove from manifest and save
                managed_services = self._keys_cache.get(_KEYRING_MANAGED_SERVICES_KEY, [])
                if service_name in managed_services:
                    managed_services.remove(service_name)
                    self._save_keys_to_fallback(self._keys_cache)
            except keyring.errors.PasswordDeleteError:
                pass # Key not found, considered deleted
            except Exception as e:
                print(f"Error deleting key from keyring for {service_name}: {e}", file=sys.stderr)
        else:
            if service_name in self._keys_cache:
                del self._keys_cache[service_name]
                self._save_keys_to_fallback(self._keys_cache)

    def re_encrypt_all_keys(self, old_encryption_service: EncryptionService, new_encryption_service: EncryptionService):
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
        if self.use_keyring:
            keyring_services = list(self._keys_cache.get(_KEYRING_MANAGED_SERVICES_KEY, [])) # Iterate copy
            if not keyring_services:
                print("No keyring-managed services found in manifest to re-encrypt.")

            for service_name in keyring_services:
                key_name_in_keyring = self._get_service_key_name(service_name)
                try:
                    encrypted_val = keyring.get_password(key_name_in_keyring, service_name)
                    if not encrypted_val:
                        print(f"No key found in keyring for {service_name}, skipping re-encryption.", file=sys.stderr)
                        continue

                    plain_key = old_encryption_service.decrypt(encrypted_val)
                    if plain_key:
                        new_encrypted_key = new_encryption_service.encrypt(plain_key)
                        keyring.set_password(key_name_in_keyring, service_name, new_encrypted_key)
                        print(f"Successfully re-encrypted key for {service_name} in keyring.")
                    else:
                        print(f"Failed to decrypt key for {service_name} from keyring using old key. Cannot re-encrypt.", file=sys.stderr)
                except Exception as e:
                    print(f"Error re-encrypting key for {service_name} in keyring: {e}", file=sys.stderr)
        else: # Fallback JSON file
            updated_keys = 0
            # Iterate over a copy of keys if modifying the cache directly
            for service_name, encrypted_val in list(self._keys_cache.items()):
                if service_name == _KEYRING_MANAGED_SERVICES_KEY:
                    continue # Skip manifest key itself

                plain_key = old_encryption_service.decrypt(encrypted_val)
                if plain_key:
                    self._keys_cache[service_name] = new_encryption_service.encrypt(plain_key)
                    updated_keys +=1
                else:
                    print(f"Failed to decrypt key for {service_name} from fallback. Cannot re-encrypt.", file=sys.stderr)
            if updated_keys > 0:
                self._save_keys_to_fallback(self._keys_cache)
            print(f"Re-encrypted {updated_keys} keys in fallback storage.")

        # Update the manager's own encryption service instance
        self.encryption_service = new_encryption_service
        print("Re-encryption process finished.")


    def clear_all_keys_and_data(self):
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
        if self.use_keyring:
            keyring_services = list(self._keys_cache.get(_KEYRING_MANAGED_SERVICES_KEY, [])) # Iterate copy
            for service_name in keyring_services:
                try:
                    keyring.delete_password(self._get_service_key_name(service_name), service_name)
                except Exception as e:
                    print(f"Error deleting key for {service_name} from keyring: {e}", file=sys.stderr)
            self._keys_cache[_KEYRING_MANAGED_SERVICES_KEY] = [] # Clear the manifest
        else: # Fallback
            # Clear all keys except the manifest itself, then clear manifest
            self._keys_cache = {_KEYRING_MANAGED_SERVICES_KEY: []}

        self._save_keys_to_fallback(self._keys_cache) # Save cleared cache/manifest
        print("All API keys cleared from primary storage.")

        if self.encryption_service:
            self.encryption_service.clear_encryption_salt()
        else:
            # Attempt to clear salt file even if service not init'd (e.g. if master pass was cleared)
            if os.path.exists(ENCRYPTION_SALT_FILE):
                try:
                    os.remove(ENCRYPTION_SALT_FILE)
                    print(f"Encryption salt file {ENCRYPTION_SALT_FILE} removed.")
                except OSError as e:
                    print(f"Error removing encryption salt file {ENCRYPTION_SALT_FILE}: {e}", file=sys.stderr)
        print("All keys and associated encryption data cleared.")


if __name__ == '__main__':
    # --- Setup for testing ---
    print(f"--- Test Start: ApiKeyManager with Encryption ---")
    # Ensure clean state for data files for each test run
    fallback_path = os.path.join("data", "api_keys.json")
    salt_path = ENCRYPTION_SALT_FILE # from encryption_service

    if os.path.exists(fallback_path):
        os.remove(fallback_path)
    if os.path.exists(salt_path):
        os.remove(salt_path)
    if not os.path.exists("data"):
        os.makedirs("data")

    # Dummy master password for EncryptionService
    master_pass = "test_master_password_123"
    enc_service = EncryptionService(master_password=master_pass)

    manager = ApiKeyManager(encryption_service=enc_service)
    print(f"Using keyring: {manager.use_keyring}")

    test_service1 = "TestServiceAlpha"
    test_key1 = "alpha_key_secret_value"
    test_service2 = "TestServiceBeta"
    test_key2 = "beta_key_more_secret"

    # 1. Save and Load keys
    print(f"\n1. Saving and Loading keys...")
    try:
        manager.save_key(test_service1, test_key1)
        print(f"Saved key for {test_service1}")
        manager.save_key(test_service2, test_key2)
        print(f"Saved key for {test_service2}")

        loaded_key1 = manager.load_key(test_service1)
        print(f"Loaded key for {test_service1}: {loaded_key1}")
        assert loaded_key1 == test_key1

        loaded_key2 = manager.load_key(test_service2)
        print(f"Loaded key for {test_service2}: {loaded_key2}")
        assert loaded_key2 == test_key2
    except Exception as e:
        print(f"Error during save/load test: {e}")
        raise

    # 2. Delete a key
    print(f"\n2. Deleting a key...")
    manager.delete_key(test_service1)
    print(f"Deleted key for {test_service1}")
    loaded_key_after_delete = manager.load_key(test_service1)
    print(f"Loaded key for {test_service1} after delete: {loaded_key_after_delete}")
    assert loaded_key_after_delete is None
    # Ensure other key is still there
    assert manager.load_key(test_service2) == test_key2
    print(f"Key for {test_service2} still exists.")

    # 3. Re-encrypt keys (simulate master password change)
    print(f"\n3. Re-encrypting keys...")
    old_enc_service = enc_service # Keep current one as "old"
    new_master_pass = "new_master_password_456"
    # Create a new encryption service instance with new password. Salt will be same or regenerated.
    # For a true re-encryption where salt might also change, one would manage salt explicitly.
    # Here, EncryptionService handles its salt; new password + same salt = new Fernet key.
    new_enc_service = EncryptionService(master_password=new_master_pass)

    # Manually update the EncryptionService's master password and fernet key
    # This simulates what would happen if a user changes their master password
    # The salt remains, but the derived key changes.
    # old_enc_service.update_master_password(master_pass) # Reset to old just in case
    # new_enc_service.update_master_password(new_master_pass)

    # The manager needs to be passed the new service. It will update its own instance.
    manager.re_encrypt_all_keys(old_encryption_service=old_enc_service, new_encryption_service=new_enc_service)

    # Verify key can be loaded with new encryption service
    loaded_key2_after_reencrypt = manager.load_key(test_service2)
    print(f"Loaded key for {test_service2} after re-encryption: {loaded_key2_after_reencrypt}")
    assert loaded_key2_after_reencrypt == test_key2

    # Try loading with old encryption service - should fail if key was re-encrypted
    # (This requires the manager to still hold the old service, which it doesn't after re_encrypt_all_keys)
    # For a more robust test of this, one might need to instantiate a separate manager or directly use old_enc_service.decrypt
    print("Attempting to decrypt with old key (should fail or return None if re-encryption worked):")
    raw_key_val = ""
    if manager.use_keyring:
        keyring_services_manifest = manager._keys_cache.get(_KEYRING_MANAGED_SERVICES_KEY, [])
        if test_service2 in keyring_services_manifest:
            raw_key_val = keyring.get_password(manager._get_service_key_name(test_service2), test_service2)
    else:
        raw_key_val = manager._keys_cache.get(test_service2)

    if raw_key_val:
        decryption_with_old_key = old_enc_service.decrypt(raw_key_val)
        print(f"Decryption attempt with OLD key for {test_service2} returned: {decryption_with_old_key}")
        assert decryption_with_old_key != test_key2 # Should not be original key if re-encrypted
        # It could be None if decryption failed, or some garbled data if encryption schemes are very different
    else:
        print(f"Could not retrieve raw key for {test_service2} to test old decryption.")


    # 4. Clear all keys and data
    print(f"\n4. Clearing all keys and data...")
    manager.clear_all_keys_and_data()
    assert manager.load_key(test_service2) is None
    print(f"Key for {test_service2} is None after clear_all_keys_and_data.")
    if not manager.use_keyring: # Check fallback cache
        assert not manager._keys_cache or manager._keys_cache.get(_KEYRING_MANAGED_SERVICES_KEY) == []
        assert not any(k for k in manager._keys_cache if k != _KEYRING_MANAGED_SERVICES_KEY)
        print("Fallback cache is empty or only contains empty manifest.")

    if os.path.exists(salt_path):
         print(f"Error: Salt file {salt_path} was not deleted.")
         assert not os.path.exists(salt_path) # Should be deleted
    else:
        print(f"Salt file {salt_path} successfully deleted.")

    if os.path.exists(fallback_path):
        with open(fallback_path, 'r') as f:
            content = json.load(f)
            print(f"Fallback file content after clear: {content}")
            assert content == {_KEYRING_MANAGED_SERVICES_KEY: []}
    else:
         # This case might happen if fallback file was never created (e.g. only keyring ops and then clear)
        print("Fallback file does not exist after clear, which is acceptable.")


    # 5. Test RuntimeError if encryption_service is None
    print("\n5. Testing RuntimeError if encryption_service is None...")
    manager_no_enc = ApiKeyManager(encryption_service=None)
    try:
        manager_no_enc.save_key("ErrorTest", "key")
        assert False, "save_key should raise RuntimeError if no encryption_service"
    except RuntimeError as e:
        print(f"Caught expected error for save_key: {e}")
    try:
        manager_no_enc.load_key("ErrorTest")
        assert False, "load_key should raise RuntimeError if no encryption_service"
    except RuntimeError as e:
        print(f"Caught expected error for load_key: {e}")

    # --- Final Cleanup of test files ---
    print("\n--- Test Cleanup ---")
    if os.path.exists(fallback_path):
        os.remove(fallback_path)
        print(f"Removed {fallback_path}")
    if os.path.exists(salt_path): # Should have been removed by clear_all_keys_and_data
        os.remove(salt_path)
        print(f"Warning: Removed {salt_path} during final cleanup, but should have been removed by clear_all_keys_and_data.")

    data_dir = os.path.join("data")
    if os.path.exists(data_dir) and not os.listdir(data_dir): # Remove 'data' if empty
        os.rmdir(data_dir)
        print(f"Removed empty directory: {data_dir}")
    elif os.path.exists(data_dir):
         print(f"Directory {data_dir} still contains files: {os.listdir(data_dir)}")


    print("\n--- ApiKeyManager Test Finished ---")
