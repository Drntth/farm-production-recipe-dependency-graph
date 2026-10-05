"""
JSON data loader for locations, resources, recipes and level limits.

Loads the normalised JSON files, merges manual overrides from
``data/overrides/``, validates everything against the Pydantic models,
optionally filters by maximum unlock level, and returns a single DataSet
object ready for graph generation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from src.models import LevelLimits, Location, Recipe, Resource

logger = logging.getLogger(__name__)

OVERRIDES_DIRNAME = "overrides"


class DataSet:
    """
    In-memory collection of all validated entities.

    Provides fast lookup by id and guarantees referential integrity
    checks (source_location_id, location_id, resource_id references).
    """

    def __init__(
        self,
        locations: list[Location],
        resources: list[Resource],
        recipes: list[Recipe],
        level_limits: LevelLimits | None = None,
    ) -> None:
        self.locations: dict[str, Location] = {loc.id: loc for loc in locations}
        self.resources: dict[str, Resource] = {res.id: res for res in resources}
        self.recipes: dict[str, Recipe] = {rec.id: rec for rec in recipes}
        self.level_limits: LevelLimits | None = level_limits

        self._validate_references()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def location_list(self) -> list[Location]:
        return list(self.locations.values())

    @property
    def resource_list(self) -> list[Resource]:
        return list(self.resources.values())

    @property
    def recipe_list(self) -> list[Recipe]:
        return list(self.recipes.values())

    def filter_by_max_level(self, max_level: int) -> DataSet:
        """Return a new DataSet containing only entities with unlock_level <= max_level."""
        locations = [l for l in self.location_list if l.unlock_level <= max_level]
        resources = [r for r in self.resource_list if r.unlock_level <= max_level]
        recipes = [r for r in self.recipe_list if r.unlock_level <= max_level]
        limits = (
            self.level_limits.filter_by_max_level(max_level)
            if self.level_limits is not None
            else None
        )
        return DataSet(locations, resources, recipes, limits)

    def summary(self) -> str:
        return (
            f"DataSet(locations={len(self.locations)}, "
            f"resources={len(self.resources)}, "
            f"recipes={len(self.recipes)})"
        )

    # ------------------------------------------------------------------
    # Integrity checks
    # ------------------------------------------------------------------

    def _validate_references(self) -> None:
        """Raise ValueError if any foreign-key style reference is broken."""
        errors: list[str] = []

        for res in self.resources.values():
            if res.source_location_id and res.source_location_id not in self.locations:
                errors.append(
                    f"Resource '{res.id}' references unknown source_location_id "
                    f"'{res.source_location_id}'"
                )

        for rec in self.recipes.values():
            if rec.location_id not in self.locations:
                errors.append(
                    f"Recipe '{rec.id}' references unknown location_id '{rec.location_id}'"
                )

            for inp in rec.inputs:
                if inp.resource_id not in self.resources:
                    logger.warning(
                        "Recipe '%s' uses external resource '%s'",
                        rec.id,
                        inp.resource_id,
                    )
            if rec.output.resource_id not in self.resources:
                errors.append(
                    f"Recipe '{rec.id}' output references unknown resource_id "
                    f"'{rec.output.resource_id}'"
                )

        if self.level_limits is not None:
            for inst in self.level_limits.location_instances:
                if inst.location_id not in self.locations:
                    errors.append(
                        f"Level limit instance {inst.instance} references unknown "
                        f"location_id '{inst.location_id}'"
                    )

        if errors:
            raise ValueError(
                "Referential integrity errors:\n  - " + "\n  - ".join(errors)
            )


# ----------------------------------------------------------------------
# Loading helpers
# ----------------------------------------------------------------------


def _load_json_file(path: Path) -> list:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}, got {type(data).__name__}")
    return data


def _parse_entities(raw: list, model_cls, label: str):
    entities = []
    for idx, item in enumerate(raw):
        try:
            entities.append(model_cls.model_validate(item))
        except ValidationError as exc:
            raise ValueError(
                f"Validation error in {label}[{idx}] (id={item.get('id', '?')}):\n{exc}"
            ) from exc
    return entities


def apply_overrides(raw: list[dict], overrides: list[dict], label: str) -> list[dict]:
    """
    Merge manual *overrides* into scraped *raw* entities by ``id``.

    An override with an existing id patches only the fields it lists;
    one with a new id adds a complete entity. ``null`` values mean
    "not filled in yet" and are skipped, so template entries are harmless.
    Order of *raw* is kept.
    """
    by_id = {item["id"]: dict(item) for item in raw}
    for idx, entry in enumerate(overrides):
        oid = entry.get("id")
        if not oid:
            raise ValueError(f"Override {label}[{idx}] has no 'id'")
        override = {k: v for k, v in entry.items() if v is not None}
        if len(override) == 1:  # only the id: nothing filled in yet
            continue
        if oid in by_id:
            by_id[oid].update(override)
            logger.info("Override patched %s '%s'", label, oid)
        else:
            by_id[oid] = dict(override)
            logger.info("Override added %s '%s'", label, oid)
    return list(by_id.values())


def _load_with_overrides(
    data_dir: Path, filename: str, overrides_dir: Path | None
) -> list[dict]:
    raw = _load_json_file(data_dir / filename)
    if overrides_dir is not None and (overrides_dir / filename).exists():
        overrides = _load_json_file(overrides_dir / filename)
        raw = apply_overrides(raw, overrides, filename.removesuffix(".json"))
    return raw


def _load_level_limits(data_dir: Path) -> LevelLimits | None:
    path = data_dir / "level_limits.json"
    if not path.exists():
        logger.info("No level_limits.json in %s", data_dir)
        return None
    try:
        return LevelLimits.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except ValidationError as exc:
        raise ValueError(f"Validation error in {path}:\n{exc}") from exc


def load_data(
    data_dir: Path | str,
    max_level: int | None = None,
    *,
    apply_data_overrides: bool = True,
) -> DataSet:
    """
    Load and validate the core JSON files from *data_dir*.

    Parameters
    ----------
    data_dir:
        Directory containing ``locations.json``, ``resources.json``,
        ``recipes.json`` and optionally ``level_limits.json``.
    max_level:
        If given, only entities with ``unlock_level <= max_level`` are kept.
    apply_data_overrides:
        Merge ``<data_dir>/overrides/*.json`` on top of the scraped data.

    Returns
    -------
    DataSet
        Validated, optionally filtered collection of entities.
    """
    data_dir = Path(data_dir)
    overrides_dir = data_dir / OVERRIDES_DIRNAME if apply_data_overrides else None

    logger.info("Loading data from %s", data_dir)

    locations_raw = _load_with_overrides(data_dir, "locations.json", overrides_dir)
    resources_raw = _load_with_overrides(data_dir, "resources.json", overrides_dir)
    recipes_raw = _load_with_overrides(data_dir, "recipes.json", overrides_dir)

    locations = _parse_entities(locations_raw, Location, "locations")
    resources = _parse_entities(resources_raw, Resource, "resources")
    recipes = _parse_entities(recipes_raw, Recipe, "recipes")

    dataset = DataSet(locations, resources, recipes, _load_level_limits(data_dir))
    logger.info("Loaded %s", dataset.summary())

    if max_level is not None:
        dataset = dataset.filter_by_max_level(max_level)
        logger.info("After max_level=%s filter: %s", max_level, dataset.summary())

    return dataset
