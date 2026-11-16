"""Load, validate and save config.yaml.

The app writes this file (from Settings), but people can also edit it by hand, so
every problem becomes a ConfigError whose message says where the problem is.
"""

import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from labcollector.models import AppConfig

HEADER = """\
# Lab Collector configuration.
# Edit it from Settings in the app, or by hand. The app re-reads it before every collection.
# Saving from the app rewrites this file, so comments you add will not be kept.
#
# output_root: where collected files are copied (a local folder or a share like //server/runs)
# udp:         message sent to a remote PC after each collection
# sources:     folders to scan. Example:
#
#   - name: Instrument A
#     path: C:/InstrumentA/Output
#     recursive: false         # also scan subfolders
#     rules:
#       - name: Measurement logs
#         category: logs       # subfolder inside each collection
#         prefix: MEAS_        # file name starts with (not case-sensitive)
#         extensions: [.csv, .log]
#         newest: 3            # keep only the 3 most recently modified files
#         max_age_minutes: 120 # only files modified in the last 2 hours
#         expected: 3          # fewer matches are reported as missing

"""


class ConfigError(Exception):
    """config.yaml can't be used. The message is written for the user."""


def default_config(output_root: Path) -> AppConfig:
    return AppConfig(output_root=str(output_root))


def load(path: Path) -> AppConfig:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}") from None
    except UnicodeDecodeError:
        raise ConfigError(
            f"{path.name} is not saved as UTF-8. Save it as UTF-8 and try again."
        ) from None
    except OSError as error:
        raise ConfigError(f"Can't read {path}: {error.strerror or error}") from error

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError(_describe_yaml_error(path, error)) from error

    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} is empty or doesn't contain settings.")

    try:
        return AppConfig.model_validate(data)
    except ValidationError as error:
        raise ConfigError(_describe_validation_error(path, data, error)) from error


def save(config: AppConfig, path: Path) -> None:
    data = config.model_dump(mode="json", exclude_none=True)
    text = HEADER + yaml.safe_dump(
        data, sort_keys=False, allow_unicode=True, default_flow_style=None
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)  # replace in one step, so a crash never leaves a half-written file


def _describe_yaml_error(path: Path, error: yaml.YAMLError) -> str:
    mark = getattr(error, "problem_mark", None)
    where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
    reason = getattr(error, "problem", None) or str(error)
    return f"{path.name} is not valid YAML{where}: {reason}"


def _describe_validation_error(path: Path, data: dict, error: ValidationError) -> str:
    lines = [f"{path.name} has invalid settings:"]
    for item in error.errors():
        message = item["msg"].removeprefix("Value error, ")
        if item["type"] == "extra_forbidden":
            message = "unknown setting (check the spelling)"
        lines.append(f"  - {_location(data, item['loc'])}: {message}")
    return "\n".join(lines)


def _location(data: dict, loc: tuple) -> str:
    """Turn pydantic's ('sources', 0, 'rules', 1, 'newest') into
    "sources > 'Instrument A' > rules > 'Logs' > newest", using names where they exist."""
    parts = []
    node = data
    for key in loc:
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError):
            node = None
        if isinstance(key, int):
            name = node.get("name") if isinstance(node, dict) else None
            parts.append(f"'{name}'" if name else f"#{key + 1}")
        else:
            parts.append(str(key))
    return " > ".join(parts)
