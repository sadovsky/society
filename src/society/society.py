"""Society manager - orchestrates agents, debates, and consensus."""

from __future__ import annotations

import asyncio
from typing import Callable

from society.llm import generate_response, generate_response_stream
from society.models import (
    AGENT_TEMPLATES,
    Agent,
    AgentConfig,
    AgentStatus,
    Message,
)


class Society:
    """Manages a collection of agents and their interactions."""

    def __init__(self) -> None:
        self.agents: dict[str, Agent] = {}
        self.conversation: list[Message] = []
        self._on_message: Callable[[Message], None] | None = None
        self._on_status_change: Callable[[str, AgentStatus], None] | None = None
        self._on_token: Callable[[str, str], None] | None = None
        self._on_debate_progress: Callable[[int, int, str], None] | None = None

    def on_message(self, callback: Callable[[Message], None]) -> None:
        self._on_message = callback

    def on_status_change(self, callback: Callable[[str, AgentStatus], None]) -> None:
        self._on_status_change = callback

    def on_token(self, callback: Callable[[str, str], None]) -> None:
        """Register a callback for streaming tokens: (agent_name, token)."""
        self._on_token = callback

    def on_debate_progress(self, callback: Callable[[int, int, str], None]) -> None:
        """Register callback for debate progress: (round_num, total_rounds, phase)."""
        self._on_debate_progress = callback

    def spawn(self, template_name: str | None = None, config: AgentConfig | None = None) -> Agent:
        """Spawn a new agent from a template or custom config."""
        if template_name:
            if template_name not in AGENT_TEMPLATES:
                raise ValueError(
                    f"Unknown template '{template_name}'. "
                    f"Available: {', '.join(AGENT_TEMPLATES.keys())}"
                )
            config = AGENT_TEMPLATES[template_name].model_copy()

        if config is None:
            raise ValueError("Provide either template_name or config")

        agent = Agent(config=config)
        self.agents[agent.name] = agent
        return agent

    def spawn_default_society(self) -> list[Agent]:
        """Spawn the default set of agents."""
        agents = []
        for template in AGENT_TEMPLATES:
            agents.append(self.spawn(template_name=template))
        return agents

    def _set_status(self, agent_name: str, status: AgentStatus) -> None:
        if agent_name in self.agents:
            self.agents[agent_name].status = status
            if self._on_status_change:
                self._on_status_change(agent_name, status)

    def _emit_message(self, message: Message) -> None:
        self.conversation.append(message)
        if self._on_message:
            self._on_message(message)

    async def _generate(self, agent: Agent, prompt: str, model: str | None = None, stream: bool = False) -> str:
        """Generate a response, optionally streaming tokens."""
        extra = {"model": model} if model else {}
        if stream and self._on_token:
            agent_name = agent.name
            def token_cb(token: str) -> None:
                self._on_token(agent_name, token)
            self._set_status(agent.name, AgentStatus.SPEAKING)
            return await generate_response_stream(
                agent, self.conversation, prompt, on_token=token_cb, **extra
            )
        else:
            return await generate_response(agent, self.conversation, prompt, **extra)

    async def ask(
        self, question: str, agent_name: str | None = None,
        model: str | None = None, stream: bool = False,
    ) -> list[Message]:
        """Ask a question to one or all agents."""
        targets = (
            [self.agents[agent_name]] if agent_name else list(self.agents.values())
        )

        # Add user message
        user_msg = Message(agent_name="You", content=question)
        self._emit_message(user_msg)

        responses: list[Message] = []
        for agent in targets:
            self._set_status(agent.name, AgentStatus.THINKING)
            try:
                text = await self._generate(agent, question, model=model, stream=stream)
                msg = Message(agent_name=agent.name, content=text)
                self._emit_message(msg)
                responses.append(msg)
                agent.add_memory(
                    content=f"Asked about: {question[:100]}",
                    source="observation",
                    importance=0.7,
                )
            except Exception as e:
                msg = Message(agent_name=agent.name, content=f"[Error: {e}]")
                self._emit_message(msg)
                responses.append(msg)
            finally:
                self._set_status(agent.name, AgentStatus.IDLE)

        return responses

    async def debate(
        self, topic: str, rounds: int = 3,
        model: str | None = None, stream: bool = False,
    ) -> list[Message]:
        """Run a multi-round debate between all agents on a topic."""
        all_messages: list[Message] = []

        # Opening prompt
        user_msg = Message(
            agent_name="You",
            content=f"[DEBATE] {topic}\n\nEach of you, share your perspective. Be direct and opinionated.",
        )
        self._emit_message(user_msg)

        agents = list(self.agents.values())

        for round_num in range(rounds):
            # Emit debate progress
            if round_num == 0:
                phase = "Opening positions"
            elif round_num == rounds - 1:
                phase = "Final summaries"
            else:
                phase = "Responses"
            if self._on_debate_progress:
                self._on_debate_progress(round_num + 1, rounds, phase)

            round_prompt = None
            if round_num == 0:
                round_prompt = f"Share your initial position on: {topic}"
            elif round_num == rounds - 1:
                round_prompt = (
                    "This is the final round. Summarize your position, "
                    "noting where you agree or disagree with others."
                )
            else:
                round_prompt = (
                    "Respond to what others have said. "
                    "Challenge points you disagree with, build on ones you support."
                )

            for agent in agents:
                self._set_status(agent.name, AgentStatus.THINKING)
                try:
                    text = await self._generate(agent, round_prompt, model=model, stream=stream)
                    msg = Message(agent_name=agent.name, content=text)
                    self._emit_message(msg)
                    all_messages.append(msg)
                except Exception as e:
                    msg = Message(agent_name=agent.name, content=f"[Error: {e}]")
                    self._emit_message(msg)
                    all_messages.append(msg)
                finally:
                    self._set_status(agent.name, AgentStatus.IDLE)

        # Store debate memory
        for agent in agents:
            agent.add_memory(
                content=f"Participated in debate about: {topic}",
                source="observation",
                importance=0.8,
            )

        # Signal debate complete
        if self._on_debate_progress:
            self._on_debate_progress(rounds, rounds, "Complete")

        return all_messages

    async def consensus(
        self, topic: str, model: str | None = None, stream: bool = False,
    ) -> Message | None:
        """Ask the facilitator (if present) to synthesize a consensus."""
        facilitator = None
        for agent in self.agents.values():
            if agent.config.temperament.value == "diplomatic":
                facilitator = agent
                break

        if not facilitator:
            # Pick first agent if no facilitator
            if self.agents:
                facilitator = next(iter(self.agents.values()))
            else:
                return None

        self._set_status(facilitator.name, AgentStatus.THINKING)
        try:
            prompt = (
                f"Synthesize the group's discussion on '{topic}'. "
                "Identify areas of agreement, remaining disagreements, "
                "and propose a consensus position."
            )
            text = await self._generate(facilitator, prompt, model=model, stream=stream)
            msg = Message(agent_name=facilitator.name, content=text)
            self._emit_message(msg)
            return msg
        finally:
            self._set_status(facilitator.name, AgentStatus.IDLE)
