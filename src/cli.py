"""
Unified CLI: one entry point for every tool.

Usage
-----
    python -m src graph                  # graph + analysis (python -m src.main)
    python -m src layout --level 30      # layout (python -m src.layout)
    python -m src plan                   # production plan (python -m src.planner)
    python -m src combine                # combined plan (python -m src.combiner)
    python -m src relocate               # relocation plan (python -m src.relocation)
    python -m src scrape --game-version 1.72
    python -m src examples               # config/examples/player_level_<N>.json
    python -m src wizard                 # interactive profile → config/player.json
    python -m src check-facts            # game fact tables vs. the wiki
    python -m src all                    # graph, farm layout, plan, combined plan

Every command takes the options of its tool (``python -m src <command> -h``).
``all`` takes the options the tools share and stops at the first failure.
The tools' own entry points (``python -m src.layout`` …) keep working.
Settings live in config files (``src/settings.py``), not in options.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Callable
from pathlib import Path

# command -> (module with main(argv), one-line description)
COMMANDS: dict[str, tuple[str, str]] = {
    "graph": ("src.main", "dependency graph and block analysis"),
    "layout": ("src.layout.cli", "farm layout"),
    "plan": ("src.planner.cli", "production plan and login schedule (farm)"),
    "combine": ("src.combiner.cli", "farm layout sized by the production plan"),
    "relocate": (
        "src.relocation.cli",
        "keep / store / place lists to reach the layout",
    ),
    "scrape": ("src.scraper.cli", "refresh data/ from the Hay Day wiki"),
    "examples": ("src.planner.examples", "write level-default player profiles"),
    "wizard": ("src.planner.wizard", "answer questions, get a player profile"),
    "check-facts": ("src.scraper.factcheck", "compare docs/game-facts with the wiki"),
}
# the run order of "all", with the shared options each tool accepts
ALL_STEPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("graph", ("level", "player_config", "data_dir", "output_dir")),
    (
        "layout",
        ("level", "player_config", "data_dir", "output_dir", "map", "design_config"),
    ),
    ("plan", ("level", "player_config", "data_dir", "output_dir", "planner_config")),
    (
        "combine",
        (
            "level",
            "player_config",
            "data_dir",
            "output_dir",
            "map",
            "design_config",
            "planner_config",
        ),
    ),
)


def _tool(command: str) -> Callable[[list[str]], int | None]:
    return importlib.import_module(COMMANDS[command][0]).main


def _run(command: str, argv: list[str]) -> int:
    """Run one tool; its help shows ``python -m src <command>`` as the program."""
    tool = _tool(command)
    saved = sys.argv[0] if sys.argv else ""
    if sys.argv:
        sys.argv[0] = f"python -m src {command}"  # argparse names it after argv[0]
    try:
        return tool(argv) or 0
    finally:
        if sys.argv:
            sys.argv[0] = saved


def _usage() -> str:
    lines = ["usage: python -m src <command> [options]", "", "commands:"]
    lines += [f"  {name:<12} {desc}" for name, (_, desc) in COMMANDS.items()]
    lines.append(f"  {'all':<12} graph, farm layout, plan and combined plan in one run")
    lines += ["", "python -m src <command> -h shows the options of a command."]
    return "\n".join(lines)


def _all_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src all",
        description="Graph, farm layout, production plan and combined plan in one run.",
    )
    parser.add_argument("--level", type=int, default=None)
    parser.add_argument("--player-config", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--map", type=Path, default=None, help="Farm map")
    parser.add_argument("--design-config", type=Path, default=None)
    parser.add_argument("--planner-config", type=Path, default=None)
    return parser.parse_args(argv)


def _forward(args: argparse.Namespace, names: tuple[str, ...]) -> list[str]:
    """The shared options that were given, as arguments for one tool."""
    out: list[str] = []
    for name in names:
        value = getattr(args, name)
        if value is not None:
            out += [f"--{name.replace('_', '-')}", str(value)]
    return out


def run_all(argv: list[str]) -> int:
    args = _all_args(argv)
    for command, names in ALL_STEPS:
        code = _run(command, _forward(args, names))
        if code:
            print(f"python -m src all: {command} failed", file=sys.stderr)
            return code
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(_usage())
        return 0 if argv else 2
    command, rest = argv[0], argv[1:]
    if command == "all":
        return run_all(rest)
    if command not in COMMANDS:
        print(f"Unknown command {command!r}\n\n{_usage()}", file=sys.stderr)
        return 2
    return _run(command, rest)
