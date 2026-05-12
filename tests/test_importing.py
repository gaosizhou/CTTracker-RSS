from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Paper, PaperResearcherLink, Researcher, Source, SourceType
from app.services.importer import upsert_paper, ensure_matches, ensure_state
from app.services.types import FetchedPaper


def test_upsert_deduplicates_by_url_and_matches_researcher():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        researcher = Researcher(name="Jane Researcher", aliases="J. Researcher", keywords="retrieval")
        source = Source(source_type=SourceType.GOOGLE_RESEARCH_PROFILE, url="https://research.google/people/jane/", researcher_id=1)
        session.add(researcher)
        session.add(source)
        session.commit()
        session.refresh(researcher)
        session.refresh(source)

        fetched = FetchedPaper(
            title="Efficient Transformers for Retrieval",
            authors=["Jane Researcher"],
            year=2024,
            url="https://research.google/pubs/pub123",
        )
        paper = upsert_paper(session, fetched, source)
        ensure_state(session, paper)
        ensure_matches(session, paper, fetched, [researcher], source)
        duplicate = upsert_paper(session, fetched, source)
        session.commit()

        assert paper.id == duplicate.id
        assert len(session.exec(select(Paper)).all()) == 1
        assert len(session.exec(select(PaperResearcherLink)).all()) == 1
