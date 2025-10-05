"""Update and migration system for PServer Manager."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ServerMetadata:
    """Metadata for tracking server config updates."""

    source: str  # "bundled" or "user"
    app_version: str  # Version when server was added/updated
    content_hash: str  # Hash of server content (excludes metadata)
    last_updated: str  # ISO timestamp

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServerMetadata:
        """Create from dictionary.

        Args:
            data: Metadata dictionary

        Returns:
            ServerMetadata instance
        """
        return cls(
            source=data.get("source", "user"),
            app_version=data.get("app_version", "unknown"),
            content_hash=data.get("content_hash", ""),
            last_updated=data.get("last_updated", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Metadata dictionary
        """
        return {
            "source": self.source,
            "app_version": self.app_version,
            "content_hash": self.content_hash,
            "last_updated": self.last_updated,
        }


@dataclass
class UpdateInfo:
    """Information about available updates."""

    new_servers: list[str]  # Server IDs that are new
    updated_servers: list[str]  # Server IDs that have updates
    conflicts: list[str]  # Server IDs with conflicts (user modified bundled server)
    schema_migration_needed: bool  # Settings schema needs migration
    new_themes: list[str]  # Theme names that are new
    updated_themes: list[str]  # Theme names that have updates
    theme_conflicts: list[str]  # Theme names with conflicts (user modified bundled theme)


class ServerUpdateChecker:
    """Checks for server updates and handles conflicts."""

    APP_VERSION = "1.0.0"  # Should be updated with each release

    def __init__(
        self,
        bundled_dir: Path,
        user_dir: Path,
        bundled_themes_dir: Path | None = None,
        user_themes_dir: Path | None = None,
    ):
        """Initialize update checker.

        Args:
            bundled_dir: Directory with bundled server configs
            user_dir: Directory with user server configs
            bundled_themes_dir: Directory with bundled themes (optional)
            user_themes_dir: Directory with user themes (optional)
        """
        self.bundled_dir = bundled_dir
        self.user_dir = user_dir
        self.bundled_themes_dir = bundled_themes_dir
        self.user_themes_dir = user_themes_dir

    @staticmethod
    def compute_content_hash(server_data: dict[str, Any]) -> str:
        """Compute hash of server content (excluding metadata).

        Args:
            server_data: Server configuration data

        Returns:
            SHA256 hash of content
        """
        # Create a copy without metadata
        content = {k: v for k, v in server_data.items() if k != "_metadata"}

        # Convert to stable string representation
        content_str = yaml.dump(content, default_flow_style=False, sort_keys=True)

        # Compute hash
        return hashlib.sha256(content_str.encode()).hexdigest()

    def add_metadata(self, server_data: dict[str, Any], source: str = "user") -> dict[str, Any]:
        """Add metadata to server config.

        Args:
            server_data: Server configuration data
            source: Source of server ("bundled" or "user")

        Returns:
            Server data with metadata
        """
        from datetime import datetime

        content_hash = self.compute_content_hash(server_data)

        metadata = ServerMetadata(
            source=source,
            app_version=self.APP_VERSION,
            content_hash=content_hash,
            last_updated=datetime.now().isoformat(),
        )

        server_data["_metadata"] = metadata.to_dict()
        return server_data

    def load_server_with_metadata(self, file_path: Path) -> tuple[dict[str, Any], ServerMetadata | None]:
        """Load server config and extract metadata.

        Args:
            file_path: Path to server YAML file

        Returns:
            Tuple of (server_data, metadata)
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        metadata = None
        if "_metadata" in data:
            metadata = ServerMetadata.from_dict(data["_metadata"])

        return data, metadata

    def check_for_theme_updates(self) -> tuple[list[str], list[str], list[str]]:
        """Check for theme updates.

        Returns:
            Tuple of (new_themes, updated_themes, theme_conflicts)
        """
        new_themes = []
        updated_themes = []
        theme_conflicts = []

        # Skip if theme directories not configured
        if not self.bundled_themes_dir or not self.user_themes_dir:
            return new_themes, updated_themes, theme_conflicts

        if not self.bundled_themes_dir.exists():
            return new_themes, updated_themes, theme_conflicts

        # Get all bundled themes
        for theme_file in self.bundled_themes_dir.glob("*.yaml"):
            theme_name = theme_file.stem
            user_theme_file = self.user_themes_dir / theme_file.name

            # Load bundled theme
            with open(theme_file, "r", encoding="utf-8") as f:
                bundled_theme = yaml.safe_load(f)

            bundled_version = bundled_theme.get("version", "1.0.0")

            if not user_theme_file.exists():
                # New theme available
                new_themes.append(theme_name)
            else:
                # Theme exists - check version and content
                with open(user_theme_file, "r", encoding="utf-8") as f:
                    user_theme = yaml.safe_load(f)

                user_version = user_theme.get("version", "1.0.0")

                # Check if content differs
                bundled_hash = self.compute_content_hash(bundled_theme)
                user_hash = self.compute_content_hash(user_theme)

                if bundled_hash != user_hash:
                    # Content differs - check if it's an update or user modification
                    if bundled_version != user_version:
                        # Versions differ - compare to see if bundled is newer
                        if self._is_version_newer(bundled_version, user_version):
                            updated_themes.append(theme_name)
                        # else: user has newer/same version but different content (user customization)
                    else:
                        # Same version but different content
                        # This is likely a bundled update (e.g., bug fix in same version)
                        # Offer as update
                        updated_themes.append(theme_name)

        return new_themes, updated_themes, theme_conflicts

    @staticmethod
    def _is_version_newer(version1: str, version2: str) -> bool:
        """Check if version1 is newer than version2.

        Args:
            version1: First version string (e.g., "1.2.0")
            version2: Second version string (e.g., "1.1.0")

        Returns:
            True if version1 > version2
        """
        try:
            v1_parts = [int(x) for x in version1.split(".")]
            v2_parts = [int(x) for x in version2.split(".")]

            # Pad shorter version with zeros
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts += [0] * (max_len - len(v1_parts))
            v2_parts += [0] * (max_len - len(v2_parts))

            return v1_parts > v2_parts
        except (ValueError, AttributeError):
            # If version parsing fails, assume not newer
            return False

    def check_for_updates(self) -> UpdateInfo:
        """Check for available updates.

        Returns:
            UpdateInfo with available updates
        """
        new_servers = []
        updated_servers = []
        conflicts = []

        # Get all bundled servers
        bundled_servers = {}
        if self.bundled_dir.exists():
            for game_dir in self.bundled_dir.iterdir():
                if game_dir.is_dir():
                    for server_file in game_dir.glob("*.yaml"):
                        server_id = f"{game_dir.name}.{server_file.stem}"
                        bundled_servers[server_id] = server_file

        # Check each bundled server against user directory
        for server_id, bundled_file in bundled_servers.items():
            game_id, server_name = server_id.split(".", 1)
            user_file = self.user_dir / game_id / f"{server_name}.yaml"

            bundled_data, _ = self.load_server_with_metadata(bundled_file)
            bundled_hash = self.compute_content_hash(bundled_data)

            if not user_file.exists():
                # New server available
                new_servers.append(server_id)
            else:
                # Server exists in user directory - check for updates
                user_data, user_metadata = self.load_server_with_metadata(user_file)
                current_user_hash = self.compute_content_hash(user_data)

                if user_metadata is None:
                    # No metadata - legacy file (migrated from old location)
                    # Since it matches a bundled server ID, treat as old bundled server
                    # Compare hashes to detect if bundled version changed
                    if bundled_hash != current_user_hash:
                        # Bundled version changed - mark as update available
                        updated_servers.append(server_id)
                    continue

                if user_metadata.source == "user":
                    # User created their own server with same ID - potential conflict
                    # Only flag if bundled version is different
                    if bundled_hash != current_user_hash:
                        conflicts.append(server_id)
                    continue

                # Bundled server - check if it's been updated
                if bundled_hash != user_metadata.content_hash:
                    # Check if user modified it
                    if current_user_hash != user_metadata.content_hash:
                        # User modified bundled server - conflict
                        conflicts.append(server_id)
                    else:
                        # Clean update - bundled version changed, user didn't modify
                        updated_servers.append(server_id)

        # Check for theme updates
        new_themes, updated_themes, theme_conflicts = self.check_for_theme_updates()

        return UpdateInfo(
            new_servers=new_servers,
            updated_servers=updated_servers,
            conflicts=conflicts,
            schema_migration_needed=False,  # TODO: Implement schema migration detection
            new_themes=new_themes,
            updated_themes=updated_themes,
            theme_conflicts=theme_conflicts,
        )

    def import_server(self, server_id: str, overwrite: bool = False) -> bool:
        """Import a bundled server to user directory.

        Args:
            server_id: Server ID (e.g., "wow.chromiecraft")
            overwrite: Whether to overwrite existing file

        Returns:
            True if successful
        """
        try:
            game_id, server_name = server_id.split(".", 1)
            bundled_file = self.bundled_dir / game_id / f"{server_name}.yaml"
            user_file = self.user_dir / game_id / f"{server_name}.yaml"

            if not bundled_file.exists():
                return False

            if user_file.exists() and not overwrite:
                return False

            # Load bundled server and add metadata
            bundled_data, _ = self.load_server_with_metadata(bundled_file)
            bundled_data = self.add_metadata(bundled_data, source="bundled")

            # Ensure user directory exists
            user_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to user directory
            with open(user_file, "w", encoding="utf-8") as f:
                yaml.dump(bundled_data, f, default_flow_style=False, sort_keys=False)

            return True
        except Exception as e:
            print(f"Error importing server {server_id}: {e}")
            return False

    def import_all_new_servers(self) -> int:
        """Import all new bundled servers.

        Returns:
            Number of servers imported
        """
        update_info = self.check_for_updates()
        count = 0

        for server_id in update_info.new_servers:
            if self.import_server(server_id):
                count += 1

        return count

    def update_server(self, server_id: str, force: bool = False) -> bool:
        """Update a server to latest bundled version.

        Args:
            server_id: Server ID to update
            force: Force update even if there's a conflict

        Returns:
            True if successful
        """
        return self.import_server(server_id, overwrite=True)

    def import_theme(self, theme_name: str, overwrite: bool = False) -> bool:
        """Import a bundled theme to user directory.

        Args:
            theme_name: Theme name (e.g., "wow")
            overwrite: Whether to overwrite existing file

        Returns:
            True if successful
        """
        try:
            if not self.bundled_themes_dir or not self.user_themes_dir:
                return False

            bundled_file = self.bundled_themes_dir / f"{theme_name}.yaml"
            user_file = self.user_themes_dir / f"{theme_name}.yaml"

            if not bundled_file.exists():
                return False

            if user_file.exists() and not overwrite:
                return False

            # Ensure user directory exists
            user_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy theme file
            import shutil

            shutil.copy2(bundled_file, user_file)

            return True
        except Exception as e:
            print(f"Error importing theme {theme_name}: {e}")
            return False

    def update_theme(self, theme_name: str) -> bool:
        """Update a theme to latest bundled version.

        Args:
            theme_name: Theme name to update

        Returns:
            True if successful
        """
        return self.import_theme(theme_name, overwrite=True)

    def import_all_new_themes(self) -> int:
        """Import all new bundled themes.

        Returns:
            Number of themes imported
        """
        new_themes, _, _ = self.check_for_theme_updates()
        count = 0

        for theme_name in new_themes:
            if self.import_theme(theme_name):
                count += 1

        return count
