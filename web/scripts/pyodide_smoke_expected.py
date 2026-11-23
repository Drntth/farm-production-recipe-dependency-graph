"""
Native side of the Pyodide smoke test (``pyodide-smoke.mjs``).

Writes ``profile.json`` (a level-30 farm profile) and ``expected.json`` (the
glue result of native CPython, ``json.dumps`` of ``plan_farm_profile``) into
the directory given as the first argument.

Run from the repository root: ``python web/scripts/pyodide_smoke_expected.py DIR``.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.api.browser import plan_farm_profile
from src.config import PlayerConfig
from src.farm_profile import FarmProfile, farm_profile_json
from src.loaders.bundle import build_bundle
from src.loaders.json_loader import dataset_from_bundle
from src.planner.examples import example_profile

LEVEL = 30


def main(out: Path) -> None:
    bundle = build_bundle(ROOT / "data")
    player = PlayerConfig.model_validate(
        example_profile(dataset_from_bundle(bundle), LEVEL)
    )
    profile = farm_profile_json(FarmProfile(name="smoke", player=player))
    out.mkdir(parents=True, exist_ok=True)
    (out / "profile.json").write_text(json.dumps(profile), encoding="utf-8")
    expected = json.dumps(plan_farm_profile(bundle, profile))
    (out / "expected.json").write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
