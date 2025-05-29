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
    QMenu, QStyle, QSizePolicy # Added QMenu for context menu, QStyle, QSizePolicy
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QTranslator, QLocale, QLibraryInfo, QPoint, QSize # Added QSize
import os # For path construction
import logging # For logging

# Attempt to import from sibling modules
from .chatroom import Chatroom, ChatroomManager
from .ai_bots import Bot, AIEngine, create_bot # AIEngine and Bot remain in ai_bots, added create_bot
from .ai_engines import GeminiEngine, GrokEngine # Engines from new package
from .api_key_manager import ApiKeyManager
from .message import Message
from . import ai_engines


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
        self.chatroom_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection) # Added
        self.chatroom_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu) # Added
        self.chatroom_list_widget.customContextMenuRequested.connect(self._show_chatroom_context_menu) # Added
        left_panel_layout.addWidget(self.chatroom_list_widget)
        
        chatroom_buttons_layout = QHBoxLayout()
        self.new_chatroom_button = QPushButton(self.tr("New Chatroom")) # Store as member for state updates
        self.new_chatroom_button.clicked.connect(self._create_chatroom)
        # self.rename_chatroom_button = QPushButton(self.tr("Rename Chatroom")) # REMOVED
        # self.rename_chatroom_button.clicked.connect(self._rename_chatroom) # REMOVED
        # self.clone_chatroom_button = QPushButton(self.tr("Clone Chatroom")) # REMOVED
        # self.clone_chatroom_button.clicked.connect(self._clone_selected_chatroom) # REMOVED
        # self.delete_chatroom_button = QPushButton(self.tr("Delete Chatroom")) # REMOVED
        # self.delete_chatroom_button.clicked.connect(self._delete_chatroom) # REMOVED
        
        chatroom_buttons_layout.addWidget(self.new_chatroom_button)
        # chatroom_buttons_layout.addWidget(self.rename_chatroom_button) # REMOVED
        # chatroom_buttons_layout.addWidget(self.clone_chatroom_button) # REMOVED
        # chatroom_buttons_layout.addWidget(self.delete_chatroom_button) # REMOVED
        left_panel_layout.addLayout(chatroom_buttons_layout)

        # Bot management UI elements have been moved to the new right panel.
        # The old layout code in left_panel_layout for bots has been removed.
        
        main_splitter.addWidget(left_panel_widget)


        # --- Middle Panel (Message Display and Input) ---
        right_panel_widget = QWidget() # This is now the middle panel
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

        # --- New Right Panel (Bot List and Controls) ---
        bot_list_container_widget = QWidget()
        right_bot_panel_layout = QVBoxLayout(bot_list_container_widget)

        self.bot_panel_label = QLabel(self.tr("Bots")) # New generic label
        right_bot_panel_layout.addWidget(self.bot_panel_label)

        self.bot_list_widget = QListWidget()
        self.bot_list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.bot_list_widget.customContextMenuRequested.connect(self._show_bot_context_menu)
        self.bot_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        right_bot_panel_layout.addWidget(self.bot_list_widget, 1) # Add stretch factor

        self.add_bot_button = QPushButton(self.tr("Add Bot"))
        self.add_bot_button.clicked.connect(self._add_bot_to_chatroom)
        right_bot_panel_layout.addWidget(self.add_bot_button)
        
        main_splitter.addWidget(bot_list_container_widget)
        main_splitter.setSizes([250, 300, 250]) # Adjusted for three panels

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

    def _show_chatroom_context_menu(self, position: QPoint):
        """Displays a context menu for chatroom items.

        Args:
            position: The position where the context menu was requested.
        """
        selected_items = self.chatroom_list_widget.selectedItems()
        if not selected_items:
            return

        menu = QMenu(self)
        num_selected = len(selected_items)

        if num_selected == 1:
            # Ensure currentItem is one of the selected_items, or set it.
            # This is important because _rename_chatroom, _clone_selected_chatroom, _delete_chatroom
            # currently rely on currentItem().
            # item_at_pos = self.chatroom_list_widget.itemAt(position) # The item actually clicked
            # if item_at_pos and item_at_pos in selected_items:
            #    self.chatroom_list_widget.setCurrentItem(item_at_pos)
            # elif selected_items: # Fallback if specific clicked item not easily determined or not in selection
            #    self.chatroom_list_widget.setCurrentItem(selected_items[0])


            rename_action = QAction(self.tr("Rename"), self)
            rename_action.triggered.connect(self._rename_chatroom) # Relies on currentItem
            menu.addAction(rename_action)

            clone_action = QAction(self.tr("Clone"), self)
            clone_action.triggered.connect(self._clone_selected_chatroom) # Relies on currentItem
            menu.addAction(clone_action)
            
            menu.addSeparator()

            delete_action = QAction(self.tr("Delete"), self)
            delete_action.triggered.connect(self._delete_chatroom) # Relies on currentItem
            menu.addAction(delete_action)

        elif num_selected > 1:
            # These actions will currently operate on self.chatroom_list_widget.currentItem()
            # which might not be intuitive if multiple items are selected.
            # The target methods _clone_selected_chatroom and _delete_chatroom
            # will need to be updated to iterate over all selectedItems().
            
            clone_selected_action = QAction(self.tr("Clone Selected Chatrooms ({0})").format(num_selected), self)
            clone_selected_action.triggered.connect(self._clone_selected_chatroom) # Needs update for multi-select
            menu.addAction(clone_selected_action)

            menu.addSeparator()

            delete_selected_action = QAction(self.tr("Delete Selected Chatrooms ({0})").format(num_selected), self)
            delete_selected_action.triggered.connect(self._delete_chatroom) # Needs update for multi-select
            menu.addAction(delete_selected_action)

        menu.exec(self.chatroom_list_widget.mapToGlobal(position))


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
        # self.remove_bot_button.setEnabled(enabled and bool(self.bot_list_widget.currentItem())) # REMOVED
        
        if enabled and chatroom_name:
            # self.bot_panel_label.setText(self.tr("Bots in '{0}'").format(chatroom_name))
            self.bot_panel_label.setText(self.tr("Bots")) # Keep it generic for now
        elif not enabled and self.chatroom_list_widget.currentItem() is None : # No chatroom selected
             self.bot_panel_label.setText(self.tr("Bots")) # Keep it generic
        else: # Chatroom selected, but panel might be disabled for other reasons
            self.bot_panel_label.setText(self.tr("Bots")) # Keep it generic

    def _update_chatroom_related_button_states(self):
        """Updates the enabled state of chatroom action buttons.

        Buttons like "Rename Chatroom", "Clone Chatroom", and "Delete Chatroom"
        are enabled only if a chatroom is currently selected in the list.
        """
        has_selection = bool(self.chatroom_list_widget.currentItem())
        # self.rename_chatroom_button.setEnabled(has_selection) # REMOVED
        # self.clone_chatroom_button.setEnabled(has_selection) # REMOVED
        # self.delete_chatroom_button.setEnabled(has_selection) # REMOVED


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
        """Clones the currently selected chatroom(s).

        If multiple chatrooms are selected, attempts to clone each one.
        Updates the chatroom list and shows a summary message.
        """
        selected_items = self.chatroom_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom(s) selected to clone."))
            return

        cloned_count = 0
        attempted_count = len(selected_items)
        last_cloned_name = None
        # Store original names for the final message if only one was selected
        original_single_selected_name = selected_items[0].text() if attempted_count == 1 else None


        for item in selected_items:
            original_chatroom_name = item.text()
            self.logger.info(f"Attempting to clone chatroom: {original_chatroom_name}")
            cloned_chatroom = self.chatroom_manager.clone_chatroom(original_chatroom_name)
            if cloned_chatroom:
                self.logger.info(f"Chatroom '{original_chatroom_name}' cloned successfully as '{cloned_chatroom.name}'.")
                cloned_count += 1
                last_cloned_name = cloned_chatroom.name # Keep track of the last one for single selection focus
            else:
                self.logger.error(f"Failed to clone chatroom '{original_chatroom_name}'.")
                # Individual error message for each failure might be too noisy for multiple selections.
                # Rely on the summary and logs.

        self._update_chatroom_list()

        if attempted_count == 1: # Single selection
            if cloned_count == 1 and last_cloned_name and original_single_selected_name:
                 # Try to select the newly cloned chatroom if it was a single clone
                for i in range(self.chatroom_list_widget.count()):
                    if self.chatroom_list_widget.item(i).text() == last_cloned_name:
                        self.chatroom_list_widget.setCurrentRow(i)
                        break
                QMessageBox.information(self, self.tr("Success"),
                                        self.tr("Chatroom '{0}' cloned as '{1}'.").format(original_single_selected_name, last_cloned_name))
            elif original_single_selected_name: # Ensure it's not None
                QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to clone chatroom '{0}'.").format(original_single_selected_name))
        else: # Multiple selections
            if cloned_count == attempted_count:
                QMessageBox.information(self, self.tr("Success"),
                                        self.tr("Successfully cloned {0} chatroom(s).").format(cloned_count))
            elif cloned_count > 0:
                QMessageBox.warning(self, self.tr("Partial Success"),
                                    self.tr("Successfully cloned {0} out of {1} selected chatrooms. See log for details.").format(cloned_count, attempted_count))
            else:
                QMessageBox.critical(self, self.tr("Error"),
                                     self.tr("Failed to clone any of the selected {0} chatrooms. See log for details.").format(attempted_count))


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


    def _trigger_bot_response(self, bot_name_override: str | None = None):
        """Triggers a response from a specified bot in the current chatroom.

        This method orchestrates fetching a bot's response. It identifies the
        target bot either through an override name or the UI's selection.
        It then gathers conversation history, checks for API key requirements,
        and invokes the bot's response generation. User feedback is provided
        throughout the process, especially for errors or when the bot is processing.

        Args:
            bot_name_override: If provided, this bot name is used directly,
                bypassing the UI selection. Defaults to None.
        
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

        selected_bot_name_to_use = bot_name_override
        if not selected_bot_name_to_use:  # Fallback to combo box if no override
            if self.bot_response_selector.count() == 0: # Should be redundant due to above check but good for safety
                self.logger.warning(f"Trigger bot response: No bots in chatroom '{chatroom_name}' (selector empty).")
                QMessageBox.warning(self, self.tr("Warning"), self.tr("Selected chatroom has no bots to respond."))
                return
            selected_bot_name_to_use = self.bot_response_selector.currentText()
            if not selected_bot_name_to_use:
                self.logger.warning("Trigger bot response: No bot selected in dropdown.")
                QMessageBox.warning(self, self.tr("Warning"), self.tr("No bot selected to respond."))
                return
        
        bot = chatroom.get_bot(selected_bot_name_to_use)
        if not bot:
            self.logger.error(f"Trigger bot response: Bot '{selected_bot_name_to_use}' not found in chatroom '{chatroom_name}'.")
            QMessageBox.critical(self, self.tr("Error"), self.tr("Bot '{0}' not found in chatroom.").format(selected_bot_name_to_use))
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
        
        self.logger.info(f"Attempting to trigger bot response for bot '{selected_bot_name_to_use}' in chatroom '{chatroom_name}'.")
        conversation_history = chatroom.get_messages()

        if not conversation_history:
            self.logger.info(f"Trigger bot response: No messages in chatroom '{chatroom_name}' to respond to for bot '{selected_bot_name_to_use}'.")
            QMessageBox.information(self, self.tr("Info"), self.tr("No messages in chat to respond to."))
            return

        # UI updates to indicate processing, only for the main button
        original_button_text = None
        is_main_button_trigger = not bot_name_override # True if triggered by the main UI button
        if is_main_button_trigger:
            original_button_text = self.trigger_bot_response_button.text()
            self.trigger_bot_response_button.setText(self.tr("Waiting for AI..."))
            self.trigger_bot_response_button.setEnabled(False)
            QApplication.processEvents()

        try:
            ai_response = bot.generate_response(conversation_history=conversation_history)
            self.logger.info(f"Bot '{selected_bot_name_to_use}' generated response successfully in chatroom '{chatroom_name}'.")
            chatroom.add_message(bot.get_name(), ai_response)
            self._update_message_display()
        except ValueError as ve: # Specific handling for ValueErrors from create_bot or engine
            self.logger.error(f"Configuration or input error for bot '{selected_bot_name_to_use}': {ve}", exc_info=True)
            QMessageBox.critical(self, self.tr("Bot Configuration Error"), str(ve))
            # Optionally add system message to chatroom for this type of error too
            # chatroom.add_message("System", self.tr("Error with bot '{0}': {1}").format(selected_bot_name_to_use, str(ve)))
            # self._update_message_display()
        except Exception as e:
            self.logger.error(f"Error during bot response generation for bot '{selected_bot_name_to_use}' in chatroom '{chatroom_name}': {e}", exc_info=True)
            QMessageBox.critical(self, self.tr("Error"), self.tr("An error occurred while getting bot response for '{0}': {1}").format(selected_bot_name_to_use, str(e)))
            chatroom.add_message("System", self.tr("Error during bot response for '{0}': {1}").format(selected_bot_name_to_use, str(e)))
            self._update_message_display()
        finally:
            if is_main_button_trigger and original_button_text is not None:
                self.trigger_bot_response_button.setText(original_button_text)
            # The message related UI state should be updated regardless of which button triggered
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

        Prompts the user for confirmation. If confirmed, the chatroom(s) are
        deleted from the manager and their file(s) are removed from disk. The
        UI is then updated.
        """
        selected_items = self.chatroom_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom(s) selected to delete."))
            return

        num_selected = len(selected_items)
        names_to_delete = [item.text() for item in selected_items]

        # For single deletion, keep the old simple message
        if num_selected == 1:
            confirm_message = self.tr("Are you sure you want to delete chatroom '{0}'?").format(names_to_delete[0])
        else: # For multiple deletions, list the names
            confirm_message = self.tr("Are you sure you want to delete the following {0} chatroom(s)?\n\n- {1}").format(
                num_selected, "\n- ".join(names_to_delete)
            )
        
        reply = QMessageBox.question(self, self.tr("Confirm Deletion"), confirm_message,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            for name in names_to_delete:
                self.logger.info(f"Deleting chatroom '{name}'.")
                if self.chatroom_manager.delete_chatroom(name): # delete_chatroom returns True on success, False on failure
                    deleted_count += 1
                else:
                    # This case (delete_chatroom returns False) implies the chatroom wasn't found or couldn't be deleted.
                    self.logger.warning(f"Failed to delete chatroom '{name}' during batch operation (it might have already been deleted or an error occurred).")
            
            self._update_chatroom_list()
            # _update_chatroom_list will handle UI updates including bot list and panel if necessary.
            # For instance, if the current selection is removed, _on_selected_chatroom_changed will eventually
            # be triggered with a None current item, or a new current item.
            # If the list becomes empty, _update_chatroom_list handles this by calling:
            # self._update_bot_list(None)
            # self._update_bot_panel_state(False)
            # self._update_message_related_ui_state(False)

            if num_selected == 1: # Message for single deletion
                if deleted_count == 1:
                    # Implicitly successful as no specific message for single success needed other than list update
                    # QMessageBox.information(self, self.tr("Success"), self.tr("Chatroom '{0}' deleted.").format(names_to_delete[0])) # Optional: could be too noisy
                    pass
                else: # Should not happen if delete_chatroom was successful, but as a fallback
                    QMessageBox.warning(self, self.tr("Deletion Failed"), self.tr("Could not delete chatroom '{0}'. It may have already been removed.").format(names_to_delete[0]))

            else: # Messages for multiple deletions
                if deleted_count == num_selected:
                     QMessageBox.information(self, self.tr("Success"),
                                            self.tr("Successfully deleted {0} chatroom(s).").format(deleted_count))
                elif deleted_count > 0:
                    QMessageBox.warning(self, self.tr("Partial Deletion"),
                                         self.tr("Successfully deleted {0} out of {1} selected chatrooms. Some may have already been deleted or an error occurred.").format(deleted_count, num_selected))
                else: # deleted_count == 0
                     QMessageBox.critical(self, self.tr("Deletion Failed"),
                                         self.tr("Failed to delete any of the selected {0} chatrooms. They may have already been deleted or an error occurred.").format(num_selected))
        else:
            self.logger.debug(f"Deletion of {num_selected} chatroom(s) cancelled by user.")


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
                    # self.bot_list_widget.addItem(QListWidgetItem(bot.get_name())) # Old way
                    bot_name_str = bot.get_name() # Ensure it's a string
                    item_widget = self._create_bot_list_item_widget(bot_name_str)
                    
                    list_item = QListWidgetItem(self.bot_list_widget)
                    list_item.setData(Qt.ItemDataRole.UserRole, bot_name_str) # Store bot name
                    
                    # Set size hint for the list item to ensure custom widget is displayed correctly
                    list_item.setSizeHint(item_widget.sizeHint()) 
                    
                    self.bot_list_widget.addItem(list_item)
                    self.bot_list_widget.setItemWidget(list_item, item_widget)

        # Update panel state based on whether a chatroom is active
        self._update_bot_panel_state(chatroom_name is not None and self.chatroom_manager.get_chatroom(chatroom_name) is not None, chatroom_name)

    def _show_bot_context_menu(self, position: QPoint):
        """Displays a context menu for bot items in the `bot_list_widget`.

        The menu options vary depending on whether one or multiple bots are selected.
        Actions include "Edit", "Clone", and "Delete".

        Args:
            position: The position (in widget coordinates) where the context menu
                      was requested, used to display the menu correctly.
        """
        selected_items = self.bot_list_widget.selectedItems()
        if not selected_items:
            return

        menu = QMenu(self)
        num_selected = len(selected_items)

        if num_selected == 1:
            edit_action = QAction(self.tr("Edit"), self)
            edit_action.triggered.connect(self._edit_selected_bot)
            menu.addAction(edit_action)

            clone_action = QAction(self.tr("Clone"), self)
            clone_action.triggered.connect(self._clone_selected_bots)
            menu.addAction(clone_action)

            delete_action = QAction(self.tr("Delete"), self)
            delete_action.triggered.connect(self._delete_selected_bots)
            menu.addAction(delete_action)
        elif num_selected > 1:
            clone_action = QAction(self.tr("Clone Selected Bots"), self) # Pluralized
            clone_action.triggered.connect(self._clone_selected_bots)
            menu.addAction(clone_action)

            delete_action = QAction(self.tr("Delete Selected Bots"), self) # Pluralized
            delete_action.triggered.connect(self._delete_selected_bots)
            menu.addAction(delete_action)

        menu.exec(self.bot_list_widget.mapToGlobal(position))

    def _edit_selected_bot(self):
        """Handles editing the configuration of the selected bot.

        This method is triggered by the "Edit" action in the bot context menu.
        It retrieves the selected bot, populates an `AddBotDialog` with its
        current settings, and if the dialog is accepted, updates the bot's
        properties including name, system prompt, and AI engine configuration.
        Handles potential errors during engine recreation and ensures UI updates.
        """
        selected_items = self.bot_list_widget.selectedItems()
        if not selected_items or len(selected_items) != 1:
            self.logger.warning("Edit bot called without a single selection.")
            return
        
        list_item = selected_items[0]
        bot_name_to_edit = list_item.data(Qt.ItemDataRole.UserRole)
        if not bot_name_to_edit:
            self.logger.error("Selected bot item has no name data.")
            return

        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            self.logger.error("No chatroom selected to edit a bot from.")
            return
        
        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            self.logger.error(f"Chatroom '{chatroom_name}' not found.")
            return

        bot_to_edit = chatroom.get_bot(bot_name_to_edit)
        if not bot_to_edit:
            self.logger.error(f"Bot '{bot_name_to_edit}' not found in chatroom '{chatroom_name}' for editing.")
            return

        # Prepare AddBotDialog
        current_name = bot_to_edit.get_name()
        current_engine_instance = bot_to_edit.get_engine()
        current_engine_type = type(current_engine_instance).__name__
        current_model_name = getattr(current_engine_instance, 'model_name', None) # Handle if no model_name
        current_system_prompt = bot_to_edit.get_system_prompt()

        all_bot_names_in_chatroom = [bot.get_name() for bot in chatroom.list_bots()]
        existing_bot_names_for_dialog = [name for name in all_bot_names_in_chatroom if name != current_name]

        dialog = AddBotDialog(existing_bot_names=existing_bot_names_for_dialog, parent=self)
        dialog.setWindowTitle(self.tr("Edit Bot: {0}").format(current_name))

        # Pre-fill dialog fields
        dialog.bot_name_input.setText(current_name)
        dialog.engine_combo.setCurrentText(current_engine_type)
        if current_model_name:
            dialog.model_name_input.setText(current_model_name)
        dialog.system_prompt_input.setPlainText(current_system_prompt)

        if dialog.exec():
            data = dialog.get_data()
            if not data: # Should not happen if dialog accept() worked
                return

            new_name = data["bot_name"]
            new_engine_type = data["engine_type"]
            new_model_name = data["model_name"]
            new_system_prompt = data["system_prompt"]

            name_changed = (new_name != current_name)
            engine_changed = (new_engine_type != current_engine_type or \
                              new_model_name != (current_model_name if current_model_name else "")) 
                              # Ensure empty new_model_name matches None current_model_name

            # If name changes, we need to remove the bot and re-add it later
            # This handles case sensitivity issues and ensures Chatroom's internal dict is updated.
            if name_changed:
                if not chatroom.remove_bot(current_name): # Use current_name for removal
                    self.logger.error(f"Failed to remove bot '{current_name}' before renaming.")
                    # Consider if we should abort here or try to proceed
                    return 
                bot_to_edit.set_name(new_name)

            bot_to_edit.set_system_prompt(new_system_prompt)

            if engine_changed:
                self.logger.debug(f"Engine change detected for bot '{new_name}'. Old: {current_engine_type}, New: {new_engine_type}")
                api_key = self.api_key_manager.load_key(new_engine_type)
                
                try:
                    engine_class = ai_engines.ENGINE_TYPE_TO_CLASS_MAP.get(new_engine_type)
                    if not engine_class:
                        raise ValueError(f"Unsupported engine type: {new_engine_type}")
                    
                    new_engine_instance = engine_class(api_key=api_key, model_name=new_model_name if new_model_name else None)
                    bot_to_edit.set_engine(new_engine_instance)
                    self.logger.info(f"Bot '{new_name}' engine updated to {new_engine_type} with model '{new_model_name}'.")

                except ValueError as e:
                    self.logger.error(f"Error updating bot engine for '{new_name}': {e}", exc_info=True)
                    QMessageBox.critical(self, self.tr("Error Updating Bot"), self.tr("Could not update bot engine: {0}").format(str(e)))
                    # Rollback name change if it happened and bot was removed
                    if name_changed:
                        bot_to_edit.set_name(current_name) # Revert name
                        chatroom.add_bot(bot_to_edit) # Re-add with old name and old engine
                    return # Stop further processing
            
            if name_changed:
                # Re-add the bot if its name changed. This ensures it's correctly indexed in the chatroom.
                if not chatroom.add_bot(bot_to_edit):
                     self.logger.error(f"Failed to re-add bot '{new_name}' after name change.")
                     # Attempt to add back with old name as a fallback, though this state is problematic
                     bot_to_edit.set_name(current_name)
                     chatroom.add_bot(bot_to_edit) 
                     QMessageBox.critical(self, self.tr("Error Updating Bot"), self.tr("Could not re-add bot with new name. Bot may be in an inconsistent state."))
                     return


            self.logger.info(f"Bot '{current_name if name_changed else new_name}' updated successfully. New name: '{new_name}'")
            
            # Explicitly notify chatroom manager about the update for saving
            self.chatroom_manager._notify_chatroom_updated(chatroom)

            self._update_bot_list(chatroom_name)
            self._update_bot_response_selector()
        else:
            self.logger.debug(f"Edit bot '{bot_name_to_edit}' cancelled.")


    def _clone_selected_bots(self):
        """Clones the selected bot(s) in the current chatroom.

        This method is triggered by the "Clone" or "Clone Selected Bots" action
        in the bot context menu. It iterates through all selected bots, creating
        a copy of each with a unique name (e.g., "Bot Name (Copy)", 
        "Bot Name (Copy) 1"). The cloned bots inherit the system prompt and
        engine configuration of their originals. User is notified of success or failure.
        """
        selected_items = self.bot_list_widget.selectedItems()
        if not selected_items:
            self.logger.warning("Clone bot(s) called without any selection.")
            return

        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item: # This should ideally not happen if items are selected from the list tied to a chatroom
            self.logger.error("No chatroom selected to clone bots into.")
            QMessageBox.critical(self, self.tr("Error"), self.tr("No chatroom context for cloning."))
            return
        
        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            self.logger.error(f"Chatroom '{chatroom_name}' not found for cloning bots.")
            QMessageBox.critical(self, self.tr("Error"), self.tr("Could not find the current chatroom."))
            return

        cloned_count = 0
        existing_bot_names_in_chatroom = [bot.get_name() for bot in chatroom.list_bots()]

        for list_item in selected_items:
            original_bot_name = list_item.data(Qt.ItemDataRole.UserRole)
            if not original_bot_name:
                self.logger.warning("Could not retrieve bot name from list item, skipping clone.")
                continue
            
            original_bot = chatroom.get_bot(original_bot_name)
            if not original_bot:
                self.logger.error(f"Bot '{original_bot_name}' not found in chatroom '{chatroom_name}' for cloning.")
                continue

            # Generate Unique Clone Name
            base_clone_name = f"{original_bot.get_name()} (Copy)"
            clone_name = base_clone_name
            copy_number = 1
            # Update the list of existing names within the loop if multiple clones are made from the same original
            # or if multiple bots are selected for cloning in one go.
            current_existing_names = [bot.get_name() for bot in chatroom.list_bots()] 
            while clone_name in current_existing_names:
                clone_name = f"{base_clone_name} {copy_number}"
                copy_number += 1
            
            # Gather Original Bot's Data
            original_system_prompt = original_bot.get_system_prompt()
            original_engine_instance = original_bot.get_engine()
            original_engine_type = type(original_engine_instance).__name__
            original_model_name = getattr(original_engine_instance, 'model_name', None)
            api_key = self.api_key_manager.load_key(original_engine_type) # API key might be None

            engine_config = {
                "engine_type": original_engine_type,
                "api_key": api_key, # Pass along, could be None
                "model_name": original_model_name
            }

            try:
                cloned_bot = create_bot(bot_name=clone_name, system_prompt=original_system_prompt, engine_config=engine_config)
            except ValueError as e:
                self.logger.error(f"Error creating cloned bot '{clone_name}': {e}", exc_info=True)
                QMessageBox.warning(self, self.tr("Clone Error"), self.tr("Could not create clone for bot '{0}': {1}").format(original_bot_name, str(e)))
                continue

            if chatroom.add_bot(cloned_bot):
                self.logger.info(f"Bot '{original_bot_name}' cloned as '{clone_name}' in chatroom '{chatroom_name}'.")
                cloned_count += 1
                # Add the new clone's name to the list for subsequent unique name checks in this loop
                # This is implicitly handled by `current_existing_names = [bot.get_name() for bot in chatroom.list_bots()]`
                # at the start of the loop, but if `add_bot` doesn't immediately update the source for `list_bots()`,
                # this might be needed: current_existing_names.append(clone_name) 
            else:
                self.logger.error(f"Failed to add cloned bot '{clone_name}' to chatroom '{chatroom_name}'. This might be due to a duplicate name if check failed.")
                QMessageBox.warning(self, self.tr("Clone Error"), self.tr("Could not add cloned bot '{0}' to chatroom. It might already exist.").format(clone_name))

        if cloned_count > 0:
            self._update_bot_list(chatroom_name)
            self._update_bot_response_selector()
            # chatroom.add_bot should call _notify_chatroom_updated, so an explicit call here might be redundant
            # but ensures saving if multiple bots are added in a loop and add_bot is not immediately saving.
            self.chatroom_manager._notify_chatroom_updated(chatroom) 

        if cloned_count == len(selected_items):
            QMessageBox.information(self, self.tr("Clone Successful"), self.tr("{0} bot(s) cloned successfully.").format(cloned_count))
        elif cloned_count > 0:
            QMessageBox.warning(self, self.tr("Clone Partially Successful"), self.tr("Successfully cloned {0} out of {1} selected bots.").format(cloned_count, len(selected_items)))
        # If cloned_count is 0 and selected_items was not empty, individual errors were already shown.

    def _delete_selected_bots(self):
        """Deletes the selected bot(s) from the current chatroom.

        Triggered by the "Delete" or "Delete Selected Bots" action in the bot
        context menu. It prompts the user for confirmation before removing
        the bots. Updates the UI and notifies the user of the outcome.
        """
        selected_items = self.bot_list_widget.selectedItems()
        if not selected_items:
            self.logger.warning("Delete bot(s) called without any selection.")
            return

        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            self.logger.error("No chatroom selected to delete bots from.")
            QMessageBox.critical(self, self.tr("Error"), self.tr("No chatroom context for deletion."))
            return
        
        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            self.logger.error(f"Chatroom '{chatroom_name}' not found for deleting bots.")
            QMessageBox.critical(self, self.tr("Error"), self.tr("Could not find the current chatroom."))
            return

        num_selected = len(selected_items)
        bot_names_to_delete = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        bot_names_to_delete = [name for name in bot_names_to_delete if name] # Filter out None values

        if not bot_names_to_delete:
            self.logger.error("Could not retrieve bot names for deletion from selected items.")
            QMessageBox.warning(self, self.tr("Error"), self.tr("Could not identify bots to delete."))
            return

        confirm_message = self.tr("Are you sure you want to delete the selected {0} bot(s)?\n\n{1}").format(num_selected, "\n".join(bot_names_to_delete))
        reply = QMessageBox.question(self, self.tr("Confirm Deletion"), confirm_message, 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.No:
            self.logger.debug("Bot deletion cancelled by user.")
            return

        deleted_count = 0
        for bot_name in bot_names_to_delete:
            if chatroom.remove_bot(bot_name): # remove_bot should notify the manager for saving
                self.logger.info(f"Bot '{bot_name}' removed from chatroom '{chatroom_name}'.")
                deleted_count += 1
            else:
                self.logger.warning(f"Failed to remove bot '{bot_name}' from chatroom '{chatroom_name}' (it might have already been removed or not found).")
        
        if deleted_count > 0:
            self._update_bot_list(chatroom_name)
            self._update_bot_response_selector()
            # Chatroom.remove_bot is expected to call _notify_chatroom_updated.
            # If it doesn't, an explicit call here would be:
            # self.chatroom_manager._notify_chatroom_updated(chatroom)
            QMessageBox.information(self, self.tr("Deletion Successful"), self.tr("{0} bot(s) deleted successfully.").format(deleted_count))
        elif selected_items: # Attempted deletion but nothing was actually deleted
             QMessageBox.warning(self, self.tr("Deletion Failed"), self.tr("No bots were deleted. They may have already been removed or an error occurred."))


    def _create_bot_list_item_widget(self, bot_name: str) -> QWidget:
        """Creates a custom QWidget for displaying a bot in the `bot_list_widget`.

        Each item includes an avatar placeholder, the bot's name, and a "Play"
        button to trigger a response from that specific bot.

        Args:
            bot_name: The name of the bot for which the item widget is created.

        Returns:
            A QWidget configured to display the bot's information and actions.
        """
        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(5, 5, 5, 5) # Add some padding
        item_layout.setSpacing(5) # Add a small spacing between elements

        # Avatar Placeholder
        avatar_label = QLabel()
        avatar_label.setFixedSize(40, 40)
        avatar_label.setStyleSheet("border: 1px solid gray; background-color: lightgray;")
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter) # Center placeholder text if any
        # You could add text like "Ava" or an icon here if desired
        # avatar_label.setText("Bot") 
        item_layout.addWidget(avatar_label)

        # Bot Name Label
        name_label = QLabel(bot_name)
        name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        item_layout.addWidget(name_label)

        # Response Button
        response_button = QPushButton()
        response_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        response_button.setToolTip(self.tr("Trigger bot response"))
        response_button.setFixedWidth(35) # Adjusted for better icon visibility
        response_button.clicked.connect(lambda checked=False, b_name=bot_name: self._on_bot_response_button_clicked(b_name))
        item_layout.addWidget(response_button)

        item_widget.setLayout(item_layout)
        return item_widget

    def _on_bot_response_button_clicked(self, bot_name: str):
        """Handles the click event of the 'Play' button on a bot list item.

        This method identifies the chatroom context and then calls
        `_trigger_bot_response` with the specific bot's name to generate
        a response.

        Args:
            bot_name: The name of the bot whose response button was clicked.
        """
        self.logger.debug(f"Response button clicked for bot: {bot_name}")
        
        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            # This case should ideally not be reached if the button is part of a visible list
            # that implies an active chatroom.
            self.logger.warning("Bot response button clicked but no chatroom selected.")
            QMessageBox.warning(self, self.tr("Action Failed"), self.tr("No chatroom is currently selected."))
            return
        
        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            self.logger.error(f"_on_bot_response_button_clicked: Chatroom '{chatroom_name}' not found unexpectedly.")
            QMessageBox.critical(self, self.tr("Error"), self.tr("Chatroom context lost for bot response."))
            return

        # Sanity check: ensure the bot still exists in the chatroom
        if not chatroom.get_bot(bot_name):
            self.logger.warning(f"Bot '{bot_name}' (from button) not found in chatroom '{chatroom_name}'. List might be stale.")
            QMessageBox.warning(self, self.tr("Action Failed"), 
                                self.tr("Bot '{0}' seems to have been removed. Please refresh or try again.").format(bot_name))
            self._update_bot_list(chatroom_name) # Refresh the list to reflect current state
            return
            
        self._trigger_bot_response(bot_name_override=bot_name)


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

        # This method is no longer needed as the button is removed.
        # Users will need a new way to remove bots (e.g., context menu on bot_list_widget)
        # For now, the functionality is removed as per instructions.
        pass # Placeholder if the method is called, though it shouldn't be for "remove bot"


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
