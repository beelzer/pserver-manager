"""Server service for managing server CRUD operations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pserver_manager.config_loader import ConfigLoader, GameDefinition, ServerDefinition

if TYPE_CHECKING:
    from pserver_manager.utils.paths import AppPaths


class ServerService:
    """Service for managing server CRUD operations."""

    def __init__(self, config_loader: ConfigLoader, app_paths: AppPaths) -> None:
        """Initialize server service.

        Args:
            config_loader: Configuration loader instance
            app_paths: Application paths manager
        """
        self._config_loader = config_loader
        self._app_paths = app_paths
        self._game_defs: list[GameDefinition] = []
        self._all_servers: list[ServerDefinition] = []

    def load_all(self) -> tuple[list[GameDefinition], list[ServerDefinition]]:
        """Load all games and servers from configuration.

        Returns:
            Tuple of (game_definitions, server_definitions)
        """
        self._game_defs = self._config_loader.load_games()
        self._all_servers = self._config_loader.load_servers()
        return self._game_defs, self._all_servers

    def get_games(self) -> list[GameDefinition]:
        """Get all loaded game definitions.

        Returns:
            List of game definitions
        """
        return self._game_defs

    def get_servers(self) -> list[ServerDefinition]:
        """Get all loaded server definitions.

        Returns:
            List of server definitions
        """
        return self._all_servers

    def get_game_by_id(self, game_id: str) -> GameDefinition | None:
        """Get game definition by ID.

        Args:
            game_id: Game ID to find

        Returns:
            Game definition or None if not found
        """
        return self._config_loader.get_game_by_id(game_id, self._game_defs)

    def get_server_by_id(self, server_id: str) -> ServerDefinition | None:
        """Get server definition by ID.

        Args:
            server_id: Server ID to find

        Returns:
            Server definition or None if not found
        """
        for server in self._all_servers:
            if server.id == server_id:
                return server
        return None

    def delete_server(self, server_id: str) -> bool:
        """Delete a server configuration file.

        Args:
            server_id: Server ID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        server = self.get_server_by_id(server_id)
        if not server:
            return False

        try:
            # Server files are in servers/{game_id}/{server_id}.yaml
            # server.id is like "wow.retro-wow", extract just "retro-wow"
            server_filename = server.id.split(".", 1)[1] if "." in server.id else server.id
            servers_dir = self._app_paths.get_servers_dir()
            server_file = servers_dir / server.game_id / f"{server_filename}.yaml"

            if server_file.exists():
                server_file.unlink()
                return True
            return False
        except Exception:
            return False

    def reload(self) -> None:
        """Reload all games and servers from configuration."""
        self.load_all()

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
        filtered = [s for s in self._all_servers if s.game_id == game_id]

        if version_id:
            filtered = [s for s in filtered if s.version_id == version_id]

        return filtered
