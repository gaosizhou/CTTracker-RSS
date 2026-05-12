import re
import unicodedata
from datetime import datetime


YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title or "")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[,;\n，；]+", value)
    return [part.strip() for part in parts if part.strip()]


def extract_year(value: str | None) -> int | None:
    if not value:
        return None
    match = YEAR_RE.search(value)
    return int(match.group(0)) if match else None


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
        return parsed.replace(tzinfo=None)
    except ValueError:
        return None
