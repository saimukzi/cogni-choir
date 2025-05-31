import sys
from PyQt6.QtWidgets import (
    QApplication, QDialog, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QLabel, QMessageBox
)
from PyQt6.QtCore import Qt # Required for Qt.AlignmentFlag

class CreateMasterPasswordDialog(QDialog):
    """A dialog for users to create a new master password.

    This dialog prompts the user to enter a new password and confirm it.
    It performs basic validation to ensure the password fields are not empty
    and that the entered passwords match.

    Attributes:
        password_input (QLineEdit): Input field for the new password.
        confirm_password_input (QLineEdit): Input field for confirming the new password.
        error_label (QLabel): Label to display validation errors.
    """
    def __init__(self, parent=None):
        """Initializes the CreateMasterPasswordDialog.

        Args:
            parent (Optional[QWidget]): The parent widget of this dialog.
        """
        super().__init__(parent)
        self.setWindowTitle("Create Master Password")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        info_label = QLabel("Create a new master password to secure your API keys.")
        layout.addWidget(info_label)

        password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(password_label)
        layout.addWidget(self.password_input)

        confirm_password_label = QLabel("Confirm Password:")
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(confirm_password_label)
        layout.addWidget(self.confirm_password_input)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        layout.addWidget(self.error_label)

        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def accept(self):
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()

        if not password or not confirm_password:
            self.error_label.setText("Password fields cannot be empty.")
        elif password != confirm_password:
            self.error_label.setText("Passwords do not match.")
        else:
            self.error_label.setText("")
            super().accept()

    def get_password(self) -> str | None:
        """Retrieves the entered password if the dialog was accepted.

        Returns:
            Optional[str]: The entered password if the dialog was accepted and
                           passwords were valid, otherwise None.
        """
        if self.result() == QDialog.DialogCode.Accepted:
            return self.password_input.text()
        return None


class EnterMasterPasswordDialog(QDialog):
    """A dialog for users to enter their existing master password.

    This dialog prompts the user for their master password to unlock the
    application or specific features. It includes an option for users who
    have forgotten their password to clear all application data.

    Attributes:
        password_input (QLineEdit): Input field for the master password.
        error_label (QLabel): Label to display validation errors.
        forgot_password_button (QPushButton): Button to initiate data clearing.
        clear_data_flag (bool): True if the user chose to clear all data,
                                False otherwise.
    """
    def __init__(self, parent=None):
        """Initializes the EnterMasterPasswordDialog.

        Args:
            parent (Optional[QWidget]): The parent widget of this dialog.
        """
        super().__init__(parent)
        self.setWindowTitle("Enter Master Password")
        self.setMinimumWidth(400)
        self.clear_data_flag = False

        layout = QVBoxLayout(self)

        info_label = QLabel("Enter your master password to unlock API keys.")
        layout.addWidget(info_label)

        password_label = QLabel("Master Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(password_label)
        layout.addWidget(self.password_input)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        layout.addWidget(self.error_label)

        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.forgot_password_button = QPushButton("Forgot Password? Clear all data")
        self.forgot_password_button.setStyleSheet("color: blue; text-decoration: underline;") # Make it look like a link
        self.forgot_password_button.setFlat(True) # Remove button border
        layout.addWidget(self.forgot_password_button, alignment=Qt.AlignmentFlag.AlignCenter)


        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.forgot_password_button.clicked.connect(self._handle_forgot_password)


    def accept(self):
        password = self.password_input.text()
        if not password:
            self.error_label.setText("Password cannot be empty.")
        else:
            self.error_label.setText("")
            super().accept()

    def get_password(self) -> str | None:
        """Retrieves the entered password if the dialog was accepted.

        This method should only return a password if the user did not choose
        the "forgot password" (clear data) option.

        Returns:
            Optional[str]: The entered password if the dialog was accepted for
                           normal password entry, otherwise None.
        """
        if self.result() == QDialog.DialogCode.Accepted and not self.clear_data_flag:
            return self.password_input.text()
        return None

    def _handle_forgot_password(self):
        """Handles the 'Forgot Password' action.

        Shows a confirmation dialog. If the user confirms, sets the
        `clear_data_flag` to True and accepts the dialog to signal this choice.
        """
        reply = QMessageBox.warning(
            self,
            "Confirm Clear Data",
            "Are you sure you want to clear all stored API keys and the master password? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.clear_data_flag = True
            super().accept() # Close the dialog, signaling acceptance for clearing


class ChangeMasterPasswordDialog(QDialog):
    """A dialog for users to change their existing master password.

    This dialog prompts the user for their old password, a new password, and
    confirmation of the new password. It performs validation for empty fields,
    mismatched new passwords, and ensures the new password is different from
    the old one.

    Attributes:
        old_password_input (QLineEdit): Input for the current master password.
        new_password_input (QLineEdit): Input for the new master password.
        confirm_new_password_input (QLineEdit): Input for confirming the new
                                                master password.
        error_label (QLabel): Label to display validation errors.
    """
    def __init__(self, parent=None):
        """Initializes the ChangeMasterPasswordDialog.

        Args:
            parent (Optional[QWidget]): The parent widget of this dialog.
        """
        super().__init__(parent)
        self.setWindowTitle("Change Master Password")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        info_label = QLabel("Enter your old password and set a new one.")
        layout.addWidget(info_label)

        old_password_label = QLabel("Old Password:")
        self.old_password_input = QLineEdit()
        self.old_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(old_password_label)
        layout.addWidget(self.old_password_input)

        new_password_label = QLabel("New Password:")
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(new_password_label)
        layout.addWidget(self.new_password_input)

        confirm_new_password_label = QLabel("Confirm New Password:")
        self.confirm_new_password_input = QLineEdit()
        self.confirm_new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(confirm_new_password_label)
        layout.addWidget(self.confirm_new_password_input)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        layout.addWidget(self.error_label)

        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def accept(self):
        old_password = self.old_password_input.text()
        new_password = self.new_password_input.text()
        confirm_new_password = self.confirm_new_password_input.text()

        if not old_password or not new_password or not confirm_new_password:
            self.error_label.setText("All password fields must be filled.")
        elif new_password != confirm_new_password:
            self.error_label.setText("New passwords do not match.")
        elif old_password == new_password:
            self.error_label.setText("New password must be different from the old password.")
        else:
            self.error_label.setText("")
            super().accept()

    def get_passwords(self) -> dict[str, str] | None:
        """Retrieves the old and new passwords if the dialog was accepted.

        Returns:
            Optional[dict[str, str]]: A dictionary with "old" and "new" password
                                      strings if the dialog was accepted and
                                      passwords were valid, otherwise None.
        """
        if self.result() == QDialog.DialogCode.Accepted:
            return {
                "old": self.old_password_input.text(),
                "new": self.new_password_input.text()
            }
        return None


if __name__ == '__main__':
    app = QApplication(sys.argv)

    print("Testing CreateMasterPasswordDialog...")
    create_dialog = CreateMasterPasswordDialog()
    if create_dialog.exec():
        print(f"CreateMasterPasswordDialog accepted. Password: {create_dialog.get_password()}")
    else:
        print("CreateMasterPasswordDialog canceled.")

    print("\nTesting EnterMasterPasswordDialog...")
    enter_dialog = EnterMasterPasswordDialog()
    if enter_dialog.exec():
        if enter_dialog.clear_data_flag:
            print("EnterMasterPasswordDialog: User chose to clear data.")
        else:
            print(f"EnterMasterPasswordDialog accepted. Password: {enter_dialog.get_password()}")
    else:
        print("EnterMasterPasswordDialog canceled.")

    print("\nTesting ChangeMasterPasswordDialog...")
    change_dialog = ChangeMasterPasswordDialog()
    if change_dialog.exec():
        passwords = change_dialog.get_passwords()
        print(f"ChangeMasterPasswordDialog accepted. Old: {passwords['old']}, New: {passwords['new']}")
    else:
        print("ChangeMasterPasswordDialog canceled.")

    # sys.exit(app.exec()) # Keep open if you want to interact more, not good for automated test
    sys.exit(0) # Exit cleanly for automated test
