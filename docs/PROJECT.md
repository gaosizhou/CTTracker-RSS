# Content Tracker Project Documentation

Content Tracker is a local FastAPI web app for following papers, videos, posts, and personally focused content from creators.

## Purpose

The app is organized around a unified content model:

- **Papers**: imported from Google Scholar profiles.
- **Videos**: imported from YouTube RSS feeds.
- **Posts**: manually added links such as tweets, short posts, and blog updates.
- **Focus**: a cross-type list of content the user explicitly cares about.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

The default SQLite database is `rss_papers.db`; set `DATABASE_URL` to use another file.

## Pages

- `/papers`: paper pool, Google Scholar profile import, paper filters.
- `/videos`: video pool, YouTube RSS source import, video filters.
- `/posts`: manual post/link entry and post filters.
- `/focus`: all focused content across papers, videos, and posts.
- `/creators`: shared creator/account/source overview.
- `/tags`: tag creation and tag list.
- `/content/{id}`: content detail.
- `/content/{id}/edit`: content edit form.

Old `/watchlist` and `/researchers` links redirect to `/focus` and `/creators`.

## Data Model

### `ContentItem`

Unified item for papers, videos, and posts.

Important fields:

- `content_type`: `paper`, `video`, or `post`
- `title`, `chinese_title`
- `creator_text`
- `description`
- `year`, `published_at`
- `url`, `pdf_url`
- `platform`
- `source_type`, `source_url`

### `Creator`

Unified creator record for scholars, video creators, bloggers, and accounts.

Important fields:

- `name`
- `kind`
- `platform`
- `profile_url`
- `aliases`, `keywords`, `notes`

### `Source`

Import source. Current active source types:

- `google_scholar_profile`
- `youtube_rss`
- `manual`

Legacy source types remain in the enum for compatibility.

### `ContentState`

User state for any content item:

- `status`: `unread`, `queued`, `read`
- `favorite`
- `in_focus`
- `focus_source`
- `notes`

### Tags

`Tag` plus `ContentTagLink` gives reusable multi-tag support for every content type.

Legacy paper tables still exist so older data can be migrated, but new routes use the unified content tables.

## Import Behavior

### Papers

Google Scholar profile URLs are accepted. The importer normalizes Scholar URLs, parses visible publication rows, and handles 403/captcha responses with clear errors.

### Videos

YouTube RSS feed URLs are accepted directly. Imported videos are stored as `ContentItem(type=video, platform=youtube)` and de-duplicated by URL first, then normalized title/year/creator.

### Posts

Posts are manual in v1. No X/Twitter scraping is attempted.

## Migration

Startup creates new unified tables and migrates existing paper data when `ContentItem` is empty:

- `Paper` -> `ContentItem(type=paper)`
- `Researcher` -> `Creator(kind=scholar)`
- `PaperState` -> `ContentState`
- `PaperTagLink` -> `ContentTagLink`
- `PaperResearcherLink` -> `ContentCreatorLink`

Existing data is preserved; old tables are not dropped.

## Tests

Run:

```powershell
python -m pytest
```

Coverage includes parser helpers, old importer compatibility, unified filtering, manual content creation, focus state, and tag links.

## Known Limits

- Google Scholar may block automated requests.
- YouTube is the only automatic video source in v1.
- Posts are manual-link only.
- The app is single-user and local.
- There is no full migration framework yet; startup migrations are lightweight compatibility helpers.
