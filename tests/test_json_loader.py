from pathlib import Path

from src.loaders.json_loader import load_data


def test_load_data():
    dataset = load_data(Path("data"))

    assert len(dataset.locations) > 0
    assert len(dataset.resources) > 0
    assert len(dataset.recipes) > 0
