"""Server configuration editor dialog."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from qtframework.widgets import Button, Input, TextArea
from qtframework.widgets.buttons import ButtonVariant


if TYPE_CHECKING:
    from pserver_manager.config_loader import GameDefinition, ServerDefinition


class ServerEditor(QDialog):
    """Dialog for editing server configuration based on game schema."""

    def __init__(
        self,
        server: ServerDefinition,
        game: GameDefinition,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the server editor.

        Args:
            server: Server definition to edit
            game: Game definition for schema
            parent: Parent widget
        """
        super().__init__(parent)
        self.server = server
        self.game = game
        self._fields: dict[str, QWidget] = {}

        self.setWindowTitle(f"Edit Server - {server.name}")
        self.setMinimumWidth(600)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Create grouped form based on game schema
        group_box = QGroupBox(f"{self.game.name} Server Configuration")
        form_layout = QFormLayout(group_box)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Create fields based on game schema
        for field_schema in self.game.server_schema:
            field_name = field_schema["name"]
            field_type = field_schema.get("type", "string")
            required = field_schema.get("required", False)
            description = field_schema.get("description", "")
            values = field_schema.get("values", [])

            # Get current value
            current_value = self.server.get_field(field_name)

            # Create appropriate widget based on type and values
            widget = self._create_field_widget(
                field_type, current_value, values, description, field_name
            )
            self._fields[field_name] = widget

            # Create label with * for required fields
            label_text = field_name.replace("_", " ").title()
            if required:
                label_text += " *"

            form_layout.addRow(f"{label_text}:", widget)

        layout.addWidget(group_box)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = Button("Cancel", variant=ButtonVariant.SECONDARY)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = Button("Save", variant=ButtonVariant.PRIMARY)
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def _create_field_widget(
        self,
        field_type: str,
        current_value: Any,
        values: list[str],
        description: str,
        field_name: str,
    ) -> QWidget:
        """Create appropriate widget for field type.

        Args:
            field_type: Type of field
            current_value: Current field value
            values: Allowed values (for dropdown)
            description: Field description
            field_name: Name of the field

        Returns:
            Widget for the field
        """
        # Special case: version_id should use game versions as dropdown
        if field_name == "version_id" and self.game.versions:
            combo = QComboBox()
            version_ids = [v.id for v in self.game.versions]
            combo.addItems(version_ids)
            if current_value in version_ids:
                combo.setCurrentText(str(current_value))
            if description:
                combo.setToolTip(description)
            return combo

        # Choice/dropdown fields
        if values:
            combo = QComboBox()
            combo.addItems(values)
            if current_value in values:
                combo.setCurrentText(str(current_value))
            if description:
                combo.setToolTip(description)
            return combo

        # Boolean fields
        if field_type == "boolean":
            checkbox = QCheckBox()
            checkbox.setChecked(bool(current_value))
            if description:
                checkbox.setToolTip(description)
            return checkbox

        # Integer fields
        if field_type == "int":
            spinbox = QSpinBox()
            spinbox.setRange(0, 999999)
            spinbox.setValue(int(current_value or 0))
            if description:
                spinbox.setToolTip(description)
            return spinbox

        # Text/multiline fields
        if field_type == "text" or (isinstance(current_value, str) and len(current_value) > 100):
            text_area = TextArea(
                value=str(current_value or ""),
                placeholder=description if description else "",
            )
            text_area.setMaximumHeight(100)
            return text_area

        # Default to line edit for strings
        input_widget = Input(
            value=str(current_value or ""),
            placeholder=description if description else "",
        )
        return input_widget

    def get_values(self) -> dict[str, Any]:
        """Get the edited values from all fields.

        Returns:
            Dictionary of field names to values
        """
        values = {}
        for field_name, widget in self._fields.items():
            if isinstance(widget, (Input, TextArea)):
                values[field_name] = widget.value
            elif isinstance(widget, QComboBox):
                values[field_name] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                values[field_name] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                values[field_name] = widget.value()

        return values

    def save_to_file(self) -> bool:
        """Save the edited values to the server's YAML file.

        Returns:
            True if saved successfully
        """
        try:
            values = self.get_values()

            # Merge with existing data to preserve any fields not in schema
            updated_data = {**self.server.data, **values}

            # Find the server's YAML file
            # Server files are in config/servers/{game_id}/{server_id}.yaml
            # server.id is like "wow.retro-wow", extract just "retro-wow"
            server_filename = self.server.id.split(".", 1)[1] if "." in self.server.id else self.server.id
            config_dir = Path(__file__).parent.parent / "config"
            server_file = config_dir / "servers" / self.server.game_id / f"{server_filename}.yaml"

            # Write to YAML file
            with open(server_file, "w", encoding="utf-8") as f:
                yaml.dump(updated_data, f, default_flow_style=False, sort_keys=False)

            return True
        except Exception as e:
            print(f"Error saving server config: {e}")
            return False
