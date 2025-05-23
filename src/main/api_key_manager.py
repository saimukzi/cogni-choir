import keyring
import json
import os
import sys

SERVICE_NAME_PREFIX = "MyChatApp"

class ApiKeyManager:
    def __init__(self):
        self.use_keyring = True
        self.fallback_file_path = os.path.join("data", "api_keys.json")

        try:
            # Test if keyring is accessible
            keyring.get_password(SERVICE_NAME_PREFIX + "_test_init", "test_user")
        except keyring.errors.NoKeyringError:
            self.use_keyring = False
            print(f"Failed to initialize keyring. Using fallback JSON file for API keys: {self.fallback_file_path}", file=sys.stderr)
        except Exception as e: # Other potential keyring errors
            self.use_keyring = False
            print(f"Could not access keyring due to {type(e).__name__}. Using fallback JSON file for API keys: {self.fallback_file_path}", file=sys.stderr)


        if not self.use_keyring:
            self._ensure_data_dir_exists()
            self._keys_cache = self._load_keys_from_fallback()
        else:
            self._keys_cache = {} # Not strictly needed for keyring but good for consistency if we were to cache

    def _ensure_data_dir_exists(self):
        if not os.path.exists("data"):
            try:
                os.makedirs("data")
            except OSError as e:
                print(f"Error creating data directory {e}", file=sys.stderr)
                # Potentially raise this or handle more gracefully

    def _get_service_key_name(self, service_name: str) -> str:
        """Helper to create a unique service name for keyring."""
        return f"{SERVICE_NAME_PREFIX}_{service_name}"

    def _load_keys_from_fallback(self) -> dict:
        if not os.path.exists(self.fallback_file_path):
            return {}
        try:
            with open(self.fallback_file_path, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading API keys from fallback file: {e}", file=sys.stderr)
            return {}

    def _save_keys_to_fallback(self, keys: dict):
        self._ensure_data_dir_exists()
        try:
            with open(self.fallback_file_path, 'w') as f:
                json.dump(keys, f, indent=4)
        except IOError as e:
            print(f"Error saving API keys to fallback file: {e}", file=sys.stderr)

    def save_key(self, service_name: str, api_key: str):
        if not service_name or not api_key: # Basic validation
            print("Service name and API key cannot be empty.", file=sys.stderr)
            return

        if self.use_keyring:
            try:
                keyring.set_password(self._get_service_key_name(service_name), service_name, api_key)
            except Exception as e: # Catch any keyring error during set
                print(f"Error setting key in keyring for {service_name}: {e}", file=sys.stderr)
                # Optionally: could fallback to JSON here if setting fails
        else:
            self._keys_cache[service_name] = api_key
            self._save_keys_to_fallback(self._keys_cache)

    def load_key(self, service_name: str) -> str | None:
        if not service_name:
            return None

        if self.use_keyring:
            try:
                return keyring.get_password(self._get_service_key_name(service_name), service_name)
            except Exception as e: # Catch any keyring error during get
                print(f"Error getting key from keyring for {service_name}: {e}", file=sys.stderr)
                return None # Or consider fallback
        else:
            return self._keys_cache.get(service_name)

    def delete_key(self, service_name: str):
        if not service_name:
            return

        if self.use_keyring:
            try:
                keyring.delete_password(self._get_service_key_name(service_name), service_name)
            except keyring.errors.PasswordDeleteError:
                # This error means the password was not found, which is fine for deletion.
                pass
            except Exception as e: # Catch other keyring errors
                print(f"Error deleting key from keyring for {service_name}: {e}", file=sys.stderr)
        else:
            if service_name in self._keys_cache:
                del self._keys_cache[service_name]
                self._save_keys_to_fallback(self._keys_cache)

if __name__ == '__main__':
    # Basic test
    manager = ApiKeyManager()
    print(f"Using keyring: {manager.use_keyring}")

    test_service = "TestService"
    test_key = "test_api_key_12345"

    print(f"Saving key for {test_service}...")
    manager.save_key(test_service, test_key)

    print(f"Loading key for {test_service}...")
    loaded_key = manager.load_key(test_service)
    print(f"Loaded key: {loaded_key}")
    assert loaded_key == test_key if manager.use_keyring or (test_service in manager._keys_cache and manager._keys_cache[test_service] == test_key) else loaded_key is None


    print(f"Deleting key for {test_service}...")
    manager.delete_key(test_service)
    loaded_key_after_delete = manager.load_key(test_service)
    print(f"Loaded key after delete: {loaded_key_after_delete}")
    assert loaded_key_after_delete is None

    # Test fallback explicitly if possible (manual intervention might be needed to trigger NoKeyringError)
    if not manager.use_keyring:
        print("Testing fallback scenario (assuming keyring was not available)")
        fallback_service = "FallbackTest"
        fallback_key = "fallback_key_value"
        manager.save_key(fallback_service, fallback_key)
        loaded_fallback = manager.load_key(fallback_service)
        print(f"Loaded fallback key: {loaded_fallback}")
        assert loaded_fallback == fallback_key
        manager.delete_key(fallback_service)
        assert manager.load_key(fallback_service) is None
        # Check if data/api_keys.json was created/deleted appropriately
        if os.path.exists(manager.fallback_file_path):
            print(f"Fallback file exists: {manager.fallback_file_path}")
            # os.remove(manager.fallback_file_path) # Clean up
    print("Test finished.")
