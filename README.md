# Farm Production Graph

A graph-based system for analysing Hay Day production chains, designing farm layouts around reusable production blocks, and generating capacity-aware production schedules.

The system converts locations, resources and recipes into a weighted directed graph. From this graph it identifies tightly coupled production blocks, supports expansion-friendly arrangement of the farm, and, using only static player data, produces practical production quantities and login schedules.

Planning is organised in two layers:

- **Functional planning** (always active): production logic, blocks, quantities, schedules, capacities and processing order.
- **Design planning** (optional): decorative elements, walkable paths between blocks, and aesthetic placement that still respects the functional constraints.

**Status:** v2.0.0 (Core API and data model), a local command-line platform (351 tests, CI on every push). It covers every wiki level of game version 1.73: the dependency graph, a farm layout of named production blocks with paths and design templates, a production plan with a login schedule, the combined plan, a relocation plan from the current farm, and a browser-based map editor. Next: v2.0.1 (map editor for the split map) and v2.1 of the web app plan, see the [roadmap](docs/roadmap.md), the [v2 design](docs/v2-design.md) and the [changelog](CHANGELOG.md).

**New here? Start with the [user guide](docs/user-guide.md).**

---

## Architecture

Three independent tools share one core. Each tool can run on its own. The Combiner links their results when both are available.

```text
                      ┌────────────────────────────┐
                      │ Core                       │
                      │ player config · data model │
                      │ loader · dependency graph  │
                      └─────────────┬──────────────┘
                 ┌──────────────────┴──────────────────┐
                 ▼                                     ▼
     ┌───────────────────────┐             ┌───────────────────────┐
     │ 1. Layout Planner     │             │ 2. Production Planner │
     │ blocks, footprints,   │             │ quantities, capacity, │
     │ visual layout         │             │ schedule              │
     └───────────┬───────────┘             └───────────┬───────────┘
                 └──────────────────┬──────────────────┘
                                    ▼
                      ┌────────────────────────────┐
                      │ 3. Combiner (optional)     │
                      │ layout sized by production │
                      └────────────────────────────┘
```

Design decisions:

- **Layout without production.** The Layout Planner can produce a usable layout, including a graphical one, from the graph, the blocks and the building footprints alone. Production data only refines block sizes, for example how many fields or pastures a block needs.
- **Production without layout.** The Production Planner never needs a layout.
- **Separate UX.** Each tool has its own CLI command and its own output files. The Combiner is a third, optional step.

Package dependencies and the data flow from the wiki to the output files: [docs/architecture.md](docs/architecture.md). Where each module lives: [docs/modules.md](docs/modules.md).

## Quick start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config/player.example.json config/player.json   # optional: your own profile
python -m src all                                   # graph, layout, plan, combined plan → output/
```

Open `output/combined.md` and `output/combined.svg`. Every command and option: [docs/cli.md](docs/cli.md). Tool settings: [docs/settings.md](docs/settings.md).

## Documentation

| Topic              | File                                                                                                                                                                                                                            |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Using the tools    | [user guide](docs/user-guide.md), [commands](docs/cli.md), [settings](docs/settings.md), [player profile](docs/player-profile.md)                                                                                               |
| How the tools work | [Layout Planner](docs/tools/layout-planner.md), [Production Planner](docs/tools/production-planner.md), [Combiner](docs/tools/combiner.md), [relocation plan](docs/tools/relocation.md), [map editor](docs/tools/map-editor.md) |
| Data and graph     | [data model](docs/data-model.md), [graph model](docs/graph-model.md), [data sources](docs/data-sources.md)                                                                                                                      |
| Code               | [architecture](docs/architecture.md), [modules](docs/modules.md), [development](docs/development.md) (setup, tests, releases), [AGENTS.md](AGENTS.md) (conventions), [CONTEXT.md](CONTEXT.md) (domain terms)                    |
| Game knowledge     | [docs index](docs/README.md): game facts, [game updates](docs/game-updates.md), [wiki gaps](docs/wiki-gaps.md)                                                                                                                  |
| History and plans  | [roadmap](docs/roadmap.md), [v2 design](docs/v2-design.md), [changelog](CHANGELOG.md)                                                                                                                                           |

## License

The code is under the [MIT License](LICENSE). The game data in `data/` is derived from the [Hay Day Wiki](https://hayday.fandom.com/) and is licensed under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/), like the wiki. The hand-measured values and estimates in `data/overrides/` are the maintainer's own work and are released under the same license, because they extend the wiki data.

## Disclaimer

This project is an independent fan-made analysis tool. This material is unofficial and is not endorsed by Supercell. For more information see Supercell's Fan Content Policy: <https://supercell.com/en/fan-content-policy/>.

Hay Day and related assets are properties of Supercell.
