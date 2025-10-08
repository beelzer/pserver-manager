"""Configuration loader for games and servers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pserver_manager.models import Game, GameVersion, Server, ServerStatus


class ColumnDefinition:
    """Table column definition."""

    def __init__(self, id: str, label: str, width: str):
        """Initialize column definition.

        Args:
            id: Column identifier
            label: Column display label
            width: Column width ('stretch' or 'content')
        """
        self.id = id
        self.label = label
        self.width = width


class GameDefinition:
    """Game definition loaded from YAML."""

    def __init__(self, data: dict[str, Any]):
        """Initialize game definition.

        Args:
            data: Game definition data from YAML
        """
        self.id: str = data["id"]
        self.name: str = data["name"]
        self.icon: str = data.get("icon", "")
        self.reddit: str = data.get("reddit", "")
        self.updates_url: str = data.get("updates_url", "")
        self.updates_is_rss: bool = data.get("updates_is_rss", False)
        self.updates_use_js: bool = data.get("updates_use_js", False)
        self.updates_selectors: dict[str, str] = data.get("updates_selectors", {})
        self.updates_max_dropdown_options: int | None = data.get("updates_max_dropdown_options")
        self.updates_forum_mode: bool = data.get("updates_forum_mode", False)
        self.updates_forum_pagination_selector: str = data.get("updates_forum_pagination_selector", ".ipsPagination_next")
        self.updates_forum_page_limit: int = data.get("updates_forum_page_limit", 1)
        self.versions: list[GameVersion] = [
            GameVersion(
                id=v["id"],
                name=v["name"],
                description=v.get("description", ""),
                icon=v.get("icon", ""),
            )
            for v in data.get("versions", [])
        ]
        self.columns: list[ColumnDefinition] = [
            ColumnDefinition(
                id=col["id"],
                label=col["label"],
                width=col["width"],
            )
            for col in data.get("table_columns", [])
        ]
        self.server_schema: list[dict[str, Any]] = data.get("server_schema", [])

    def to_game(self) -> Game:
        """Convert to Game model.

        Returns:
            Game instance
        """
        return Game(
            id=self.id,
            name=self.name,
            icon=self.icon,
            versions=self.versions,
        )


class ServerDefinition:
    """Server definition loaded from YAML."""

    def __init__(self, data: dict[str, Any], game_id: str | None = None):
        """Initialize server definition.

        Args:
            data: Server data from YAML
            game_id: Game ID (if not in data, will be inferred from directory)
        """
        self.data = data
        # If game_id not in YAML, use the one passed from directory structure
        self.game_id: str = data.get("game_id", game_id or "")
        # Server ID is scoped to game (e.g., "retro" becomes "wow.retro")
        self.id: str = f"{self.game_id}.{data['id']}"
        self.name: str = data["name"]
        self.host: str = data.get("host", "")
        self.patchlist: str = data.get("patchlist", "")
        self.version_id: str = data["version_id"]
        self.status: ServerStatus = ServerStatus(data.get("status", "offline"))
        self.players: int = data.get("players", -1)
        self.max_players: int = data.get("max_players", 0)
        self.alliance_count: int | None = None  # Populated by player count scraping
        self.horde_count: int | None = None  # Populated by player count scraping
        self.uptime: str = data.get("uptime", "-")
        self.description: str = data.get("description", "")
        self.icon: str = data.get("icon", "")
        self.reddit: str = data.get("reddit", "")
        self.updates_url: str = data.get("updates_url", "")
        self.updates_is_rss: bool = data.get("updates_is_rss", False)
        self.updates_use_js: bool = data.get("updates_use_js", False)
        self.updates_selectors: dict[str, str] = data.get("updates_selectors", {})
        self.updates_max_dropdown_options: int | None = data.get("updates_max_dropdown_options")
        self.updates_forum_mode: bool = data.get("updates_forum_mode", False)
        self.updates_forum_pagination_selector: str = data.get("updates_forum_pagination_selector", ".ipsPagination_next")
        self.updates_forum_page_limit: int = data.get("updates_forum_page_limit", 1)
        self.ping_ms: int = -1  # -1 means not pinged yet

    def to_server(self) -> Server:
        """Convert to Server model.

        Returns:
            Server instance
        """
        # Parse host and port if needed (for backwards compatibility)
        host = self.host
        port = 0
        if ":" in self.host:
            parts = self.host.rsplit(":", 1)
            host = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                pass

        return Server(
            id=self.id,
            name=self.name,
            game_id=self.game_id,
            version_id=self.version_id,
            status=self.status,
            host=host,
            port=port,
            players=self.players,
            max_players=self.max_players,
            uptime=self.uptime,
            description=self.description,
        )

    def get_field(self, field_name: str, default: Any = "") -> Any:
        """Get a field value from the server data.

        Args:
            field_name: Field name to retrieve
            default: Default value if field not found

        Returns:
            Field value
        """
        return self.data.get(field_name, default)


class ConfigLoader:
    """Loads game and server configurations from YAML files."""

    def __init__(self, config_dir: Path, servers_dir: Path | None = None):
        """Initialize config loader.

        Args:
            config_dir: Root configuration directory (for game definitions)
            servers_dir: Server configurations directory (defaults to config_dir/servers)
        """
        self.config_dir = config_dir
        self.games_dir = config_dir / "games"
        self.servers_dir = servers_dir if servers_dir else config_dir / "servers"

    def load_games(self) -> list[GameDefinition]:
        """Load all game definitions.

        Returns:
            List of game definitions
        """
        games = []
        if not self.games_dir.exists():
            return games

        for yaml_file in self.games_dir.glob("*.yaml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                games.append(GameDefinition(data))

        return sorted(games, key=lambda g: g.name)

    def load_servers(self) -> list[ServerDefinition]:
        """Load all server definitions.

        Returns:
            List of server definitions
        """
        servers = []
        if not self.servers_dir.exists():
            return servers

        # Load from game-specific subdirectories (e.g., servers/wow/*.yaml)
        for game_dir in self.servers_dir.iterdir():
            if game_dir.is_dir():
                game_id = game_dir.name  # Infer game_id from directory name
                for yaml_file in game_dir.glob("*.yaml"):
                    with open(yaml_file, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        servers.append(ServerDefinition(data, game_id=game_id))

        return servers

    def get_game_by_id(self, game_id: str, games: list[GameDefinition]) -> GameDefinition | None:
        """Get game definition by ID.

        Args:
            game_id: Game ID to find
            games: List of game definitions

        Returns:
            Game definition or None if not found
        """
        for game in games:
            if game.id == game_id:
                return game
        return None
