"""Session persistence for Society — stores state between CLI invocations."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from society.models import Agent, Message
from society.society import Society

SESSION_DIR = Path.home() / ".society"
SESSION_FILE = SESSION_DIR / "session.json"


class SessionData(BaseModel):
    """Serializable snapshot of a Society session."""

    version: int = 1
    agents: list[Agent] = Field(default_factory=list)
    conversation: list[Message] = Field(default_factory=list)


def load_session() -> SessionData:
    """Load session from disk. Returns empty session if file doesn't exist."""
    if not SESSION_FILE.exists():
        return SessionData()
    try:
        raw = json.loads(SESSION_FILE.read_text())
        return SessionData.model_validate(raw)
    except (json.JSONDecodeError, Exception):
        return SessionData()


def save_session(data: SessionData) -> None:
    """Write session state to ~/.society/session.json."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(data.model_dump_json(indent=2))


def session_to_society(data: SessionData) -> Society:
    """Hydrate a Society instance from saved session data."""
    society = Society()
    for agent in data.agents:
        society.agents[agent.name] = agent
    society.conversation = list(data.conversation)
    return society


def society_to_session(society: Society) -> SessionData:
    """Extract session data from a live Society instance."""
    return SessionData(
        agents=list(society.agents.values()),
        conversation=list(society.conversation),
    )
