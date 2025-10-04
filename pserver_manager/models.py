"""Data models for PServer Manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ServerStatus(Enum):
    """Server status enumeration."""

    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    STARTING = "starting"


@dataclass
class GameVersion:
    """Represents a game version or expansion."""

    id: str
    name: str
    description: str = ""


@dataclass
class Game:
    """Represents a game."""

    id: str
    name: str
    icon: str = ""
    versions: list[GameVersion] = field(default_factory=list)


@dataclass
class Server:
    """Represents a game server."""

    id: str
    name: str
    game_id: str
    version_id: str
    status: ServerStatus
    host: str
    port: int
    players: int = 0
    max_players: int = 0
    uptime: str = "0h 0m"
    description: str = ""

    @property
    def player_count(self) -> str:
        """Get formatted player count."""
        return f"{self.players}/{self.max_players}"

    @property
    def address(self) -> str:
        """Get full server address."""
        return f"{self.host}:{self.port}"
