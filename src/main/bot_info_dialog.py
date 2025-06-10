"""Dialog for adding a new AI bot to a chatroom."""
import logging

from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QLabel, QMessageBox,
    QDialog, QComboBox, QLineEdit, QFormLayout,
    QTextEdit, QDialogButtonBox
)

from .ai_bots import BotData
from . import third_party
from .third_party import AIEngineArgType # Added import
from . import thirdpartyapikey_manager

class BotInfoDialog(QDialog):
    """A dialog for adding a new bot to a chatroom.

    This dialog allows the user to specify the bot's name, select an AI engine,
    optionally provide a model name, and set a system prompt for the bot.
    It also validates the bot name for emptiness and uniqueness.
    """
    def __init__(self,
                 existing_bot_names: list[str],
                 aiengine_info_list: list[third_party.AIEngineInfo],
                 thirdpartyapikey_query_list: list[thirdpartyapikey_manager.ThirdPartyApiKeyQueryData],
                 old_bot: BotData | None = None,
                 parent=None):
        """Initializes the BotInfoDialog.

        Args:
            existing_bot_names: A list of names of bots that already exist
                                in the current context, used for validation.
            parent: The parent widget, if any.
        """
        super().__init__(parent)

        self._logger = logging.getLogger(__name__)

        self.existing_bot_names = existing_bot_names
        self.aiengine_info_list = aiengine_info_list
        self.thirdpartyapikey_query_list = thirdpartyapikey_query_list
        self._dynamic_widgets = []
        self._dynamic_input_widgets = {}

        # self._logger.debug(f"len(thirdpartyapikey_query_list) = {len(thirdpartyapikey_query_list)}")

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

        # # Model Name (Optional)
        # self.model_name_label = QLabel(self.tr("Model Name (Optional):"))
        # self.model_name_input = QLineEdit()
        # self.form_layout.addRow(self.model_name_label, self.model_name_input)

        # # System Prompt
        # self.system_prompt_label = QLabel(self.tr("System Prompt:"))
        # self.system_prompt_input = QTextEdit()
        # self.system_prompt_input.setMinimumHeight(100)
        # self.form_layout.addRow(self.system_prompt_label, self.system_prompt_input)

        main_layout.addLayout(self.form_layout)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept) # Connect to custom accept method
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Initialize dynamic fields for the initially selected engine
        # self._update_input_fields() # Call it once at init
        self._set_values_by_bot(old_bot)
        # Connect to the new method
        self.engine_combo.currentIndexChanged.connect(self._update_input_fields)

    def _set_values_by_bot(self, bot: BotData | None):
        """Sets the dialog fields with values from an existing Bot instance.

        Args:
            bot: An instance of Bot containing the bot's configuration.
        """
        if bot:
            self.bot_name_input.setText(bot.name)
            self.engine_combo.setCurrentIndex(self.engine_combo.findData(bot.aiengine_id))

        self._update_input_fields()

        # Set dynamic input fields based on the bot's AI engine arguments
        if bot:
            for arg_id, value in bot.aiengine_arg_dict.items():
                if arg_id not in self._dynamic_input_widgets:
                    continue
                widget = self._dynamic_input_widgets[arg_id]
                if isinstance(widget, QLineEdit):
                    widget.setText(value)
                elif isinstance(widget, QTextEdit):
                    widget.setPlainText(value)
                elif isinstance(widget, QComboBox):
                    widget.setCurrentText(value)

    def _update_input_fields(self):
        """Updates dynamic input fields based on selected AI engine."""
        # # Clear previous dynamic widgets
        # # Static rows are: Bot Name, AI Engine, Model Name, System Prompt. These are the first 4 rows.
        # # Row indices for these are 0, 1, 2, 3.
        # while self.form_layout.rowCount() > 4:
        #     # Removing row at index 4, because rows are 0-indexed.
        #     # This removes the 5th row, which is the first dynamic row.
        #     self.form_layout.removeRow(4)

        for widget in self._dynamic_widgets:
            # print('delete widget')
            widget.deleteLater()
        self._dynamic_widgets.clear()
        self._dynamic_input_widgets.clear()

        current_ai_engine_info = self._get_current_aiengine_info()
        if not current_ai_engine_info:
            return

        for arg_info in current_ai_engine_info.arg_list:

            label = QLabel(self.tr(arg_info.name) + (" (Optional):" if not arg_info.required else ":"))
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
                if arg_info.value_option_list:
                    for item in arg_info.value_option_list: # Ensure items are strings for addItem
                        widget.addItem(str(item))
                if arg_info.default_value:
                    widget.setCurrentText(str(arg_info.default_value))
            elif arg_info.arg_type == AIEngineArgType.SUGGESTION:
                widget = QComboBox()
                if arg_info.value_option_list:
                    for item in arg_info.value_option_list: # Ensure items are strings for addItem
                        widget.addItem(str(item))
                if arg_info.default_value:
                    widget.setCurrentText(str(arg_info.default_value))
                widget.setEditable(True)  # Allow user to type in suggestions
            else:
                assert False, f"Unsupported AIEngineArgType: {arg_info.arg_type}"

            if widget:
                self.form_layout.addRow(label, widget)
                self._dynamic_widgets.append(label)
                self._dynamic_widgets.append(widget)
                self._dynamic_input_widgets[arg_info.arg_id] = widget


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

    def _get_matched_api_query_list(self) -> list[thirdpartyapikey_manager.ThirdPartyApiKeyQueryData]:
        """Gets API key queries matching the selected AI engine's requirements.

        Filters the dialog's `thirdpartyapikey_query_list` to include only those queries
        whose `thirdpartyapikey_slot_id` is present in the `thirdpartyapikey_slot_id_list` of the
        currently selected `AIEngineInfo`.

        Returns:
            A list of `ThirdPartyApiKeyQuery` objects that match the API key requirements
            of the selected AI engine. Returns an empty list if no AI engine is
            selected or if no matching API key queries are found.
        """
        aiengine_info = self._get_current_aiengine_info()
        if not aiengine_info:
            return []

        thirdpartyapikey_slot_id_set = aiengine_info.thirdpartyapikey_slot_id_list
        thirdpartyapikey_slot_id_set = set(thirdpartyapikey_slot_id_set)

        thirdpartyapikey_query_list = self.thirdpartyapikey_query_list
        thirdpartyapikey_query_list = filter(lambda x: x.thirdpartyapikey_slot_id in thirdpartyapikey_slot_id_set, thirdpartyapikey_query_list)
        thirdpartyapikey_query_list = list(thirdpartyapikey_query_list)

        return thirdpartyapikey_query_list

    def get_bot(self) -> BotData | None:
        """Retrieves the bot configuration from the dialog.

        Returns:
            A Bot instance with the configuration data if the dialog was accepted,
            otherwise None.
        """
        if self.result() == QDialog.DialogCode.Accepted:
            bot = BotData()
            bot.name = self.bot_name_input.text().strip()
            bot.aiengine_id = self.engine_combo.currentData()
            bot.aiengine_arg_dict = {}
            # Retrieve values from dynamic fields
            for arg_id, widget in self._dynamic_input_widgets.items():
                if isinstance(widget, QLineEdit):
                    bot.aiengine_arg_dict[arg_id] = widget.text().strip()
                elif isinstance(widget, QTextEdit):
                    bot.aiengine_arg_dict[arg_id] = widget.toPlainText().strip()
                elif isinstance(widget, QComboBox):
                    bot.aiengine_arg_dict[arg_id] = widget.currentText()

            bot.thirdpartyapikey_query_list = self._get_matched_api_query_list()

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
        return QApplication.translate("BotInfoDialog", text, disambiguation, n)
