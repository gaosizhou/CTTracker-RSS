from sqlmodel import Session, SQLModel, create_engine

from app.main import content_result, content_rows, creators_for_type, sync_content_tags
from app.models import ContentCreatorLink, ContentItem, ContentState, ContentType, Creator, CreatorKind, PaperStatus, SourceType, Tag
from app.services.normalization import normalize_title


def test_content_rows_filters_by_year_keyword_tag_and_status():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        tag = Tag(name="llm")
        session.add(tag)
        session.commit()
        session.refresh(tag)

        item = ContentItem(
            content_type=ContentType.PAPER,
            title="Retrieval Augmented Models",
            normalized_title=normalize_title("Retrieval Augmented Models"),
            creator_text="Jane Researcher",
            description="search and retrieval",
            year=2024,
            platform="google_scholar",
            source_type=SourceType.GOOGLE_SCHOLAR_PROFILE,
            source_url="https://scholar.google.com/citations?user=abc",
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        session.add(ContentState(content_id=item.id, status=PaperStatus.QUEUED))
        sync_content_tags(session, item.id, [tag.id])
        session.commit()

        rows = content_rows(
            session=session,
            content_type=ContentType.PAPER,
            focus_only=False,
            filters={
                "creator_id": None,
                "year": 2024,
                "keyword": "retrieval",
                "tag_ids": [tag.id],
                "status": PaperStatus.QUEUED.value,
                "platform": "",
                "match_mode": "all",
                "sort": "year_desc",
            },
        )

        assert len(rows) == 1
        assert rows[0]["item"].title == "Retrieval Augmented Models"


def test_creators_are_scoped_by_content_type():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        scholar = Creator(name="Scholar", kind=CreatorKind.SCHOLAR, platform="google_scholar")
        channel = Creator(name="Channel", kind=CreatorKind.VIDEO_CREATOR, platform="youtube")
        account = Creator(name="Account", kind=CreatorKind.ACCOUNT, platform="x")
        session.add(scholar)
        session.add(channel)
        session.add(account)
        session.commit()
        session.refresh(scholar)
        session.refresh(channel)
        session.refresh(account)

        paper_creators = creators_for_type(session, ContentType.PAPER)
        video_creators = creators_for_type(session, ContentType.VIDEO)
        post_creators = creators_for_type(session, ContentType.POST)

        assert [creator.name for creator in paper_creators] == ["Scholar"]
        assert [creator.name for creator in video_creators] == ["Channel"]
        assert [creator.name for creator in post_creators] == ["Account"]


def test_content_result_paginates_after_filtering():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        creator = Creator(name="Scholar", kind=CreatorKind.SCHOLAR, platform="google_scholar")
        session.add(creator)
        session.commit()
        session.refresh(creator)

        for index in range(25):
            item = ContentItem(
                content_type=ContentType.PAPER,
                title=f"Paper {index:02d}",
                normalized_title=normalize_title(f"Paper {index:02d}"),
                creator_text="Scholar",
                year=2026,
                platform="google_scholar",
                source_type=SourceType.GOOGLE_SCHOLAR_PROFILE,
                source_url="https://scholar.google.com/citations?user=abc",
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            session.add(ContentState(content_id=item.id))
            session.add(ContentCreatorLink(content_id=item.id, creator_id=creator.id))
        session.commit()

        result = content_result(
            session=session,
            content_type=ContentType.PAPER,
            focus_only=False,
            filters={
                "creator_id": creator.id,
                "year": None,
                "keyword": "",
                "tag_ids": [],
                "status": "",
                "platform": "",
                "content_type": "",
                "match_mode": "all",
                "sort": "title",
                "page": 2,
                "page_size": 20,
            },
        )

        assert result["pagination"]["total"] == 25
        assert result["pagination"]["page"] == 2
        assert len(result["rows"]) == 5
        assert result["rows"][0]["item"].title == "Paper 20"


def test_match_any_keeps_page_content_type_boundaries():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        paper = ContentItem(
            content_type=ContentType.PAPER,
            title="Paper About Systems",
            normalized_title=normalize_title("Paper About Systems"),
            year=2026,
            platform="google_scholar",
            source_type=SourceType.GOOGLE_SCHOLAR_PROFILE,
            source_url="https://scholar.google.com/citations?user=abc",
        )
        video = ContentItem(
            content_type=ContentType.VIDEO,
            title="Systems Video",
            normalized_title=normalize_title("Systems Video"),
            year=2026,
            platform="youtube",
            source_type=SourceType.YOUTUBE_RSS,
            source_url="https://youtube.test/feed",
        )
        session.add(paper)
        session.add(video)
        session.commit()
        session.refresh(paper)
        session.refresh(video)
        session.add(ContentState(content_id=paper.id))
        session.add(ContentState(content_id=video.id))
        session.commit()

        rows = content_rows(
            session=session,
            content_type=ContentType.PAPER,
            focus_only=False,
            filters={
                "creator_id": None,
                "year": None,
                "keyword": "Systems",
                "tag_ids": [],
                "status": "",
                "platform": "youtube",
                "content_type": "",
                "match_mode": "any",
                "sort": "title",
                "page": 1,
                "page_size": 20,
            },
        )

        assert [row["item"].content_type for row in rows] == [ContentType.PAPER]
