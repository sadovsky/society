"""Session persistence for Society — stores state between CLI invocations."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from society.models import Agent, Message
from society.society import Society

SESSION_DIR = Path.home() / ".society"
SESSION_FILE = SESSION_DIR / "session.json"
SESSIONS_DIR = SESSION_DIR / "sessions"


class SessionData(BaseModel):
    """Serializable snapshot of a Society session."""

    version: int = 1
    agents: list[Agent] = Field(default_factory=list)
    conversation: list[Message] = Field(default_factory=list)
    conversation_summary: str | None = None


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
    society.conversation_summary = data.conversation_summary
    return society


def society_to_session(society: Society) -> SessionData:
    """Extract session data from a live Society instance."""
    return SessionData(
        agents=list(society.agents.values()),
        conversation=list(society.conversation),
        conversation_summary=society.conversation_summary,
    )


def save_named_session(name: str, data: SessionData) -> None:
    """Save a session snapshot to ~/.society/sessions/<name>.json."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / f"{name}.json"
    path.write_text(data.model_dump_json(indent=2))


def load_named_session(name: str) -> SessionData | None:
    """Load a named session. Returns None if not found."""
    path = SESSIONS_DIR / f"{name}.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text())
        return SessionData.model_validate(raw)
    except (json.JSONDecodeError, Exception):
        return None


def list_sessions() -> list[str]:
    """List all saved session names."""
    if not SESSIONS_DIR.exists():
        return []
    return sorted(p.stem for p in SESSIONS_DIR.glob("*.json"))
