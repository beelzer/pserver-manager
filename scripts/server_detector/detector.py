"""
Detects launch configurations for RuneScape private server JAR files.
Scans for batch files, shell scripts, config files, and other launch requirements.
"""

import os
import re
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class LaunchConfig:
    """Configuration for launching a server JAR."""
    jar_path: Path
    java_args: List[str]
    main_class: Optional[str]
    config_url: Optional[str]
    working_dir: Path
    launch_script: Optional[Path]

    def to_command(self) -> List[str]:
        """Convert to a java command."""
        cmd = ["java"]
        cmd.extend(self.java_args)
        cmd.extend(["-jar", str(self.jar_path)])
        if self.config_url:
            cmd.extend(["-configurl", self.config_url])
        return cmd


class ServerDetector:
    """Detects server configuration from a directory."""

    def __init__(self, server_dir: Path):
        self.server_dir = Path(server_dir)

    def detect(self) -> Optional[LaunchConfig]:
        """
        Detect the launch configuration for the server.
        Returns LaunchConfig if successful, None otherwise.
        """
        # First, try to find launch scripts
        script_config = self._detect_from_scripts()
        if script_config:
            return script_config

        # If no scripts found, try to find JAR files directly
        jar_config = self._detect_from_jars()
        if jar_config:
            return jar_config

        return None

    def _detect_from_scripts(self) -> Optional[LaunchConfig]:
        """Detect configuration from batch/shell scripts."""
        # Look for common script patterns
        script_patterns = [
            "*.bat",
            "*.sh",
            "start.*",
            "run.*",
            "launch.*",
            "*.cmd"
        ]

        for pattern in script_patterns:
            for script in self.server_dir.rglob(pattern):
                config = self._parse_script(script)
                if config:
                    return config

        return None

    def _parse_script(self, script_path: Path) -> Optional[LaunchConfig]:
        """Parse a launch script to extract java command and arguments."""
        try:
            content = script_path.read_text(encoding='utf-8', errors='ignore')

            # Look for java commands
            java_patterns = [
                r'java\s+(.+?)(?:-jar|$)',  # Java args before -jar
                r'java\s+.*?-jar\s+([^\s]+)',  # JAR path
                r'-configurl\s+(\S+)',  # Config URL
                r'-Xmx(\d+[MG])',  # Memory settings
                r'-D([^\s]+)',  # System properties
            ]

            java_args = []
            jar_path = None
            config_url = None

            # Extract all java arguments
            for line in content.split('\n'):
                if 'java' not in line.lower():
                    continue

                # Extract memory settings
                xmx_match = re.search(r'-Xmx\d+[MG]', line)
                if xmx_match:
                    java_args.append(xmx_match.group(0))

                # Extract system properties
                for prop_match in re.finditer(r'(-D[^\s]+)', line):
                    java_args.append(prop_match.group(1))

                # Extract JAR path
                jar_match = re.search(r'-jar\s+([^\s]+)', line)
                if jar_match:
                    jar_rel = jar_match.group(1).strip('"\'')
                    # Resolve relative to script directory
                    jar_path = (script_path.parent / jar_rel).resolve()

                # Extract config URL
                config_match = re.search(r'-configurl\s+(\S+)', line)
                if config_match:
                    config_url = config_match.group(1).strip('"\'')

            if jar_path and jar_path.exists():
                return LaunchConfig(
                    jar_path=jar_path,
                    java_args=java_args,
                    main_class=None,
                    config_url=config_url,
                    working_dir=script_path.parent,
                    launch_script=script_path
                )

        except Exception as e:
            print(f"Error parsing script {script_path}: {e}")

        return None

    def _detect_from_jars(self) -> Optional[LaunchConfig]:
        """Detect configuration from JAR files directly."""
        # Find all JAR files
        jar_files = list(self.server_dir.rglob("*.jar"))

        if not jar_files:
            return None

        # Prioritize certain JAR names
        priority_names = ["server", "loader", "gameserver", "world"]

        for name in priority_names:
            for jar in jar_files:
                if name in jar.name.lower():
                    return self._create_default_config(jar)

        # If no priority match, use the first JAR
        return self._create_default_config(jar_files[0])

    def _create_default_config(self, jar_path: Path) -> LaunchConfig:
        """Create a default configuration for a JAR file."""
        return LaunchConfig(
            jar_path=jar_path,
            java_args=["-Xmx512M"],  # Default memory
            main_class=None,
            config_url=None,
            working_dir=jar_path.parent,
            launch_script=None
        )
