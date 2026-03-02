from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

from autopaper.models import RunReport
from autopaper.utils import ensure_directory



def render_report(report: RunReport) -> str:
    data = report.to_dict()
    lines: list[str] = []
    lines.append(f"# Daily Research Ingestion Report ({data['timestamp']})")
    lines.append("")
    lines.append(f"Profile: `{data['profile_name']}`")
    lines.append(f"Queries: `{'; '.join(data['queries'])}`")
    lines.append(f"Sources: `{', '.join(data['sources'])}`")
    lines.append(f"Collection: `{data['collection_name']}`")
    lines.append(f"Focus mode: `{data['focus_mode']}`")
    lines.append(f"Candidates considered: `{data['candidate_count']}`")
    lines.append("")

    lines.append("## Scheduler Context")
    scheduler_context = data.get("scheduler_context") or {}
    if not scheduler_context:
        lines.append("- None")
    else:
        for key, value in scheduler_context.items():
            lines.append(f"- {key}: `{value}`")
    lines.append("")

    lines.append("## Source Stats")
    source_stats = data.get("source_stats") or {}
    if not source_stats:
        lines.append("- None")
    else:
        for source, payload in source_stats.items():
            lines.append(f"- {source}: fetched={payload.get('fetched', 0)} failures={payload.get('failures', 0)}")
    lines.append("")

    lines.append("## Summary Providers")
    summary_stats = data.get("summary_provider_stats") or {}
    if not summary_stats:
        lines.append("- None")
    else:
        for provider, count in summary_stats.items():
            lines.append(f"- {provider}: `{count}`")
    lines.append("")

    lines.append("## Added")
    if not data["added"]:
        lines.append("- None")
    for row in data["added"]:
        lines.append(
            f"- {row['title']} ({row['source_id']}) -> Zotero key `{row['zotero_key']}` | "
            f"score={row.get('score')} | summary_provider={row.get('summary_provider')} | "
            f"pdf_sourced={row['pdf_sourced']} | code_links={row['code_links_count']}"
        )
    lines.append("")

    lines.append("## Attention")
    if not data["attention"]:
        lines.append("- None")
    for row in data["attention"]:
        lines.append(f"- {row['title']} ({row['source_id']}): {row['issue']}")
    lines.append("")

    lines.append("## Skipped")
    if not data["skipped"]:
        lines.append("- None")
    for row in data["skipped"]:
        lines.append(f"- {row['title']} ({row['source_id']}) because {row['reason']}")
    lines.append("")

    lines.append("## Failures")
    if not data["failures"]:
        lines.append("- None")
    for row in data["failures"]:
        lines.append(f"- {row['title']} ({row['source_id']}): {row['error']}")
    lines.append("")

    lines.append("## Real PDF Import")
    pdf_import = data.get("pdf_import")
    if not pdf_import:
        lines.append("- Not requested")
    else:
        lines.append(f"- imported={len(pdf_import.get('imported', []))} skipped={len(pdf_import.get('skipped', []))} failures={len(pdf_import.get('failures', []))}")
    return "\n".join(lines).strip() + "\n"



def save_report(report: RunReport, report_root: str) -> Tuple[str, str]:
    report_dir = ensure_directory(Path(report_root) / report.profile_name)
    stamp = report.timestamp.replace(":", "").replace("-", "").replace("+", "_")
    md_path = report_dir / f"daily_ingest_report_{stamp}.md"
    json_path = report_dir / f"daily_ingest_report_{stamp}.json"
    md_path.write_text(render_report(report), encoding="utf-8")
    json_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return str(md_path), str(json_path)
