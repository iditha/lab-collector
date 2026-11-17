"""Reading and saving the app's settings (config.yaml), and testing the UDP settings."""

import logging
from pathlib import Path

from labcollector import __version__
from labcollector.config_models import AppConfig, Source, UdpSettings
from labcollector.infra import config_store, udp_notifier
from labcollector.infra.config_store import ConfigError

__all__ = ["ConfigError", "SettingsService"]  # the UI catches ConfigError from here

log = logging.getLogger(__name__)


class SettingsService:
    def __init__(self, config_path: Path, default_output_root: Path):
        self.config_path = config_path
        self._default_output_root = default_output_root

    def load(self) -> AppConfig:
        """Read config.yaml (creating a default one the first time). Raises ConfigError."""
        return config_store.load_or_create(self.config_path, self._default_output_root)

    def validate(self, data: dict) -> AppConfig:
        """Check all settings from the Settings dialog. Raises ConfigError listing problems."""
        return config_store.validate(data, AppConfig)

    def validate_source(self, data: dict) -> Source:
        """Check one source from the source dialog. Raises ConfigError listing problems."""
        return config_store.validate(data, Source)

    def save(self, config: AppConfig) -> None:
        config_store.save(config, self.config_path)
        log.info("Settings saved to %s", self.config_path)

    def file_changed_at(self) -> float | None:
        """When config.yaml was last changed (by the app or by hand), or None if it's missing.

        The Settings dialog compares this before saving, so it can warn instead of silently
        overwriting edits made in a text editor while the dialog was open.
        """
        try:
            return self.config_path.stat().st_mtime
        except FileNotFoundError:
            return None

    def reset_to_default(self) -> Path:
        """Keep the current file as config.yaml.bak and write a default config.

        Used when config.yaml is broken, so the app can start. Returns the backup's path.
        """
        backup = self.config_path.with_name(self.config_path.name + ".bak")
        if self.config_path.exists():
            self.config_path.replace(backup)
        config_store.save(config_store.default_config(self._default_output_root), self.config_path)
        log.warning("Config reset to default; the old file was kept as %s", backup)
        return backup

    def send_test_message(self, udp: UdpSettings) -> str | None:
        """Send a test UDP message. Returns None if it was sent, else the error."""
        payload = {"app": "LabCollector", "app_version": __version__, "test": True}
        return udp_notifier.send(udp.host, udp.port, payload)
