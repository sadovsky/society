"""Tests for society.config — user configuration."""

from pathlib import Path
from unittest.mock import patch

from society.config import SocietyConfig, _parse_config, get_custom_agent_config, init_config


class TestSocietyConfig:
    def test_defaults(self):
        cfg = SocietyConfig()
        assert "sonnet" in cfg.model
        assert cfg.max_tokens == 1024
        assert cfg.temperature is None
        assert cfg.debate_rounds == 3
        assert cfg.memory_limit == 100
        assert cfg.default_preset is None
        assert cfg.custom_agents == {}

    def test_load_missing_file(self, tmp_path):
        fake_config = tmp_path / "config.toml"
        with patch("society.config.CONFIG_FILE", fake_config):
            cfg = SocietyConfig.load()
        assert cfg.model == SocietyConfig().model  # defaults

    def test_load_valid_config(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("""\
model = "claude-opus-4-20250514"
max_tokens = 2048
temperature = 0.8
debate_rounds = 5
""")
        with patch("society.config.CONFIG_FILE", config_file):
            cfg = SocietyConfig.load()

        assert cfg.model == "claude-opus-4-20250514"
        assert cfg.max_tokens == 2048
        assert cfg.temperature == 0.8
        assert cfg.debate_rounds == 5

    def test_load_with_custom_agents(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("""\
[agents.devops]
name = "Otto"
role = "DevOps Engineer"
temperament = "pragmatic"
color = "#76a5af"
""")
        with patch("society.config.CONFIG_FILE", config_file):
            cfg = SocietyConfig.load()

        assert "devops" in cfg.custom_agents
        assert cfg.custom_agents["devops"].name == "Otto"
        assert cfg.custom_agents["devops"].role == "DevOps Engineer"

    def test_load_corrupted_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("not valid toml {{{")
        with patch("society.config.CONFIG_FILE", config_file):
            cfg = SocietyConfig.load()
        # Should fall back to defaults
        assert cfg.max_tokens == 1024


class TestParseConfig:
    def test_parse_empty(self):
        cfg = _parse_config({})
        assert cfg.model == SocietyConfig().model

    def test_parse_partial(self):
        cfg = _parse_config({"max_tokens": 4096})
        assert cfg.max_tokens == 4096
        assert cfg.temperature is None  # not set

    def test_parse_agents(self):
        cfg = _parse_config({
            "agents": {
                "test": {
                    "name": "Testy",
                    "role": "Test Runner",
                    "temperament": "skeptical",
                }
            }
        })
        assert "test" in cfg.custom_agents
        assert cfg.custom_agents["test"].name == "Testy"


class TestCustomAgentConfig:
    def test_get_custom_agent_config(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("""\
[agents.devops]
name = "Otto"
role = "DevOps Engineer"
temperament = "pragmatic"
goals = ["Automate everything"]
color = "#76a5af"
""")
        with patch("society.config.CONFIG_FILE", config_file):
            cfg = get_custom_agent_config("devops")

        assert cfg is not None
        assert cfg.name == "Otto"
        assert cfg.role == "DevOps Engineer"
        from society.models import Temperament
        assert cfg.temperament == Temperament.PRAGMATIC

    def test_get_custom_agent_missing(self, tmp_path):
        config_file = tmp_path / "nonexistent.toml"
        with patch("society.config.CONFIG_FILE", config_file):
            cfg = get_custom_agent_config("nope")
        assert cfg is None


class TestInitConfig:
    def test_creates_file(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_dir = tmp_path

        with patch("society.config.CONFIG_FILE", config_file), \
             patch("society.config.CONFIG_DIR", config_dir):
            init_config()

        assert config_file.exists()
        content = config_file.read_text()
        assert "model" in content

    def test_does_not_overwrite(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text("custom content")

        with patch("society.config.CONFIG_FILE", config_file):
            init_config()

        assert config_file.read_text() == "custom content"
