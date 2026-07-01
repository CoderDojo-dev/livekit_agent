"""Alternate entry shim. Delegates to the AgentServer composition root in server.py so that
both `python -m server console` and `python -m entrypoints.worker console` run the same wiring.
"""
from __future__ import annotations

from livekit import agents

from server import server


def main() -> None:
    """Run the worker CLI (supports the console / dev / start subcommands)."""
    agents.cli.run_app(server)


if __name__ == "__main__":
    main()