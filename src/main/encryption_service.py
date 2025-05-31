import os
import json
import hashlib
import base64
from cryptography.fernet import Fernet, InvalidToken
import binascii

ENCRYPTION_SALT_FILE = os.path.join("data", "encryption_salt.json")

class EncryptionService:
    """Provides encryption and decryption services using a master password.

    This service uses Fernet symmetric encryption (AES CBC with PKCS7 padding
    and HMAC SHA256 for authentication). The Fernet key is derived from the
    provided master password and a persisted salt using PBKDF2 HMAC SHA256.
    The salt is stored in a JSON file (`data/encryption_salt.json`).

    Attributes:
        master_password (str): The master password used for key derivation.
        encryption_salt (bytes): The salt loaded or created for key derivation.
        fernet_key (bytes): The Fernet encryption key derived from the master
            password and salt. This key is URL-safe base64 encoded.
        fernet (cryptography.fernet.Fernet): The Fernet instance used for
            encryption and decryption operations.
    """
    def __init__(self, master_password: str):
        """Initializes the EncryptionService.

        Args:
            master_password (str): The master password from which to derive the
                encryption key. Must not be empty.

        Raises:
            ValueError: If `master_password` is empty.
        """
        if not master_password:
            raise ValueError("Master password cannot be empty for EncryptionService.")
        self.master_password = master_password
        self.encryption_salt = self._load_or_create_salt()
        self.fernet_key = self._derive_fernet_key(self.master_password, self.encryption_salt)
        self.fernet = Fernet(self.fernet_key)

    def _load_or_create_salt(self) -> bytes:
        """Loads the encryption salt from file or creates and saves a new one.

        The salt is stored in `ENCRYPTION_SALT_FILE` as a hex-encoded JSON value.
        If the file is not found, or an error occurs during loading/decoding,
        a new 16-byte salt is generated using `os.urandom(16)`, saved to the
        file, and then returned. Ensures the 'data' directory exists.

        Returns:
            bytes: The loaded or newly generated encryption salt.
        """
        os.makedirs(os.path.dirname(ENCRYPTION_SALT_FILE), exist_ok=True)
        try:
            if os.path.exists(ENCRYPTION_SALT_FILE):
                with open(ENCRYPTION_SALT_FILE, 'r') as f:
                    data = json.load(f)
                    return binascii.unhexlify(data['salt'])
        except (FileNotFoundError, json.JSONDecodeError, KeyError, binascii.Error) as e:
            print(f"Error loading encryption salt, creating a new one: {e}")

        new_salt = os.urandom(16)
        try:
            with open(ENCRYPTION_SALT_FILE, 'w') as f:
                json.dump({'salt': binascii.hexlify(new_salt).decode('utf-8')}, f)
            return new_salt
        except IOError as e:
            print(f"Error saving new encryption salt: {e}")
            # If saving fails, still return the generated salt for in-memory use,
            # but it won't persist for the next session if the app restarts before successful save.
            return new_salt


    def _derive_fernet_key(self, password: str, salt: bytes) -> bytes:
        """Derives a 32-byte key using PBKDF2-HMAC-SHA256 and base64 encodes it.

        This creates a Fernet-compatible encryption key.

        Args:
            password (str): The password to use for key derivation.
            salt (bytes): The salt to use for key derivation.

        Returns:
            bytes: A base64 URL-safe encoded Fernet key.

        Raises:
            ValueError: If salt is not available (e.g., None).
        """
        if not salt:
             raise ValueError("Encryption salt is not available for key derivation.")
        derived_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000,  # NIST recommended iterations for PBKDF2
            dklen=32   # Fernet keys must be 32 bytes
        )
        return base64.urlsafe_b64encode(derived_key)

    def encrypt(self, data: str) -> str:
        """Encrypts a UTF-8 string using the derived Fernet key.

        Args:
            data (str): The string data to encrypt.

        Returns:
            str: The Fernet token (encrypted data) as a UTF-8 string.
        """
        encrypted_bytes = self.fernet.encrypt(data.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')

    def decrypt(self, encrypted_data: str) -> str | None:
        """Decrypts a Fernet token (UTF-8 string) using the derived key.

        Args:
            encrypted_data (str): The Fernet token (encrypted data) as a
                UTF-8 string.

        Returns:
            Optional[str]: The decrypted string if successful, otherwise None.
                           Logs an error message on decryption failure.
        """
        try:
            decrypted_bytes = self.fernet.decrypt(encrypted_data.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except InvalidToken:
            print("Error: Decryption failed. Invalid token or key.")
            return None
        except Exception as e: # Catch other potential errors during decryption
            print(f"An unexpected error occurred during decryption: {e}")
            return None

    def get_current_fernet_key(self) -> bytes:
        """Returns the current base64 URL-safe encoded Fernet key.

        Returns:
            bytes: The current Fernet key.
        """
        return self.fernet_key

    def update_master_password(self, new_master_password: str) -> bytes:
        """Updates the master password and re-derives the Fernet key.

        This method updates the internal master password, then re-derives the
        Fernet key using the new password and the existing (or newly created if
        missing) encryption salt. The Fernet instance is then updated with the
        new key.

        Note: Data encrypted with the old Fernet key will not be decryptable
        with the new key. Re-encryption of existing data is required externally.

        Args:
            new_master_password (str): The new master password.

        Returns:
            bytes: The new Fernet key.

        Raises:
            ValueError: If `new_master_password` is empty.
        """
        if not new_master_password:
            raise ValueError("New master password cannot be empty.")
        self.master_password = new_master_password
        # The salt is typically not changed during a master password update unless explicitly managed.
        # _load_or_create_salt ensures salt is available.
        self.encryption_salt = self._load_or_create_salt()
        self.fernet_key = self._derive_fernet_key(self.master_password, self.encryption_salt)
        self.fernet = Fernet(self.fernet_key)
        return self.fernet_key


    def clear_encryption_salt(self):
        """Deletes the encryption salt file (`ENCRYPTION_SALT_FILE`) from storage.

        This method should typically be called when all encrypted data associated
        with this salt is also being cleared (e.g., when clearing all application data).
        It also sets the `self.encryption_salt` attribute to None.
        """
        if os.path.exists(ENCRYPTION_SALT_FILE):
            try:
                os.remove(ENCRYPTION_SALT_FILE)
                print(f"Encryption salt file {ENCRYPTION_SALT_FILE} removed.")
            except OSError as e:
                print(f"Error removing encryption salt file {ENCRYPTION_SALT_FILE}: {e}")
        self.encryption_salt = None
