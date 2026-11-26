"""Browser glue and build-time files (src/api/browser.py, src/recommend/web_files.py)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from src.api import production_plan
from src.api.browser import level_defaults, plan_farm_profile
from src.config import PlayerConfig
from src.farm_profile import FarmProfile, farm_profile_json
from src.loaders.bundle import build_bundle
from src.loaders.json_loader import dataset_from_bundle
from src.planner.examples import example_profile
from src.recommend.web_files import build_defaults, core_files
from src.recommend.web_files import main as web_files_main

DATA_DIR = Path("data")
pytestmark = pytest.mark.skipif(
    not (DATA_DIR / "locations.json").exists(), reason="data/locations.json not found"
)


@pytest.fixture(scope="module")
def bundle() -> dict:
    return build_bundle(DATA_DIR)


@pytest.fixture(scope="module")
def profile_json(bundle: dict) -> dict:
    player = PlayerConfig.model_validate(
        example_profile(dataset_from_bundle(bundle), 20)
    )
    return farm_profile_json(FarmProfile(player=player))


def test_plan_matches_core_api(bundle: dict, profile_json: dict):
    out = plan_farm_profile(bundle, profile_json)
    direct = production_plan(bundle, player=profile_json["player"])
    assert out["result"] == direct["result"]
    assert set(out["files"]) == {"capacity.json", "schedule.json", "schedule.md"}
    assert isinstance(out["warnings"], list)


def test_plan_collects_warnings(bundle: dict, profile_json: dict):
    out = plan_farm_profile(bundle, profile_json)
    assert any("barn_capacity" in w or "storage" in w for w in out["warnings"])
    assert all(w.startswith("src.") for w in out["warnings"])


def test_plan_rejects_invalid_profile(bundle: dict):
    with pytest.raises(ValueError):
        plan_farm_profile(bundle, {"player": {"level": 0}})


def test_level_defaults(bundle: dict):
    out = level_defaults(bundle, 12)
    assert out["level"] == 12
    assert out["profile"]["level"] == 12
    assert set(out["locations"]) == set(out["profile"]["locations"])
    first = next(iter(out["locations"].values()))
    assert set(first) == {"name", "type"}
    json.dumps(out)


def test_defaults_file_covers_every_level(bundle: dict):
    defaults = build_defaults(bundle, range(1, 4))
    assert list(defaults["levels"]) == ["1", "2", "3"]
    assert set(defaults["locations"]) >= set(defaults["levels"]["3"]["locations"])


def test_defaults_carry_the_form_limits(bundle: dict):
    # the bounds of the farm profile form: copies and fields per level, shelter
    # capacity and slots per location, all from the data (not from the page)
    data = dataset_from_bundle(bundle)
    defaults = build_defaults(bundle, range(1, 4))
    assert defaults["schema_version"] == 2
    limits = defaults["limits"]
    assert list(limits) == ["1", "2", "3"]
    assert limits["3"]["fields"] == data.level_limits.fields_at(3)
    assert limits["3"]["copies"]["chicken_coop"] == data.level_limits.instances_at(
        "chicken_coop", 3
    )
    assert limits["1"]["copies"]["chicken_coop"] == 1
    chicken = defaults["locations"]["chicken_coop"]
    assert chicken["animal_capacity"] == data.locations["chicken_coop"].animal_capacity
    # a machine with slots: the machine default of 9 (feed mill unlocks at level 2)
    assert defaults["locations"]["feed_mill"]["max_slots"] == 9
    assert "max_slots" not in defaults["locations"].get("field", {})


def test_core_files_exclude_scraper_and_tests():
    names = set(core_files())
    assert "src/api/browser.py" in names
    assert "src/farm_profile.py" in names
    assert not any(n.startswith(("src/scraper", "src/recommend")) for n in names)
    assert not any("__pycache__" in n or "tests" in n for n in names)


def test_web_files_run_from_the_zip(tmp_path: Path):
    out = tmp_path / "py"
    assert web_files_main(["--output-dir", str(out)]) == 0
    assert (out / "data_bundle.json").read_text(encoding="utf-8").startswith("{")
    defaults = json.loads((out / "defaults.json").read_text(encoding="utf-8"))
    meta = json.loads((DATA_DIR / "meta.json").read_text(encoding="utf-8"))
    assert list(defaults["levels"]) == [str(n) for n in range(1, meta["max_level"] + 1)]
    with zipfile.ZipFile(out / "core.zip") as z:
        assert not [n for n in z.namelist() if "__pycache__" in n]
    # the zip alone (no source tree) is enough to import the glue
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "import src.api.browser as b; print(b.__file__);"
        "bad = [m for m in sys.modules if m.startswith(('src.scraper', 'src.recommend'))];"
        "assert not bad, bad"
    )
    run = subprocess.run(
        [sys.executable, "-I", "-c", code, str(out / "core.zip")],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert "core.zip" in run.stdout


WEB = Path(__file__).resolve().parent.parent / "web"


def test_web_profile_plans_with_a_partial_login_window(bundle: dict):
    """The web form writes a new profile with only the changed planner keys."""
    profile = json.loads(
        (WEB / "src" / "profiles" / "fixture.farm-profile.json").read_text("utf-8")
    )
    profile["planner"] = {
        "schema_version": 2,
        "production": {"login_window": {"start": "08:00", "logins": 4}},
    }
    out = plan_farm_profile(bundle, profile)
    assert out["result"]["logins_per_day"] == 4
    assert out["result"]["login_times"][0] == "08:00"


def test_worker_calls_only_the_browser_glue():
    """The web app reaches the core only through src.api.browser."""
    worker = (WEB / "src" / "worker" / "planner.worker.ts").read_text("utf-8")
    imports = set(
        re.findall(r"^\s*(?:from|import)\s+(src[\w.]*)", worker, re.MULTILINE)
    )
    assert imports == {"src.api.browser"}


def test_pyodide_and_networkx_versions_agree():
    """Worker, smoke test, package.json and requirements.txt pin the same versions."""
    worker = (WEB / "src" / "worker" / "planner.worker.ts").read_text("utf-8")
    smoke = (WEB / "scripts" / "pyodide-smoke.mjs").read_text("utf-8")
    package = json.loads((WEB / "package.json").read_text("utf-8"))
    requirements = (WEB.parent / "requirements.txt").read_text("utf-8")
    pyodide = re.search(r'PYODIDE_VERSION = "([^"]+)"', worker)
    assert pyodide and pyodide[1] == package["devDependencies"]["pyodide"]
    networkx = re.search(r"^networkx==(\S+)", requirements, re.MULTILINE)
    assert networkx
    wheel = f"networkx-{networkx[1]}-py3-none-any.whl"
    assert wheel in worker
    assert wheel in smoke
