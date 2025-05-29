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
