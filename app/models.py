from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class SourceType(str, Enum):
    MANUAL = "manual"
    GOOGLE_SCHOLAR_PROFILE = "google_scholar_profile"
    GOOGLE_RESEARCH_PROFILE = "google_research_profile"
    RSS_ATOM = "rss_atom"
    YOUTUBE_RSS = "youtube_rss"


class ContentType(str, Enum):
    PAPER = "paper"
    VIDEO = "video"
    POST = "post"


class CreatorKind(str, Enum):
    SCHOLAR = "scholar"
    VIDEO_CREATOR = "video_creator"
    BLOGGER = "blogger"
    ACCOUNT = "account"


class PaperStatus(str, Enum):
    UNREAD = "unread"
    QUEUED = "queued"
    READ = "read"


class Researcher(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    google_profile_url: str | None = Field(default=None, index=True)
    aliases: str = ""
    keywords: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Source(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source_type: SourceType = Field(index=True)
    url: str = Field(index=True)
    researcher_id: int | None = Field(default=None, foreign_key="researcher.id", index=True)
    creator_id: int | None = Field(default=None, foreign_key="creator.id", index=True)
    last_refreshed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Creator(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    kind: CreatorKind = Field(default=CreatorKind.ACCOUNT, index=True)
    profile_url: str | None = Field(default=None, index=True)
    platform: str = Field(default="", index=True)
    aliases: str = ""
    keywords: str = ""
    notes: str = ""
    legacy_researcher_id: int | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContentItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content_type: ContentType = Field(index=True)
    title: str = Field(index=True)
    chinese_title: str = ""
    normalized_title: str = Field(index=True)
    creator_text: str = ""
    description: str = ""
    year: int | None = Field(default=None, index=True)
    published_at: datetime | None = Field(default=None, index=True)
    url: str | None = Field(default=None, index=True)
    pdf_url: str | None = None
    platform: str = Field(default="", index=True)
    source_type: SourceType = Field(index=True)
    source_url: str = Field(index=True)
    legacy_paper_id: int | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ContentState(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content_id: int = Field(foreign_key="contentitem.id", unique=True, index=True)
    status: PaperStatus = Field(default=PaperStatus.UNREAD, index=True)
    favorite: bool = Field(default=False, index=True)
    in_focus: bool = Field(default=False, index=True)
    focus_source: str = Field(default="", index=True)
    notes: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ContentCreatorLink(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content_id: int = Field(foreign_key="contentitem.id", index=True)
    creator_id: int = Field(foreign_key="creator.id", index=True)
    match_reason: str = ""


class Paper(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    chinese_title: str = ""
    normalized_title: str = Field(index=True)
    authors: str = ""
    abstract: str = ""
    year: int | None = Field(default=None, index=True)
    published_at: datetime | None = Field(default=None, index=True)
    url: str | None = Field(default=None, index=True)
    pdf_url: str | None = None
    source_type: SourceType = Field(index=True)
    source_url: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PaperState(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id", unique=True, index=True)
    status: PaperStatus = Field(default=PaperStatus.UNREAD, index=True)
    favorite: bool = Field(default=False, index=True)
    in_watchlist: bool = Field(default=False, index=True)
    watch_source: str = Field(default="", index=True)
    watch_tags: str = Field(default="", index=True)
    tags: str = Field(default="", index=True)
    notes: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PaperResearcherLink(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id", index=True)
    researcher_id: int = Field(foreign_key="researcher.id", index=True)
    match_reason: str = ""


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PaperTagLink(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id", index=True)
    tag_id: int = Field(foreign_key="tag.id", index=True)


class ContentTagLink(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    content_id: int = Field(foreign_key="contentitem.id", index=True)
    tag_id: int = Field(foreign_key="tag.id", index=True)
