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
            id="dairy",
            name="Dairy",
            type="production",
            unlock_level=6,
            footprint_width=4,
        )


def test_lifetime_yield_requires_harvests() -> None:
    with pytest.raises(ValidationError):
        Location(
            id="apple_tree",
            name="Apple Tree",
            type="tree",
            unlock_level=10,
            lifetime_yield=13,
        )
    tree = Location(
        id="apple_tree",
        name="Apple Tree",
        type="tree",
        unlock_level=10,
        lifetime_yield=13,
        lifetime_harvests=4,
    )
    assert tree.lifetime_harvests == 4


def test_mastery_bonus_range() -> None:
    from src.models import MasteryBonus

    assert MasteryBonus(location_id="feed_mill", stars=1, time_reduction_percent=5)
    with pytest.raises(ValidationError):
        MasteryBonus(location_id="feed_mill", stars=4, time_reduction_percent=5)


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
