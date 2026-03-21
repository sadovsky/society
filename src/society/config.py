"""User configuration for Society — loads from ~/.society/config.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


CONFIG_DIR = Path.home() / ".society"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# Sentinel default so we know when the user hasn't set a value
_DEFAULT_MODEL = "claude-sonnet-4-20250514"


class AgentDef(BaseModel):
    """A user-defined custom agent from config."""

    name: str
    role: str
    temperament: str = "analytical"
    goals: list[str] = Field(default_factory=list)
    backstory: str = ""
    color: str = "white"


class SocietyConfig(BaseModel):
    """User configuration loaded from ~/.society/config.toml."""

    model: str = _DEFAULT_MODEL
    max_tokens: int = 1024
    temperature: float | None = None  # None = use API default
    default_preset: str | None = None
    debate_rounds: int = 3
    memory_limit: int = 100
    custom_agents: dict[str, AgentDef] = Field(default_factory=dict)

    @classmethod
    def load(cls) -> SocietyConfig:
        """Load config from ~/.society/config.toml. Returns defaults if missing."""
        if not CONFIG_FILE.exists():
            return cls()
        try:
            with open(CONFIG_FILE, "rb") as f:
                raw = tomllib.load(f)
            return _parse_config(raw)
        except Exception:
            return cls()


def _parse_config(raw: dict[str, Any]) -> SocietyConfig:
    """Parse a raw TOML dict into a SocietyConfig."""
    kwargs: dict[str, Any] = {}

    if "model" in raw:
        kwargs["model"] = str(raw["model"])
    if "max_tokens" in raw:
        kwargs["max_tokens"] = int(raw["max_tokens"])
    if "temperature" in raw:
        kwargs["temperature"] = float(raw["temperature"])
    if "default_preset" in raw:
        kwargs["default_preset"] = str(raw["default_preset"])
    if "debate_rounds" in raw:
        kwargs["debate_rounds"] = int(raw["debate_rounds"])
    if "memory_limit" in raw:
        kwargs["memory_limit"] = int(raw["memory_limit"])

    # Parse [agents.name] sections
    agents_raw = raw.get("agents", {})
    custom: dict[str, AgentDef] = {}
    for key, val in agents_raw.items():
        if isinstance(val, dict):
            custom[key] = AgentDef(name=val.get("name", key.capitalize()), **{
                k: v for k, v in val.items() if k != "name"
            })
    if custom:
        kwargs["custom_agents"] = custom

    return SocietyConfig(**kwargs)


def get_config() -> SocietyConfig:
    """Convenience function to load the config."""
    return SocietyConfig.load()


def get_custom_agent_config(key: str) -> "AgentConfig | None":
    """Look up a custom agent from config and return an AgentConfig, or None."""
    from society.models import AgentConfig, Temperament

    cfg = get_config()
    if key not in cfg.custom_agents:
        return None
    agent_def = cfg.custom_agents[key]
    try:
        temperament = Temperament(agent_def.temperament)
    except ValueError:
        temperament = Temperament.ANALYTICAL
    return AgentConfig(
        name=agent_def.name,
        role=agent_def.role,
        temperament=temperament,
        goals=agent_def.goals,
        backstory=agent_def.backstory,
        color=agent_def.color,
    )


def init_config() -> None:
    """Create a default config file if none exists."""
    if CONFIG_FILE.exists():
        return
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text("""\
# Society configuration
# model = "claude-sonnet-4-20250514"
# max_tokens = 1024
# temperature = 0.7
# default_preset = "software"
# debate_rounds = 3
# memory_limit = 100

# Custom agents — use any key name
# [agents.devops]
# name = "Otto"
# role = "DevOps Engineer"
# temperament = "pragmatic"
# goals = ["Automate everything", "Keep systems reliable"]
# backstory = "A battle-tested ops engineer."
# color = "#76a5af"
""")
