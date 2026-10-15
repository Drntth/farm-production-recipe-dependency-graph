"""Client for fetching Hay Day Fandom Wiki pages via MediaWiki API.

Uses the parse API to avoid Cloudflare challenges on direct page requests.
"""

from __future__ import annotations

import time

import requests
from bs4 import BeautifulSoup


class WikiClient:
    """Simple client for Hay Day Fandom Wiki."""

    BASE_URL = "https://hayday.fandom.com"
    API_URL = f"{BASE_URL}/api.php"

    def __init__(self, timeout: int = 30, delay: float = 0.5):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "FarmProductionGraphScraper/0.1 "
                    "(educational/fan project; +https://github.com/Drntth/farm-production-recipe-dependency-graph)"
                )
            }
        )
        self.timeout = timeout
        self.delay = delay
        self._last_request = 0.0
        self.fetched_pages: set[str] = set()

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.time()

    def get_page_html(self, page_name: str) -> str:
        """Fetch rendered HTML of a wiki page via the MediaWiki parse API."""
        self._throttle()
        params = {
            "action": "parse",
            "page": page_name,
            "prop": "text",
            "format": "json",
            "disabletoc": "1",
        }
        response = self.session.get(self.API_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"Wiki API error for '{page_name}': {data['error']}")
        self.fetched_pages.add(page_name)
        return data["parse"]["text"]["*"]

    def _query(self, params: dict) -> dict:
        self._throttle()
        response = self.session.get(
            self.API_URL,
            params={"action": "query", "format": "json", **params},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("query", {})

    def get_category_members(self, category: str) -> list[str]:
        """Page titles in ``Category:<category>`` (subcategories excluded)."""
        self.fetched_pages.add(f"Category:{category}")
        query = self._query(
            {
                "list": "categorymembers",
                "cmtitle": f"Category:{category}",
                "cmtype": "page",
                "cmlimit": "500",
            }
        )
        return [m["title"] for m in query.get("categorymembers", [])]

    def list_pages(self, prefix: str) -> list[str]:
        """Titles of all pages starting with *prefix* (e.g. 'Experience_Levels/')."""
        query = self._query({"list": "allpages", "apprefix": prefix, "aplimit": "500"})
        return [p["title"] for p in query.get("allpages", [])]

    def get_revision_timestamps(self, page_names: set[str]) -> dict[str, str | None]:
        """
        Last-revision timestamp (ISO 8601) of each page, None if missing.

        Redirects are followed, like ``get_wikitext``: a renamed page reports
        the revision of the page it points to, under the name asked for.
        """
        result: dict[str, str | None] = {}
        names = sorted(page_names)
        for i in range(0, len(names), 50):  # MediaWiki limit per query
            batch = names[i : i + 50]
            query = self._query(
                {
                    "titles": "|".join(batch),
                    "prop": "revisions",
                    "rvprop": "timestamp",
                    "redirects": "1",
                }
            )
            result.update(_timestamps_by_name(batch, query))
        return result

    def get_wikitext(self, page_name: str) -> str:
        """Raw wikitext of a page (infobox fields like ``|level = 39``)."""
        self._throttle()
        params = {
            "action": "parse",
            "page": page_name,
            "prop": "wikitext",
            "format": "json",
            "redirects": "1",
        }
        response = self.session.get(self.API_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"Wiki API error for '{page_name}': {data['error']}")
        self.fetched_pages.add(page_name)
        return data["parse"]["wikitext"]["*"]

    def get_page(self, page_name: str) -> BeautifulSoup:
        """Return a BeautifulSoup of the rendered page content."""
        html = self.get_page_html(page_name)
        return BeautifulSoup(html, "html.parser")

    def get_goods_list(self) -> BeautifulSoup:
        return self.get_page("Goods_List")

    def get_production_locations_list(self) -> BeautifulSoup:
        return self.get_page("Production_Buildings_List")

    def get_page_optional(self, page_name: str) -> BeautifulSoup | None:
        """Fetch a page; return None on 404 / missing page."""
        try:
            return self.get_page(page_name)
        except (requests.RequestException, RuntimeError, ValueError):
            return None


def _timestamps_by_name(names: list[str], query: dict) -> dict[str, str | None]:
    """
    Map a revisions query answer back to the names asked for.

    The API answers with normalised titles ("Goods List") and, with
    ``redirects``, with the redirect targets; both steps are followed.
    """
    normalized = {n["from"]: n["to"] for n in query.get("normalized", [])}
    redirects = {r["from"]: r["to"] for r in query.get("redirects", [])}
    stamps: dict[str, str | None] = {}
    for page in query.get("pages", {}).values():
        revisions = page.get("revisions")
        stamps[page["title"]] = revisions[0]["timestamp"] if revisions else None
    result: dict[str, str | None] = {}
    for name in names:
        title = normalized.get(name, name)
        title = redirects.get(title, title)
        result[name] = stamps.get(title)
    return result
