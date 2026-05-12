import os
from collections.abc import Generator
from sqlalchemy import inspect, text

from sqlmodel import Session, SQLModel, create_engine, select


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///rss_papers.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    migrate_sqlite()
    migrate_legacy_content()


def migrate_sqlite() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if not inspector.has_table("paper"):
        return
    paper_columns = {column["name"] for column in inspector.get_columns("paper")}
    state_columns = {column["name"] for column in inspector.get_columns("paperstate")}
    source_columns = {column["name"] for column in inspector.get_columns("source")} if inspector.has_table("source") else set()
    with engine.begin() as connection:
        if "chinese_title" not in paper_columns:
            connection.execute(text("ALTER TABLE paper ADD COLUMN chinese_title VARCHAR NOT NULL DEFAULT ''"))
        if "in_watchlist" not in state_columns:
            connection.execute(text("ALTER TABLE paperstate ADD COLUMN in_watchlist BOOLEAN NOT NULL DEFAULT 0"))
        if "watch_source" not in state_columns:
            connection.execute(text("ALTER TABLE paperstate ADD COLUMN watch_source VARCHAR NOT NULL DEFAULT ''"))
        if "watch_tags" not in state_columns:
            connection.execute(text("ALTER TABLE paperstate ADD COLUMN watch_tags VARCHAR NOT NULL DEFAULT ''"))
        if "creator_id" not in source_columns:
            connection.execute(text("ALTER TABLE source ADD COLUMN creator_id INTEGER"))


def migrate_legacy_content() -> None:
    from app.models import (
        ContentCreatorLink,
        ContentItem,
        ContentState,
        ContentTagLink,
        ContentType,
        Creator,
        CreatorKind,
        Paper,
        PaperResearcherLink,
        PaperState,
        PaperTagLink,
        Researcher,
        Source,
        SourceType,
    )

    with Session(engine) as session:
        if session.exec(select(ContentItem)).first():
            return

        creator_map: dict[int, int] = {}
        for researcher in session.exec(select(Researcher)).all():
            creator = Creator(
                name=researcher.name,
                kind=CreatorKind.SCHOLAR,
                profile_url=researcher.google_profile_url,
                platform="google_scholar",
                aliases=researcher.aliases,
                keywords=researcher.keywords,
                notes=researcher.notes,
                legacy_researcher_id=researcher.id,
                created_at=researcher.created_at,
            )
            session.add(creator)
            session.flush()
            creator_map[researcher.id] = creator.id

        content_map: dict[int, int] = {}
        for paper in session.exec(select(Paper)).all():
            item = ContentItem(
                content_type=ContentType.PAPER,
                title=paper.title,
                chinese_title=paper.chinese_title,
                normalized_title=paper.normalized_title,
                creator_text=paper.authors,
                description=paper.abstract,
                year=paper.year,
                published_at=paper.published_at,
                url=paper.url,
                pdf_url=paper.pdf_url,
                platform="google_scholar" if paper.source_type == SourceType.GOOGLE_SCHOLAR_PROFILE else paper.source_type.value,
                source_type=paper.source_type,
                source_url=paper.source_url,
                legacy_paper_id=paper.id,
                created_at=paper.created_at,
                updated_at=paper.updated_at,
            )
            session.add(item)
            session.flush()
            content_map[paper.id] = item.id

            old_state = session.exec(select(PaperState).where(PaperState.paper_id == paper.id)).first()
            state = ContentState(
                content_id=item.id,
                favorite=old_state.favorite if old_state else False,
                in_focus=old_state.in_watchlist if old_state else False,
                focus_source=old_state.watch_source if old_state else "",
                notes=old_state.notes if old_state else "",
                updated_at=old_state.updated_at if old_state else paper.updated_at,
            )
            if old_state:
                state.status = old_state.status
            session.add(state)

        for link in session.exec(select(PaperResearcherLink)).all():
            content_id = content_map.get(link.paper_id)
            creator_id = creator_map.get(link.researcher_id)
            if content_id and creator_id:
                session.add(ContentCreatorLink(content_id=content_id, creator_id=creator_id, match_reason=link.match_reason))

        for link in session.exec(select(PaperTagLink)).all():
            content_id = content_map.get(link.paper_id)
            if content_id:
                session.add(ContentTagLink(content_id=content_id, tag_id=link.tag_id))

        for source in session.exec(select(Source)).all():
            if source.researcher_id and source.researcher_id in creator_map:
                source.creator_id = creator_map[source.researcher_id]
                session.add(source)

        session.commit()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
