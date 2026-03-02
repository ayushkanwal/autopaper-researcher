from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List

import requests

from autopaper.models import PaperRecord
from autopaper.utils import adapt_query_for_source, extract_keywords, normalize_whitespace

ARXIV_API_URL = "https://export.arxiv.org/api/query"
USER_AGENT = "auto-paper-populator/0.3"


class ArxivSource:
    name = "arxiv"

    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def search(self, query: str, max_results: int) -> List[PaperRecord]:
        adapted_query = adapt_query_for_source(query, self.name)
        response = self.session.get(
            ARXIV_API_URL,
            params={
                "search_query": adapted_query,
                "start": 0,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
            timeout=45,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        return self._parse_feed(response.text, adapted_query)

    def _parse_feed(self, feed_xml: str, query: str) -> List[PaperRecord]:
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        root = ET.fromstring(feed_xml)
        papers: List[PaperRecord] = []
        for entry in root.findall("atom:entry", ns):
            id_url = normalize_whitespace(entry.findtext("atom:id", default="", namespaces=ns))
            title = normalize_whitespace(entry.findtext("atom:title", default="", namespaces=ns))
            abstract = normalize_whitespace(entry.findtext("atom:summary", default="", namespaces=ns))
            comments = normalize_whitespace(entry.findtext("arxiv:comment", default="", namespaces=ns))
            authors = [
                normalize_whitespace(author.findtext("atom:name", default="", namespaces=ns))
                for author in entry.findall("atom:author", ns)
            ]
            published = normalize_whitespace(entry.findtext("atom:published", default="", namespaces=ns))
            updated = normalize_whitespace(entry.findtext("atom:updated", default="", namespaces=ns))
            doi_node = entry.find("arxiv:doi", ns)
            doi = normalize_whitespace(doi_node.text) if doi_node is not None and doi_node.text else None
            pdf_url = None
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("title") == "pdf":
                    pdf_url = link.attrib.get("href")
                    break
            if not pdf_url and id_url:
                base = id_url.replace("/abs/", "/pdf/")
                pdf_url = f"{base}.pdf" if not base.endswith(".pdf") else base
            source_id = id_url.rsplit("/", 1)[-1] if id_url else ""
            papers.append(
                PaperRecord(
                    source="arXiv",
                    source_id=source_id,
                    title=title,
                    abstract=abstract,
                    authors=[author for author in authors if author],
                    published_at=published,
                    updated_at=updated,
                    doi=doi,
                    url=id_url,
                    pdf_url=pdf_url,
                    keywords=extract_keywords(title, abstract),
                    raw_metadata={"matched_query": query, "comments": comments},
                )
            )
        return papers
