from datetime import datetime

from app.services.normalization import extract_year, parse_datetime
from app.services.types import FetchedPaper


def fetch_rss(url: str) -> list[FetchedPaper]:
    import feedparser

    parsed = feedparser.parse(url)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise ValueError(f"Could not parse RSS/Atom feed: {url}")
    return parse_rss_entries(parsed.entries)


def parse_rss_entries(entries: list[object]) -> list[FetchedPaper]:
    papers: list[FetchedPaper] = []
    for entry in entries:
        data = _entry_dict(entry)
        title = data.get("title", "").strip()
        if not title:
            continue
        authors = _authors(data)
        abstract = data.get("summary", "") or data.get("description", "")
        published_at = _published_at(data)
        year = extract_year(data.get("published") or data.get("updated") or title) or (
            published_at.year if published_at else None
        )
        papers.append(
            FetchedPaper(
                title=title,
                authors=authors,
                abstract=abstract,
                year=year,
                published_at=published_at,
                url=data.get("link"),
                pdf_url=_pdf_url(data),
            )
        )
    return papers


def _entry_dict(entry: object) -> dict:
    if isinstance(entry, dict):
        return entry
    return dict(entry)


def _authors(data: dict) -> list[str]:
    if "authors" in data and data["authors"]:
        return [item.get("name", "").strip() for item in data["authors"] if item.get("name")]
    if data.get("author"):
        return [part.strip() for part in data["author"].replace(" and ", ",").split(",") if part.strip()]
    return []


def _published_at(data: dict) -> datetime | None:
    for key in ("published", "updated", "created"):
        parsed = parse_datetime(data.get(key))
        if parsed:
            return parsed
    return None


def _pdf_url(data: dict) -> str | None:
    for link in data.get("links", []) or []:
        href = link.get("href")
        if not href:
            continue
        if link.get("type") == "application/pdf" or href.lower().endswith(".pdf"):
            return href
    return None
