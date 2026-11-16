"""The shape of the configuration in config.yaml.

These are pydantic models because config.yaml is edited by people: pydantic checks
every value and reports exactly which setting is wrong. ``extra="forbid"`` turns a
misspelled setting name into an error instead of silently ignoring it.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

INVALID_NAME_CHARS = set('<>:"/\\|?*')

# Names Windows reserves for devices; a folder can't have them, with or without an extension.
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10)
}


def folder_name_problem(name: str) -> str | None:
    """Why ``name`` can't be used as a Windows folder name, or None if it's fine."""
    if not name.strip():
        return "must not be empty"
    bad = sorted(set(name) & INVALID_NAME_CHARS)
    if bad:
        return "must not contain " + " ".join(bad)
    if name != name.strip() or name.endswith("."):
        return "must not start or end with a space, or end with a dot"
    if name.split(".")[0].upper() in RESERVED_NAMES:
        return f"'{name}' is reserved by Windows"
    return None


class Rule(BaseModel):
    """Which files to pick from a source folder, and where to put them."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    category: str  # subfolder in the collection
    prefix: str = ""  # file name starts with (any case)
    extensions: list[str] = []  # e.g. [.csv, .log]; empty = any
    newest: int | None = Field(default=None, ge=1)  # keep only the N newest files
    max_age_minutes: float | None = Field(default=None, gt=0)  # only files modified recently
    expected: int = Field(default=1, ge=0)  # fewer matches = files missing

    @field_validator("category")
    @classmethod
    def _category_is_folder_name(cls, value: str) -> str:
        problem = folder_name_problem(value)
        if problem:
            raise ValueError(f"category {problem}")
        return value

    @field_validator("extensions")
    @classmethod
    def _normalize_extensions(cls, values: list[str]) -> list[str]:
        """'CSV', '.Csv' and '.csv' all become '.csv'."""
        normalized = []
        for value in values:
            ext = value.strip().lower()
            if ext:
                normalized.append(ext if ext.startswith(".") else "." + ext)
        return normalized

    @model_validator(mode="after")
    def _expected_fits_newest(self) -> Self:
        if self.newest is not None and self.expected > self.newest:
            raise ValueError(
                f"expected ({self.expected}) can't be more than newest ({self.newest})"
            )
        return self


class Source(BaseModel):
    """A folder to scan, with the rules applied to it."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    path: str = Field(min_length=1)
    recursive: bool = False  # also scan subfolders
    rules: list[Rule] = Field(min_length=1)

    @field_validator("rules")
    @classmethod
    def _rule_names_unique(cls, rules: list[Rule]) -> list[Rule]:
        _require_unique([rule.name for rule in rules], "rule")
        return rules


class UdpSettings(BaseModel):
    """Where to send the UDP message after each collection."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=5005, ge=1, le=65535)


class AppConfig(BaseModel):
    """Everything in config.yaml."""

    model_config = ConfigDict(extra="forbid")

    output_root: str = Field(min_length=1)  # where collected files are copied
    udp: UdpSettings = Field(default_factory=UdpSettings)
    sources: list[Source] = []

    @field_validator("sources")
    @classmethod
    def _source_names_unique(cls, sources: list[Source]) -> list[Source]:
        _require_unique([source.name for source in sources], "source")
        return sources


def _require_unique(names: list[str], what: str) -> None:
    seen = set()
    for name in names:
        key = name.lower()
        if key in seen:
            raise ValueError(f"two {what}s are named '{name}'; {what} names must be unique")
        seen.add(key)
