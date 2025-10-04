"""Server ping utility for checking WoW server status."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from pserver_manager.models import ServerStatus


if TYPE_CHECKING:
    from pserver_manager.config_loader import ServerDefinition


async def ping_server(server: ServerDefinition, timeout: float = 3.0) -> tuple[ServerStatus, int]:
    """Ping a WoW server to check if it's online and measure latency.

    Args:
        server: Server definition to ping
        timeout: Timeout in seconds

    Returns:
        Tuple of (ServerStatus, latency_ms) - latency is -1 if offline
    """
    if not server.host:
        return ServerStatus.OFFLINE, -1

    # Extract host and port
    host = server.host
    port = 3724  # Default WoW auth server port

    if ":" in host:
        parts = host.rsplit(":", 1)
        host = parts[0]
        try:
            port = int(parts[1])
        except ValueError:
            pass

    try:
        # Measure connection time
        start_time = time.perf_counter()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        end_time = time.perf_counter()

        writer.close()
        await writer.wait_closed()

        # Calculate latency in milliseconds
        latency_ms = int((end_time - start_time) * 1000)
        return ServerStatus.ONLINE, latency_ms
    except (asyncio.TimeoutError, OSError, ConnectionRefusedError):
        return ServerStatus.OFFLINE, -1


async def ping_multiple_servers(
    servers: list[ServerDefinition], timeout: float = 3.0
) -> dict[str, tuple[ServerStatus, int]]:
    """Ping multiple servers concurrently.

    Args:
        servers: List of server definitions to ping
        timeout: Timeout in seconds for each ping

    Returns:
        Dictionary mapping server IDs to (status, latency_ms) tuples
    """
    tasks = [ping_server(server, timeout) for server in servers]
    results = await asyncio.gather(*tasks)

    return {server.id: result for server, result in zip(servers, results)}


def ping_server_sync(server: ServerDefinition, timeout: float = 3.0) -> tuple[ServerStatus, int]:
    """Synchronous wrapper for pinging a server.

    Args:
        server: Server definition to ping
        timeout: Timeout in seconds

    Returns:
        Tuple of (ServerStatus, latency_ms)
    """
    try:
        return asyncio.run(ping_server(server, timeout))
    except RuntimeError:
        # If event loop is already running, create a new one
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(ping_server(server, timeout))
        finally:
            loop.close()


def ping_multiple_servers_sync(
    servers: list[ServerDefinition], timeout: float = 3.0
) -> dict[str, tuple[ServerStatus, int]]:
    """Synchronous wrapper for pinging multiple servers.

    Args:
        servers: List of server definitions to ping
        timeout: Timeout in seconds for each ping

    Returns:
        Dictionary mapping server IDs to (status, latency_ms) tuples
    """
    try:
        return asyncio.run(ping_multiple_servers(servers, timeout))
    except RuntimeError:
        # If event loop is already running, create a new one
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(ping_multiple_servers(servers, timeout))
        finally:
            loop.close()
