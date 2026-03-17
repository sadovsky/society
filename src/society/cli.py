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

    subparsers = parser.add_subparsers(dest="command")

    # spawn
    sp = subparsers.add_parser("spawn", help="Spawn an agent (template name or custom role)")
    sp.add_argument("role", help="Template name (architect, critic, etc.) or custom role description")

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
        cmd_history,
        cmd_memories,
        cmd_reset,
        cmd_solve,
        cmd_spawn,
        cmd_status,
        cmd_tui,
    )

    dispatch = {
        "spawn": lambda: cmd_spawn(args.role),
        "solve": lambda: cmd_solve(args.question),
        "ask": lambda: cmd_ask(args.agent, args.question),
        "debate": lambda: cmd_debate(args.topic, args.rounds),
        "consensus": lambda: cmd_consensus(),
        "status": lambda: cmd_status(),
        "history": lambda: cmd_history(),
        "memories": lambda: cmd_memories(args.agent),
        "reset": lambda: cmd_reset(),
        "tui": lambda: cmd_tui(),
    }
    dispatch[args.command]()


if __name__ == "__main__":
    main()
