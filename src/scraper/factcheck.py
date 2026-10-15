"""
Game fact checker: compare the game fact tables with the wiki.

Reads every ``| Fact | Value | Source | Checked |`` table of
``docs/game-facts/*.md``. For each row whose source names wiki pages
(``wiki:<Page>``, several separated by commas), it fetches each page once
through the MediaWiki API and reports:

- ``changed``: a source page was edited after the row's ``Checked`` date, so
  the value may be stale;
- ``value not found``: a number of the value (``9``, ``1,000``, ``4.5``) is
  in none of the source pages' wikitext (category pages hold no values). Values without numbers are only
  checked for page changes. The value check is a hint, not a proof: derived
  or rounded numbers need a look by hand;
- ``page error``: a source page could not be fetched (missing, network).

Rows with other sources (``in-game``, ``data/…``, player estimates) are
skipped. Writes ``output/fact_check.md`` and ``output/fact_check.json``;
``python -m src check-facts``. With ``--fail-on-findings`` the exit code is
``FINDINGS_EXIT`` when a row is ``changed`` or has a ``page error`` (the
``value not found`` hints never fail), for a scheduled check.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol

import requests

logger = logging.getLogger("src.scraper.factcheck")

FACT_DIR = Path("docs/game-facts")
FINDINGS_EXIT = 3
FAILING = ("changed", "page error")  # "value not found" is only a hint
HEADER = ("Fact", "Value", "Source", "Checked")
_WIKI = re.compile(r"wiki:([^,|…\s][^,|…]*)")
# what a wiki request may raise: HTTP / network errors, API errors, odd answers
_FETCH_ERRORS = (requests.RequestException, RuntimeError, KeyError, ValueError)
_DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


class WikiPages(Protocol):
    def get_revision_timestamps(
        self, page_names: set[str]
    ) -> dict[str, str | None]: ...

    def get_wikitext(self, page_name: str) -> str: ...


@dataclass(frozen=True)
class FactRow:
    file: str
    line: int
    fact: str
    value: str
    source: str
    checked: date | None

    @property
    def pages(self) -> list[str]:
        """Wiki page names of the source (``wiki:Barn, wiki:Silo``)."""
        source = re.sub(r"\s*\([^)]*\)", "", self.source)  # "(times)": a remark
        return [m.strip().replace(" ", "_") for m in _WIKI.findall(source)]


@dataclass
class Finding:
    row: FactRow
    status: str  # "ok", "changed", "value not found", "page error"
    details: list[str] = field(default_factory=list)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]


def parse_fact_tables(text: str, file: str) -> list[FactRow]:
    """Every row of the fact tables (header Fact / Value / Source / Checked)."""
    rows: list[FactRow] = []
    in_table = False
    for number, line in enumerate(text.splitlines(), 1):
        if not line.lstrip().startswith("|"):
            in_table = False
            continue
        cells = _cells(line)
        if tuple(cells) == HEADER:
            in_table = True
            continue
        if not in_table or all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        if len(cells) != len(HEADER):
            continue
        fact, value, source, checked = cells
        try:
            when = date.fromisoformat(checked)
        except ValueError:
            when = None
        rows.append(FactRow(file, number, fact, value, source, when))
    return rows


def load_fact_rows(directory: Path = FACT_DIR) -> list[FactRow]:
    rows: list[FactRow] = []
    for path in sorted(directory.glob("*.md")):
        rows += parse_fact_tables(path.read_text(encoding="utf-8"), path.name)
    return rows


def _numbers(text: str) -> set[str]:
    """
    Numbers of *text*, thousands separators removed (``1,000`` -> ``1000``).

    Dates (``2026-08``, ``2026-10-05``) are not values: they are left out.
    """
    text = _DATE.sub(" ", text)
    return {
        n.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", n) else n
        for n in _NUMBER.findall(text)
    }


def check_facts(rows: list[FactRow], client: WikiPages) -> list[Finding]:
    """One finding per row with a wiki source."""
    wiki_rows = [r for r in rows if r.pages]
    pages = {p for r in wiki_rows for p in r.pages}
    try:
        revisions = client.get_revision_timestamps(pages) if pages else {}
    except _FETCH_ERRORS as exc:  # network or API error: every page is unknown
        logger.warning("Revision timestamps not available: %s", exc)
        revisions = {}
    texts: dict[str, str | None] = {}
    errors: dict[str, str] = {}
    for page in sorted(pages):
        try:
            texts[page] = client.get_wikitext(page)
        except _FETCH_ERRORS as exc:  # a missing page must not stop the others
            texts[page] = None
            errors[page] = str(exc)

    findings: list[Finding] = []
    for row in wiki_rows:
        details: list[str] = []
        status = "ok"
        failed = [p for p in row.pages if texts.get(p) is None]
        if failed:
            status = "page error"
            details += [f"{p}: {errors.get(p, 'not fetched')}" for p in failed]
        for page in row.pages:
            stamp = revisions.get(page)
            if stamp and row.checked and date.fromisoformat(stamp[:10]) > row.checked:
                details.append(f"{page} edited {stamp[:10]} (checked {row.checked})")
                if status == "ok":
                    status = "changed"
        # a category page lists members, it holds no values
        content = [p for p in row.pages if not p.startswith("Category:")]
        found = set().union(*(_numbers(texts[p] or "") for p in content))
        missing = sorted(_numbers(row.value) - found)
        if missing and content and not failed:
            details.append(f"not in the page text: {', '.join(missing)}")
            status = "value not found"
        findings.append(Finding(row, status, details))
    return findings


def report_markdown(findings: list[Finding], skipped: int) -> str:
    flagged = [f for f in findings if f.status != "ok"]
    lines = [
        "# Game fact check",
        "",
        (
            f"{len(findings)} rows with a wiki source checked, {len(flagged)} to "
            f"look at; {skipped} rows with other sources skipped."
        ),
        "",
    ]
    if not flagged:
        return "\n".join(lines + ["Every checked row still matches the wiki."]) + "\n"
    lines += [
        "| File | Line | Fact | Status | Details |",
        "| --- | --- | --- | --- | --- |",
    ]
    for f in flagged:
        details = "; ".join(f.details).replace("|", "\\|")
        lines.append(
            f"| {f.row.file} | {f.row.line} | {f.row.fact} | {f.status} | {details} |"
        )
    return "\n".join(lines) + "\n"


def report_dict(findings: list[Finding], skipped: int) -> dict:
    return {
        "checked": len(findings),
        "skipped": skipped,
        "findings": [
            {
                **{k: v for k, v in asdict(f.row).items() if k != "checked"},
                "checked": f.row.checked.isoformat() if f.row.checked else None,
                "pages": f.row.pages,
                "status": f.status,
                "details": f.details,
            }
            for f in findings
        ],
    }


def main(argv: list[str] | None = None, client: WikiPages | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Check the game fact tables against the Hay Day wiki."
    )
    parser.add_argument("--facts-dir", type=Path, default=FACT_DIR)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help=f"Exit with {FINDINGS_EXIT} when a row is changed or its page fails "
        "(for scheduled checks)",
    )
    args = parser.parse_args(argv)
    rows = load_fact_rows(args.facts_dir)
    if not rows:
        logger.error("No fact tables found in %s", args.facts_dir)
        return 1
    if client is None:
        from .wiki_client import WikiClient

        client = WikiClient()
    findings = check_facts(rows, client)
    skipped = len(rows) - len(findings)
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "fact_check.md").write_text(
        report_markdown(findings, skipped), encoding="utf-8"
    )
    (out / "fact_check.json").write_text(
        json.dumps(report_dict(findings, skipped), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    flagged = sum(1 for f in findings if f.status != "ok")
    logger.info(
        "%d rows checked, %d to look at, %d skipped → %s",
        len(findings),
        flagged,
        skipped,
        out / "fact_check.md",
    )
    if args.fail_on_findings and any(f.status in FAILING for f in findings):
        return FINDINGS_EXIT
    return 0


if __name__ == "__main__":
    sys.exit(main())
