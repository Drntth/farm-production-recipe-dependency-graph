"""The site's UI strings: web/content/<lang>.json share every key and placeholder."""

import json
import re
from itertools import combinations
from pathlib import Path

from src.planner.capacity import FEEDER_BUSHES
from src.planner.schedule import ACTIONS, collect_what

CONTENT = Path(__file__).resolve().parent.parent / "web" / "content"
LANGS = ("en", "hu")
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _flatten(data: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            out |= _flatten(value, f"{path}.")
        else:
            out[path] = value
    return out


def _load(lang: str) -> dict[str, str]:
    return _flatten(json.loads((CONTENT / f"{lang}.json").read_text(encoding="utf-8")))


def test_languages_have_the_same_keys():
    en = _load("en")
    for lang in LANGS[1:]:
        other = _load(lang)
        assert sorted(other.keys() - en.keys()) == [], f"{lang}: keys missing from en"
        assert sorted(en.keys() - other.keys()) == [], f"{lang}: keys missing"


def test_translations_keep_the_placeholders():
    en = _load("en")
    for lang in LANGS[1:]:
        other = _load(lang)
        for key, text in en.items():
            assert set(PLACEHOLDER.findall(other[key])) == set(
                PLACEHOLDER.findall(text)
            ), f"{lang}: {key}"


def test_no_empty_strings():
    for lang in LANGS:
        assert [
            key for key, text in _load(lang).items() if not str(text).strip()
        ] == [], lang


def test_fan_content_policy_wording_is_identical():
    # Supercell's required notice is not translated
    texts = {_load(lang)["footer.fanPolicy"] for lang in LANGS}
    assert len(texts) == 1


def test_every_schedule_action_and_what_is_translated():
    # the level page looks the planner's English wording up; a missing key
    # would silently show English on the Hungarian page
    feeder = list(FEEDER_BUSHES)
    whats = {
        collect_what(list(subset))
        for n in range(len(feeder) + 1)
        for subset in combinations(feeder, n)
    }
    for lang in LANGS:
        data = json.loads((CONTENT / f"{lang}.json").read_text(encoding="utf-8"))
        assert set(ACTIONS) <= data["actions"].keys(), lang
        assert sorted(whats - data["whats"].keys()) == [], lang
