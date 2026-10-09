"""Per-level limits - how many fields and location instances a player level allows."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class FieldGrant(BaseModel):
    """Fields granted when reaching a level (one row per level)."""

    level: int = Field(..., ge=1)
    count: int = Field(..., ge=1, description="Number of new fields at this level")

    model_config = {"extra": "forbid"}


class LocationInstance(BaseModel):
    """
    One placeable copy of a location and the level it unlocks at.

    Example: feed_mill has instance 1 at level 2 and instance 2 at level 12.
    """

    location_id: str
    instance: int = Field(..., ge=1, description="1-based copy number")
    unlock_level: int = Field(..., ge=1)

    @field_validator("location_id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError(
                f"location_id must be lower-case snake_case alphanumeric, got: {v!r}"
            )
        return v

    model_config = {"extra": "forbid"}


class LevelLimits(BaseModel):
    """
    Level-gated limits, stored as two 3NF tables.

    Barn / silo capacity is not level-gated (it is upgraded with supplies),
    so it lives in the player config instead.
    """

    field_grants: list[FieldGrant] = Field(default_factory=list)
    location_instances: list[LocationInstance] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def keys_are_unique(self) -> LevelLimits:
        levels = [g.level for g in self.field_grants]
        if len(levels) != len(set(levels)):
            raise ValueError("field_grants contains duplicate levels")
        keys = [(i.location_id, i.instance) for i in self.location_instances]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "location_instances contains duplicate (location_id, instance)"
            )
        return self

    def fields_at(self, level: int) -> int:
        """Total number of fields available at *level*."""
        return sum(g.count for g in self.field_grants if g.level <= level)

    def instances_at(self, location_id: str, level: int) -> int:
        """Number of copies of *location_id* available at *level*."""
        return sum(
            1
            for i in self.location_instances
            if i.location_id == location_id and i.unlock_level <= level
        )

    def filter_by_max_level(self, max_level: int) -> LevelLimits:
        return LevelLimits(
            field_grants=[g for g in self.field_grants if g.level <= max_level],
            location_instances=[
                i for i in self.location_instances if i.unlock_level <= max_level
            ],
        )
