from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.main import app
from app.models import ContentItem, ContentState, ContentTagLink, ContentType, SourceType, Tag


def test_manual_focus_content_creation():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    from app.database import get_session

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        tag_response = client.post("/tags", data={"name": "important"}, headers={"referer": "/focus"}, follow_redirects=False)
        assert tag_response.status_code == 303
        with Session(engine) as session:
            tag = session.exec(select(Tag).where(Tag.name == "important")).one()

        response = client.post(
            "/content/manual",
            data={
                "content_type": ContentType.VIDEO.value,
                "title": "Manual Focus Video",
                "creator_text": "Jane Creator",
                "platform": "youtube",
                "year": "2026",
                "tag_ids": [str(tag.id)],
            },
            follow_redirects=False,
        )

        assert response.status_code == 303
        with Session(engine) as session:
            item = session.exec(select(ContentItem).where(ContentItem.title == "Manual Focus Video")).one()
            state = session.exec(select(ContentState).where(ContentState.content_id == item.id)).one()
            links = session.exec(select(ContentTagLink).where(ContentTagLink.content_id == item.id)).all()
            assert item.content_type == ContentType.VIDEO
            assert item.source_type == SourceType.MANUAL
            assert state.in_focus is True
            assert state.focus_source == "manual"
            assert len(links) == 1
    finally:
        app.dependency_overrides.clear()
