"""
Flask API Server for CogniChoir.

This module provides a simple Flask-based API server that can be run in a
separate thread from the main PyQt6 application. It exposes endpoints that
can be used for external integrations or interactions with the CogniChoir application.

Attributes:
    api_app (Flask): The global Flask application instance.
    cc_api_key_manager (Optional[CcApiKeyManager]): A global instance of the
        CogniChoir API Key Manager, injected via `initialize_api_server_dependencies`.
        Used for authenticating API requests.
    encryption_serv (Optional[EncryptionService]): A global instance of the
        Encryption Service, injected via `initialize_api_server_dependencies`.
        Currently not directly used by the API server itself after CcApiKeyManager
        is initialized with it, but available for future use if needed.
    server_thread (Optional[threading.Thread]): The thread in which the Flask
        development server runs. This is managed by the main application.
"""
from flask import Flask, jsonify, request

# Attempt to import from sibling modules. This structure assumes that when the API server
# is run (typically as part of the main application), the Python path is set up
# such that 'src.main' or similar is accessible, or that it's run in a context
# where '.' refers to the 'src/main' directory.
from .ccapikey_manager import CcApiKeyManager
from .encryption_service import EncryptionService

api_app: Flask = Flask(__name__)
"""The global Flask application instance."""

cc_api_key_manager: CcApiKeyManager | None = None
"""Global instance of CcApiKeyManager, injected by `initialize_api_server_dependencies`."""

encryption_serv: EncryptionService | None = None
"""Global instance of EncryptionService, injected by `initialize_api_server_dependencies`.
Currently not directly used by api_server routes after CcApiKeyManager is initialized."""

server_thread = None # Explicitly typing can be done if Thread type is imported: Optional[threading.Thread]
"""The thread object running the Flask server, managed by the main application."""

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
    # Flask's app.logger can be used if it's configured, e.g., api_app.logger.info(...)
    # print("API server dependencies initialized.") # Or use logging module

@api_app.route('/hello', methods=['GET'])
def hello():
    """
    A simple authenticated endpoint that returns a JSON message.

    This endpoint requires API key authentication via the "CcApiKey" or "ccapikey"
    HTTP header. It validates the provided key against those managed by
    `CcApiKeyManager`.

    Returns:
        Response: A JSON response.
                  - `{"message": "hello, authenticated user!"}` on success (200 OK).
                  - `{"error": "API key required"}` if key is missing (401 Unauthorized).
                  - `{"error": "API key manager not initialized"}` if the server-side
                    manager isn't set up (500 Internal Server Error).
                  - `{"error": "Invalid API key"}` if key is invalid (403 Forbidden).
                  - `{"error": "Server error during key validation"}` on other validation
                    issues (500 Internal Server Error).
    """
    provided_api_key = request.headers.get("CcApiKey")
    if not provided_api_key:
        # Fallback to check lowercase header name for flexibility
        provided_api_key = request.headers.get("ccapikey")

    if not provided_api_key:
        return jsonify({"error": "API key required"}), 401

    if cc_api_key_manager is None:
        # This state indicates an issue with server setup/initialization.
        # Consider logging this server-side as it's an unexpected state.
        # api_app.logger.error("CcApiKeyManager not initialized in /hello endpoint.")
        return jsonify({"error": "API key manager not initialized"}), 500

    is_valid = False
    # The client sends a key *value*. The CcApiKeyManager stores keys by user-defined
    # *names*, with values in the keyring. So, we must iterate through all stored
    # keys, retrieve their actual values, and compare.
    try:
        all_key_names = cc_api_key_manager.list_key_names()
        for key_name in all_key_names:
            stored_key_value = cc_api_key_manager.get_key(key_name)
            if stored_key_value == provided_api_key:
                is_valid = True
                break # Key found and matched
    except Exception as e:
        # Log the exception server-side for diagnostics.
        # api_app.logger.error(f"Error during API key validation: {e}", exc_info=True)
        return jsonify({"error": "Server error during key validation"}), 500

    if not is_valid:
        return jsonify({"error": "Invalid API key"}), 403

    return jsonify({"message": "hello, authenticated user!"})

def run_server(port: int, debug: bool = False):
    """
    Starts the Flask development server.

    This function is intended to be run in a separate thread from the main
    application to avoid blocking the GUI. It configures the server to listen
    on all available network interfaces (`0.0.0.0`).

    Args:
        port (int): The port number on which the server will listen.
        debug (bool): If True, runs the Flask server in debug mode.
                      `use_reloader=False` is important when running in a thread
                      to prevent issues with the reloader.
    """
    # Note: Flask's built-in development server is not suitable for production use.
    # For production, a WSGI server like Gunicorn or uWSGI should be used.
    # The server runs in a separate thread, so it doesn't block the main application.
    # However, the dev server is not always thread-safe, especially with reloader.
    try:
        # `use_reloader=False` is crucial when running in a thread or when the server
        # is managed by an external process, as the reloader can cause issues.
        api_app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)
    except OSError as e:
        # This commonly occurs if the port is already in use.
        # In a real application, this error should be communicated back to the main thread/user.
        print(f"Error starting API server on port {port}: {e}")
        # Consider raising an exception or using a more robust logging/notification mechanism.

if __name__ == '__main__':
    # This block allows testing the API server independently.
    # In the actual application, `run_server` is invoked by `main_window.py`.
    # A dummy CcApiKeyManager and EncryptionService would be needed for full testing here,
    # or one would have to ensure a valid keyring backend is available and keys are pre-populated.

    # For basic startup test:
    test_port = 5001
    print(f"Starting Flask development server on http://localhost:{test_port}/hello for testing...")
    print("Note: For the /hello endpoint to work, CcApiKeyManager needs to be initialized")
    print("and have at least one API key. This standalone test does not initialize it.")
    print("You can test server startup and basic routing if /hello is not called, or modify")
    print("this section to initialize a dummy CcApiKeyManager for testing the endpoint.")
    run_server(port=test_port, debug=True)
