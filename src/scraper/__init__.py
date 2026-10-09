"""Hay Day Fandom Wiki scraper for production data."""

__all__ = ["main"]


def __getattr__(name: str):
    if name == "main":
        from .cli import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
