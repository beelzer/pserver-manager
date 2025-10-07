"""
Network monitoring to detect server connections.
"""

import subprocess
import re
import time
from typing import Set, Dict, Optional
from dataclasses import dataclass


@dataclass
class Connection:
    """Represents a network connection."""
    local_addr: str
    local_port: int
    remote_addr: str
    remote_port: int
    state: str

    def __hash__(self):
        return hash((self.remote_addr, self.remote_port))

    def is_likely_game_server(self) -> bool:
        """Check if this connection is likely a game server (not web/CDN)."""
        # Common game server ports
        game_ports = {
            43594,  # RuneScape private servers
            43595, 43596, 43597,  # Other common RS ports
            50000, 50001, 50002,  # WoW-style ports
            7777, 7778,  # Other game server ports
        }

        # Check if exact port match
        if self.remote_port in game_ports:
            return True

        # Check if port is in common game server ranges
        if 40000 <= self.remote_port <= 50000:
            return True

        # Web/CDN ports are unlikely to be game servers
        web_ports = {80, 443, 8080, 8443}
        if self.remote_port in web_ports:
            return False

        # High ports (ephemeral range) are more likely game servers
        if self.remote_port > 30000:
            return True

        return False


class NetworkMonitor:
    """Monitors network connections for a process."""

    def __init__(self, process_id: int):
        self.process_id = process_id
        self.connections: Set[Connection] = set()
        self.remote_hosts: Set[str] = set()
        self.game_servers: Set[str] = set()
        self.web_resources: Set[str] = set()

    def get_connections_windows(self) -> Set[Connection]:
        """Get active connections using netstat on Windows."""
        try:
            # Use netstat to get connections for the process
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                timeout=5
            )

            connections = set()
            for line in result.stdout.split('\n'):
                if str(self.process_id) not in line:
                    continue

                # Parse netstat output
                # Format: TCP    127.0.0.1:50123        1.2.3.4:43594     ESTABLISHED     12345
                parts = line.split()
                if len(parts) < 5:
                    continue

                protocol = parts[0]
                if protocol not in ['TCP', 'UDP']:
                    continue

                try:
                    local = parts[1].rsplit(':', 1)
                    remote = parts[2].rsplit(':', 1)

                    if len(local) == 2 and len(remote) == 2:
                        conn = Connection(
                            local_addr=local[0],
                            local_port=int(local[1]),
                            remote_addr=remote[0],
                            remote_port=int(remote[1]),
                            state=parts[3] if len(parts) > 3 else 'UNKNOWN'
                        )
                        connections.add(conn)
                except (ValueError, IndexError):
                    continue

            return connections

        except Exception as e:
            print(f"Error monitoring network: {e}")
            return set()

    def get_connections_unix(self) -> Set[Connection]:
        """Get active connections using lsof on Unix systems."""
        try:
            # Use lsof to get connections for the process
            result = subprocess.run(
                ['lsof', '-p', str(self.process_id), '-i', '-n', '-P'],
                capture_output=True,
                text=True,
                timeout=5
            )

            connections = set()
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if not line.strip():
                    continue

                parts = line.split()
                if len(parts) < 9:
                    continue

                # Extract connection info
                # Format: java 12345 user 123u IPv4 0x... 0t0 TCP 127.0.0.1:50123->1.2.3.4:43594 (ESTABLISHED)
                if '->' in line:
                    conn_str = parts[8]
                    try:
                        local, remote = conn_str.split('->')
                        local_parts = local.rsplit(':', 1)
                        remote_parts = remote.rsplit(':', 1)

                        if len(local_parts) == 2 and len(remote_parts) == 2:
                            conn = Connection(
                                local_addr=local_parts[0],
                                local_port=int(local_parts[1]),
                                remote_addr=remote_parts[0],
                                remote_port=int(remote_parts[1]),
                                state=parts[9] if len(parts) > 9 else 'UNKNOWN'
                            )
                            connections.add(conn)
                    except (ValueError, IndexError):
                        continue

            return connections

        except Exception as e:
            print(f"Error monitoring network: {e}")
            return set()

    def monitor(self) -> Set[Connection]:
        """Monitor network connections (platform-aware)."""
        import platform

        if platform.system() == 'Windows':
            return self.get_connections_windows()
        else:
            return self.get_connections_unix()

    def update(self) -> Set[str]:
        """Update connection list and return new remote hosts."""
        new_connections = self.monitor()
        new_hosts = set()

        for conn in new_connections:
            if conn not in self.connections:
                # Filter out localhost and invalid IPs
                if self._is_valid_remote_host(conn.remote_addr):
                    host_str = f"{conn.remote_addr}:{conn.remote_port}"
                    self.remote_hosts.add(host_str)
                    new_hosts.add(host_str)

                    # Categorize connection
                    if conn.is_likely_game_server():
                        self.game_servers.add(host_str)
                        print(f"[GAME SERVER] New connection: {conn.remote_addr}:{conn.remote_port} ({conn.state})")
                    else:
                        self.web_resources.add(host_str)
                        print(f"[WEB/CDN] New connection: {conn.remote_addr}:{conn.remote_port} ({conn.state})")

        self.connections = new_connections
        return new_hosts

    def _is_valid_remote_host(self, addr: str) -> bool:
        """Check if a remote host is valid (not localhost, etc.)."""
        # Filter out localhost
        if addr.startswith('127.') or addr == '::1':
            return False

        # Filter out 0.0.0.0
        if addr == '0.0.0.0' or addr == '::':
            return False

        # Filter out broadcast
        if addr == '255.255.255.255':
            return False

        return True

    def get_all_remote_hosts(self) -> Set[str]:
        """Get all detected remote hosts."""
        return self.remote_hosts

    def get_game_servers(self) -> Set[str]:
        """Get likely game server connections (filtered by port heuristics)."""
        return self.game_servers

    def get_web_resources(self) -> Set[str]:
        """Get likely web/CDN connections."""
        return self.web_resources
