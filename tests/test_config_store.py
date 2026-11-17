import pytest

from labcollector.config_models import AppConfig, Rule, Source, folder_name_problem
from labcollector.infra.config_store import ConfigError, default_config, load, save

VALID_YAML = """
output_root: D:/LabRuns
udp: {host: 192.168.1.50, port: 5005}
sources:
  - name: Instrument A
    path: C:/InstrumentA/Output
    rules:
      - name: Logs
        category: logs
        prefix: MEAS_
        extensions: [CSV, .Log]
        newest: 3
        expected: 3
"""


def write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_valid_file(tmp_path):
    config = load(write(tmp_path, VALID_YAML))
    rule = config.sources[0].rules[0]
    assert config.udp.host == "192.168.1.50"
    assert rule.extensions == [".csv", ".log"]  # normalized
    assert rule.max_age_minutes is None  # default


def test_save_then_load_gives_same_config(tmp_path):
    config = load(write(tmp_path, VALID_YAML))
    path = tmp_path / "saved" / "config.yaml"
    save(config, path)
    assert load(path) == config
    assert path.read_text(encoding="utf-8").startswith("# Lab Collector configuration")


def test_default_config_round_trip(tmp_path):
    path = tmp_path / "config.yaml"
    save(default_config(tmp_path / "out"), path)
    assert load(path).sources == []


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load(tmp_path / "nope.yaml")


def test_empty_file(tmp_path):
    with pytest.raises(ConfigError, match="empty"):
        load(write(tmp_path, ""))


def test_broken_yaml_reports_line(tmp_path):
    with pytest.raises(ConfigError, match=r"line 2"):
        load(write(tmp_path, "output_root: D:/x\nudp: host: oops\n"))


def test_invalid_value_reports_where_by_name(tmp_path):
    with pytest.raises(ConfigError) as error:
        load(write(tmp_path, VALID_YAML.replace("newest: 3", "newest: 0")))
    message = str(error.value)
    assert "sources > 'Instrument A' > rules > 'Logs' > newest" in message


def test_misspelled_setting_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="unknown setting"):
        load(write(tmp_path, VALID_YAML.replace("prefix:", "prefx:")))


def test_expected_cannot_exceed_newest():
    with pytest.raises(ValueError, match="can't be more than newest"):
        Rule(name="r", category="c", newest=2, expected=3)


def test_duplicate_source_names_rejected():
    rule = Rule(name="r", category="c")
    with pytest.raises(ValueError, match="unique"):
        AppConfig(
            output_root="x",
            sources=[
                Source(name="A", path="p", rules=[rule]),
                Source(name="a", path="q", rules=[rule]),
            ],
        )


@pytest.mark.parametrize(
    "name, ok",
    [
        ("logs", True),
        ("Run 7", True),
        ("bad/name", False),
        ("a:b", False),
        ("   ", False),
        ("trailing.", False),
        (" lead", False),
        ("CON", False),
        ("nul.txt", False),
        ("com1", False),
        ("Console", True),
        ("LPT10", True),
    ],
)
def test_folder_name_problem(name, ok):
    assert (folder_name_problem(name) is None) == ok


def test_star_in_extensions_is_ignored():
    rule = Rule(name="r", category="c", extensions=["*.csv", "*.LOG", "txt"])
    assert rule.extensions == [".csv", ".log", ".txt"]


def test_star_dot_star_means_any_extension():
    assert Rule(name="r", category="c", extensions=["*.*"]).extensions == []  # empty = any
    assert Rule(name="r", category="c", extensions=["*", ".csv"]).extensions == [".csv"]


def test_other_wildcards_are_rejected():
    with pytest.raises(ValueError, match="can't contain wildcards"):
        Rule(name="r", category="c", extensions=["c*v"])


def test_enabled_sources():
    rule = Rule(name="r", category="c")
    config = AppConfig(
        output_root="x",
        sources=[
            Source(name="On", path="p", rules=[rule]),
            Source(name="Off", path="q", enabled=False, rules=[rule]),
        ],
    )
    assert [source.name for source in config.enabled_sources] == ["On"]
