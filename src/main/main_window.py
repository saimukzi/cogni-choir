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
    from .ai_bots import Bot, AIEngine # AIEngine and Bot remain in ai_bots
    from .ai_engines import GeminiEngine, GrokEngine, OpenAIEngine # Engines from new package
    from .api_key_manager import ApiKeyManager
    from .message import Message
except ImportError:
    # Fallback for running script directly for testing
    from chatroom import Chatroom, ChatroomManager
    from ai_bots import Bot, AIEngine # AIEngine and Bot remain in ai_bots
    from ai_engines import GeminiEngine, GrokEngine, OpenAIEngine # Engines from new package
    from api_key_manager import ApiKeyManager
    from message import Message


class ApiKeyDialog(QDialog):
    def __init__(self, api_key_manager: ApiKeyManager, parent=None):
        super().__init__(parent)
        self.api_key_manager = api_key_manager
        self.setWindowTitle(self.tr("API Key Management"))
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.service_combo = QComboBox()
        self.service_combo.addItems(["OpenAI", "Gemini", "Grok"]) # Service names should match what ApiKeyManager expects
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
        selected_service = self.service_combo.currentText()
        if selected_service: # Ensure a service is actually selected
            key = self.api_key_manager.load_key(selected_service)
            self.api_key_input.setText(key if key else "")
        else:
            self.api_key_input.clear()


    def _save_key(self):
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
    def __init__(self, current_bots: list[str], parent=None):
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
        if self.result() == QDialog.DialogCode.Accepted:
            return self.sender_combo.currentText(), self.content_input.toPlainText()
        return None
    
    # Using QApplication.translate for robustness, especially if this dialog moves to another file.
    def tr(self, text, disambiguation=None, n=-1):
        return QApplication.translate("CreateFakeMessageDialog", text, disambiguation, n)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle(self.tr("Chatroom and Bot Manager"))
        self.setGeometry(100, 100, 800, 600)

        self.api_key_manager = ApiKeyManager()
        self.chatroom_manager = ChatroomManager(api_key_manager=self.api_key_manager)

        self._init_ui()
        self._update_chatroom_list() # Initial population

    def _init_ui(self):
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
        """Enable/disable message input, send button, bot selector, and trigger button."""
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
        menu = QMenu()
        if self.message_display_area.selectedItems():
            delete_action = menu.addAction(self.tr("Delete Message(s)"))
            delete_action.triggered.connect(self._delete_selected_messages)
        menu.exec(self.message_display_area.mapToGlobal(position))


    def _update_bot_panel_state(self, enabled: bool, chatroom_name: str | None = None):
        """Updates the enabled state of the bot panel and its label."""
        self.bot_list_widget.setEnabled(enabled)
        self.add_bot_button.setEnabled(enabled)
        self.remove_bot_button.setEnabled(enabled and bool(self.bot_list_widget.currentItem()))
        
        if enabled and chatroom_name:
            self.bot_panel_label.setText(self.tr("Bots in '{0}'").format(chatroom_name))
        elif not enabled and self.chatroom_list_widget.currentItem() is None : # No chatroom selected
             self.bot_panel_label.setText(self.tr("Bots (No Chatroom Selected)"))
        # else: Keep current label if chatroom selected but panel is being disabled for other reasons

    def _update_chatroom_related_button_states(self):
        has_selection = bool(self.chatroom_list_widget.currentItem())
        self.rename_chatroom_button.setEnabled(has_selection)
        self.clone_chatroom_button.setEnabled(has_selection)
        self.delete_chatroom_button.setEnabled(has_selection)


    def _update_chatroom_list(self):
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
        engine_type_name = type(engine).__name__.replace("Engine", "") 
        
        if isinstance(engine, (GeminiEngine, GrokEngine, OpenAIEngine)): 
            api_key = self.api_key_manager.load_key(engine_type_name)
            if not api_key:
                self.logger.warning(f"Trigger bot response: API key missing for bot '{bot.get_name()}' using engine '{engine_type_name}'.")
                QMessageBox.warning(self, self.tr("API Key Missing"), 
                                    self.tr("Bot {0} (using {1}) needs an API key. Please set it in Settings.").format(bot.get_name(), engine_type_name))
                return
        
        self.logger.info(f"Attempting to trigger bot response for bot '{selected_bot_name}' in chatroom '{chatroom_name}'.")
        conversation_history_tuples = [(msg.sender, msg.content) for msg in chatroom.get_messages()]
        current_user_prompt = ""
        history_for_ai = []

        if not conversation_history_tuples:
            self.logger.info(f"Trigger bot response: No messages in chatroom '{chatroom_name}' to respond to.")
            QMessageBox.information(self, self.tr("Info"), self.tr("No messages in chat to respond to."))
            return 
        
        if conversation_history_tuples[-1][0] == "User":
            current_user_prompt = conversation_history_tuples[-1][1]
            history_for_ai = conversation_history_tuples[:-1]
        else:
            history_for_ai = conversation_history_tuples
            current_user_prompt = bot.get_system_prompt() or "Continue the conversation." 

        if not current_user_prompt and not history_for_ai: # Should be 'or' not 'and'
             self.logger.warning(f"Trigger bot response: Cannot send an empty prompt to bot '{selected_bot_name}' in chatroom '{chatroom_name}'.")
             QMessageBox.warning(self, self.tr("Warning"), self.tr("Cannot send an empty prompt to the bot."))
             return
        
        original_button_text = self.trigger_bot_response_button.text()
        try:
            self.trigger_bot_response_button.setText(self.tr("Waiting for AI..."))
            self.trigger_bot_response_button.setEnabled(False)
            QApplication.processEvents() 

            ai_response = bot.generate_response(current_user_prompt=current_user_prompt, conversation_history=history_for_ai)
            
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
        self.bot_list_widget.clear()
        if chatroom_name:
            chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
            if chatroom:
                for bot in chatroom.list_bots():
                    self.bot_list_widget.addItem(QListWidgetItem(bot.get_name()))
        # Update panel state based on whether a chatroom is active
        self._update_bot_panel_state(chatroom_name is not None and self.chatroom_manager.get_chatroom(chatroom_name) is not None, chatroom_name)


    def _add_bot_to_chatroom(self):
        current_chatroom_item = self.chatroom_list_widget.currentItem()
        if not current_chatroom_item:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("No chatroom selected to add a bot to."))
            return

        chatroom_name = current_chatroom_item.text()
        chatroom = self.chatroom_manager.get_chatroom(chatroom_name)
        if not chatroom: # Should not happen if item is selected
            QMessageBox.critical(self, self.tr("Error"), self.tr("Selected chatroom not found.")) # Should be translated
            return

        bot_name, ok_name = QInputDialog.getText(self, self.tr("Add Bot"), self.tr("Enter bot name (role):"))
        if not (ok_name and bot_name.strip()): 
            self.logger.debug(f"Add bot to chatroom '{chatroom_name}' cancelled or name was invalid (name: '{bot_name}').") # DEBUG - user cancelled
            return
        bot_name = bot_name.strip() 
        
        if chatroom.get_bot(bot_name):
            self.logger.warning(f"Attempt to add bot with existing name '{bot_name}' to chatroom '{chatroom_name}'.") # WARNING - user action failed
            QMessageBox.warning(self, self.tr("Error"), self.tr("A bot named '{0}' already exists in this chatroom.").format(bot_name))
            return

        system_prompt, ok_prompt = QInputDialog.getText(self, self.tr("Add Bot"), self.tr("Enter system prompt for {0}:").format(bot_name))
        if not ok_prompt: 
            self.logger.debug(f"Add bot '{bot_name}' to chatroom '{chatroom_name}' cancelled by user at system prompt input.") # DEBUG - user cancelled
            return 

        engine_types = ["Gemini", "Grok", "OpenAI"] 
        engine_type, ok_engine = QInputDialog.getItem(self, self.tr("Add Bot"), self.tr("Select AI engine for {0}:").format(bot_name), engine_types, 0, False)
        if not ok_engine:
            self.logger.debug(f"Add bot '{bot_name}' to chatroom '{chatroom_name}' cancelled by user at engine selection.") # DEBUG - user cancelled
            return
        
        self.logger.info(f"Attempting to add bot '{bot_name}' with engine '{engine_type}' to chatroom '{chatroom_name}'.") # INFO - user action

        api_key = self.api_key_manager.load_key(engine_type) 
        # Do NOT log the api_key itself
        if not api_key and engine_type in ["OpenAI", "Gemini", "Grok"]: 
            self.logger.warning(f"API Key for {engine_type} not found when adding bot '{bot_name}'. Bot will be created but may not function.") # WARNING - API key missing
            QMessageBox.warning(self, self.tr("Warning"), 
                                self.tr("API Key for {0} not found. Please set it in Settings. Bot will be created but may not function.").format(engine_type))

        engine: AIEngine
        if engine_type == "Gemini":
            engine = GeminiEngine(api_key=api_key) 
        elif engine_type == "Grok":
            engine = GrokEngine(api_key=api_key)
        elif engine_type == "OpenAI":
            engine = OpenAIEngine(api_key=api_key)
        else: 
            self.logger.error(f"Invalid AI engine type '{engine_type}' selected for bot '{bot_name}'.") # ERROR - should not happen
            QMessageBox.critical(self, self.tr("Error"), self.tr("Invalid AI engine selected."))
            return

        new_bot = Bot(name=bot_name, system_prompt=system_prompt, engine=engine)
        if chatroom.add_bot(new_bot): 
            self.logger.info(f"Bot '{bot_name}' (engine: {engine_type}) added to chatroom '{chatroom_name}' successfully.") # INFO - user action success
            self._update_bot_list(chatroom_name)
            self._update_bot_response_selector() 
        else:
            self.logger.error(f"Failed to add bot '{bot_name}' to chatroom '{chatroom_name}' for an unknown reason after initial checks.") # ERROR - unexpected failure
            QMessageBox.critical(self, self.tr("Error"), self.tr("Could not add bot. An unexpected error occurred."))


    def _show_api_key_dialog(self):
        self.logger.debug("Showing API Key Management dialog.") # DEBUG - UI interaction
        dialog = ApiKeyDialog(self.api_key_manager, self)
        dialog.exec()

    def _remove_bot_from_chatroom(self):
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
    logging.basicConfig(
        level=logging.DEBUG, # Changed to DEBUG
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        filename='app.log',
        filemode='w' # Overwrite log file each time for now, can be changed to 'a' for append
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
