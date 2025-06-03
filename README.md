# Multi-AI Chat Application

A desktop application that allows users to interact with multiple AI language models from different providers within various chatrooms.

## Prerequisites

- Python 3.10 or newer.
- Required Python packages. Install them using pip:
  ```bash
  pip install -r requirements.txt
  ```

## Setup

1.  **Clone the Repository (Optional):**
    If you have downloaded the source code as a ZIP, extract it. If you are using Git:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **API Keys:**
    This application requires API keys for the AI services you wish to use (Google Gemini, OpenAI ChatGPT).
    - Launch the application.
    - Go to **Settings > Manage API Keys**.
    - Select the service (e.g., OpenAI, Gemini) from the dropdown.
    - Enter your API key and click "Save Key".
    - API keys are stored securely using the system's keyring/credential manager (with a JSON file fallback if keyring access fails).

## Running the Application

To run the application, execute the following command from the project root directory:

```bash
python src/main/main_window.py
```

## Features
- **Chatroom Management:** Create, rename, clone, and delete chatrooms.
- **Multi-AI Support:** Integrate and use multiple AI language models (e.g., Gemini, OpenAI) within any chatroom.
- **Bot Customization:** Configure individual bots with specific AI engines, models, and system prompts.
- **Bot Templates:** Create, manage, and reuse bot configurations as templates to quickly deploy similar bots.
- **API Key Management:** Securely store and manage API keys for different AI services using system keyring and encryption.
- **Master Password Protection:** Encrypt sensitive data like API keys and settings with a user-defined master password.
- **Message History:** Each chatroom maintains its conversation history, saved locally.
- **Internationalization:** Supports multiple languages for the UI (e.g., English, Chinese).

## Running Tests

To run the unit tests, execute the following command from the project root directory:

```bash
python -m unittest discover src/test
```
Make sure your `PYTHONPATH` is set up to include the project root or `src` directory if you encounter import errors, e.g.:
```bash
export PYTHONPATH=.  # For Linux/macOS
set PYTHONPATH=.    # For Windows (in Command Prompt)
# Or run as: python -m unittest discover -s src/test -p 'test_*.py'
```
(Note: The test runner should ideally work without manual PYTHONPATH changes if `discover` is started from the root and test files use appropriate relative imports for `src.main.*` modules, which is the current setup.)


## Project Structure

- **`src/main/`**: Contains the main application source code.
  - **`ai_bots.py`**: Core `Bot` and `AIEngine` abstract class.
  - **`ai_engines/`**: Concrete AI engine implementations (Gemini, OpenAI, Grok placeholder).
  - **`thirdpartyapikey_manager.py`**: Handles storage and retrieval of API keys.
  - **`chatroom.py`**: `Chatroom` and `ChatroomManager` logic.
  - **`main_window.py`**: Main application window (PyQt6 UI).
  - **`message.py`**: `Message` class definition.
- **`src/test/`**: Contains unit tests.
- **`data/`**: Used for storing application data.
  - **`chatrooms/`**: Stores chatroom data (JSON files).
  - (Fallback `thirdpartyapikeys.json` might appear here if keyring fails).
- **`design/`**: Contains design documents and use cases.
- **`i18n/`**: Contains internationalization files (e.g., `app_zh_TW.ts`, `app_zh_TW.qm`).
- **`requirements.txt`**: Lists Python package dependencies.
- **`README.md`**: This file.

## Logging

This application uses the Python `logging` module to record its operations and any potential errors.
- Logs are saved to a file named `app.log` in the same directory where the application is run.
- The log file is overwritten each time the application starts.
- The default logging level is DEBUG, which means detailed information useful for troubleshooting will be recorded.
- Log entries include a timestamp, log level (DEBUG, INFO, WARNING, ERROR), the module where the log originated, and the log message.

This log can be helpful for:
- Understanding the application's behavior.
- Diagnosing issues or unexpected behavior.
- Tracking events like chatroom creation, bot interactions, and API calls.
