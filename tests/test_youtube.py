from app.services.youtube import extract_channel_id, resolve_youtube_feed_url


def test_extract_channel_id_from_youtube_html():
    html = '<html><head><meta itemprop="channelId" content="UCabcDEF12345678901234"></head></html>'

    assert extract_channel_id(html) == "UCabcDEF12345678901234"


def test_resolve_youtube_channel_path_to_feed():
    url = "https://www.youtube.com/channel/UCabcDEF12345678901234/videos"

    assert resolve_youtube_feed_url(url) == "https://www.youtube.com/feeds/videos.xml?channel_id=UCabcDEF12345678901234"


def test_resolve_youtube_handle_page_to_feed(monkeypatch):
    class FakeResponse:
        text = '{"channelId":"UCabcDEF12345678901234"}'

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def get(self, url):
            return FakeResponse()

    monkeypatch.setattr("app.services.youtube.httpx.Client", FakeClient)

    assert (
        resolve_youtube_feed_url("https://www.youtube.com/@-techbeat3270/videos")
        == "https://www.youtube.com/feeds/videos.xml?channel_id=UCabcDEF12345678901234"
    )
