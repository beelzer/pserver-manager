"""Theme controller for managing theme operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from qtframework import Application
    from qtframework.config import ConfigManager
    from pserver_manager.utils.paths import AppPaths
    from qtframework.widgets.advanced import NotificationManager


class ThemeController(QObject):
    """Controller for managing theme operations."""

    def __init__(
        self,
        application: Application,
        config_manager: ConfigManager,
        app_paths: AppPaths,
        notifications: NotificationManager,
    ) -> None:
        """Initialize theme controller.

        Args:
            application: Application instance
            config_manager: Configuration manager
            app_paths: Application paths
            notifications: Notification manager
        """
        super().__init__()
        self._application = application
        self._config_manager = config_manager
        self._app_paths = app_paths
        self._notifications = notifications
        self._theme_manager = application.theme_manager

    def apply_theme(self, theme_name: str) -> None:
        """Apply a theme and save to config.

        Args:
            theme_name: Theme name to apply
        """
        self._theme_manager.set_theme(theme_name)
        self._config_manager.set("ui.theme", theme_name)
        config_file = self._app_paths.get_settings_file()
        self._config_manager.save(config_file)

    def get_current_theme_name(self) -> str | None:
        """Get the current theme name.

        Returns:
            Current theme name or None
        """
        current_theme = self._theme_manager.get_current_theme()
        return current_theme.name if current_theme else None

    def list_themes(self) -> list[str]:
        """Get list of available theme names.

        Returns:
            List of theme names
        """
        return self._theme_manager.list_themes()

    def get_theme_info(self, theme_name: str) -> dict | None:
        """Get theme information.

        Args:
            theme_name: Theme name

        Returns:
            Theme info dict or None
        """
        return self._theme_manager.get_theme_info(theme_name)

    def reload_themes(self) -> None:
        """Reload all themes from disk."""
        try:
            from PySide6.QtWidgets import QApplication

            # Get current theme name
            current_theme = self._config_manager.get("ui.theme", "auto")

            # Get application instance
            app = QApplication.instance()
            if not app:
                return

            # Reload themes in theme manager
            self._theme_manager.reload_themes()

            # Reapply current theme
            self._theme_manager.set_theme(current_theme)

            # Regenerate and apply stylesheet
            stylesheet = self._theme_manager.get_stylesheet()
            app.setStyleSheet(stylesheet)

        except Exception as e:
            self._notifications.error("Theme Reload Failed", f"Error: {str(e)}")

    def get_saved_theme(self) -> str:
        """Get the saved theme from config.

        Returns:
            Saved theme name
        """
        return self._config_manager.get("ui.theme", "nord")
