from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

from autopaper.models import PaperRecord
from autopaper.utils import ensure_directory, normalize_whitespace
from autopaper.zotero.client import USER_AGENT, ZoteroClient
from autopaper.zotero.pdf_sourcing import crossref_pdf_for_doi, openalex_pdf_for_doi, query_arxiv_by_title



def download_pdf(url: str, target_path: Path) -> Tuple[int, str]:
    response = requests.get(url, stream=True, timeout=120, headers={"User-Agent": USER_AGENT}, allow_redirects=True)
    response.raise_for_status()
    content_type = (response.headers.get("Content-Type") or "").lower()
    if "pdf" not in content_type and not response.url.lower().endswith(".pdf"):
        if "html" in content_type or "text/" in content_type:
            snippet = response.text[:200] if hasattr(response, "text") else ""
            raise RuntimeError(f"Source did not return PDF content-type ({content_type}). {snippet}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with target_path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if not chunk:
                continue
            handle.write(chunk)
            written += len(chunk)
    return written, content_type



def import_real_pdf_for_parent(
    client: ZoteroClient,
    parent_key: str,
    title: str,
    pdf_url: str,
    download_dir: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    filename = f"{parent_key}.pdf"
    local_path = ensure_directory(download_dir) / filename
    result: Dict[str, Any] = {
        "item_key": parent_key,
        "title": title,
        "url": pdf_url,
        "attachment_key": "<dry-run>" if dry_run else None,
        "bytes": 0,
    }
    if dry_run:
        return result
    size, content_type = download_pdf(pdf_url, local_path)
    if size <= 0:
        raise RuntimeError("Downloaded file is empty")
    file_bytes = local_path.read_bytes()
    md5_hex = hashlib.md5(file_bytes).hexdigest()
    filesize = len(file_bytes)
    mtime_ms = int(local_path.stat().st_mtime * 1000)
    attachment_key = client.create_imported_file_attachment(parent_key=parent_key, filename=filename, source_url=pdf_url)
    auth = client.authorize_upload(
        attachment_key=attachment_key,
        md5_hex=md5_hex,
        filename=filename,
        filesize=filesize,
        mtime_ms=mtime_ms,
    )
    if auth.get("exists") != 1:
        upload_key = auth.get("uploadKey")
        if not upload_key:
            raise RuntimeError(f"Missing uploadKey in auth response: {json.dumps(auth)}")
        client.upload_binary(auth, file_bytes)
        client.register_upload(attachment_key, upload_key)
    if not client.attachment_has_remote_file(attachment_key):
        raise RuntimeError("Upload completed but remote file check failed")
    result.update({"attachment_key": attachment_key, "bytes": filesize, "content_type": content_type})
    return result



def pick_pdf_source_url(item_data: Dict[str, Any], children: List[Dict[str, Any]]) -> Tuple[Optional[str], str]:
    for child in children:
        data = child.get("data", {})
        if data.get("itemType") != "attachment" or data.get("linkMode") != "linked_url":
            continue
        url = normalize_whitespace(data.get("url", ""))
        content_type = (data.get("contentType") or "").lower()
        title = (data.get("title") or "").lower()
        if url and (url.lower().endswith(".pdf") or "pdf" in title or "application/pdf" in content_type):
            return url, "existing-linked-url"
    doi = normalize_whitespace(item_data.get("DOI", ""))
    url = normalize_whitespace(item_data.get("url", ""))
    title = normalize_whitespace(item_data.get("title", ""))
    if doi:
        openalex = openalex_pdf_for_doi(doi)
        if openalex:
            return openalex, "openalex"
        crossref = crossref_pdf_for_doi(doi)
        if crossref:
            return crossref, "crossref"
        if "10.1145/" in doi:
            return f"https://dl.acm.org/doi/pdf/{doi}", "acm-doi"
    if title:
        match = query_arxiv_by_title(title)
        if match:
            return f"https://arxiv.org/pdf/{match[0]}.pdf", "arxiv-title"
    if url and url.lower().endswith(".pdf"):
        return url, "item-url"
    return None, "not-found"



def import_real_pdfs_for_collection(
    client: ZoteroClient,
    collection_name: str,
    download_dir: str,
    report_dir: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    run_stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dl_dir = ensure_directory(Path(download_dir) / f"run_{run_stamp}")
    ensure_directory(report_dir)
    report: Dict[str, Any] = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "user_id": client.user_id,
        "collection_name": collection_name,
        "dry_run": bool(dry_run),
        "download_dir": str(dl_dir),
        "imported": [],
        "skipped": [],
        "failures": [],
    }
    collection_key = client.find_collection_key(collection_name)
    if not collection_key:
        raise RuntimeError(f"Collection not found: {collection_name}")
    items = client.get_collection_items(collection_key)
    top_items = [item for item in items if item.get("data", {}).get("itemType") not in {"note", "attachment", "annotation"}]
    for item in top_items:
        item_key = item.get("key")
        data = item.get("data", {})
        title = data.get("title", "<untitled>")
        try:
            children = client.get_children(item_key)
            if any(
                child.get("data", {}).get("linkMode") in {"imported_file", "imported_url"}
                and child.get("key")
                and client.attachment_has_remote_file(child.get("key"))
                for child in children
            ):
                report["skipped"].append({"item_key": item_key, "title": title, "reason": "real pdf attachment already present"})
                continue
            pdf_url, source = pick_pdf_source_url(data, children)
            if not pdf_url:
                report["skipped"].append({"item_key": item_key, "title": title, "reason": f"no pdf source ({source})"})
                continue
            imported = import_real_pdf_for_parent(client, item_key, title, pdf_url, str(dl_dir), dry_run=dry_run)
            imported["source"] = source
            report["imported"].append(imported)
        except Exception as exc:  # noqa: BLE001
            report["failures"].append({"item_key": item_key, "title": title, "error": str(exc)})
    return report
