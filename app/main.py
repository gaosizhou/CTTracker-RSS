from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.database import create_db_and_tables, get_session
from app.i18n import get_lang, translate
from app.models import (
    ContentCreatorLink,
    ContentItem,
    ContentState,
    ContentTagLink,
    ContentType,
    Creator,
    CreatorKind,
    PaperStatus,
    Source,
    SourceType,
    Tag,
)
from app.services.google_scholar import fetch_google_scholar_profile, is_google_scholar_profile_url
from app.services.normalization import normalize_title
from app.services.rss import fetch_rss
from app.services.types import FetchedPaper
from app.services.youtube import resolve_youtube_feed_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    scheduler = None
    try:
        from app.services.scheduler import start_scheduler

        scheduler = start_scheduler()
    except Exception:
        scheduler = None
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Content Tracker", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["tr"] = translate


@app.get("/")
def home():
    return RedirectResponse("/focus", status_code=303)


@app.get("/papers")
def papers_page(request: Request, session: Session = Depends(get_session)):
    return content_page(request, session, ContentType.PAPER, "papers", "paper")


@app.get("/videos")
def videos_page(request: Request, session: Session = Depends(get_session)):
    return content_page(request, session, ContentType.VIDEO, "videos", "video")


@app.get("/posts")
def posts_page(request: Request, session: Session = Depends(get_session)):
    return content_page(request, session, ContentType.POST, "posts", "post")


@app.get("/focus")
def focus_page(request: Request, session: Session = Depends(get_session)):
    return content_page(request, session, None, "focus", "focus", focus_only=True)


@app.get("/watchlist")
def old_watchlist():
    return RedirectResponse("/focus", status_code=303)


@app.get("/researchers")
def old_researchers():
    return RedirectResponse("/creators", status_code=303)


def content_page(
    request: Request,
    session: Session,
    content_type: ContentType | None,
    page_key: str,
    add_mode: str,
    focus_only: bool = False,
):
    filters = parsed_filters(request)
    selected_type = content_type_from_filter(filters) if focus_only else content_type
    result = content_result(session, content_type, focus_only, filters)
    return templates.TemplateResponse(
        "content_list.html",
        {
            "request": request,
            "rows": result["rows"],
            "pagination": result["pagination"],
            "content_type": content_type.value if content_type else "",
            "content_type_options": list(ContentType),
            "page_key": page_key,
            "add_mode": add_mode,
            "filters": filters,
            "creators": creators_for_type(session, selected_type, focus_only=focus_only),
            "tags": all_tags(session),
            "years": content_years(session, selected_type),
            "platforms": content_platforms(session, selected_type),
            "statuses": PaperStatus,
            **view_prefs(request),
        },
    )


@app.post("/tags")
def create_tag(request: Request, name: str = Form(...), session: Session = Depends(get_session)):
    get_or_create_tag(session, name)
    session.commit()
    return back(request)


@app.get("/tags")
def tags_page(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse("tags.html", {"request": request, "tags": all_tags(session), **view_prefs(request)})


@app.post("/papers/scholars")
def add_scholar_source(
    scholar_profile_url: str = Form(...),
    aliases: str = Form(""),
    keywords: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    if not is_google_scholar_profile_url(scholar_profile_url):
        return redirect_error("/papers", "Please paste a Google Scholar citations URL.")
    try:
        name, _ = fetch_google_scholar_profile(scholar_profile_url)
    except Exception as exc:
        return redirect_error("/papers", f"Could not read this Scholar profile: {exc}")
    creator = Creator(
        name=name,
        kind=CreatorKind.SCHOLAR,
        profile_url=scholar_profile_url,
        platform="google_scholar",
        aliases=aliases,
        keywords=keywords,
        notes=notes,
    )
    session.add(creator)
    session.flush()
    source = Source(source_type=SourceType.GOOGLE_SCHOLAR_PROFILE, url=scholar_profile_url, creator_id=creator.id)
    session.add(source)
    session.flush()
    try:
        refresh_content_source(session, source)
    except Exception as exc:
        session.commit()
        return redirect_error("/papers", f"Scholar saved, but import failed: {exc}")
    session.commit()
    return RedirectResponse("/papers", status_code=303)


@app.post("/videos/sources")
def add_video_source(
    creator_name: str = Form(...),
    feed_url: str = Form(...),
    platform: str = Form("youtube"),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    try:
        resolved_feed_url = resolve_youtube_feed_url(feed_url)
    except Exception as exc:
        return redirect_error("/videos", f"Could not resolve YouTube feed: {exc}")
    creator = Creator(name=creator_name.strip(), kind=CreatorKind.VIDEO_CREATOR, profile_url=feed_url.strip(), platform=platform, notes=notes)
    session.add(creator)
    session.flush()
    source = Source(source_type=SourceType.YOUTUBE_RSS, url=resolved_feed_url, creator_id=creator.id)
    session.add(source)
    session.flush()
    try:
        refresh_content_source(session, source)
    except Exception as exc:
        session.commit()
        return redirect_error("/videos", f"Video source saved, but import failed: {exc}")
    session.commit()
    return RedirectResponse("/videos", status_code=303)


@app.post("/posts/manual")
def add_manual_post(
    title: str = Form(...),
    platform: str = Form("x"),
    creator_name: str = Form(""),
    url: str = Form(""),
    year: str = Form(""),
    description: str = Form(""),
    tag_ids: list[int] = Form(default=[]),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    creator = get_or_create_creator(session, creator_name, CreatorKind.ACCOUNT, platform) if creator_name.strip() else None
    item = create_content_item(
        session,
        ContentType.POST,
        FetchedPaper(title=title, authors=[creator_name] if creator_name else [], abstract=description, year=parse_year(year), url=url or None),
        SourceType.MANUAL,
        "manual",
        platform,
        creator,
    )
    state = ensure_content_state(session, item.id)
    state.in_focus = True
    state.focus_source = "manual"
    state.notes = notes
    session.add(state)
    sync_content_tags(session, item.id, tag_ids)
    session.commit()
    return RedirectResponse("/posts", status_code=303)


@app.post("/content/manual")
def add_manual_content(
    content_type: ContentType = Form(...),
    title: str = Form(...),
    chinese_title: str = Form(""),
    creator_text: str = Form(""),
    platform: str = Form("manual"),
    year: str = Form(""),
    url: str = Form(""),
    pdf_url: str = Form(""),
    description: str = Form(""),
    tag_ids: list[int] = Form(default=[]),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    item = ContentItem(
        content_type=content_type,
        title=title.strip(),
        chinese_title=chinese_title.strip(),
        normalized_title=normalize_title(title),
        creator_text=creator_text.strip(),
        description=description.strip(),
        year=parse_year(year),
        url=url.strip() or None,
        pdf_url=pdf_url.strip() or None,
        platform=platform.strip() or "manual",
        source_type=SourceType.MANUAL,
        source_url="manual",
    )
    session.add(item)
    session.flush()
    state = ensure_content_state(session, item.id)
    state.in_focus = True
    state.focus_source = "manual"
    state.notes = notes
    session.add(state)
    sync_content_tags(session, item.id, tag_ids)
    session.commit()
    return RedirectResponse(f"/{content_type.value}s" if content_type != ContentType.POST else "/posts", status_code=303)


@app.post("/api/refresh")
def refresh_all(session: Session = Depends(get_session)):
    for source in session.exec(select(Source)).all():
        refresh_content_source(session, source)
    session.commit()
    return RedirectResponse("/focus", status_code=303)


@app.post("/api/sources/{source_id}/refresh")
def refresh_one(source_id: int, request: Request, session: Session = Depends(get_session)):
    source = session.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    refresh_content_source(session, source)
    session.commit()
    return back(request)


@app.post("/content/{content_id}/focus-toggle")
def toggle_focus(content_id: int, request: Request, session: Session = Depends(get_session)):
    item = session.get(ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    state = ensure_content_state(session, content_id)
    state.in_focus = not state.in_focus
    if state.in_focus and not state.focus_source:
        state.focus_source = "selected"
    state.updated_at = datetime.utcnow()
    session.add(state)
    session.commit()
    return back(request)


@app.get("/content/{content_id}")
def content_detail(content_id: int, request: Request, session: Session = Depends(get_session)):
    item = session.get(ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    return templates.TemplateResponse(
        "content_detail.html",
        {
            "request": request,
            "item": item,
            "state": ensure_content_state(session, content_id),
            "tags": all_tags(session),
            "selected_tag_ids": selected_content_tag_ids(session, content_id),
            "creators": content_creators(session, content_id),
            "statuses": PaperStatus,
            **view_prefs(request),
        },
    )


@app.get("/content/{content_id}/edit")
def edit_content_page(content_id: int, request: Request, session: Session = Depends(get_session)):
    item = session.get(ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    return templates.TemplateResponse(
        "content_edit.html",
        {
            "request": request,
            "item": item,
            "state": ensure_content_state(session, content_id),
            "tags": all_tags(session),
            "selected_tag_ids": selected_content_tag_ids(session, content_id),
            "statuses": PaperStatus,
            **view_prefs(request),
        },
    )


@app.post("/content/{content_id}/edit")
def update_content(
    content_id: int,
    title: str = Form(...),
    chinese_title: str = Form(""),
    creator_text: str = Form(""),
    platform: str = Form(""),
    year: str = Form(""),
    url: str = Form(""),
    pdf_url: str = Form(""),
    description: str = Form(""),
    status: PaperStatus = Form(PaperStatus.UNREAD),
    favorite: bool = Form(False),
    in_focus: bool = Form(False),
    tag_ids: list[int] = Form(default=[]),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    item = session.get(ContentItem, content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    item.title = title.strip()
    item.chinese_title = chinese_title.strip()
    item.normalized_title = normalize_title(title)
    item.creator_text = creator_text.strip()
    item.platform = platform.strip()
    item.year = parse_year(year)
    item.url = url.strip() or None
    item.pdf_url = pdf_url.strip() or None
    item.description = description.strip()
    item.updated_at = datetime.utcnow()
    session.add(item)
    state = ensure_content_state(session, content_id)
    state.status = status
    state.favorite = favorite
    state.in_focus = in_focus
    if in_focus and not state.focus_source:
        state.focus_source = "selected"
    state.notes = notes
    state.updated_at = datetime.utcnow()
    session.add(state)
    sync_content_tags(session, content_id, tag_ids)
    session.commit()
    return RedirectResponse(f"/content/{content_id}", status_code=303)


@app.post("/content/{content_id}/tags")
def update_content_tags(content_id: int, tag_ids: list[int] = Form(default=[]), request: Request = None, session: Session = Depends(get_session)):
    sync_content_tags(session, content_id, tag_ids)
    session.commit()
    return back(request)


@app.post("/content/{content_id}/delete")
def delete_content(content_id: int, session: Session = Depends(get_session)):
    delete_content_records(session, content_id)
    session.commit()
    return RedirectResponse("/focus", status_code=303)


@app.get("/creators")
def creators_page(request: Request, session: Session = Depends(get_session)):
    sources = session.exec(select(Source)).all()
    source_map: dict[int, list[Source]] = {}
    for source in sources:
        if source.creator_id:
            source_map.setdefault(source.creator_id, []).append(source)
    return templates.TemplateResponse(
        "creators.html",
        {"request": request, "creator_groups": creator_groups(session), "source_map": source_map, **view_prefs(request)},
    )


@app.post("/creators")
def add_creator(
    name: str = Form(...),
    kind: CreatorKind = Form(CreatorKind.ACCOUNT),
    platform: str = Form(""),
    profile_url: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    session.add(Creator(name=name.strip(), kind=kind, platform=platform.strip(), profile_url=profile_url.strip() or None, notes=notes))
    session.commit()
    return RedirectResponse("/creators", status_code=303)


@app.post("/creators/{creator_id}/delete")
def delete_creator(creator_id: int, session: Session = Depends(get_session)):
    creator = session.get(Creator, creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    for source in session.exec(select(Source).where(Source.creator_id == creator_id)).all():
        session.delete(source)
    for link in session.exec(select(ContentCreatorLink).where(ContentCreatorLink.creator_id == creator_id)).all():
        session.delete(link)
    session.delete(creator)
    session.commit()
    return RedirectResponse("/creators", status_code=303)


@app.post("/preferences/language")
def toggle_language(request: Request):
    next_lang = "en" if get_lang(request) == "zh" else "zh"
    response = RedirectResponse(request.headers.get("referer", "/"), status_code=303)
    response.set_cookie("ui_lang", next_lang, max_age=60 * 60 * 24 * 365)
    return response


def refresh_content_source(session: Session, source: Source) -> int:
    creator = session.get(Creator, source.creator_id) if source.creator_id else None
    if source.source_type == SourceType.GOOGLE_SCHOLAR_PROFILE:
        profile_name, fetched_items = fetch_google_scholar_profile(source.url)
        if creator and creator.name == "Unknown Scholar":
            creator.name = profile_name
            session.add(creator)
        content_type = ContentType.PAPER
        platform = "google_scholar"
    elif source.source_type == SourceType.YOUTUBE_RSS:
        fetched_items = fetch_rss(source.url)
        content_type = ContentType.VIDEO
        platform = creator.platform if creator and creator.platform else "youtube"
    else:
        return 0

    changed = 0
    for fetched in fetched_items:
        item = create_content_item(session, content_type, fetched, source.source_type, source.url, platform, creator)
        ensure_content_state(session, item.id)
        changed += 1
    source.last_refreshed_at = datetime.utcnow()
    session.add(source)
    return changed


def create_content_item(
    session: Session,
    content_type: ContentType,
    fetched: FetchedPaper,
    source_type: SourceType,
    source_url: str,
    platform: str,
    creator: Creator | None,
) -> ContentItem:
    normalized = normalize_title(fetched.title)
    item = find_existing_content(session, fetched.url, normalized, fetched.year, creator)
    now = datetime.utcnow()
    if not item:
        item = ContentItem(
            content_type=content_type,
            title=fetched.title,
            normalized_title=normalized,
            source_type=source_type,
            source_url=source_url,
            platform=platform,
        )
    item.title = fetched.title
    item.normalized_title = normalized
    item.creator_text = ", ".join(fetched.authors) if fetched.authors else (creator.name if creator else "")
    item.description = fetched.abstract
    item.year = fetched.year
    item.published_at = fetched.published_at
    item.url = fetched.url
    item.pdf_url = fetched.pdf_url
    item.content_type = content_type
    item.source_type = source_type
    item.source_url = source_url
    item.platform = platform
    item.updated_at = now
    session.add(item)
    session.flush()
    if creator:
        link = session.exec(
            select(ContentCreatorLink).where(ContentCreatorLink.content_id == item.id, ContentCreatorLink.creator_id == creator.id)
        ).first()
        if not link:
            session.add(ContentCreatorLink(content_id=item.id, creator_id=creator.id, match_reason="source_owner"))
    return item


def find_existing_content(session: Session, url: str | None, normalized_title: str, year: int | None, creator: Creator | None) -> ContentItem | None:
    if url:
        existing = session.exec(select(ContentItem).where(ContentItem.url == url)).first()
        if existing:
            return existing
    query = select(ContentItem).where(ContentItem.normalized_title == normalized_title)
    if year:
        query = query.where(ContentItem.year == year)
    if creator:
        ids = session.exec(select(ContentCreatorLink.content_id).where(ContentCreatorLink.creator_id == creator.id)).all()
        if ids:
            query = query.where(col(ContentItem.id).in_(ids))
    return session.exec(query).first()


def content_result(session: Session, content_type: ContentType | None, focus_only: bool, filters: dict) -> dict:
    rows = content_rows(session, content_type, focus_only, filters)
    total = len(rows)
    page_size = filters["page_size"]
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(filters["page"], total_pages)
    start_index = (page - 1) * page_size
    end_index = min(start_index + page_size, total)
    return {
        "rows": rows[start_index:end_index],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_page": page - 1,
            "next_page": page + 1,
            "start": start_index + 1 if total else 0,
            "end": end_index,
        },
    }


def content_rows(session: Session, content_type: ContentType | None, focus_only: bool, filters: dict) -> list[dict]:
    query = select(ContentItem, ContentState).join(ContentState, ContentState.content_id == ContentItem.id)
    base_conditions = []
    filter_conditions = []
    if content_type:
        base_conditions.append(ContentItem.content_type == content_type)
    elif filters.get("content_type"):
        selected_type = content_type_from_filter(filters)
        if selected_type:
            base_conditions.append(ContentItem.content_type == selected_type)
    if focus_only:
        base_conditions.append(ContentState.in_focus == True)
    if filters["year"]:
        filter_conditions.append(ContentItem.year == filters["year"])
    if filters["platform"]:
        filter_conditions.append(ContentItem.platform == filters["platform"])
    if filters["status"]:
        filter_conditions.append(ContentState.status == filters["status"])
    if filters["keyword"]:
        like = f"%{filters['keyword']}%"
        filter_conditions.append(
            col(ContentItem.title).ilike(like)
            | col(ContentItem.chinese_title).ilike(like)
            | col(ContentItem.description).ilike(like)
            | col(ContentItem.creator_text).ilike(like)
        )
    if filters["creator_id"]:
        ids = session.exec(select(ContentCreatorLink.content_id).where(ContentCreatorLink.creator_id == filters["creator_id"])).all()
        filter_conditions.append(col(ContentItem.id).in_(ids or [-1]))
    if filters["tag_ids"]:
        ids = session.exec(select(ContentTagLink.content_id).where(col(ContentTagLink.tag_id).in_(filters["tag_ids"]))).all()
        filter_conditions.append(col(ContentItem.id).in_(ids or [-1]))

    if base_conditions:
        query = query.where(*base_conditions)
    if filter_conditions:
        if filters["match_mode"] == "any":
            query = query.where(or_(*filter_conditions))
        else:
            query = query.where(*filter_conditions)
    if filters["sort"] == "title":
        query = query.order_by(ContentItem.title)
    elif filters["sort"] == "year":
        query = query.order_by(col(ContentItem.year).asc(), col(ContentItem.published_at).asc())
    else:
        query = query.order_by(col(ContentItem.year).desc(), col(ContentItem.published_at).desc(), ContentItem.title)

    return [row_dict(session, item, state) for item, state in session.exec(query).all()]


def row_dict(session: Session, item: ContentItem, state: ContentState) -> dict:
    return {
        "item": item,
        "state": state,
        "creators": content_creators(session, item.id),
        "tags": content_tags(session, item.id),
        "tag_ids": selected_content_tag_ids(session, item.id),
    }


def parsed_filters(request: Request) -> dict:
    params = request.query_params
    return {
        "creator_id": safe_int(params.get("creator_id")),
        "year": safe_int(params.get("year")),
        "keyword": params.get("keyword", ""),
        "tag_ids": [safe_int(value) for value in params.getlist("tag_ids") if safe_int(value)],
        "status": params.get("status", ""),
        "platform": params.get("platform", ""),
        "content_type": params.get("content_type", ""),
        "match_mode": params.get("match_mode", "all"),
        "sort": params.get("sort", "year_desc"),
        "page": max(1, safe_int(params.get("page")) or 1),
        "page_size": min(100, max(1, safe_int(params.get("page_size")) or 20)),
    }


def ensure_content_state(session: Session, content_id: int) -> ContentState:
    state = session.exec(select(ContentState).where(ContentState.content_id == content_id)).first()
    if state:
        return state
    state = ContentState(content_id=content_id)
    session.add(state)
    session.flush()
    return state


def all_tags(session: Session) -> list[Tag]:
    return list(session.exec(select(Tag).order_by(Tag.name)).all())


def all_creators(session: Session) -> list[Creator]:
    return list(session.exec(select(Creator).order_by(Creator.name)).all())


def creators_for_type(session: Session, content_type: ContentType | None, focus_only: bool = False) -> list[Creator]:
    creators = all_creators(session)
    linked_creator_ids = linked_creator_ids_for_type(session, content_type, focus_only)
    if not content_type:
        if focus_only:
            return [creator for creator in creators if creator.id in linked_creator_ids]
        return creators
    allowed_kinds = {
        ContentType.PAPER: {CreatorKind.SCHOLAR},
        ContentType.VIDEO: {CreatorKind.VIDEO_CREATOR},
        ContentType.POST: {CreatorKind.ACCOUNT, CreatorKind.BLOGGER},
    }[content_type]
    return [creator for creator in creators if creator.kind in allowed_kinds or creator.id in linked_creator_ids]


def linked_creator_ids_for_type(session: Session, content_type: ContentType | None, focus_only: bool = False) -> set[int]:
    query = select(ContentCreatorLink.creator_id).join(ContentItem, ContentItem.id == ContentCreatorLink.content_id)
    if content_type:
        query = query.where(ContentItem.content_type == content_type)
    if focus_only:
        query = query.join(ContentState, ContentState.content_id == ContentItem.id).where(ContentState.in_focus == True)
    return {creator_id for creator_id in session.exec(query).all() if creator_id}


def creator_groups(session: Session) -> list[dict]:
    groups = []
    for kind in CreatorKind:
        creators = list(session.exec(select(Creator).where(Creator.kind == kind).order_by(Creator.name)).all())
        if creators:
            groups.append({"kind": kind, "creators": creators})
    return groups


def get_or_create_creator(session: Session, name: str, kind: CreatorKind, platform: str) -> Creator:
    existing = session.exec(select(Creator).where(Creator.name == name.strip(), Creator.platform == platform.strip())).first()
    if existing:
        return existing
    creator = Creator(name=name.strip(), kind=kind, platform=platform.strip())
    session.add(creator)
    session.flush()
    return creator


def get_or_create_tag(session: Session, name: str) -> Tag | None:
    clean = name.strip()
    if not clean:
        return None
    existing = session.exec(select(Tag).where(col(Tag.name).ilike(clean))).first()
    if existing:
        return existing
    tag = Tag(name=clean)
    session.add(tag)
    session.flush()
    return tag


def sync_content_tags(session: Session, content_id: int, tag_ids: list[int]) -> None:
    clean_ids = {int(tag_id) for tag_id in tag_ids if tag_id}
    for link in session.exec(select(ContentTagLink).where(ContentTagLink.content_id == content_id)).all():
        session.delete(link)
    for tag_id in clean_ids:
        if session.get(Tag, tag_id):
            session.add(ContentTagLink(content_id=content_id, tag_id=tag_id))


def selected_content_tag_ids(session: Session, content_id: int) -> list[int]:
    return list(session.exec(select(ContentTagLink.tag_id).where(ContentTagLink.content_id == content_id)).all())


def content_tags(session: Session, content_id: int) -> list[Tag]:
    ids = selected_content_tag_ids(session, content_id)
    if not ids:
        return []
    return list(session.exec(select(Tag).where(col(Tag.id).in_(ids)).order_by(Tag.name)).all())


def content_creators(session: Session, content_id: int) -> list[Creator]:
    ids = session.exec(select(ContentCreatorLink.creator_id).where(ContentCreatorLink.content_id == content_id)).all()
    if not ids:
        return []
    return list(session.exec(select(Creator).where(col(Creator.id).in_(ids)).order_by(Creator.name)).all())


def content_years(session: Session, content_type: ContentType | None) -> list[int]:
    query = select(ContentItem.year).where(ContentItem.year != None).distinct().order_by(col(ContentItem.year).desc())
    if content_type:
        query = query.where(ContentItem.content_type == content_type)
    return list(session.exec(query).all())


def content_platforms(session: Session, content_type: ContentType | None) -> list[str]:
    query = select(ContentItem.platform).where(ContentItem.platform != "").distinct().order_by(ContentItem.platform)
    if content_type:
        query = query.where(ContentItem.content_type == content_type)
    return list(session.exec(query).all())


def delete_content_records(session: Session, content_id: int) -> None:
    item = session.get(ContentItem, content_id)
    if not item:
        return
    for state in session.exec(select(ContentState).where(ContentState.content_id == content_id)).all():
        session.delete(state)
    for link in session.exec(select(ContentCreatorLink).where(ContentCreatorLink.content_id == content_id)).all():
        session.delete(link)
    for link in session.exec(select(ContentTagLink).where(ContentTagLink.content_id == content_id)).all():
        session.delete(link)
    session.delete(item)


def parse_year(value: str) -> int | None:
    return int(value) if value and value.strip() else None


def safe_int(value: str | None) -> int | None:
    if not value or not str(value).strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


def content_type_from_filter(filters: dict) -> ContentType | None:
    try:
        return ContentType(filters.get("content_type"))
    except ValueError:
        return None


def back(request: Request | None) -> RedirectResponse:
    return RedirectResponse(request.headers.get("referer", "/focus") if request else "/focus", status_code=303)


def redirect_error(path: str, message: str) -> RedirectResponse:
    return RedirectResponse(f"{path}?{urlencode({'error': message})}", status_code=303)


def view_prefs(request: Request) -> dict:
    return {"lang": get_lang(request)}
