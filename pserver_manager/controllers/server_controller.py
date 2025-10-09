"""Server controller for coordinating server operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from pserver_manager.config_loader import GameDefinition, ServerDefinition
    from pserver_manager.services.server_service import ServerService
    from pserver_manager.services.cache_service import CacheService
    from qtframework.widgets.advanced import NotificationManager


class ServerController(QObject):
    """Controller for coordinating server operations between UI and services."""

    # Signals
    servers_loaded = Signal(list, list)  # game_defs, server_defs
    server_deleted = Signal(str)  # server_id

    def __init__(
        self,
        server_service: ServerService,
        cache_service: CacheService,
        notifications: NotificationManager,
    ) -> None:
        """Initialize server controller.

        Args:
            server_service: Server service instance
            cache_service: Cache service instance
            notifications: Notification manager
        """
        super().__init__()
        self._server_service = server_service
        self._cache_service = cache_service
        self._notifications = notifications
        self._current_game: GameDefinition | None = None
        self._current_server: ServerDefinition | None = None

    def load_servers(self) -> tuple[list[GameDefinition], list[ServerDefinition]]:
        """Load all games and servers.

        Returns:
            Tuple of (game_definitions, server_definitions)
        """
        game_defs, server_defs = self._server_service.load_all()
        self.servers_loaded.emit(game_defs, server_defs)
        return game_defs, server_defs

    def reload_servers(self) -> None:
        """Reload all servers and emit signal."""
        self._server_service.reload()
        game_defs = self._server_service.get_games()
        server_defs = self._server_service.get_servers()
        self.servers_loaded.emit(game_defs, server_defs)

    def get_game_by_id(self, game_id: str) -> GameDefinition | None:
        """Get game definition by ID.

        Args:
            game_id: Game ID

        Returns:
            Game definition or None
        """
        return self._server_service.get_game_by_id(game_id)

    def get_server_by_id(self, server_id: str) -> ServerDefinition | None:
        """Get server definition by ID.

        Args:
            server_id: Server ID

        Returns:
            Server definition or None
        """
        return self._server_service.get_server_by_id(server_id)

    def delete_server(self, server_id: str) -> bool:
        """Delete a server.

        Args:
            server_id: Server ID to delete

        Returns:
            True if deleted successfully
        """
        server = self.get_server_by_id(server_id)
        if not server:
            self._notifications.error("Server Not Found", f"Could not find server: {server_id}")
            return False

        if self._server_service.delete_server(server_id):
            self._cache_service.clear_server_cache(server_id)
            self._notifications.success("Server Deleted", f"'{server.name}' deleted successfully")
            self.server_deleted.emit(server_id)
            return True
        else:
            self._notifications.error("Delete Failed", "Server configuration file not found")
            return False

    def filter_servers_by_game(
        self, game_id: str, version_id: str | None = None
    ) -> list[ServerDefinition]:
        """Filter servers by game and optionally by version.

        Args:
            game_id: Game ID to filter by
            version_id: Optional version ID to filter by

        Returns:
            List of filtered server definitions
        """
        return self._server_service.filter_servers_by_game(game_id, version_id)

    def set_current_game(self, game: GameDefinition | None) -> None:
        """Set the currently selected game.

        Args:
            game: Game definition or None
        """
        self._current_game = game

    def set_current_server(self, server: ServerDefinition | None) -> None:
        """Set the currently selected server.

        Args:
            server: Server definition or None
        """
        self._current_server = server

    def get_current_game(self) -> GameDefinition | None:
        """Get the currently selected game.

        Returns:
            Current game definition or None
        """
        return self._current_game

    def get_current_server(self) -> ServerDefinition | None:
        """Get the currently selected server.

        Returns:
            Current server definition or None
        """
        return self._current_server

    def get_all_servers(self) -> list[ServerDefinition]:
        """Get all loaded servers.

        Returns:
            List of all server definitions
        """
        return self._server_service.get_servers()

    def get_all_games(self) -> list[GameDefinition]:
        """Get all loaded games.

        Returns:
            List of all game definitions
        """
        return self._server_service.get_games()

    def open_server_url(self, server_id: str, url_field: str) -> bool:
        """Open a URL associated with a server.

        Args:
            server_id: Server ID
            url_field: Field name containing the URL (e.g., 'register_url', 'login_url')

        Returns:
            True if URL was opened, False otherwise
        """
        import webbrowser

        server = self.get_server_by_id(server_id)
        if not server:
            return False

        url = server.get_field(url_field, "")
        if url:
            webbrowser.open(url)
            return True
        return False
