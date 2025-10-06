"""Account management with secure password storage."""

from __future__ import annotations

import yaml
import base64
from pathlib import Path
from typing import TYPE_CHECKING
from dataclasses import dataclass, asdict

from cryptography.fernet import Fernet

if TYPE_CHECKING:
    pass


@dataclass
class ServerAccount:
    """Represents a server account."""

    username: str
    password: str  # Encrypted
    email: str = ""
    notes: str = ""
    is_primary: bool = False


class AccountManager:
    """Manages server accounts with encrypted password storage."""

    def __init__(self, accounts_file: Path) -> None:
        """Initialize account manager.

        Args:
            accounts_file: Path to accounts JSON file
        """
        self.accounts_file = accounts_file
        self._cipher = self._get_cipher()
        self._accounts: dict[str, list[ServerAccount]] = {}
        self._load()

    def _get_cipher(self) -> Fernet:
        """Get or create encryption cipher.

        Uses a machine-specific key derived from system info.

        Returns:
            Fernet cipher instance
        """
        # Use app data directory for key storage
        key_file = self.accounts_file.parent / ".key"

        if key_file.exists():
            key = key_file.read_bytes()
        else:
            # Generate new key
            key = Fernet.generate_key()
            # Ensure parent directory exists
            key_file.parent.mkdir(parents=True, exist_ok=True)
            # Save key with restricted permissions
            key_file.write_bytes(key)
            # Try to restrict permissions (Unix-like systems)
            try:
                import os
                os.chmod(key_file, 0o600)
            except Exception:
                pass

        return Fernet(key)

    def _encrypt_password(self, password: str) -> str:
        """Encrypt a password.

        Args:
            password: Plain text password

        Returns:
            Encrypted password (base64 encoded)
        """
        encrypted = self._cipher.encrypt(password.encode())
        return base64.b64encode(encrypted).decode()

    def _decrypt_password(self, encrypted_password: str) -> str:
        """Decrypt a password.

        Args:
            encrypted_password: Encrypted password (base64 encoded)

        Returns:
            Plain text password
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_password.encode())
            decrypted = self._cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception:
            return ""

    def _load(self) -> None:
        """Load accounts from file."""
        if not self.accounts_file.exists():
            self._accounts = {}
            return

        try:
            with open(self.accounts_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            # Convert dict to ServerAccount objects
            self._accounts = {}
            for server_id, accounts_data in data.items():
                self._accounts[server_id] = [
                    ServerAccount(**account) for account in accounts_data
                ]
        except Exception as e:
            print(f"Error loading accounts: {e}")
            self._accounts = {}

    def _save(self) -> None:
        """Save accounts to file."""
        try:
            # Ensure parent directory exists
            self.accounts_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert ServerAccount objects to dicts
            data = {}
            for server_id, accounts in self._accounts.items():
                data[server_id] = [asdict(account) for account in accounts]

            with open(self.accounts_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            print(f"Error saving accounts: {e}")

    def get_accounts(self, server_id: str) -> list[ServerAccount]:
        """Get all accounts for a server.

        Args:
            server_id: Server ID

        Returns:
            List of accounts (with decrypted passwords)
        """
        accounts = self._accounts.get(server_id, [])
        # Return copies with decrypted passwords
        return [
            ServerAccount(
                username=acc.username,
                password=self._decrypt_password(acc.password),
                email=acc.email,
                notes=acc.notes,
                is_primary=acc.is_primary
            )
            for acc in accounts
        ]

    def add_account(
        self,
        server_id: str,
        username: str,
        password: str,
        email: str = "",
        notes: str = "",
        is_primary: bool = False
    ) -> None:
        """Add or update an account.

        Args:
            server_id: Server ID
            username: Account username
            password: Account password (will be encrypted)
            email: Optional email
            notes: Optional notes
            is_primary: Mark as primary account
        """
        if server_id not in self._accounts:
            self._accounts[server_id] = []

        # If marking as primary, unmark others
        if is_primary:
            for acc in self._accounts[server_id]:
                acc.is_primary = False

        # Check if account exists (update) or is new
        existing = None
        for acc in self._accounts[server_id]:
            if acc.username == username:
                existing = acc
                break

        if existing:
            # Update existing
            existing.password = self._encrypt_password(password)
            existing.email = email
            existing.notes = notes
            existing.is_primary = is_primary
        else:
            # Add new
            self._accounts[server_id].append(
                ServerAccount(
                    username=username,
                    password=self._encrypt_password(password),
                    email=email,
                    notes=notes,
                    is_primary=is_primary
                )
            )

        self._save()

    def remove_account(self, server_id: str, username: str) -> bool:
        """Remove an account.

        Args:
            server_id: Server ID
            username: Account username

        Returns:
            True if account was removed
        """
        if server_id not in self._accounts:
            return False

        original_len = len(self._accounts[server_id])
        self._accounts[server_id] = [
            acc for acc in self._accounts[server_id]
            if acc.username != username
        ]

        if len(self._accounts[server_id]) < original_len:
            self._save()
            return True
        return False

    def get_primary_account(self, server_id: str) -> ServerAccount | None:
        """Get the primary account for a server.

        Args:
            server_id: Server ID

        Returns:
            Primary account or None
        """
        accounts = self.get_accounts(server_id)
        for acc in accounts:
            if acc.is_primary:
                return acc
        # If no primary, return first account
        return accounts[0] if accounts else None

    def has_accounts(self, server_id: str) -> bool:
        """Check if server has any accounts.

        Args:
            server_id: Server ID

        Returns:
            True if server has accounts
        """
        return server_id in self._accounts and len(self._accounts[server_id]) > 0


# Global instance
_account_manager: AccountManager | None = None


def get_account_manager() -> AccountManager:
    """Get the global AccountManager instance.

    Returns:
        AccountManager instance
    """
    global _account_manager
    if _account_manager is None:
        from pserver_manager.utils.paths import get_app_paths
        _account_manager = AccountManager(get_app_paths().get_accounts_file())
    return _account_manager
