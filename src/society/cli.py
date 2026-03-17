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
        "--agents",
        nargs="*",
        choices=["architect", "critic", "creative", "pragmatist", "facilitator"],
        help="Which agent templates to spawn (default: all)",
    )

    args = parser.parse_args()

    from society.app import SocietyApp

    app = SocietyApp()

    # If specific agents requested, replace defaults
    if args.agents:
        app.society.agents.clear()
        for template in args.agents:
            app.society.spawn(template_name=template)

    app.run()


if __name__ == "__main__":
    main()
