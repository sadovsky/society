"""Tests for society.session — persistence layer."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from society.models import Agent, AgentConfig, Memory, Message, Temperament
from society.session import (
    SessionData,
    load_named_session,
    load_session,
    save_named_session,
    save_session,
    session_to_society,
    society_to_session,
    list_sessions,
)
from society.society import Society


def _make_agent(name: str = "Test") -> Agent:
    config = AgentConfig(name=name, role="Tester", temperament=Temperament.ANALYTICAL)
    agent = Agent(config=config)
    agent.add_memory("test memory", importance=0.7)
    return agent


class TestSessionData:
    def test_serialization_roundtrip(self):
        agent = _make_agent()
        msg = Message(agent_name="Test", content="Hello world")
        data = SessionData(agents=[agent], conversation=[msg])

        json_str = data.model_dump_json()
        restored = SessionData.model_validate_json(json_str)

        assert len(restored.agents) == 1
        assert restored.agents[0].name == "Test"
        assert len(restored.conversation) == 1
        assert restored.conversation[0].content == "Hello world"

    def test_empty_session(self):
        data = SessionData()
        assert data.agents == []
        assert data.conversation == []
        assert data.version == 1

    def test_relationships_persist(self):
        agent = _make_agent()
        agent.update_relationship("Rex", 0.5)
        data = SessionData(agents=[agent])

        json_str = data.model_dump_json()
        restored = SessionData.model_validate_json(json_str)

        assert restored.agents[0].relationships["Rex"] == 0.5


class TestSessionIO:
    def test_save_and_load(self, tmp_path):
        agent = _make_agent()
        data = SessionData(agents=[agent])

        session_file = tmp_path / "session.json"
        session_dir = tmp_path

        with patch("society.session.SESSION_FILE", session_file), \
             patch("society.session.SESSION_DIR", session_dir):
            save_session(data)
            loaded = load_session()

        assert len(loaded.agents) == 1
        assert loaded.agents[0].name == "Test"

    def test_load_missing_file(self, tmp_path):
        session_file = tmp_path / "nonexistent.json"
        with patch("society.session.SESSION_FILE", session_file):
            data = load_session()
        assert data.agents == []

    def test_load_corrupted_file(self, tmp_path):
        session_file = tmp_path / "session.json"
        session_file.write_text("not valid json{{{")
        with patch("society.session.SESSION_FILE", session_file):
            data = load_session()
        assert data.agents == []  # Falls back to empty


class TestNamedSessions:
    def test_save_and_load_named(self, tmp_path):
        sessions_dir = tmp_path / "sessions"

        agent = _make_agent("Aria")
        data = SessionData(agents=[agent])

        with patch("society.session.SESSIONS_DIR", sessions_dir):
            save_named_session("my-test", data)
            loaded = load_named_session("my-test")

        assert loaded is not None
        assert loaded.agents[0].name == "Aria"

    def test_load_missing_named(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        with patch("society.session.SESSIONS_DIR", sessions_dir):
            result = load_named_session("nonexistent")
        assert result is None

    def test_list_sessions(self, tmp_path):
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        (sessions_dir / "alpha.json").write_text("{}")
        (sessions_dir / "beta.json").write_text("{}")

        with patch("society.session.SESSIONS_DIR", sessions_dir):
            names = list_sessions()
        assert names == ["alpha", "beta"]

    def test_list_sessions_empty(self, tmp_path):
        sessions_dir = tmp_path / "nonexistent"
        with patch("society.session.SESSIONS_DIR", sessions_dir):
            names = list_sessions()
        assert names == []


class TestSocietyConversion:
    def test_session_to_society(self):
        agent = _make_agent("Aria")
        msg = Message(agent_name="Aria", content="Hello")
        data = SessionData(agents=[agent], conversation=[msg])

        society = session_to_society(data)
        assert "Aria" in society.agents
        assert len(society.conversation) == 1

    def test_society_to_session(self):
        society = Society()
        society.spawn(template_name="architect")
        society.conversation.append(Message(agent_name="Aria", content="test"))

        data = society_to_session(society)
        assert len(data.agents) == 1
        assert len(data.conversation) == 1

    def test_roundtrip(self):
        society = Society()
        society.spawn(template_name="architect")
        society.spawn(template_name="critic")
        society.agents["Aria"].add_memory("test mem", importance=0.8)
        society.agents["Aria"].update_relationship("Rex", 0.4)

        data = society_to_session(society)
        restored = session_to_society(data)

        assert set(restored.agents.keys()) == {"Aria", "Rex"}
        assert len(restored.agents["Aria"].memories) == 1
        assert restored.agents["Aria"].relationships["Rex"] == 0.4
