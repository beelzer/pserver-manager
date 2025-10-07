"""
Executes server JAR files and monitors their output.
"""

import subprocess
import threading
import time
import re
from pathlib import Path
from typing import Optional, Set, Callable
from queue import Queue

from .detector import LaunchConfig
from .network_monitor import NetworkMonitor


class ServerExecutor:
    """Executes a server and captures its output."""

    def __init__(self, config: LaunchConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.output_queue = Queue()
        self.running = False
        self.network_monitor: Optional[NetworkMonitor] = None

    def start(self) -> bool:
        """Start the server process."""
        try:
            cmd = self.config.to_command()
            print(f"Launching: {' '.join(cmd)}")
            print(f"Working directory: {self.config.working_dir}")

            self.process = subprocess.Popen(
                cmd,
                cwd=str(self.config.working_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            self.running = True

            # Start threads to capture output
            threading.Thread(target=self._capture_output, args=(self.process.stdout,), daemon=True).start()
            threading.Thread(target=self._capture_output, args=(self.process.stderr,), daemon=True).start()

            # Initialize network monitor
            self.network_monitor = NetworkMonitor(self.process.pid)
            print(f"Monitoring network connections for PID: {self.process.pid}")

            return True

        except Exception as e:
            print(f"Error starting server: {e}")
            return False

    def _capture_output(self, stream):
        """Capture output from a stream."""
        try:
            for line in stream:
                if line:
                    self.output_queue.put(line.rstrip('\n'))
        except Exception:
            pass

    def monitor(self, callback: Callable[[str], None], timeout: int = 30) -> None:
        """
        Monitor server output and network connections, calling callback for each line.
        Stops after timeout seconds or when server stops.
        """
        start_time = time.time()
        last_network_check = 0

        print("\nMonitoring output and network connections...")
        print("(If a dialog appears, please interact with it manually)")

        while self.running and (time.time() - start_time) < timeout:
            try:
                # Check if process has terminated
                if self.process and self.process.poll() is not None:
                    print("Server process terminated")
                    break

                # Get output with timeout
                try:
                    while not self.output_queue.empty():
                        line = self.output_queue.get_nowait()
                        callback(line)
                except:
                    pass

                # Check network connections every second
                current_time = time.time()
                if self.network_monitor and (current_time - last_network_check) >= 1.0:
                    self.network_monitor.update()
                    last_network_check = current_time

                time.sleep(0.1)

            except KeyboardInterrupt:
                break

    def stop(self):
        """Stop the server process."""
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                try:
                    self.process.kill()
                except:
                    pass

    def get_network_hosts(self) -> Set[str]:
        """Get all detected remote hosts from network monitoring."""
        if self.network_monitor:
            return self.network_monitor.get_all_remote_hosts()
        return set()

    def get_game_servers(self) -> Set[str]:
        """Get likely game server connections."""
        if self.network_monitor:
            return self.network_monitor.get_game_servers()
        return set()

    def get_web_resources(self) -> Set[str]:
        """Get likely web/CDN connections."""
        if self.network_monitor:
            return self.network_monitor.get_web_resources()
        return set()


class OutputAnalyzer:
    """Analyzes server output to extract domains and IPs."""

    # Regex patterns for finding domains and IPs
    DOMAIN_PATTERN = re.compile(
        r'(?:(?:http|https|ftp)://)?'
        r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*'
        r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
        r'\.(?:com|net|org|io|gg|co|us|uk|ca|de|fr|eu|xyz|online|pro|me)'
        r'(?::[0-9]{1,5})?'
        r'(?:/[^\s]*)?',
        re.IGNORECASE
    )

    IP_PATTERN = re.compile(
        r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        r'(?::[0-9]{1,5})?'
    )

    # Common server-related keywords that might appear near domains/IPs
    SERVER_KEYWORDS = [
        'server', 'world', 'host', 'address', 'connecting', 'connection',
        'bind', 'listening', 'port', 'url', 'config', 'endpoint'
    ]

    def __init__(self):
        self.domains: Set[str] = set()
        self.ips: Set[str] = set()
        self.output_lines: list = []

    def analyze_line(self, line: str) -> None:
        """Analyze a single line of output."""
        self.output_lines.append(line)
        print(f"[SERVER] {line}")

        # Extract domains
        for match in self.DOMAIN_PATTERN.finditer(line):
            domain = match.group(0)
            # Filter out obvious false positives
            if self._is_valid_domain(domain):
                self.domains.add(domain)
                print(f"[DETECTED] Domain: {domain}")

        # Extract IPs
        for match in self.IP_PATTERN.finditer(line):
            ip = match.group(0)
            # Filter out localhost and common false positives
            if self._is_valid_ip(ip):
                self.ips.add(ip)
                print(f"[DETECTED] IP: {ip}")

    def _is_valid_domain(self, domain: str) -> bool:
        """Check if a domain looks legitimate."""
        # Remove protocol
        domain = re.sub(r'^(?:https?|ftp)://', '', domain)

        # Filter out common false positives
        if domain.lower().startswith('example.'):
            return False
        if 'localhost' in domain.lower():
            return False
        if domain.lower().startswith('127.'):
            return False

        # Must have at least one dot
        if '.' not in domain:
            return False

        # Check if domain has valid TLD
        parts = domain.split('/')
        host = parts[0].split(':')[0]
        if len(host.split('.')) < 2:
            return False

        return True

    def _is_valid_ip(self, ip: str) -> bool:
        """Check if an IP looks legitimate."""
        # Remove port if present
        ip_only = ip.split(':')[0]

        # Filter out localhost and private IPs for now
        # (though we may want to keep private IPs in some cases)
        if ip_only.startswith('127.'):
            return False
        if ip_only.startswith('0.0.0.'):
            return False
        if ip_only == '0.0.0.0':
            return False

        return True

    def get_results(self) -> dict:
        """Get analysis results."""
        return {
            'domains': sorted(list(self.domains)),
            'ips': sorted(list(self.ips)),
            'output_lines': self.output_lines
        }

    def get_primary_domain(self) -> Optional[str]:
        """Get the most likely primary domain."""
        if not self.domains:
            return None

        # Prefer domains with server-related context
        for domain in self.domains:
            domain_lower = domain.lower()
            for keyword in self.SERVER_KEYWORDS:
                # Check if this domain appeared near server keywords
                for line in self.output_lines:
                    if domain in line and keyword in line.lower():
                        return domain

        # Otherwise return the first domain found
        return sorted(list(self.domains))[0]
