from app.services.google_research import is_google_research_profile_url, parse_google_research_profile
from app.services.google_scholar import (
    is_google_scholar_profile_url,
    normalize_scholar_url,
    parse_google_scholar_profile,
)
from app.services.rss import parse_rss_entries


GOOGLE_HTML = """
<html>
  <body>
    <h1>Jane Researcher</h1>
    <article class="publication-card">
      <a href="/pubs/pub123">Efficient Transformers for Retrieval</a>
      <p>Alice A.</p>
      <p>Jane Researcher</p>
      <p>NeurIPS (2024)</p>
      <p>Preview abstract We study retrieval models. View details</p>
      <a href="/pubs/pub123.pdf">PDF</a>
    </article>
  </body>
</html>
"""


def test_google_research_parser_extracts_profile_and_papers():
    name, papers = parse_google_research_profile(GOOGLE_HTML, "https://research.google/people/jane/")

    assert name == "Jane Researcher"
    assert len(papers) == 1
    assert papers[0].title == "Efficient Transformers for Retrieval"
    assert papers[0].authors == ["Alice A.", "Jane Researcher"]
    assert papers[0].year == 2024
    assert papers[0].url == "https://research.google/pubs/pub123"
    assert papers[0].pdf_url == "https://research.google/pubs/pub123.pdf"
    assert "retrieval models" in papers[0].abstract


def test_rss_parser_extracts_basic_paper_fields():
    entries = [
        {
            "title": "Scaling Retrieval Systems",
            "author": "Jane Researcher, Bob Builder",
            "summary": "A paper about search.",
            "published": "2025-01-02T00:00:00",
            "link": "https://example.com/paper",
            "links": [{"href": "https://example.com/paper.pdf", "type": "application/pdf"}],
        }
    ]

    papers = parse_rss_entries(entries)

    assert len(papers) == 1
    assert papers[0].year == 2025
    assert papers[0].authors == ["Jane Researcher", "Bob Builder"]
    assert papers[0].pdf_url == "https://example.com/paper.pdf"


def test_google_research_url_validation_rejects_scholar_profiles():
    assert is_google_research_profile_url("https://research.google/people/jane/")
    assert not is_google_research_profile_url("https://scholar.google.com/citations?user=abc")


def test_google_scholar_parser_extracts_profile_and_papers():
    html = """
    <html>
      <head><title>Jane Scholar - Google Scholar</title></head>
      <body>
        <div id="gsc_prf_in">Jane Scholar</div>
        <table>
          <tr class="gsc_a_tr">
            <td class="gsc_a_t">
              <a class="gsc_a_at" href="/citations?view_op=view_citation&user=abc&citation_for_view=abc:1">
                Efficient retrieval for agents
              </a>
              <div class="gs_gray">Jane Scholar, Bob Author</div>
              <div class="gs_gray">Conference on Search Systems</div>
            </td>
            <td class="gsc_a_y"><span>2025</span></td>
          </tr>
        </table>
      </body>
    </html>
    """
    name, papers = parse_google_scholar_profile(html, "https://scholar.google.com/citations?user=abc")

    assert name == "Jane Scholar"
    assert len(papers) == 1
    assert papers[0].title == "Efficient retrieval for agents"
    assert papers[0].authors == ["Jane Scholar", "Bob Author"]
    assert papers[0].abstract == "Conference on Search Systems"
    assert papers[0].year == 2025
    assert papers[0].url.startswith("https://scholar.google.com/citations")


def test_google_scholar_url_helpers_accept_user_profile():
    url = "https://scholar.google.com/citations?hl=en&user=Np1dTpQAAAAJ&view_op=list_works&sortby=pubdate"
    assert is_google_scholar_profile_url(url)
    assert "pagesize=100" in normalize_scholar_url(url)
    assert "sortby=pubdate" in normalize_scholar_url(url)
