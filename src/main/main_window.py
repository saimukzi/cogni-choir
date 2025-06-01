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
import os # For path construction
import logging # For logging
import copy
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QLabel, QInputDialog, QMessageBox,
    QListWidgetItem, QTextEdit,
    QSplitter, QAbstractItemView,
    QMenu, QStyle, QSizePolicy
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QTranslator, QLocale, QLibraryInfo, QPoint, pyqtSignal, QTimer # Added QTimer

# Attempt to import from sibling modules
from .chatroom import ChatroomManager
# from .ai_bots import Bot, create_bot
# from .ai_engines import GeminiEngine, GrokEngine
from .apikey_manager import ApiKeyManager
# from . import ai_engines
from .add_bot_dialog import AddBotDialog
from .create_fake_message_dialog import CreateFakeMessageDialog
from .apikey_dialog import ApiKeyDialog
from .password_manager import PasswordManager
from .encryption_service import EncryptionService, ENCRYPTION_SALT_FILE
from .password_dialogs import CreateMasterPasswordDialog, EnterMasterPasswordDialog, ChangeMasterPasswordDialog
from . import third_parties
from . import third_party


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
        ApiKeyManager, ChatroomManager, and the main user interface.
        If master password setup fails or is cancelled, the application
        initialization is halted, and the window is scheduled to close.
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle(self.tr("Chatroom and Bot Manager"))
        self.setGeometry(100, 100, 800, 600)

        self.third_party_group = third_party.ThirdPartyGroup(third_parties.THIRD_PARTY_CLASSES)

        self.password_manager = PasswordManager()
        self.encryption_service = None
        self.apikey_manager = None # Initialized after password setup


        if not self._handle_master_password_startup():
            self.logger.warning("Master password setup failed or was cancelled. Closing application.")
            # If running in a context where QApplication is already running, self.close() is preferred.
            # If this is very early startup, sys.exit() might be needed.
            # For now, assume self.close() is sufficient if called before app.exec().
            # A more robust way might involve a flag that main() checks after __init__ returns.
            QTimer.singleShot(0, self.close) # Close after current event loop processing
            return # Stop further initialization in __init__

        # Initialize ApiKeyManager now that encryption_service is available
        self.apikey_manager = ApiKeyManager(encryption_service=self.encryption_service)
        self.chatroom_manager = ChatroomManager(apikey_manager=self.apikey_manager)

        self._init_ui()
        self._update_chatroom_list() # Initial population

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
        manage_keys_action = QAction(self.tr("Manage API Keys"), self)
        manage_keys_action.triggered.connect(self._show_apikey_dialog)
        settings_menu.addAction(manage_keys_action)

        change_mp_action = QAction(self.tr("Change Master Password"), self)
        change_mp_action.triggered.connect(self._show_change_master_password_dialog)
        settings_menu.addAction(change_mp_action)

        clear_all_data_action = QAction(self.tr("Clear All Stored Data..."), self)
        clear_all_data_action.triggered.connect(self._clear_all_user_data_via_menu)
        settings_menu.addAction(clear_all_data_action)

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
        self.message_display_area.setWordWrap(True) # Enable word wrap
        self.message_display_area.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.message_display_area.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.message_display_area.customContextMenuRequested.connect(self._show_message_context_menu)
        right_panel_layout.addWidget(self.message_display_area, 5)

        # Message Actions Layout (for delete and fake message buttons)
        message_actions_layout = QHBoxLayout()
        # self.delete_message_button = QPushButton(self.tr("Delete Selected Message(s)"))
        # self.delete_message_button.clicked.connect(self._delete_selected_messages)
        # message_actions_layout.addWidget(self.delete_message_button)

        self.create_fake_message_button = QPushButton(self.tr("Create Fake Message"))
        self.create_fake_message_button.clicked.connect(self._show_create_fake_message_dialog)
        message_actions_layout.addWidget(self.create_fake_message_button)
        right_panel_layout.addLayout(message_actions_layout)


        # Message Input Area
        message_input_layout = QHBoxLayout()
        # self.message_input_area = QLineEdit()
        self.message_input_area = MessageInputTextEdit() # Changed to custom QTextEdit for Ctrl+Enter
        self.message_input_area.setMinimumHeight(60) # Set a minimum height for better usability
        self.message_input_area.ctrl_enter_pressed.connect(self._send_user_message)
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
            self.bot_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.bot_list_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus) # Allow focus for keyboard navigation
        else:
            self.bot_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
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
        """Refreshes the message display area with messages from the current chatroom.

        Clears the `message_display_area` and repopulates it with messages
        from the currently selected chatroom in `chatroom_list_widget`.
        Messages are retrieved from the `Chatroom` object and sorted by
        timestamp before display. Each list item stores the message's
        timestamp for potential use in other operations like deletion.
        If no chatroom is selected, the display area is simply cleared.
        """
        current_chatroom_name = self.chatroom_list_widget.currentItem().text() if self.chatroom_list_widget.currentItem() else None
        self.message_display_area.clear()
        if current_chatroom_name:
            chatroom = self.chatroom_manager.get_chatroom(current_chatroom_name)
            if chatroom:
                # Ensure sorted display by timestamp
                for message in sorted(chatroom.get_messages(), key=lambda m: m.timestamp):
                    item = QListWidgetItem(message.to_display_string()+'\n') # Use to_display_string for formatting
                    item.setData(Qt.ItemDataRole.UserRole, message.timestamp) # Store timestamp
                    self.message_display_area.addItem(item)

    def _delete_selected_messages(self):
        """Deletes selected messages from the current chatroom's history.

        Retrieves the currently selected chatroom and the selected messages
        from `message_display_area`. After confirming with the user, it
        iterates through the selected messages, using their stored timestamps
        to delete them from the `Chatroom` object via `chatroom.delete_message()`.
        Finally, it refreshes the message display.
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
        """Opens a dialog to manually create and add a "fake" message.

        This method is typically used for testing or development purposes.
        It ensures a chatroom is selected, then displays the
        `CreateFakeMessageDialog`. If the dialog is accepted and returns
        valid sender and content, the message is added to the current
        chatroom's history, and the message display is updated.
        """
        current_chatroom_name = self.chatroom_list_widget.currentItem().text() if self.chatroom_list_widget.currentItem() else None
        if not current_chatroom_name:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected."))
            return

        chatroom = self.chatroom_manager.get_chatroom(current_chatroom_name)
        if not chatroom:
            return # Should not happen

        current_bot_names = [bot.name for bot in chatroom.list_bots()]
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
        """Sends a message from the user to the current chatroom.

        Retrieves the text from the `message_input_area`. If a chatroom
        is selected and the message text is not empty, it adds the message
        to the `Chatroom` object with "User" as the sender.
        The message display is then updated, and the input area is cleared.
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

        # text = self.message_input_area.text().strip()
        text = self.message_input_area.toPlainText().strip() # Use QTextEdit for multi-line input
        if not text:
            return

        self.logger.info(f"Sending user message of length {len(text)} to chatroom '{chatroom_name}'.")
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
        with the bot's configuration, API keys (retrieved via `apikey_manager`),
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
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom:
            self.logger.error(f"Trigger bot response: Selected chatroom '{chatroom_name}' not found.")
            QMessageBox.critical(self, self.tr("Error"), self.tr("Selected chatroom not found."))
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
            self.logger.error(f"Trigger bot response: Bot '{selected_bot_name_to_use}' not found in chatroom '{chatroom_name}'.")
            QMessageBox.critical(self, self.tr("Error"), self.tr("Bot '{0}' not found in chatroom.").format(selected_bot_name_to_use))
            return


        # if isinstance(engine, (GeminiEngine, GrokEngine)):
        #     apikey = self.apikey_manager.load_key(engine_type_name)
        #     if not apikey:
        #         self.logger.warning(f"Trigger bot response: API key missing for bot '{bot.get_name()}' using engine '{engine_type_name}'.")
        #         QMessageBox.warning(self, self.tr("API Key Missing"),
        #                             self.tr("Bot {0} (using {1}) needs an API key. Please set it in Settings.").format(bot.get_name(), engine_type_name))
        #         return

        self.logger.info(f"Attempting to trigger bot response for bot '{selected_bot_name_to_use}' in chatroom '{chatroom_name}'.")
        conversation_history = chatroom.get_messages()

        if not conversation_history:
            self.logger.info(f"Trigger bot response: No messages in chatroom '{chatroom_name}' to respond to for bot '{selected_bot_name_to_use}'.")
            QMessageBox.information(self, self.tr("Info"), self.tr("No messages in chat to respond to."))
            return

        # UI updates to indicate processing, only for the main button
        # original_button_text = None
        is_main_button_trigger = not bot_name_override # True if triggered by the main UI button
        if is_main_button_trigger:
            # original_button_text = self.trigger_bot_response_button.text()
            # self.trigger_bot_response_button.setText(self.tr("Waiting for AI..."))
            # self.trigger_bot_response_button.setEnabled(False)
            QApplication.processEvents()

        try:
            ai_response = self.third_party_group.generate_response(
                aiengine_id = bot.aiengine_id,
                aiengine_arg_dict = bot.aiengine_arg_dict,
                apikey_list = self.apikey_manager.get_apikey_list(bot.apikey_query_list),
                role_name = bot.name,
                conversation_history = conversation_history,
            )
            self.logger.info(f"Bot '{selected_bot_name_to_use}' generated response successfully in chatroom '{chatroom_name}'.")
            chatroom.add_message(bot.name, ai_response)
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
            # if is_main_button_trigger and original_button_text is not None:
            #     self.trigger_bot_response_button.setText(original_button_text)
            # The message related UI state should be updated regardless of which button triggered
            self._update_message_related_ui_state(bool(self.chatroom_list_widget.currentItem()))


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
        elif name: # Name was provided but 'ok' was false (dialog cancelled) or name was empty after ok.
            self.logger.debug(f"Chatroom creation cancelled or name was invalid: '{name}'.")
        else: # 'ok' was false and name was empty (dialog cancelled with no input).
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
        elif not ok: # User cancelled the dialog
            self.logger.debug(f"Chatroom rename for '{old_name}' cancelled by user.")


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
                    bot_name_str = bot.name # Ensure it's a string
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
        # current_name = bot_to_edit.name
        # current_engine_instance = bot_to_edit.get_engine()
        # current_engine_type = type(current_engine_instance).__name__
        # current_model_name = getattr(current_engine_instance, 'model_name', None) # Handle if no model_name
        # current_system_prompt = bot_to_edit.get_system_prompt()

        all_bot_names_in_chatroom = [bot.name for bot in chatroom.list_bots()]
        existing_bot_names_for_dialog = [name for name in all_bot_names_in_chatroom if name != bot_to_edit.name]

        dialog = AddBotDialog(
            existing_bot_names=existing_bot_names_for_dialog,
            aiengine_info_list=self.third_party_group.aiengine_info_list,
            apikey_query_list=self.apikey_manager.get_available_apikey_query_list(),
            parent=self
        )
        dialog.setWindowTitle(self.tr("Edit Bot: {0}").format(bot_to_edit.name))

        # Pre-fill dialog fields
        dialog.bot_name_input.setText(bot_to_edit.name)
        dialog.engine_combo.setCurrentText(bot_to_edit.aiengine_id)
        # if current_model_name:
        dialog.model_name_input.setText(bot_to_edit.get_aiengine_arg('model_name',''))
        dialog.system_prompt_input.setPlainText(bot_to_edit.get_aiengine_arg('system_prompt',''))

        if dialog.exec():
            new_bot = dialog.get_bot()
            if not new_bot: # Should not happen if dialog accept() worked
                return

            # name_changed = (new_bot.name != bot_to_edit.name)
            # engine_changed = (new_bot.aiengine_id != bot_to_edit.aiengine_id or \
            #                   new_bot.get_aiengine_arg('model_name') !=new_bot.get_aiengine_arg('model_name'))
            #                   # Ensure empty new_model_name matches None current_model_name

            if not chatroom.remove_bot(bot_to_edit.name): # Use current_name for removal
                self.logger.error(f"Failed to remove bot '{bot_to_edit.name}' before renaming.")
                return

            # if engine_changed:
            #     self.logger.debug(f"Engine change detected for bot '{new_name}'. Old: {current_engine_type}, New: {new_engine_type}")
            #     apikey = self.apikey_manager.load_key(new_engine_type)

            #     try:
            #         engine_class = ai_engines.ENGINE_TYPE_TO_CLASS_MAP.get(new_engine_type)
            #         if not engine_class:
            #             raise ValueError(f"Unsupported engine type: {new_engine_type}")

            #         new_engine_instance = engine_class(apikey=apikey, model_name=new_model_name if new_model_name else None)
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
                self.logger.error(f"Failed to re-add bot '{new_bot.name}' after name change.")
                QMessageBox.critical(self, self.tr("Error Updating Bot"), self.tr("Could not re-add bot with new name. Bot may be in an inconsistent state."))
                return

            self.logger.info(f"Bot '{bot_to_edit.name}' updated successfully. New name: '{new_bot.name}'")

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
        # existing_bot_names_in_chatroom = [bot.get_name() for bot in chatroom.list_bots()]

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
            # apikey = self.apikey_manager.load_key(original_engine_type) # API key might be None

            # engine_config = {
            #     "engine_type": original_engine_type,
            #     "apikey": apikey, # Pass along, could be None
            #     "model_name": original_model_name
            # }

            # try:
            #     cloned_bot = create_bot(bot_name=clone_name, system_prompt=original_system_prompt, engine_config=engine_config)
            # except ValueError as e:
            #     self.logger.error(f"Error creating cloned bot '{clone_name}': {e}", exc_info=True)
            #     QMessageBox.warning(self, self.tr("Clone Error"), self.tr("Could not create clone for bot '{0}': {1}").format(original_bot_name, str(e)))
            #     continue
            cloned_bot = copy.deepcopy(original_bot)
            cloned_bot.name = clone_name # Set the new name

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
            # self._update_bot_response_selector()
            # chatroom.add_bot should call _notify_chatroom_updated, so an explicit call here might be redundant
            # but ensures saving if multiple bots are added in a loop and add_bot is not immediately saving.
            self.chatroom_manager.notify_chatroom_updated(chatroom)

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
            # self._update_bot_response_selector()
            # Chatroom.remove_bot is expected to call _notify_chatroom_updated.
            # If it doesn't, an explicit call here would be:
            # self.chatroom_manager._notify_chatroom_updated(chatroom)
            QMessageBox.information(self, self.tr("Deletion Successful"), self.tr("{0} bot(s) deleted successfully.").format(deleted_count))
        elif selected_items: # Attempted deletion but nothing was actually deleted
            QMessageBox.warning(self, self.tr("Deletion Failed"), self.tr("No bots were deleted. They may have already been removed or an error occurred."))


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
        """Initiates adding a new bot to the currently selected chatroom.

        Ensures a chatroom is selected. Then, it opens an `AddBotDialog`,
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
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected to add a bot to."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom: # Should not happen if item is selected
            QMessageBox.critical(self, self.tr("Error"), self.tr("Selected chatroom not found."))
            return

        existing_bot_names_in_chatroom = [bot.name for bot in chatroom.list_bots()]
        dialog = AddBotDialog(
            existing_bot_names=existing_bot_names_in_chatroom,
            aiengine_info_list=self.third_party_group.aiengine_info_list,
            apikey_query_list=self.apikey_manager.get_available_apikey_query_list(),
            parent=self
        )

        if dialog.exec(): # This now uses the overridden accept method for validation
            # data = dialog.get_data()
            new_bot = dialog.get_bot() # This will return None if validation fails
            if not new_bot: # Safeguard, should not happen if accept validation passed
                return

            # Bot name validation (emptiness, duplication) is now handled within AddBotDialog.accept()
            # bot_name = data["bot_name"] # Already stripped in dialog's get_data or accept
            # engine_type = data["engine_type"]
            # model_name = data["model_name"] # Already stripped
            # system_prompt = data["system_prompt"]
            # Validation for bot_name (empty, duplicate) is now done in AddBotDialog.accept()

            # Check if the selected engine type requires an API key by looking at the class constructor
            # This check is illustrative; a more robust check might involve inspecting constructor parameters
            # or having a metadata attribute in engine classes.
            # engine_class = ai_engines.ENGINE_TYPE_TO_CLASS_MAP.get(engine_type)

            # new_bot_aiengine_id = new_bot.aiengine_id
            # new_bot_apikey_slot_id_list = self.third_party_group.aiengine_id_to_aiengine_info_dict[new_bot_aiengine_id].apikey_slot_id_list

            # apikey_exist = any(map(lambda apikey_slot_id: self.apikey_manager.has_key(apikey_slot_id), new_bot_apikey_slot_id_list))

            # apikey = self.apikey_manager.load_key(engine_type)

            # engine_config = {"engine_type": engine_type, "apikey": apikey if apikey else None}
            # if model_name:
            #     engine_config["model_name"] = model_name

            # try:
            #     new_bot = create_bot(bot_name=bot_name, system_prompt=system_prompt, engine_config=engine_config)
            # except ValueError as e:
            #     self.logger.error(f"Error creating bot '{bot_name}' with engine '{engine_type}': {e}", exc_info=True)
            #     QMessageBox.critical(self, self.tr("Error Creating Bot"), self.tr("Could not create bot: {0}").format(str(e)))
            #     return

            if chatroom.add_bot(new_bot):
                self.logger.info(f"Bot '{new_bot}) added to chatroom '{chatroom_name}' successfully.")
                self._update_bot_list(chatroom_name)
                # self._update_bot_response_selector()
            else:
                self.logger.error(f"Failed to add bot '{new_bot}' to chatroom '{chatroom_name}' for an unknown reason after initial checks.")
                QMessageBox.critical(self, self.tr("Error"), self.tr("Could not add bot. An unexpected error occurred."))
        else:
            self.logger.debug(f"Add bot to chatroom '{chatroom_name}' cancelled by user in dialog.")


    def _show_apikey_dialog(self):
        """Displays the API Key Management dialog (`ApiKeyDialog`).

        Before showing the dialog, it checks if the `encryption_service` is
        available and if a master password has been set (via `password_manager`).
        If these prerequisites are not met (which typically shouldn't happen if
        the application startup sequence is correct), it shows an error message.
        Otherwise, it creates and executes an `ApiKeyDialog` instance, passing
        necessary information like available API key slot info and the
        `apikey_manager`.
        """
        if not self.encryption_service or not self.password_manager.has_master_password():
            QMessageBox.critical(self, self.tr("Error"), self.tr("Master password not set up or unlocked. Cannot manage API keys."))
            return

        self.logger.debug("Showing API Key Management dialog.")
        dialog = ApiKeyDialog(
            apikey_slot_info_list=self.third_party_group.apikey_slot_info_list,
            apikey_manager=self.apikey_manager,
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
            self.logger.info("No master password set. Prompting user to create one.")
            create_dialog = CreateMasterPasswordDialog(self)
            if create_dialog.exec():
                password = create_dialog.get_password()
                if not password: # Should be caught by dialog validation, but as safeguard
                    QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to create master password."))
                    self.logger.error("Master password creation dialog accepted but no password returned.")
                    return False
                self.password_manager.set_master_password(password)
                self.encryption_service = EncryptionService(master_password=password)
                self.logger.info("Master password created and encryption service initialized.")
                return True
            else:
                QMessageBox.information(self, self.tr("Setup Required"),
                                        self.tr("Master password creation was cancelled. The application will close."))
                self.logger.info("Master password creation cancelled by user.")
                return False
        else: # Master password exists
            self.logger.info("Master password exists. Prompting user to enter it.")
            enter_dialog = EnterMasterPasswordDialog(self)
            if enter_dialog.exec():
                if enter_dialog.clear_data_flag:
                    self.logger.info("User opted to clear all data from 'Forgot Password' flow.")
                    # Confirmation is already handled in EnterMasterPasswordDialog
                    self._perform_clear_all_data_actions()
                    QMessageBox.information(self, self.tr("Data Cleared"),
                                            self.tr("All API keys and master password have been cleared. Please create a new master password."))
                    return self._handle_master_password_startup() # Recursive call to set new password
                else:
                    password = enter_dialog.get_password()
                    if not password: # Dialog cancelled or empty password somehow
                        QMessageBox.critical(self, self.tr("Login Failed"),
                                             self.tr("Password entry cancelled. The application will close."))
                        self.logger.warning("Master password entry dialog accepted but no password returned (or cancelled).")
                        return False

                    if self.password_manager.verify_master_password(password):
                        self.encryption_service = EncryptionService(master_password=password)
                        self.logger.info("Master password verified and encryption service initialized.")
                        return True
                    else:
                        QMessageBox.critical(self, self.tr("Login Failed"),
                                             self.tr("Invalid master password. The application will close."))
                        self.logger.warning("Invalid master password entered.")
                        return False
            else: # Dialog was cancelled
                QMessageBox.information(self, self.tr("Login Required"),
                                        self.tr("Master password entry was cancelled. The application will close."))
                self.logger.info("Master password entry cancelled by user.")
                return False
        return False # Fallback, should ideally be covered by above logic

    def _show_change_master_password_dialog(self):
        """Manages the process of changing the master password.

        This method first checks if a master password is set and the encryption
        service is available. It then shows the `ChangeMasterPasswordDialog`.
        If the user successfully enters their old password and a new password:
        1. Verifies the old master password.
        2. Creates a temporary `EncryptionService` with the old password (for decryption).
        3. Updates the `PasswordManager` with the new password (this also changes the password hash salt).
        4. Updates the main `self.encryption_service` to use the new master password.
        5. Calls `self.apikey_manager.re_encrypt()` to re-encrypt all stored API keys
           using the old and new encryption services.
        6. Updates the `apikey_manager` to use the (now new) `self.encryption_service`.
        Provides feedback to the user on success or failure.
        """
        if not self.password_manager.has_master_password(): # Should not happen if app is running
            QMessageBox.warning(self, self.tr("Error"), self.tr("No master password set. This should not happen."))
            self.logger.error("Change master password dialog called when no master password is set.")
            return
        if not self.encryption_service: # Also should not happen
            QMessageBox.warning(self, self.tr("Error"), self.tr("Encryption service not available."))
            self.logger.error("Change master password dialog called when encryption service is not available.")
            return

        change_dialog = ChangeMasterPasswordDialog(self)
        if change_dialog.exec():
            passwords = change_dialog.get_passwords()
            if not passwords: # Dialog was likely cancelled or an issue occurred
                self.logger.info("Change master password dialog did not return passwords.")
                return

            old_password = passwords["old"]
            new_password = passwords["new"]

            if self.password_manager.verify_master_password(old_password):
                self.logger.info("Old master password verified. Proceeding with change.")
                # Create a temporary EncryptionService with the old password to decrypt keys
                temp_old_encryption_service = EncryptionService(master_password=old_password)

                # Update the main PasswordManager (changes its salt for password hashing)
                self.password_manager.change_master_password(old_password, new_password)

                # Update the main EncryptionService to use the new password (reuses data encryption salt)
                self.encryption_service.update_master_password(new_master_password=new_password)

                # Re-encrypt all API keys
                if self.apikey_manager:
                    self.apikey_manager.re_encrypt(temp_old_encryption_service, self.encryption_service)
                    # Ensure ApiKeyManager instance uses the updated encryption_service
                    self.apikey_manager.encryption_service = self.encryption_service
                else:
                    self.logger.warning("ApiKeyManager not initialized during master password change. Keys not re-encrypted.")

                QMessageBox.information(self, self.tr("Success"),
                                        self.tr("Master password changed successfully. API keys have been re-encrypted."))
                self.logger.info("Master password changed and API keys re-encrypted successfully.")
            else:
                QMessageBox.critical(self, self.tr("Error"), self.tr("Incorrect old password."))
                self.logger.warning("Incorrect old password entered during master password change.")
        else:
            self.logger.info("Change master password dialog cancelled.")

    def _perform_clear_all_data_actions(self):
        """Executes the steps to clear all sensitive user data.

        This method is called when the user confirms they want to clear all data,
        typically after forgetting their master password or choosing to reset.
        The actions include:
        - Clearing the master password from `PasswordManager`.
        - Deleting the data encryption salt file (`ENCRYPTION_SALT_FILE`).
        - Calling `clear()` on the `apikey_manager` to remove all stored API keys
          (and its associated salt if any).
        - Setting `self.encryption_service` and the `encryption_service` in
          `self.apikey_manager` to None.
        If `apikey_manager` is not initialized, a temporary one might be created
        to attempt clearing any persistent API key storage.
        """
        self.logger.info("Performing clear all data actions.")
        self.password_manager.clear_master_password()

        # Clear encryption salt file using the imported constant
        if os.path.exists(ENCRYPTION_SALT_FILE):
            try:
                os.remove(ENCRYPTION_SALT_FILE)
                self.logger.info(f"Encryption salt file {ENCRYPTION_SALT_FILE} removed.")
            except OSError as e:
                self.logger.error(f"Error removing encryption salt file {ENCRYPTION_SALT_FILE}: {e}")

        if self.apikey_manager:
            self.apikey_manager.clear()
        else:
            self.logger.info("ApiKeyManager was not initialized, creating temporary one to clear potential fallback file.")
            temp_manager = ApiKeyManager(encryption_service=None)
            temp_manager.clear()

        self.encryption_service = None
        if self.apikey_manager:
            self.apikey_manager.encryption_service = None

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
        5. If successful, the `apikey_manager` is re-initialized or updated with
           the new `encryption_service`.
        6. UI elements like chatroom list, message display, and bot list are
           cleared or reset to their initial states.
        """
        self.logger.warning("User initiated 'Clear All Stored Data' action.")
        reply = QMessageBox.question(self, self.tr("Confirm Clear All Data"),
                                     self.tr("Are you sure you want to permanently delete all API keys, the master password, and encryption salt? This action cannot be undone."),
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
                self.logger.critical("Master password setup failed after clearing all data. Closing application.")
                QTimer.singleShot(0, self.close)
                return

            # If startup was successful, ApiKeyManager needs to be re-initialized with new encryption service
            if self.apikey_manager:
                self.apikey_manager.encryption_service = self.encryption_service # Update existing
            else: # Should be re-created if was None or after full clear
                self.apikey_manager = ApiKeyManager(encryption_service=self.encryption_service)

            # Potentially refresh UI elements that depend on keys/chatrooms
            self.logger.info("Data cleared and master password setup re-initiated. Refreshing UI.")
            self._update_chatroom_list() # Will clear messages if no chatroom selected
            self.message_display_area.clear() # Explicitly clear current messages
            self.bot_list_widget.clear() # Explicitly clear bot list
            self._update_bot_panel_state(False)
            self._update_message_related_ui_state(False)
        else:
            self.logger.info("User cancelled 'Clear All Stored Data' action.")

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
    app.setStyleSheet("QWidget { font-size: 12pt; }")

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

    # translation_loaded = False
    # Try specific locale first
    if translator.load(locale_name, "app", "_", i18n_dir): # e.g. app_zh_TW.qm or app_en_US.qm
        QApplication.installTranslator(translator)
        # translation_loaded = True
    # Fallback to zh_TW if system locale not found or different
    elif locale_name != "zh_TW" and translator.load("app_zh_TW", i18n_dir): # Avoid double loading if system is zh_TW
        QApplication.installTranslator(translator)
        # translation_loaded = True

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

    # If running in offscreen mode for testing, don't run the app event loop.
    # Check if __init__ completed enough for basic checks.
    if os.environ.get('QT_QPA_PLATFORM') == 'offscreen':
        if hasattr(main_window, 'apikey_manager') and main_window.apikey_manager is not None:
            logging.info("MainWindow initialized successfully in offscreen mode (up to ApiKeyManager).")
            # Test if a master password was created/loaded and encryption service is up
            if main_window.password_manager.has_master_password() and main_window.encryption_service:
                logging.info("Master password found and encryption service initialized in offscreen mode.")
            else:
                 # This will happen if user cancels dialogs, or if it's first run and create dialog is "cancelled" by offscreen mode
                logging.warning("Master password setup likely did not complete as expected in offscreen mode (dialogs would block).")
            sys.exit(0) # Exit cleanly for test purposes
        elif hasattr(main_window, 'password_manager') and not hasattr(main_window, 'apikey_manager'):
            # This means __init__ returned early due to password setup failure/cancellation
            logging.warning("MainWindow initialization aborted during password setup (as expected in offscreen mode if dialogs block/are cancelled).")
            sys.exit(0) # Still a "successful" test of the init-blocking mechanism
        else:
            logging.error("MainWindow initialization appears incomplete in offscreen mode for unknown reasons.")
            sys.exit(1) # Exit with error for test purposes
    else:
        # Normal GUI execution
        # Check if __init__ completed. If apikey_manager is None, it means __init__ returned early.
        if hasattr(main_window, 'apikey_manager') and main_window.apikey_manager is not None :
            main_window.show()
            logging.info("Application started successfully.")
            sys.exit(app.exec())
        else:
            logging.warning("MainWindow initialization failed or was aborted (likely password setup). Application will not show.")
            sys.exit(1) # Exit with an error code

if __name__ == "__main__":
    main()
