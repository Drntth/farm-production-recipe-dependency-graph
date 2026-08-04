"""
JSON data loader for locations, resources and recipes.

Loads the three normalised JSON files, validates them against the Pydantic
models, optionally filters by maximum unlock level, and returns a single
DataSet object ready for graph generation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from src.models import Location, Recipe, Resource

logger = logging.getLogger(__name__)


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
    ) -> None:
        self.locations: dict[str, Location] = {loc.id: loc for loc in locations}
        self.resources: dict[str, Resource] = {res.id: res for res in resources}
        self.recipes: dict[str, Recipe] = {rec.id: rec for rec in recipes}

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
        return DataSet(locations, resources, recipes)

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


def load_data(
    data_dir: Path | str,
    max_level: int | None = None,
) -> DataSet:
    """
    Load and validate the three core JSON files from *data_dir*.

    Parameters
    ----------
    data_dir:
        Directory containing ``locations.json``, ``resources.json`` and
        ``recipes.json``.
    max_level:
        If given, only entities with ``unlock_level <= max_level`` are kept.

    Returns
    -------
    DataSet
        Validated, optionally filtered collection of entities.
    """
    data_dir = Path(data_dir)

    logger.info("Loading data from %s", data_dir)

    locations_raw = _load_json_file(data_dir / "locations.json")
    resources_raw = _load_json_file(data_dir / "resources.json")
    recipes_raw = _load_json_file(data_dir / "recipes.json")

    locations = _parse_entities(locations_raw, Location, "locations")
    resources = _parse_entities(resources_raw, Resource, "resources")
    recipes = _parse_entities(recipes_raw, Recipe, "recipes")

    dataset = DataSet(locations, resources, recipes)
    logger.info("Loaded %s", dataset.summary())

    if max_level is not None:
        dataset = dataset.filter_by_max_level(max_level)
        logger.info("After max_level=%s filter: %s", max_level, dataset.summary())

    return dataset
