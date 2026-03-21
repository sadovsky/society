"""Tests for society.society — orchestration layer."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from society.models import Agent, AgentConfig, AgentStatus, Message, Temperament
from society.society import Society


@pytest.fixture
def society():
    """A Society with 3 agents and mocked LLM."""
    s = Society()
    s.spawn(template_name="architect")
    s.spawn(template_name="critic")
    s.spawn(template_name="facilitator")
    return s


class TestSpawn:
    def test_spawn_from_template(self):
        s = Society()
        agent = s.spawn(template_name="architect")
        assert agent.name == "Aria"
        assert "Aria" in s.agents

    def test_spawn_from_config(self):
        s = Society()
        config = AgentConfig(name="Custom", role="Tester")
        agent = s.spawn(config=config)
        assert agent.name == "Custom"
        assert "Custom" in s.agents

    def test_spawn_unknown_template_raises(self):
        s = Society()
        with pytest.raises(ValueError, match="Unknown template"):
            s.spawn(template_name="nonexistent")

    def test_spawn_no_args_raises(self):
        s = Society()
        with pytest.raises(ValueError, match="Provide either"):
            s.spawn()

    def test_spawn_default_society(self):
        s = Society()
        agents = s.spawn_default_society()
        assert len(agents) == 5
        assert "Aria" in s.agents


class TestCallbacks:
    def test_on_message_fires(self, society):
        received = []
        society.on_message(lambda m: received.append(m))
        msg = Message(agent_name="Test", content="hi")
        society._emit_message(msg)
        assert len(received) == 1
        assert received[0].content == "hi"

    def test_on_status_change_fires(self, society):
        received = []
        society.on_status_change(lambda name, status: received.append((name, status)))
        society._set_status("Aria", AgentStatus.THINKING)
        assert received == [("Aria", AgentStatus.THINKING)]
        assert society.agents["Aria"].status == AgentStatus.THINKING


class TestAsk:
    @pytest.mark.asyncio
    async def test_ask_all_agents(self, society):
        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "I think..."
            messages = await society.ask("What is good design?")

        # Should get a user message + one response per agent
        assert len(messages) == 3  # 3 agents
        assert all(m.content == "I think..." for m in messages)
        # Conversation should have user + 3 responses
        assert len(society.conversation) == 4

    @pytest.mark.asyncio
    async def test_ask_single_agent(self, society):
        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "My answer"
            messages = await society.ask("Question?", agent_name="Aria")

        assert len(messages) == 1
        assert messages[0].agent_name == "Aria"

    @pytest.mark.asyncio
    async def test_ask_creates_memory(self, society):
        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "Response"
            await society.ask("Test question?", agent_name="Aria")

        # Agent should have a memory about being asked
        assert any("Asked about" in m.content for m in society.agents["Aria"].memories)

    @pytest.mark.asyncio
    async def test_ask_handles_error(self, society):
        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = Exception("API error")
            messages = await society.ask("test", agent_name="Aria")

        assert len(messages) == 1
        assert "[Error:" in messages[0].content


class TestDebate:
    @pytest.mark.asyncio
    async def test_debate_rounds(self, society):
        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen, \
             patch("society.society.generate_reflection", new_callable=AsyncMock) as mock_ref, \
             patch("society.society.extract_relationship_deltas", new_callable=AsyncMock) as mock_rel:
            mock_gen.return_value = "My position is..."
            mock_ref.return_value = "I learned that..."
            mock_rel.return_value = {}

            messages = await society.debate("Should we use microservices?", rounds=2)

        # 2 rounds × 3 agents = 6 messages
        assert len(messages) == 6

    @pytest.mark.asyncio
    async def test_debate_creates_memories(self, society):
        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen, \
             patch("society.society.generate_reflection", new_callable=AsyncMock) as mock_ref, \
             patch("society.society.extract_relationship_deltas", new_callable=AsyncMock) as mock_rel:
            mock_gen.return_value = "point"
            mock_ref.return_value = "reflection text"
            mock_rel.return_value = {}

            await society.debate("topic", rounds=1)

        for agent in society.agents.values():
            sources = [m.source for m in agent.memories]
            assert "observation" in sources  # debate participation memory
            assert "reflection" in sources  # post-debate reflection

    @pytest.mark.asyncio
    async def test_debate_updates_relationships(self, society):
        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen, \
             patch("society.society.generate_reflection", new_callable=AsyncMock) as mock_ref, \
             patch("society.society.extract_relationship_deltas", new_callable=AsyncMock) as mock_rel:
            mock_gen.return_value = "point"
            mock_ref.return_value = "reflection"
            mock_rel.return_value = {"Rex": 0.1, "Sage": -0.05}

            await society.debate("topic", rounds=1)

        # Aria should have updated relationships
        aria = society.agents["Aria"]
        assert "Rex" in aria.relationships or "Sage" in aria.relationships

    @pytest.mark.asyncio
    async def test_debate_progress_callback(self, society):
        progress = []
        society.on_debate_progress(lambda r, t, p: progress.append((r, t, p)))

        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen, \
             patch("society.society.generate_reflection", new_callable=AsyncMock) as mock_ref, \
             patch("society.society.extract_relationship_deltas", new_callable=AsyncMock) as mock_rel:
            mock_gen.return_value = "ok"
            mock_ref.return_value = "ok"
            mock_rel.return_value = {}

            await society.debate("topic", rounds=2)

        phases = [p for _, _, p in progress]
        assert "Opening positions" in phases
        assert "Complete" in phases


class TestConsensus:
    @pytest.mark.asyncio
    async def test_consensus_uses_facilitator(self, society):
        society.conversation.append(Message(agent_name="Aria", content="point"))

        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "The group agrees..."
            result = await society.consensus("test topic")

        assert result is not None
        assert result.agent_name == "Sage"  # Sage is the diplomatic facilitator

    @pytest.mark.asyncio
    async def test_consensus_no_agents(self):
        s = Society()
        result = await s.consensus("topic")
        assert result is None

    @pytest.mark.asyncio
    async def test_consensus_fallback_no_facilitator(self):
        s = Society()
        config = AgentConfig(name="Solo", role="Lone Wolf", temperament=Temperament.SKEPTICAL)
        s.spawn(config=config)
        s.conversation.append(Message(agent_name="Solo", content="test"))

        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "consensus"
            result = await s.consensus("topic")

        assert result is not None
        assert result.agent_name == "Solo"


class TestDirect:
    @pytest.mark.asyncio
    async def test_direct_conversation(self, society):
        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "I hear you"
            messages = await society.direct("Aria", "Rex", "Let's discuss architecture")

        assert len(messages) == 2
        assert messages[0].agent_name == "Aria"
        assert messages[1].agent_name == "Rex"
        assert messages[1].reply_to == messages[0].id

    @pytest.mark.asyncio
    async def test_direct_creates_memories(self, society):
        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "ok"
            await society.direct("Aria", "Rex", "test topic")

        aria_mems = [m.content for m in society.agents["Aria"].memories]
        rex_mems = [m.content for m in society.agents["Rex"].memories]
        assert any("Spoke to Rex" in m for m in aria_mems)
        assert any("Aria talked to me" in m for m in rex_mems)

    @pytest.mark.asyncio
    async def test_direct_invalid_agent_raises(self, society):
        with pytest.raises(ValueError, match="Both agents must exist"):
            await society.direct("Aria", "Ghost", "test")


class TestSummarization:
    @pytest.mark.asyncio
    async def test_auto_summarize_triggers(self, society):
        """When conversation exceeds 40 messages, summarization should trigger."""
        # Add 45 messages
        for i in range(45):
            society.conversation.append(
                Message(agent_name="Aria" if i % 2 == 0 else "Rex", content=f"msg {i}")
            )

        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen, \
             patch("society.society.summarize_conversation", new_callable=AsyncMock) as mock_sum:
            mock_gen.return_value = "response"
            mock_sum.return_value = "Summary of earlier discussion"
            await society.ask("test?", agent_name="Aria")

        mock_sum.assert_called_once()
        assert society.conversation_summary is not None
        assert "Summary" in society.conversation_summary
        assert len(society.conversation) <= 25  # trimmed + new messages

    @pytest.mark.asyncio
    async def test_no_summarize_short_conversation(self, society):
        """Short conversations should not trigger summarization."""
        society.conversation.append(Message(agent_name="Aria", content="hello"))

        with patch("society.society.generate_response", new_callable=AsyncMock) as mock_gen, \
             patch("society.society.summarize_conversation", new_callable=AsyncMock) as mock_sum:
            mock_gen.return_value = "hi"
            await society.ask("test?", agent_name="Aria")

        mock_sum.assert_not_called()

    def test_conversation_summary_persists(self):
        """Summary should survive session roundtrip."""
        from society.session import session_to_society, society_to_session

        s = Society()
        s.spawn(template_name="architect")
        s.conversation_summary = "Previous discussion about microservices"

        data = society_to_session(s)
        restored = session_to_society(data)

        assert restored.conversation_summary == "Previous discussion about microservices"


class TestStreaming:
    @pytest.mark.asyncio
    async def test_ask_with_streaming(self, society):
        tokens = []
        society.on_token(lambda name, tok: tokens.append((name, tok)))

        with patch("society.society.generate_response_stream", new_callable=AsyncMock) as mock_stream:
            mock_stream.return_value = "streamed response"
            await society.ask("test?", agent_name="Aria", stream=True)

        # The mock bypasses actual streaming, but verify the stream path was taken
        mock_stream.assert_called_once()
