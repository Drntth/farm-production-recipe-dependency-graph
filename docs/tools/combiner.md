# Combiner

The Combiner (`src/combiner/`) is the only place that joins the Layout Planner and the Production Planner.

## Combiner purpose

Merge the results of the Layout Planner and the Production Planner into one coordinated, usable farm plan. Farm only.

## How the Combiner works

`python -m src.combiner` (package `src/combiner/`, the only code that imports both planners):

1. **Production plan**: runs the Production Planner for the profile (same `production` settings in `config/planner.json`).
2. **Block sizes from the quantities** (`sizing_from_plan`): the plan becomes a layout `Sizing` (`src/layout/sizing.py`), so the Layout Planner itself never imports the Production Planner:
   - every crop's fields are split among the blocks in proportion to how much of the crop their buildings use; fields of crops that are only sold and owned fields the plan leaves empty go to the Shared fields block;
   - trees and bushes the profile leaves open get the recommended count;
   - the goods flows between locations (goods per hour) strengthen the pull between the blocks that exchange the most.
3. **Expansion-friendly** (`combiner.lookahead`, default 5 levels): more copies of placed buildings and more fields unlocked within the lookahead get reserved space in their blocks; new buildings are listed with the tiles they will need, and the report warns when the free land is too small for them.
4. **A→B processing order**: the blocks are placed upstream first (`combiner.strategy: flow`, default; it overrides the `strategy` of `design.json`; `all` is not allowed here), each pulled toward the blocks it exchanges goods with. When a block does not fit, the Layout Planner's fallback applies: `item_gap` first, then the design templates, then the reserve in 1 % steps; only if a block does not fit even without reserve, the size order takes over.
5. **Functional plan always, design on request**: `design_layer: true` in `design.json` adds the paths and the decoration band of the Layout Planner. Gap, reserve and templates also come from `design.json`.
6. Writes `output/combined.json` (settings used, summary, blocks with copies, fields, busy share and output per hour, goods flows between blocks with the tiles between them and the weighted flow distance Σ goods / h × tiles apart (lower is better), expansion, the full layout and schedule), `output/combined.md` (one report: blocks upstream → downstream, the heaviest flows and the weighted flow distance, expansion, then the layout and the schedule sections) and `output/combined.svg`; with `block_images: true` also one SVG per block in `output/combined_blocks/`. The `settings` key of `combined.json` holds the `design`, `production` and `combiner` settings used.

The sizes inherit the estimates of the Production Planner (tree / bush yield, honeycomb rate; see [docs/wiki-gaps.md](../wiki-gaps.md)): measuring them changes the counts, not the method. Nectar bushes are not sized: the plan gives the bushes to plant per day, but how long a bush stands is unknown, so their count stays the profile's.
