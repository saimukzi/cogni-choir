"""Manages the application's master password.

This module is responsible for handling the master password, which is used to
protect sensitive information within the application. It includes functionality
for setting, verifying, changing, and clearing the master password.
The password itself is not stored directly; instead, a salted hash is used.
"""
import os
import json
import hashlib
import binascii
import hmac

DEFAULT_MASTER_KEY_FILE = os.path.join("data", "master_key.json")

class PasswordManager:
    """Manages the lifecycle of a master password for the application.

    This class handles the storage, verification, and management of a master
    password. The password hash and salt are stored in a JSON file.
    It uses PBKDF2 HMAC SHA256 for password hashing and securely compares
    hashes using `hmac.compare_digest`.

    Attributes:
        hashed_password (Optional[bytes]): The hashed master password, loaded
            from `MASTER_KEY_FILE` or None if not set.
        salt (Optional[bytes]): The salt used for hashing, loaded from
            `MASTER_KEY_FILE` or None if not set.
    """

    def __init__(self, master_key_file: str = DEFAULT_MASTER_KEY_FILE):
        """Initializes the PasswordManager instance.

        Sets initial `hashed_password` and `salt` to None, then attempts to
        load existing master key data from the `MASTER_KEY_FILE`.
        """
        self._master_key_file = master_key_file
        self.hashed_password: bytes | None = None
        self.salt: bytes | None = None
        self._load_master_key_data()

    def _load_master_key_data(self):
        """Loads master key data (hashed password and salt) from storage.

        Reads `MASTER_KEY_FILE`, decodes hex-encoded values for
        `hashed_password` and `salt`. Handles `FileNotFoundError`,
        `json.JSONDecodeError`, or `KeyError` by leaving attributes as `None`
        and printing an error message.
        """
        try:
            if os.path.exists(self._master_key_file):
                with open(self._master_key_file, 'r') as f:
                    data = json.load(f)
                    self.hashed_password = binascii.unhexlify(data['hashed_password'])
                    self.salt = binascii.unhexlify(data['salt'])
        except FileNotFoundError:
            # File not found, master key not set yet.
            pass
        except (json.JSONDecodeError, KeyError) as e:
            # Error decoding JSON or key missing, treat as no master key.
            print(f"Error loading master key data: {e}")
            self.hashed_password = None
            self.salt = None

    def _save_master_key_data(self):
        """Saves the current master key data (hashed password and salt) to storage.

        Ensures the "data" directory exists. If `hashed_password` and `salt`
        are set, they are hex-encoded and stored in `MASTER_KEY_FILE` as a
        JSON object. If they are `None` (e.g., after `clear_master_password`),
        `MASTER_KEY_FILE` is deleted if it exists. Handles potential `IOError`
        or `OSError` during file operations.
        """
        os.makedirs(os.path.dirname(self._master_key_file), exist_ok=True)
        try:
            if self.hashed_password and self.salt:
                data = {
                    'hashed_password': binascii.hexlify(self.hashed_password).decode('utf-8'),
                    'salt': binascii.hexlify(self.salt).decode('utf-8'),
                }
                with open(self._master_key_file, 'w') as f:
                    json.dump(data, f)
            else:
                if os.path.exists(self._master_key_file):
                    try:
                        os.remove(self._master_key_file)
                    except OSError as e:
                        print(f"Error removing master key file: {e}")
        except IOError as e: # Covers file open/write errors
            print(f"Error saving master key data (IOError): {e}")
        except OSError as e: # Covers os.makedirs errors if exist_ok=False or other OS issues
            print(f"Error saving master key data (OSError): {e}")


    def _hash_password(self, password: str, salt: bytes) -> bytes:
        """Hashes a password using PBKDF2-HMAC-SHA256.

        The iteration count is reduced if the `CI_TEST_MODE` environment
        variable is set to 'true'.

        Args:
            password (str): The password string to hash.
            salt (bytes): The salt to use for hashing.

        Returns:
            bytes: The derived hashed password.
        """
        # Reduce iterations in test mode to speed up tests
        iterations = 1 if os.environ.get('CI_TEST_MODE') == 'true' else 100000
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations, dklen=64)

    def set_master_password(self, password: str) -> bool:
        """Sets or updates the master password.

        A new salt is generated, the password is hashed, and the data is saved.
        If a master password already exists, this method effectively overwrites it
        by generating a new salt and hash.

        Args:
            password (str): The new master password.

        Returns:
            bool: True if the password was set successfully.

        Raises:
            ValueError: If the provided password is empty.
        """
        if not password:
            raise ValueError("Password cannot be empty.")
        self.salt = os.urandom(16)
        self.hashed_password = self._hash_password(password, self.salt)
        self._save_master_key_data()
        return True

    def verify_master_password(self, password: str) -> bool:
        """Verifies a given password against the stored master password.

        Hashes the provided password using the stored salt and compares it
        securely against the stored hashed password.

        Args:
            password (str): The password to verify.

        Returns:
            bool: True if the password matches the stored master password,
                  False otherwise or if no master password is set.
        """
        if not self.has_master_password():
            return False
        # Type guard for salt, as has_master_password ensures it's not None
        current_salt = self.salt
        if current_salt is None: # Should not be reached if has_master_password is True
             return False

        hashed_input_password = self._hash_password(password, current_salt)
        # Use hmac.compare_digest for compatibility with older Python versions
        # and for secure comparison against timing attacks.
        # Type guard for hashed_password
        current_hashed_password = self.hashed_password
        if current_hashed_password is None: # Should not be reached
            return False
        return hmac.compare_digest(current_hashed_password, hashed_input_password)

    def has_master_password(self) -> bool:
        """Checks if a master password (hash and salt) is currently set and loaded.

        Returns:
            bool: True if both `hashed_password` and `salt` are not `None`,
                  False otherwise.
        """
        return (self.hashed_password is not None) and (self.salt is not None)

    def change_master_password(self, old_password: str, new_password: str) -> bool:
        """Changes the master password after verifying the old one.

        If the old password is correct, this method sets the new password,
        which involves generating a new salt, hashing the new password, and
        saving the updated data.

        Args:
            old_password (str): The current master password.
            new_password (str): The new master password to set.

        Returns:
            bool: True if the password was changed successfully, False if the
                  old password verification failed.

        Raises:
            ValueError: If the new_password is empty (raised by
                        `set_master_password`).
        """
        if not self.verify_master_password(old_password):
            return False
        return self.set_master_password(new_password)

    def clear_master_password(self):
        """Clears the current master password from memory and storage.

        Sets `hashed_password` and `salt` attributes to `None` and deletes
        the `MASTER_KEY_FILE` from disk.
        """
        self.hashed_password = None
        self.salt = None
        self._save_master_key_data()

if __name__ == '__main__':
    pm = PasswordManager()

    if not pm.has_master_password():
        print("No master password set. Setting one now.")
        pm.set_master_password("StrongPassword123!")
        print("Master password set.")
    else:
        print("Master password already set.")

    print("\nVerifying master password:")
    if pm.verify_master_password("StrongPassword123!"):
        print("Password verification successful.")
    else:
        print("Password verification failed.")

    print("\nChanging master password:")
    if pm.change_master_password("StrongPassword123!", "EvenStrongerPassword456!"):
        print("Master password changed successfully.")
        # Verify with the new password
        if pm.verify_master_password("EvenStrongerPassword456!"):
            print("New password verification successful.")
        else:
            print("New password verification failed.")
    else:
        print("Failed to change master password. Old password might be incorrect.")

    print("\nClearing master password.")
    pm.clear_master_password()
    if not pm.has_master_password():
        print("Master password cleared successfully.")
    else:
        print("Failed to clear master password.")

    # Test setting password again after clearing
    print("\nSetting master password again after clearing.")
    pm.set_master_password("NewPassword789!")
    if pm.has_master_password() and pm.verify_master_password("NewPassword789!"):
        print("Master password set and verified successfully after clearing.")
    else:
        print("Failed to set/verify master password after clearing.")

    # Final cleanup
    print("\nPerforming final cleanup...")
    pm.clear_master_password() # Ensure the master_key.json is deleted by the manager

    data_dir = os.path.dirname(DEFAULT_MASTER_KEY_FILE)
    gitkeep_file = os.path.join(data_dir, ".gitkeep")

    if os.path.exists(gitkeep_file):
        try:
            os.remove(gitkeep_file)
            print(f"Removed {gitkeep_file}.")
        except OSError as e:
            print(f"Error removing {gitkeep_file}: {e}")

    # master_key.json should have been deleted by pm.clear_master_password()
    # but check and remove if it still exists for any reason.
    if os.path.exists(DEFAULT_MASTER_KEY_FILE):
        print(f"Warning: {DEFAULT_MASTER_KEY_FILE} still exists after clear. Attempting removal again.")
        try:
            os.remove(DEFAULT_MASTER_KEY_FILE)
        except OSError as e:
            print(f"Error removing {DEFAULT_MASTER_KEY_FILE} during cleanup: {e}")

    if os.path.exists(data_dir):
        try:
            # Attempt to remove the directory
            os.rmdir(data_dir)
            print(f"Directory {data_dir} removed successfully.")
        except OSError as e:
            print(f"Error removing directory {data_dir}: {e}")
            # If rmdir failed, list contents to see what's left
            if os.path.exists(data_dir):
                print(f"Final check: Contents of {data_dir} after failed rmdir: {os.listdir(data_dir)}")
    else:
        print(f"Directory {data_dir} does not exist or was already removed.")

    print("Cleanup process finished.")

    print("No master password set. Setting one now.")
    pm.set_master_password("StrongPassword123!")
    print("Master password set.")

    print("\nVerifying master password:")
    if pm.verify_master_password("StrongPassword123!"):
        print("Password verification successful.")
    else:
        print("Password verification failed.")

    print("\nChanging master password:")
    if pm.change_master_password("StrongPassword123!", "EvenStrongerPassword456!"):
        print("Master password changed successfully.")
        # Verify with the new password
        if pm.verify_master_password("EvenStrongerPassword456!"):
            print("New password verification successful.")
        else:
            print("New password verification failed.")
    else:
        print("Failed to change master password. Old password might be incorrect.")

    print("\nClearing master password.")
    pm.clear_master_password()
    if not pm.has_master_password():
        print("Master password cleared successfully.")
    else:
        print("Failed to clear master password.")

    # Test setting password again after clearing
    print("\nSetting master password again after clearing.")
    pm.set_master_password("NewPassword789!")
    if pm.has_master_password() and pm.verify_master_password("NewPassword789!"):
        print("Master password set and verified successfully after clearing.")
    else:
        print("Failed to set/verify master password after clearing.")

    # Final cleanup
    print("\nPerforming final cleanup...")
    pm.clear_master_password() # Ensure the master_key.json is deleted by the manager

    data_dir = os.path.dirname(DEFAULT_MASTER_KEY_FILE)
    gitkeep_file = os.path.join(data_dir, ".gitkeep")

    if os.path.exists(gitkeep_file):
        try:
            os.remove(gitkeep_file)
            print(f"Removed {gitkeep_file}.")
        except OSError as e:
            print(f"Error removing {gitkeep_file}: {e}")

    # master_key.json should have been deleted by pm.clear_master_password()
    # but check and remove if it still exists for any reason.
    if os.path.exists(DEFAULT_MASTER_KEY_FILE):
        print(f"Warning: {DEFAULT_MASTER_KEY_FILE} still exists after clear. Attempting removal again.")
        try:
            os.remove(DEFAULT_MASTER_KEY_FILE)
        except OSError as e:
            print(f"Error removing {DEFAULT_MASTER_KEY_FILE} during cleanup: {e}")

    if os.path.exists(data_dir):
        try:
            # Attempt to remove the directory
            os.rmdir(data_dir)
            print(f"Directory {data_dir} removed successfully.")
        except OSError as e:
            print(f"Error removing directory {data_dir}: {e}")
            # If rmdir failed, list contents to see what's left
            if os.path.exists(data_dir):
                print(f"Final check: Contents of {data_dir} after failed rmdir: {os.listdir(data_dir)}")
    else:
        print(f"Directory {data_dir} does not exist or was already removed.")

    print("Cleanup process finished.")
