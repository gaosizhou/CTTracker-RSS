from datetime import datetime

from sqlmodel import Session, select

from app.models import Paper, PaperResearcherLink, PaperState, Researcher, Source, SourceType
from app.services.google_research import fetch_google_research_profile
from app.services.google_scholar import fetch_google_scholar_profile
from app.services.matching import match_researchers
from app.services.normalization import normalize_title
from app.services.rss import fetch_rss
from app.services.types import FetchedPaper


def refresh_source(session: Session, source: Source) -> int:
    if source.source_type == SourceType.GOOGLE_SCHOLAR_PROFILE:
        profile_name, fetched = fetch_google_scholar_profile(source.url)
        if source.researcher_id:
            researcher = session.get(Researcher, source.researcher_id)
            if researcher and (not researcher.name or researcher.name == "Unknown Scholar"):
                researcher.name = profile_name
                session.add(researcher)
    elif source.source_type == SourceType.GOOGLE_RESEARCH_PROFILE:
        profile_name, fetched = fetch_google_research_profile(source.url)
        if source.researcher_id:
            researcher = session.get(Researcher, source.researcher_id)
            if researcher and (not researcher.name or researcher.name == "Unknown Researcher"):
                researcher.name = profile_name
                session.add(researcher)
    elif source.source_type == SourceType.RSS_ATOM:
        fetched = fetch_rss(source.url)
    else:
        fetched = []

    researchers = list(session.exec(select(Researcher)).all())
    changed = 0
    for item in fetched:
        paper = upsert_paper(session, item, source)
        ensure_state(session, paper)
        ensure_matches(session, paper, item, researchers, source)
        changed += 1
    source.last_refreshed_at = datetime.utcnow()
    session.add(source)
    session.commit()
    return changed


def refresh_all_sources(session: Session) -> int:
    total = 0
    for source in session.exec(select(Source)).all():
        total += refresh_source(session, source)
    return total


def upsert_paper(session: Session, fetched: FetchedPaper, source: Source) -> Paper:
    normalized = normalize_title(fetched.title)
    paper = find_existing_paper(session, fetched.url, normalized, fetched.year)
    now = datetime.utcnow()
    if not paper:
        paper = Paper(
            title=fetched.title,
            normalized_title=normalized,
            source_type=source.source_type,
            source_url=source.url,
        )
    paper.title = fetched.title
    paper.normalized_title = normalized
    paper.authors = ", ".join(fetched.authors)
    paper.abstract = fetched.abstract
    paper.year = fetched.year
    paper.published_at = fetched.published_at
    paper.url = fetched.url
    paper.pdf_url = fetched.pdf_url
    paper.source_type = source.source_type
    paper.source_url = source.url
    paper.updated_at = now
    session.add(paper)
    session.flush()
    return paper


def find_existing_paper(session: Session, url: str | None, normalized_title: str, year: int | None) -> Paper | None:
    if url:
        existing = session.exec(select(Paper).where(Paper.url == url)).first()
        if existing:
            return existing
    query = select(Paper).where(Paper.normalized_title == normalized_title)
    if year:
        query = query.where(Paper.year == year)
    return session.exec(query).first()


def ensure_state(session: Session, paper: Paper) -> None:
    state = session.exec(select(PaperState).where(PaperState.paper_id == paper.id)).first()
    if not state:
        session.add(PaperState(paper_id=paper.id))


def ensure_matches(
    session: Session,
    paper: Paper,
    fetched: FetchedPaper,
    researchers: list[Researcher],
    source: Source,
) -> None:
    matches = match_researchers(fetched, researchers)
    if source.researcher_id:
        researcher = next((item for item in researchers if item.id == source.researcher_id), None)
        if researcher and all(match.id != source.researcher_id for match, _ in matches):
            matches.append((researcher, "source_owner"))

    for researcher, reason in matches:
        exists = session.exec(
            select(PaperResearcherLink).where(
                PaperResearcherLink.paper_id == paper.id,
                PaperResearcherLink.researcher_id == researcher.id,
            )
        ).first()
        if not exists:
            session.add(PaperResearcherLink(paper_id=paper.id, researcher_id=researcher.id, match_reason=reason))
