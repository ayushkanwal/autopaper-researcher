from __future__ import annotations

import datetime as dt
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from autopaper.utils import ensure_directory, normalize_whitespace
from autopaper.zotero.client import ZoteroClient

DEFAULT_ATTACHMENT_MODES = ("imported_file", "imported_url")


@dataclass
class CleanupCredentials:
    user_id: Optional[str]
    api_key: str


@dataclass
class BackupAttachmentsConfig:
    credentials: CleanupCredentials
    modes: List[str]
    backup_root: str
    report_dir: str
    limit: int = 0
    backup_from_item_url_on_missing_file: bool = False
    delete_remote: bool = False
    delete_when_no_remote_file: bool = False
    dry_run: bool = False


@dataclass
class PurgeAttachmentsConfig:
    credentials: CleanupCredentials
    modes: List[str]
    zotero_storage_dir: str
    report_dir: str
    dry_run: bool = False
    confirm_my_library: bool = False


def safe_filename(value: str, fallback: str = "file") -> str:
    import re

    value = normalize_whitespace(value)
    if not value:
        value = fallback
    value = re.sub(r"[\\/:*?\"<>|]", "_", value)
    value = value.strip(" .")
    return value[:180] or fallback


def guess_ext(content_type: str) -> str:
    ct = (content_type or "").lower()
    if "pdf" in ct:
        return ".pdf"
    if "html" in ct:
        return ".html"
    if "json" in ct:
        return ".json"
    if "xml" in ct:
        return ".xml"
    if "plain" in ct:
        return ".txt"
    return ""


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def render_backup_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Zotero Backup/Cleanup Report ({report['timestamp']})")
    lines.append("")
    lines.append(f"- User ID: `{report['user_id']}`")
    lines.append(f"- Modes: `{', '.join(report['modes'])}`")
    lines.append(f"- Backup dir: `{report['backup_dir']}`")
    lines.append(f"- Delete remote: `{report['delete_remote']}`")
    lines.append(f"- Dry run: `{report['dry_run']}`")
    lines.append("")
    lines.append("## Totals")
    lines.append(f"- Attachment items scanned: `{report['totals']['scanned']}`")
    lines.append(f"- Targeted for backup: `{report['totals']['targeted']}`")
    lines.append(f"- Backed up: `{report['totals']['backed_up']}`")
    lines.append(f"- Zotero files found: `{report['totals']['remote_file_found']}`")
    lines.append(f"- Zotero files missing: `{report['totals']['remote_file_missing']}`")
    lines.append(f"- Backed up from item URL fallback: `{report['totals']['backed_up_from_item_url']}`")
    lines.append(f"- Backup failures: `{report['totals']['backup_failed']}`")
    lines.append(f"- Deleted remote: `{report['totals']['deleted']}`")
    lines.append(f"- Delete failures: `{report['totals']['delete_failed']}`")
    lines.append(f"- Bytes downloaded: `{report['totals']['bytes_downloaded']}`")
    lines.append("")
    lines.append("## Mode Breakdown")
    for mode, count in sorted(report["mode_counts"].items()):
        lines.append(f"- {mode}: `{count}`")
    lines.append("")
    lines.append("## Failures")
    failures = report.get("failures", [])
    if not failures:
        lines.append("- None")
    else:
        for row in failures[:30]:
            lines.append(f"- `{row['stage']}` {row['attachment_key']}: {row['error']}")
        if len(failures) > 30:
            lines.append(f"- ... and {len(failures) - 30} more")
    lines.append("")
    lines.append("## Sample")
    sample = report.get("sample", [])
    if not sample:
        lines.append("- None")
    else:
        for row in sample[:20]:
            lines.append(f"- `{row['attachment_key']}` `{row['link_mode']}` `{row['content_type']}` -> `{row['local_path']}`")
    return "\n".join(lines).strip() + "\n"


def render_purge_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# My Library Attachment Purge Report ({report['timestamp']})")
    lines.append("")
    lines.append(f"- User ID: `{report['user_id']}`")
    lines.append(f"- Modes: `{', '.join(report['modes'])}`")
    lines.append(f"- Local storage dir: `{report['storage_dir']}`")
    lines.append(f"- Dry run: `{report['dry_run']}`")
    lines.append("")
    t = report["totals"]
    lines.append("## Totals")
    lines.append(f"- Attachments scanned in My Library: `{t['scanned']}`")
    lines.append(f"- Attachments targeted: `{t['targeted']}`")
    lines.append(f"- Remote deleted: `{t['remote_deleted']}`")
    lines.append(f"- Remote delete failed: `{t['remote_delete_failed']}`")
    lines.append(f"- Local storage dirs removed: `{t['local_dirs_removed']}`")
    lines.append(f"- Local storage dirs missing: `{t['local_dirs_missing']}`")
    lines.append(f"- Local delete failed: `{t['local_delete_failed']}`")
    lines.append(f"- Trash empty attempted: `{report['trash']['attempted']}`")
    lines.append(f"- Trash empty success: `{report['trash']['success']}`")
    lines.append(f"- Trash empty detail: `{report['trash']['detail']}`")
    lines.append("")
    lines.append("## Failures")
    if not report["failures"]:
        lines.append("- None")
    else:
        for row in report["failures"][:50]:
            lines.append(f"- `{row['stage']}` `{row['key']}`: {row['error']}")
        if len(report["failures"]) > 50:
            lines.append(f"- ... and {len(report['failures']) - 50} more")
    return "\n".join(lines).strip() + "\n"


def backup_attachments(config: BackupAttachmentsConfig) -> Tuple[Dict[str, Any], int]:
    client = ZoteroClient(api_key=config.credentials.api_key, user_id=config.credentials.user_id)

    run_stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(config.backup_root) / f"run_{run_stamp}"
    report_dir = ensure_directory(config.report_dir)

    report: Dict[str, Any] = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "user_id": client.user_id,
        "modes": config.modes,
        "backup_dir": str(backup_dir),
        "delete_remote": bool(config.delete_remote),
        "dry_run": bool(config.dry_run),
        "mode_counts": {},
        "totals": {
            "scanned": 0,
            "targeted": 0,
            "backed_up": 0,
            "remote_file_found": 0,
            "remote_file_missing": 0,
            "backed_up_from_item_url": 0,
            "backup_failed": 0,
            "deleted": 0,
            "delete_failed": 0,
            "bytes_downloaded": 0,
        },
        "sample": [],
        "failures": [],
        "manifest_path": "",
        "report_path": "",
        "report_json_path": "",
    }

    attachments = client.get_attachment_items(limit=100)
    report["totals"]["scanned"] = len(attachments)
    targeted: List[Dict[str, Any]] = []
    for item in attachments:
        data = item.get("data", {})
        mode = (data.get("linkMode") or "").strip()
        report["mode_counts"][mode] = report["mode_counts"].get(mode, 0) + 1
        if mode in config.modes:
            targeted.append(item)
    if config.limit and config.limit > 0:
        targeted = targeted[: config.limit]
    report["totals"]["targeted"] = len(targeted)

    parent_cache: Dict[str, Dict[str, Any]] = {}
    backed_up_keys: List[str] = []
    manifest_rows: List[Dict[str, Any]] = []

    for item in targeted:
        key = item.get("key", "")
        data = item.get("data", {})
        parent_key = data.get("parentItem") or ""
        parent_title = ""
        if parent_key:
            if parent_key not in parent_cache:
                try:
                    parent_cache[parent_key] = client.get_item(parent_key)
                except Exception as exc:  # noqa: BLE001
                    parent_cache[parent_key] = {"data": {"title": ""}}
                    report["failures"].append({"stage": "parent_fetch", "attachment_key": key, "error": str(exc)})
            parent_title = normalize_whitespace(parent_cache.get(parent_key, {}).get("data", {}).get("title", ""))

        link_mode = data.get("linkMode", "")
        content_type = data.get("contentType", "")
        original_name = data.get("filename") or data.get("title") or key
        base_name = safe_filename(original_name, fallback=key)
        ext = Path(base_name).suffix or guess_ext(content_type)
        if ext and not base_name.lower().endswith(ext.lower()):
            base_name = f"{base_name}{ext}"
        folder_name = safe_filename(parent_title, fallback=f"parent_{parent_key or 'unknown'}")
        local_path = backup_dir / folder_name / f"{key}_{base_name}"

        row: Dict[str, Any] = {
            "attachment_key": key,
            "attachment_version": item.get("version", data.get("version", 0)),
            "parent_key": parent_key,
            "parent_title": parent_title,
            "link_mode": link_mode,
            "content_type": content_type,
            "title": data.get("title", ""),
            "url": data.get("url", ""),
            "local_path": str(local_path),
            "backup_ok": False,
            "backup_source": "",
            "remote_file_available": False,
            "bytes": 0,
            "deleted": False,
        }

        if config.dry_run:
            row["backup_ok"] = True
            manifest_rows.append(row)
            report["totals"]["backed_up"] += 1
            backed_up_keys.append(key)
            if len(report["sample"]) < 20:
                report["sample"].append(row)
            continue

        try:
            has_remote_file, size = client.download_attachment_to_path(key, local_path)
            row["remote_file_available"] = has_remote_file
            if has_remote_file:
                row["backup_ok"] = True
                row["backup_source"] = "zotero_file"
                row["bytes"] = size
                report["totals"]["remote_file_found"] += 1
                report["totals"]["backed_up"] += 1
                report["totals"]["bytes_downloaded"] += size
                backed_up_keys.append(key)
            else:
                report["totals"]["remote_file_missing"] += 1
                fallback_url = (data.get("url") or "").strip()
                if config.backup_from_item_url_on_missing_file and fallback_url:
                    fallback_size = client.download_url_to_path(fallback_url, local_path)
                    row["backup_ok"] = True
                    row["backup_source"] = "item_url"
                    row["bytes"] = fallback_size
                    report["totals"]["backed_up_from_item_url"] += 1
                    report["totals"]["backed_up"] += 1
                    report["totals"]["bytes_downloaded"] += fallback_size
                    backed_up_keys.append(key)
        except Exception as exc:  # noqa: BLE001
            report["totals"]["backup_failed"] += 1
            row["backup_error"] = str(exc)
            report["failures"].append({"stage": "backup", "attachment_key": key, "error": str(exc)})

        manifest_rows.append(row)
        if len(report["sample"]) < 20:
            report["sample"].append(row)

    if config.delete_remote and not config.dry_run:
        for row in manifest_rows:
            key = row["attachment_key"]
            version = int(row.get("attachment_version") or 0)
            if key not in backed_up_keys:
                continue
            if not row.get("remote_file_available") and not config.delete_when_no_remote_file:
                continue
            try:
                client.delete_item(key, version=version)
                row["deleted"] = True
                report["totals"]["deleted"] += 1
            except Exception as exc:  # noqa: BLE001
                report["totals"]["delete_failed"] += 1
                row["delete_error"] = str(exc)
                report["failures"].append({"stage": "delete", "attachment_key": key, "error": str(exc)})

    manifest = {
        "run": {
            "timestamp": report["timestamp"],
            "user_id": report["user_id"],
            "modes": report["modes"],
            "delete_remote": report["delete_remote"],
            "dry_run": report["dry_run"],
            "backup_dir": report["backup_dir"],
        },
        "items": manifest_rows,
    }

    if not config.dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = backup_dir / "manifest.json"
    else:
        manifest_path = Path(report_dir) / f"zotero_backup_manifest_dryrun_{run_stamp}.json"
    _write_json(manifest_path, manifest)
    report["manifest_path"] = str(manifest_path)

    report_path = Path(report_dir) / f"zotero_backup_cleanup_report_{run_stamp}.md"
    report_json_path = Path(report_dir) / f"zotero_backup_cleanup_report_{run_stamp}.json"
    report["report_path"] = str(report_path)
    report["report_json_path"] = str(report_json_path)
    report_path.write_text(render_backup_report(report), encoding="utf-8")
    report_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    exit_code = 1 if report["totals"]["backup_failed"] > 0 or report["totals"]["delete_failed"] > 0 else 0
    return report, exit_code


def purge_attachments(config: PurgeAttachmentsConfig) -> Tuple[Dict[str, Any], int]:
    if not config.dry_run and not config.confirm_my_library:
        raise ValueError("Refusing to purge without explicit confirmation. Pass --confirm-my-library or use --dry-run.")

    client = ZoteroClient(api_key=config.credentials.api_key, user_id=config.credentials.user_id)
    storage_dir = Path(config.zotero_storage_dir).expanduser()
    report: Dict[str, Any] = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "user_id": client.user_id,
        "modes": config.modes,
        "storage_dir": str(storage_dir),
        "dry_run": bool(config.dry_run),
        "totals": {
            "scanned": 0,
            "targeted": 0,
            "remote_deleted": 0,
            "remote_delete_failed": 0,
            "local_dirs_removed": 0,
            "local_dirs_missing": 0,
            "local_delete_failed": 0,
        },
        "trash": {"attempted": False, "success": False, "detail": "not attempted"},
        "failures": [],
        "report_path": "",
        "report_json_path": "",
    }

    all_attachments = client.get_attachment_items(limit=100)
    report["totals"]["scanned"] = len(all_attachments)
    targeted = [item for item in all_attachments if (item.get("data", {}).get("linkMode") or "").strip() in config.modes]
    report["totals"]["targeted"] = len(targeted)

    for item in targeted:
        key = item.get("key", "")
        version = int(item.get("version", item.get("data", {}).get("version", 0)) or 0)
        if config.dry_run:
            continue
        try:
            client.delete_item(key, version=version)
            report["totals"]["remote_deleted"] += 1
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 412:
                try:
                    fresh = client.get_item(key)
                    fresh_version = int(fresh.get("version", fresh.get("data", {}).get("version", 0)) or 0)
                    client.delete_item(key, version=fresh_version)
                    report["totals"]["remote_deleted"] += 1
                    continue
                except Exception as retry_exc:  # noqa: BLE001
                    report["totals"]["remote_delete_failed"] += 1
                    report["failures"].append({"stage": "remote_delete_retry", "key": key, "error": str(retry_exc)})
                    continue
            report["totals"]["remote_delete_failed"] += 1
            report["failures"].append({"stage": "remote_delete", "key": key, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            report["totals"]["remote_delete_failed"] += 1
            report["failures"].append({"stage": "remote_delete", "key": key, "error": str(exc)})

    if not config.dry_run:
        report["trash"]["attempted"] = True
        ok, detail = client.empty_trash()
        report["trash"]["success"] = ok
        report["trash"]["detail"] = detail

    for item in targeted:
        key = (item.get("key") or "").strip()
        if not key or config.dry_run:
            continue
        dir_path = storage_dir / key
        if not dir_path.exists():
            report["totals"]["local_dirs_missing"] += 1
            continue
        try:
            shutil.rmtree(dir_path)
            report["totals"]["local_dirs_removed"] += 1
        except Exception as exc:  # noqa: BLE001
            report["totals"]["local_delete_failed"] += 1
            report["failures"].append({"stage": "local_delete", "key": key, "error": str(exc)})

    report_dir = ensure_directory(config.report_dir)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(report_dir) / f"purge_my_library_attachments_{stamp}.md"
    report_json_path = Path(report_dir) / f"purge_my_library_attachments_{stamp}.json"
    report["report_path"] = str(report_path)
    report["report_json_path"] = str(report_json_path)
    report_path.write_text(render_purge_report(report), encoding="utf-8")
    report_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    exit_code = 1 if report["totals"]["remote_delete_failed"] > 0 or report["totals"]["local_delete_failed"] > 0 else 0
    return report, exit_code
