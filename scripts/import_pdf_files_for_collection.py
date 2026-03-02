#!/usr/bin/env python3
"""Legacy wrapper for real PDF file import using the packaged Zotero helpers."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from autopaper.utils import load_env_file
from autopaper.zotero import ZoteroClient
from autopaper.zotero.pdf_import import import_real_pdfs_for_collection



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import real PDF files for items in a Zotero collection")
    parser.add_argument("--env-file", default=None, help="Path to .env file")
    parser.add_argument("--collection-name", default="autopaper-ingested", help="Collection name")
    parser.add_argument("--zotero-user-id", default=None, help="Override ZOTERO_USER_ID")
    parser.add_argument("--zotero-api-key", default=None, help="Override ZOTERO_API_KEY")
    parser.add_argument("--download-dir", default="local_backups/collection_pdf_imports", help="Local download dir")
    parser.add_argument("--report-dir", default="reports", help="Report dir")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    load_env_file(args.env_file)
    api_key = args.zotero_api_key or os.getenv("ZOTERO_API_KEY")
    user_id = args.zotero_user_id or os.getenv("ZOTERO_USER_ID")
    if not api_key:
        print("Missing ZOTERO_API_KEY", file=sys.stderr)
        raise SystemExit(1)
    client = ZoteroClient(api_key=api_key, user_id=user_id)
    report = import_real_pdfs_for_collection(
        client=client,
        collection_name=args.collection_name,
        download_dir=args.download_dir,
        report_dir=args.report_dir,
        dry_run=args.dry_run,
    )
    stamp = report["timestamp"].replace(":", "").replace("-", "")
    report_path = Path(args.report_dir) / f"import_pdf_files_report_{stamp}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Report saved to: {report_path}")
    raise SystemExit(0 if not report["failures"] else 1)
