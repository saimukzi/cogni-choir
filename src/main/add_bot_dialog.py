"""Dialog for adding a new AI bot to a chatroom."""
from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QLabel, QMessageBox,
    QDialog, QComboBox, QLineEdit, QFormLayout,
    QTextEdit, QDialogButtonBox
)
# Attempt to import from sibling modules
from . import ai_engines

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
        remains open. If validation passes, `super().accept()` is called to
        close the dialog.
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
