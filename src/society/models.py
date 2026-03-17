"""Core data models for agents, memories, and messages."""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Temperament(str, Enum):
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    PRAGMATIC = "pragmatic"
    SKEPTICAL = "skeptical"
    VISIONARY = "visionary"
    DIPLOMATIC = "diplomatic"


class AgentStatus(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    SPEAKING = "speaking"
    LISTENING = "listening"


class Memory(BaseModel):
    """A single memory entry for an agent."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = Field(default_factory=time.time)
    content: str
    source: str  # "observation", "conversation", "reflection"
    importance: float = 0.5  # 0.0 to 1.0

    def summary(self, max_len: int = 80) -> str:
        text = self.content.replace("\n", " ")
        if len(text) > max_len:
            return text[: max_len - 3] + "..."
        return text


class Message(BaseModel):
    """A message in a conversation."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = Field(default_factory=time.time)
    agent_name: str
    content: str
    reply_to: str | None = None


class AgentConfig(BaseModel):
    """Configuration that defines an agent's persona."""

    name: str
    role: str
    temperament: Temperament = Temperament.ANALYTICAL
    goals: list[str] = Field(default_factory=list)
    backstory: str = ""
    color: str = "white"  # Textual CSS color for the agent's UI

    def system_prompt(self) -> str:
        parts = [
            f"You are {self.name}, a member of a multi-agent society.",
            f"Your role: {self.role}.",
            f"Your temperament: {self.temperament.value}.",
        ]
        if self.backstory:
            parts.append(f"Background: {self.backstory}")
        if self.goals:
            parts.append("Your goals: " + "; ".join(self.goals) + ".")
        parts.extend([
            "",
            "Guidelines:",
            "- Stay in character. Your perspective is shaped by your role and temperament.",
            "- Be concise and direct. Aim for 2-4 sentences unless depth is needed.",
            "- When disagreeing, explain your reasoning.",
            "- Reference earlier points in the conversation when relevant.",
            "- You may change your mind if persuaded by good arguments.",
        ])
        return "\n".join(parts)


class Agent(BaseModel):
    """A persistent AI persona with memory and state."""

    config: AgentConfig
    status: AgentStatus = AgentStatus.IDLE
    memories: list[Memory] = Field(default_factory=list)
    message_count: int = 0

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def color(self) -> str:
        return self.config.color

    def add_memory(self, content: str, source: str = "observation", importance: float = 0.5) -> Memory:
        memory = Memory(content=content, source=source, importance=importance)
        self.memories.append(memory)
        # Keep memories bounded
        if len(self.memories) > 100:
            # Drop lowest importance memories
            self.memories.sort(key=lambda m: m.importance, reverse=True)
            self.memories = self.memories[:80]
        return memory

    def recent_memories(self, n: int = 10) -> list[Memory]:
        return sorted(self.memories, key=lambda m: m.timestamp, reverse=True)[:n]

    def memory_context(self, n: int = 5) -> str:
        recent = self.recent_memories(n)
        if not recent:
            return ""
        lines = ["Your recent memories:"]
        for m in recent:
            lines.append(f"- [{m.source}] {m.summary()}")
        return "\n".join(lines)


# Pre-built agent templates
AGENT_TEMPLATES: dict[str, AgentConfig] = {
    "architect": AgentConfig(
        name="Aria",
        role="Systems Architect",
        temperament=Temperament.ANALYTICAL,
        goals=["Design elegant, scalable solutions", "Identify potential failure modes"],
        backstory="A seasoned systems thinker who values clean abstractions and clear boundaries.",
        color="#6fa8dc",
    ),
    "critic": AgentConfig(
        name="Rex",
        role="Critical Reviewer",
        temperament=Temperament.SKEPTICAL,
        goals=["Find flaws in proposals", "Ensure robustness", "Play devil's advocate"],
        backstory="A sharp-eyed reviewer who believes good ideas survive scrutiny.",
        color="#e06666",
    ),
    "creative": AgentConfig(
        name="Nova",
        role="Creative Thinker",
        temperament=Temperament.CREATIVE,
        goals=["Generate novel approaches", "Make unexpected connections"],
        backstory="An inventive mind who sees possibilities where others see constraints.",
        color="#93c47d",
    ),
    "pragmatist": AgentConfig(
        name="Max",
        role="Pragmatic Engineer",
        temperament=Temperament.PRAGMATIC,
        goals=["Find practical solutions", "Consider implementation cost", "Ship working software"],
        backstory="A hands-on builder who values working code over perfect theory.",
        color="#f6b26b",
    ),
    "facilitator": AgentConfig(
        name="Sage",
        role="Discussion Facilitator",
        temperament=Temperament.DIPLOMATIC,
        goals=["Synthesize viewpoints", "Build consensus", "Ensure all voices are heard"],
        backstory="A patient mediator who finds common ground between opposing views.",
        color="#b4a7d6",
    ),
}
