# Architecture

Two diagrams of the code base: which package imports which, and how data moves from the wiki to the output files. The rules behind them are in the [README](../README.md#architecture). GitHub renders the Mermaid blocks; elsewhere paste them into [mermaid.live](https://mermaid.live).

## Package dependencies

Each node is a package or module under `src/`. A solid arrow is a static import (`A --> B`: A imports B). A dotted arrow is the unified CLI starting a tool by name (`importlib`). `tests/test_architecture.py` fails when the solid arrows differ from the real imports, so update this diagram together with the code.

```mermaid
flowchart TB
    subgraph entry[Entry points]
        cli[cli.py<br/>python -m src]
        main[main.py<br/>graph CLI]
    end
    subgraph tools[Tools]
        layout[layout/<br/>Layout Planner]
        planner[planner/<br/>Production Planner]
        combiner[combiner/<br/>Combiner]
        relocation[relocation/<br/>relocation plan]
    end
    subgraph core[Core]
        config[config.py<br/>player profile]
        settings[settings.py<br/>tool settings]
        dgraph[graph/<br/>dependency graph]
        loaders[loaders/<br/>data loader]
        models[models/<br/>pydantic models]
    end
    subgraph io[Data in and out]
        scraper[scraper/<br/>wiki scraper]
        exporters[exporters/<br/>JSON, CSV, GraphML]
    end

    cli -.-> main
    cli -.-> layout
    cli -.-> planner
    cli -.-> combiner
    cli -.-> relocation
    cli -.-> scraper

    main --> config
    main --> exporters
    main --> dgraph
    main --> loaders

    combiner --> config
    combiner --> layout
    combiner --> loaders
    combiner --> models
    combiner --> planner
    combiner --> settings

    layout --> config
    layout --> dgraph
    layout --> loaders
    layout --> models
    layout --> settings

    planner --> config
    planner --> loaders
    planner --> models
    planner --> settings

    relocation --> layout
    relocation --> loaders
    relocation --> models

    config --> loaders
    config --> models
    dgraph --> loaders
    dgraph --> models
    loaders --> models
    scraper --> models
```

What to read from it:

- `layout` and `planner` have no arrow between them: they stay independent, only `combiner` joins them.
- Every arrow points down towards `models`; the core never imports a tool.
- `relocation` imports only the farm map model from `layout` (`layout/farm_map.py`) and reads the layout as a JSON file; it never imports `planner`.

## Data flow

From the wiki to the files a player reads. Rounded nodes are files, rectangles are commands.

```mermaid
flowchart LR
    wiki([Hay Day Fandom wiki]) --> scrape[python -m src scrape]
    scrape --> data([data/*.json])
    overrides([data/overrides/*.json<br/>measured, estimated]) --> load[loaders]
    data --> load
    profile([config/player.json]) --> load

    load --> gcmd[python -m src graph]
    gcmd --> gout([graph.json, .csv, .graphml<br/>analysis.json])

    editor[tools/farm_map_editor.html] --> farmmap([config/farm_map.json])
    farmmap --> layoutcmd[python -m src layout]
    design([config/design.json<br/>config/templates/]) --> layoutcmd
    load --> layoutcmd
    layoutcmd --> layoutout([layout.json, .md, .svg])

    plannercfg([config/planner.json]) --> plancmd[python -m src plan]
    load --> plancmd
    plancmd --> planout([capacity.json<br/>schedule.json, .md])

    load --> combinecmd[python -m src combine]
    farmmap --> combinecmd
    design --> combinecmd
    plannercfg --> combinecmd
    combinecmd --> combout([combined.json, .md, .svg])

    combout --> relocate[python -m src relocate]
    layoutout -.->|without combined.json| relocate
    farmmap -->|current farm| relocate
    relocate --> relout([relocation.json, .md])

    layoutout -.->|overlay| editor
    combout -.->|overlay| editor
```

- `python -m src all` runs graph, layout, plan and combine in this order; `relocate` is separate.
- The Combiner runs the Layout Planner and the Production Planner itself; it does not read their output files.
- Every generated file goes to `output/` (git-ignored).
