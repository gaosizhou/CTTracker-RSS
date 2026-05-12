import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from app.services.normalization import extract_year
from app.services.types import FetchedPaper


SCHOLAR_HOSTS = {"scholar.google.com", "scholar.google.com.hk"}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def fetch_google_scholar_profile(url: str) -> tuple[str, list[FetchedPaper]]:
    if not is_google_scholar_profile_url(url):
        raise ValueError("Please use a Google Scholar citations URL, for example https://scholar.google.com/citations?user=...")

    response = httpx.get(
        normalize_scholar_url(url),
        follow_redirects=True,
        timeout=30,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    if response.status_code == 403:
        raise ValueError("Google Scholar returned 403. It often blocks automated access; try again later or open the page in your browser first.")
    response.raise_for_status()
    return parse_google_scholar_profile(response.text, str(response.url))


def parse_google_scholar_profile(html: str, base_url: str) -> tuple[str, list[FetchedPaper]]:
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one("form#captcha-form") or "unusual traffic" in soup.get_text(" ", strip=True).lower():
        raise ValueError("Google Scholar showed a captcha or unusual-traffic page.")

    name_node = soup.select_one("#gsc_prf_in")
    name = _clean(name_node.get_text(" ", strip=True)) if name_node else _name_from_title(soup)
    papers = []
    seen = set()
    for row in soup.select("tr.gsc_a_tr"):
        title_node = row.select_one("a.gsc_a_at")
        if not title_node:
            continue
        title = _clean(title_node.get_text(" ", strip=True))
        detail_url = urljoin(base_url, title_node.get("href") or "")
        gray = [_clean(node.get_text(" ", strip=True)) for node in row.select(".gs_gray")]
        year_text = _clean(row.select_one(".gsc_a_y span").get_text(" ", strip=True)) if row.select_one(".gsc_a_y span") else ""
        paper = FetchedPaper(
            title=title,
            authors=_split_authors(gray[0] if gray else ""),
            abstract=gray[1] if len(gray) > 1 else "",
            year=extract_year(year_text),
            url=detail_url,
        )
        key = (paper.url or paper.title).lower()
        if paper.title and key not in seen:
            seen.add(key)
            papers.append(paper)
    return name, papers


def is_google_scholar_profile_url(url: str) -> bool:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() in SCHOLAR_HOSTS and parsed.path == "/citations" and bool(query.get("user"))


def normalize_scholar_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    normalized = {
        "hl": query.get("hl", ["en"])[0],
        "user": query["user"][0],
        "view_op": "list_works",
        "sortby": "pubdate",
        "pagesize": "100",
    }
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(normalized), ""))


def _split_authors(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r",|\band\b", value) if part.strip()]


def _name_from_title(soup: BeautifulSoup) -> str:
    title = soup.find("title")
    if not title:
        return "Unknown Scholar"
    return re.sub(r"\s*-\s*Google Scholar\s*$", "", title.get_text(" ", strip=True)).strip() or "Unknown Scholar"


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
