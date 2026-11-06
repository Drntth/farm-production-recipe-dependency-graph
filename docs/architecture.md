# Architecture

Two diagrams of the code base: which package imports which, and how data moves from the wiki to the output files. The rules behind them are in the [README](../README.md#architecture). GitHub renders the Mermaid blocks; elsewhere paste them into [mermaid.live](https://mermaid.live).

## Package dependencies

Each node is a package or module under `src/`. A solid arrow is a static import (`A --> B`: A imports B). A dotted arrow is the unified CLI starting a tool by name (`importlib`). The `cli.py` of each tool package is one node, `toolcli`: it reads the input files and writes the outputs, while `api/` runs the same steps on objects without file IO. `tests/test_architecture.py` fails when the solid arrows differ from the real imports, so update this diagram together with the code.

```mermaid
flowchart TB
    subgraph entry[Entry points]
        cli[cli.py<br/>python -m src]
        main[main.py<br/>graph CLI]
        toolcli[tool cli.py files<br/>file IO]
    end
    api[api/<br/>Core API, no file IO]
    subgraph tools[Tools]
        layout[layout/<br/>Layout Planner]
        planner[planner/<br/>Production Planner]
        combiner[combiner/<br/>Combiner]
        relocation[relocation/<br/>relocation plan]
        recommend[recommend/<br/>level recommendations]
    end
    subgraph core[Core]
        config[config.py<br/>player profile]
        fprofile[farm_profile.py<br/>farm profile]
        settings[settings.py<br/>tool settings]
        dgraph[graph/<br/>dependency graph]
        loaders[loaders/<br/>data loader]
        models[models/<br/>pydantic models]
        schema[schema.py<br/>schema_version, migrations]
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
    cli -.-> fprofile
    cli -.-> loaders
    cli -.-> recommend

    toolcli --> api
    toolcli --> config
    toolcli --> fprofile
    toolcli --> layout
    toolcli --> loaders
    toolcli --> recommend
    toolcli --> scraper
    toolcli --> settings

    api --> combiner
    api --> config
    api --> layout
    api --> loaders
    api --> planner
    api --> relocation
    api --> settings

    fprofile --> config
    fprofile --> layout
    fprofile --> schema
    fprofile --> settings

    config --> schema
    loaders --> schema
    settings --> schema
    layout --> schema
    planner --> schema

    main --> config
    main --> fprofile
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

    recommend --> api
    recommend --> layout
    recommend --> loaders
    recommend --> planner
    recommend --> schema
    recommend --> settings

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
    wizard[python -m src wizard] --> profile([config/player.json])
    data --> wizard
    data --> examples[python -m src examples]
    examples --> exout([config/examples/<br/>player_level_N.json])

    load --> gcmd[python -m src graph]
    profile --> gcmd
    gcmd --> gout([graph.json, .csv, .graphml<br/>analysis.json])

    editor[tools/farm_map_editor.html] --> farmmap([data/base_map.json<br/>config/profile_map.json])
    farmmap --> layoutcmd[python -m src layout]
    design([config/design.json<br/>config/templates/]) --> layoutcmd
    load --> layoutcmd
    profile --> layoutcmd
    layoutcmd --> layoutout([layout.json, .md, .svg])

    plannercfg([config/planner.json]) --> plancmd[python -m src plan]
    load --> plancmd
    profile --> plancmd
    plancmd --> planout([capacity.json<br/>schedule.json, .md])

    load --> combinecmd[python -m src combine]
    profile --> combinecmd
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

    load --> reccmd[python -m src recommend]
    farmmap -->|base map only| reccmd
    reccmd --> recout([recommendations/<br/>level_N.json, .svg, index.json])
    recout --> web[web/: Astro build]
    web --> site([static site<br/>GitHub Pages])

    facts([docs/game-facts/*.md]) --> check[python -m src check-facts]
    wiki --> check
    check --> factout([fact_check.md])
```

- `python -m src all` runs graph, layout, plan and combine in this order; `relocate` is separate.
- The Combiner runs the Layout Planner and the Production Planner itself; it does not read their output files.
- Every generated file goes to `output/` (git-ignored), except the profiles of `wizard` (`config/player.json`) and `examples` (`config/examples/`).
- The player profile is read by `config.py` (`load_player_config`), not by the data loader; without `config/player.json` the committed example is used.
