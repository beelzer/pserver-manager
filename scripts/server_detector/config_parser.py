"""
Parses configuration files to extract server addresses.
"""

import re
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Set, Dict, List


class ConfigParser:
    """Parses various config file formats for server addresses."""

    # Common config file patterns
    CONFIG_PATTERNS = [
        "**/*.xml",
        "**/*.json",
        "**/*.properties",
        "**/*.cfg",
        "**/*.conf",
        "**/*.ini",
        "**/*.yaml",
        "**/*.yml",
        "**/config.*",
        "**/server.*",
    ]

    # Regex patterns for finding addresses
    ADDRESS_PATTERNS = [
        r'(?:server|host|address|ip|world)[\s=:]+([a-zA-Z0-9.-]+(?:\.[a-zA-Z]{2,}|:\d+))',
        r'(?:url|endpoint)[\s=:]+(?:https?://)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'<(?:server|host|address|url)>([^<]+)</(?:server|host|address|url)>',
    ]

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)

    def find_addresses(self) -> Set[str]:
        """Find all server addresses in config files."""
        addresses = set()

        # Find all config files
        config_files = self._find_config_files()

        for config_file in config_files:
            try:
                file_addresses = self._parse_file(config_file)
                addresses.update(file_addresses)
            except Exception as e:
                # Silently skip files that can't be parsed
                pass

        return addresses

    def _find_config_files(self) -> List[Path]:
        """Find all potential config files."""
        files = []
        for pattern in self.CONFIG_PATTERNS:
            files.extend(self.base_dir.glob(pattern))
        return files

    def _parse_file(self, file_path: Path) -> Set[str]:
        """Parse a single config file."""
        addresses = set()

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')

            # Try format-specific parsing first
            if file_path.suffix == '.json':
                addresses.update(self._parse_json(content))
            elif file_path.suffix == '.xml':
                addresses.update(self._parse_xml(content))
            elif file_path.suffix in ['.yaml', '.yml']:
                addresses.update(self._parse_yaml(content))
            elif file_path.suffix in ['.properties', '.ini', '.cfg', '.conf']:
                addresses.update(self._parse_properties(content))

            # Always do regex parsing as fallback
            addresses.update(self._parse_regex(content))

        except Exception:
            pass

        # Filter valid addresses
        return {addr for addr in addresses if self._is_valid_address(addr)}

    def _parse_json(self, content: str) -> Set[str]:
        """Parse JSON config files."""
        addresses = set()
        try:
            data = json.loads(content)
            addresses.update(self._extract_from_dict(data))
        except:
            pass
        return addresses

    def _parse_xml(self, content: str) -> Set[str]:
        """Parse XML config files."""
        addresses = set()
        try:
            root = ET.fromstring(content)
            for elem in root.iter():
                if elem.tag.lower() in ['server', 'host', 'address', 'url', 'endpoint']:
                    if elem.text:
                        addresses.add(elem.text.strip())
                for attr_value in elem.attrib.values():
                    if self._looks_like_address(attr_value):
                        addresses.add(attr_value)
        except:
            pass
        return addresses

    def _parse_yaml(self, content: str) -> Set[str]:
        """Parse YAML config files (basic, no external deps)."""
        addresses = set()
        # Simple key-value parsing
        for line in content.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key_lower = key.strip().lower()
                if any(kw in key_lower for kw in ['server', 'host', 'address', 'url']):
                    val = value.strip().strip('"\'')
                    if self._looks_like_address(val):
                        addresses.add(val)
        return addresses

    def _parse_properties(self, content: str) -> Set[str]:
        """Parse .properties/.ini/.cfg files."""
        addresses = set()
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith(';'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key_lower = key.strip().lower()
                if any(kw in key_lower for kw in ['server', 'host', 'address', 'url', 'ip']):
                    val = value.strip().strip('"\'')
                    if self._looks_like_address(val):
                        addresses.add(val)
        return addresses

    def _parse_regex(self, content: str) -> Set[str]:
        """Use regex patterns to find addresses."""
        addresses = set()
        for pattern in self.ADDRESS_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                addr = match.group(1).strip()
                if self._looks_like_address(addr):
                    addresses.add(addr)
        return addresses

    def _extract_from_dict(self, data: dict, addresses: Set[str] = None) -> Set[str]:
        """Recursively extract addresses from dict/list structures."""
        if addresses is None:
            addresses = set()

        if isinstance(data, dict):
            for key, value in data.items():
                key_lower = str(key).lower()
                if any(kw in key_lower for kw in ['server', 'host', 'address', 'url', 'ip']):
                    if isinstance(value, str) and self._looks_like_address(value):
                        addresses.add(value)
                if isinstance(value, (dict, list)):
                    self._extract_from_dict(value, addresses)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    self._extract_from_dict(item, addresses)
                elif isinstance(item, str) and self._looks_like_address(item):
                    addresses.add(item)

        return addresses

    def _looks_like_address(self, text: str) -> bool:
        """Check if text looks like a server address."""
        if not text or len(text) < 4:
            return False

        # Remove common prefixes
        text = re.sub(r'^(?:https?|ftp)://', '', text)

        # Check for domain or IP
        if '.' in text:
            # Could be domain or IP
            parts = text.split(':')[0].split('.')
            if len(parts) >= 2:
                return True

        return False

    def _is_valid_address(self, addr: str) -> bool:
        """Validate an address."""
        if not addr:
            return False

        # Filter out common false positives
        addr_lower = addr.lower()
        if any(x in addr_lower for x in ['example.', 'localhost', '127.0.0.1', '0.0.0.0']):
            return False

        # Must have domain or IP format
        return self._looks_like_address(addr)
