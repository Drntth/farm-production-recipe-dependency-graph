import pytest
from pydantic import ValidationError

from src.models import LevelLimits


@pytest.fixture
def limits() -> LevelLimits:
    return LevelLimits.model_validate(
        {
            "field_grants": [
                {"level": 1, "count": 6},
                {"level": 3, "count": 3},
                {"level": 51, "count": 2},
            ],
            "location_instances": [
                {"location_id": "feed_mill", "instance": 1, "unlock_level": 2},
                {"location_id": "feed_mill", "instance": 2, "unlock_level": 12},
                {"location_id": "dairy", "instance": 1, "unlock_level": 6},
            ],
        }
    )


def test_fields_at(limits: LevelLimits) -> None:
    assert limits.fields_at(1) == 6
    assert limits.fields_at(2) == 6
    assert limits.fields_at(50) == 9
    assert limits.fields_at(56) == 11


def test_instances_at(limits: LevelLimits) -> None:
    assert limits.instances_at("feed_mill", 1) == 0
    assert limits.instances_at("feed_mill", 11) == 1
    assert limits.instances_at("feed_mill", 12) == 2
    assert limits.instances_at("bakery", 56) == 0


def test_filter_by_max_level(limits: LevelLimits) -> None:
    low = limits.filter_by_max_level(10)
    assert [g.level for g in low.field_grants] == [1, 3]
    assert {(i.location_id, i.instance) for i in low.location_instances} == {
        ("feed_mill", 1),
        ("dairy", 1),
    }


def test_duplicate_keys_rejected() -> None:
    with pytest.raises(ValidationError):
        LevelLimits.model_validate(
            {"field_grants": [{"level": 1, "count": 6}, {"level": 1, "count": 3}]}
        )
    with pytest.raises(ValidationError):
        LevelLimits.model_validate(
            {
                "location_instances": [
                    {"location_id": "dairy", "instance": 1, "unlock_level": 6},
                    {"location_id": "dairy", "instance": 1, "unlock_level": 7},
                ]
            }
        )
