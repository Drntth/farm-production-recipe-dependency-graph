"""Game fact checker, with a fake wiki (no network)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import requests

from src.scraper import factcheck as fc

TABLE = """# Barn

| Fact | Value | Source | Checked |
| --- | --- | --- | --- |
| Starting capacity | 50 | wiki:Barn | 2026-10-05 |
| Upgrade stages | 1,000 at the end | wiki:Barn, wiki:Silo | 2026-10-05 |
| Rolled out | since 2026-08 | wiki:Update (notes) | 2026-10-05 |
| Measured size | 3x3 | in-game | 2026-10-09 |
| Members | all storage buildings | wiki:Category:Storage | 2026-10-05 |
| Broken | 7 | wiki:Missing_Page | 2026-10-05 |

| Other | Table |
| --- | --- |
| not | a fact |
"""


class FakeWiki:
    def __init__(self) -> None:
        self.texts = {
            "Barn": "The barn starts at 50 and grows to 1000.",
            "Silo": "Same table as the barn.",
            "Update": "Workbench update.",
            "Category:Storage": "[[Barn]] [[Silo]] 12",
        }
        self.stamps = {
            "Barn": "2026-10-01T10:00:00Z",
            "Silo": "2026-10-08T10:00:00Z",  # edited after the check
            "Update": "2026-09-30T00:00:00Z",
            "Category:Storage": "2026-01-01T00:00:00Z",
        }
        self.fetched: list[str] = []

    def get_revision_timestamps(self, page_names: set[str]) -> dict[str, str | None]:
        return {p: self.stamps.get(p) for p in page_names}

    def get_wikitext(self, page_name: str) -> str:
        self.fetched.append(page_name)
        if page_name not in self.texts:
            raise RuntimeError(f"missing page {page_name}")
        return self.texts[page_name]


def test_parse_fact_tables() -> None:
    rows = fc.parse_fact_tables(TABLE, "storage.md")
    assert [r.fact for r in rows] == [
        "Starting capacity",
        "Upgrade stages",
        "Rolled out",
        "Measured size",
        "Members",
        "Broken",
    ]
    assert rows[0].line == 5 and rows[0].checked == date(2026, 10, 5)
    assert rows[1].pages == ["Barn", "Silo"]
    assert rows[2].pages == ["Update"]  # "(notes)" is a remark, not a page
    assert rows[3].pages == []


def test_numbers_skip_dates_and_join_thousands() -> None:
    assert fc._numbers("1,000 coins since 2026-08, 4.5 h, 2026-10-05") == {
        "1000",
        "4.5",
    }


def test_check_facts() -> None:
    wiki = FakeWiki()
    findings = fc.check_facts(fc.parse_fact_tables(TABLE, "storage.md"), wiki)
    status = {f.row.fact: f.status for f in findings}
    assert status == {
        "Starting capacity": "ok",
        "Upgrade stages": "changed",  # Silo edited after 2026-10-05
        "Rolled out": "ok",  # the date is no value
        "Members": "ok",  # category pages hold no values
        "Broken": "page error",
    }
    # every page is fetched once, even when several rows name it
    assert sorted(wiki.fetched) == sorted(set(wiki.fetched))
    broken = next(f for f in findings if f.row.fact == "Broken")
    assert "missing page" in broken.details[0]


def test_value_not_found() -> None:
    rows = fc.parse_fact_tables(TABLE.replace("| 50 |", "| 75 |"), "storage.md")
    findings = fc.check_facts(rows, FakeWiki())
    first = findings[0]
    assert first.status == "value not found"
    assert "75" in first.details[0]


def test_network_errors_do_not_stop_the_check() -> None:
    class Offline(FakeWiki):
        def get_revision_timestamps(self, page_names):
            raise requests.ConnectionError("offline")

        def get_wikitext(self, page_name):
            raise requests.ConnectionError("offline")

    findings = fc.check_facts(fc.parse_fact_tables(TABLE, "x.md"), Offline())
    assert {f.status for f in findings} == {"page error"}


def test_main_writes_reports(tmp_path: Path) -> None:
    facts = tmp_path / "facts"
    facts.mkdir()
    (facts / "storage.md").write_text(TABLE, encoding="utf-8")
    out = tmp_path / "out"
    args = ["--facts-dir", str(facts), "--output-dir", str(out)]
    assert fc.main(args, client=FakeWiki()) == 0
    data = json.loads((out / "fact_check.json").read_text())
    assert data["checked"] == 5 and data["skipped"] == 1
    md = (out / "fact_check.md").read_text()
    assert "| storage.md | 6 | Upgrade stages | changed |" in md
    # changed rows fail the check on request; hints alone do not
    strict = [*args, "--fail-on-findings"]
    assert fc.main(strict, client=FakeWiki()) == fc.FINDINGS_EXIT
    hint_only = tmp_path / "hints"
    hint_only.mkdir()
    (hint_only / "a.md").write_text(
        "| Fact | Value | Source | Checked |\n| --- | --- | --- | --- |\n"
        "| Capacity | 75 | wiki:Barn | 2026-10-05 |\n",
        encoding="utf-8",
    )
    hint_args = ["--facts-dir", str(hint_only), "--output-dir", str(out)]
    assert fc.main([*hint_args, "--fail-on-findings"], client=FakeWiki()) == 0
    empty = tmp_path / "empty"
    empty.mkdir()
    assert fc.main(["--facts-dir", str(empty)], client=FakeWiki()) == 1


def test_committed_fact_tables_parse() -> None:
    rows = fc.load_fact_rows()
    assert rows and all(r.checked is not None for r in rows)
    assert sum(1 for r in rows if r.pages) > len(rows) / 2
