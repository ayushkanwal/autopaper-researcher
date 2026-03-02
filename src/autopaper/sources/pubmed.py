from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List

import requests

from autopaper.models import PaperRecord
from autopaper.utils import adapt_query_for_source, extract_keywords, normalize_whitespace

USER_AGENT = "auto-paper-populator/0.3"
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedSource:
    name = "pubmed"

    def __init__(self, email: str | None = None, api_key: str | None = None, session: requests.Session | None = None) -> None:
        self.email = email
        self.api_key = api_key
        self.session = session or requests.Session()

    def _base_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def search(self, query: str, max_results: int) -> List[PaperRecord]:
        adapted_query = adapt_query_for_source(query, self.name)
        params = self._base_params()
        params.update(
            {
                "db": "pubmed",
                "term": adapted_query,
                "retmode": "json",
                "retmax": str(max_results),
                "sort": "pub date",
            }
        )
        response = self.session.get(
            f"{EUTILS_BASE}/esearch.fcgi",
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=45,
        )
        response.raise_for_status()
        ids = response.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        fetch_params = self._base_params()
        fetch_params.update({"db": "pubmed", "retmode": "xml", "id": ",".join(ids)})
        fetch = self.session.get(
            f"{EUTILS_BASE}/efetch.fcgi",
            params=fetch_params,
            headers={"User-Agent": USER_AGENT},
            timeout=45,
        )
        fetch.raise_for_status()
        root = ET.fromstring(fetch.text)
        papers: List[PaperRecord] = []
        for article in root.findall(".//PubmedArticle"):
            pmid = normalize_whitespace(article.findtext(".//PMID", default=""))
            title = normalize_whitespace(article.findtext(".//ArticleTitle", default=""))
            abstract_parts = [normalize_whitespace(node.text or "") for node in article.findall(".//Abstract/AbstractText")]
            abstract = normalize_whitespace(" ".join(part for part in abstract_parts if part))
            authors = []
            for author in article.findall(".//Author"):
                collective = normalize_whitespace(author.findtext("CollectiveName", default=""))
                if collective:
                    authors.append(collective)
                    continue
                last = normalize_whitespace(author.findtext("LastName", default=""))
                fore = normalize_whitespace(author.findtext("ForeName", default=""))
                full = normalize_whitespace(f"{fore} {last}")
                if full:
                    authors.append(full)
            doi = None
            for aid in article.findall(".//ArticleId"):
                if (aid.attrib.get("IdType") or "").lower() == "doi":
                    doi = normalize_whitespace(aid.text or "")
                    break
            year = normalize_whitespace(article.findtext(".//PubDate/Year", default=""))
            month = normalize_whitespace(article.findtext(".//PubDate/Month", default="01")) or "01"
            day = normalize_whitespace(article.findtext(".//PubDate/Day", default="01")) or "01"
            published = f"{year}-{month}-{day}" if year else ""
            papers.append(
                PaperRecord(
                    source="PubMed",
                    source_id=pmid,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    published_at=published,
                    updated_at=published,
                    doi=doi,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                    pdf_url=None,
                    keywords=extract_keywords(title, abstract),
                    raw_metadata={"matched_query": adapted_query, "pmid": pmid},
                )
            )
        return papers
