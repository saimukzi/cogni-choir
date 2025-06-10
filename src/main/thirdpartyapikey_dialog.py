"""Dialog for managing API keys for various AI services."""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QPushButton, QMessageBox,
    QDialog, QComboBox, QLineEdit, QFormLayout
)
from PyQt6.QtCore import Qt
# Attempt to import from sibling modules
from .thirdpartyapikey_manager import ThirdPartyApiKeyManager, ThirdPartyApiKeyQueryData
from . import third_party


class ThirdPartyApiKeyDialog(QDialog):
    """A dialog for managing API keys for various AI services."""
    def __init__(self, thirdpartyapikey_slot_info_list: list[third_party.ThirdPartyApiKeySlotInfo], thirdpartyapikey_manager: ThirdPartyApiKeyManager, parent=None):
        """Initializes the ThirdPartyApiKeyDialog.

        Args:
            thirdpartyapikey_manager: An instance of ThirdPartyApiKeyManager to handle key storage.
            parent: The parent widget, if any.
        """
        super().__init__(parent)
        self.thirdpartyapikey_manager = thirdpartyapikey_manager
        self.setWindowTitle(self.tr("API Key Management"))
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.service_combo = QComboBox()
        for thirdpartyapikey_slot_info in thirdpartyapikey_slot_info_list:
            self.service_combo.addItem(thirdpartyapikey_slot_info.name, thirdpartyapikey_slot_info.thirdpartyapikey_slot_id)
        self.service_combo.currentTextChanged.connect(self._load_key_for_display)
        form_layout.addRow(self.tr("Service:"), self.service_combo)

        self.thirdpartyapikey_input = QLineEdit()
        self.thirdpartyapikey_input.setEchoMode(QLineEdit.EchoMode.Password) # Mask API key
        form_layout.addRow(self.tr("API Key:"), self.thirdpartyapikey_input)

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
        thirdpartyapikey_slot_id = self.service_combo.currentData()
        thirdpartyapikey_id = thirdpartyapikey_slot_id # TODO: Handle multiple keys per service if needed
        if thirdpartyapikey_slot_id: # Ensure a service is actually selected
            key = self.thirdpartyapikey_manager.get_thirdpartyapikey(ThirdPartyApiKeyQueryData(thirdpartyapikey_slot_id, thirdpartyapikey_id))
            self.thirdpartyapikey_input.setText(key if key else "")
        else:
            self.thirdpartyapikey_input.clear()


    def _save_key(self):
        """Saves the API key entered in the input field for the selected service."""
        thirdpartyapikey_slot_id = self.service_combo.currentData()
        thirdpartyapikey_id = thirdpartyapikey_slot_id # TODO: Handle multiple keys per service if needed
        key_text = self.thirdpartyapikey_input.text()
        if not thirdpartyapikey_slot_id:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Please select a service."))
            return
        if not key_text:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("API Key cannot be empty."))
            return

        self.thirdpartyapikey_manager.set_thirdpartyapikey(ThirdPartyApiKeyQueryData(thirdpartyapikey_slot_id, thirdpartyapikey_id), key_text)
        QMessageBox.information(self, self.tr("Success"), self.tr("API Key saved."))

    def _delete_key(self):
        """Deletes the API key for the selected service after confirmation."""
        thirdpartyapikey_slot_id = self.service_combo.currentData()
        thirdpartyapikey_id = thirdpartyapikey_slot_id # TODO: Handle multiple keys per service if needed
        if not thirdpartyapikey_slot_id:
            QMessageBox.warning(self, self.tr("Warning"), self.tr("Please select a service to delete the key for."))
            return

        reply = QMessageBox.question(self, self.tr("Confirm Delete"),
                                     self.tr("Are you sure you want to delete the API key for {0}?").format(thirdpartyapikey_slot_id),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.thirdpartyapikey_manager.delete_thirdpartyapikey(ThirdPartyApiKeyQueryData(thirdpartyapikey_slot_id, thirdpartyapikey_id))
            self.thirdpartyapikey_input.clear()
            QMessageBox.information(self, self.tr("Success"), self.tr("API Key deleted."))
