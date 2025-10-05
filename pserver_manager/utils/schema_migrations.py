"""Schema migration system for server configurations.

Uses qtframework's ConfigValidator to detect and fix outdated schemas.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml
from qtframework.config import ConfigValidator


class ServerSchemaMigrator:
    """Handles schema migrations for server configurations."""

    CURRENT_SCHEMA_VERSION = "1.0.0"

    def __init__(self):
        """Initialize schema migrator."""
        self.validator = ConfigValidator()
        self._setup_current_schema()

    def _setup_current_schema(self) -> None:
        """Define the current expected schema for server configs."""
        # Define the schema that server configs should conform to
        # This is our source of truth for what a valid server looks like
        self.current_schema = {
            "id": {"type": str, "required": True},
            "name": {"type": str, "required": True},
            "game_id": {"type": str, "required": False},  # May not be in YAML
            "host": {"type": str, "required": True},
            "version_id": {"type": str, "required": True},
            "status": {"type": str, "required": True},
            "realm_name": {"type": str, "required": False},
            "realm_type": {"type": str, "required": False},
            "rates": {"type": str, "required": False},
            "description": {"type": str, "required": False},
            "website": {"type": str, "required": False},
            "discord": {"type": str, "required": False},
            "icon": {"type": str, "required": False},
            "features": {"type": list, "required": False},
            "launch_date": {"type": str, "required": False},
            "region": {"type": str, "required": False},
            "language": {"type": str, "required": False},
            "population": {"type": str, "required": False},
            "uptime": {"type": str, "required": False},
            "_metadata": {"type": dict, "required": False},
        }

    def validate_server_config(self, server_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate a server config against current schema.

        Args:
            server_data: Server configuration data

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields
        for field_name, field_spec in self.current_schema.items():
            if field_spec.get("required", False) and field_name not in server_data:
                errors.append(f"Missing required field: {field_name}")

        # Check field types
        for field_name, value in server_data.items():
            if field_name in self.current_schema:
                expected_type = self.current_schema[field_name]["type"]
                if not isinstance(value, expected_type):
                    errors.append(
                        f"Field '{field_name}' has wrong type. "
                        f"Expected {expected_type.__name__}, got {type(value).__name__}"
                    )

        return len(errors) == 0, errors

    def needs_migration(self, server_data: dict[str, Any]) -> bool:
        """Check if server config needs migration.

        Args:
            server_data: Server configuration data

        Returns:
            True if migration is needed
        """
        is_valid, errors = self.validate_server_config(server_data)
        return not is_valid

    def detect_schema_issues(self, server_data: dict[str, Any]) -> dict[str, Any]:
        """Detect specific schema issues in server config.

        Args:
            server_data: Server configuration data

        Returns:
            Dictionary describing issues found
        """
        issues = {
            "missing_fields": [],
            "wrong_types": [],
            "deprecated_fields": [],
            "legacy_format": None,
        }

        # Check for missing required fields
        for field_name, field_spec in self.current_schema.items():
            if field_spec.get("required", False) and field_name not in server_data:
                issues["missing_fields"].append(field_name)

        # Check for type mismatches
        for field_name, value in server_data.items():
            if field_name in self.current_schema:
                expected_type = self.current_schema[field_name]["type"]
                if not isinstance(value, expected_type):
                    issues["wrong_types"].append({
                        "field": field_name,
                        "expected": expected_type.__name__,
                        "actual": type(value).__name__,
                    })

        # Check for legacy host:port format (example migration scenario)
        if "host" in server_data:
            host_value = str(server_data["host"])
            if ":" in host_value and "port" not in server_data:
                issues["legacy_format"] = "host_port_combined"

        return issues

    def migrate_server_config(self, server_data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """Migrate server config to current schema.

        Args:
            server_data: Server configuration data

        Returns:
            Tuple of (migrated_data, list_of_changes)
        """
        migrated_data = server_data.copy()
        changes = []

        issues = self.detect_schema_issues(server_data)

        # Handle legacy host:port format
        if issues["legacy_format"] == "host_port_combined":
            host_value = str(migrated_data["host"])
            if ":" in host_value:
                parts = host_value.rsplit(":", 1)
                migrated_data["host"] = parts[0]
                try:
                    migrated_data["port"] = int(parts[1])
                    changes.append(f"Split 'host' into 'host' and 'port' ({parts[0]}:{parts[1]})")
                except ValueError:
                    # Port wasn't a number, leave as-is
                    pass

        # Handle legacy 'version' field (should be 'version_id')
        if "version" in migrated_data and "version_id" not in migrated_data:
            migrated_data["version_id"] = migrated_data["version"]
            del migrated_data["version"]
            changes.append(f"Renamed 'version' to 'version_id'")

        # Add default values for missing optional fields if sensible
        # (Only add if they make sense to have defaults)

        # Validate the migrated config
        is_valid, validation_errors = self.validate_server_config(migrated_data)

        if is_valid:
            changes.append("✓ Schema migration successful")
        else:
            changes.append(f"⚠ Migration incomplete: {', '.join(validation_errors)}")

        return migrated_data, changes

    def migrate_server_file(self, server_file: Path, create_backup: bool = True) -> tuple[bool, list[str]]:
        """Migrate a server YAML file to current schema.

        Args:
            server_file: Path to server YAML file
            create_backup: Whether to create .backup file

        Returns:
            Tuple of (success, list_of_changes)
        """
        changes = []

        try:
            # Load current data
            with open(server_file, "r", encoding="utf-8") as f:
                server_data = yaml.safe_load(f)

            # Check if migration needed
            if not self.needs_migration(server_data):
                return True, ["No migration needed - schema is current"]

            # Create backup
            if create_backup:
                backup_file = server_file.with_suffix(server_file.suffix + ".backup")
                shutil.copy2(server_file, backup_file)
                changes.append(f"Created backup: {backup_file.name}")

            # If 'id' is missing, generate from filename
            if "id" not in server_data:
                server_id = server_file.stem  # filename without extension
                server_data["id"] = server_id
                changes.append(f"Added missing 'id' field from filename: {server_id}")

            # Migrate
            migrated_data, migration_changes = self.migrate_server_config(server_data)
            changes.extend(migration_changes)

            # Write migrated data
            with open(server_file, "w", encoding="utf-8") as f:
                yaml.dump(migrated_data, f, default_flow_style=False, sort_keys=False)

            changes.append(f"Updated {server_file.name}")
            return True, changes

        except Exception as e:
            changes.append(f"✗ Migration failed: {str(e)}")
            return False, changes

    def scan_and_migrate_directory(
        self, servers_dir: Path, create_backups: bool = True
    ) -> dict[str, Any]:
        """Scan directory and migrate all servers that need it.

        Args:
            servers_dir: Root servers directory
            create_backups: Whether to create backup files

        Returns:
            Dictionary with migration report
        """
        report = {
            "total_scanned": 0,
            "needs_migration": 0,
            "migrated": 0,
            "failed": 0,
            "details": [],
        }

        # Scan all game directories
        if not servers_dir.exists():
            return report

        for game_dir in servers_dir.iterdir():
            if not game_dir.is_dir():
                continue

            # Scan all server YAML files in this game
            for server_file in game_dir.glob("*.yaml"):
                report["total_scanned"] += 1

                # Load and check if migration needed
                try:
                    with open(server_file, "r", encoding="utf-8") as f:
                        server_data = yaml.safe_load(f)

                    if self.needs_migration(server_data):
                        report["needs_migration"] += 1

                        # Migrate
                        success, changes = self.migrate_server_file(server_file, create_backups)

                        if success:
                            report["migrated"] += 1
                            report["details"].append({
                                "file": str(server_file.relative_to(servers_dir)),
                                "status": "migrated",
                                "changes": changes,
                            })
                        else:
                            report["failed"] += 1
                            report["details"].append({
                                "file": str(server_file.relative_to(servers_dir)),
                                "status": "failed",
                                "changes": changes,
                            })

                except Exception as e:
                    report["failed"] += 1
                    report["details"].append({
                        "file": str(server_file.relative_to(servers_dir)),
                        "status": "error",
                        "changes": [f"Error: {str(e)}"],
                    })

        return report


def migrate_user_servers(servers_dir: Path, show_report: bool = True) -> dict[str, Any]:
    """Convenience function to migrate all user servers.

    Args:
        servers_dir: Root servers directory
        show_report: Whether to print report to console

    Returns:
        Migration report dictionary
    """
    migrator = ServerSchemaMigrator()
    report = migrator.scan_and_migrate_directory(servers_dir, create_backups=True)

    if show_report and report["total_scanned"] > 0:
        print(f"\n=== Server Schema Migration Report ===")
        print(f"Total servers scanned: {report['total_scanned']}")
        print(f"Needed migration: {report['needs_migration']}")
        print(f"Successfully migrated: {report['migrated']}")
        print(f"Failed: {report['failed']}")

        if report["details"]:
            print(f"\nDetails:")
            for detail in report["details"]:
                print(f"  - {detail['file']}: {detail['status']}")
                for change in detail["changes"]:
                    print(f"    {change}")

    return report
