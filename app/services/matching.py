from app.models import Researcher
from app.services.normalization import split_csv
from app.services.types import FetchedPaper


def match_researchers(paper: FetchedPaper, researchers: list[Researcher]) -> list[tuple[Researcher, str]]:
    haystack = " ".join([paper.title, " ".join(paper.authors), paper.abstract]).lower()
    matches: list[tuple[Researcher, str]] = []
    for researcher in researchers:
        names = [researcher.name, *split_csv(researcher.aliases)]
        if any(name and name.lower() in haystack for name in names):
            matches.append((researcher, "author_or_alias"))
            continue
        keywords = split_csv(researcher.keywords)
        if keywords and any(keyword.lower() in haystack for keyword in keywords):
            matches.append((researcher, "keyword"))
    return matches
