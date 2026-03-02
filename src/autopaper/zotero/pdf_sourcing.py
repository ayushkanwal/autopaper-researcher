from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET
from typing import Optional, Tuple

import requests

from autopaper.models import PaperRecord
from autopaper.utils import doi_to_arxiv_id, normalize_arxiv_id, normalize_doi, normalize_title, normalize_whitespace, url_to_arxiv_id

ARXIV_API_URL = "https://export.arxiv.org/api/query"
USER_AGENT = "auto-paper-populator/0.3"



def query_arxiv_by_title(title: str) -> Optional[Tuple[str, str]]:
    response = requests.get(
        ARXIV_API_URL,
        params={"search_query": f'all:"{title}"', "start": 0, "max_results": 3},
        timeout=40,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(response.text)
    wanted = normalize_title(title)
    for entry in root.findall("atom:entry", ns):
        found_title = normalize_whitespace(entry.findtext("atom:title", default="", namespaces=ns))
        found_id_url = normalize_whitespace(entry.findtext("atom:id", default="", namespaces=ns))
        if not found_id_url:
            continue
        found_norm = normalize_title(found_title)
        if found_norm == wanted or wanted in found_norm or found_norm in wanted:
            arxiv_id = normalize_arxiv_id(found_id_url.rsplit("/", 1)[-1])
            return arxiv_id, found_id_url
    return None



def openalex_pdf_for_doi(doi: str) -> Optional[str]:
    target = urllib.parse.quote(f"https://doi.org/{normalize_doi(doi)}", safe="")
    response = requests.get(
        f"https://api.openalex.org/works/{target}",
        timeout=30,
        headers={"User-Agent": USER_AGENT},
    )
    if response.status_code != 200:
        return None
    payload = response.json()
    best = payload.get("best_oa_location") or {}
    primary = payload.get("primary_location") or {}
    for candidate in (best.get("pdf_url"), primary.get("pdf_url")):
        if candidate:
            return candidate
    return None



def crossref_pdf_for_doi(doi: str) -> Optional[str]:
    response = requests.get(
        f"https://api.crossref.org/works/{normalize_doi(doi)}",
        timeout=30,
        headers={"User-Agent": USER_AGENT},
    )
    if response.status_code != 200:
        return None
    message = response.json().get("message", {})
    links = message.get("link") or []
    for link in links:
        url = link.get("URL") or ""
        content_type = (link.get("content-type") or "").lower()
        if url and ("pdf" in content_type or "/pdf/" in url or url.lower().endswith(".pdf")):
            return url
    return None



def source_pdf_url(paper: PaperRecord) -> Tuple[Optional[str], str]:
    if paper.pdf_url:
        return paper.pdf_url, "source-entry"
    if paper.doi:
        arxiv_id = doi_to_arxiv_id(paper.doi)
        if arxiv_id:
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf", "doi-arxiv"
    if paper.url:
        arxiv_id = url_to_arxiv_id(paper.url)
        if arxiv_id:
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf", "url-arxiv"
    if paper.doi:
        openalex = openalex_pdf_for_doi(paper.doi)
        if openalex:
            return openalex, "openalex"
        crossref = crossref_pdf_for_doi(paper.doi)
        if crossref:
            return crossref, "crossref"
    by_title = query_arxiv_by_title(paper.title)
    if by_title:
        arxiv_id, _ = by_title
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf", "title-arxiv"
    return None, "not-found"
