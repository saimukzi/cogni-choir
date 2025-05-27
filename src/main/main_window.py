"""
Main window and associated dialogs for the Chat Application.

This module defines the main graphical user interface (GUI) for the chat
application, including the `MainWindow` class which orchestrates the various
UI elements and interactions. It also defines helper dialog classes:
- `ApiKeyDialog`: For managing API keys for different AI services.
- `CreateFakeMessageDialog`: For manually adding messages to a chatroom (for testing/dev).

The application uses PyQt6 for its GUI components. Internationalization (i18n)
is supported using QTranslator. Logging is used for diagnostics.
"""
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QLabel, QInputDialog, QMessageBox,
    QListWidgetItem, QDialog, QComboBox, QLineEdit, QFormLayout,
    QTextEdit, QSplitter, QAbstractItemView, QDialogButtonBox,
    QMenu # Added QMenu for context menu
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QTranslator, QLocale, QLibraryInfo, QPoint
import os # For path construction
import logging # For logging

# Attempt to import from sibling modules
try:
    from .chatroom import Chatroom, ChatroomManager
    from .ai_bots import Bot, AIEngine, create_bot # AIEngine and Bot remain in ai_bots, added create_bot
    from .ai_engines import GeminiEngine, GrokEngine # Engines from new package
    from .api_key_manager import ApiKeyManager
    from .message import Message
    from . import ai_engines
except ImportError:
    # Fallback for running script directly for testing
    from chatroom import Chatroom, ChatroomManager
    from ai_bots import Bot, AIEngine, create_bot # AIEngine and Bot remain in ai_bots, added create_bot
    from ai_engines import GeminiEngine, GrokEngine # Engines from new package
    from api_key_manager import ApiKeyManager
    from message import Message


class ApiKeyDialog(QDialog):
    """A dialog for managing API keys for various AI services."""
    def __init__(self, api_key_manager: ApiKeyManager, parent=None):
        """Initializes the ApiKeyDialog.

        Args:
            api_key_manager: An instance of ApiKeyManager to handle key storage.
            parent: The parent widget, if any.
        """
        super().__init__(parent)
        self.api_key_manager = api_key_manager
        self.setWindowTitle(self.tr("API Key Management"))
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.service_combo = QComboBox()
        # self.service_combo.addItems(["OpenAI", "Gemini", "Grok"]) # Service names should match what ApiKeyManager expects
        self.service_combo.addItems(ai_engines.ENGINE_TYPE_TO_CLASS_MAP.keys()) # Dynamically load service names from ENGINE_TYPE_TO_CLASS_MAP
        self.service_combo.currentTextChanged.connect(self._load_key_for_display)
        form_layout.addRow(self.tr("Service:"), self.service_combo)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password) # Mask API key
        form_layout.addRow(self.tr("API Key:"), self.api_key_input)
        
        layout.addLayout(form_layout)

        buttons_layout = QHBoxLayout()
        save_button = QPushButton(self.tr("Save Key"))
        save_button.clicked.connect(self._save_key)
        buttons_layout.addWidget(save_button)

        delete_button = QPushButton(self.tr("Delete Key"))
        delete_button.clicked.connect(self._delete_key)
        buttons_layout.addWidget(delete_button)
        
        layout.addLayout(buttons_layout)

        close_button = QPushButton(self.tr("Close"))
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)

        self._load_key_for_display() # Initial load

    def _load_key_for_display(self):
        """Loads and displays the API key for the currently selected service."""
        selected_service = self.service_combo.currentText()
        if selected_service: # Ensure a service is actually selected
            key = self.api_key_manager.load_key(selected_service)
            self.api_key_input.setText(key if key else "")
        else:
            self.api_key_input.clear()


    def _save_key(self):
        """Saves the API key entered in the input field for the selected service."""
        selected_service = self.service_combo.currentText()
        key_text = self.api_key_input.text()
        if not selected_service:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Please select a service."))
            return
        if not key_text:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("API Key cannot be empty."))
            return

        self.api_key_manager.save_key(selected_service, key_text)
        QMessageBox.information(self, self.tr("Success"), self.tr("API Key saved."))

    def _delete_key(self):
        """Deletes the API key for the selected service after confirmation."""
        selected_service = self.service_combo.currentText()
        if not selected_service:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Please select a service to delete the key for."))
            return
            
        reply = QMessageBox.question(self, self.tr("Confirm Delete"),
                                     self.tr("Are you sure you want to delete the API key for {0}?").format(selected_service),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.api_key_manager.delete_key(selected_service)
            self.api_key_input.clear()
            QMessageBox.information(self, self.tr("Success"), self.tr("API Key deleted."))


class CreateFakeMessageDialog(QDialog):
    """A dialog for creating and inserting a 'fake' message into a chatroom.

    This is primarily a development/testing utility. It allows specifying
    the sender (User or any existing bot) and the message content.
    """
    def __init__(self, current_bots: list[str], parent=None):
        """Initializes the CreateFakeMessageDialog.

        Args:
            current_bots: A list of names of bots currently in the active chatroom.
            parent: The parent widget, if any.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Create Fake Message"))

        layout = QVBoxLayout(self)

        self.content_label = QLabel(self.tr("Message Content:"))
        layout.addWidget(self.content_label)
        self.content_input = QTextEdit()
        self.content_input.setMinimumHeight(80) # Give some space for content
        layout.addWidget(self.content_input)

        self.sender_label = QLabel(self.tr("Sender:"))
        layout.addWidget(self.sender_label)
        self.sender_combo = QComboBox()
        self.sender_combo.addItem("User") # Default sender
        for bot_name in current_bots:
            self.sender_combo.addItem(bot_name)
        layout.addWidget(self.sender_combo)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_data(self) -> tuple[str, str] | None:
        """Retrieves the sender and content from the dialog if accepted.

        Returns:
            A tuple containing the sender name (str) and message content (str)
            if the dialog was accepted, otherwise None.
        """
        if self.result() == QDialog.DialogCode.Accepted:
            return self.sender_combo.currentText(), self.content_input.toPlainText()
        return None
    
    # Using QApplication.translate for robustness, especially if this dialog moves to another file.
    def tr(self, text, disambiguation=None, n=-1) -> str:
        """Translates text using the application's translator.

        This method is provided for convenience if this dialog were to be
        moved to its own module, ensuring it uses the correct translation context.

        Args:
            text: The text to translate.
            disambiguation: Optional disambiguation string.
            n: Optional number for plural forms.

        Returns:
            The translated string.
        """
        return QApplication.translate("CreateFakeMessageDialog", text, disambiguation, n)


class AddBotDialog(QDialog):
    """A dialog for adding a new bot to a chatroom.

    This dialog allows the user to specify the bot's name, select an AI engine,
    optionally provide a model name, and set a system prompt for the bot.
    It also validates the bot name for emptiness and uniqueness.
    """
    def __init__(self, existing_bot_names: list[str], parent=None):
        """Initializes the AddBotDialog.

        Args:
            existing_bot_names: A list of names of bots that already exist
                                in the current context, used for validation.
            parent: The parent widget, if any.
        """
        super().__init__(parent)
        self.existing_bot_names = existing_bot_names
        self.setWindowTitle(self.tr("Add New Bot"))
        self.setMinimumWidth(400) # Set a reasonable minimum width

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Bot Name
        self.bot_name_label = QLabel(self.tr("Bot Name:"))
        self.bot_name_input = QLineEdit()
        form_layout.addRow(self.bot_name_label, self.bot_name_input)

        # AI Engine
        self.engine_label = QLabel(self.tr("AI Engine:"))
        self.engine_combo = QComboBox()
        # Populate with keys from ai_engines.ENGINE_TYPE_TO_CLASS_MAP
        # Ensure ai_engines is imported at the top of the file
        if hasattr(ai_engines, 'ENGINE_TYPE_TO_CLASS_MAP'):
            self.engine_combo.addItems(ai_engines.ENGINE_TYPE_TO_CLASS_MAP.keys())
        else:
            # Fallback or error handling if import failed or map is not there
            # This case should ideally not be hit if imports are correct
            self.engine_combo.addItem("Error: Engines not loaded")
        form_layout.addRow(self.engine_label, self.engine_combo)

        # Model Name (Optional)
        self.model_name_label = QLabel(self.tr("Model Name (Optional):"))
        self.model_name_input = QLineEdit()
        form_layout.addRow(self.model_name_label, self.model_name_input)

        # System Prompt
        self.system_prompt_label = QLabel(self.tr("System Prompt:"))
        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setMinimumHeight(100)
        form_layout.addRow(self.system_prompt_label, self.system_prompt_input)

        main_layout.addLayout(form_layout)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept) # Connect to custom accept method
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def accept(self):
        """
        Validates the bot name before accepting the dialog.

        Checks if the bot name is empty or if it already exists.
        If validation fails, a warning message is displayed, and the dialog
        remains open. If validation passes, the dialog is accepted.
        """
        bot_name = self.bot_name_input.text().strip()
        if not bot_name:
            QMessageBox.warning(self, self.tr("Input Error"), self.tr("Bot name cannot be empty."))
            return  # Keep dialog open

        if bot_name in self.existing_bot_names:
            QMessageBox.warning(self, self.tr("Input Error"), 
                                self.tr("A bot named '{0}' already exists. Please choose a different name.").format(bot_name))
            return  # Keep dialog open

        super().accept() # All checks passed, proceed to close

    def get_data(self) -> dict | None:
        """Retrieves the data entered into the dialog.

        Returns:
            A dictionary containing the bot's configuration data if the dialog
            was accepted (OK clicked), otherwise None. The dictionary includes:
            - "bot_name": str
            - "engine_type": str
            - "model_name": str
            - "system_prompt": str
        """
        if self.result() == QDialog.DialogCode.Accepted:
            return {
                "bot_name": self.bot_name_input.text(),
                "engine_type": self.engine_combo.currentText(),
                "model_name": self.model_name_input.text(),
                "system_prompt": self.system_prompt_input.toPlainText()
            }
        return None

    # Using QApplication.translate for robustness if this dialog becomes more complex
    # or needs its own translation context.
    def tr(self, text, disambiguation=None, n=-1) -> str:
        """Translates text using the application's translator.

        Args:
            text: The text to translate.
            disambiguation: Optional disambiguation string.
            n: Optional number for plural forms.

        Returns:
            The translated string.
        """
        return QApplication.translate("AddBotDialog", text, disambiguation, n)


class MainWindow(QMainWindow):
    """The main window of the chat application.

    This class orchestrates the user interface, manages chatrooms and bots,
    and handles user interactions for sending messages, managing API keys,
    and configuring chatrooms.
    """
    def __init__(self):
        """Initializes the MainWindow.

        Sets up logging, API key manager, chatroom manager, and initializes the UI.
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle(self.tr("Chatroom and Bot Manager"))
        self.setGeometry(100, 100, 800, 600)

        self.api_key_manager = ApiKeyManager()
        self.chatroom_manager = ChatroomManager(api_key_manager=self.api_key_manager)

        self._init_ui()
        self._update_chatroom_list() # Initial population

    def _init_ui(self):
        """Initializes the main user interface components and layout.

        This includes setting up the menu bar, chatroom list, bot list,
        message display area, message input, and various control buttons.
        A QSplitter is used to make the chatroom/bot panel and the message
        panel resizable.
        """
        self.logger.debug("Initializing UI...") # Changed to DEBUG
        # Central Widget and Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # --- Menu Bar ---
        settings_menu = self.menuBar().addMenu(self.tr("Settings"))
        manage_keys_action = QAction(self.tr("Manage API Keys"), self)
        manage_keys_action.triggered.connect(self._show_api_key_dialog)
        settings_menu.addAction(manage_keys_action)

        # --- Main Layout (Splitter for resizable panels) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal, central_widget)
        main_layout = QHBoxLayout(central_widget) # Main layout to hold the splitter
        main_layout.addWidget(main_splitter)


        # --- Left Panel (Chatroom List and Bot List) ---
        left_panel_widget = QWidget()
        left_panel_layout = QVBoxLayout(left_panel_widget)
        
        # Chatroom Management
        chatroom_label = QLabel(self.tr("Chatrooms"))
        left_panel_layout.addWidget(chatroom_label)
        self.chatroom_list_widget = QListWidget()
        self.chatroom_list_widget.currentItemChanged.connect(self._on_selected_chatroom_changed)
        # Attempt to set stylesheet for selected item clarity
        self.chatroom_list_widget.setStyleSheet("QListWidget::item:selected { background-color: #ADD8E6; color: black; }")
        left_panel_layout.addWidget(self.chatroom_list_widget)
        
        chatroom_buttons_layout = QHBoxLayout()
        self.new_chatroom_button = QPushButton(self.tr("New Chatroom")) # Store as member for state updates
        self.new_chatroom_button.clicked.connect(self._create_chatroom)
        self.rename_chatroom_button = QPushButton(self.tr("Rename Chatroom")) # Store as member
        self.rename_chatroom_button.clicked.connect(self._rename_chatroom)
        self.clone_chatroom_button = QPushButton(self.tr("Clone Chatroom")) 
        self.clone_chatroom_button.clicked.connect(self._clone_selected_chatroom)
        self.delete_chatroom_button = QPushButton(self.tr("Delete Chatroom")) # Store as member
        self.delete_chatroom_button.clicked.connect(self._delete_chatroom)
        
        chatroom_buttons_layout.addWidget(self.new_chatroom_button)
        chatroom_buttons_layout.addWidget(self.rename_chatroom_button)
        chatroom_buttons_layout.addWidget(self.clone_chatroom_button)
        chatroom_buttons_layout.addWidget(self.delete_chatroom_button)
        left_panel_layout.addLayout(chatroom_buttons_layout)

        # Bot Management (within the same left panel)
        self.bot_panel_label = QLabel(self.tr("Bots in Selected Chatroom"))
        left_panel_layout.addWidget(self.bot_panel_label)
        self.bot_list_widget = QListWidget()
        left_panel_layout.addWidget(self.bot_list_widget) # Stretch factor for bot list?
        bot_buttons_layout = QHBoxLayout()
        self.add_bot_button = QPushButton(self.tr("Add Bot"))
        self.add_bot_button.clicked.connect(self._add_bot_to_chatroom)
        self.remove_bot_button = QPushButton(self.tr("Remove Bot"))
        self.remove_bot_button.clicked.connect(self._remove_bot_from_chatroom)
        bot_buttons_layout.addWidget(self.add_bot_button)
        bot_buttons_layout.addWidget(self.remove_bot_button)
        left_panel_layout.addLayout(bot_buttons_layout)
        
        main_splitter.addWidget(left_panel_widget)


        # --- Right Panel (Message Display and Input) ---
        right_panel_widget = QWidget()
        right_panel_layout = QVBoxLayout(right_panel_widget)

        self.message_display_area = QListWidget() 
        self.message_display_area.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.message_display_area.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.message_display_area.customContextMenuRequested.connect(self._show_message_context_menu)
        right_panel_layout.addWidget(self.message_display_area, 5) 

        # Message Actions Layout (for delete and fake message buttons)
        message_actions_layout = QHBoxLayout()
        self.delete_message_button = QPushButton(self.tr("Delete Selected Message(s)"))
        self.delete_message_button.clicked.connect(self._delete_selected_messages)
        message_actions_layout.addWidget(self.delete_message_button)
        
        self.create_fake_message_button = QPushButton(self.tr("Create Fake Message"))
        self.create_fake_message_button.clicked.connect(self._show_create_fake_message_dialog)
        message_actions_layout.addWidget(self.create_fake_message_button)
        right_panel_layout.addLayout(message_actions_layout)


        # Message Input Area
        message_input_layout = QHBoxLayout()
        self.message_input_area = QLineEdit()
        self.message_input_area.returnPressed.connect(self._send_user_message)
        message_input_layout.addWidget(self.message_input_area)
        self.send_message_button = QPushButton(self.tr("Send"))
        self.send_message_button.clicked.connect(self._send_user_message)
        message_input_layout.addWidget(self.send_message_button)
        right_panel_layout.addLayout(message_input_layout)

        # Bot Response Area
        bot_response_layout = QHBoxLayout()
        bot_response_label = QLabel(self.tr("Select Bot to Respond:"))
        bot_response_layout.addWidget(bot_response_label)
        self.bot_response_selector = QComboBox()
        bot_response_layout.addWidget(self.bot_response_selector)
        self.trigger_bot_response_button = QPushButton(self.tr("Get Bot Response"))
        self.trigger_bot_response_button.clicked.connect(self._trigger_bot_response)
        bot_response_layout.addWidget(self.trigger_bot_response_button)
        right_panel_layout.addLayout(bot_response_layout)

        main_splitter.addWidget(right_panel_widget)
        main_splitter.setSizes([250, 550]) # Initial sizes for left and right panels

        self._update_bot_panel_state(False) # Initial state
        self._update_message_related_ui_state(False) # Message UI disabled initially

    def _update_message_related_ui_state(self, enabled: bool):
        """Updates the enabled state of message-related UI elements.

        This includes the message input field, send button, bot response selector,
        delete message button, trigger bot response button, and create fake message button.
        It also clears the message display and bot response selector if disabling.

        Args:
            enabled: True to enable the UI elements, False to disable them.
        """
        self.message_input_area.setEnabled(enabled)
        self.send_message_button.setEnabled(enabled)
        self.bot_response_selector.setEnabled(enabled)
        
        # Specific state for delete button
        self.delete_message_button.setEnabled(enabled and bool(self.message_display_area.selectedItems()))
        # Specific state for trigger bot response button
        self.trigger_bot_response_button.setEnabled(enabled and bool(self.bot_response_selector.currentText()))
        # Specific state for create fake message button
        self.create_fake_message_button.setEnabled(enabled)

        if not enabled:
            self.message_display_area.clear()
            self.bot_response_selector.clear()

    def _show_message_context_menu(self, position: QPoint):
        """Displays a context menu for messages in the message display area.

        Currently, the only action is to delete selected message(s).

        Args:
            position: The position where the context menu was requested (local to the widget).
        """
        menu = QMenu()
        if self.message_display_area.selectedItems():
            delete_action = menu.addAction(self.tr("Delete Message(s)"))
            delete_action.triggered.connect(self._delete_selected_messages)
        menu.exec(self.message_display_area.mapToGlobal(position))


    def _update_bot_panel_state(self, enabled: bool, chatroom_name: str | None = None):
        """Updates the enabled state of the bot management panel and its label.

        This includes the bot list widget, add bot button, and remove bot button.
        The label of the panel is updated to reflect the selected chatroom or
        indicate that no chatroom is selected.

        Args:
            enabled: True to enable the bot panel, False to disable it.
            chatroom_name: The name of the currently selected chatroom, if any.
        """
        self.bot_list_widget.setEnabled(enabled)
        self.add_bot_button.setEnabled(enabled)
        self.remove_bot_button.setEnabled(enabled and bool(self.bot_list_widget.currentItem()))
        
        if enabled and chatroom_name:
            self.bot_panel_label.setText(self.tr("Bots in '{0}'").format(chatroom_name))
        elif not enabled and self.chatroom_list_widget.currentItem() is None : # No chatroom selected
             self.bot_panel_label.setText(self.tr("Bots (No Chatroom Selected)"))
        # else: Keep current label if chatroom selected but panel is being disabled for other reasons

    def _update_chatroom_related_button_states(self):
        """Updates the enabled state of chatroom action buttons.

        Buttons like "Rename Chatroom", "Clone Chatroom", and "Delete Chatroom"
        are enabled only if a chatroom is currently selected in the list.
        """
        has_selection = bool(self.chatroom_list_widget.currentItem())
        self.rename_chatroom_button.setEnabled(has_selection)
        self.clone_chatroom_button.setEnabled(has_selection)
        self.delete_chatroom_button.setEnabled(has_selection)


    def _update_chatroom_list(self):
        """Refreshes the list of chatrooms displayed in the UI.

        It preserves the current selection if possible. If no chatroom
        is selected after the update (e.g., if the list becomes empty),
        it updates the bot list and related UI states accordingly.
        """
        current_selection_name = self.chatroom_list_widget.currentItem().text() if self.chatroom_list_widget.currentItem() else None
        
        self.chatroom_list_widget.clear()
        # list_chatrooms now returns list[Chatroom]
        for chatroom_obj in self.chatroom_manager.list_chatrooms(): 
            item = QListWidgetItem(chatroom_obj.name)
            self.chatroom_list_widget.addItem(item)
            if chatroom_obj.name == current_selection_name:
                self.chatroom_list_widget.setCurrentItem(item) # Restore selection
        
        if self.chatroom_list_widget.currentItem() is None:
            self._update_bot_list(None)
            self._update_bot_panel_state(False)
            self._update_message_related_ui_state(False)
        
        self._update_chatroom_related_button_states()


    def _on_selected_chatroom_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handles the change in the selected chatroom.

        Updates the bot list, bot panel state, message display, bot response selector,
        and the overall state of message-related UI elements based on the newly
        selected chatroom. If no chatroom is selected, these UI elements are
        typically disabled or cleared.

        Args:
            current: The currently selected QListWidgetItem (the new selection).
            previous: The previously selected QListWidgetItem.
        """
        self._update_chatroom_related_button_states() # Update button states based on selection
        if current:
            selected_chatroom_name = current.text()
            self._update_bot_list(selected_chatroom_name) 
            self._update_bot_panel_state(True, selected_chatroom_name)
            self._update_message_display()
            self._update_bot_response_selector() 
            self._update_message_related_ui_state(True)
        else:
            self._update_bot_list(None)
            self._update_bot_panel_state(False)
            self._update_message_display() 
            self._update_bot_response_selector() 
            self._update_message_related_ui_state(False)


    def _clone_selected_chatroom(self):
        """Clones the currently selected chatroom.

        Prompts the user for confirmation. If successful, updates the
        chatroom list and optionally selects the newly cloned chatroom.
        Shows success or error messages accordingly.
        """
        current_item = self.chatroom_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected to clone."))
            return

        original_chatroom_name = current_item.text()
        self.logger.info(f"Attempting to clone chatroom: {original_chatroom_name}")
        cloned_chatroom = self.chatroom_manager.clone_chatroom(original_chatroom_name)

        if cloned_chatroom:
            self.logger.info(f"Chatroom '{original_chatroom_name}' cloned successfully as '{cloned_chatroom.name}'.")
            self._update_chatroom_list()
            # Optionally, find and select the new chatroom in the list
            for i in range(self.chatroom_list_widget.count()):
                if self.chatroom_list_widget.item(i).text() == cloned_chatroom.name:
                    self.chatroom_list_widget.setCurrentRow(i)
                    break
            QMessageBox.information(self, self.tr("Success"), 
                                    self.tr("Chatroom '{0}' cloned as '{1}'.").format(original_chatroom_name, cloned_chatroom.name))
        else:
            self.logger.error(f"Failed to clone chatroom '{original_chatroom_name}'.")
            QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to clone chatroom '{0}'.").format(original_chatroom_name))


    def _update_message_display(self):
        """Refreshes the message display area for the currently selected chatroom.

        Messages are cleared and then repopulated from the chatroom's history,
        sorted by timestamp. Each message item stores its timestamp for later use
        (e.g., deletion).
        """
        current_chatroom_name = self.chatroom_list_widget.currentItem().text() if self.chatroom_list_widget.currentItem() else None
        self.message_display_area.clear()
        if current_chatroom_name:
            chatroom = self.chatroom_manager.get_chatroom(current_chatroom_name)
            if chatroom:
                # Ensure sorted display by timestamp
                for message in sorted(chatroom.get_messages(), key=lambda m: m.timestamp):
                    item = QListWidgetItem(message.to_display_string())
                    item.setData(Qt.ItemDataRole.UserRole, message.timestamp) # Store timestamp
                    self.message_display_area.addItem(item)

    def _delete_selected_messages(self):
        """Deletes the selected messages from the current chatroom.

        Prompts the user for confirmation before deleting. Updates the
        message display if messages are deleted.
        """
        current_chatroom_name = self.chatroom_list_widget.currentItem().text() if self.chatroom_list_widget.currentItem() else None
        if not current_chatroom_name:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected."))
            return

        chatroom = self.chatroom_manager.get_chatroom(current_chatroom_name)
        if not chatroom:
            return # Should not happen if UI is consistent

        selected_items = self.message_display_area.selectedItems()
        if not selected_items:
            QMessageBox.information(self, self.tr("Information"), self.tr("No messages selected to delete."))
            return

        reply = QMessageBox.question(self, self.tr("Confirm Deletion"),
                                   self.tr("Are you sure you want to delete {0} message(s)?").format(len(selected_items)),
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            for item in selected_items:
                timestamp = item.data(Qt.ItemDataRole.UserRole)
                if chatroom.delete_message(timestamp): # delete_message calls _notify_chatroom_updated
                    deleted_count +=1
            if deleted_count > 0:
                self._update_message_display() # Refresh display


    def _show_create_fake_message_dialog(self):
        """Shows the dialog to create a 'fake' message.

        If a chatroom is selected and the dialog is accepted with valid content,
        the message is added to the current chatroom and the display is updated.
        """
        current_chatroom_name = self.chatroom_list_widget.currentItem().text() if self.chatroom_list_widget.currentItem() else None
        if not current_chatroom_name:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected."))
            return

        chatroom = self.chatroom_manager.get_chatroom(current_chatroom_name)
        if not chatroom:
            return # Should not happen

        current_bot_names = [bot.get_name() for bot in chatroom.list_bots()]
        dialog = CreateFakeMessageDialog(current_bot_names, self)
        
        if dialog.exec(): # exec() shows the dialog
            data = dialog.get_data()
            if data:
                sender, content = data
                if not content.strip():
                    QMessageBox.warning(self, self.tr("Warning"), self.tr("Message content cannot be empty."))
                    return
                chatroom.add_message(sender, content) # This will use current timestamp and trigger save
                self._update_message_display() # Refresh


    def _send_user_message(self):
        """Sends a message from the user to the currently selected chatroom.

        The message content is taken from the message input area.
        If successful, the message is added to the chatroom, the display
        is updated, and the input area is cleared.
        """
        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected to send message."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom: # Should not happen if item is selected
            QMessageBox.critical(self, self.tr("Error"), self.tr("Selected chatroom not found."))
            return

        text = self.message_input_area.text().strip()
        if not text:
            return

        self.logger.info(f"Sending user message of length {len(text)} to chatroom '{chatroom_name}'.")
        chatroom.add_message("User", text)
        self._update_message_display()
        self.message_input_area.clear()

    def _update_bot_response_selector(self):
        """Updates the bot response selector combo box.

        Populates the combo box with the names of bots from the currently
        selected chatroom. The "Get Bot Response" button is enabled only
        if there are bots in the selector.
        """
        self.bot_response_selector.clear()
        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if chatroom:
            for bot in chatroom.list_bots():
                self.bot_response_selector.addItem(bot.get_name())
        
        # Disable trigger button if no bots are available
        self.trigger_bot_response_button.setEnabled(self.bot_response_selector.count() > 0)


    def _trigger_bot_response(self):
        """Triggers a response from the selected bot in the current chatroom.

        Collects the conversation history, sends it to the selected bot's
        engine, and displays the response. Handles potential errors like
        missing API keys or exceptions during generation. The UI is updated
        to indicate that the bot is processing.
        """
        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            self.logger.error(f"Trigger bot response: Selected chatroom '{chatroom_name}' not found.")
            QMessageBox.critical(self, self.tr("Error"), self.tr("Selected chatroom not found."))
            return

        if self.bot_response_selector.count() == 0:
            self.logger.warning(f"Trigger bot response: No bots in chatroom '{chatroom_name}'.")
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Selected chatroom has no bots to respond."))
            return
            
        selected_bot_name = self.bot_response_selector.currentText()
        if not selected_bot_name:
            self.logger.warning("Trigger bot response: No bot selected.")
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No bot selected to respond."))
            return

        bot = chatroom.get_bot(selected_bot_name)
        if not bot: 
            self.logger.error(f"Trigger bot response: Selected bot '{selected_bot_name}' not found in chatroom '{chatroom_name}'.")
            QMessageBox.critical(self, self.tr("Error"), self.tr("Selected bot not found in chatroom."))
            return

        engine = bot.get_engine()
        engine_type_name = type(engine).__name__
        
        if isinstance(engine, (GeminiEngine, GrokEngine)): 
            api_key = self.api_key_manager.load_key(engine_type_name)
            if not api_key:
                self.logger.warning(f"Trigger bot response: API key missing for bot '{bot.get_name()}' using engine '{engine_type_name}'.")
                QMessageBox.warning(self, self.tr("API Key Missing"), 
                                    self.tr("Bot {0} (using {1}) needs an API key. Please set it in Settings.").format(bot.get_name(), engine_type_name))
                return
        
        self.logger.info(f"Attempting to trigger bot response for bot '{selected_bot_name}' in chatroom '{chatroom_name}'.")
        conversation_history = chatroom.get_messages()

        if not conversation_history:
            self.logger.info(f"Trigger bot response: No messages in chatroom '{chatroom_name}' to respond to.")
            QMessageBox.information(self, self.tr("Info"), self.tr("No messages in chat to respond to."))
            return 
        
        original_button_text = self.trigger_bot_response_button.text()
        try:
            self.trigger_bot_response_button.setText(self.tr("Waiting for AI..."))
            self.trigger_bot_response_button.setEnabled(False)
            QApplication.processEvents() 

            ai_response = bot.generate_response(conversation_history=conversation_history)
            
            self.logger.info(f"Bot '{selected_bot_name}' generated response successfully in chatroom '{chatroom_name}'.")
            chatroom.add_message(bot.get_name(), ai_response)
            self._update_message_display()
        except Exception as e: 
            self.logger.error(f"Error during bot response generation for bot '{selected_bot_name}' in chatroom '{chatroom_name}': {e}", exc_info=True)
            QMessageBox.critical(self, self.tr("Error"), self.tr("An error occurred while getting bot response: {0}").format(str(e)))
            chatroom.add_message("System", self.tr("Error during bot response: {0}").format(str(e)))
            self._update_message_display()
        finally:
            self.trigger_bot_response_button.setText(original_button_text)
            self._update_message_related_ui_state(bool(self.chatroom_list_widget.currentItem()))


    def _create_chatroom(self):
        """Handles the creation of a new chatroom.

        Prompts the user for a chatroom name. If a valid name is provided
        and does not already exist, a new chatroom is created and the
        list is updated.
        """
        name, ok = QInputDialog.getText(self, self.tr("New Chatroom"), self.tr("Enter chatroom name:"))
        if ok and name:
            if self.chatroom_manager.create_chatroom(name):
                self.logger.info(f"Chatroom '{name}' created successfully.") # INFO - user action success
                self._update_chatroom_list()
                # Optionally select the new chatroom
                items = self.chatroom_list_widget.findItems(name, Qt.MatchFlag.MatchExactly)
                if items:
                    self.chatroom_list_widget.setCurrentItem(items[0])
            else:
                self.logger.warning(f"Failed to create chatroom '{name}', it likely already exists.") # WARNING - user action failed, but recoverable
                QMessageBox.warning(self, self.tr("Error"), self.tr("Chatroom '{0}' already exists.").format(name))
        elif name: 
            self.logger.debug(f"Chatroom creation cancelled or name was invalid: '{name}'.") # DEBUG - user cancelled, not an error
        else: 
            self.logger.debug("Chatroom creation cancelled by user.") # DEBUG - user cancelled

    def _rename_chatroom(self):
        """Handles renaming of the selected chatroom.

        Prompts the user for a new name. If a chatroom is selected and a
        valid new name is provided that isn't already in use, the chatroom
        is renamed and the list is updated.
        """
        current_item = self.chatroom_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected to rename."))
            return

        old_name = current_item.text()
        new_name, ok = QInputDialog.getText(self, self.tr("Rename Chatroom"), self.tr("Enter new name:"), text=old_name)

        if ok and new_name and new_name != old_name:
            if self.chatroom_manager.rename_chatroom(old_name, new_name):
                self.logger.info(f"Chatroom '{old_name}' renamed to '{new_name}' successfully.")
                self._update_chatroom_list()
                # Re-select the renamed chatroom
                items = self.chatroom_list_widget.findItems(new_name, Qt.MatchFlag.MatchExactly)
                if items:
                    self.chatroom_list_widget.setCurrentItem(items[0])
            else:
                self.logger.warning(f"Failed to rename chatroom '{old_name}' to '{new_name}'. New name might already exist.") # WARNING - user action failed
                QMessageBox.warning(self, self.tr("Error"), self.tr("Could not rename chatroom. New name '{0}' might already exist.").format(new_name))
        elif ok and not new_name: 
            self.logger.warning(f"Attempt to rename chatroom '{old_name}' with an empty name.") # WARNING - invalid input
            QMessageBox.warning(self, self.tr("Warning"), self.tr("New chatroom name cannot be empty."))
        elif not ok: 
             self.logger.debug(f"Chatroom rename for '{old_name}' cancelled by user.") # DEBUG - user cancelled


    def _delete_chatroom(self):
        """Handles deletion of the selected chatroom.

        Prompts the user for confirmation. If confirmed, the chatroom is
        deleted from the manager and its file is removed from disk. The
        UI is then updated.
        """
        current_item = self.chatroom_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected to delete."))
            return

        name = current_item.text()
        reply = QMessageBox.question(self, self.tr("Confirm Delete"), 
                                     self.tr("Are you sure you want to delete chatroom '{0}'?").format(name),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.logger.info(f"Deleting chatroom '{name}'.")
            self.chatroom_manager.delete_chatroom(name)
            self._update_chatroom_list()
            # Bot list will be cleared by _on_selected_chatroom_changed if no item is selected
            # or updated if a new item gets selected.
            # Explicitly clear if list becomes empty:
            if self.chatroom_list_widget.count() == 0:
                 self._update_bot_list(None)
                 self._update_bot_panel_state(False)
        else:
            self.logger.debug(f"Deletion of chatroom '{name}' cancelled by user.") # DEBUG - user cancelled


    def _update_bot_list(self, chatroom_name: str | None):
        """Updates the list of bots displayed for the selected chatroom.

        Clears the existing bot list and repopulates it with bots from the
        specified chatroom. Also updates the bot panel's state.

        Args:
            chatroom_name: The name of the chatroom whose bots are to be listed,
                           or None to clear the list.
        """
        self.bot_list_widget.clear()
        if chatroom_name:
            chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
            if chatroom:
                for bot in chatroom.list_bots():
                    self.bot_list_widget.addItem(QListWidgetItem(bot.get_name()))
        # Update panel state based on whether a chatroom is active
        self._update_bot_panel_state(chatroom_name is not None and self.chatroom_manager.get_chatroom(chatroom_name) is not None, chatroom_name)


    def _add_bot_to_chatroom(self):
        """Handles adding a new bot to the selected chatroom using the AddBotDialog.

        Opens the AddBotDialog to gather the bot's name, AI engine, model name (optional),
        and system prompt. If the dialog is accepted and inputs are valid (e.g., non-empty
        bot name, bot name doesn't already exist), it proceeds to create the bot.
        The method then calls the `create_bot` factory function and adds the
        resulting bot to the chatroom.
        Updates the UI (bot list and response selector) accordingly.
        Warns if an API key is missing for the chosen engine but still allows creation.
        """
        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected to add a bot to."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom: # Should not happen if item is selected
            QMessageBox.critical(self, self.tr("Error"), self.tr("Selected chatroom not found."))
            return
        
        existing_bot_names_in_chatroom = [bot.get_name() for bot in chatroom.list_bots()]
        dialog = AddBotDialog(existing_bot_names=existing_bot_names_in_chatroom, parent=self)

        if dialog.exec(): # This now uses the overridden accept method for validation
            data = dialog.get_data()
            if not data: # Safeguard, should not happen if accept validation passed
                return

            # Bot name validation (emptiness, duplication) is now handled within AddBotDialog.accept()
            bot_name = data["bot_name"] # Already stripped in dialog's get_data or accept
            engine_type = data["engine_type"]
            model_name = data["model_name"] # Already stripped
            system_prompt = data["system_prompt"]
            # Validation for bot_name (empty, duplicate) is now done in AddBotDialog.accept()
            
            # Check if the selected engine type requires an API key by looking at the class constructor
            # This check is illustrative; a more robust check might involve inspecting constructor parameters
            # or having a metadata attribute in engine classes.
            engine_class = ai_engines.ENGINE_TYPE_TO_CLASS_MAP.get(engine_type)

            api_key = self.api_key_manager.load_key(engine_type)

            engine_config = {"engine_type": engine_type, "api_key": api_key if api_key else None}
            if model_name:
                engine_config["model_name"] = model_name

            try:
                new_bot = create_bot(bot_name=bot_name, system_prompt=system_prompt, engine_config=engine_config)
            except ValueError as e:
                self.logger.error(f"Error creating bot '{bot_name}' with engine '{engine_type}': {e}", exc_info=True)
                QMessageBox.critical(self, self.tr("Error Creating Bot"), self.tr("Could not create bot: {0}").format(str(e)))
                return

            if chatroom.add_bot(new_bot):
                self.logger.info(f"Bot '{bot_name}' (engine: {engine_type}, model: {model_name if model_name else 'default'}) added to chatroom '{chatroom_name}' successfully.")
                self._update_bot_list(chatroom_name)
                self._update_bot_response_selector()
            else:
                self.logger.error(f"Failed to add bot '{bot_name}' to chatroom '{chatroom_name}' for an unknown reason after initial checks.")
                QMessageBox.critical(self, self.tr("Error"), self.tr("Could not add bot. An unexpected error occurred."))
        else:
            self.logger.debug(f"Add bot to chatroom '{chatroom_name}' cancelled by user in dialog.")


    def _show_api_key_dialog(self):
        """Displays the API Key Management dialog."""
        self.logger.debug("Showing API Key Management dialog.") # DEBUG - UI interaction
        dialog = ApiKeyDialog(self.api_key_manager, self)
        dialog.exec()

    def _remove_bot_from_chatroom(self):
        """Handles removing the selected bot from the current chatroom.

        Prompts the user for confirmation. If confirmed, the bot is removed
        from the chatroom and the UI is updated.
        """
        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected."))
            return
        
        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            self.logger.error(f"Remove bot: Selected chatroom '{chatroom_name}' not found.") # ERROR - prerequisite failed
            QMessageBox.critical(self, self.tr("Error"), self.tr("Selected chatroom not found."))
            return

        current_bot_item = self.bot_list_widget.currentItem()
        if not current_bot_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No bot selected to remove."))
            return

        bot_name = current_bot_item.text()
        reply = QMessageBox.question(self, self.tr("Confirm Delete Bot"), 
                                     self.tr("Are you sure you want to remove bot '{0}' from chatroom '{1}'?").format(bot_name, chatroom_name),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.logger.info(f"Removing bot '{bot_name}' from chatroom '{chatroom_name}'.") # INFO - user action
            chatroom.remove_bot(bot_name)
            self._update_bot_list(chatroom_name)
            self._update_bot_response_selector() 
        else:
            self.logger.debug(f"Removal of bot '{bot_name}' from chatroom '{chatroom_name}' cancelled by user.") # DEBUG - user cancelled


def main():
    """Main entry point for the application.

    Initializes logging, sets up the QApplication, handles internationalization
    by loading translation files, creates and shows the MainWindow, and starts
    the application event loop.
    """
    logging.basicConfig(
        level=logging.DEBUG, # Changed to DEBUG
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        filename='app.log',
        filemode='w', # Overwrite log file each time for now, can be changed to 'a' for append
        encoding='utf-8'  # Ensure UTF-8 encoding for log file
    )
    logging.info("Application starting")
    app = QApplication(sys.argv)

    translator = QTranslator()
    # Try to load system locale, fallback to zh_TW for testing, then to nothing
    locale_name = QLocale.system().name() # e.g., "en_US", "zh_TW"
    
    # Construct path to i18n directory relative to this script
    # This assumes i18n is a sibling to the directory containing this script (e.g. src/main/i18n)
    # More robust path handling might be needed depending on project structure
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Corrected path: Assume main_window.py is in src/main/, and i18n is in project_root/i18n/
    project_root = os.path.dirname(os.path.dirname(current_dir)) # up to src, then up to project_root
    i18n_dir = os.path.join(project_root, "i18n")

    translation_loaded = False
    # Try specific locale first
    if translator.load(locale_name, "app", "_", i18n_dir): # e.g. app_zh_TW.qm or app_en_US.qm
        QApplication.installTranslator(translator)
        translation_loaded = True
    # Fallback to zh_TW if system locale not found or different
    elif locale_name != "zh_TW" and translator.load("app_zh_TW", i18n_dir): # Avoid double loading if system is zh_TW
        QApplication.installTranslator(translator)
        translation_loaded = True
    
    # Fallback for Qt's own standard dialog translations (e.g. "Cancel", "OK")
    qt_translator = QTranslator()
    # Try to find Qt's base translations, often in a path like /usr/share/qt6/translations/
    # QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath) is the most reliable way
    qt_translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(QLocale.system(), "qtbase", "_", qt_translations_path):
        QApplication.installTranslator(qt_translator)
    elif qt_translator.load("qtbase_" + locale_name.split('_')[0], qt_translations_path): # Try just language e.g. qtbase_en
        QApplication.installTranslator(qt_translator)


    main_window = MainWindow()
    main_window.show()
    logging.info("Application started successfully.") 
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
