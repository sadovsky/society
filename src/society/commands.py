"""CLI subcommand implementations for Society."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from society.config import get_config, init_config
from society.models import AGENT_TEMPLATES, PRESETS, AgentConfig, Temperament
from society.session import load_session, save_session, session_to_society, society_to_session

console = Console()

# Colors for custom agents (rotated when templates are exhausted)
_CUSTOM_COLORS = [
    "#c27ba0",  # pink
    "#76a5af",  # teal
    "#d5a6bd",  # mauve
    "#a4c2f4",  # light blue
    "#b6d7a8",  # light green
    "#ffe599",  # yellow
    "#ea9999",  # salmon
    "#d9d2e9",  # lavender
]

# Heuristic mapping of keywords to temperaments for custom agents
_TEMPERAMENT_HINTS: dict[str, Temperament] = {
    "security": Temperament.SKEPTICAL,
    "review": Temperament.SKEPTICAL,
    "test": Temperament.SKEPTICAL,
    "qa": Temperament.SKEPTICAL,
    "audit": Temperament.SKEPTICAL,
    "design": Temperament.CREATIVE,
    "creative": Temperament.CREATIVE,
    "art": Temperament.CREATIVE,
    "ux": Temperament.CREATIVE,
    "lead": Temperament.DIPLOMATIC,
    "manage": Temperament.DIPLOMATIC,
    "facilitate": Temperament.DIPLOMATIC,
    "product": Temperament.DIPLOMATIC,
    "vision": Temperament.VISIONARY,
    "strategy": Temperament.VISIONARY,
    "future": Temperament.VISIONARY,
    "build": Temperament.PRAGMATIC,
    "ship": Temperament.PRAGMATIC,
    "ops": Temperament.PRAGMATIC,
    "devops": Temperament.PRAGMATIC,
    "infra": Temperament.PRAGMATIC,
}


def _pick_temperament(role: str) -> Temperament:
    """Pick a temperament based on role keywords."""
    lower = role.lower()
    for keyword, temp in _TEMPERAMENT_HINTS.items():
        if keyword in lower:
            return temp
    return Temperament.ANALYTICAL


def _pick_color(existing_count: int) -> str:
    """Pick a color from the rotation list."""
    return _CUSTOM_COLORS[existing_count % len(_CUSTOM_COLORS)]


def _generate_name(role: str, existing_names: set[str]) -> str:
    """Generate a display name from a role, avoiding collisions."""
    # Capitalize first word as the name
    name = role.strip().split()[0].capitalize()
    if name not in existing_names:
        return name
    # Append numbers to resolve collisions
    for i in range(2, 100):
        candidate = f"{name}{i}"
        if candidate not in existing_names:
            return candidate
    return name


def _require_agents(agent_count: int) -> bool:
    """Print error and return False if no agents are spawned."""
    if agent_count == 0:
        console.print("[bold red]No agents spawned.[/bold red] Run [cyan]society spawn <role>[/cyan] first.")
        return False
    return True


def cmd_spawn(role_or_template: str) -> None:
    """Spawn an agent from a template or custom role description."""
    data = load_session()
    society = session_to_society(data)

    if role_or_template.lower() in AGENT_TEMPLATES:
        template_key = role_or_template.lower()
        # Check if this template's agent already exists
        template_config = AGENT_TEMPLATES[template_key]
        if template_config.name in society.agents:
            console.print(f"[yellow]{template_config.name} is already spawned.[/yellow]")
            return
        agent = society.spawn(template_name=template_key)
    else:
        existing_names = set(society.agents.keys())
        name = _generate_name(role_or_template, existing_names)
        config = AgentConfig(
            name=name,
            role=role_or_template.title(),
            temperament=_pick_temperament(role_or_template),
            goals=[f"Provide expert {role_or_template.lower()} perspective"],
            backstory=f"A knowledgeable {role_or_template.lower()} contributing to group discussions.",
            color=_pick_color(len(society.agents)),
        )
        agent = society.spawn(config=config)

    save_session(society_to_session(society))
    console.print(
        f"[bold {agent.color}]Spawned {agent.name}[/bold {agent.color}] "
        f"— {agent.config.role} ({agent.config.temperament.value})"
    )


def cmd_solve(question: str, model: str | None = None) -> None:
    """Ask all agents a question with streaming output."""
    data = load_session()
    society = session_to_society(data)
    if not _require_agents(len(society.agents)):
        return

    _streaming_buf: dict[str, str] = {"agent": "", "text": ""}

    def on_msg(msg):
        # Clear streaming line before printing final message
        if msg.agent_name == "You":
            console.print(f"\n[bold cyan]You:[/bold cyan] {msg.content}")
        # Agent messages are printed by the streaming callback already

    def on_token(agent_name, token):
        if _streaming_buf["agent"] != agent_name:
            # New agent speaking — print header
            if _streaming_buf["agent"]:
                console.print()  # end previous agent's output
            agent = society.agents.get(agent_name)
            color = agent.color if agent else "white"
            console.print(f"\n[bold {color}]{agent_name}:[/bold {color}] ", end="")
            _streaming_buf["agent"] = agent_name
            _streaming_buf["text"] = ""
        print(token, end="", flush=True)
        _streaming_buf["text"] += token

    def on_msg_done(msg):
        if msg.agent_name != "You":
            console.print()  # newline after streamed output

    society.on_token(on_token)
    society.on_message(on_msg_done)

    # Print the question
    console.print(f"\n[bold cyan]You:[/bold cyan] {question}")
    asyncio.run(society.ask(question, model=model, stream=True))
    save_session(society_to_session(society))


def cmd_ask(agent_ref: str, question: str, model: str | None = None) -> None:
    """Ask a specific agent a question with streaming output."""
    data = load_session()
    society = session_to_society(data)
    if not _require_agents(len(society.agents)):
        return

    # Strip leading @ if present
    name = agent_ref.lstrip("@")
    # Case-insensitive lookup
    agent_name = None
    for n in society.agents:
        if n.lower() == name.lower():
            agent_name = n
            break

    if not agent_name:
        console.print(f"[bold red]Agent '{name}' not found.[/bold red]")
        console.print(f"Available: {', '.join(society.agents.keys())}")
        return

    _header_printed = {"done": False}

    def on_token(a_name, token):
        if not _header_printed["done"]:
            agent = society.agents.get(a_name)
            color = agent.color if agent else "white"
            console.print(f"\n[bold {color}]{a_name}:[/bold {color}] ", end="")
            _header_printed["done"] = True
        print(token, end="", flush=True)

    def on_msg(msg):
        if msg.agent_name != "You":
            console.print()  # newline after stream

    society.on_token(on_token)
    society.on_message(on_msg)

    console.print(f"\n[bold cyan]You:[/bold cyan] {question}")
    asyncio.run(society.ask(question, agent_name, model=model, stream=True))
    save_session(society_to_session(society))


def cmd_debate(topic: str, rounds: int | None = None, model: str | None = None) -> None:
    """Run a multi-round debate between all agents with streaming output."""
    cfg = get_config()
    if rounds is None:
        rounds = cfg.debate_rounds

    data = load_session()
    society = session_to_society(data)
    if not _require_agents(len(society.agents)):
        return

    console.print(f"\n[bold]Debate:[/bold] {topic} ({rounds} rounds)\n")

    _streaming_buf: dict[str, str] = {"agent": ""}

    def on_token(agent_name, token):
        if _streaming_buf["agent"] != agent_name:
            if _streaming_buf["agent"]:
                console.print()
            agent = society.agents.get(agent_name)
            color = agent.color if agent else "white"
            console.print(f"\n[bold {color}]{agent_name}:[/bold {color}] ", end="")
            _streaming_buf["agent"] = agent_name
        print(token, end="", flush=True)

    def on_msg(msg):
        if msg.agent_name == "You":
            console.print(f"[dim]{msg.content}[/dim]")
        elif msg.agent_name != "You":
            console.print()  # newline after stream

    def on_progress(round_num, total, phase):
        if phase == "Reflecting":
            console.print(f"\n[dim]Agents reflecting on debate...[/dim]")
        elif phase == "Complete":
            console.print(f"\n[bold green]Debate complete![/bold green]")
        else:
            console.print(f"\n[dim]— Round {round_num}/{total}: {phase} —[/dim]")

    society.on_token(on_token)
    society.on_message(on_msg)
    society.on_debate_progress(on_progress)

    asyncio.run(society.debate(topic, rounds=rounds, model=model, stream=True))
    save_session(society_to_session(society))


def cmd_consensus(model: str | None = None) -> None:
    """Synthesize group consensus from current conversation."""
    data = load_session()
    society = session_to_society(data)
    if not _require_agents(len(society.agents)):
        return

    if not society.conversation:
        console.print("[yellow]No conversation yet.[/yellow] Run [cyan]society solve[/cyan] or [cyan]society debate[/cyan] first.")
        return

    def print_message(msg):
        agent = society.agents.get(msg.agent_name)
        color = agent.color if agent else "white"
        console.print(f"\n[bold {color}]{msg.agent_name} (consensus):[/bold {color}] {msg.content}")

    society.on_message(print_message)
    asyncio.run(society.consensus("the current discussion", model=model))
    save_session(society_to_session(society))


def cmd_status() -> None:
    """Show current agents and session stats."""
    data = load_session()

    if not data.agents:
        console.print("[dim]No agents spawned.[/dim] Run [cyan]society spawn <role>[/cyan] to get started.")
        return

    table = Table(title="Society", show_lines=False)
    table.add_column("Name", style="bold")
    table.add_column("Role")
    table.add_column("Temperament")
    table.add_column("Memories", justify="right")
    table.add_column("Messages", justify="right")
    table.add_column("Relationships")

    for agent in data.agents:
        # Format relationships as compact string
        rels = ""
        if agent.relationships:
            parts = []
            for name, score in sorted(agent.relationships.items(), key=lambda x: x[1], reverse=True):
                if score > 0.1:
                    parts.append(f"[green]+{name}[/green]")
                elif score < -0.1:
                    parts.append(f"[red]-{name}[/red]")
            rels = " ".join(parts[:3]) if parts else "[dim]—[/dim]"
        else:
            rels = "[dim]—[/dim]"

        table.add_row(
            f"[{agent.color}]{agent.name}[/{agent.color}]",
            agent.config.role,
            agent.config.temperament.value,
            str(len(agent.memories)),
            str(agent.message_count),
            rels,
        )

    console.print(table)
    console.print(f"\n[dim]{len(data.conversation)} messages in conversation history[/dim]")


def cmd_history() -> None:
    """Show conversation history."""
    data = load_session()

    if not data.conversation:
        console.print("[dim]No conversation history.[/dim]")
        return

    # Build a color lookup from agents
    colors = {a.name: a.color for a in data.agents}

    for msg in data.conversation:
        if msg.agent_name == "You":
            console.print(f"\n[bold cyan]You:[/bold cyan] {msg.content}")
        else:
            color = colors.get(msg.agent_name, "white")
            console.print(f"\n[bold {color}]{msg.agent_name}:[/bold {color}] {msg.content}")


def cmd_memories(agent_ref: str, search: str | None = None) -> None:
    """Show memories for a specific agent, optionally filtered by search."""
    data = load_session()

    name = agent_ref.lstrip("@")
    agent = None
    for a in data.agents:
        if a.name.lower() == name.lower():
            agent = a
            break

    if not agent:
        console.print(f"[bold red]Agent '{name}' not found.[/bold red]")
        if data.agents:
            console.print(f"Available: {', '.join(a.name for a in data.agents)}")
        return

    if search:
        memories = agent.search_memories(search)
        console.print(f"[dim]Search: '{search}' ({len(memories)} results)[/dim]\n")
    else:
        memories = agent.recent_memories(20)

    if not memories:
        console.print(f"[dim]{agent.name} has no memories yet.[/dim]")
        return

    console.print(f"[bold {agent.color}]{agent.name}'s Memories[/bold {agent.color}]\n")
    for m in memories:
        importance = "!" * int(m.effective_importance() * 5)
        console.print(f"  [{m.source}] {importance} {m.summary()}")


def cmd_preset(name: str | None = None) -> None:
    """Spawn a preset team of agents, replacing any existing session."""
    if name is None:
        # List available presets
        table = Table(title="Available Presets")
        table.add_column("Name", style="bold")
        table.add_column("Agents")
        for preset_name, configs in PRESETS.items():
            agents_str = ", ".join(f"[{c.color}]{c.name}[/{c.color}]" for c in configs)
            table.add_row(preset_name, agents_str)
        console.print(table)
        return

    if name.lower() not in PRESETS:
        console.print(f"[bold red]Unknown preset '{name}'.[/bold red]")
        console.print(f"Available: {', '.join(PRESETS.keys())}")
        return

    from society.society import Society

    society = Society()
    for config in PRESETS[name.lower()]:
        society.spawn(config=config.model_copy())

    save_session(society_to_session(society))

    console.print(f"[bold green]Preset '{name}' activated![/bold green]")
    for agent in society.agents.values():
        console.print(
            f"  [{agent.color}]{agent.name}[/{agent.color}] "
            f"— {agent.config.role} ({agent.config.temperament.value})"
        )


def cmd_remove(agent_ref: str) -> None:
    """Remove an agent from the society."""
    data = load_session()
    society = session_to_society(data)

    name = agent_ref.lstrip("@")
    # Case-insensitive lookup
    agent_key = None
    for n in society.agents:
        if n.lower() == name.lower():
            agent_key = n
            break

    if not agent_key:
        console.print(f"[bold red]Agent '{name}' not found.[/bold red]")
        if society.agents:
            console.print(f"Available: {', '.join(society.agents.keys())}")
        return

    removed = society.agents.pop(agent_key)
    save_session(society_to_session(society))
    console.print(f"[bold {removed.color}]{removed.name}[/bold {removed.color}] removed.")


def cmd_templates() -> None:
    """List available agent templates and presets."""
    table = Table(title="Agent Templates")
    table.add_column("Key", style="bold")
    table.add_column("Name")
    table.add_column("Role")
    table.add_column("Temperament")
    for key, config in AGENT_TEMPLATES.items():
        table.add_row(
            key,
            f"[{config.color}]{config.name}[/{config.color}]",
            config.role,
            config.temperament.value,
        )
    console.print(table)

    console.print()
    preset_table = Table(title="Presets")
    preset_table.add_column("Name", style="bold")
    preset_table.add_column("Agents")
    for preset_name, configs in PRESETS.items():
        agents_str = ", ".join(f"[{c.color}]{c.name}[/{c.color}]" for c in configs)
        preset_table.add_row(preset_name, agents_str)
    console.print(preset_table)


def cmd_save(name: str) -> None:
    """Save the current session to a named slot."""
    from society.session import save_named_session

    data = load_session()
    if not data.agents:
        console.print("[dim]No active session to save.[/dim]")
        return

    save_named_session(name, data)
    console.print(
        f"[bold green]Session saved as '{name}'[/bold green] "
        f"({len(data.agents)} agents, {len(data.conversation)} messages)"
    )


def cmd_load(name: str) -> None:
    """Load a named session as the active session."""
    from society.session import load_named_session

    data = load_named_session(name)
    if data is None:
        console.print(f"[bold red]Session '{name}' not found.[/bold red]")
        from society.session import list_sessions

        saved = list_sessions()
        if saved:
            console.print(f"Available: {', '.join(saved)}")
        return

    save_session(data)
    console.print(
        f"[bold green]Loaded '{name}'[/bold green] "
        f"({len(data.agents)} agents, {len(data.conversation)} messages)"
    )


def cmd_sessions() -> None:
    """List all saved sessions."""
    from society.session import list_sessions, load_named_session

    saved = list_sessions()
    if not saved:
        console.print("[dim]No saved sessions.[/dim] Use [cyan]society save <name>[/cyan] to save one.")
        return

    table = Table(title="Saved Sessions")
    table.add_column("Name", style="bold")
    table.add_column("Agents", justify="right")
    table.add_column("Messages", justify="right")

    for name in saved:
        data = load_named_session(name)
        if data:
            table.add_row(name, str(len(data.agents)), str(len(data.conversation)))
    console.print(table)


def cmd_export(fmt: str = "md", output: str | None = None) -> None:
    """Export conversation history."""
    data = load_session()
    if not data.conversation:
        console.print("[dim]No conversation to export.[/dim]")
        return

    if fmt == "json":
        import json

        content = data.model_dump_json(indent=2)
    else:
        # Markdown format
        lines = ["# Society Conversation\n"]
        if data.agents:
            lines.append("## Agents\n")
            for agent in data.agents:
                lines.append(f"- **{agent.name}** — {agent.config.role} ({agent.config.temperament.value})")
            lines.append("")
        lines.append("## Conversation\n")
        for msg in data.conversation:
            lines.append(f"**{msg.agent_name}:** {msg.content}\n")
        content = "\n".join(lines)

    if output:
        Path(output).write_text(content)
        console.print(f"[bold green]Exported to {output}[/bold green]")
    else:
        console.print(content)


def cmd_init() -> None:
    """Create a default config file."""
    from society.config import CONFIG_FILE

    if CONFIG_FILE.exists():
        console.print(f"[yellow]Config already exists:[/yellow] {CONFIG_FILE}")
    else:
        init_config()
        console.print(f"[bold green]Config created:[/bold green] {CONFIG_FILE}")
        console.print("[dim]Edit the file to customize model, temperature, agents, etc.[/dim]")


def cmd_reset() -> None:
    """Clear the current session."""
    from society.session import SESSION_FILE

    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
        console.print("[bold]Session cleared.[/bold]")
    else:
        console.print("[dim]No active session.[/dim]")


def cmd_tui() -> None:
    """Launch the Textual TUI dashboard, loading session state."""
    from society.app import SocietyApp

    data = load_session()
    if data.agents:
        society = session_to_society(data)
        app = SocietyApp(society=society)
    else:
        app = SocietyApp()

    app.run()

    # Save state on TUI exit
    save_session(society_to_session(app.society))
