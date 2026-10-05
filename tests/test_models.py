import pytest
from pydantic import ValidationError

from src.models import Area, Location


def test_location_defaults_to_farm() -> None:
    loc = Location(id="dairy", name="Dairy", type="production", unlock_level=6)
    assert loc.area == Area.FARM
    assert loc.movable is True
    assert loc.rotatable is False
    assert loc.footprint_width is None


def test_footprint_requires_both_sides() -> None:
    with pytest.raises(ValidationError):
        Location(
            id="dairy", name="Dairy", type="production", unlock_level=6, footprint_width=4
        )


def test_footprint_and_area() -> None:
    loc = Location(
        id="lobster_pool",
        name="Lobster Pool",
        type="animal",
        unlock_level=44,
        area="fishing_lake",
        footprint_width=3,
        footprint_height=3,
    )
    assert loc.area == Area.FISHING_LAKE
    assert (loc.footprint_width, loc.footprint_height) == (3, 3)
