"""Account management dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QFormLayout,
    QGroupBox,
    QScrollArea,
    QWidget,
    QCheckBox,
)

from qtframework.widgets import Button, Input
from qtframework.widgets.buttons import ButtonVariant
from pserver_manager.utils.account_manager import get_account_manager

if TYPE_CHECKING:
    from pserver_manager.config_loader import ServerDefinition


class AccountDialog(QDialog):
    """Dialog for managing server accounts."""

    def __init__(self, server: ServerDefinition, parent=None) -> None:
        """Initialize account dialog.

        Args:
            server: Server definition
            parent: Parent widget
        """
        super().__init__(parent)
        self.server = server
        self.account_manager = get_account_manager()
        self.current_account = None

        self.setWindowTitle(f"Accounts - {server.name}")
        self.setMinimumSize(700, 500)

        self._setup_ui()
        self._load_accounts()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main content area with scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)

        # Left side - Account list
        left_panel = QVBoxLayout()

        list_label = QWidget()
        list_label_layout = QHBoxLayout(list_label)
        list_label_layout.setContentsMargins(0, 0, 0, 8)
        from PySide6.QtWidgets import QLabel
        label = QLabel("<b>Accounts</b>")
        list_label_layout.addWidget(label)
        list_label_layout.addStretch()

        left_panel.addWidget(list_label)

        self.account_list = QListWidget()
        self.account_list.setMinimumWidth(200)
        self.account_list.currentItemChanged.connect(self._on_account_selected)
        left_panel.addWidget(self.account_list)

        # Account list buttons
        list_buttons = QHBoxLayout()
        add_btn = Button("Add", variant=ButtonVariant.PRIMARY)
        add_btn.clicked.connect(self._add_account)
        list_buttons.addWidget(add_btn)

        remove_btn = Button("Remove", variant=ButtonVariant.SECONDARY)
        remove_btn.clicked.connect(self._remove_account)
        list_buttons.addWidget(remove_btn)
        self.remove_btn = remove_btn

        left_panel.addLayout(list_buttons)

        content_layout.addLayout(left_panel, stretch=1)

        # Right side - Account details
        right_panel = QGroupBox("Account Details")
        self.form_layout = QFormLayout(right_panel)

        # Username
        self.username_input = Input(placeholder="Username")
        self.form_layout.addRow("Username:", self.username_input)

        # Password
        self.password_input = Input(placeholder="Password")
        self.password_input.setEchoMode(Input.EchoMode.Password)
        self.form_layout.addRow("Password:", self.password_input)

        # Show password checkbox
        self.show_password_cb = QCheckBox("Show password")
        self.show_password_cb.toggled.connect(self._toggle_password_visibility)
        self.form_layout.addRow("", self.show_password_cb)

        # Email (optional)
        self.email_input = Input(placeholder="Email (optional)")
        self.form_layout.addRow("Email:", self.email_input)

        # Notes (optional)
        self.notes_input = Input(placeholder="Notes (optional)")
        self.form_layout.addRow("Notes:", self.notes_input)

        # Primary account checkbox
        self.primary_cb = QCheckBox("Set as primary account")
        self.primary_cb.setToolTip("Primary account is used for quick login")
        self.form_layout.addRow("", self.primary_cb)

        # Save button
        save_btn = Button("Save Account", variant=ButtonVariant.PRIMARY)
        save_btn.clicked.connect(self._save_current_account)
        self.form_layout.addRow("", save_btn)
        self.save_btn = save_btn

        content_layout.addWidget(right_panel, stretch=2)

        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area, stretch=1)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(16, 12, 16, 12)
        button_layout.addStretch()

        close_btn = Button("Close", variant=ButtonVariant.PRIMARY)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        # Initially disable form
        self._set_form_enabled(False)

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable the form.

        Args:
            enabled: Whether to enable the form
        """
        self.username_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.email_input.setEnabled(enabled)
        self.notes_input.setEnabled(enabled)
        self.primary_cb.setEnabled(enabled)
        self.save_btn.setEnabled(enabled)
        self.show_password_cb.setEnabled(enabled)

    def _toggle_password_visibility(self, show: bool) -> None:
        """Toggle password visibility.

        Args:
            show: Whether to show password
        """
        if show:
            self.password_input.setEchoMode(Input.EchoMode.Normal)
        else:
            self.password_input.setEchoMode(Input.EchoMode.Password)

    def _load_accounts(self) -> None:
        """Load accounts for the server."""
        self.account_list.clear()
        accounts = self.account_manager.get_accounts(self.server.id)

        for account in accounts:
            item = QListWidgetItem(account.username)
            if account.is_primary:
                item.setText(f"⭐ {account.username}")
            item.setData(Qt.ItemDataRole.UserRole, account)
            self.account_list.addItem(item)

        self.remove_btn.setEnabled(len(accounts) > 0)

        # If no accounts exist, enable the form for adding a new one
        if len(accounts) == 0:
            self._set_form_enabled(True)
            self.username_input.setFocus()

    def _on_account_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        """Handle account selection.

        Args:
            current: Currently selected item
            previous: Previously selected item
        """
        if current is None:
            self._set_form_enabled(False)
            self.current_account = None
            return

        self._set_form_enabled(True)
        account = current.data(Qt.ItemDataRole.UserRole)
        self.current_account = account

        # Populate form (handle None values)
        self.username_input.setText(account.username or "")
        self.password_input.setText(account.password or "")
        self.email_input.setText(account.email or "")
        self.notes_input.setText(account.notes or "")
        self.primary_cb.setChecked(account.is_primary if account.is_primary is not None else False)

    def _add_account(self) -> None:
        """Add a new account."""
        # Clear form and enable it
        self.username_input.setText("")
        self.password_input.setText("")
        self.email_input.setText("")
        self.notes_input.setText("")
        self.primary_cb.setChecked(False)
        self.current_account = None
        self._set_form_enabled(True)
        self.account_list.setCurrentItem(None)
        self.username_input.setFocus()

    def _remove_account(self) -> None:
        """Remove selected account."""
        current = self.account_list.currentItem()
        if current is None:
            return

        account = current.data(Qt.ItemDataRole.UserRole)
        from qtframework.widgets.advanced import ConfirmDialog
        if ConfirmDialog.confirm(
            "Remove Account",
            f"Are you sure you want to remove the account '{account.username}'?",
            self
        ):
            self.account_manager.remove_account(self.server.id, account.username)
            self._load_accounts()
            self._set_form_enabled(False)

    def _save_current_account(self) -> None:
        """Save the current account."""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid Input", "Username cannot be empty.")
            return

        if not password:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid Input", "Password cannot be empty.")
            return

        self.account_manager.add_account(
            server_id=self.server.id,
            username=username,
            password=password,
            email=self.email_input.text().strip(),
            notes=self.notes_input.text().strip(),
            is_primary=self.primary_cb.isChecked()
        )

        self._load_accounts()

        # Reselect the account if it was being edited
        if self.current_account and self.current_account.username == username:
            for i in range(self.account_list.count()):
                item = self.account_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole).username == username:
                    self.account_list.setCurrentItem(item)
                    break
