#!/usr/bin/env python3
"""
Configuration management system
Handles loading, saving, and validating application configuration.
"""

import json
import logging
import os
import shutil
from typing import Any


class Configuration:
    """Application configuration manager"""

    def __init__(self, config_file: str | None = None):
        """
        Initialize configuration

        Args:
            config_file: Path to configuration file
        """
        self.config_file = config_file
        self.config_data: dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)

        # Default configuration
        self.default_config = {
            # Application settings
            "app.window_width": 1200,
            "app.window_height": 800,
            "app.window_x": 100,
            "app.window_y": 100,
            "app.max_recent_files": 10,
            # UI settings
            "ui.theme": "default",
            "ui.font_size": 12,
            "ui.show_toolbar": True,
            "ui.show_status_bar": True,
            # Audio settings
            "audio.output_format": "wav",
            "audio.sample_rate": 44100,
            "audio.bit_depth": 16,
            "audio.volume": 100,
            # Image settings
            "image.cache_size": 100,
            "image.thumbnail_size": 128,
            "image.max_display_size": 2048,
            # Logging settings
            "logging.level": "INFO",
            "logging.file_enabled": True,
            "logging.file_path": "logs/app.log",
            "logging.max_file_size": 10485760,  # 10MB
            "logging.backup_count": 5,
            # Recent files
            "recent_files": [],
            # sf33rd integration
            "sf33rd.auto_detect": True,
            "sf33rd.extract_path": "extracted_assets",
            "sf33rd.process_subdirectories": True,
        }

    def _ensure_config_directory(self, config_path: str) -> None:
        """Ensure the configuration directory exists"""
        config_dir = os.path.dirname(config_path)
        if config_dir and not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, exist_ok=True)
                self.logger.debug("Created configuration directory: %s", config_dir)
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.logger.error("Failed to create configuration directory %s: %s", config_dir, e)
                raise

    def load_config(self, config_file: str | None = None):
        """
        Load configuration from file

        Args:
            config_file: Path to configuration file (uses instance config_file if None)
        """
        if config_file:
            self.config_file = config_file

        if not self.config_file:
            # Use default config file path
            self.config_file = self._get_default_config_path()

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, encoding="utf-8") as f:
                    loaded_config = json.load(f)

                # Merge with defaults and apply migrations
                self.config_data = self._merge_with_defaults(loaded_config)
                self.logger.info("Configuration loaded from %s", self.config_file)
            else:
                # Use defaults
                self.config_data = self.default_config.copy()
                self.logger.info("Using default configuration")

                # Create directory if it doesn't exist
                self._ensure_config_directory(self.config_file)

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Failed to load configuration: %s", e)
            # Fall back to defaults
            self.config_data = self.default_config.copy()

    def save_config(self, config_file: str | None = None):
        """
        Save configuration to file

        Args:
            config_file: Path to configuration file (uses instance config_file if None)
        """
        if config_file:
            self.config_file = config_file

        if not self.config_file:
            self.config_file = self._get_default_config_path()

        try:
            # Create directory if it doesn't exist
            self._ensure_config_directory(self.config_file)

            # Create backup before saving if config file exists
            if os.path.exists(self.config_file):
                try:
                    backup_path = self.config_file + ".backup"
                    shutil.copy2(self.config_file, backup_path)
                    self.logger.debug("Created configuration backup: %s", backup_path)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self.logger.warning("Failed to create configuration backup: %s", e)

            # Custom encoder to handle QByteArray
            class ConfigEncoder(json.JSONEncoder):
                """Custom JSON encoder for configuration data"""

                def default(self, o):
                    # Handle QByteArray
                    if hasattr(o, "toBase64"):
                        return o.toBase64().data().decode("ascii")
                    # Handle bytes
                    if isinstance(o, bytes):
                        return o.decode("ascii", errors="ignore")
                    return super().default(o)

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False, cls=ConfigEncoder)

            self.logger.info("Configuration saved to %s", self.config_file)

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Failed to save configuration: %s", e)
            raise

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config_data.get(key, default)

    def set(self, key: str, value: Any):
        """
        Set a configuration value

        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config_data[key] = value
        self.logger.debug("Configuration set: %s = %s", key, value)

    def update(self, updates: dict[str, Any]):
        """
        Update multiple configuration values

        Args:
            updates: Dictionary of key-value pairs to update
        """
        self.config_data.update(updates)
        self.logger.debug("Configuration updated with %s values", len(updates))

    def validate_config(self) -> bool:
        """
        Validate the current configuration

        Returns:
            True if valid, False otherwise
        """
        try:
            # Validate window dimensions
            width = self.get("app.window_width", 800)
            height = self.get("app.window_height", 600)

            if not (100 <= width <= 3840 and 100 <= height <= 2160):
                self.logger.warning("Invalid window dimensions: %sx%s", width, height)
                return False

            # Validate logging level
            log_level = self.get("logging.level", "INFO")
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if log_level not in valid_levels:
                self.logger.warning("Invalid log level: %s", log_level)
                return False

            # Validate audio settings
            sample_rate = self.get("audio.sample_rate", 44100)
            if not 8000 <= sample_rate <= 192000:
                self.logger.warning("Invalid sample rate: %s", sample_rate)
                return False

            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Configuration validation failed: %s", e)
            return False

    def reset_to_defaults(self):
        """Reset configuration to default values"""
        self.config_data = self.default_config.copy()
        self.logger.info("Configuration reset to defaults")

    def get_section(self, section: str) -> dict[str, Any]:
        """
        Get all configuration values for a specific section

        Args:
            section: Configuration section (e.g., 'app', 'ui', 'audio')

        Returns:
            Dictionary of configuration values for the section
        """
        section_data = {}
        for key, value in self.config_data.items():
            if key.startswith(f"{section}."):
                section_key = key[len(section) + 1 :]  # Remove section prefix
                section_data[section_key] = value
        return section_data

    def add_recent_file(self, file_path: str):
        """
        Add a file to the recent files list

        Args:
            file_path: Path to add to recent files
        """
        if not file_path or not os.path.exists(file_path):
            return

        recent_files = self.get("recent_files", [])

        # Remove if already exists
        if file_path in recent_files:
            recent_files.remove(file_path)

        # Add to beginning
        recent_files.insert(0, file_path)

        # Limit length
        max_files = self.get("app.max_recent_files", 10)
        recent_files = recent_files[:max_files]

        self.set("recent_files", recent_files)

        # Save immediately for recent files
        try:
            self.save_config()
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.warning("Failed to save recent files: %s", e)

    def get_recent_files(self) -> list:
        """
        Get the list of recent files

        Returns:
            List of recent file paths
        """
        return list(self.get("recent_files", []))

    def migrate_config(self, loaded_config: dict[str, Any]) -> dict[str, Any]:
        """Migrate old configuration format to new format"""
        migrated_config = loaded_config.copy()

        # Migration: old 'window' section to new 'app' section
        if "window" in migrated_config:
            if "app.window_width" not in migrated_config:
                migrated_config["app.window_width"] = migrated_config.get("window.width", 1200)
            if "app.window_height" not in migrated_config:
                migrated_config["app.window_height"] = migrated_config.get("window.height", 800)
            if "app.window_x" not in migrated_config:
                migrated_config["app.window_x"] = migrated_config.get("window.x", 100)
            if "app.window_y" not in migrated_config:
                migrated_config["app.window_y"] = migrated_config.get("window.y", 100)
            # Remove old section
            del migrated_config["window"]

        # Migration: old 'recent' section to new 'recent_files'
        if "recent" in migrated_config and "recent_files" not in migrated_config:
            migrated_config["recent_files"] = migrated_config.get("recent", [])
            del migrated_config["recent"]

        # Migration: ensure all default values exist
        for key, default_value in self.default_config.items():
            if key not in migrated_config:
                migrated_config[key] = default_value

        return migrated_config

    def export_config(self, export_path: str) -> bool:
        """Export configuration to a file"""
        try:
            # Ensure directory exists
            export_dir = os.path.dirname(export_path)
            if export_dir:
                os.makedirs(export_dir, exist_ok=True)

            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)

            self.logger.info("Configuration exported to %s", export_path)
            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Failed to export configuration: %s", e)
            return False

    def import_config(self, import_path: str) -> bool:
        """Import configuration from a file"""
        try:
            if not os.path.exists(import_path):
                self.logger.error("Import file does not exist: %s", import_path)
                return False

            with open(import_path, encoding="utf-8") as f:
                imported_config = json.load(f)

            # Merge with current defaults
            merged_config = self._merge_with_defaults(imported_config)

            # Validate the imported configuration
            if self._validate_imported_config(merged_config):
                self.config_data = merged_config
                self.save_config()
                self.logger.info("Configuration imported from %s", import_path)
                return True

            self.logger.error("Imported configuration failed validation")
            return False

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Failed to import configuration: %s", e)
            return False

    def _validate_imported_config(self, config: dict[str, Any]) -> bool:
        """Validate imported configuration"""
        try:
            # Check for required sections
            required_sections = ["app", "ui", "logging"]
            for section in required_sections:
                if not any(key.startswith(f"{section}.") for key in config):
                    self.logger.warning("Missing required section: %s", section)
                    return False

            # Validate critical settings
            if not isinstance(config.get("app.max_recent_files", 0), int) or config.get("app.max_recent_files", 0) < 0:
                return False

            return config.get("logging.level") in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Configuration validation error: %s", e)
            return False

    def _get_default_config_path(self) -> str:
        """Get the default configuration file path"""
        # Use user config directory
        config_dir = os.path.expanduser("~/.config/sf3assetexplorer")
        return os.path.join(config_dir, "config.json")

    def _merge_with_defaults(self, loaded_config: dict[str, Any]) -> dict[str, Any]:
        """
        Merge loaded configuration with defaults

        Args:
            loaded_config: Configuration loaded from file

        Returns:
            Merged configuration
        """
        merged = self.default_config.copy()
        merged.update(loaded_config)

        # Apply migrations if needed
        if any(key.startswith("window.") or key.startswith("recent.") for key in loaded_config):
            merged = self.migrate_config(merged)

        return merged
