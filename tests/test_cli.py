"""Unified CLI: python -m src <command>."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src import cli

HAS_REAL_DATA = Path("data/locations.json").exists()


def test_usage_and_unknown_command(capsys: pytest.CaptureFixture) -> None:
    assert cli.main([]) == 2
    assert cli.main(["--help"]) == 0
    out = capsys.readouterr().out
    for command in (*cli.COMMANDS, "all"):
        assert command in out
    assert cli.main(["dance"]) == 2
    assert "Unknown command 'dance'" in capsys.readouterr().err


def test_every_command_has_a_main() -> None:
    for command in cli.COMMANDS:
        assert callable(cli._tool(command))


def test_command_forwards_its_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, list[str]]] = []

    def tool(command):
        return lambda argv: seen.append((sys.argv[0], argv))

    monkeypatch.setattr(cli, "_tool", tool)
    before = sys.argv[0]
    assert cli.main(["layout", "--level", "30"]) == 0
    # the tool sees the unified program name; it is restored afterwards
    assert seen == [("python -m src layout", ["--level", "30"])]
    assert sys.argv[0] == before


def test_all_runs_the_steps_in_order_and_stops_at_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, list[str]]] = []

    def fake(command):
        def run(argv):
            calls.append((command, argv))
            return 1 if command == "plan" else 0

        return run

    monkeypatch.setattr(cli, "_tool", fake)
    assert cli.main(["all", "--level", "20", "--map", "m.json"]) == 1
    assert [c for c, _ in calls] == ["graph", "layout", "plan"]  # no combine
    by_command = dict(calls)
    assert by_command["graph"] == ["--level", "20"]  # graph takes no map
    assert by_command["layout"] == ["--level", "20", "--map", "m.json"]


@pytest.mark.skipif(not HAS_REAL_DATA, reason="data/locations.json not found")
def test_all_writes_every_output(tmp_path: Path) -> None:
    player = tmp_path / "player.json"
    player.write_text(json.dumps({"level": 20}))
    args = ["all", "--player-config", str(player), "--output-dir", str(tmp_path)]
    assert cli.main(args) == 0
    for name in ("graph.json", "layout.json", "schedule.json", "combined.json"):
        assert (tmp_path / name).exists(), name
