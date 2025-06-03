import unittest
from unittest.mock import patch, MagicMock
import json
import requests
import threading
import time
import http.server

# Adjust import paths as necessary
from src.main import api_server
from src.main.api_server import set_api_server_enabled, API_SERVER_ENABLED
from src.main.ccapikey_manager import CcApiKeyManager
from src.main.encryption_service import EncryptionService

TEST_SERVER_PORT = 5002 # Choose a port for testing
BASE_URL = f"http://localhost:{TEST_SERVER_PORT}"

class TestApiServerHttp(unittest.TestCase):
    """Test suite for the HTTP API server endpoints."""

    original_cc_api_key_manager = None
    original_api_server_enabled_state = None

    @classmethod
    def setUpClass(cls):
        """Set up once before all tests in the class."""
        cls.original_cc_api_key_manager = api_server.cc_api_key_manager
        cls.original_api_server_enabled_state = API_SERVER_ENABLED

        # Mock EncryptionService globally for the test class if needed, or per test
        cls.mock_encryption_service = MagicMock(spec=EncryptionService)

    @classmethod
    def tearDownClass(cls):
        """Tear down once after all tests in the class."""
        api_server.cc_api_key_manager = cls.original_cc_api_key_manager
        set_api_server_enabled(cls.original_api_server_enabled_state)
        if api_server.httpd: # Ensure server is shut down if test_shutdown failed
            api_server.httpd.shutdown()
            api_server.httpd.server_close()
        if api_server.server_thread and api_server.server_thread.is_alive():
            api_server.server_thread.join(timeout=1)


    def setUp(self):
        """Set up for each test case."""
        # Reset API server enabled state to True before each test that might change it
        set_api_server_enabled(True)
        api_server.httpd = None # Ensure httpd is None before each test
        api_server.server_thread = None # Ensure server_thread is None

        # Mock CcApiKeyManager for each test
        self.mock_cc_api_key_manager = MagicMock(spec=CcApiKeyManager)

        # Initialize API server dependencies with the mock manager
        # The mock_encryption_service from setUpClass can be used or a new one per test
        api_server.initialize_api_server_dependencies(
            cc_manager=self.mock_cc_api_key_manager,
            enc_service=self.mock_encryption_service # Using class-level mock
        )
        self.server_thread = None # For managing server thread in tests that run the server

    def tearDown(self):
        """Clean up after each test."""
        self._stop_server() # Ensure server is stopped after each test that starts it
        # Restore global cc_api_key_manager to the class original for isolation between tests
        # This is important if a test modifies it directly (e.g. test_hello_api_key_manager_not_initialized)
        api_server.cc_api_key_manager = self.original_cc_api_key_manager
        api_server.initialize_api_server_dependencies(
            cc_manager=self.mock_cc_api_key_manager, # Re-initialize with the current test's mock
            enc_service=self.mock_encryption_service
        )


    def _start_server(self):
        """Starts the HTTP server in a separate thread for testing."""
        if not api_server.API_SERVER_ENABLED:
            print("Test server start skipped: API_SERVER_ENABLED is False.")
            return

        # Ensure any previous server instance is shut down
        # if api_server.httpd:
        #     api_server.httpd.shutdown()
        #     api_server.httpd.server_close()
        #     api_server.httpd = None
        api_server.shutdown_server()
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1)
            self.server_thread = None

        self.server_thread = threading.Thread(target=api_server.run_server, args=(TEST_SERVER_PORT, False), daemon=True)
        self.server_thread.start()
        time.sleep(0.1) # Give the server a moment to start

        # Check if server started (httpd should be set)
        # print('TestHelper _start_server: Waiting for server to start...')
        for _ in range(20): # Wait up to 5 seconds
            if api_server.httpd:
                break
            time.sleep(0.1)
        self.assertIsNotNone(api_server.httpd, "Server did not start in time.")


    def _stop_server(self):
        api_server.shutdown_server()

        for _ in range(20): # Wait up to 2 seconds
            if not api_server.httpd:
                break
            time.sleep(0.1)
        self.assertIsNone(api_server.httpd, "Server did not stop in time.")

        # """Stops the HTTP server thread, primarily by using the /shutdown endpoint."""
        # if self.server_thread and self.server_thread.is_alive():
        #     if api_server.httpd: # Check if the server believes it's running
        #         try:
        #             print(f"TestHelper _stop_server: Attempting graceful shutdown via POST to {BASE_URL}/shutdown")
        #             # Increased timeout for the shutdown request itself.
        #             requests.post(f"{BASE_URL}/shutdown", timeout=1.0)
        #             # Wait for the server thread to process shutdown and for serve_forever() to return.
        #             # The join() timeout should be generous enough for the server's finally block to run.
        #             self.server_thread.join(timeout=2.0)
        #         except requests.exceptions.RequestException as e:
        #             print(f"TestHelper _stop_server: Request to /shutdown failed (server might be already down or unresponsive): {e}")
        #             # If POST fails, the server might already be in shutdown.
        #             # We still try to join the thread.
        #             if self.server_thread.is_alive():
        #                 self.server_thread.join(timeout=1.0)
        #     else:
        #         # If api_server.httpd is None, but thread is alive, it's an odd state.
        #         # Try to join anyway.
        #         print("TestHelper _stop_server: api_server.httpd is None, but server_thread is alive. Joining thread.")
        #         if self.server_thread.is_alive(): # Re-check, condition might have changed
        #             self.server_thread.join(timeout=1.0)

        # # After attempts to shut down and join, if thread is *still* alive, it's problematic.
        # if self.server_thread and self.server_thread.is_alive():
        #     print("TestHelper _stop_server: Server thread still alive after shutdown attempts. This may indicate an issue.")
        #     # At this point, forcefully trying to shutdown global httpd (if any) might be too late or risky
        #     # as the thread might be stuck. The test for this scenario will likely fail on assertion.

        # self.server_thread = None
        # # `api_server.httpd` should be set to None by the `run_server`'s `finally` block.
        # # `api_server.server_thread` is not managed by api_server.py itself, but by its caller.
        # time.sleep(0.2) # Brief pause to help ensure resources are released system-wide.


    def test_hello_no_api_key_header(self):
        """Test /hello endpoint without providing an API key header."""
        self._start_server()
        response = requests.get(f"{BASE_URL}/hello")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "API key required"})

    def test_hello_invalid_api_key(self):
        """Test /hello endpoint with an invalid/unknown API key."""
        self._start_server()
        self.mock_cc_api_key_manager.list_key_names.return_value = ["valid_key_name_1"]
        self.mock_cc_api_key_manager.get_key.return_value = "actual_stored_valid_key_value"

        provided_invalid_key = "this_is_an_invalid_key"
        headers = {"CcApiKey": provided_invalid_key}
        response = requests.get(f"{BASE_URL}/hello", headers=headers)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": "Invalid API key"})

    def test_hello_valid_api_key(self):
        """Test /hello endpoint with a valid API key."""
        self._start_server()
        valid_key_value = "my_secret_cc_api_key_value"
        self.mock_cc_api_key_manager.list_key_names.return_value = ["sample_key_name"]
        self.mock_cc_api_key_manager.get_key.side_effect = lambda name: valid_key_value if name == "sample_key_name" else None

        headers = {"CcApiKey": valid_key_value}
        response = requests.get(f"{BASE_URL}/hello", headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "hello, authenticated user!"})

    def test_hello_valid_api_key_lowercase_header(self):
        """Test /hello endpoint with a valid API key using lowercase 'ccapikey' header."""
        self._start_server()
        valid_key_value = "my_secret_cc_api_key_value_lowercase"
        self.mock_cc_api_key_manager.list_key_names.return_value = ["another_key_name"]
        self.mock_cc_api_key_manager.get_key.side_effect = lambda name: valid_key_value if name == "another_key_name" else None

        headers = {"ccapikey": valid_key_value} # Lowercase header
        response = requests.get(f"{BASE_URL}/hello", headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "hello, authenticated user!"})

    def test_hello_api_key_manager_not_initialized(self):
        """Test /hello when cc_api_key_manager is None (not initialized)."""
        # Store current manager and set to None for this test
        # This test needs careful handling of global state
        current_manager_backup = api_server.cc_api_key_manager
        api_server.cc_api_key_manager = None
        self._start_server() # Server will start with cc_api_key_manager as None

        try:
            headers = {"CcApiKey": "any_key_value"}
            response = requests.get(f"{BASE_URL}/hello", headers=headers)
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json(), {"error": "API key manager not initialized"})
        finally:
            # Restore the original manager to avoid affecting other tests
            api_server.cc_api_key_manager = current_manager_backup
            # Stop server started with modified global state
            self._stop_server()
            # Re-initialize with the test's default mock manager for subsequent tests in the class
            # This is now handled by tearDown and setUp.
            # api_server.initialize_api_server_dependencies(self.mock_cc_api_key_manager, self.mock_encryption_service)


    def test_hello_key_validation_raises_exception(self):
        """Test /hello when key validation in API server raises an unexpected exception."""
        self._start_server()
        self.mock_cc_api_key_manager.list_key_names.side_effect = Exception("Unexpected validation error")

        headers = {"CcApiKey": "any_key_value"}
        response = requests.get(f"{BASE_URL}/hello", headers=headers)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"error": "Server error during key validation"})

    @patch('http.server.HTTPServer.serve_forever')
    def test_run_server_starts_when_enabled(self, mock_serve_forever):
        """Test that HTTPServer.serve_forever is called when the server is enabled."""
        set_api_server_enabled(True)
        # api_server.run_server calls http.server.HTTPServer(...) and then serve_forever()
        # We need to ensure that the HTTPServer constructor is also called.
        # Patching the constructor might be too complex, so we trust it's called if serve_forever is.
        with patch('http.server.HTTPServer') as mock_http_server_constructor:
            # Configure the mock constructor to return an object that has a serve_forever method
            mock_server_instance = MagicMock()
            mock_http_server_constructor.return_value = mock_server_instance

            api_server.run_server(port=TEST_SERVER_PORT)

            mock_http_server_constructor.assert_called_once_with(('0.0.0.0', TEST_SERVER_PORT), api_server.ApiRequestHandler)
            mock_server_instance.serve_forever.assert_called_once()


    @patch('http.server.HTTPServer.serve_forever')
    def test_run_server_does_not_start_when_disabled(self, mock_serve_forever):
        """Test that HTTPServer.serve_forever is not called when the server is disabled."""
        set_api_server_enabled(False)
        api_server.run_server(port=TEST_SERVER_PORT + 1) # Use a different port to avoid state issues
        mock_serve_forever.assert_not_called()

    @patch('builtins.print')
    @patch('http.server.HTTPServer.serve_forever')
    def test_run_server_prints_message_when_disabled(self, mock_serve_forever, mock_print):
        """Test that a message is printed when server is disabled and run_server is called."""
        set_api_server_enabled(False)
        api_server.run_server(port=TEST_SERVER_PORT + 2)
        mock_serve_forever.assert_not_called()
        mock_print.assert_any_call("API server is disabled by configuration.")


    # def test_shutdown_endpoint(self):
    #     """Test the /shutdown endpoint."""
    #     self._start_server()
    #     self.assertIsNotNone(api_server.httpd, "Server should be running before shutdown test.")
    #     self.assertTrue(self.server_thread and self.server_thread.is_alive(), "Server thread should be alive.")

    #     response = requests.post(f"{BASE_URL}/shutdown")
    #     self.assertEqual(response.status_code, 200)
    #     self.assertEqual(response.json(), {"message": "Server shutting down..."})

    #     # Wait for server to shut down
    #     if self.server_thread:
    #         self.server_thread.join(timeout=2) # Wait for thread to terminate

    #     self.assertFalse(self.server_thread and self.server_thread.is_alive(), "Server thread should have terminated.")

    #     # Wait a bit longer for the server's finally block in run_server to complete fully,
    #     # which includes setting api_server.httpd to None.
    #     time.sleep(0.3) # Increased from 0.2 to 0.3 for more buffer

    #     self.assertIsNone(api_server.httpd, "Global api_server.httpd should be None after server shutdown sequence.")

    #     with self.assertRaises(requests.exceptions.ConnectionError):
    #         print(f"TestClient: Attempting to connect to {BASE_URL}/hello to confirm server is down...")
    #         # Increased timeout for this check, as the port might take a moment to be fully unlistenable.
    #         requests.get(f"{BASE_URL}/hello", timeout=1.0)

    #     # api_server.httpd should already be None due to run_server's finally block.
    #     # api_server.server_thread is not managed by api_server.py; self.server_thread is the test's handle.


if __name__ == '__main__':
    unittest.main()

# To run these tests:
# Ensure this file is in a 'tests' directory (e.g., src/test/)
# From the project root directory:
# python -m unittest src/test/test_api_server.py
# Note: Ensure no other service is running on TEST_SERVER_PORT during tests.
