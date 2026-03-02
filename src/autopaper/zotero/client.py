from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from autopaper.models import PaperRecord
from autopaper.utils import normalize_arxiv_id, normalize_doi, normalize_title, normalize_whitespace

ZOTERO_API_URL = "https://api.zotero.org"
USER_AGENT = "auto-paper-populator/0.3"



def resolve_zotero_user_id(api_key: str, candidate: Optional[str] = None) -> str:
    if candidate and str(candidate).isdigit():
        return str(candidate)
    response = requests.get(
        f"{ZOTERO_API_URL}/keys/current",
        headers={
            "Zotero-API-Key": api_key,
            "Zotero-API-Version": "3",
            "User-Agent": USER_AGENT,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    user_id = payload.get("userID")
    if user_id is None:
        raise RuntimeError("Could not resolve numeric Zotero userID from API key")
    return str(user_id)



def split_author(name: str) -> Dict[str, str]:
    chunks = normalize_whitespace(name).split(" ")
    if len(chunks) <= 1:
        return {"creatorType": "author", "name": chunks[0] if chunks else "Unknown"}
    return {
        "creatorType": "author",
        "firstName": " ".join(chunks[:-1]),
        "lastName": chunks[-1],
    }


class ZoteroClient:
    def __init__(self, api_key: str, user_id: Optional[str] = None) -> None:
        self.api_key = api_key
        self.user_id = resolve_zotero_user_id(api_key, user_id)
        self.base = f"{ZOTERO_API_URL}/users/{self.user_id}"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Zotero-API-Key": api_key,
                "Zotero-API-Version": "3",
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
            }
        )

    def _get_items(self, q: str, qmode: str = "everything", limit: int = 25) -> List[Dict[str, Any]]:
        response = self.session.get(
            f"{self.base}/items",
            params={"q": q, "qmode": qmode, "limit": limit, "format": "json", "include": "data"},
            timeout=45,
        )
        response.raise_for_status()
        return response.json()

    def _post_items(self, payload: List[Dict[str, Any]]) -> Dict[str, Any]:
        response = self.session.post(
            f"{self.base}/items",
            data=json.dumps(payload),
            headers={"Zotero-Write-Token": uuid.uuid4().hex},
            timeout=45,
        )
        response.raise_for_status()
        return response.json()

    def _get_collections(self, limit: int = 200) -> List[Dict[str, Any]]:
        response = self.session.get(
            f"{self.base}/collections",
            params={"format": "json", "include": "data", "limit": limit},
            timeout=45,
        )
        response.raise_for_status()
        return response.json()

    def _post_collections(self, payload: List[Dict[str, Any]]) -> Dict[str, Any]:
        response = self.session.post(
            f"{self.base}/collections",
            data=json.dumps(payload),
            headers={"Zotero-Write-Token": uuid.uuid4().hex},
            timeout=45,
        )
        response.raise_for_status()
        return response.json()

    def get_item(self, item_key: str) -> Dict[str, Any]:
        response = self.session.get(
            f"{self.base}/items/{item_key}",
            params={"format": "json", "include": "data"},
            timeout=45,
        )
        response.raise_for_status()
        return response.json()

    def get_attachment_items(self, limit: int = 100) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        start = 0
        while True:
            response = self.session.get(
                f"{self.base}/items",
                params={
                    "itemType": "attachment",
                    "format": "json",
                    "include": "data",
                    "limit": limit,
                    "start": start,
                },
                timeout=60,
            )
            response.raise_for_status()
            page = response.json()
            if not page:
                break
            items.extend(page)
            start += len(page)
        return items

    def get_children(self, parent_key: str) -> List[Dict[str, Any]]:
        response = self.session.get(
            f"{self.base}/items/{parent_key}/children",
            params={"format": "json", "include": "data", "limit": 100},
            timeout=45,
        )
        response.raise_for_status()
        return response.json()

    def get_collection_items(self, collection_key: str) -> List[Dict[str, Any]]:
        response = self.session.get(
            f"{self.base}/collections/{collection_key}/items",
            params={"format": "json", "include": "data", "limit": 100},
            timeout=45,
        )
        response.raise_for_status()
        return response.json()

    def attachment_has_remote_file(self, attachment_key: str) -> bool:
        response = self.session.get(
            f"{self.base}/items/{attachment_key}/file",
            allow_redirects=False,
            timeout=30,
        )
        if response.status_code in (200, 301, 302):
            return True
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return False

    def download_attachment_to_path(self, attachment_key: str, target_path: str | Path, timeout: int = 180) -> Tuple[bool, int]:
        url = f"{self.base}/items/{attachment_key}/file"
        with self.session.get(url, timeout=timeout, allow_redirects=False) as probe:
            if probe.status_code == 404:
                return False, 0
            probe.raise_for_status()
            location = probe.headers.get("Location")
            if not location:
                raise RuntimeError(f"Missing redirect location while downloading attachment {attachment_key}.")

        path = Path(target_path)
        with requests.get(location, stream=True, timeout=timeout, headers={"User-Agent": USER_AGENT}) as response:
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with path.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    written += len(chunk)
        return True, written

    def download_url_to_path(self, url: str, target_path: str | Path, timeout: int = 180) -> int:
        path = Path(target_path)
        with requests.get(url, stream=True, timeout=timeout, allow_redirects=True, headers={"User-Agent": USER_AGENT}) as response:
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with path.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    written += len(chunk)
        return written

    def delete_item(self, key: str, version: int) -> None:
        response = self.session.delete(
            f"{self.base}/items/{key}",
            headers={
                "Zotero-Write-Token": str(int(time.time() * 1000)),
                "If-Unmodified-Since-Version": str(version),
            },
            timeout=45,
        )
        response.raise_for_status()

    def get_library_version(self) -> str:
        response = self.session.get(
            f"{self.base}/items",
            params={"limit": 1, "format": "json"},
            timeout=30,
        )
        response.raise_for_status()
        return response.headers.get("Last-Modified-Version", "0")

    def empty_trash(self) -> Tuple[bool, str]:
        lib_version = self.get_library_version()
        response = self.session.delete(
            f"{self.base}/items/trash",
            headers={
                "Zotero-Write-Token": str(int(time.time() * 1000)),
                "If-Unmodified-Since-Version": str(lib_version),
            },
            timeout=45,
        )
        if response.status_code in (200, 204):
            return True, "trash emptied"
        return False, f"{response.status_code} {response.text[:200]}"

    def ensure_collection(self, name: str) -> str:
        target = normalize_whitespace(name)
        for coll in self._get_collections(limit=300):
            data = coll.get("data", {})
            existing = normalize_whitespace(data.get("name", ""))
            if existing.lower() == target.lower():
                return coll.get("key", "")
        create_result = self._post_collections([{"name": target}])
        successful = create_result.get("successful", {})
        if "0" not in successful:
            raise RuntimeError(f"Zotero create collection failed: {json.dumps(create_result)}")
        return successful["0"]["key"]

    def find_collection_key(self, collection_name: str) -> Optional[str]:
        target = normalize_whitespace(collection_name).lower()
        for coll in self._get_collections(limit=300):
            data = coll.get("data", {})
            existing = normalize_whitespace(data.get("name", ""))
            if existing.lower() == target:
                return coll.get("key")
        return None

    def dedupe_check(self, paper: PaperRecord) -> Tuple[bool, Optional[str]]:
        paper_title_norm = normalize_title(paper.title)
        if paper.doi:
            doi_norm = normalize_doi(paper.doi)
            for item in self._get_items(paper.doi, qmode="everything", limit=20):
                data = item.get("data", {})
                existing = data.get("DOI")
                if existing and normalize_doi(existing) == doi_norm:
                    return True, f"DOI match with Zotero item {item.get('key')}"
        if paper.source_id:
            source_norm = normalize_arxiv_id(paper.source_id)
            for item in self._get_items(source_norm, qmode="everything", limit=20):
                data = item.get("data", {})
                archive_loc = data.get("archiveLocation") or ""
                url = data.get("url") or ""
                if normalize_arxiv_id(archive_loc) == source_norm:
                    return True, f"Source ID match with Zotero item {item.get('key')}"
                if source_norm and source_norm in normalize_arxiv_id(url):
                    return True, f"Source URL match with Zotero item {item.get('key')}"
        for item in self._get_items(paper.title, qmode="titleCreatorYear", limit=25):
            data = item.get("data", {})
            existing_title = data.get("title", "")
            if existing_title and normalize_title(existing_title) == paper_title_norm:
                return True, f"Title match with Zotero item {item.get('key')}"
        return False, None

    def add_paper(
        self,
        paper: PaperRecord,
        note_html: str,
        tags: List[str],
        collection_key: Optional[str],
        pdf_url: Optional[str],
    ) -> str:
        creators = [split_author(author) for author in paper.authors] or [{"creatorType": "author", "name": "Unknown"}]
        item_type = "preprint" if paper.source.lower() == "arxiv" else "journalArticle"
        payload = [
            {
                "itemType": item_type,
                "title": paper.title,
                "creators": creators,
                "abstractNote": paper.abstract,
                "date": paper.published_at[:10] if paper.published_at else "",
                "DOI": paper.doi or "",
                "url": paper.url,
                "archive": paper.source if paper.source.lower() == "arxiv" else "",
                "archiveLocation": normalize_arxiv_id(paper.source_id) if paper.source_id else "",
                "collections": [collection_key] if collection_key else [],
                "tags": [{"tag": tag} for tag in tags],
                "extra": f"ingestedBy: autopaper\ningestedAt: {paper.raw_metadata.get('ingested_at', '')}",
            }
        ]
        add_result = self._post_items(payload)
        successful = add_result.get("successful", {})
        if "0" not in successful:
            raise RuntimeError(f"Zotero add paper failed: {json.dumps(add_result)}")
        parent_key = successful["0"]["key"]
        if pdf_url:
            self._post_items(
                [
                    {
                        "itemType": "attachment",
                        "parentItem": parent_key,
                        "title": "PDF Source Link",
                        "linkMode": "linked_url",
                        "url": pdf_url,
                        "contentType": "application/pdf",
                        "tags": [{"tag": "auto-sourced"}],
                    }
                ]
            )
        self._post_items([{"itemType": "note", "parentItem": parent_key, "note": note_html}])
        return parent_key

    def create_imported_file_attachment(self, parent_key: str, filename: str, source_url: str) -> str:
        result = self._post_items(
            [
                {
                    "itemType": "attachment",
                    "parentItem": parent_key,
                    "linkMode": "imported_file",
                    "title": "PDF (auto-imported)",
                    "contentType": "application/pdf",
                    "filename": filename,
                    "url": source_url,
                    "tags": [{"tag": "auto-imported"}],
                }
            ]
        )
        successful = result.get("successful", {})
        if "0" not in successful:
            raise RuntimeError(f"Failed to create imported attachment: {json.dumps(result)}")
        return successful["0"]["key"]

    def authorize_upload(self, attachment_key: str, md5_hex: str, filename: str, filesize: int, mtime_ms: int) -> Dict[str, Any]:
        response = self.session.post(
            f"{self.base}/items/{attachment_key}/file",
            headers={"If-None-Match": "*", "Content-Type": "application/x-www-form-urlencoded"},
            data={"md5": md5_hex, "filename": filename, "filesize": str(filesize), "mtime": str(mtime_ms)},
            timeout=45,
        )
        response.raise_for_status()
        return response.json()

    def upload_binary(self, auth_payload: Dict[str, Any], file_bytes: bytes) -> None:
        if auth_payload.get("exists") == 1:
            return
        upload_url = auth_payload.get("url")
        prefix = auth_payload.get("prefix")
        suffix = auth_payload.get("suffix")
        content_type = auth_payload.get("contentType")
        if not upload_url or prefix is None or suffix is None or not content_type:
            raise RuntimeError(f"Unexpected upload auth payload: {json.dumps(auth_payload)}")
        body = prefix.encode("utf-8") + file_bytes + suffix.encode("utf-8")
        response = requests.post(
            upload_url,
            data=body,
            headers={"Content-Type": content_type, "User-Agent": USER_AGENT},
            timeout=300,
        )
        response.raise_for_status()
        if response.status_code != 201:
            raise RuntimeError(f"Unexpected upload status: {response.status_code} {response.text[:200]}")

    def register_upload(self, attachment_key: str, upload_key: str) -> None:
        response = self.session.post(
            f"{self.base}/items/{attachment_key}/file",
            headers={"If-None-Match": "*", "Content-Type": "application/x-www-form-urlencoded"},
            data={"upload": upload_key},
            timeout=45,
        )
        response.raise_for_status()
        if response.status_code != 204:
            raise RuntimeError(f"Unexpected register status: {response.status_code} {response.text[:200]}")
