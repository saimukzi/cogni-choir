"""
Main window and associated dialogs for the Chat Application.

This module defines the main graphical user interface (GUI) for the chat
application, including the `MainWindow` class which orchestrates the various
UI elements and interactions. It also defines helper dialog classes:
- `ThirdPartyApiKeyDialog`: For managing API keys for different AI services.
- `CreateFakeMessageDialog`: For manually adding messages to a chatroom (for testing/dev).

The application uses PyQt6 for its GUI components. Internationalization (i18n)
is supported using QTranslator. Logging is used for diagnostics.
"""
import sys
import os  # For path construction
import logging  # For logging
import threading
import copy
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QLabel, QInputDialog, QMessageBox,
    QListWidgetItem, QTextEdit,
    QSplitter, QAbstractItemView,
    QMenu, QStyle, QSizePolicy, QSpacerItem  # Added QSpacerItem for potential use
)
from PyQt6.QtGui import QAction, QIcon  # Added QIcon
from PyQt6.QtCore import Qt, QTranslator, QLocale, QLibraryInfo, QPoint, pyqtSignal, QTimer, QSettings  # Added QTimer and QSettings

# Attempt to import from sibling modules
from .chatroom import ChatroomManager
from .bot_template_manager import BotTemplateManager  # Added
# from .ai_bots import Bot, create_bot
# from .ai_engines import GeminiEngine, GrokEngine
from .thirdpartyapikey_manager import ThirdPartyApiKeyManager
# from . import ai_engines
from . import api_server
from .bot_info_dialog import BotInfoDialog
from .create_fake_message_dialog import CreateFakeMessageDialog
from .thirdpartyapikey_dialog import ThirdPartyApiKeyDialog
from .password_manager import PasswordManager
from .encryption_service import EncryptionService, ENCRYPTION_SALT_FILE
from .password_dialogs import CreateMasterPasswordDialog, EnterMasterPasswordDialog, ChangeMasterPasswordDialog
from . import third_parties
from . import third_party
from .ccapikey_manager import CcApiKeyManager
from .ccapikey_dialog import CcApiKeyDialog


class MessageInputTextEdit(QTextEdit):
    """A custom QTextEdit that emits a signal when Ctrl+Enter is pressed.

    This class is used for the message input area, allowing users to send
    messages by pressing Ctrl+Enter.

    Signals:
        ctrl_enter_pressed: Emitted when Ctrl+Enter is pressed.
    """
    ctrl_enter_pressed = pyqtSignal()

    def keyPressEvent(self, event):
        """Handles key press events.

        Emits `ctrl_enter_pressed` if Ctrl+Enter is detected.
        Otherwise, passes the event to the base class.

        Args:
            event (QKeyEvent): The key event.
        """
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.ctrl_enter_pressed.emit()
            return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    """The main window of the chat application.

    This class orchestrates the user interface, manages chatrooms, bots,
    and user interactions. It includes features for sending messages,
    managing API keys with master password protection and encryption,
    and configuring chatrooms and bots. The application requires a master
    password to be set up on first run, which is then used to encrypt
    sensitive data like API keys.
    """

    def __init__(self):
        """Initializes the MainWindow.

        Sets up logging, critical components like PasswordManager, and then
        initiates the master password handling sequence. If master password
        setup is successful, it proceeds to initialize EncryptionService,
        ThirdPartyApiKeyManager, ChatroomManager, and the main user interface.
        If master password setup fails or is cancelled, the application
        initialization is halted, and the window is scheduled to close.
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle(self.tr("Chatroom and Bot Manager"))
        self.setGeometry(100, 100, 800, 600)

        self.third_party_group = third_party.ThirdPartyGroup(
            third_parties.THIRD_PARTY_CLASSES)

        self.data_dir_path = 'data'

        self.password_manager = PasswordManager()
        self.encryption_service = None
        """Service for encrypting/decrypting data, initialized after master password setup."""
        self.thirdpartyapikey_manager = None  # Initialized after password setup
        """Manages third-party API keys, initialized after master password setup."""
        self.ccapikey_manager = None # Initialized after password setup
        """Manages CogniChoir-specific API keys, initialized after master password setup."""

        if not self._handle_master_password_startup():
            self.logger.warning(
                "Master password setup failed or was cancelled. Closing application.")
            # If running in a context where QApplication is already running, self.close() is preferred.
            # If this is very early startup, sys.exit() might be needed.
            # For now, assume self.close() is sufficient if called before app.exec().
            # A more robust way might involve a flag that main() checks after __init__ returns.
            # Close after current event loop processing
            QTimer.singleShot(0, self.close)
            return  # Stop further initialization in __init__

        # Initialize ThirdPartyApiKeyManager now that encryption_service is available
        self.thirdpartyapikey_manager = ThirdPartyApiKeyManager(
            encryption_service=self.encryption_service)
        # Initialize CcApiKeyManager
        self.ccapikey_manager = CcApiKeyManager(
            data_dir=self.data_dir_path,
            encryption_service=self.encryption_service
        )
        self.chatroom_manager = ChatroomManager(
            thirdpartyapikey_manager=self.thirdpartyapikey_manager)
        self.bot_template_manager = BotTemplateManager(
            data_dir=self.data_dir_path)  # Added

        self.api_server_thread = None
        """Thread object for running the Flask API server."""
        self.api_server_port = 5001 # Default, will be loaded from settings
        """Port number for the API server."""
        # self.api_server_port is loaded in _load_settings()

        self._init_ui()
        self._load_settings() # Load settings before starting server
        self._update_chatroom_list()  # Initial population
        self._update_bot_template_list()  # Initial population for templates
        self._start_api_server()

    def _init_ui(self):
        """Initializes the main user interface components and layout.

        This method sets up the entire UI structure of the main window,
        including the menu bar, main layout with splitters, chatroom list panel,
        message display and input panel, and the bot list panel. It connects
        signals from UI elements to their respective handler methods.
        """
        self.logger.debug("Initializing UI...")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # --- Menu Bar ---
        settings_menu = self.menuBar().addMenu(self.tr("Settings"))
        manage_keys_action = QAction(self.tr("Manage 3rd Party API Keys"), self) # Renamed for clarity
        manage_keys_action.triggered.connect(self._show_thirdpartyapikey_dialog)
        settings_menu.addAction(manage_keys_action)

        self.manage_cc_keys_action = QAction(self.tr("Manage CogniChoir API Keys"), self)
        """Menu action to open the CcApiKey management dialog."""
        self.manage_cc_keys_action.triggered.connect(self._show_ccapikey_dialog)
        settings_menu.addAction(self.manage_cc_keys_action)
        # Initial state: enabled if ccapikey_manager was successfully initialized.
        self.manage_cc_keys_action.setEnabled(self.ccapikey_manager is not None)


        change_mp_action = QAction(self.tr("Change Master Password"), self)
        change_mp_action.triggered.connect(
            self._show_change_master_password_dialog)
        settings_menu.addAction(change_mp_action)

        clear_all_data_action = QAction(
            self.tr("Clear All Stored Data..."), self)
        clear_all_data_action.triggered.connect(
            self._clear_all_user_data_via_menu)
        settings_menu.addAction(clear_all_data_action)

        settings_menu.addSeparator() # Added separator

        configure_api_port_action = QAction(self.tr("Configure API Port"), self)
        configure_api_port_action.triggered.connect(self._show_configure_api_port_dialog)
        settings_menu.addAction(configure_api_port_action)

        # --- Main Layout (Splitter for resizable panels) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal, central_widget)
        # Main layout to hold the splitter
        main_layout = QHBoxLayout(central_widget)
        main_layout.addWidget(main_splitter)

        # --- Left Panel (Chatroom List and Bot List) ---
        left_panel_widget = QWidget()
        left_panel_layout = QVBoxLayout(left_panel_widget)

        # Chatroom Management
        chatroom_label = QLabel(self.tr("Chatrooms"))
        left_panel_layout.addWidget(chatroom_label)
        self.chatroom_list_widget = QListWidget()
        self.chatroom_list_widget.currentItemChanged.connect(
            self._on_selected_chatroom_changed)
        # Attempt to set stylesheet for selected item clarity
        self.chatroom_list_widget.setStyleSheet(
            "QListWidget::item:selected { background-color: #ADD8E6; color: black; }")
        self.chatroom_list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)  # Added
        self.chatroom_list_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)  # Added
        self.chatroom_list_widget.customContextMenuRequested.connect(
            self._show_chatroom_context_menu)  # Added
        left_panel_layout.addWidget(self.chatroom_list_widget)

        chatroom_buttons_layout = QHBoxLayout()
        self.new_chatroom_button = QPushButton(
            self.tr("New Chatroom"))  # Store as member for state updates
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

        # --- Bot Template Management ---
        bot_template_label = QLabel(self.tr("Bot Templates"))
        left_panel_layout.addWidget(bot_template_label)

        self.bot_template_list_widget = QListWidget()
        self.bot_template_list_widget.currentItemChanged.connect(
            self._on_selected_bot_template_changed)
        self.bot_template_list_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.bot_template_list_widget.customContextMenuRequested.connect(
            self._show_bot_template_context_menu)
        left_panel_layout.addWidget(self.bot_template_list_widget)

        template_buttons_layout = QHBoxLayout()
        self.new_template_button = QPushButton(self.tr("New"))
        self.new_template_button.clicked.connect(self._create_bot_template)
        template_buttons_layout.addWidget(self.new_template_button)

        self.edit_template_button = QPushButton(self.tr("Edit"))
        self.edit_template_button.clicked.connect(
            self._edit_selected_bot_template)
        template_buttons_layout.addWidget(self.edit_template_button)

        self.remove_template_button = QPushButton(self.tr("Remove"))
        self.remove_template_button.clicked.connect(
            self._remove_selected_bot_template)
        template_buttons_layout.addWidget(self.remove_template_button)

        left_panel_layout.addLayout(template_buttons_layout)
        # End Bot Template Management

        # Bot management UI elements have been moved to the new right panel.
        # The old layout code in left_panel_layout for bots has been removed.

        main_splitter.addWidget(left_panel_widget)

        # --- Middle Panel (Message Display and Input) ---
        right_panel_widget = QWidget()  # This is now the middle panel
        right_panel_layout = QVBoxLayout(right_panel_widget)

        self.message_display_area = QListWidget()
        self.message_display_area.setWordWrap(True)  # Enable word wrap
        self.message_display_area.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.message_display_area.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.message_display_area.customContextMenuRequested.connect(
            self._show_message_context_menu)
        right_panel_layout.addWidget(self.message_display_area, 5)

        # Message Actions Layout (for delete and fake message buttons)
        message_actions_layout = QHBoxLayout()
        # self.delete_message_button = QPushButton(self.tr("Delete Selected Message(s)"))
        # self.delete_message_button.clicked.connect(self._delete_selected_messages)
        # message_actions_layout.addWidget(self.delete_message_button)

        self.create_fake_message_button = QPushButton(
            self.tr("Create Fake Message"))
        self.create_fake_message_button.clicked.connect(
            self._show_create_fake_message_dialog)
        message_actions_layout.addWidget(self.create_fake_message_button)
        right_panel_layout.addLayout(message_actions_layout)

        # Message Input Area
        message_input_layout = QHBoxLayout()
        # self.message_input_area = QLineEdit()
        # Changed to custom QTextEdit for Ctrl+Enter
        self.message_input_area = MessageInputTextEdit()
        # Set a minimum height for better usability
        self.message_input_area.setMinimumHeight(60)
        self.message_input_area.ctrl_enter_pressed.connect(
            self._send_user_message)
        message_input_layout.addWidget(self.message_input_area)
        self.send_message_button = QPushButton(self.tr("Send"))
        self.send_message_button.clicked.connect(self._send_user_message)
        message_input_layout.addWidget(self.send_message_button)
        right_panel_layout.addLayout(message_input_layout)

        # Bot Response Area
        # bot_response_layout = QHBoxLayout()
        # bot_response_label = QLabel(self.tr("Select Bot to Respond:"))
        # bot_response_layout.addWidget(bot_response_label)
        # self.bot_response_selector = QComboBox()
        # bot_response_layout.addWidget(self.bot_response_selector)
        # self.trigger_bot_response_button = QPushButton(self.tr("Get Bot Response"))
        # self.trigger_bot_response_button.clicked.connect(self._trigger_bot_response)
        # bot_response_layout.addWidget(self.trigger_bot_response_button)
        # right_panel_layout.addLayout(bot_response_layout)

        main_splitter.addWidget(right_panel_widget)

        # --- New Right Panel (Bot List and Controls) ---
        bot_list_container_widget = QWidget()
        right_bot_panel_layout = QVBoxLayout(bot_list_container_widget)

        self.bot_panel_label = QLabel(self.tr("Bots"))  # New generic label
        right_bot_panel_layout.addWidget(self.bot_panel_label)

        self.bot_list_widget = QListWidget()
        self.bot_list_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.bot_list_widget.customContextMenuRequested.connect(
            self._show_bot_context_menu)
        self.bot_list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        right_bot_panel_layout.addWidget(
            self.bot_list_widget, 1)  # Add stretch factor

        self.add_bot_button = QPushButton(self.tr("Add Bot"))
        self.add_bot_button.clicked.connect(self._add_bot_to_chatroom)
        right_bot_panel_layout.addWidget(self.add_bot_button)

        main_splitter.addWidget(bot_list_container_widget)
        main_splitter.setSizes([250, 300, 250])  # Adjusted for three panels

        self._update_bot_panel_state(False)  # Initial state
        self._update_message_related_ui_state(
            False)  # Message UI disabled initially
        self._update_template_button_states()  # Initial state for template buttons

    def _update_message_related_ui_state(self, enabled: bool):
        """Updates the enabled/read-only state of message-related UI elements.

        Controls the interactivity of the message input area, send button,
        and create fake message button. If disabling, the message display area
        is cleared.

        Args:
            enabled (bool): True to enable UI elements, False to disable them
                            (sets input to read-only, clears display).
        """
        # Instead of disabling, set read-only for message_input_area
        self.message_input_area.setReadOnly(not enabled)
        self.send_message_button.setEnabled(enabled)
        self.create_fake_message_button.setEnabled(enabled)

        if not enabled:
            self.message_display_area.clear()
            # self.bot_response_selector.clear()

    def _show_message_context_menu(self, position: QPoint):
        """Displays a context menu for selected messages.

        Provides an option to delete the selected message(s) in the
        message display area.

        Args:
            position (QPoint): The position where the context menu was requested,
                               local to the message_display_area widget.
        """
        menu = QMenu()
        if self.message_display_area.selectedItems():
            delete_action = menu.addAction(self.tr("Delete Message(s)"))
            delete_action.triggered.connect(self._delete_selected_messages)
        menu.exec(self.message_display_area.mapToGlobal(position))

    def _show_chatroom_context_menu(self, position: QPoint):
        """Displays a context menu for selected chatroom(s).

        Provides actions like "Rename", "Clone", and "Delete" for chatrooms.
        The available actions depend on whether one or multiple chatrooms are selected.

        Args:
            position (QPoint): The position where the context menu was requested,
                               local to the chatroom_list_widget.
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
            rename_action.triggered.connect(
                self._rename_chatroom)  # Relies on currentItem
            menu.addAction(rename_action)

            clone_action = QAction(self.tr("Clone"), self)
            clone_action.triggered.connect(
                self._clone_selected_chatroom)  # Relies on currentItem
            menu.addAction(clone_action)

            menu.addSeparator()

            delete_action = QAction(self.tr("Delete"), self)
            delete_action.triggered.connect(
                self._delete_chatroom)  # Relies on currentItem
            menu.addAction(delete_action)

        elif num_selected > 1:
            # These actions will currently operate on self.chatroom_list_widget.currentItem()
            # which might not be intuitive if multiple items are selected.
            # The target methods _clone_selected_chatroom and _delete_chatroom
            # will need to be updated to iterate over all selectedItems().

            clone_selected_action = QAction(
                self.tr("Clone Selected Chatrooms ({0})").format(num_selected), self)
            clone_selected_action.triggered.connect(
                self._clone_selected_chatroom)  # Needs update for multi-select
            menu.addAction(clone_selected_action)

            menu.addSeparator()

            delete_selected_action = QAction(
                self.tr("Delete Selected Chatrooms ({0})").format(num_selected), self)
            delete_selected_action.triggered.connect(
                self._delete_chatroom)  # Needs update for multi-select
            menu.addAction(delete_selected_action)

        menu.exec(self.chatroom_list_widget.mapToGlobal(position))

    def _update_bot_panel_state(self, enabled: bool, _chatroom_name: str | None = None):
        """Updates the state of the bot panel UI elements.

        Controls the interactivity of the bot list and "Add Bot" button.
        The bot list's selection mode and focus policy are adjusted based
        on the enabled state.

        Args:
            enabled (bool): True to enable the bot panel elements, False to disable.
            _chatroom_name (Optional[str]): The name of the current chatroom.
                Currently unused in the method body but kept for signature consistency.
        """
        # Instead of disabling, set selection mode to NoSelection when not enabled
        if enabled:
            self.bot_list_widget.setSelectionMode(
                QAbstractItemView.SelectionMode.ExtendedSelection)
            # Allow focus for keyboard navigation
            self.bot_list_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        else:
            self.bot_list_widget.setSelectionMode(
                QAbstractItemView.SelectionMode.NoSelection)
            self.bot_list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.add_bot_button.setEnabled(enabled)
        # self.remove_bot_button.setEnabled(enabled and bool(self.bot_list_widget.currentItem())) # REMOVED

        self.bot_panel_label.setText(self.tr("Bots"))

    # def _update_chatroom_related_button_states(self):
    #     """Updates the enabled state of chatroom action buttons.

    #     Buttons like "Rename Chatroom", "Clone Chatroom", and "Delete Chatroom"
    #     are enabled only if a chatroom is currently selected in the list.
    #     """
    #     has_selection = bool(self.chatroom_list_widget.currentItem())
    #     # self.rename_chatroom_button.setEnabled(has_selection) # REMOVED
    #     # self.clone_chatroom_button.setEnabled(has_selection) # REMOVED
    #     # self.delete_chatroom_button.setEnabled(has_selection) # REMOVED

    def _update_chatroom_list(self):
        """Refreshes the chatroom list widget from the `ChatroomManager`.

        This method clears the existing items in `chatroom_list_widget` and
        repopulates it with the current list of chatrooms. It attempts to
        restore the previously selected chatroom. If no chatroom is selected
        after the update (e.g., if the list is empty or the selected one was
        deleted), it updates other UI parts like the bot list and message area
        to reflect an empty state.
        """
        current_selection_name = self.chatroom_list_widget.currentItem(
        ).text() if self.chatroom_list_widget.currentItem() else None

        self.chatroom_list_widget.clear()
        # list_chatrooms now returns list[Chatroom]
        for chatroom_obj in self.chatroom_manager.list_chatrooms():
            item = QListWidgetItem(chatroom_obj.name)
            self.chatroom_list_widget.addItem(item)
            if chatroom_obj.name == current_selection_name:
                self.chatroom_list_widget.setCurrentItem(
                    item)  # Restore selection

        if self.chatroom_list_widget.currentItem() is None:
            self._update_bot_list(None)
            self._update_bot_panel_state(False)
            self._update_message_related_ui_state(False)

        # self._update_chatroom_related_button_states()

    def _on_selected_chatroom_changed(self, current: QListWidgetItem, _previous: QListWidgetItem):
        """Handles the event when the selected chatroom changes.

        When a new chatroom is selected in the `chatroom_list_widget`, this
        method updates various parts of the UI to reflect the context of the
        newly selected chatroom. This includes:
        - Updating the bot list for the selected chatroom.
        - Enabling/disabling the bot panel.
        - Refreshing the message display area with the chatroom's messages.
        - Enabling/disabling message-related UI elements.

        If no chatroom is selected (e.g., `current` is None), it sets the UI
        to a state reflecting no active chatroom.

        Args:
            current (QListWidgetItem): The newly selected list widget item representing
                                     the current chatroom. Can be None if selection is cleared.
            _previous (QListWidgetItem): The previously selected list widget item.
                                       Currently unused.
        """
        # self._update_chatroom_related_button_states() # Update button states based on selection
        if current:
            selected_chatroom_name = current.text()
            self._update_bot_list(selected_chatroom_name)
            self._update_bot_panel_state(True, selected_chatroom_name)
            self._update_message_display()
            # self._update_bot_response_selector()
            self._update_message_related_ui_state(True)
        else:
            self._update_bot_list(None)
            self._update_bot_panel_state(False)
            self._update_message_display()
            # self._update_bot_response_selector()
            self._update_message_related_ui_state(False)

    def _clone_selected_chatroom(self):
        """Clones the selected chatroom(s) via `ChatroomManager`.

        This method is triggered by the "Clone" action in the chatroom context menu.
        It iterates over all selected chatrooms in `chatroom_list_widget`.
        For each selected chatroom, it calls `self.chatroom_manager.clone_chatroom()`.
        After attempting to clone all selected chatrooms, it updates the
        `chatroom_list_widget` to reflect any new chatrooms.
        It also provides feedback to the user regarding the success or failure
        of the clone operation(s) via `QMessageBox`.
        """
        selected_items = self.chatroom_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, self.tr("Warning"), self.tr(
                "No chatroom(s) selected to clone."))
            return

        cloned_count = 0
        attempted_count = len(selected_items)
        last_cloned_name = None
        # Store original names for the final message if only one was selected
        original_single_selected_name = selected_items[0].text(
        ) if attempted_count == 1 else None

        for item in selected_items:
            original_chatroom_name = item.text()
            self.logger.info(
                f"Attempting to clone chatroom: {original_chatroom_name}")
            cloned_chatroom = self.chatroom_manager.clone_chatroom(
                original_chatroom_name)
            if cloned_chatroom:
                self.logger.info(
                    f"Chatroom '{original_chatroom_name}' cloned successfully as '{cloned_chatroom.name}'.")
                cloned_count += 1
                # Keep track of the last one for single selection focus
                last_cloned_name = cloned_chatroom.name
            else:
                self.logger.error(
                    f"Failed to clone chatroom '{original_chatroom_name}'.")
                # Individual error message for each failure might be too noisy for multiple selections.
                # Rely on the summary and logs.

        self._update_chatroom_list()

        if attempted_count == 1:  # Single selection
            if cloned_count == 1 and last_cloned_name and original_single_selected_name:
                # Try to select the newly cloned chatroom if it was a single clone
                for i in range(self.chatroom_list_widget.count()):
                    if self.chatroom_list_widget.item(i).text() == last_cloned_name:
                        self.chatroom_list_widget.setCurrentRow(i)
                        break
                QMessageBox.information(self, self.tr("Success"),
                                        self.tr("Chatroom '{0}' cloned as '{1}'.").format(original_single_selected_name, last_cloned_name))
            elif original_single_selected_name:  # Ensure it's not None
                QMessageBox.critical(self, self.tr("Error"), self.tr(
                    "Failed to clone chatroom '{0}'.").format(original_single_selected_name))
        else:  # Multiple selections
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
        """Refreshes the message display area with messages from the current chatroom.

        Clears the `message_display_area` and repopulates it with messages
        from the currently selected chatroom in `chatroom_list_widget`.
        Messages are retrieved from the `Chatroom` object and sorted by
        timestamp before display. Each list item stores the message's
        timestamp for potential use in other operations like deletion.
        If no chatroom is selected, the display area is simply cleared.
        """
        current_chatroom_name = self.chatroom_list_widget.currentItem(
        ).text() if self.chatroom_list_widget.currentItem() else None
        self.message_display_area.clear()
        if current_chatroom_name:
            chatroom = self.chatroom_manager.get_chatroom(
                current_chatroom_name)
            if chatroom:
                # Ensure sorted display by timestamp
                for message in sorted(chatroom.get_messages(), key=lambda m: m.timestamp):
                    # Use to_display_string for formatting
                    item = QListWidgetItem(message.to_display_string()+'\n')
                    item.setData(Qt.ItemDataRole.UserRole,
                                 message.timestamp)  # Store timestamp
                    self.message_display_area.addItem(item)

    def _delete_selected_messages(self):
        """Deletes selected messages from the current chatroom's history.

        Retrieves the currently selected chatroom and the selected messages
        from `message_display_area`. After confirming with the user, it
        iterates through the selected messages, using their stored timestamps
        to delete them from the `Chatroom` object via `chatroom.delete_message()`.
        Finally, it refreshes the message display.
        """
        current_chatroom_name = self.chatroom_list_widget.currentItem(
        ).text() if self.chatroom_list_widget.currentItem() else None
        if not current_chatroom_name:
            QMessageBox.warning(self, self.tr("Warning"),
                                self.tr("No chatroom selected."))
            return

        chatroom = self.chatroom_manager.get_chatroom(current_chatroom_name)
        if not chatroom:
            return  # Should not happen if UI is consistent

        selected_items = self.message_display_area.selectedItems()
        if not selected_items:
            QMessageBox.information(self, self.tr("Information"), self.tr(
                "No messages selected to delete."))
            return

        reply = QMessageBox.question(self, self.tr("Confirm Deletion"),
                                     self.tr("Are you sure you want to delete {0} message(s)?").format(
                                         len(selected_items)),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            for item in selected_items:
                timestamp = item.data(Qt.ItemDataRole.UserRole)
                # delete_message calls _notify_chatroom_updated
                if chatroom.delete_message(timestamp):
                    deleted_count += 1
            if deleted_count > 0:
                self._update_message_display()  # Refresh display

    def _show_create_fake_message_dialog(self):
        """Opens a dialog to manually create and add a "fake" message.

        This method is typically used for testing or development purposes.
        It ensures a chatroom is selected, then displays the
        `CreateFakeMessageDialog`. If the dialog is accepted and returns
        valid sender and content, the message is added to the current
        chatroom's history, and the message display is updated.
        """
        current_chatroom_name = self.chatroom_list_widget.currentItem(
        ).text() if self.chatroom_list_widget.currentItem() else None
        if not current_chatroom_name:
            QMessageBox.warning(self, self.tr("Warning"),
                                self.tr("No chatroom selected."))
            return

        chatroom = self.chatroom_manager.get_chatroom(current_chatroom_name)
        if not chatroom:
            return  # Should not happen

        current_bot_names = [bot.name for bot in chatroom.list_bots()]
        dialog = CreateFakeMessageDialog(current_bot_names, self)

        if dialog.exec():  # exec() shows the dialog
            data = dialog.get_data()
            if data:
                sender, content = data
                if not content.strip():
                    QMessageBox.warning(self, self.tr("Warning"), self.tr(
                        "Message content cannot be empty."))
                    return
                # This will use current timestamp and trigger save
                chatroom.add_message(sender, content)
                self._update_message_display()  # Refresh

    def _send_user_message(self):
        """Sends a message from the user to the current chatroom.

        Retrieves the text from the `message_input_area`. If a chatroom
        is selected and the message text is not empty, it adds the message
        to the `Chatroom` object with "User" as the sender.
        The message display is then updated, and the input area is cleared.
        """
        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr(
                "No chatroom selected to send message."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:  # Should not happen if item is selected
            QMessageBox.critical(self, self.tr("Error"),
                                 self.tr("Selected chatroom not found."))
            return

        # text = self.message_input_area.text().strip()
        # Use QTextEdit for multi-line input
        text = self.message_input_area.toPlainText().strip()
        if not text:
            return

        self.logger.info(
            f"Sending user message of length {len(text)} to chatroom '{chatroom_name}'.")
        chatroom.add_message("User", text)
        self._update_message_display()
        self.message_input_area.clear()

    # def _update_bot_response_selector(self):
    #     """Updates the bot response selector combo box.

    #     Populates the combo box with the names of bots from the currently
    #     selected chatroom. The "Get Bot Response" button is enabled only
    #     if there are bots in the selector.
    #     """
    #     self.bot_response_selector.clear()
    #     current_chatroom_item = self.chatroom_list_widget.currentItem()
    #     if not current_chatroom_item:
    #         return

    #     chatroom_name = current_chatroom_item.text()
    #     chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
    #     if chatroom:
    #         for bot in chatroom.list_bots():
    #             self.bot_response_selector.addItem(bot.get_name())

    #     # Disable trigger button if no bots are available
    #     # self.trigger_bot_response_button.setEnabled(self.bot_response_selector.count() > 0)

    def _trigger_bot_response(self, bot_name_override: str | None = None):
        """Triggers a response from a specified bot in the current chatroom.

        This method orchestrates fetching a bot's response. It identifies the
        target bot either through an override name (if provided) or by
        determining which bot's "play" button was clicked.
        It gathers the conversation history from the current chatroom.
        The method then calls `third_party_group.generate_response()`
        with the bot's configuration, API keys (retrieved via `thirdpartyapikey_manager`),
        and conversation history.

        The bot's response is added to the chatroom and the message display
        is updated. Errors during response generation (e.g., network issues,
        API errors, configuration problems) are caught, logged, and displayed
        to the user via `QMessageBox`. A system message indicating the error
        may also be added to the chat.

        Args:
            bot_name_override (Optional[str]): If provided, this specific bot's name
                is used to trigger the response, bypassing UI elements like
                a bot selector dropdown. Defaults to None.
        """
        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            QMessageBox.warning(self, self.tr("Warning"),
                                self.tr("No chatroom selected."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            self.logger.error(
                f"Trigger bot response: Selected chatroom '{chatroom_name}' not found.")
            QMessageBox.critical(self, self.tr("Error"),
                                 self.tr("Selected chatroom not found."))
            return

        # if self.bot_response_selector.count() == 0:
        #     self.logger.warning(f"Trigger bot response: No bots in chatroom '{chatroom_name}'.")
        #     QMessageBox.warning(self, self.tr("Warning"), self.tr("Selected chatroom has no bots to respond."))
        #     return

        selected_bot_name_to_use = bot_name_override
        # if not selected_bot_name_to_use:  # Fallback to combo box if no override
        #     if self.bot_response_selector.count() == 0: # Should be redundant due to above check but good for safety
        #         self.logger.warning(f"Trigger bot response: No bots in chatroom '{chatroom_name}' (selector empty).")
        #         QMessageBox.warning(self, self.tr("Warning"), self.tr("Selected chatroom has no bots to respond."))
        #         return
        #     selected_bot_name_to_use = self.bot_response_selector.currentText()
        #     if not selected_bot_name_to_use:
        #         self.logger.warning("Trigger bot response: No bot selected in dropdown.")
        #         QMessageBox.warning(self, self.tr("Warning"), self.tr("No bot selected to respond."))
        #         return

        bot = chatroom.get_bot(selected_bot_name_to_use)
        if not bot:
            self.logger.error(
                f"Trigger bot response: Bot '{selected_bot_name_to_use}' not found in chatroom '{chatroom_name}'.")
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "Bot '{0}' not found in chatroom.").format(selected_bot_name_to_use))
            return

        # if isinstance(engine, (GeminiEngine, GrokEngine)):
        #     thirdpartyapikey = self.thirdpartyapikey_manager.load_key(engine_type_name)
        #     if not thirdpartyapikey:
        #         self.logger.warning(f"Trigger bot response: API key missing for bot '{bot.get_name()}' using engine '{engine_type_name}'.")
        #         QMessageBox.warning(self, self.tr("API Key Missing"),
        #                             self.tr("Bot {0} (using {1}) needs an API key. Please set it in Settings.").format(bot.get_name(), engine_type_name))
        #         return

        self.logger.info(
            f"Attempting to trigger bot response for bot '{selected_bot_name_to_use}' in chatroom '{chatroom_name}'.")
        conversation_history = chatroom.get_messages()

        if not conversation_history:
            self.logger.info(
                f"Trigger bot response: No messages in chatroom '{chatroom_name}' to respond to for bot '{selected_bot_name_to_use}'.")
            QMessageBox.information(self, self.tr("Info"), self.tr(
                "No messages in chat to respond to."))
            return

        # UI updates to indicate processing, only for the main button
        # original_button_text = None
        # True if triggered by the main UI button
        is_main_button_trigger = not bot_name_override
        if is_main_button_trigger:
            # original_button_text = self.trigger_bot_response_button.text()
            # self.trigger_bot_response_button.setText(self.tr("Waiting for AI..."))
            # self.trigger_bot_response_button.setEnabled(False)
            QApplication.processEvents()

        try:
            ai_response = self.third_party_group.generate_response(
                aiengine_id=bot.aiengine_id,
                aiengine_arg_dict=bot.aiengine_arg_dict,
                thirdpartyapikey_list=self.thirdpartyapikey_manager.get_thirdpartyapikey_list(
                    bot.thirdpartyapikey_query_list),
                role_name=bot.name,
                conversation_history=conversation_history,
            )
            self.logger.info(
                f"Bot '{selected_bot_name_to_use}' generated response successfully in chatroom '{chatroom_name}'.")
            chatroom.add_message(bot.name, ai_response)
            self._update_message_display()
        except ValueError as ve:  # Specific handling for ValueErrors from create_bot or engine
            self.logger.error(
                f"Configuration or input error for bot '{selected_bot_name_to_use}': {ve}", exc_info=True)
            QMessageBox.critical(self, self.tr(
                "Bot Configuration Error"), str(ve))
            # Optionally add system message to chatroom for this type of error too
            # chatroom.add_message("System", self.tr("Error with bot '{0}': {1}").format(selected_bot_name_to_use, str(ve)))
            # self._update_message_display()
        except Exception as e:
            self.logger.error(
                f"Error during bot response generation for bot '{selected_bot_name_to_use}' in chatroom '{chatroom_name}': {e}", exc_info=True)
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "An error occurred while getting bot response for '{0}': {1}").format(selected_bot_name_to_use, str(e)))
            chatroom.add_message("System", self.tr(
                "Error during bot response for '{0}': {1}").format(selected_bot_name_to_use, str(e)))
            self._update_message_display()
        finally:
            # if is_main_button_trigger and original_button_text is not None:
            #     self.trigger_bot_response_button.setText(original_button_text)
            # The message related UI state should be updated regardless of which button triggered
            self._update_message_related_ui_state(
                bool(self.chatroom_list_widget.currentItem()))

    def _create_chatroom(self):
        """Initiates the creation of a new chatroom.

        Opens a `QInputDialog` to get the desired name for the new chatroom
        from the user. If a name is provided and it's not empty:
        - It calls `self.chatroom_manager.create_chatroom()` to create and
          persist the new chatroom.
        - If creation is successful, `_update_chatroom_list()` is called to
          refresh the UI, and the new chatroom is selected.
        - If the chatroom name already exists, a warning message is shown.
        """
        name, ok = QInputDialog.getText(self, self.tr(
            "New Chatroom"), self.tr("Enter chatroom name:"))
        if ok and name:
            if self.chatroom_manager.create_chatroom(name):
                # INFO - user action success
                self.logger.info(f"Chatroom '{name}' created successfully.")
                self._update_chatroom_list()
                # Optionally select the new chatroom
                items = self.chatroom_list_widget.findItems(
                    name, Qt.MatchFlag.MatchExactly)
                if items:
                    self.chatroom_list_widget.setCurrentItem(items[0])
            else:
                # WARNING - user action failed, but recoverable
                self.logger.warning(
                    f"Failed to create chatroom '{name}', it likely already exists.")
                QMessageBox.warning(self, self.tr("Error"), self.tr(
                    "Chatroom '{0}' already exists.").format(name))
        # Name was provided but 'ok' was false (dialog cancelled) or name was empty after ok.
        elif name:
            self.logger.debug(
                f"Chatroom creation cancelled or name was invalid: '{name}'.")
        # 'ok' was false and name was empty (dialog cancelled with no input).
        else:
            self.logger.debug("Chatroom creation cancelled by user.")

    def _rename_chatroom(self):
        """Initiates renaming of the selected chatroom.

        Ensures a chatroom is selected in `chatroom_list_widget`.
        Opens a `QInputDialog` pre-filled with the current chatroom name,
        prompting the user for a new name.
        If a new name is provided, is not empty, and is different from the old name:
        - It calls `self.chatroom_manager.rename_chatroom()`.
        - If renaming is successful, `_update_chatroom_list()` is called, and
          the renamed chatroom is re-selected.
        - If renaming fails (e.g., new name already exists), a warning is shown.
        """
        current_item = self.chatroom_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr(
                "No chatroom selected to rename."))
            return

        old_name = current_item.text()
        new_name, ok = QInputDialog.getText(self, self.tr(
            "Rename Chatroom"), self.tr("Enter new name:"), text=old_name)

        if ok and new_name and new_name != old_name:
            if self.chatroom_manager.rename_chatroom(old_name, new_name):
                self.logger.info(
                    f"Chatroom '{old_name}' renamed to '{new_name}' successfully.")
                self._update_chatroom_list()
                # Re-select the renamed chatroom
                items = self.chatroom_list_widget.findItems(
                    new_name, Qt.MatchFlag.MatchExactly)
                if items:
                    self.chatroom_list_widget.setCurrentItem(items[0])
            else:
                # WARNING - user action failed
                self.logger.warning(
                    f"Failed to rename chatroom '{old_name}' to '{new_name}'. New name might already exist.")
                QMessageBox.warning(self, self.tr("Error"), self.tr(
                    "Could not rename chatroom. New name '{0}' might already exist.").format(new_name))
        elif ok and not new_name:
            # WARNING - invalid input
            self.logger.warning(
                f"Attempt to rename chatroom '{old_name}' with an empty name.")
            QMessageBox.warning(self, self.tr("Warning"), self.tr(
                "New chatroom name cannot be empty."))
        elif not ok:  # User cancelled the dialog
            self.logger.debug(
                f"Chatroom rename for '{old_name}' cancelled by user.")

    def _delete_chatroom(self):
        """Initiates deletion of the selected chatroom(s).

        Retrieves all selected chatrooms from `chatroom_list_widget`.
        Prompts the user with a confirmation dialog, listing the names of
        chatrooms to be deleted.
        If confirmed:
        - It iterates through the selected chatroom names and calls
          `self.chatroom_manager.delete_chatroom()` for each.
        - After attempting deletion for all selected, `_update_chatroom_list()`
          is called to refresh the UI.
        - Feedback is provided to the user about the outcome (success, partial
          deletion, or failure).
        """
        selected_items = self.chatroom_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, self.tr("Warning"), self.tr(
                "No chatroom(s) selected to delete."))
            return

        num_selected = len(selected_items)
        names_to_delete = [item.text() for item in selected_items]

        # For single deletion, keep the old simple message
        if num_selected == 1:
            confirm_message = self.tr(
                "Are you sure you want to delete chatroom '{0}'?").format(names_to_delete[0])
        else:  # For multiple deletions, list the names
            confirm_message = self.tr("Are you sure you want to delete the following {0} chatroom(s)?\n\n- {1}").format(
                num_selected, "\n- ".join(names_to_delete)
            )

        reply = QMessageBox.question(self, self.tr("Confirm Deletion"), confirm_message,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            for name in names_to_delete:
                self.logger.info(f"Deleting chatroom '{name}'.")
                # delete_chatroom returns True on success, False on failure
                if self.chatroom_manager.delete_chatroom(name):
                    deleted_count += 1
                else:
                    # This case (delete_chatroom returns False) implies the chatroom wasn't found or couldn't be deleted.
                    self.logger.warning(
                        f"Failed to delete chatroom '{name}' during batch operation (it might have already been deleted or an error occurred).")

            self._update_chatroom_list()
            # _update_chatroom_list will handle UI updates including bot list and panel if necessary.
            # For instance, if the current selection is removed, _on_selected_chatroom_changed will eventually
            # be triggered with a None current item, or a new current item.
            # If the list becomes empty, _update_chatroom_list handles this by calling:
            # self._update_bot_list(None)
            # self._update_bot_panel_state(False)
            # self._update_message_related_ui_state(False)

            if num_selected == 1:  # Message for single deletion
                if deleted_count == 1:
                    # Implicitly successful as no specific message for single success needed other than list update
                    # QMessageBox.information(self, self.tr("Success"), self.tr("Chatroom '{0}' deleted.").format(names_to_delete[0])) # Optional: could be too noisy
                    pass
                else:  # Should not happen if delete_chatroom was successful, but as a fallback
                    QMessageBox.warning(self, self.tr("Deletion Failed"), self.tr(
                        "Could not delete chatroom '{0}'. It may have already been removed.").format(names_to_delete[0]))

            else:  # Messages for multiple deletions
                if deleted_count == num_selected:
                    QMessageBox.information(self, self.tr("Success"),
                                            self.tr("Successfully deleted {0} chatroom(s).").format(deleted_count))
                elif deleted_count > 0:
                    QMessageBox.warning(self, self.tr("Partial Deletion"),
                                        self.tr("Successfully deleted {0} out of {1} selected chatrooms. Some may have already been deleted or an error occurred.").format(deleted_count, num_selected))
                else:  # deleted_count == 0
                    QMessageBox.critical(self, self.tr("Deletion Failed"),
                                         self.tr("Failed to delete any of the selected {0} chatrooms. They may have already been deleted or an error occurred.").format(num_selected))
        else:
            self.logger.debug(
                f"Deletion of {num_selected} chatroom(s) cancelled by user.")

    def _update_bot_list(self, chatroom_name: Optional[str]):
        """Refreshes the bot list widget for the given chatroom.

        Clears `bot_list_widget` and repopulates it with bots from the
        chatroom specified by `chatroom_name`. Each bot is displayed using
        a custom widget created by `_create_bot_list_item_widget()`.
        If `chatroom_name` is None or the chatroom is not found, the list
        is cleared. The state of the bot panel is also updated.

        Args:
            chatroom_name (Optional[str]): The name of the chatroom whose bots
                are to be displayed. If None, the bot list is cleared.
        """
        self.bot_list_widget.clear()
        if chatroom_name:
            chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
            if chatroom:
                for bot in chatroom.list_bots():
                    # self.bot_list_widget.addItem(QListWidgetItem(bot.get_name())) # Old way
                    bot_name_str = bot.name  # Ensure it's a string
                    item_widget = self._create_bot_list_item_widget(
                        bot_name_str)

                    list_item = QListWidgetItem(self.bot_list_widget)
                    list_item.setData(Qt.ItemDataRole.UserRole,
                                      bot_name_str)  # Store bot name

                    # Set size hint for the list item to ensure custom widget is displayed correctly
                    list_item.setSizeHint(item_widget.sizeHint())

                    self.bot_list_widget.addItem(list_item)
                    self.bot_list_widget.setItemWidget(list_item, item_widget)

        # Update panel state based on whether a chatroom is active
        self._update_bot_panel_state(chatroom_name is not None and self.chatroom_manager.get_chatroom(
            chatroom_name) is not None, chatroom_name)

    def _show_bot_context_menu(self, position: QPoint):
        """Displays a context menu for selected bot(s) in the bot list.

        Provides actions like "Edit" (for single selection), "Clone", and
        "Delete". The available actions adapt based on the number of selected bots.

        Args:
            position (QPoint): The position where the context menu was requested,
                               local to the `bot_list_widget`.
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
            clone_action = QAction(
                self.tr("Clone Selected Bots"), self)  # Pluralized
            clone_action.triggered.connect(self._clone_selected_bots)
            menu.addAction(clone_action)

            delete_action = QAction(
                self.tr("Delete Selected Bots"), self)  # Pluralized
            delete_action.triggered.connect(self._delete_selected_bots)
            menu.addAction(delete_action)

        menu.exec(self.bot_list_widget.mapToGlobal(position))

    def _edit_selected_bot(self):
        """Handles editing the configuration of the selected bot.

        This method is triggered by the "Edit" action in the bot context menu.
        It retrieves the selected bot, populates an `BotInfoDialog` with its
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
            self.logger.error(
                f"Bot '{bot_name_to_edit}' not found in chatroom '{chatroom_name}' for editing.")
            return

        # Prepare BotInfoDialog
        # current_name = bot_to_edit.name
        # current_engine_instance = bot_to_edit.get_engine()
        # current_engine_type = type(current_engine_instance).__name__
        # current_model_name = getattr(current_engine_instance, 'model_name', None) # Handle if no model_name
        # current_system_prompt = bot_to_edit.get_system_prompt()

        all_bot_names_in_chatroom = [bot.name for bot in chatroom.list_bots()]
        existing_bot_names_for_dialog = [
            name for name in all_bot_names_in_chatroom if name != bot_to_edit.name]

        dialog = BotInfoDialog(
            existing_bot_names=existing_bot_names_for_dialog,
            aiengine_info_list=self.third_party_group.aiengine_info_list,
            thirdpartyapikey_query_list=self.thirdpartyapikey_manager.get_available_thirdpartyapikey_query_list(),
            old_bot=bot_to_edit,
            parent=self
        )
        dialog.setWindowTitle(
            self.tr("Edit Bot: {0}").format(bot_to_edit.name))

        # Pre-fill dialog fields
        # dialog.set_bot_values(bot_to_edit)
        # dialog.bot_name_input.setText(bot_to_edit.name)
        # dialog.engine_combo.setCurrentText(bot_to_edit.aiengine_id)
        # # if current_model_name:
        # dialog.model_name_input.setText(bot_to_edit.get_aiengine_arg('model_name',''))
        # dialog.system_prompt_input.setPlainText(bot_to_edit.get_aiengine_arg('system_prompt',''))

        if dialog.exec():
            new_bot = dialog.get_bot()
            if not new_bot:  # Should not happen if dialog accept() worked
                return

            # name_changed = (new_bot.name != bot_to_edit.name)
            # engine_changed = (new_bot.aiengine_id != bot_to_edit.aiengine_id or \
            #                   new_bot.get_aiengine_arg('model_name') !=new_bot.get_aiengine_arg('model_name'))
            #                   # Ensure empty new_model_name matches None current_model_name

            # Use current_name for removal
            if not chatroom.remove_bot(bot_to_edit.name):
                self.logger.error(
                    f"Failed to remove bot '{bot_to_edit.name}' before renaming.")
                return

            # if engine_changed:
            #     self.logger.debug(f"Engine change detected for bot '{new_name}'. Old: {current_engine_type}, New: {new_engine_type}")
            #     thirdpartyapikey = self.thirdpartyapikey_manager.load_key(new_engine_type)

            #     try:
            #         engine_class = ai_engines.ENGINE_TYPE_TO_CLASS_MAP.get(new_engine_type)
            #         if not engine_class:
            #             raise ValueError(f"Unsupported engine type: {new_engine_type}")

            #         new_engine_instance = engine_class(thirdpartyapikey=thirdpartyapikey, model_name=new_model_name if new_model_name else None)
            #         bot_to_edit.set_engine(new_engine_instance)
            #         self.logger.info(f"Bot '{new_name}' engine updated to {new_engine_type} with model '{new_model_name}'.")

            #     except ValueError as e:
            #         self.logger.error(f"Error updating bot engine for '{new_name}': {e}", exc_info=True)
            #         QMessageBox.critical(self, self.tr("Error Updating Bot"), self.tr("Could not update bot engine: {0}").format(str(e)))
            #         # Rollback name change if it happened and bot was removed
            #         if name_changed:
            #             bot_to_edit.set_name(current_name) # Revert name
            #             chatroom.add_bot(bot_to_edit) # Re-add with old name and old engine
            #         return # Stop further processing

            if not chatroom.add_bot(new_bot):
                self.logger.error(
                    f"Failed to re-add bot '{new_bot.name}' after name change.")
                QMessageBox.critical(self, self.tr("Error Updating Bot"), self.tr(
                    "Could not re-add bot with new name. Bot may be in an inconsistent state."))
                return

            self.logger.info(
                f"Bot '{bot_to_edit.name}' updated successfully. New name: '{new_bot.name}'")

            # Explicitly notify chatroom manager about the update for saving
            self.chatroom_manager.notify_chatroom_updated(chatroom)

            self._update_bot_list(chatroom_name)
            # self._update_bot_response_selector()
        else:
            self.logger.debug(f"Edit bot '{bot_name_to_edit}' cancelled.")

    def _clone_selected_bots(self):
        """Clones the selected bot(s) within the current chatroom.

        Iterates through bots selected in `bot_list_widget`. For each original bot:
        1. Determines a unique name for the clone (e.g., "Bot (Copy)", "Bot (Copy) 1").
        2. Creates a deep copy of the original bot.
        3. Sets the unique name for the cloned bot.
        4. Adds the cloned bot to the current chatroom using `chatroom.add_bot()`.
        After processing all selections, the bot list is updated, and the user
        is notified of the outcome.
        """
        selected_items = self.bot_list_widget.selectedItems()
        if not selected_items:
            self.logger.warning("Clone bot(s) called without any selection.")
            return

        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:  # This should ideally not happen if items are selected from the list tied to a chatroom
            self.logger.error("No chatroom selected to clone bots into.")
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "No chatroom context for cloning."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            self.logger.error(
                f"Chatroom '{chatroom_name}' not found for cloning bots.")
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "Could not find the current chatroom."))
            return

        cloned_count = 0
        # existing_bot_names_in_chatroom = [bot.get_name() for bot in chatroom.list_bots()]

        for list_item in selected_items:
            original_bot_name = list_item.data(Qt.ItemDataRole.UserRole)
            if not original_bot_name:
                self.logger.warning(
                    "Could not retrieve bot name from list item, skipping clone.")
                continue

            original_bot = chatroom.get_bot(original_bot_name)
            if not original_bot:
                self.logger.error(
                    f"Bot '{original_bot_name}' not found in chatroom '{chatroom_name}' for cloning.")
                continue

            # Generate Unique Clone Name
            base_clone_name = f"{original_bot.name} (Copy)"
            clone_name = base_clone_name
            copy_number = 1
            # Update the list of existing names within the loop if multiple clones are made from the same original
            # or if multiple bots are selected for cloning in one go.
            current_existing_names = [bot.name for bot in chatroom.list_bots()]
            while clone_name in current_existing_names:
                clone_name = f"{base_clone_name} {copy_number}"
                copy_number += 1

            # Gather Original Bot's Data
            # original_system_prompt = original_bot.get_system_prompt()
            # original_engine_instance = original_bot.get_engine()
            # original_engine_type = type(original_engine_instance).__name__
            # original_model_name = getattr(original_engine_instance, 'model_name', None)
            # thirdpartyapikey = self.thirdpartyapikey_manager.load_key(original_engine_type) # API key might be None

            # engine_config = {
            #     "engine_type": original_engine_type,
            #     "thirdpartyapikey": thirdpartyapikey, # Pass along, could be None
            #     "model_name": original_model_name
            # }

            # try:
            #     cloned_bot = create_bot(bot_name=clone_name, system_prompt=original_system_prompt, engine_config=engine_config)
            # except ValueError as e:
            #     self.logger.error(f"Error creating cloned bot '{clone_name}': {e}", exc_info=True)
            #     QMessageBox.warning(self, self.tr("Clone Error"), self.tr("Could not create clone for bot '{0}': {1}").format(original_bot_name, str(e)))
            #     continue
            cloned_bot = copy.deepcopy(original_bot)
            cloned_bot.name = clone_name  # Set the new name

            if chatroom.add_bot(cloned_bot):
                self.logger.info(
                    f"Bot '{original_bot_name}' cloned as '{clone_name}' in chatroom '{chatroom_name}'.")
                cloned_count += 1
                # Add the new clone's name to the list for subsequent unique name checks in this loop
                # This is implicitly handled by `current_existing_names = [bot.get_name() for bot in chatroom.list_bots()]`
                # at the start of the loop, but if `add_bot` doesn't immediately update the source for `list_bots()`,
                # this might be needed: current_existing_names.append(clone_name)
            else:
                self.logger.error(
                    f"Failed to add cloned bot '{clone_name}' to chatroom '{chatroom_name}'. This might be due to a duplicate name if check failed.")
                QMessageBox.warning(self, self.tr("Clone Error"), self.tr(
                    "Could not add cloned bot '{0}' to chatroom. It might already exist.").format(clone_name))

        if cloned_count > 0:
            self._update_bot_list(chatroom_name)
            # self._update_bot_response_selector()
            # chatroom.add_bot should call _notify_chatroom_updated, so an explicit call here might be redundant
            # but ensures saving if multiple bots are added in a loop and add_bot is not immediately saving.
            self.chatroom_manager.notify_chatroom_updated(chatroom)

        if cloned_count == len(selected_items):
            QMessageBox.information(self, self.tr("Clone Successful"), self.tr(
                "{0} bot(s) cloned successfully.").format(cloned_count))
        elif cloned_count > 0:
            QMessageBox.warning(self, self.tr("Clone Partially Successful"), self.tr(
                "Successfully cloned {0} out of {1} selected bots.").format(cloned_count, len(selected_items)))
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
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "No chatroom context for deletion."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            self.logger.error(
                f"Chatroom '{chatroom_name}' not found for deleting bots.")
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "Could not find the current chatroom."))
            return

        num_selected = len(selected_items)
        bot_names_to_delete = [
            item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        # Filter out None values
        bot_names_to_delete = [name for name in bot_names_to_delete if name]

        if not bot_names_to_delete:
            self.logger.error(
                "Could not retrieve bot names for deletion from selected items.")
            QMessageBox.warning(self, self.tr("Error"), self.tr(
                "Could not identify bots to delete."))
            return

        confirm_message = self.tr("Are you sure you want to delete the selected {0} bot(s)?\n\n{1}").format(
            num_selected, "\n".join(bot_names_to_delete))
        reply = QMessageBox.question(self, self.tr("Confirm Deletion"), confirm_message,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.No:
            self.logger.debug("Bot deletion cancelled by user.")
            return

        deleted_count = 0
        for bot_name in bot_names_to_delete:
            # remove_bot should notify the manager for saving
            if chatroom.remove_bot(bot_name):
                self.logger.info(
                    f"Bot '{bot_name}' removed from chatroom '{chatroom_name}'.")
                deleted_count += 1
            else:
                self.logger.warning(
                    f"Failed to remove bot '{bot_name}' from chatroom '{chatroom_name}' (it might have already been removed or not found).")

        if deleted_count > 0:
            self._update_bot_list(chatroom_name)
            # self._update_bot_response_selector()
            # Chatroom.remove_bot is expected to call _notify_chatroom_updated.
            # If it doesn't, an explicit call here would be:
            # self.chatroom_manager._notify_chatroom_updated(chatroom)
            QMessageBox.information(self, self.tr("Deletion Successful"), self.tr(
                "{0} bot(s) deleted successfully.").format(deleted_count))
        elif selected_items:  # Attempted deletion but nothing was actually deleted
            QMessageBox.warning(self, self.tr("Deletion Failed"), self.tr(
                "No bots were deleted. They may have already been removed or an error occurred."))

    def _create_bot_list_item_widget(self, bot_name: str) -> QWidget:
        """Creates a custom widget for an item in the bot list.

        This widget displays the bot's name and a "play" button to trigger
        its response. It includes a placeholder for a bot avatar.

        Args:
            bot_name (str): The name of the bot to display in this item.

        Returns:
            QWidget: A custom widget designed for display in the `bot_list_widget`.
        """
        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(5, 5, 5, 5)  # Add some padding
        item_layout.setSpacing(5)  # Add a small spacing between elements

        # Avatar Placeholder
        avatar_label = QLabel()
        avatar_label.setFixedSize(40, 40)
        avatar_label.setStyleSheet(
            "border: 1px solid gray; background-color: lightgray;")
        # Center placeholder text if any
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # You could add text like "Ava" or an icon here if desired
        # avatar_label.setText("Bot")
        item_layout.addWidget(avatar_label)

        # Bot Name Label
        name_label = QLabel(bot_name)
        name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        item_layout.addWidget(name_label)

        # Response Button
        response_button = QPushButton()
        response_button.setIcon(self.style().standardIcon(
            QStyle.StandardPixmap.SP_MediaPlay))
        response_button.setToolTip(self.tr("Trigger bot response"))
        # Adjusted for better icon visibility
        response_button.setFixedWidth(35)
        response_button.clicked.connect(
            lambda checked=False, b_name=bot_name: self._on_bot_response_button_clicked(b_name))
        item_layout.addWidget(response_button)

        item_widget.setLayout(item_layout)
        return item_widget

    def _on_bot_response_button_clicked(self, bot_name: str):
        """Handles the click of the 'play' button on a bot list item.

        This method is connected to the click signal of the response button
        created in `_create_bot_list_item_widget()`. It triggers a response
        from the specified bot within the context of the currently selected
        chatroom.

        Args:
            bot_name (str): The name of the bot whose response button was clicked.
        """
        self.logger.debug(f"Response button clicked for bot: {bot_name}")

        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            # This case should ideally not be reached if the button is part of a visible list
            # that implies an active chatroom.
            self.logger.warning(
                "Bot response button clicked but no chatroom selected.")
            QMessageBox.warning(self, self.tr("Action Failed"), self.tr(
                "No chatroom is currently selected."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            self.logger.error(
                f"_on_bot_response_button_clicked: Chatroom '{chatroom_name}' not found unexpectedly.")
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "Chatroom context lost for bot response."))
            return

        # Sanity check: ensure the bot still exists in the chatroom
        if not chatroom.get_bot(bot_name):
            self.logger.warning(
                f"Bot '{bot_name}' (from button) not found in chatroom '{chatroom_name}'. List might be stale.")
            QMessageBox.warning(self, self.tr("Action Failed"),
                                self.tr("Bot '{0}' seems to have been removed. Please refresh or try again.").format(bot_name))
            # Refresh the list to reflect current state
            self._update_bot_list(chatroom_name)
            return

        self._trigger_bot_response(bot_name_override=bot_name)

    def _add_bot_to_chatroom(self):
        """Initiates adding a new bot to the currently selected chatroom.

        Ensures a chatroom is selected. Then, it opens an `BotInfoDialog`,
        providing it with existing bot names in the current chatroom (to prevent
        duplicates), a list of available AI engine information, and available API
        key queries.

        If the dialog is accepted and returns a valid new `Bot` object:
        - The new bot is added to the current chatroom using `chatroom.add_bot()`.
        - The bot list UI is updated.
        - If adding fails for some reason after dialog acceptance, an error is shown.
        """
        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr(
                "No chatroom selected to add a bot to."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:  # Should not happen if item is selected
            QMessageBox.critical(self, self.tr("Error"),
                                 self.tr("Selected chatroom not found."))
            return

        existing_bot_names_in_chatroom = [
            bot.name for bot in chatroom.list_bots()]
        dialog = BotInfoDialog(
            existing_bot_names=existing_bot_names_in_chatroom,
            aiengine_info_list=self.third_party_group.aiengine_info_list,
            thirdpartyapikey_query_list=self.thirdpartyapikey_manager.get_available_thirdpartyapikey_query_list(),
            parent=self
        )

        if dialog.exec():  # This now uses the overridden accept method for validation
            # data = dialog.get_data()
            new_bot = dialog.get_bot()  # This will return None if validation fails
            if not new_bot:  # Safeguard, should not happen if accept validation passed
                return

            # Bot name validation (emptiness, duplication) is now handled within BotInfoDialog.accept()
            # bot_name = data["bot_name"] # Already stripped in dialog's get_data or accept
            # engine_type = data["engine_type"]
            # model_name = data["model_name"] # Already stripped
            # system_prompt = data["system_prompt"]
            # Validation for bot_name (empty, duplicate) is now done in BotInfoDialog.accept()

            # Check if the selected engine type requires an API key by looking at the class constructor
            # This check is illustrative; a more robust check might involve inspecting constructor parameters
            # or having a metadata attribute in engine classes.
            # engine_class = ai_engines.ENGINE_TYPE_TO_CLASS_MAP.get(engine_type)

            # new_bot_aiengine_id = new_bot.aiengine_id
            # new_bot_thirdpartyapikey_slot_id_list = self.third_party_group.aiengine_id_to_aiengine_info_dict[new_bot_aiengine_id].thirdpartyapikey_slot_id_list

            # thirdpartyapikey_exist = any(map(lambda thirdpartyapikey_slot_id: self.thirdpartyapikey_manager.has_key(thirdpartyapikey_slot_id), new_bot_thirdpartyapikey_slot_id_list))

            # thirdpartyapikey = self.thirdpartyapikey_manager.load_key(engine_type)

            # engine_config = {"engine_type": engine_type, "thirdpartyapikey": thirdpartyapikey if thirdpartyapikey else None}
            # if model_name:
            #     engine_config["model_name"] = model_name

            # try:
            #     new_bot = create_bot(bot_name=bot_name, system_prompt=system_prompt, engine_config=engine_config)
            # except ValueError as e:
            #     self.logger.error(f"Error creating bot '{bot_name}' with engine '{engine_type}': {e}", exc_info=True)
            #     QMessageBox.critical(self, self.tr("Error Creating Bot"), self.tr("Could not create bot: {0}").format(str(e)))
            #     return

            if chatroom.add_bot(new_bot):
                self.logger.info(
                    f"Bot '{new_bot}) added to chatroom '{chatroom_name}' successfully.")
                self._update_bot_list(chatroom_name)
                # self._update_bot_response_selector()
            else:
                self.logger.error(
                    f"Failed to add bot '{new_bot}' to chatroom '{chatroom_name}' for an unknown reason after initial checks.")
                QMessageBox.critical(self, self.tr("Error"), self.tr(
                    "Could not add bot. An unexpected error occurred."))
        else:
            self.logger.debug(
                f"Add bot to chatroom '{chatroom_name}' cancelled by user in dialog.")

    def _show_thirdpartyapikey_dialog(self):
        """Displays the API Key Management dialog (`ThirdPartyApiKeyDialog`).

        Before showing the dialog, it checks if the `encryption_service` is
        available and if a master password has been set (via `password_manager`).
        If these prerequisites are not met (which typically shouldn't happen if
        the application startup sequence is correct), it shows an error message.
        Otherwise, it creates and executes an `ThirdPartyApiKeyDialog` instance, passing
        necessary information like available API key slot info and the
        `thirdpartyapikey_manager`.
        """
        if not self.encryption_service or not self.password_manager.has_master_password():
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "Master password not set up or unlocked. Cannot manage API keys."))
            return

        self.logger.debug("Showing API Key Management dialog.")
        dialog = ThirdPartyApiKeyDialog(
            thirdpartyapikey_slot_info_list=self.third_party_group.thirdpartyapikey_slot_info_list,
            thirdpartyapikey_manager=self.thirdpartyapikey_manager,
            parent=self
        )
        dialog.exec()

    def _handle_master_password_startup(self) -> bool:
        """Manages master password creation or entry at application launch.

        If no master password is set, it guides the user through creating one
        using `CreateMasterPasswordDialog`.
        If a master password exists, it prompts the user to enter it using
        `EnterMasterPasswordDialog`. This dialog also handles a "forgot password"
        scenario, which involves clearing all sensitive data.

        This method is critical for application startup. If it returns False,
        the main application window typically will not proceed to full
        initialization and may close.

        Returns:
            bool: True if master password procedures are successfully completed
                  (created, or entered correctly) and `self.encryption_service`
                  is initialized. False if any part of the process is cancelled
                  by the user or fails (e.g., incorrect password entry, failure
                  to set a new password).
        """
        if not self.password_manager.has_master_password():
            self.logger.info(
                "No master password set. Prompting user to create one.")
            create_dialog = CreateMasterPasswordDialog(self)
            if create_dialog.exec():
                password = create_dialog.get_password()
                if not password:  # Should be caught by dialog validation, but as safeguard
                    QMessageBox.critical(self, self.tr("Error"), self.tr(
                        "Failed to create master password."))
                    self.logger.error(
                        "Master password creation dialog accepted but no password returned.")
                    return False
                self.password_manager.set_master_password(password)
                self.encryption_service = EncryptionService(
                    master_password=password)
                self.logger.info(
                    "Master password created and encryption service initialized.")
                return True
            else:
                QMessageBox.information(self, self.tr("Setup Required"),
                                        self.tr("Master password creation was cancelled. The application will close."))
                self.logger.info("Master password creation cancelled by user.")
                return False
        else:  # Master password exists
            self.logger.info(
                "Master password exists. Prompting user to enter it.")
            enter_dialog = EnterMasterPasswordDialog(self)
            if enter_dialog.exec():
                if enter_dialog.clear_data_flag:
                    self.logger.info(
                        "User opted to clear all data from 'Forgot Password' flow.")
                    # Confirmation is already handled in EnterMasterPasswordDialog
                    self._perform_clear_all_data_actions()
                    QMessageBox.information(self, self.tr("Data Cleared"),
                                            self.tr("All API keys and master password have been cleared. Please create a new master password."))
                    # Recursive call to set new password
                    return self._handle_master_password_startup()
                else:
                    password = enter_dialog.get_password()
                    if not password:  # Dialog cancelled or empty password somehow
                        QMessageBox.critical(self, self.tr("Login Failed"),
                                             self.tr("Password entry cancelled. The application will close."))
                        self.logger.warning(
                            "Master password entry dialog accepted but no password returned (or cancelled).")
                        return False

                    if self.password_manager.verify_master_password(password):
                        self.encryption_service = EncryptionService(
                            master_password=password)
                        self.logger.info(
                            "Master password verified and encryption service initialized.")
                        return True
                    else:
                        QMessageBox.critical(self, self.tr("Login Failed"),
                                             self.tr("Invalid master password. The application will close."))
                        self.logger.warning("Invalid master password entered.")
                        return False
            else:  # Dialog was cancelled
                QMessageBox.information(self, self.tr("Login Required"),
                                        self.tr("Master password entry was cancelled. The application will close."))
                self.logger.info("Master password entry cancelled by user.")
                return False
        return False  # Fallback, should ideally be covered by above logic

    def _show_change_master_password_dialog(self):
        """Manages the process of changing the master password.

        This method first checks if a master password is set and the encryption
        service is available. It then shows the `ChangeMasterPasswordDialog`.
        If the user successfully enters their old password and a new password:
        1. Verifies the old master password.
        2. Creates a temporary `EncryptionService` with the old password (for decryption).
        3. Updates the `PasswordManager` with the new password (this also changes the password hash salt).
        4. Updates the main `self.encryption_service` to use the new master password.
        5. Calls `self.thirdpartyapikey_manager.re_encrypt()` to re-encrypt all stored API keys
           using the old and new encryption services.
        6. Updates the `thirdpartyapikey_manager` to use the (now new) `self.encryption_service`.
        Provides feedback to the user on success or failure.
        """
        if not self.password_manager.has_master_password():  # Should not happen if app is running
            QMessageBox.warning(self, self.tr("Error"), self.tr(
                "No master password set. This should not happen."))
            self.logger.error(
                "Change master password dialog called when no master password is set.")
            return
        if not self.encryption_service:  # Also should not happen
            QMessageBox.warning(self, self.tr("Error"), self.tr(
                "Encryption service not available."))
            self.logger.error(
                "Change master password dialog called when encryption service is not available.")
            return

        change_dialog = ChangeMasterPasswordDialog(self)
        if change_dialog.exec():
            passwords = change_dialog.get_passwords()
            if not passwords:  # Dialog was likely cancelled or an issue occurred
                self.logger.info(
                    "Change master password dialog did not return passwords.")
                return

            old_password = passwords["old"]
            new_password = passwords["new"]

            if self.password_manager.verify_master_password(old_password):
                self.logger.info(
                    "Old master password verified. Proceeding with change.")
                # Create a temporary EncryptionService with the old password to decrypt keys
                temp_old_encryption_service = EncryptionService(
                    master_password=old_password)

                # Update the main PasswordManager (changes its salt for password hashing)
                self.password_manager.change_master_password(
                    old_password, new_password)

                # Update the main EncryptionService to use the new password (reuses data encryption salt)
                self.encryption_service.update_master_password(
                    new_master_password=new_password)

                # Re-encrypt all API keys
                if self.thirdpartyapikey_manager:
                    self.thirdpartyapikey_manager.re_encrypt(
                        temp_old_encryption_service, self.encryption_service)
                    # Ensure ThirdPartyApiKeyManager instance uses the updated encryption_service
                    self.thirdpartyapikey_manager.encryption_service = self.encryption_service
                # Also update CcApiKeyManager's encryption service and call its re_encrypt_keys
                if self.ccapikey_manager:
                    self.ccapikey_manager.re_encrypt_keys(temp_old_encryption_service, self.encryption_service)
                    # self.ccapikey_manager.update_encryption_service(self.encryption_service) # re_encrypt_keys does this
                else:
                    self.logger.warning("CcApiKeyManager not initialized during master password change. CC API Keys not processed for re-encryption.")
                else:
                    self.logger.warning(
                        "ThirdPartyApiKeyManager not initialized during master password change. Keys not re-encrypted.")

                QMessageBox.information(self, self.tr("Success"),
                                    self.tr("Master password changed successfully. All relevant API keys have been re-encrypted."))
                self.logger.info(
                    "Master password changed and API keys re-encrypted successfully.")
            else:
                QMessageBox.critical(self, self.tr(
                    "Error"), self.tr("Incorrect old password."))
                self.logger.warning(
                    "Incorrect old password entered during master password change.")
        else:
            self.logger.info("Change master password dialog cancelled.")

    def _perform_clear_all_data_actions(self):
        """Executes the steps to clear all sensitive user data.

        This method is called when the user confirms they want to clear all data,
        typically after forgetting their master password or choosing to reset.
        The actions include:
        - Clearing the master password from `PasswordManager`.
        - Deleting the data encryption salt file (`ENCRYPTION_SALT_FILE`).
        - Calling `clear()` on the `thirdpartyapikey_manager` to remove all stored API keys
          (and its associated salt if any).
        - Setting `self.encryption_service` and the `encryption_service` in
          `self.thirdpartyapikey_manager` to None.
        If `thirdpartyapikey_manager` is not initialized, a temporary one might be created
        to attempt clearing any persistent API key storage.
        """
        self.logger.info("Performing clear all data actions.")
        self.password_manager.clear_master_password()

        # Clear encryption salt file using the imported constant
        if os.path.exists(ENCRYPTION_SALT_FILE):
            try:
                os.remove(ENCRYPTION_SALT_FILE)
                self.logger.info(
                    f"Encryption salt file {ENCRYPTION_SALT_FILE} removed.")
            except OSError as e:
                self.logger.error(
                    f"Error removing encryption salt file {ENCRYPTION_SALT_FILE}: {e}")

        if self.thirdpartyapikey_manager:
            self.thirdpartyapikey_manager.clear()
        else:
            self.logger.info(
                "ThirdPartyApiKeyManager was not initialized during clear data. Skipping its clear.")

        if self.ccapikey_manager:
            self.ccapikey_manager.clear()
            self.manage_cc_keys_action.setEnabled(False) # Disable menu item as manager is cleared
        else:
            self.logger.info("CcApiKeyManager was not initialized during clear data. Skipping its clear.")
            if hasattr(self, 'manage_cc_keys_action'): # Check if it exists before trying to disable
                self.manage_cc_keys_action.setEnabled(False)


        if hasattr(self, 'bot_template_manager') and self.bot_template_manager:
            self.bot_template_manager.clear_all_templates()
            # self.bot_template_manager = None # Optionally nullify, will be recreated if needed

        self.encryption_service = None
        if self.thirdpartyapikey_manager:
            self.thirdpartyapikey_manager.encryption_service = None
        if self.ccapikey_manager: # Also update ccapikey_manager's service ref
            self.ccapikey_manager.encryption_service = None
        # self.thirdpartyapikey_manager = None # Optionally nullify, will be recreated
        # self.ccapikey_manager = None # Optionally nullify

        self.logger.info("All data clearing actions performed.")

    def _clear_all_user_data_via_menu(self):
        """Handles the 'Clear All Stored Data' action from the settings menu.

        Prompts the user for confirmation before proceeding. If confirmed:
        1. Calls `_perform_clear_all_data_actions()` to erase sensitive data.
        2. Informs the user that data has been cleared and a new master password
           needs to be set up.
        3. Calls `_handle_master_password_startup()` to guide the user through
           creating a new master password.
        4. If master password setup fails (e.g., user cancels), the application
           is scheduled to close.
        5. If successful, the `thirdpartyapikey_manager` is re-initialized or updated with
           the new `encryption_service`.
        6. UI elements like chatroom list, message display, and bot list are
           cleared or reset to their initial states.
        """
        self.logger.warning("User initiated 'Clear All Stored Data' action.")
        reply = QMessageBox.question(self, self.tr("Confirm Clear All Data"),
                                     self.tr(
                                         "Are you sure you want to permanently delete all API keys, the master password, and encryption salt? This action cannot be undone."),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.logger.info("User confirmed clearing all data.")
            self._perform_clear_all_data_actions()
            QMessageBox.information(self, self.tr("Data Cleared"),
                                    self.tr("All user data has been cleared. Please create a new master password."))

            # Restart master password setup. If it fails, close the app.
            if not self._handle_master_password_startup():
                QMessageBox.critical(self, self.tr("Setup Required"),
                                     self.tr("Master password setup was cancelled or failed. The application will now close."))
                self.logger.critical(
                    "Master password setup failed after clearing all data. Closing application.")
                QTimer.singleShot(0, self.close)
                return

            # If startup was successful, ThirdPartyApiKeyManager needs to be re-initialized with new encryption service
            if self.thirdpartyapikey_manager:
                self.thirdpartyapikey_manager.encryption_service = self.encryption_service  # Update existing
            else:  # Should be re-created if was None or after full clear
                self.thirdpartyapikey_manager = ThirdPartyApiKeyManager(
                    encryption_service=self.encryption_service)

            # Re-initialize or update CcApiKeyManager
            if self.ccapikey_manager:
                self.ccapikey_manager.encryption_service = self.encryption_service
                self.manage_cc_keys_action.setEnabled(True) # Re-enable
            else:
                self.ccapikey_manager = CcApiKeyManager(
                    data_dir=self.data_dir_path,
                    encryption_service=self.encryption_service
                )
                self.manage_cc_keys_action.setEnabled(True) # Enable

            if hasattr(self, 'bot_template_manager') and self.bot_template_manager:
                # Already done in _perform_clear_all_data_actions, but ensure it's re-initialized if cleared
                pass  # It should be cleared by _perform_clear_all_data_actions

            # If it was cleared or never existed
            if not hasattr(self, 'bot_template_manager') or not self.bot_template_manager:
                self.bot_template_manager = BotTemplateManager(
                    data_dir=self.data_dir_path)  # Re-initialize

            # Potentially refresh UI elements that depend on keys/chatrooms
            self.logger.info(
                "Data cleared and master password setup re-initiated. Refreshing UI.")
            self._update_chatroom_list()  # Will clear messages if no chatroom selected
            self.message_display_area.clear()  # Explicitly clear current messages
            self.bot_list_widget.clear()  # Explicitly clear bot list
            self._update_bot_panel_state(False)
            self._update_message_related_ui_state(False)
            self._update_bot_template_list()  # Refresh template list
        else:
            self.logger.info("User cancelled 'Clear All Stored Data' action.")


    def _show_ccapikey_dialog(self):
        """Displays the CcApiKeyDialog for managing CogniChoir API Keys."""
        if not self.ccapikey_manager:
            # This should ideally not happen if menu item enabling/disabling is correct
            QMessageBox.critical(self, self.tr("Error"),
                                 self.tr("CogniChoir API Key Manager is not available. This may be due to a setup issue."))
            self.logger.error("Attempted to show CcApiKeyDialog, but ccapikey_manager is None.")
            return

        if not self.encryption_service or not self.password_manager.has_master_password():
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "Master password not set up or unlocked. Cannot manage CogniChoir API keys."))
            return

        self.logger.debug("Showing CogniChoir API Key Management dialog.")
        dialog = CcApiKeyDialog(ccapikey_manager=self.ccapikey_manager, parent=self)
        dialog.exec()
        # No specific action needed after close, dialog handles its operations.

    # --- Bot Template Methods ---
    def _update_bot_template_list(self):
        """Refreshes the bot template list widget from the BotTemplateManager."""
        current_selection_id = None
        current_item = self.bot_template_list_widget.currentItem()
        if current_item:
            current_selection_id = current_item.data(Qt.ItemDataRole.UserRole)

        self.bot_template_list_widget.clear()
        templates_with_ids = self.bot_template_manager.list_templates_with_ids()

        for template_id, template_bot in templates_with_ids:
            # Make sure template_bot.name is accessible; if template_bot is a dict, adjust access
            bot_name = template_bot.name if hasattr(
                template_bot, 'name') else "Unnamed Template"
            item_widget = self._create_bot_template_list_item_widget(
                template_id, bot_name)

            list_item = QListWidgetItem(self.bot_template_list_widget)
            list_item.setData(Qt.ItemDataRole.UserRole,
                              template_id)  # Store template_id

            list_item.setSizeHint(item_widget.sizeHint())
            self.bot_template_list_widget.addItem(list_item)
            self.bot_template_list_widget.setItemWidget(list_item, item_widget)

            if template_id == current_selection_id:
                self.bot_template_list_widget.setCurrentItem(list_item)

        self._update_template_button_states()

    def _create_bot_template_list_item_widget(self, template_id: str, template_name: str) -> QWidget:
        """Creates a custom widget for an item in the bot template list."""
        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(5, 2, 5, 2)  # Smaller vertical margins
        item_layout.setSpacing(5)

        name_label = QLabel(template_name)
        name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        item_layout.addWidget(name_label)

        add_to_chat_button = QPushButton("+")
        add_to_chat_button.setFixedSize(25, 25)  # Small square button
        add_to_chat_button.setToolTip(
            self.tr("Add this template to the current chatroom"))
        add_to_chat_button.clicked.connect(
            lambda checked=False, t_id=template_id: self._add_template_to_chatroom(t_id))
        item_layout.addWidget(add_to_chat_button)

        item_widget.setLayout(item_layout)
        return item_widget

    def _show_bot_template_context_menu(self, position: QPoint):
        selected_items = self.bot_template_list_widget.selectedItems()
        if not selected_items:
            return

        # Assuming single selection for now for simplicity
        item = selected_items[0]
        template_id = item.data(Qt.ItemDataRole.UserRole)
        if not template_id:
            return

        menu = QMenu(self)

        edit_action = QAction(self.tr("Edit Template"), self)
        edit_action.triggered.connect(
            lambda: self._edit_selected_bot_template(template_id_override=template_id))
        menu.addAction(edit_action)

        remove_action = QAction(self.tr("Remove Template"), self)
        remove_action.triggered.connect(
            lambda: self._remove_selected_bot_template(template_id_override=template_id))
        menu.addAction(remove_action)

        menu.addSeparator()

        add_to_chat_action = QAction(self.tr("Add to Current Chatroom"), self)
        add_to_chat_action.triggered.connect(
            lambda: self._add_template_to_chatroom(template_id))
        current_chatroom_item = self.chatroom_list_widget.currentItem()
        # Enable only if a chatroom is selected
        add_to_chat_action.setEnabled(bool(current_chatroom_item))
        menu.addAction(add_to_chat_action)

        menu.exec(self.bot_template_list_widget.mapToGlobal(position))

    def _create_bot_template(self):
        self.logger.info("Attempting to create a new bot template.")
        # Pass an empty list for existing_bot_names if template names can be non-unique globally,
        # or manage template name uniqueness if required (e.g., by passing existing template names).
        # For now, let's assume template names don't need to be unique across all templates,
        # as they are identified by IDs. The BotInfoDialog itself might have name validation
        # if it's creating a bot for a specific chatroom, which is not the case here.
        # We will rely on the user to manage meaningful names for templates.

        # Get all existing template names to prevent duplicates if desired at this level
        existing_template_names = [
            t.name for t in self.bot_template_manager.list_templates()]

        dialog = BotInfoDialog(
            # To check for duplicate names among templates
            existing_bot_names=existing_template_names,
            aiengine_info_list=self.third_party_group.aiengine_info_list,
            thirdpartyapikey_query_list=self.thirdpartyapikey_manager.get_available_thirdpartyapikey_query_list(),
            old_bot=None,  # Creating a new template
            parent=self
        )
        dialog.setWindowTitle(self.tr("Create New Bot Template"))

        if dialog.exec():
            new_bot_config = dialog.get_bot()
            if new_bot_config:
                template_id = self.bot_template_manager.create_template(
                    new_bot_config)
                if template_id:
                    self.logger.info(
                        f"Bot template '{new_bot_config.name}' created with ID {template_id}.")
                    self._update_bot_template_list()
                    # Optionally select the new template in the list
                    for i in range(self.bot_template_list_widget.count()):
                        item = self.bot_template_list_widget.item(i)
                        if item.data(Qt.ItemDataRole.UserRole) == template_id:
                            self.bot_template_list_widget.setCurrentItem(item)
                            break
                else:
                    self.logger.error(
                        "Failed to create bot template after dialog confirmation.")
                    QMessageBox.critical(self, self.tr("Error"), self.tr(
                        "Could not save the bot template."))
            else:
                # This case should ideally be handled by dialog's own validation,
                # but as a fallback.
                self.logger.warning(
                    "BotInfoDialog accepted but returned no valid bot configuration for template.")
                QMessageBox.warning(self, self.tr("Error"), self.tr(
                    "Failed to retrieve bot configuration from dialog."))
        else:
            self.logger.info("Bot template creation cancelled by user.")

    def _edit_selected_bot_template(self, template_id_override: str | None = None):
        template_id_to_edit = template_id_override
        if not template_id_to_edit:
            current_item = self.bot_template_list_widget.currentItem()
            if not current_item:
                QMessageBox.warning(self, self.tr("Warning"), self.tr(
                    "No bot template selected to edit."))
                return
            template_id_to_edit = current_item.data(Qt.ItemDataRole.UserRole)

        if not template_id_to_edit:
            self.logger.error("Could not determine template ID for editing.")
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "Cannot identify the template to edit."))
            return

        template_to_edit = self.bot_template_manager.get_template(
            template_id_to_edit)
        if not template_to_edit:
            self.logger.error(
                f"Bot template with ID '{template_id_to_edit}' not found for editing.")
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "Selected bot template not found."))
            self._update_bot_template_list()  # Refresh list if template disappeared
            return

        self.logger.info(
            f"Attempting to edit bot template '{template_to_edit.name}' (ID: {template_id_to_edit}).")

        # Get all existing template names *excluding* the current one for validation
        existing_template_names = [
            t.name for t_id, t in self.bot_template_manager.list_templates_with_ids() if t_id != template_id_to_edit
        ]

        dialog = BotInfoDialog(
            existing_bot_names=existing_template_names,  # For duplicate name check
            aiengine_info_list=self.third_party_group.aiengine_info_list,
            thirdpartyapikey_query_list=self.thirdpartyapikey_manager.get_available_thirdpartyapikey_query_list(),
            old_bot=template_to_edit,  # Pass the existing bot config
            parent=self
        )
        dialog.setWindowTitle(
            self.tr("Edit Bot Template: {0}").format(template_to_edit.name))

        if dialog.exec():
            updated_bot_config = dialog.get_bot()
            if updated_bot_config:
                if self.bot_template_manager.update_template(template_id_to_edit, updated_bot_config):
                    self.logger.info(
                        f"Bot template '{updated_bot_config.name}' (ID: {template_id_to_edit}) updated.")
                    self._update_bot_template_list()
                    # Restore selection
                    for i in range(self.bot_template_list_widget.count()):
                        item = self.bot_template_list_widget.item(i)
                        if item.data(Qt.ItemDataRole.UserRole) == template_id_to_edit:
                            self.bot_template_list_widget.setCurrentItem(item)
                            break
                else:
                    self.logger.error(
                        f"Failed to update bot template '{updated_bot_config.name}' (ID: {template_id_to_edit}).")
                    QMessageBox.critical(self, self.tr("Error"), self.tr(
                        "Could not save the updated bot template."))
            else:
                self.logger.warning(
                    f"BotInfoDialog accepted for edit, but returned no valid bot configuration for template ID {template_id_to_edit}.")
                QMessageBox.warning(self, self.tr("Error"), self.tr(
                    "Failed to retrieve updated bot configuration from dialog."))
        else:
            self.logger.info(
                f"Editing of bot template '{template_to_edit.name}' cancelled by user.")

    def _remove_selected_bot_template(self, template_id_override: str | None = None):
        template_id_to_delete = template_id_override
        if not template_id_to_delete:
            current_item = self.bot_template_list_widget.currentItem()
            if not current_item:
                QMessageBox.warning(self, self.tr("Warning"), self.tr(
                    "No bot template selected to remove."))
                return
            template_id_to_delete = current_item.data(Qt.ItemDataRole.UserRole)

        if not template_id_to_delete:
            self.logger.error("Could not determine template ID for removal.")
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "Cannot identify the template to remove."))
            return

        template_to_delete = self.bot_template_manager.get_template(
            template_id_to_delete)
        if not template_to_delete:
            self.logger.error(
                f"Bot template with ID '{template_id_to_delete}' not found for removal.")
            # It might have been deleted by another action, refresh list
            self._update_bot_template_list()
            QMessageBox.warning(self, self.tr("Warning"), self.tr(
                "Selected bot template could not be found. It may have already been removed."))
            return

        self.logger.info(
            f"Attempting to remove bot template '{template_to_delete.name}' (ID: {template_id_to_delete}).")

        reply = QMessageBox.question(self, self.tr("Confirm Removal"),
                                     self.tr("Are you sure you want to remove the bot template '{0}'?").format(
                                         template_to_delete.name),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            if self.bot_template_manager.delete_template(template_id_to_delete):
                self.logger.info(
                    f"Bot template '{template_to_delete.name}' (ID: {template_id_to_delete}) removed.")
                self._update_bot_template_list()
                # No need to show another success message, list update is enough
            else:
                # This might happen if the template was deleted between the check and now, though unlikely.
                self.logger.error(
                    f"Failed to remove bot template '{template_to_delete.name}' (ID: {template_id_to_delete}) via manager.")
                QMessageBox.critical(self, self.tr("Error"), self.tr(
                    "Could not remove the bot template. It might have been removed by another process."))
                self._update_bot_template_list()  # Refresh list
        else:
            self.logger.info(
                f"Removal of bot template '{template_to_delete.name}' cancelled by user.")

    def _add_template_to_chatroom(self, template_id: str):
        self.logger.info(
            f"Attempting to add bot from template ID '{template_id}' to current chatroom.")

        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr(
                "No chatroom selected to add the bot to."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            self.logger.error(
                f"Selected chatroom '{chatroom_name}' not found.")
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "Selected chatroom not found. Cannot add bot."))
            return

        template_bot_config = self.bot_template_manager.get_template(
            template_id)
        if not template_bot_config:
            self.logger.error(
                f"Bot template with ID '{template_id}' not found.")
            QMessageBox.critical(self, self.tr("Error"), self.tr(
                "Bot template not found. Cannot add bot."))
            self._update_bot_template_list()  # Refresh template list
            return

        # Create a new Bot instance from the template config
        # We need to make a copy to avoid modifying the template itself,
        # especially if we plan to change its name for the chatroom.
        # import copy # Already imported at the top
        new_bot_instance = copy.deepcopy(template_bot_config)

        # Determine a unique name for the bot in the chatroom
        # Option 1: Use template name, append number if duplicate
        # Option 2: Prompt user for a new name
        # For simplicity, let's use Option 1.
        base_name = new_bot_instance.name
        bot_name_in_chatroom = base_name
        suffix = 1
        existing_bot_names_in_chatroom = [
            bot.name for bot in chatroom.list_bots()]
        while bot_name_in_chatroom in existing_bot_names_in_chatroom:
            bot_name_in_chatroom = f"{base_name} ({suffix})"
            suffix += 1
        new_bot_instance.name = bot_name_in_chatroom

        # Potentially, we might need to re-evaluate API key requirements here if they are
        # stored as part of the template and need to be resolved against current thirdpartyapikey_manager.
        # However, BotInfoDialog already associates ThirdPartyApiKeyQuery objects.
        # If the template's thirdpartyapikey_query_list is valid, it should be usable.

        if chatroom.add_bot(new_bot_instance):
            self.logger.info(
                f"Bot '{new_bot_instance.name}' (from template ID '{template_id}') added to chatroom '{chatroom_name}'.")
            # Refresh the bot list for the current chatroom
            self._update_bot_list(chatroom_name)
            QMessageBox.information(self, self.tr("Success"),
                                    self.tr("Bot '{0}' added to chatroom '{1}' from template.").format(new_bot_instance.name, chatroom_name))
        else:
            # This could happen if add_bot has its own validation that fails (e.g. unexpected duplicate after name generation)
            self.logger.error(
                f"Failed to add bot '{new_bot_instance.name}' to chatroom '{chatroom_name}'.")
            QMessageBox.critical(self, self.tr("Error"),
                                 self.tr("Could not add bot '{0}' to the chatroom. It might already exist or an internal error occurred.").format(new_bot_instance.name))

    def _update_template_button_states(self):
        has_selection = bool(self.bot_template_list_widget.currentItem())
        self.edit_template_button.setEnabled(has_selection)
        self.remove_template_button.setEnabled(has_selection)
        # Add other button state updates if needed

    def _on_selected_bot_template_changed(self, _current: QListWidgetItem, _previous: QListWidgetItem):
        self._update_template_button_states()
    # --- End Bot Template Methods ---

    def _start_api_server(self):
        """Initializes dependencies and starts the Flask API server in a separate thread."""
        if not self.ccapikey_manager or not self.encryption_service:
            self.logger.error("Cannot start API server: CcApiKeyManager or EncryptionService not initialized.")
            # Optionally, inform the user via QMessageBox or status bar update
            QMessageBox.critical(self, self.tr("API Server Error"),
                                 self.tr("Could not start the API server due to missing critical components (API Key Manager or Encryption Service). Please check logs or restart."))
            return

        self.logger.info(f"Initializing API server dependencies and starting server on port {self.api_server_port}")
        try:
            api_server.initialize_api_server_dependencies(
                cc_manager=self.ccapikey_manager,
                enc_service=self.encryption_service
            )
        except Exception as e:
            self.logger.error(f"Error initializing API server dependencies: {e}", exc_info=True)
            QMessageBox.critical(self, self.tr("API Server Error"),
                                 self.tr("Failed to initialize API server components. The server will not start. See logs for details."))
            return

        self.api_server_thread = threading.Thread(
            target=api_server.run_server,
            args=(self.api_server_port, False),  # port, debug=False
            daemon=True
        )
        self.api_server_thread.start()
        self.logger.info(f"API server thread started on port {self.api_server_port}.")


    def closeEvent(self, event):
        """
        Handles the window close event.

        This method is called when the user attempts to close the main window.
        It ensures that application settings (like the API server port) are saved
        before the application exits. It also logs the closing action. The API
        server, running as a daemon thread, will terminate automatically when
        the main application exits.

        Args:
            event (QCloseEvent): The close event.
        """
        self._save_settings() # Ensure settings are saved on close
        self.logger.info("Application closing. API server (daemon thread) will terminate automatically.")
        # Any other specific cleanup before closing can be added here.
        super().closeEvent(event)

    def _load_settings(self):
        """
        Loads application settings using QSettings.

        Currently, this method loads the port number for the API server.
        It uses "CcOrg" as the organization name and "CogniChoir" as the
        application name for storing settings, ensuring they are saved in a
        platform-appropriate location. If the "api_server_port" setting is
        not found, it defaults to 5001.
        """
        settings = QSettings("CcOrg", "CogniChoir") # Organization and Application names
        self.api_server_port = settings.value("api_server_port", 5001, type=int)
        self.logger.info(f"Loaded API server port from settings: {self.api_server_port}")

    def _save_settings(self):
        """
        Saves application settings using QSettings.

        Currently, this method saves the port number for the API server
        (`self.api_server_port`). It uses the same organization and application
        names as `_load_settings` for consistency.
        """
        settings = QSettings("CcOrg", "CogniChoir")
        settings.setValue("api_server_port", self.api_server_port)
        self.logger.info(f"Saved API server port to settings: {self.api_server_port}")

    def _show_configure_api_port_dialog(self):
        """
        Displays a dialog to allow the user to configure the API server port.

        Uses `QInputDialog.getInt()` to get a new port number from the user.
        The allowed port range is 1024-65535. If the user changes the port,
        the new port is saved to settings immediately, and the user is informed
        that a restart is required for the change to take effect, as changing
        the port of a running server is complex and not implemented.
        """
        new_port, ok = QInputDialog.getInt(self,
                                           self.tr("Configure API Port"),
                                           self.tr("Enter API Server Port (1024-65535):"),
                                           self.api_server_port,  # Current port value
                                           1024,                 # Minimum allowed port
                                           65535,                # Maximum allowed port
                                           1)                    # Step value for increment/decrement

        if ok: # User clicked OK
            if new_port != self.api_server_port:
                self.api_server_port = new_port
                self.logger.info(f"API server port configuration changed to: {self.api_server_port}")
                self._save_settings() # Save the new port setting immediately
                QMessageBox.information(self,
                                        self.tr("API Port Changed"),
                                        self.tr("The API server port has been updated to {0}.\n"
                                                "Please restart the application for this change to take effect.").format(self.api_server_port))
            else:
                # Port was not changed by the user
                self.logger.debug("API server port configuration dialog shown, but port value was not changed.")
        else:
            # User cancelled the dialog
            self.logger.debug("API server port configuration cancelled by user.")

    def _remove_bot_from_chatroom(self):
        """Removes the selected bot from the current chatroom. (DEPRECATED/UNUSED)

        Note: This method is currently not wired to any UI element directly as
        the 'Remove Bot' button was removed. Bot deletion is typically handled
        by `_delete_selected_bots` via the context menu.

        If it were to be used, it would:
        - Ensure a chatroom and a bot are selected.
        - Prompt for confirmation.
        - Call `chatroom.remove_bot()`.
        - Update the UI.
        """
        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            QMessageBox.warning(self, self.tr("Warning"),
                                self.tr("No chatroom selected."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            # ERROR - prerequisite failed
            self.logger.error(
                f"Remove bot: Selected chatroom '{chatroom_name}' not found.")
            QMessageBox.critical(self, self.tr("Error"),
                                 self.tr("Selected chatroom not found."))
            return

        # This method is no longer needed as the button is removed.
        # Users will need a new way to remove bots (e.g., context menu on bot_list_widget)
        # For now, the functionality is removed as per instructions.


def main():
    """Main entry point for the application.

    Initializes logging, sets up the QApplication, handles internationalization
    by loading translation files, creates and shows the MainWindow, and starts
    the application event loop.
    """
    logging.basicConfig(
        level=logging.DEBUG,  # Changed to DEBUG
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        filename='app.log',
        filemode='w',  # Overwrite log file each time for now, can be changed to 'a' for append
        encoding='utf-8'  # Ensure UTF-8 encoding for log file
    )
    logging.info("Application starting")
    app = QApplication(sys.argv)
    app.setStyleSheet("QWidget { font-size: 12pt; }")

    translator = QTranslator()
    # Try to load system locale, fallback to zh_TW for testing, then to nothing
    locale_name = QLocale.system().name()  # e.g., "en_US", "zh_TW"

    # Construct path to i18n directory relative to this script
    # This assumes i18n is a sibling to the directory containing this script (e.g. src/main/i18n)
    # More robust path handling might be needed depending on project structure
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Corrected path: Assume main_window.py is in src/main/, and i18n is in project_root/i18n/
    # up to src, then up to project_root
    project_root = os.path.dirname(os.path.dirname(current_dir))
    i18n_dir = os.path.join(project_root, "i18n")

    # translation_loaded = False
    # Try specific locale first
    # e.g. app_zh_TW.qm or app_en_US.qm
    if translator.load(locale_name, "app", "_", i18n_dir):
        QApplication.installTranslator(translator)
        # translation_loaded = True
    # Fallback to zh_TW if system locale not found or different
    # Avoid double loading if system is zh_TW
    elif locale_name != "zh_TW" and translator.load("app_zh_TW", i18n_dir):
        QApplication.installTranslator(translator)
        # translation_loaded = True

    # Fallback for Qt's own standard dialog translations (e.g. "Cancel", "OK")
    qt_translator = QTranslator()
    # Try to find Qt's base translations, often in a path like /usr/share/qt6/translations/
    # QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath) is the most reliable way
    qt_translations_path = QLibraryInfo.path(
        QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(QLocale.system(), "qtbase", "_", qt_translations_path):
        QApplication.installTranslator(qt_translator)
    # Try just language e.g. qtbase_en
    elif qt_translator.load("qtbase_" + locale_name.split('_')[0], qt_translations_path):
        QApplication.installTranslator(qt_translator)

    main_window = MainWindow()

    # If running in offscreen mode for testing, don't run the app event loop.
    # Check if __init__ completed enough for basic checks.
    if os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        if hasattr(main_window, 'thirdpartyapikey_manager') and main_window.thirdpartyapikey_manager is not None:
            logging.info(
                "MainWindow initialized successfully in offscreen mode (up to ThirdPartyApiKeyManager).")
            # Test if a master password was created/loaded and encryption service is up
            if main_window.password_manager.has_master_password() and main_window.encryption_service:
                logging.info(
                    "Master password found and encryption service initialized in offscreen mode.")
            else:
                # This will happen if user cancels dialogs, or if it's first run and create dialog is "cancelled" by offscreen mode
                logging.warning(
                    "Master password setup likely did not complete as expected in offscreen mode (dialogs would block).")
            sys.exit(0)  # Exit cleanly for test purposes
        elif hasattr(main_window, 'password_manager') and not hasattr(main_window, 'thirdpartyapikey_manager'):
            # This means __init__ returned early due to password setup failure/cancellation
            logging.warning(
                "MainWindow initialization aborted during password setup (as expected in offscreen mode if dialogs block/are cancelled).")
            # Still a "successful" test of the init-blocking mechanism
            sys.exit(0)
        else:
            logging.error(
                "MainWindow initialization appears incomplete in offscreen mode for unknown reasons.")
            sys.exit(1)  # Exit with error for test purposes
    else:
        # Normal GUI execution
        # Check if __init__ completed. If thirdpartyapikey_manager is None, it means __init__ returned early.
        if hasattr(main_window, 'thirdpartyapikey_manager') and main_window.thirdpartyapikey_manager is not None:
            main_window.show()
            logging.info("Application started successfully.")
            sys.exit(app.exec())
        else:
            logging.warning(
                "MainWindow initialization failed or was aborted (likely password setup). Application will not show.")
            sys.exit(1)  # Exit with an error code


if __name__ == "__main__":
    main()
