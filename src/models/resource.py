"""Resource entity - crops, animal products, processed goods, ores."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class ResourceType(str, Enum):
    """Allowed resource types as defined by the data model."""

    CROP = "crop"
    ANIMAL_PRODUCT = "animal_product"
    PROCESSED_MATERIAL = "processed_material"
    RAW_MATERIAL = "raw_material"
    ORE = "ore"


_RAW_TYPES = {ResourceType.CROP, ResourceType.ANIMAL_PRODUCT, ResourceType.ORE}


class Resource(BaseModel):
    """
    A good that can be produced, harvested or processed.

    All goods (including intermediate items such as Bread and final items
    such as cakes) are modelled as resources. Whether an item is intermediate
    or final is derived later from the dependency graph.
    """

    id: str = Field(..., description="Snake_case English identifier, e.g. 'milk'")
    name: str = Field(..., description="Human-readable name, e.g. 'Milk'")
    type: ResourceType = Field(..., description="Category of the resource")
    unlock_level: int = Field(..., ge=1, description="Player level required to unlock")

    source_location_id: str | None = Field(
        None,
        description="Location that produces this raw resource (required for crop, animal_product, ore)",
    )

    description: str | None = None
    max_in_barn: int | None = Field(None, ge=1)
    growth_time_seconds: int | None = Field(
        None,
        ge=0,
        description="Time from planting / feeding to harvest for raw resources; 0 = instant",
    )

    @field_validator("id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError(
                f"Resource id must be lower-case snake_case alphanumeric, got: {v!r}"
            )
        return v

    @model_validator(mode="after")
    def require_source_location_for_raw(self) -> Resource:
        if self.type in _RAW_TYPES and not self.source_location_id:
            raise ValueError(
                f"Resource '{self.id}' of type '{self.type.value}' "
                "must have a source_location_id"
            )
        return self

    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
    }
