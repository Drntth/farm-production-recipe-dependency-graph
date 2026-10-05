"""Recipe entity - transformations that happen inside production locations."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RecipeInput(BaseModel):
    """A single input resource required by a recipe."""

    resource_id: str = Field(..., description="Id of the required resource")
    amount: int = Field(..., ge=1, description="Quantity needed")

    @field_validator("resource_id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError(
                f"resource_id must be lower-case snake_case alphanumeric, got: {v!r}"
            )
        return v

    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class RecipeOutput(BaseModel):
    """The output resource produced by a recipe."""

    resource_id: str = Field(..., description="Id of the produced resource")
    amount: int = Field(..., ge=1, description="Quantity produced")

    @field_validator("resource_id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError(
                f"resource_id must be lower-case snake_case alphanumeric, got: {v!r}"
            )
        return v

    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class Recipe(BaseModel):
    """
    A production transformation that happens inside a location.

    Recipes may have zero or more inputs. Some wiki-defined recipes,
    such as lure crafting entries, represent production actions without
    explicit ingredient requirements.
    """

    id: str = Field(..., description="Snake_case English identifier, e.g. 'cream'")
    name: str = Field(..., description="Human-readable name, e.g. 'Cream'")
    location_id: str = Field(..., description="Location where the recipe is crafted")
    unlock_level: int = Field(..., ge=1, description="Player level required to unlock")
    inputs: list[RecipeInput] = Field(
        default_factory=list,
        description="Required inputs (may be empty for recipes without ingredients)",
    )
    output: RecipeOutput = Field(..., description="Produced output")

    production_time_seconds: int | None = Field(None, ge=0)
    production_time_3star_seconds: int | None = Field(
        None, ge=0, description="Production time with full 3-star mastery"
    )
    description: str | None = None

    @field_validator("id", "location_id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError(
                f"id / location_id must be lower-case snake_case alphanumeric, got: {v!r}"
            )
        return v

    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
    }
