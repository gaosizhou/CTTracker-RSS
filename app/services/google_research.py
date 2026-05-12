import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from app.services.normalization import extract_year
from app.services.types import FetchedPaper


DETAIL_HINTS = ("/pubs/", "/publication", "/papers/")
SKIP_TITLES = {
    "view details",
    "preview",
    "preview abstract",
    "learn more",
    "research",
    "people",
    "publications",
}


def fetch_google_research_profile(url: str) -> tuple[str, list[FetchedPaper]]:
    if not is_google_research_profile_url(url):
        raise ValueError("Only Google Research author pages are supported here, for example https://research.google/people/...")
    response = httpx.get(url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    return parse_google_research_profile(response.text, str(response.url))


def is_google_research_profile_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return parsed.scheme in {"http", "https"} and host == "research.google" and parsed.path.startswith("/people/")


def parse_google_research_profile(html: str, base_url: str) -> tuple[str, list[FetchedPaper]]:
    soup = BeautifulSoup(html, "html.parser")
    researcher_name = _profile_name(soup)
    papers: list[FetchedPaper] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a"):
        if not isinstance(anchor, Tag):
            continue
        title = _clean(anchor.get_text(" ", strip=True))
        href = anchor.get("href") or ""
        if not _looks_like_publication_link(title, href):
            continue
        card = _publication_container(anchor)
        paper = _paper_from_card(card, anchor, base_url)
        key = (paper.url or paper.title).lower()
        if paper.title and key not in seen:
            seen.add(key)
            papers.append(paper)

    return researcher_name, papers


def _profile_name(soup: BeautifulSoup) -> str:
    heading = soup.find("h1")
    if heading:
        name = _clean(heading.get_text(" ", strip=True))
        if name:
            return name
    meta = soup.find("meta", property="og:title") or soup.find("title")
    if meta:
        value = meta.get("content") if isinstance(meta, Tag) and meta.name == "meta" else meta.get_text(" ", strip=True)
        value = re.sub(r"\s*-\s*Google Research\s*$", "", value or "")
        if value:
            return _clean(value)
    return "Unknown Researcher"


def _looks_like_publication_link(title: str, href: str) -> bool:
    lowered = title.lower()
    if len(title) < 8 or lowered in SKIP_TITLES:
        return False
    if any(hint in href for hint in DETAIL_HINTS):
        return True
    parsed = urlparse(href)
    return "research.google" in parsed.netloc and "/pubs/" in parsed.path


def _publication_container(anchor: Tag) -> Tag:
    best = anchor
    for parent in anchor.parents:
        if not isinstance(parent, Tag) or parent.name in {"body", "html"}:
            break
        text = parent.get_text("\n", strip=True)
        class_text = " ".join(parent.get("class", []))
        if re.search(r"\b(19|20)\d{2}\b", text) and (
            "publication" in class_text.lower()
            or "card" in class_text.lower()
            or parent.name in {"article", "li"}
            or len(text) < 5000
        ):
            best = parent
            break
        if len(text) < 2500:
            best = parent
    return best


def _paper_from_card(card: Tag, title_anchor: Tag, base_url: str) -> FetchedPaper:
    title = _clean(title_anchor.get_text(" ", strip=True))
    lines = [_clean(line) for line in card.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line and line.lower() not in SKIP_TITLES]
    title_index = _first_index(lines, title)
    year_line_index = _first_year_line(lines, start=title_index + 1)
    authors = _authors_between(lines, title_index + 1, year_line_index)
    year_source = lines[year_line_index] if year_line_index is not None else card.get_text(" ", strip=True)
    abstract = _extract_abstract(card.get_text(" ", strip=True))
    paper_url = urljoin(base_url, title_anchor.get("href") or "")
    pdf_url = _find_pdf_url(card, base_url)

    return FetchedPaper(
        title=title,
        authors=authors,
        abstract=abstract,
        year=extract_year(year_source),
        url=paper_url,
        pdf_url=pdf_url,
    )


def _authors_between(lines: list[str], start: int, end: int | None) -> list[str]:
    if start < 0:
        start = 0
    if end is None:
        end = min(len(lines), start + 30)
    authors: list[str] = []
    for line in lines[start:end]:
        if line.lower() in SKIP_TITLES or extract_year(line):
            continue
        if len(line) > 80:
            continue
        authors.append(line)
    return authors


def _extract_abstract(text: str) -> str:
    match = re.search(r"Preview\s+abstract\s+(.*?)(?:\s+View details\s*$|\s+View details\s+)", text, re.I | re.S)
    if match:
        return _clean(match.group(1))
    match = re.search(r"Abstract\s+(.*)", text, re.I | re.S)
    return _clean(match.group(1)) if match else ""


def _find_pdf_url(card: Tag, base_url: str) -> str | None:
    for anchor in card.find_all("a"):
        href = anchor.get("href") or ""
        label = anchor.get_text(" ", strip=True).lower()
        if ".pdf" in href.lower() or label == "pdf":
            return urljoin(base_url, href)
    return None


def _first_index(lines: list[str], value: str) -> int:
    value = _clean(value)
    for index, line in enumerate(lines):
        if line == value:
            return index
    return -1


def _first_year_line(lines: list[str], start: int = 0) -> int | None:
    for index in range(max(0, start), len(lines)):
        if extract_year(lines[index]):
            return index
    return None


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
