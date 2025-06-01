"""Dialog for adding a new AI bot to a chatroom."""
from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QLabel, QMessageBox,
    QDialog, QComboBox, QLineEdit, QFormLayout,
    QTextEdit, QDialogButtonBox
)

from .ai_bots import Bot
from . import third_party
from .third_party import AIEngineArgType # Added import
from . import apikey_manager

class AddBotDialog(QDialog):
    """A dialog for adding a new bot to a chatroom.

    This dialog allows the user to specify the bot's name, select an AI engine,
    optionally provide a model name, and set a system prompt for the bot.
    It also validates the bot name for emptiness and uniqueness.
    """
    def __init__(self,
                 existing_bot_names: list[str],
                 aiengine_info_list: list[third_party.AIEngineInfo],
                 apikey_query_list: list[apikey_manager.ApiKeyQuery],
                 parent=None):
        """Initializes the AddBotDialog.

        Args:
            existing_bot_names: A list of names of bots that already exist
                                in the current context, used for validation.
            parent: The parent widget, if any.
        """
        super().__init__(parent)
        self.existing_bot_names = existing_bot_names
        self.aiengine_info_list = aiengine_info_list
        self.apikey_query_list = apikey_query_list
        self._dynamic_widgets = []
        self._dynamic_input_widgets = {}

        self.setWindowTitle(self.tr("Add New Bot"))
        self.setMinimumWidth(400) # Set a reasonable minimum width

        main_layout = QVBoxLayout(self)
        self.form_layout = QFormLayout() # Store form_layout as instance member

        # Bot Name
        self.bot_name_label = QLabel(self.tr("Bot Name:"))
        self.bot_name_input = QLineEdit()
        self.form_layout.addRow(self.bot_name_label, self.bot_name_input)

        # AI Engine
        self.engine_label = QLabel(self.tr("AI Engine:"))
        self.engine_combo = QComboBox()
        for aiengine_info in self.aiengine_info_list:
            self.engine_combo.addItem(aiengine_info.name, aiengine_info.aiengine_id)
        self.form_layout.addRow(self.engine_label, self.engine_combo)

        # Model Name (Optional)
        self.model_name_label = QLabel(self.tr("Model Name (Optional):"))
        self.model_name_input = QLineEdit()
        self.form_layout.addRow(self.model_name_label, self.model_name_input)

        # System Prompt
        self.system_prompt_label = QLabel(self.tr("System Prompt:"))
        self.system_prompt_input = QTextEdit()
        self.system_prompt_input.setMinimumHeight(100)
        self.form_layout.addRow(self.system_prompt_label, self.system_prompt_input)

        main_layout.addLayout(self.form_layout)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept) # Connect to custom accept method
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self._set_model_name_input_to_default()
        # Initialize dynamic fields for the initially selected engine
        self._update_input_fields() # Call it once at init
        # Connect to the new method
        self.engine_combo.currentIndexChanged.connect(self._update_input_fields)

    def _set_model_name_input_to_default(self):
        """Sets the model name input to its default for the current engine.

        Retrieves the default model name for the currently selected AI engine
        and updates the `model_name_input` QLineEdit. If no default model
        name is found, the input field is cleared.
        """
        default_model_name = self._get_default_model_name()
        if default_model_name:
            self.model_name_input.setText(default_model_name)
        else:
            self.model_name_input.clear()

    def _get_default_model_name(self) -> str:
        """Gets the default model name for the currently selected AI engine.

        Returns:
            The default model name as a string, or an empty string if no
            default model name is defined for the selected engine or if no
            engine is selected.
        """
        aiengine_info = self._get_current_aiengine_info()
        if not aiengine_info:
            return ''

        aiengine_arg_info = aiengine_info.get_aiengine_arg_info("model_name")
        if not aiengine_arg_info:
            return ''
        if not aiengine_arg_info.default_value:
            return ''
        return aiengine_arg_info.default_value

    def _update_input_fields(self):
        """Updates dynamic input fields based on selected AI engine."""
        # Clear previous dynamic widgets
        # Static rows are: Bot Name, AI Engine, Model Name, System Prompt. These are the first 4 rows.
        # Row indices for these are 0, 1, 2, 3.
        while self.form_layout.rowCount() > 4:
            # Removing row at index 4, because rows are 0-indexed.
            # This removes the 5th row, which is the first dynamic row.
            self.form_layout.removeRow(4)

        for widget in self._dynamic_widgets:
            widget.deleteLater()
        self._dynamic_widgets.clear()
        self._dynamic_input_widgets.clear()

        current_ai_engine_info = self._get_current_aiengine_info()
        if not current_ai_engine_info:
            return

        for arg_info in current_ai_engine_info.arg_list:
            # Skip model_name and system_prompt as they are handled separately for now
            if arg_info.arg_id in ["model_name", "system_prompt"]:
                continue

            label = QLabel(self.tr(arg_info.name) + (" (Optional):" if arg_info.is_optional else ":"))
            widget = None

            if arg_info.arg_type == AIEngineArgType.SINGLE_LINE:
                widget = QLineEdit()
                if arg_info.default_value:
                    widget.setText(arg_info.default_value)
            elif arg_info.arg_type == AIEngineArgType.MULTI_LINE:
                widget = QTextEdit()
                if arg_info.default_value:
                    widget.setPlainText(arg_info.default_value)
                widget.setMinimumHeight(60) # Smaller height for generic multi-line
            elif arg_info.arg_type == AIEngineArgType.SELECTION:
                widget = QComboBox()
                if arg_info.selection_list:
                    for item in arg_info.selection_list: # Ensure items are strings for addItem
                        widget.addItem(str(item))
                if arg_info.default_value:
                    widget.setCurrentText(str(arg_info.default_value))

            if widget:
                self.form_layout.addRow(label, widget)
                self._dynamic_widgets.append(label)
                self._dynamic_widgets.append(widget)
                self._dynamic_input_widgets[arg_info.arg_id] = widget

        # Special handling for model_name to set its default if it's part of arg_list
        # This ensures _set_model_name_input_to_default works as expected
        # or can be integrated here. For now, let's call it to keep its logic.
        self._set_model_name_input_to_default()


    def _get_current_aiengine_info(self) -> third_party.AIEngineInfo | None:
        """Retrieves the currently selected AI engine information.

        Returns:
            An instance of AIEngineInfo corresponding to the selected AI engine,
            or None if no engine is selected.
        """
        aiengine_id = self.engine_combo.currentData()
        if not aiengine_id:
            return None

        aiengine_info = self.aiengine_info_list
        aiengine_info = filter(lambda x: x.aiengine_id == aiengine_id, aiengine_info)
        aiengine_info = list(aiengine_info)
        assert len(aiengine_info) <= 1, "AI Engine ID should be unique"
        if not aiengine_info:
            return None
        aiengine_info = aiengine_info[0]
        return aiengine_info

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
                                self.tr("A bot named '{0}' already exists. "
                                        "Please choose a different name.").format(bot_name))
            return  # Keep dialog open

        aiengine_id = self.engine_combo.currentData()
        if not aiengine_id:
            QMessageBox.warning(self, self.tr("Input Error"),
                                self.tr("Please select an AI engine."))
            return

        if not self._get_matched_api_query_list():
            QMessageBox.warning(self, self.tr("Input Error"),
                                self.tr("The selected AI engine requires an API key, "
                                        "but no API key is provided."))
            return

        super().accept() # All checks passed, proceed to close

    # def get_data(self) -> dict | None:
    #     """Retrieves the data entered into the dialog.

    #     Returns:
    #         A dictionary containing the bot's configuration data if the dialog
    #         was accepted (OK clicked), otherwise None. The dictionary includes:
    #         - "bot_name": str
    #         - "engine_type": str
    #         - "model_name": str
    #         - "system_prompt": str
    #     """
    #     if self.result() == QDialog.DialogCode.Accepted:
    #         return {
    #             "bot_name": self.bot_name_input.text(),
    #             "engine_type": self.engine_combo.currentData(),
    #             "model_name": self.model_name_input.text(),
    #             "system_prompt": self.system_prompt_input.toPlainText()
    #         }
    #     return None

    def _get_matched_api_query_list(self) -> list[apikey_manager.ApiKeyQuery]:
        """Gets API key queries matching the selected AI engine's requirements.

        Filters the dialog's `apikey_query_list` to include only those queries
        whose `apikey_slot_id` is present in the `apikey_slot_id_list` of the
        currently selected `AIEngineInfo`.

        Returns:
            A list of `ApiKeyQuery` objects that match the API key requirements
            of the selected AI engine. Returns an empty list if no AI engine is
            selected or if no matching API key queries are found.
        """
        aiengine_info = self._get_current_aiengine_info()
        if not aiengine_info:
            return []

        apikey_slot_id_set = aiengine_info.apikey_slot_id_list
        apikey_slot_id_set = set(apikey_slot_id_set)

        apikey_query_list = self.apikey_query_list
        apikey_query_list = filter(lambda x: x.apikey_slot_id in apikey_slot_id_set, apikey_query_list)
        apikey_query_list = list(apikey_query_list)

        return apikey_query_list

    def get_bot(self) -> Bot | None:
        """Retrieves the bot configuration from the dialog.

        Returns:
            A Bot instance with the configuration data if the dialog was accepted,
            otherwise None.
        """
        if self.result() == QDialog.DialogCode.Accepted:
            bot = Bot()
            bot.name = self.bot_name_input.text().strip()
            bot.aiengine_id = self.engine_combo.currentData()
            bot.aiengine_arg_dict = {
                "model_name": self.model_name_input.text().strip(),
                "system_prompt": self.system_prompt_input.toPlainText().strip()
            }
            # Retrieve values from dynamic fields
            for arg_id, widget in self._dynamic_input_widgets.items():
                if isinstance(widget, QLineEdit):
                    bot.aiengine_arg_dict[arg_id] = widget.text().strip()
                elif isinstance(widget, QTextEdit):
                    bot.aiengine_arg_dict[arg_id] = widget.toPlainText().strip()
                elif isinstance(widget, QComboBox):
                    bot.aiengine_arg_dict[arg_id] = widget.currentText()

            bot.apikey_query_list = self._get_matched_api_query_list()

            # fill default value
            aiengine_info = self._get_current_aiengine_info()
            assert aiengine_info is not None, "AI Engine info should not be None"
            for k, v in bot.aiengine_arg_dict.items():
                if v:
                    continue
                aiengine_arg_info = aiengine_info.get_aiengine_arg_info(k)
                if not aiengine_arg_info:
                    continue
                if not aiengine_arg_info.default_value:
                    continue
                bot.aiengine_arg_dict[k] = aiengine_arg_info.default_value

            return bot
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
