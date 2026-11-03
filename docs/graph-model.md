# Graph model

How `src/graph/` turns the data into a weighted directed graph, and what the analysis computes.

The system builds a directed weighted dependency graph (NetworkX `DiGraph`).

## Nodes

Every Location and every Resource becomes a node.

| Attribute             | Present on       | Description                             |
| --------------------- | ---------------- | --------------------------------------- |
| `kind`                | all              | `"location"` or `"resource"`            |
| `id`                  | all              | Original entity id                      |
| `name`                | all              | Human-readable name                     |
| `type`                | all              | LocationType / ResourceType value       |
| `unlock_level`        | all              | Player level required                   |
| `source_location_id`  | resources (raw)  | Producing location                      |
| `area`                | locations        | `farm` / `town` / `fishing_lake`        |
| `movable`             | locations        | `false` for fixed buildings             |
| `rotatable`           | locations        | footprint can be turned                 |
| `footprint_width`     | locations (opt.) | Width in tiles                          |
| `footprint_height`    | locations (opt.) | Height in tiles                         |
| `animal_capacity`     | locations (opt.) | Animals per shelter                     |
| `base_slots`          | locations (opt.) | Slots per copy at purchase              |
| `max_slots`           | locations (opt.) | Maximum slots per copy (default 9)      |
| `lifetime_yield`      | locations (opt.) | Goods a tree / bush gives in its life   |
| `lifetime_harvests`   | locations (opt.) | Harvests of a tree / bush, incl. revive |
| `max_in_barn`         | resources (opt.) | Storage limit for the resource          |
| `growth_time_seconds` | resources (opt.) | Growth / animal production time         |

## Edges - three semantic kinds

```text
location  ──PRODUCES──►  resource  ──CONSUMES──►  location  ──OUTPUTS──►  resource
(field)                  (soybean)                (feed_mill)             (cow_feed)
```

1. **PRODUCES** (`location → resource`)  
   Created for every resource of type `crop`, `animal_product` or `ore` from its `source_location_id`.  
   Captures “this field / animal shelter / mine produces this raw good”.

2. **CONSUMES** (`resource → location`)  
   Created for every recipe input that exists in `resources.json`.  
   Weight = `input_amount / output_amount` (stoichiometry).  
   Captures “this resource is consumed at this production building”.

3. **OUTPUTS** (`location → resource`)  
   Created for every recipe output.  
   Captures “this building produces this (processed) good”.  
   Skipped for feeding recipes, whose output already has a PRODUCES edge (`cow_feed ─CONSUMES→ cow_pasture ─PRODUCES→ milk`).

## Weighting rules

| Edge kind | Weight formula               | Default  |
| --------- | ---------------------------- | -------- |
| PRODUCES  | constant                     | 1.0      |
| CONSUMES  | input_amount / output_amount | e.g. 3.0 |
| OUTPUTS   | constant                     | 1.0      |

Higher weight means stronger coupling → the two locations should be placed closer together on the farm.

The graph is a `DiGraph`, so there is at most one edge per ordered node pair. When several recipes create the same edge, it is merged: the weights are summed, the `recipe_id` values are kept as a sorted comma-separated list, and `amount` and `ratio` keep their maximum.

## Why this model supports layout planning

- High-weight CONSUMES edges give direct proximity signals.
- The Layout Planner forms its named blocks from the coupling between locations (anchor method, `src/layout/blocks.py`); see [Layout Planner](tools/layout-planner.md).
- Community detection (Louvain) on the undirected location-proximity graph is an analysis output only (`analysis.json`); the layout does not use it.
- Shortest-path lengths and multi-level weights become the “desired distance” cost for later placement heuristics.
- The same builder accepts a level-filtered `DataSet`, so different player levels produce different graphs.
- The Production Planner does not use the graph: it works from the recipes directly. The Combiner passes its goods flows to the layout as a `Sizing`.

## Analysis capabilities (already implemented)

- Location proximity graph with multi-level hop propagation and decay
- Production-block detection (Louvain community detection; analysis only)
- Degree and betweenness centrality (bottleneck ranking)
- Dependency path queries
- Full analysis payload written to `output/analysis.json`
