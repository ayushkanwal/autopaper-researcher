from __future__ import annotations

from typing import List

import requests

from autopaper.models import PaperRecord
from autopaper.utils import adapt_query_for_source, extract_keywords, normalize_whitespace, reconstruct_openalex_abstract

USER_AGENT = "auto-paper-populator/0.3"
OPENALEX_API_URL = "https://api.openalex.org/works"


class OpenAlexSource:
    name = "openalex"

    def __init__(self, mailto: str | None = None, session: requests.Session | None = None) -> None:
        self.mailto = mailto
        self.session = session or requests.Session()

    def search(self, query: str, max_results: int) -> List[PaperRecord]:
        adapted_query = adapt_query_for_source(query, self.name)
        params = {
            "search": adapted_query,
            "per-page": min(max_results, 200),
            "sort": "publication_date:desc",
        }
        if self.mailto:
            params["mailto"] = self.mailto
        response = self.session.get(
            OPENALEX_API_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or []
        papers: List[PaperRecord] = []
        for item in results:
            title = normalize_whitespace(item.get("display_name") or "")
            abstract = reconstruct_openalex_abstract(item.get("abstract_inverted_index"))
            doi = item.get("doi")
            if doi:
                doi = doi.replace("https://doi.org/", "")
            source_id = (item.get("id") or "").rsplit("/", 1)[-1]
            authors = [
                normalize_whitespace((authorship.get("author") or {}).get("display_name") or "")
                for authorship in item.get("authorships") or []
            ]
            best_oa = item.get("best_oa_location") or {}
            primary = item.get("primary_location") or {}
            pdf_url = best_oa.get("pdf_url") or primary.get("pdf_url")
            keywords = [
                normalize_whitespace((concept or {}).get("display_name") or "")
                for concept in item.get("concepts") or []
                if normalize_whitespace((concept or {}).get("display_name") or "")
            ]
            if not keywords:
                keywords = extract_keywords(title, abstract)
            papers.append(
                PaperRecord(
                    source="OpenAlex",
                    source_id=source_id,
                    title=title,
                    abstract=abstract,
                    authors=[author for author in authors if author],
                    published_at=normalize_whitespace(item.get("publication_date") or ""),
                    updated_at=normalize_whitespace(item.get("updated_date") or item.get("publication_date") or ""),
                    doi=doi,
                    url=item.get("id") or "",
                    pdf_url=pdf_url,
                    keywords=keywords[:12],
                    raw_metadata={"matched_query": adapted_query, "openalex_id": item.get("id")},
                )
            )
        return papers
