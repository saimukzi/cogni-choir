"""Unit tests for the PasswordManager.

This module contains unit tests for the `PasswordManager` class.
The tests focus on the core functionalities of master password management,
including setting, verifying, changing, and clearing the master password.
It also covers the persistence of the password data (hashed password and salt)
to a file and its subsequent loading.
"""
import unittest
import os
import json
# hmac is used by PasswordManager internally, not directly needed for these tests usually
# from hashlib import hmac

# Adjust import path based on how tests are run.
# If run from root with `python -m unittest discover src/test`:
from src.main.password_manager import PasswordManager

# Use a unique data directory for this test class
TEST_DATA_DIR_PWD_MGR = "test_data_pwd_mgr"
TEST_MASTER_KEY_FILE = os.path.join(TEST_DATA_DIR_PWD_MGR, "test_master_key.json")


class TestPasswordManager(unittest.TestCase):
    """Test suite for the PasswordManager class.

    This class groups together all the unit tests for the `PasswordManager`.
    It ensures that all aspects of the master password lifecycle—setting,
    verifying, changing, clearing, and persistence—function correctly.
    """

    def setUp(self):
        self._ensure_data_dir_exists() # Ensure unique test data directory exists
        self._cleanup_test_file()    # Ensure specific test file is gone before test

        # Override the master key file path for testing
        self.pm = PasswordManager(TEST_MASTER_KEY_FILE)

    def tearDown(self):
        self._cleanup_test_file()
        # Attempt to remove the unique test data directory if it's empty
        if os.path.exists(TEST_DATA_DIR_PWD_MGR) and not os.listdir(TEST_DATA_DIR_PWD_MGR):
            try:
                os.rmdir(TEST_DATA_DIR_PWD_MGR)
            except OSError as e: # pragma: no cover
                print(f"Warning: Error removing directory {TEST_DATA_DIR_PWD_MGR} in cleanup: {e}")
        elif os.path.exists(TEST_DATA_DIR_PWD_MGR) and os.listdir(TEST_DATA_DIR_PWD_MGR):
             print(f"Warning: Test data directory {TEST_DATA_DIR_PWD_MGR} not empty during cleanup.")


    def _ensure_data_dir_exists(self):
        """Ensures the unique test data directory exists."""
        if not os.path.exists(TEST_DATA_DIR_PWD_MGR):
            try:
                os.makedirs(TEST_DATA_DIR_PWD_MGR)
            except OSError as e: # pragma: no cover
                if not os.path.isdir(TEST_DATA_DIR_PWD_MGR):
                    raise RuntimeError(f"Failed to create data directory {TEST_DATA_DIR_PWD_MGR} for tests: {e}")

    def _cleanup_test_file(self):
        """Removes only the specific test file used by this test class."""
        if os.path.exists(TEST_MASTER_KEY_FILE):
            try:
                os.remove(TEST_MASTER_KEY_FILE)
            except OSError as e: # pragma: no cover
                print(f"Warning: Error removing {TEST_MASTER_KEY_FILE} in cleanup: {e}")


    def test_initial_state(self):
        self.assertFalse(self.pm.has_master_password(), "Initially, PasswordManager should not have a master password.")

    def test_set_and_verify_password(self):
        self.assertTrue(self.pm.set_master_password("testpass"), "set_master_password should return True on success.")
        self.assertTrue(self.pm.has_master_password(), "Should have master password after setting one.")
        self.assertTrue(self.pm.verify_master_password("testpass"), "Verification with correct password should succeed.")
        self.assertFalse(self.pm.verify_master_password("wrongpass"), "Verification with incorrect password should fail.")
        self.assertTrue(os.path.exists(TEST_MASTER_KEY_FILE), "Master key file should exist after setting password.")

    def test_set_empty_password(self):
        with self.assertRaisesRegex(ValueError, "Password cannot be empty."):
            self.pm.set_master_password("")
        self.assertFalse(self.pm.has_master_password(), "Should not have master password after attempting to set an empty one.")

    def test_change_password(self):
        self.pm.set_master_password("oldpass")
        self.assertTrue(self.pm.change_master_password("oldpass", "newpass"), "change_master_password should return True on success.")
        self.assertTrue(self.pm.verify_master_password("newpass"), "Should verify with new password.")
        self.assertFalse(self.pm.verify_master_password("oldpass"), "Should not verify with old password anymore.")

    def test_change_password_incorrect_old(self):
        self.pm.set_master_password("oldpass")
        self.assertFalse(self.pm.change_master_password("wrongoldpass", "newpass"), "change_master_password should return False with incorrect old password.")
        self.assertTrue(self.pm.verify_master_password("oldpass"), "Should still verify with the original old password.")
        self.assertFalse(self.pm.verify_master_password("newpass"), "Should not verify with new password if change failed.")


    def test_clear_password(self):
        self.pm.set_master_password("testpass")
        self.assertTrue(self.pm.has_master_password(), "Ensure password is set before clearing.")

        self.pm.clear_master_password()
        self.assertFalse(self.pm.has_master_password(), "Should not have master password after clearing.")
        self.assertFalse(os.path.exists(TEST_MASTER_KEY_FILE), "Master key file should not exist after clearing password.")

    def test_persistence(self):
        self.pm.set_master_password("persistpass")
        # Ensure data is saved before creating a new instance
        self.assertTrue(os.path.exists(TEST_MASTER_KEY_FILE))

        pm2 = PasswordManager(TEST_MASTER_KEY_FILE)

        self.assertTrue(pm2.has_master_password(), "New instance should load persisted master password.")
        self.assertTrue(pm2.verify_master_password("persistpass"), "New instance should verify persisted password.")
        self.assertFalse(pm2.verify_master_password("wrongpass"), "New instance should fail verification with wrong password.")

    def test_verify_password_when_none_set(self):
        self.assertFalse(self.pm.verify_master_password("anypass"), "Verification should fail if no password is set.")

    def test_change_password_when_none_set(self):
         self.assertFalse(self.pm.change_master_password("anypass", "newpass"), "Changing password should fail if none is set.")


if __name__ == '__main__':
    unittest.main()
