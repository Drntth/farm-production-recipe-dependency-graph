"""Mastery bonuses - production speed-ups a building earns with mastery stars."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class MasteryBonus(BaseModel):
    """
    Production time reduction of a building at one mastery star level.

    One row per (location, stars). The percentage is the total reduction at
    that star level, not an increment: the feed mill has 5 / 10 / 15 %, most
    machines only 15 % at three stars (wiki: Masteries). Coin and XP bonuses
    are not stored.
    """

    location_id: str
    stars: int = Field(..., ge=1, le=3)
    time_reduction_percent: int = Field(..., ge=1, le=99)

    @field_validator("location_id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError(
                f"location_id must be lower-case snake_case alphanumeric, got: {v!r}"
            )
        return v

    model_config = {"extra": "forbid"}
