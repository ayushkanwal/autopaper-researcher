from __future__ import annotations

import html
from typing import List, Optional

from autopaper.config import RuntimeConfig
from autopaper.models import PaperRecord, RankedPaper, SummaryOutcome



def render_note_html(
    paper: PaperRecord,
    summary: SummaryOutcome,
    pdf_url: Optional[str],
    pdf_status: str,
    code_links: List[str],
    config: RuntimeConfig,
    ranked: RankedPaper,
) -> str:
    def esc(text: str) -> str:
        return html.escape(text or "")

    payload = summary.payload
    bullets_html = "".join(f"<li>{esc(line)}</li>" for line in payload.five_bullet_summary)
    deeper_html = "".join(f"<li>{esc(line)}</li>" for line in payload.deeper_breakdown)
    repl_html = "".join(f"<li>{esc(line)}</li>" for line in payload.replication_checklist)
    confidence_html = "".join(f"<li>{esc(line)}</li>" for line in payload.confidence_notes)
    code_html = "<li>None found in metadata/search.</li>"
    if code_links:
        code_html = "".join(f"<li><a href=\"{esc(link)}\">{esc(link)}</a></li>" for link in code_links)
    source_line = f"Available ({esc(pdf_status)}): <a href=\"{esc(pdf_url or '')}\">PDF</a>" if pdf_url else f"Not found ({esc(pdf_status)})"
    matched_query = paper.raw_metadata.get("matched_query", "")
    provider_line = summary.provider + (" (fallback used)" if summary.fallback_used else "")
    fallback_detail = f"<p><b>Summary Provider Error:</b> {esc(summary.provider_error or '')}</p>" if summary.provider_error else ""
    reasons_html = "".join(f"<li>{esc(reason)}</li>" for reason in ranked.matched_reasons)

    return (
        "<h1>Structured Summary (Detailed)</h1>"
        f"<p><b>Paper:</b> {esc(paper.title)}</p>"
        f"<p><b>Source:</b> {esc(paper.source)} ({esc(paper.source_id)})</p>"
        f"<p><b>Published:</b> {esc(paper.published_at)}</p>"
        f"<p><b>Collection:</b> {esc(config.collection_name)}</p>"
        f"<p><b>Summary Provider:</b> {esc(provider_line)}</p>"
        f"{fallback_detail}"
        f"<p><b>Search Provenance:</b> {esc(paper.source)} query match: {esc(str(matched_query))}</p>"
        f"<p><b>Ranking Score:</b> {ranked.score}</p>"
        "<h2>Matched Reasons</h2>"
        f"<ul>{reasons_html or '<li>No specific reasons captured.</li>'}</ul>"
        "<h2>5-Bullet Summary</h2>"
        f"<ul>{bullets_html}</ul>"
        "<h2>In-Depth Breakdown</h2>"
        f"<ul>{deeper_html or '<li>Abstract does not provide enough detail.</li>'}</ul>"
        f"<p><b>Research Question:</b> {esc(payload.research_question)}</p>"
        f"<p><b>Method:</b> {esc(payload.method)}</p>"
        f"<p><b>Dataset:</b> {esc(payload.dataset)}</p>"
        f"<p><b>Metrics:</b> {esc(payload.metrics)}</p>"
        f"<p><b>Key Findings:</b> {esc(payload.key_findings)}</p>"
        f"<p><b>Limitations:</b> {esc(payload.limitations)}</p>"
        f"<p><b>Practical Relevance:</b> {esc(payload.practical_relevance)}</p>"
        "<h2>Reproducibility Checklist</h2>"
        f"<ul>{repl_html}</ul>"
        "<h2>Confidence Notes</h2>"
        f"<ul>{confidence_html}</ul>"
        "<h2>Resources</h2>"
        f"<p><b>Paper URL:</b> <a href=\"{esc(paper.url)}\">{esc(paper.url)}</a></p>"
        f"<p><b>PDF Source Status:</b> {source_line}</p>"
        "<p><b>Code / Implementation Links:</b></p>"
        f"<ul>{code_html}</ul>"
        "<h2>Action Note</h2>"
        + (
            "<p>PDF source could not be auto-resolved. Manual sourcing needed.</p>"
            if not pdf_url
            else "<p>PDF source was auto-resolved and attached as a link.</p>"
        )
    )
