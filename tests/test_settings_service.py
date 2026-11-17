import json
import socket

import pytest

from labcollector import __version__
from labcollector.config_models import UdpSettings
from labcollector.services.settings_service import ConfigError, SettingsService


@pytest.fixture
def settings(tmp_path):
    return SettingsService(tmp_path / "config.yaml", tmp_path / "collected")


def test_first_load_creates_a_default_config(settings, tmp_path):
    config = settings.load()
    assert settings.config_path.exists()
    assert config.output_root == str(tmp_path / "collected")
    assert config.sources == []


def test_validate_lists_problems_by_name(settings):
    data = {
        "output_root": "D:/out",
        "sources": [{"name": "Scope", "path": "C:/s", "rules": [{"name": "R", "category": ""}]}],
    }
    with pytest.raises(ConfigError) as error:
        settings.validate(data)
    assert "Some settings are invalid" in str(error.value)
    assert "sources > 'Scope' > rules > 'R' > category" in str(error.value)


def test_validate_source_checks_one_source(settings):
    with pytest.raises(ConfigError, match="newest"):
        settings.validate_source(
            {
                "name": "Scope",
                "path": "C:/s",
                "rules": [{"name": "R", "category": "c", "newest": "x"}],
            }
        )
    source = settings.validate_source(
        {
            "name": "Scope",
            "path": "C:/s",
            "rules": [{"name": "R", "category": "c", "extensions": ["CSV"]}],
        }
    )
    assert source.rules[0].extensions == [".csv"]


def test_reset_to_default_keeps_the_broken_file(settings):
    settings.config_path.write_text("output_root: [broken", encoding="utf-8")
    with pytest.raises(ConfigError):
        settings.load()

    backup = settings.reset_to_default()

    assert backup.read_text(encoding="utf-8") == "output_root: [broken"
    assert settings.load().sources == []


def test_send_test_message(settings):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2)
        port = receiver.getsockname()[1]
        assert settings.send_test_message(UdpSettings(host="127.0.0.1", port=port)) is None
        message = json.loads(receiver.recv(1024))
    assert message == {"app": "LabCollector", "app_version": __version__, "test": True}


def test_send_test_message_reports_errors(settings, broken_network):
    error = settings.send_test_message(UdpSettings(host="192.168.1.50", port=5005))
    assert error and "unreachable network" in error
