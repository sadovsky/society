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

    def effective_importance(self) -> float:
        """Importance with time decay — 5% per day."""
        age_days = (time.time() - self.timestamp) / 86400
        decay = 0.95 ** age_days
        return self.importance * decay

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
    relationships: dict[str, float] = Field(default_factory=dict)  # agent_name -> affinity (-1 to 1)

    def update_relationship(self, other_name: str, delta: float) -> float:
        """Adjust affinity toward another agent. Returns new value."""
        current = self.relationships.get(other_name, 0.0)
        new_val = max(-1.0, min(1.0, current + delta))
        self.relationships[other_name] = round(new_val, 3)
        return self.relationships[other_name]

    def relationship_context(self) -> str:
        """Format relationships for system prompt injection."""
        if not self.relationships:
            return ""
        lines = ["Your opinions of other agents:"]
        for name, score in sorted(self.relationships.items(), key=lambda x: x[1], reverse=True):
            if score > 0.3:
                lines.append(f"- {name}: You tend to agree with them (affinity {score:+.2f})")
            elif score < -0.3:
                lines.append(f"- {name}: You often disagree with them (affinity {score:+.2f})")
            else:
                lines.append(f"- {name}: Neutral (affinity {score:+.2f})")
        return "\n".join(lines)

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def color(self) -> str:
        return self.config.color

    def add_memory(
        self, content: str, source: str = "observation",
        importance: float = 0.5, memory_limit: int = 100,
    ) -> Memory:
        memory = Memory(content=content, source=source, importance=importance)
        self.memories.append(memory)
        # Keep memories bounded — evict by effective importance (time-decayed)
        if len(self.memories) > memory_limit:
            self.memories.sort(key=lambda m: m.effective_importance(), reverse=True)
            self.memories = self.memories[: int(memory_limit * 0.8)]
        return memory

    def recent_memories(self, n: int = 10) -> list[Memory]:
        return sorted(self.memories, key=lambda m: m.timestamp, reverse=True)[:n]

    def relevant_memories(self, query: str, n: int = 10) -> list[Memory]:
        """Retrieve memories ranked by relevance to a query."""
        query_words = set(query.lower().split())
        now = time.time()
        scored = []
        for m in self.memories:
            memory_words = set(m.content.lower().split())
            relevance = len(query_words & memory_words) / max(len(query_words), 1)
            recency = 1.0 / (1 + (now - m.timestamp) / 86400)
            score = m.effective_importance() * 0.4 + recency * 0.3 + relevance * 0.3
            scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:n]]

    def search_memories(self, query: str, n: int = 20) -> list[Memory]:
        """Search memories by keyword substring match."""
        query_lower = query.lower()
        matches = [m for m in self.memories if query_lower in m.content.lower()]
        return sorted(matches, key=lambda m: m.timestamp, reverse=True)[:n]

    def memory_context(self, n: int = 10, query: str | None = None) -> str:
        """Format memories for system prompt injection."""
        if query:
            memories = self.relevant_memories(query, n)
        else:
            memories = self.recent_memories(n)
        if not memories:
            return ""
        lines = ["Your recent memories:"]
        for m in memories:
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

# Pre-built agent presets — curated teams for common scenarios
PRESETS: dict[str, list[AgentConfig]] = {
    "software": [
        AGENT_TEMPLATES["architect"],
        AGENT_TEMPLATES["critic"],
        AGENT_TEMPLATES["creative"],
        AGENT_TEMPLATES["pragmatist"],
        AGENT_TEMPLATES["facilitator"],
    ],
    "review": [
        AGENT_TEMPLATES["architect"],
        AGENT_TEMPLATES["critic"],
        AgentConfig(
            name="Shield",
            role="Security Analyst",
            temperament=Temperament.SKEPTICAL,
            goals=["Identify security vulnerabilities", "Assess threat models", "Ensure secure defaults"],
            backstory="A vigilant security specialist who assumes every system can be compromised.",
            color="#c27ba0",
        ),
    ],
    "brainstorm": [
        AGENT_TEMPLATES["creative"],
        AGENT_TEMPLATES["facilitator"],
        AgentConfig(
            name="Zara",
            role="Visionary Strategist",
            temperament=Temperament.VISIONARY,
            goals=["See the big picture", "Identify emerging trends", "Challenge conventional thinking"],
            backstory="A forward-thinking strategist who connects dots others don't see.",
            color="#76a5af",
        ),
    ],
}
