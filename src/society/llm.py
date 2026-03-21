"""Claude API integration for agent reasoning."""

from __future__ import annotations

import os
from typing import Callable

import anthropic

from society.config import get_config
from society.models import Agent, Message


def get_client() -> anthropic.Anthropic:
    """Get an Anthropic client.

    Supports two auth methods (checked automatically by the SDK):
      - ANTHROPIC_API_KEY: standard API key (x-api-key header)
      - ANTHROPIC_AUTH_TOKEN: OAuth/bearer token, e.g. from `claude auth print-oauth-token`
    """
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        raise RuntimeError(
            "No authentication configured. Set one of:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...\n"
            "  export ANTHROPIC_AUTH_TOKEN=$(claude auth print-oauth-token)"
        )
    return anthropic.Anthropic()


def build_messages(
    agent: Agent,
    conversation: list[Message],
    user_prompt: str | None = None,
) -> list[dict]:
    """Build the messages list for the Claude API call."""
    messages: list[dict] = []

    # Add conversation history
    for msg in conversation[-20:]:  # Keep last 20 messages for context
        if msg.agent_name == agent.name:
            messages.append({"role": "assistant", "content": msg.content})
        else:
            messages.append({
                "role": "user",
                "content": f"[{msg.agent_name}]: {msg.content}",
            })

    # Add user prompt if provided
    if user_prompt:
        messages.append({"role": "user", "content": user_prompt})

    # Ensure messages alternate correctly and start with user
    if not messages or messages[0]["role"] != "user":
        messages.insert(0, {"role": "user", "content": "[System]: The discussion begins."})

    # Merge consecutive same-role messages
    merged: list[dict] = []
    for msg in messages:
        if merged and merged[-1]["role"] == msg["role"]:
            merged[-1]["content"] += "\n" + msg["content"]
        else:
            merged.append(msg)

    return merged


async def generate_response(
    agent: Agent,
    conversation: list[Message],
    user_prompt: str | None = None,
    model: str | None = None,
) -> str:
    """Generate a response from an agent using Claude."""
    client = get_client()
    cfg = get_config()
    model = model or cfg.model

    system = agent.config.system_prompt()
    rel_ctx = agent.relationship_context()
    if rel_ctx:
        system += "\n\n" + rel_ctx
    memory_ctx = agent.memory_context(query=user_prompt)
    if memory_ctx:
        system += "\n\n" + memory_ctx

    messages = build_messages(agent, conversation, user_prompt)

    extra_kwargs = {}
    if cfg.temperature is not None:
        extra_kwargs["temperature"] = cfg.temperature

    response = client.messages.create(
        model=model,
        max_tokens=cfg.max_tokens,
        system=system,
        messages=messages,
        **extra_kwargs,
    )

    text = response.content[0].text
    agent.message_count += 1
    agent.add_memory(
        content=f"I said: {text[:200]}",
        source="conversation",
        importance=0.6,
    )
    return text


async def generate_response_stream(
    agent: Agent,
    conversation: list[Message],
    user_prompt: str | None = None,
    model: str | None = None,
    on_token: Callable[[str], None] | None = None,
) -> str:
    """Generate a response with streaming, calling on_token for each chunk."""
    client = get_client()
    cfg = get_config()
    model = model or cfg.model

    system = agent.config.system_prompt()
    rel_ctx = agent.relationship_context()
    if rel_ctx:
        system += "\n\n" + rel_ctx
    memory_ctx = agent.memory_context(query=user_prompt)
    if memory_ctx:
        system += "\n\n" + memory_ctx

    messages = build_messages(agent, conversation, user_prompt)

    extra_kwargs = {}
    if cfg.temperature is not None:
        extra_kwargs["temperature"] = cfg.temperature

    full_text = ""
    with client.messages.stream(
        model=model,
        max_tokens=cfg.max_tokens,
        system=system,
        messages=messages,
        **extra_kwargs,
    ) as stream:
        for text in stream.text_stream:
            full_text += text
            if on_token:
                on_token(text)

    agent.message_count += 1
    agent.add_memory(
        content=f"I said: {full_text[:200]}",
        source="conversation",
        importance=0.6,
    )
    return full_text


async def generate_reflection(
    agent: Agent,
    debate_context: str,
    topic: str,
    model: str | None = None,
) -> str:
    """Short internal reflection — no memory/message_count side effects."""
    client = get_client()
    cfg = get_config()
    model = model or cfg.model
    system = agent.config.system_prompt()
    prompt = (
        f"Reflect briefly on this debate about '{topic}'. "
        "In 2-3 sentences: What did you learn? "
        "Which agents agreed or disagreed with you and why?\n\n"
        f"Recent discussion:\n{debate_context}"
    )
    response = client.messages.create(
        model=model,
        max_tokens=256,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


async def extract_relationship_deltas(
    agent: Agent,
    debate_context: str,
    other_agents: list[str],
    model: str | None = None,
) -> dict[str, float]:
    """Ask the agent to rate agreement/disagreement with other agents.

    Returns a dict of agent_name -> delta (-0.2 to +0.2).
    """
    if not other_agents:
        return {}
    client = get_client()
    cfg = get_config()
    model = model or cfg.model
    system = agent.config.system_prompt()
    agent_list = ", ".join(other_agents)
    prompt = (
        f"Based on this debate, rate how much you agreed or disagreed with each agent.\n"
        f"Agents: {agent_list}\n\n"
        f"Recent discussion:\n{debate_context}\n\n"
        f"Reply with ONLY one line per agent in the format: name:score\n"
        f"Score from -2 (strongly disagree) to +2 (strongly agree). Example:\n"
        f"Rex:-1\nNova:2\n"
        f"No other text."
    )
    try:
        response = client.messages.create(
            model=model,
            max_tokens=128,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        deltas: dict[str, float] = {}
        for line in text.splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            parts = line.rsplit(":", 1)
            name = parts[0].strip()
            try:
                raw = float(parts[1].strip())
                # Scale from [-2,2] to [-0.2, 0.2]
                deltas[name] = max(-0.2, min(0.2, raw / 10.0))
            except ValueError:
                continue
        return deltas
    except Exception:
        return {}
