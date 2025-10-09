"""Update service for checking bundled configuration updates."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pserver_manager.utils import ServerUpdateChecker

if TYPE_CHECKING:
    from pserver_manager.utils.paths import AppPaths
    from pserver_manager.utils.updates import UpdateInfo


class UpdateService:
    """Service for managing bundled configuration updates."""

    def __init__(self, app_paths: AppPaths) -> None:
        """Initialize update service.

        Args:
            app_paths: Application paths manager
        """
        self._app_paths = app_paths

        # Initialize update checker
        bundled_servers_dir = Path(__file__).parent.parent / "config" / "servers"
        user_servers_dir = app_paths.get_servers_dir()
        bundled_themes_dir = Path(__file__).parent.parent / "themes"
        user_themes_dir = app_paths.get_themes_dir()

        self._update_checker = ServerUpdateChecker(
            bundled_servers_dir, user_servers_dir, bundled_themes_dir, user_themes_dir
        )

    def check_for_updates(self) -> UpdateInfo:
        """Check for available updates.

        Returns:
            UpdateInfo object with available updates
        """
        return self._update_checker.check_for_updates()

    def has_updates(self, update_info: UpdateInfo) -> bool:
        """Check if there are any updates available.

        Args:
            update_info: UpdateInfo object to check

        Returns:
            True if updates are available, False otherwise
        """
        return (
            len(update_info.new_servers) > 0
            or len(update_info.updated_servers) > 0
            or len(update_info.removed_servers) > 0
            or len(update_info.conflicts) > 0
            or len(update_info.new_themes) > 0
            or len(update_info.updated_themes) > 0
            or len(update_info.theme_conflicts) > 0
        )

    def import_all_new_servers(self) -> int:
        """Import all new bundled servers.

        Returns:
            Number of servers imported
        """
        return self._update_checker.import_all_new_servers()

    def import_all_new_themes(self) -> int:
        """Import all new bundled themes.

        Returns:
            Number of themes imported
        """
        return self._update_checker.import_all_new_themes()

    def is_first_run(self) -> bool:
        """Check if this is the first run (no user servers exist).

        Returns:
            True if first run, False otherwise
        """
        user_servers_dir = self._app_paths.get_servers_dir()
        existing_files = list(user_servers_dir.rglob("*.yaml"))
        return len(existing_files) == 0

    def get_update_checker(self) -> ServerUpdateChecker:
        """Get the underlying update checker instance.

        Returns:
            ServerUpdateChecker instance
        """
        return self._update_checker
