#!/usr/bin/env python3
"""Legacy wrapper that maps the old latest-paper command onto the packaged CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from autopaper.cli import main



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch one latest relevant paper and ingest it")
    parser.add_argument("--env-file", default=None, help="Path to .env file")
    parser.add_argument("--profile-name", default=None, help="Profile name")
    parser.add_argument("--query-preset", default=None, help="Query preset name")
    parser.add_argument("--query", action="append", dest="queries", help="Extra query (repeatable)")
    parser.add_argument("--source", action="append", dest="sources", help="Source adapter (repeatable)")
    parser.add_argument("--max-results", type=int, default=None, help="Maximum results per query")
    parser.add_argument("--min-relevance-score", type=int, default=None, help="Minimum relevance score")
    parser.add_argument("--collection-name", default=None, help="Target Zotero collection")
    parser.add_argument("--report-dir", default=None, help="Report directory")
    parser.add_argument("--state-dir", default=None, help="State directory")
    parser.add_argument("--timezone", default=None, help="Timezone override")
    parser.add_argument("--attach-real-pdfs", action="store_true", help="Import real PDF files")
    parser.add_argument("--no-github-search", action="store_true", help="Disable GitHub repo search")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to Zotero")
    parser.add_argument("--zotero-user-id", default=None, help="Override ZOTERO_USER_ID")
    parser.add_argument("--zotero-api-key", default=None, help="Override ZOTERO_API_KEY")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    argv = ["run-once", "--max-new", "1"]
    if args.env_file:
        argv.extend(["--env-file", args.env_file])
    if args.profile_name:
        argv.extend(["--profile-name", args.profile_name])
    if args.query_preset:
        argv.extend(["--query-preset", args.query_preset])
    for query in args.queries or []:
        argv.extend(["--query", query])
    for source in args.sources or []:
        argv.extend(["--source", source])
    if args.max_results is not None:
        argv.extend(["--max-results-per-query", str(args.max_results)])
    if args.min_relevance_score is not None:
        argv.extend(["--min-relevance-score", str(args.min_relevance_score)])
    if args.collection_name:
        argv.extend(["--collection-name", args.collection_name])
    if args.report_dir:
        argv.extend(["--report-dir", args.report_dir])
    if args.state_dir:
        argv.extend(["--state-dir", args.state_dir])
    if args.timezone:
        argv.extend(["--timezone", args.timezone])
    if args.attach_real_pdfs:
        argv.append("--attach-real-pdfs")
    if args.no_github_search:
        argv.append("--no-github-search")
    if args.dry_run:
        argv.append("--dry-run")
    if args.zotero_user_id:
        argv.extend(["--zotero-user-id", args.zotero_user_id])
    if args.zotero_api_key:
        argv.extend(["--zotero-api-key", args.zotero_api_key])
    raise SystemExit(main(argv))
