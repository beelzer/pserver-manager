"""Path management for PServer Manager.

Handles user data directories following OS conventions:
- Documents/PServer Manager - User-editable server configs
- AppData/Local/PServerManager - App settings and cache
- Portable mode - Use app install directory if portable.txt exists
"""

from __future__ import annotations

import sys
from pathlib import Path


class AppPaths:
    """Manages application paths following OS conventions."""

    APP_NAME = "PServer Manager"
    APP_NAME_NO_SPACE = "PServerManager"

    def __init__(self) -> None:
        """Initialize application paths."""
        self._portable_mode = self._detect_portable_mode()
        self._base_paths = self._get_base_paths()

    def _detect_portable_mode(self) -> bool:
        """Check if running in portable mode.

        Returns:
            True if portable.txt exists in app directory
        """
        app_dir = self.get_app_install_dir()
        portable_marker = app_dir / "portable.txt"
        return portable_marker.exists()

    def _get_base_paths(self) -> dict[str, Path]:
        """Get base paths based on OS and portable mode.

        Returns:
            Dictionary of base paths
        """
        if self._portable_mode:
            # Portable mode - everything in app directory
            base = self.get_app_install_dir()
            return {
                "user_data": base / "data",
                "app_data": base / "data",
            }

        # Standard mode - use OS conventions
        if sys.platform == "win32":
            # Windows paths
            import os

            documents = Path(os.path.expandvars(r"%USERPROFILE%\Documents"))
            appdata = Path(os.path.expandvars(r"%LOCALAPPDATA%"))

            return {
                "user_data": documents / self.APP_NAME,
                "app_data": appdata / self.APP_NAME_NO_SPACE,
            }
        elif sys.platform == "darwin":
            # macOS paths
            home = Path.home()
            return {
                "user_data": home / "Documents" / self.APP_NAME,
                "app_data": home / "Library" / "Application Support" / self.APP_NAME_NO_SPACE,
            }
        else:
            # Linux/Unix paths (XDG)
            import os

            home = Path.home()
            xdg_data = os.environ.get("XDG_DATA_HOME", str(home / ".local" / "share"))
            xdg_config = os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))

            return {
                "user_data": Path(xdg_data) / self.APP_NAME_NO_SPACE,
                "app_data": Path(xdg_config) / self.APP_NAME_NO_SPACE,
            }

    @staticmethod
    def get_app_install_dir() -> Path:
        """Get the application installation directory.

        Returns:
            Path to app install directory
        """
        if getattr(sys, "frozen", False):
            # Running as compiled exe
            return Path(sys.executable).parent
        else:
            # Running from source
            return Path(__file__).parent.parent.parent

    def get_user_data_dir(self) -> Path:
        """Get user data directory (Documents/PServer Manager).

        This is where users can manually edit server configs.

        Returns:
            Path to user data directory
        """
        return self._base_paths["user_data"]

    def get_app_data_dir(self) -> Path:
        """Get app data directory (AppData/Local/PServerManager).

        This is for app-managed settings and cache.

        Returns:
            Path to app data directory
        """
        return self._base_paths["app_data"]

    def get_servers_dir(self) -> Path:
        """Get servers configuration directory.

        Returns:
            Path to servers directory (in user data)
        """
        return self.get_user_data_dir() / "servers"

    def get_settings_file(self) -> Path:
        """Get settings file path.

        Returns:
            Path to settings.yaml (in app data)
        """
        return self.get_app_data_dir() / "settings.yaml"

    def get_cache_dir(self) -> Path:
        """Get cache directory.

        Returns:
            Path to cache directory (in app data)
        """
        return self.get_app_data_dir() / "cache"

    def get_logs_dir(self) -> Path:
        """Get logs directory.

        Returns:
            Path to logs directory (in app data)
        """
        return self.get_app_data_dir() / "logs"

    def get_themes_dir(self) -> Path:
        """Get custom themes directory.

        Returns:
            Path to themes directory (in user data)
        """
        return self.get_user_data_dir() / "themes"

    def get_icons_dir(self) -> Path:
        """Get icons directory.

        Returns:
            Path to icons directory (in user data)
        """
        return self.get_user_data_dir() / "icons"

    def ensure_directories(self) -> None:
        """Create all necessary directories if they don't exist."""
        dirs_to_create = [
            self.get_user_data_dir(),
            self.get_app_data_dir(),
            self.get_servers_dir(),
            self.get_cache_dir(),
            self.get_logs_dir(),
            self.get_themes_dir(),
            self.get_icons_dir(),
        ]

        for directory in dirs_to_create:
            directory.mkdir(parents=True, exist_ok=True)

    def is_portable_mode(self) -> bool:
        """Check if running in portable mode.

        Returns:
            True if portable mode
        """
        return self._portable_mode

    def enable_portable_mode(self) -> None:
        """Enable portable mode by creating portable.txt marker."""
        marker_file = self.get_app_install_dir() / "portable.txt"
        marker_file.write_text("Portable mode enabled for PServer Manager\n")
        # Reinitialize paths
        self._portable_mode = True
        self._base_paths = self._get_base_paths()

    def disable_portable_mode(self) -> None:
        """Disable portable mode by removing portable.txt marker."""
        marker_file = self.get_app_install_dir() / "portable.txt"
        if marker_file.exists():
            marker_file.unlink()
        # Reinitialize paths
        self._portable_mode = False
        self._base_paths = self._get_base_paths()

    def migrate_old_config(self, old_config_dir: Path) -> bool:
        """Migrate old config structure to new paths.

        Args:
            old_config_dir: Old config directory to migrate from

        Returns:
            True if migration was successful
        """
        if not old_config_dir.exists():
            return False

        try:
            import shutil

            # Ensure new directories exist
            self.ensure_directories()

            # Migrate servers
            old_servers = old_config_dir / "servers"
            if old_servers.exists():
                new_servers = self.get_servers_dir()
                for game_dir in old_servers.iterdir():
                    if game_dir.is_dir():
                        dest_game_dir = new_servers / game_dir.name
                        dest_game_dir.mkdir(parents=True, exist_ok=True)
                        for server_file in game_dir.glob("*.yaml"):
                            shutil.copy2(server_file, dest_game_dir / server_file.name)

            # Migrate icons from bundled assets to user directory
            bundled_assets_dir = self.get_app_install_dir() / "pserver_manager" / "assets"
            if bundled_assets_dir.exists():
                new_icons_dir = self.get_icons_dir()

                # Copy server icons
                bundled_servers_icons = bundled_assets_dir / "servers"
                if bundled_servers_icons.exists():
                    for game_icon_dir in bundled_servers_icons.iterdir():
                        if game_icon_dir.is_dir():
                            dest_game_icon_dir = new_icons_dir / "servers" / game_icon_dir.name
                            dest_game_icon_dir.mkdir(parents=True, exist_ok=True)
                            for icon_file in game_icon_dir.iterdir():
                                if icon_file.is_file():
                                    shutil.copy2(icon_file, dest_game_icon_dir / icon_file.name)

                # Copy game icons
                bundled_games_icons = bundled_assets_dir / "games"
                if bundled_games_icons.exists():
                    dest_games_dir = new_icons_dir / "games"
                    dest_games_dir.mkdir(parents=True, exist_ok=True)
                    for icon_file in bundled_games_icons.iterdir():
                        if icon_file.is_file():
                            shutil.copy2(icon_file, dest_games_dir / icon_file.name)

                # Copy version icons
                bundled_versions_icons = bundled_assets_dir / "versions"
                if bundled_versions_icons.exists():
                    dest_versions_dir = new_icons_dir / "versions"
                    dest_versions_dir.mkdir(parents=True, exist_ok=True)
                    for icon_file in bundled_versions_icons.iterdir():
                        if icon_file.is_file():
                            shutil.copy2(icon_file, dest_versions_dir / icon_file.name)

            # Migrate settings
            old_settings = old_config_dir / "settings.yaml"
            if old_settings.exists():
                shutil.copy2(old_settings, self.get_settings_file())

            return True
        except Exception as e:
            print(f"Migration failed: {e}")
            return False

    def get_path_info(self) -> dict[str, str]:
        """Get information about all paths.

        Returns:
            Dictionary with path descriptions and locations
        """
        return {
            "Mode": "Portable" if self._portable_mode else "Standard",
            "User Data (Servers)": str(self.get_user_data_dir()),
            "App Data (Settings)": str(self.get_app_data_dir()),
            "Servers Directory": str(self.get_servers_dir()),
            "Icons Directory": str(self.get_icons_dir()),
            "Settings File": str(self.get_settings_file()),
            "Cache Directory": str(self.get_cache_dir()),
            "Logs Directory": str(self.get_logs_dir()),
            "Themes Directory": str(self.get_themes_dir()),
        }


# Global instance
_app_paths: AppPaths | None = None


def get_app_paths() -> AppPaths:
    """Get the global AppPaths instance.

    Returns:
        AppPaths instance
    """
    global _app_paths
    if _app_paths is None:
        _app_paths = AppPaths()
    return _app_paths
