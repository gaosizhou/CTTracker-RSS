import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
CHANNEL_ID_PATTERN = re.compile(r"UC[a-zA-Z0-9_-]{20,}")


def resolve_youtube_feed_url(url: str) -> str:
    clean_url = url.strip()
    if not clean_url:
        raise ValueError("YouTube URL is required.")
    parsed = urlparse(clean_url)
    host = parsed.netloc.lower()
    if host not in YOUTUBE_HOSTS:
        return clean_url
    if parsed.path == "/feeds/videos.xml":
        return clean_url
    if parsed.path.startswith("/channel/"):
        channel_id = parsed.path.split("/")[2]
        return youtube_feed_url(channel_id)
    channel_id = extract_channel_id_from_page(clean_url)
    if not channel_id:
        raise ValueError("Could not find a YouTube channel id from this page. Please paste the channel RSS URL instead.")
    return youtube_feed_url(channel_id)


def youtube_feed_url(channel_id: str) -> str:
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def extract_channel_id_from_page(url: str) -> str | None:
    with httpx.Client(
        follow_redirects=True,
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    ) as client:
        response = client.get(url)
        response.raise_for_status()
    return extract_channel_id(response.text)


def extract_channel_id(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", itemprop="channelId")
    if meta and meta.get("content"):
        return meta["content"].strip()
    for pattern in ('"channelId":"', '"externalId":"', '"browseId":"'):
        index = html.find(pattern)
        if index >= 0:
            start = index + len(pattern)
            end = html.find('"', start)
            if end > start:
                value = html[start:end]
                if CHANNEL_ID_PATTERN.fullmatch(value):
                    return value
    match = CHANNEL_ID_PATTERN.search(html)
    return match.group(0) if match else None
