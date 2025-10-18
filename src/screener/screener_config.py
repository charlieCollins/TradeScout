"""Screener configuration loader for YAML-based screener definitions."""

import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml


class ScreenerConfig:
    """Load and validate screener configurations from YAML files."""

    def __init__(self, config_dir: str = "configs/screeners"):
        """Initialize screener config loader.

        Args:
            config_dir: Directory containing screener YAML files
        """
        self.config_dir = Path(config_dir)
        self.screeners = {}
        self._load_all_screeners()

    def _load_all_screeners(self):
        """Load all screener YAML files from config directory."""
        if not self.config_dir.exists():
            raise ValueError(f"Screener config directory not found: {self.config_dir}")

        # Load all .yaml files in the directory
        for yaml_file in self.config_dir.glob("*.yaml"):
            try:
                screener_def = self._load_yaml(yaml_file)
                if screener_def.get("enabled", True):  # Default to enabled
                    name = screener_def.get("name", yaml_file.stem)
                    self.screeners[name] = screener_def
            except Exception as e:
                print(f"Warning: Failed to load screener {yaml_file}: {e}")

    def _load_yaml(self, yaml_path: Path) -> Dict:
        """Load and parse a YAML file.

        Args:
            yaml_path: Path to YAML file

        Returns:
            Parsed YAML content as dictionary
        """
        with open(yaml_path, 'r') as f:
            return yaml.safe_load(f)

    def get_screener(self, name: str) -> Dict:
        """Get screener configuration by name.

        Args:
            name: Screener name

        Returns:
            Screener configuration dictionary

        Raises:
            ValueError: If screener not found
        """
        if name not in self.screeners:
            # Try to reload in case new files were added
            self._load_all_screeners()

            if name not in self.screeners:
                available = ", ".join(sorted(self.screeners.keys()))
                raise ValueError(f"Screener '{name}' not found. Available: {available}")

        return self.screeners[name]

    def list_available_screeners(self) -> List[Dict[str, str]]:
        """List all available screener names and descriptions.

        Returns:
            List of dictionaries with 'name', 'description', and 'enabled' keys
        """
        screener_list = []
        for name, config in sorted(self.screeners.items()):
            screener_list.append({
                "name": name,
                "description": config.get("description", "No description"),
                "enabled": config.get("enabled", True)
            })
        return screener_list

    def reload(self):
        """Reload all screener configurations from disk."""
        self.screeners = {}
        self._load_all_screeners()