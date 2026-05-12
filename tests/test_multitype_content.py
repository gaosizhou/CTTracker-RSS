from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.main import app, refresh_content_source
from app.models import ContentCreatorLink, ContentItem, ContentState, ContentType, Creator, CreatorKind, Source, SourceType
from app.services.types import FetchedPaper


def test_youtube_rss_source_imports_videos_without_duplicates(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def fake_fetch_rss(url):
        return [FetchedPaper(title="New Video", authors=["Channel"], year=2026, url="https://youtube.test/v/1")]

    monkeypatch.setattr("app.main.fetch_rss", fake_fetch_rss)

    with Session(engine) as session:
        creator = Creator(name="Channel", kind=CreatorKind.VIDEO_CREATOR, platform="youtube")
        session.add(creator)
        session.commit()
        session.refresh(creator)
        source = Source(source_type=SourceType.YOUTUBE_RSS, url="https://youtube.test/feed", creator_id=creator.id)
        session.add(source)
        session.commit()
        session.refresh(source)

        assert refresh_content_source(session, source) == 1
        assert refresh_content_source(session, source) == 1
        session.commit()

        items = session.exec(select(ContentItem)).all()
        assert len(items) == 1
        assert items[0].content_type == ContentType.VIDEO
        assert items[0].platform == "youtube"


def test_manual_post_creation_route():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    from app.database import get_session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.post(
                "/posts/manual",
                data={
                    "title": "Interesting thread",
                    "platform": "x",
                    "creator_name": "Some Account",
                    "url": "https://x.test/post/1",
                    "year": "2026",
                    "description": "Short-form post",
                },
                follow_redirects=False,
            )
            assert response.status_code == 303

        with Session(engine) as session:
            item = session.exec(select(ContentItem).where(ContentItem.title == "Interesting thread")).one()
            state = session.exec(select(ContentState).where(ContentState.content_id == item.id)).one()
            assert item.content_type == ContentType.POST
            assert item.platform == "x"
            assert state.in_focus is True
    finally:
        app.dependency_overrides.clear()


def test_creator_delete_removes_sources_and_links_but_keeps_content():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    from app.database import get_session

    with Session(engine) as session:
        creator = Creator(name="Channel", kind=CreatorKind.VIDEO_CREATOR, platform="youtube")
        session.add(creator)
        session.commit()
        session.refresh(creator)
        item = ContentItem(
            content_type=ContentType.VIDEO,
            title="Video",
            normalized_title="video",
            platform="youtube",
            source_type=SourceType.YOUTUBE_RSS,
            source_url="https://youtube.test/feed",
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        session.add(Source(source_type=SourceType.YOUTUBE_RSS, url="https://youtube.test/feed", creator_id=creator.id))
        session.add(ContentCreatorLink(content_id=item.id, creator_id=creator.id))
        session.commit()
        creator_id = creator.id

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.post(f"/creators/{creator_id}/delete", follow_redirects=False)
            assert response.status_code == 303

        with Session(engine) as session:
            assert session.get(Creator, creator_id) is None
            assert session.exec(select(Source)).all() == []
            assert session.exec(select(ContentCreatorLink)).all() == []
            assert len(session.exec(select(ContentItem)).all()) == 1
    finally:
        app.dependency_overrides.clear()
