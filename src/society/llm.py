"""Claude API integration for agent reasoning."""

from __future__ import annotations

import os

import anthropic

from society.models import Agent, Message


def get_client() -> anthropic.Anthropic:
    """Get an Anthropic client, raising a clear error if no API key."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is required. "
            "Set it with: export ANTHROPIC_API_KEY=your-key-here"
        )
    return anthropic.Anthropic(api_key=api_key)


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
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """Generate a response from an agent using Claude."""
    client = get_client()

    system = agent.config.system_prompt()
    memory_ctx = agent.memory_context()
    if memory_ctx:
        system += "\n\n" + memory_ctx

    messages = build_messages(agent, conversation, user_prompt)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=messages,
    )

    text = response.content[0].text
    agent.message_count += 1
    agent.add_memory(
        content=f"I said: {text[:200]}",
        source="conversation",
        importance=0.6,
    )
    return text
