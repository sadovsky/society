"""CLI entry point for Society."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="society",
        description="A terminal-native multi-agent system where AI personas collaborate, debate, and evolve.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="society 0.1.0",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Claude model to use (e.g. claude-opus-4-20250514, claude-haiku-4-5-20251001)",
    )

    subparsers = parser.add_subparsers(dest="command")

    # spawn
    sp = subparsers.add_parser("spawn", help="Spawn an agent (template name or custom role)")
    sp.add_argument("role", help="Template name (architect, critic, etc.) or custom role description")

    # preset
    sp = subparsers.add_parser("preset", help="Spawn a preset team of agents")
    sp.add_argument("name", nargs="?", default=None, help="Preset name (software, review, brainstorm)")

    # remove
    sp = subparsers.add_parser("remove", help="Remove an agent from the society")
    sp.add_argument("agent", help="Agent name (e.g. Rex or @Rex)")

    # solve
    sp = subparsers.add_parser("solve", help="Ask all agents a question")
    sp.add_argument("question", help="The question to ask")

    # ask
    sp = subparsers.add_parser("ask", help="Ask a specific agent a question")
    sp.add_argument("agent", help="Agent name (e.g. @Aria or Aria)")
    sp.add_argument("question", help="The question to ask")

    # debate
    sp = subparsers.add_parser("debate", help="Multi-round debate on a topic")
    sp.add_argument("topic", help="The debate topic")
    sp.add_argument("--rounds", type=int, default=3, help="Number of rounds (default: 3)")

    # consensus
    subparsers.add_parser("consensus", help="Synthesize group consensus")

    # status
    subparsers.add_parser("status", help="Show agents and session info")

    # history
    subparsers.add_parser("history", help="Show conversation history")

    # memories
    sp = subparsers.add_parser("memories", help="Show an agent's memories")
    sp.add_argument("agent", help="Agent name (e.g. @Aria)")
    sp.add_argument("--search", "-s", default=None, help="Search memories by keyword")

    # templates
    subparsers.add_parser("templates", help="List available agent templates and presets")

    # save
    sp = subparsers.add_parser("save", help="Save current session with a name")
    sp.add_argument("name", help="Session name")

    # load
    sp = subparsers.add_parser("load", help="Load a saved session")
    sp.add_argument("name", help="Session name")

    # sessions
    subparsers.add_parser("sessions", help="List saved sessions")

    # export
    sp = subparsers.add_parser("export", help="Export conversation history")
    sp.add_argument("--format", dest="fmt", choices=["md", "json"], default="md", help="Output format (default: md)")
    sp.add_argument("--output", "-o", default=None, help="Output file (default: stdout)")

    # reset
    subparsers.add_parser("reset", help="Clear session and start fresh")

    # tui
    subparsers.add_parser("tui", help="Launch the interactive TUI dashboard")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Lazy imports to keep startup fast
    from society.commands import (
        cmd_ask,
        cmd_consensus,
        cmd_debate,
        cmd_export,
        cmd_history,
        cmd_load,
        cmd_memories,
        cmd_preset,
        cmd_remove,
        cmd_reset,
        cmd_save,
        cmd_sessions,
        cmd_solve,
        cmd_spawn,
        cmd_status,
        cmd_templates,
        cmd_tui,
    )

    dispatch = {
        "spawn": lambda: cmd_spawn(args.role),
        "preset": lambda: cmd_preset(args.name),
        "remove": lambda: cmd_remove(args.agent),
        "solve": lambda: cmd_solve(args.question, model=args.model),
        "ask": lambda: cmd_ask(args.agent, args.question, model=args.model),
        "debate": lambda: cmd_debate(args.topic, args.rounds, model=args.model),
        "consensus": lambda: cmd_consensus(model=args.model),
        "status": lambda: cmd_status(),
        "history": lambda: cmd_history(),
        "memories": lambda: cmd_memories(args.agent, search=args.search),
        "templates": lambda: cmd_templates(),
        "save": lambda: cmd_save(args.name),
        "load": lambda: cmd_load(args.name),
        "sessions": lambda: cmd_sessions(),
        "export": lambda: cmd_export(fmt=args.fmt, output=args.output),
        "reset": lambda: cmd_reset(),
        "tui": lambda: cmd_tui(),
    }
    dispatch[args.command]()


if __name__ == "__main__":
    main()
