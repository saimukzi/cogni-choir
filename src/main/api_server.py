"""
HTTP API Server for CogniChoir.

This module provides a simple HTTP server using Python's built-in `http.server`
that can be run in a separate thread from the main PyQt6 application.
It exposes endpoints for external integrations or interactions with CogniChoir.

Attributes:
    cc_api_key_manager (Optional[CcApiKeyManager]): A global instance of the
        CogniChoir API Key Manager, injected via `initialize_api_server_dependencies`.
        Used for authenticating API requests.
    encryption_serv (Optional[EncryptionService]): A global instance of the
        Encryption Service, injected via `initialize_api_server_dependencies`.
        Currently not directly used by the API server itself after CcApiKeyManager
        is initialized with it, but available for future use if needed.
    server_thread (Optional[threading.Thread]): The thread in which the HTTP
        server runs. This is managed by the main application.
    httpd (Optional[http.server.HTTPServer]): The HTTP server instance.
"""
API_SERVER_ENABLED: bool = True
"""Global flag to enable or disable the API server."""

import http.server
import json
import threading
from typing import Optional # Import Optional for type hinting

# Attempt to import from sibling modules.
from .ccapikey_manager import CcApiKeyManager
from .encryption_service import EncryptionService

cc_api_key_manager: Optional[CcApiKeyManager] = None
"""Global instance of CcApiKeyManager, injected by `initialize_api_server_dependencies`."""

encryption_serv: Optional[EncryptionService] = None
"""Global instance of EncryptionService, injected by `initialize_api_server_dependencies`."""

server_thread: Optional[threading.Thread] = None
"""The thread object running the HTTP server, managed by the main application."""

httpd: Optional[http.server.HTTPServer] = None
"""The HTTP server instance."""

httpd_lock = threading.Lock()
# Lock to manage access to the httpd instance across threads.

class ApiRequestHandler(http.server.BaseHTTPRequestHandler):
    """
    Request handler for the CogniChoir API server.

    Handles GET requests for /hello.
    """

    def _send_response(self, status_code: int, content_type: str, body: str):
        """Sends an HTTP response.

        Args:
            status_code: The HTTP status code.
            content_type: The content type of the response.
            body: The response body as a string.
        """
        self.send_response(status_code)
        self.send_header("Content-type", content_type)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _send_json_response(self, status_code: int, data: dict):
        """Sends a JSON HTTP response.

        Args:
            status_code: The HTTP status code.
            data: A dictionary to be serialized to JSON.
        """
        self._send_response(status_code, "application/json", json.dumps(data))

    def do_GET(self):
        """Handles GET requests.

        Responds to /hello with authentication.
        Responds with 404 for other paths.
        """
        if self.path == '/hello':
            provided_api_key = self.headers.get("CcApiKey")
            if not provided_api_key:
                provided_api_key = self.headers.get("ccapikey")

            if not provided_api_key:
                self._send_json_response(401, {"error": "API key required"})
                return

            if cc_api_key_manager is None:
                self._send_json_response(500, {"error": "API key manager not initialized"})
                return

            is_valid = False
            try:
                all_key_names = cc_api_key_manager.list_key_names()
                for key_name in all_key_names:
                    stored_key_value = cc_api_key_manager.get_key(key_name)
                    if stored_key_value == provided_api_key:
                        is_valid = True
                        break
            except Exception:
                # Log the exception server-side for diagnostics.
                # print(f"Error during API key validation: {e}", file=sys.stderr)
                self._send_json_response(500, {"error": "Server error during key validation"})
                return

            if not is_valid:
                self._send_json_response(403, {"error": "Invalid API key"})
                return

            self._send_json_response(200, {"message": "hello, authenticated user!"})
        else:
            self._send_json_response(404, {"error": "Not Found"})

    def do_POST(self):
        """Handles POST requests.

        Responds with 404 for other paths.
        """
        # if self.path == '/shutdown':
        #     self._send_json_response(200, {"message": "Server shutting down..."})
        #     # Schedule shutdown in a new thread to allow response to complete.
        #     threading.Thread(target=self.server.shutdown).start() # type: ignore[attr-defined]

        self._send_json_response(404, {"error": "Not Found"})

def initialize_api_server_dependencies(cc_manager: CcApiKeyManager, enc_service: EncryptionService):
    """
    Initializes dependencies required by the API server.

    This function is called from the main application (main_window.py) before
    the API server thread is started. It sets global instances of the
    CcApiKeyManager and EncryptionService for use by API endpoints.

    Args:
        cc_manager (CcApiKeyManager): An initialized instance of the CcApiKeyManager.
        enc_service (EncryptionService): An initialized instance of the EncryptionService.
    """
    global cc_api_key_manager
    global encryption_serv
    cc_api_key_manager = cc_manager
    encryption_serv = enc_service
    # print("API server dependencies initialized.") # Or use logging module

def set_api_server_enabled(enable: bool):
    """Sets the global state for enabling or disabling the API server.

    Args:
        enable (bool): If True, the API server can be started. If False,
                       calls to `run_server` will not start the server.
    """
    global API_SERVER_ENABLED
    API_SERVER_ENABLED = enable

def shutdown_server():
    """
    Shuts down the HTTP server.

    Signals the HTTPServer instance to stop serving requests and shut down.
    This function is typically called from a different thread than the one
    running the server, or as a result of a specific request (e.g., /shutdown).
    """
    global httpd
    with httpd_lock:  # Ensure thread-safe access to httpd
        if httpd:
            print("Attempting to shut down API server...")
            httpd.shutdown() # Signal the server to stop
            httpd.server_close() # Close the server socket
            httpd = None
            print("API server shut down.")
        else:
            print("API server is not running or already shut down.")


def run_server(port: int, debug: bool = False): # pylint: disable=unused-argument
    """
    Starts the HTTP server if API_SERVER_ENABLED is True.

    If `API_SERVER_ENABLED` is False, this function will print a message
    to the console and return immediately without starting the server.
    Otherwise, it creates an `http.server.HTTPServer` instance with
    `ApiRequestHandler` and starts it.

    This function is intended to be run in a separate thread from the main
    application to avoid blocking the GUI.

    Args:
        port (int): The port number on which the server will listen.
        debug (bool): This argument is kept for compatibility with the previous
                      Flask `run_server` signature but is not used by `HTTPServer`.
    """
    global API_SERVER_ENABLED
    global httpd # Ensure we are referencing the global httpd
    # server_thread is managed by the caller (e.g. main_window.py or tests)

    if not API_SERVER_ENABLED:
        print("API server is disabled by configuration.")
        return

    # Temporary variable to hold the server instance for this specific run_server call.
    # This helps manage cleanup correctly, especially if run_server could be called in quick succession
    # (though typically it's one server instance at a time).
    server_instance_for_this_call: Optional[http.server.HTTPServer] = None
    try:
        server_address = ('0.0.0.0', port)
        server_instance_for_this_call = http.server.HTTPServer(server_address, ApiRequestHandler)

        # Assign to the global `httpd` variable *after* successful creation.
        with httpd_lock:
            httpd = server_instance_for_this_call

        print(f"Starting HTTP server on port {port} (global httpd is now set)...")
        httpd.serve_forever() # Blocks until httpd.shutdown() is called from another thread.
        # ---- serve_forever() has returned, meaning shutdown() was called ----
        print(f"serve_forever() returned for port {port}. Server is shutting down.")

    except SystemExit:
        # SystemExit can be raised by httpd.shutdown() in some contexts or Python versions,
        # though typically it just makes serve_forever return.
        print(f"SystemExit caught during server operation on port {port}. Server shutting down.")
    except OSError as e:
        print(f"OSError starting or running API server on port {port}: {e}")
        # If the error occurred after server_instance_for_this_call was assigned to httpd,
        # we should clear the global httpd as it's no longer valid.
        with httpd_lock:
            if httpd == server_instance_for_this_call:
                httpd = None
    except Exception as e: # pylint: disable=broad-except
        print(f"An unexpected error occurred in API server on port {port}: {e}")
        with httpd_lock:
            if httpd == server_instance_for_this_call: # If this instance was the global one
                httpd = None
    finally:
        # This block executes after serve_forever() returns (normal shutdown)
        # or if an exception occurs in the try block.
        if server_instance_for_this_call:
            print(f"Server on port {port}: Closing server socket (server_instance_for_this_call exists).")
            server_instance_for_this_call.server_close() # Ensure the server socket is closed.

            with httpd_lock:
                # If the global `httpd` is still pointing to this instance, clear it.
                if httpd == server_instance_for_this_call:
                    httpd = None
                    print(f"Server on port {port}: Global httpd cleared.")
                else:
                    # This might happen if another thread/call modified global httpd in the meantime.
                    print(f"Server on port {port}: Global httpd (port: {httpd.server_port if httpd else 'None'}) did not match this instance, not clearing global httpd from this finally block.")
        else:
            # This means server_instance_for_this_call was never created (e.g. error in constructor)
            # If global httpd somehow points to something related, it's an inconsistent state.
            # However, httpd should ideally be None if server_instance_for_this_call is None.
            print(f"Server on port {port}: server_instance_for_this_call is None. Global httpd is: {'set' if httpd else 'None'}")

        print(f"HTTP server on port {port} has completed its run_server() execution path.")


if __name__ == '__main__':
    # This block allows testing the API server independently.
    # In the actual application, `run_server` is invoked by `main_window.py`
    # within a thread.

    # Dummy CcApiKeyManager and EncryptionService for testing
    class DummyEncryptionService(EncryptionService):
        def __init__(self):
            super().__init__("dummy_password")
        def encrypt(self, data: bytes) -> bytes: return data
        def decrypt(self, data: bytes) -> bytes: return data

    class DummyCcApiKeyManager(CcApiKeyManager):
        def __init__(self, encryption_service: EncryptionService):
            super().__init__(encryption_service)
            self._keys = {"test_key_name": "test_key_value"}

        def list_key_names(self) -> list[str]:
            return list(self._keys.keys())

        def get_key(self, name: str) -> Optional[str]:
            return self._keys.get(name)

        def add_key(self, name: str, key: str) -> None:
            self._keys[name] = key

        def delete_key(self, name: str) -> None:
            if name in self._keys:
                del self._keys[name]

    dummy_enc_service = DummyEncryptionService()
    dummy_manager = DummyCcApiKeyManager(dummy_enc_service)
    initialize_api_server_dependencies(dummy_manager, dummy_enc_service)

    test_port = 5001
    print(f"Starting HTTP development server on http://localhost:{test_port}/hello for testing...")

    # To run the server in a thread for testing, similar to the main app:
    server_test_thread = threading.Thread(target=run_server, args=(test_port,), daemon=True)
    server_test_thread.start()
    print("Server is running in a test thread. Send POST to /shutdown to stop.")
    print("Example valid GET: curl -H \"CcApiKey: test_key_value\" http://localhost:5001/hello")
    print("Example shutdown: curl -X POST http://localhost:5001/shutdown")

    # Keep the main thread alive for a bit to allow server interaction, or wait for thread.
    # For this example, we'll let it run until manually stopped or /shutdown is called.
    # In a real test, you might join the thread with a timeout or have a specific stop condition.
    try:
        while server_test_thread.is_alive():
            server_test_thread.join(timeout=1) # Keep main thread responsive
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received, shutting down server...")
        if httpd: # Global httpd instance
            httpd.shutdown()
            httpd.server_close()
        if server_test_thread.is_alive():
            server_test_thread.join()
    print("Test server finished.")
