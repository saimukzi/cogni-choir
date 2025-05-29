"""Dialog for creating and inserting a 'fake' message into a chatroom.

This module provides a QDialog subclass that allows users (primarily for
development and testing purposes) to manually specify a sender (either "User"
or an existing bot) and message content, then insert this message into the
active chatroom.
"""
from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QLabel,
    QDialog, QComboBox,
    QTextEdit, QDialogButtonBox
)


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
