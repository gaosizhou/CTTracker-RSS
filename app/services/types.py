from dataclasses import dataclass
from datetime import datetime


@dataclass
class FetchedPaper:
    title: str
    authors: list[str]
    abstract: str = ""
    year: int | None = None
    published_at: datetime | None = None
    url: str | None = None
    pdf_url: str | None = None
