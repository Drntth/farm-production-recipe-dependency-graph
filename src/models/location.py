"""Location entity - anything that occupies space on the farm."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class LocationType(str, Enum):
    """Allowed location types as defined by the data model."""

    PRODUCTION = "production"
    ANIMAL = "animal"
    FIELD = "field"
    TREE = "tree"
    BUSH = "bush"
    STORAGE = "storage"
    OTHER = "other"


class Location(BaseModel):
    """
    A farm location (production building, animal shelter, field, tree, etc.).

    Mandatory fields follow the Layout Planner schema so that the same
    structure maps cleanly to a future PostgreSQL table.
    """

    id: str = Field(..., description="Snake_case English identifier, e.g. 'dairy'")
    name: str = Field(..., description="Human-readable name, e.g. 'Dairy'")
    type: LocationType = Field(..., description="Category of the location")
    unlock_level: int = Field(..., ge=1, description="Player level required to unlock")

    description: str | None = None
    max_slots: int | None = Field(
        None, ge=1, description="Production slots if applicable"
    )

    @field_validator("id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError(
                f"Location id must be lower-case snake_case alphanumeric, got: {v!r}"
            )
        return v

    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
    }
