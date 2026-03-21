"""Tests for society.models — agents, memories, relationships."""

import time

from society.models import (
    AGENT_TEMPLATES,
    PRESETS,
    Agent,
    AgentConfig,
    AgentStatus,
    Memory,
    Message,
    Temperament,
)


def _make_agent(name: str = "Test", role: str = "Tester") -> Agent:
    config = AgentConfig(name=name, role=role, temperament=Temperament.ANALYTICAL)
    return Agent(config=config)


# --- Memory ---

class TestMemory:
    def test_effective_importance_fresh(self):
        m = Memory(content="hello", source="observation", importance=1.0)
        # Fresh memory should have ~1.0 effective importance
        assert m.effective_importance() > 0.99

    def test_effective_importance_decays(self):
        m = Memory(
            content="old",
            source="observation",
            importance=1.0,
            timestamp=time.time() - 86400 * 10,  # 10 days ago
        )
        eff = m.effective_importance()
        # 0.95^10 ≈ 0.5987
        assert 0.55 < eff < 0.65

    def test_summary_truncation(self):
        m = Memory(content="x" * 100, source="test", importance=0.5)
        summary = m.summary(max_len=20)
        assert len(summary) == 20
        assert summary.endswith("...")

    def test_summary_short(self):
        m = Memory(content="short", source="test", importance=0.5)
        assert m.summary() == "short"


# --- Agent ---

class TestAgent:
    def test_add_memory(self):
        agent = _make_agent()
        mem = agent.add_memory("test memory", source="observation", importance=0.7)
        assert len(agent.memories) == 1
        assert mem.content == "test memory"
        assert mem.importance == 0.7

    def test_memory_eviction(self):
        agent = _make_agent()
        for i in range(105):
            agent.add_memory(f"memory {i}", importance=0.1 + (i % 10) * 0.05)
        # Eviction triggers at >100, keeps top 80, then remaining adds go through
        # After 101st memory → evict to 80, then 102-105 added = 84
        assert len(agent.memories) <= 85  # bounded, not unlimited

    def test_recent_memories(self):
        agent = _make_agent()
        for i in range(5):
            agent.add_memory(f"memory {i}")
        recent = agent.recent_memories(3)
        assert len(recent) == 3
        # Most recent first
        assert "memory 4" in recent[0].content

    def test_relevant_memories(self):
        agent = _make_agent()
        agent.add_memory("python programming language", importance=0.9)
        agent.add_memory("cooking recipes for dinner", importance=0.9)
        agent.add_memory("python web frameworks", importance=0.9)
        results = agent.relevant_memories("python programming", n=2)
        assert len(results) == 2
        # Python-related memories should rank higher
        assert "python" in results[0].content.lower()

    def test_search_memories(self):
        agent = _make_agent()
        agent.add_memory("architecture design patterns")
        agent.add_memory("test driven development")
        agent.add_memory("system architecture review")
        results = agent.search_memories("architecture")
        assert len(results) == 2

    def test_memory_context_empty(self):
        agent = _make_agent()
        assert agent.memory_context() == ""

    def test_memory_context_with_query(self):
        agent = _make_agent()
        agent.add_memory("important design decision", importance=0.9)
        ctx = agent.memory_context(query="design")
        assert "recent memories" in ctx.lower()
        assert "design" in ctx.lower()

    def test_name_and_color_properties(self):
        config = AgentConfig(name="Aria", role="Architect", color="#6fa8dc")
        agent = Agent(config=config)
        assert agent.name == "Aria"
        assert agent.color == "#6fa8dc"


# --- Relationships ---

class TestRelationships:
    def test_update_relationship(self):
        agent = _make_agent()
        val = agent.update_relationship("Rex", 0.3)
        assert val == 0.3
        assert agent.relationships["Rex"] == 0.3

    def test_relationship_clamped(self):
        agent = _make_agent()
        agent.update_relationship("Rex", 0.8)
        agent.update_relationship("Rex", 0.5)
        assert agent.relationships["Rex"] == 1.0  # clamped at 1.0

    def test_relationship_negative_clamp(self):
        agent = _make_agent()
        agent.update_relationship("Rex", -0.8)
        agent.update_relationship("Rex", -0.5)
        assert agent.relationships["Rex"] == -1.0

    def test_relationship_context_empty(self):
        agent = _make_agent()
        assert agent.relationship_context() == ""

    def test_relationship_context_with_data(self):
        agent = _make_agent()
        agent.update_relationship("Rex", -0.5)
        agent.update_relationship("Nova", 0.6)
        ctx = agent.relationship_context()
        assert "Nova" in ctx
        assert "Rex" in ctx
        assert "agree" in ctx.lower()
        assert "disagree" in ctx.lower()


# --- AgentConfig ---

class TestAgentConfig:
    def test_system_prompt_includes_role(self):
        config = AgentConfig(
            name="Test",
            role="Architect",
            temperament=Temperament.ANALYTICAL,
            goals=["Build things"],
            backstory="A test agent.",
        )
        prompt = config.system_prompt()
        assert "Architect" in prompt
        assert "analytical" in prompt
        assert "Build things" in prompt
        assert "A test agent" in prompt


# --- Templates and Presets ---

class TestTemplatesAndPresets:
    def test_all_templates_have_required_fields(self):
        for key, config in AGENT_TEMPLATES.items():
            assert config.name
            assert config.role
            assert config.color != "white"  # All templates should have custom colors

    def test_presets_have_valid_agents(self):
        for name, configs in PRESETS.items():
            assert len(configs) >= 2  # At least 2 agents per preset
            for config in configs:
                assert config.name
                assert config.role

    def test_software_preset_has_facilitator(self):
        configs = PRESETS["software"]
        has_facilitator = any(c.temperament == Temperament.DIPLOMATIC for c in configs)
        assert has_facilitator


# --- Message ---

class TestMessage:
    def test_message_auto_id(self):
        m1 = Message(agent_name="Test", content="Hello")
        m2 = Message(agent_name="Test", content="World")
        assert m1.id != m2.id

    def test_message_timestamp(self):
        before = time.time()
        m = Message(agent_name="Test", content="Hello")
        after = time.time()
        assert before <= m.timestamp <= after
