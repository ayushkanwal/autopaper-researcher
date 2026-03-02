from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from autopaper.config import RuntimeConfig, config_as_json
from autopaper.models import PaperRecord, RunReport, SummaryOutcome
from autopaper.ranking import filter_and_rank, merge_candidates
from autopaper.reports import save_report
from autopaper.state import StateStore
from autopaper.summaries.base import SummaryProviderError, build_summarizer, build_summarizer_by_name
from autopaper.summaries.offline import OfflineSummarizer
from autopaper.utils import (
    extract_urls,
    normalize_arxiv_id,
    normalize_title,
    now_utc,
    title_tokens,
    unique_preserve_order,
)
from autopaper.zotero.client import ZoteroClient
from autopaper.zotero.notes import render_note_html
from autopaper.zotero.pdf_import import import_real_pdf_for_parent
from autopaper.zotero.pdf_sourcing import source_pdf_url
from autopaper.sources import ArxivSource, OpenAlexSource, PubMedSource

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
CODE_HOST_MARKERS = ["github.com", "gitlab.com", "huggingface.co", "bitbucket.org"]
USER_AGENT = "auto-paper-populator/0.3"



def _build_sources(config: RuntimeConfig) -> Dict[str, Any]:
    adapters: Dict[str, Any] = {}
    if "arxiv" in config.sources:
        adapters["arxiv"] = ArxivSource()
    if "openalex" in config.sources:
        adapters["openalex"] = OpenAlexSource(mailto=config.openalex_mailto)
    if "pubmed" in config.sources:
        adapters["pubmed"] = PubMedSource(email=config.pubmed_email, api_key=config.pubmed_api_key)
    return adapters



def _github_repo_from_title(title: str, source_id: str, token: Optional[str]) -> Optional[str]:
    alias = title.split(":", 1)[0].strip()
    queries: List[str] = []
    if source_id:
        queries.append(source_id)
    if alias and 6 <= len(alias) <= 30:
        queries.append(alias)
    queries.append(f'"{title}"')
    tokens = title_tokens(title)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for query in queries:
        response = requests.get(
            GITHUB_SEARCH_URL,
            params={"q": query, "sort": "stars", "order": "desc", "per_page": 5},
            headers=headers,
            timeout=25,
        )
        if response.status_code != 200:
            continue
        payload = response.json()
        for item in payload.get("items", []):
            full_name = (item.get("full_name") or "").lower()
            desc = (item.get("description") or "").lower()
            repo_text = f"{full_name} {desc}"
            overlap = sum(1 for token_value in tokens if token_value in repo_text)
            score = 0
            if source_id and source_id in desc:
                score += 3
            if alias and len(alias) >= 6 and alias.lower() in full_name:
                score += 2
            if overlap >= 2:
                score += 2
            if "time series" in desc:
                score += 1
            if score >= 3 and item.get("html_url"):
                return item["html_url"]
    return None



def discover_code_links(paper: PaperRecord, enable_github_search: bool, github_token: Optional[str]) -> List[str]:
    metadata_text = "\n".join(str(value) for value in paper.raw_metadata.values() if isinstance(value, str))
    urls = extract_urls(f"{paper.abstract}\n{metadata_text}")
    links = [url for url in urls if any(marker in url.lower() for marker in CODE_HOST_MARKERS)]
    if not links and enable_github_search:
        maybe = _github_repo_from_title(paper.title, normalize_arxiv_id(paper.source_id), github_token)
        if maybe:
            links.append(maybe)
    return unique_preserve_order(links)[:5]



def _summarize_with_fallback(paper: PaperRecord, config: RuntimeConfig) -> SummaryOutcome:
    primary = build_summarizer(config)
    try:
        payload = primary.summarize(paper, config)
        return SummaryOutcome(payload=payload, provider=primary.name)
    except Exception as exc:  # noqa: BLE001
        if config.summary_fallback == config.summarizer:
            raise SummaryProviderError(str(exc)) from exc
        fallback = OfflineSummarizer() if config.summary_fallback == "offline" else build_summarizer_by_name(config.summary_fallback)
        payload = fallback.summarize(paper, config)
        return SummaryOutcome(payload=payload, provider=fallback.name, fallback_used=True, provider_error=str(exc))



def _tags_for_paper(paper: PaperRecord, profile_name: str, summary: SummaryOutcome, pdf_url: Optional[str], code_links: List[str]) -> List[str]:
    publication_year = paper.published_at[:4] if paper.published_at else str(now_utc().year)
    tags = set(paper.keywords)
    tags.update(
        {
            publication_year,
            "time-series",
            "auto-ingested",
            "detailed-summary",
            f"profile:{profile_name}",
            f"summary-provider:{summary.provider}",
            "code-found" if code_links else "code-not-found",
            "pdf-sourced" if pdf_url else "pdf-unsourced",
        }
    )
    if summary.fallback_used:
        tags.add("summary-fallback")
    return sorted(tags)



def execute_run(config: RuntimeConfig, logger: Optional[logging.Logger] = None, scheduler_context: Optional[Dict[str, Any]] = None) -> RunReport:
    logger = logger or logging.getLogger("autopaper")
    state = StateStore(config.state_dir)
    started_at = now_utc().isoformat()
    scheduler_context = scheduler_context or {"mode": "run-once"}
    state.capture_config_snapshot(config.profile_name, started_at, config_as_json(config))
    run_id = state.start_run(config.profile_name, started_at, scheduler_context)

    report = RunReport(
        timestamp=started_at,
        profile_name=config.profile_name,
        queries=config.queries,
        sources=config.sources,
        collection_name=config.collection_name,
        focus_mode=config.query_preset,
        candidate_count=0,
        scheduler_context=scheduler_context,
        source_stats={source: {"fetched": 0, "failures": 0} for source in config.sources},
        summary_provider_stats={},
    )

    client: Optional[ZoteroClient] = None
    if not config.dry_run:
        client = ZoteroClient(api_key=config.zotero_api_key or "", user_id=config.zotero_user_id)
    collection_key = client.ensure_collection(config.collection_name) if client else None

    try:
        adapters = _build_sources(config)
        fetched: List[PaperRecord] = []
        for query in config.queries:
            for source_name, adapter in adapters.items():
                try:
                    papers = adapter.search(query=query, max_results=config.max_results_per_query)
                    report.source_stats[source_name]["fetched"] += len(papers)
                    fetched.extend(papers)
                except Exception as exc:  # noqa: BLE001
                    report.source_stats[source_name]["failures"] += 1
                    issue = f"Source {source_name} failed for query '{query}': {exc}"
                    report.attention.append({"title": source_name, "source_id": "<source>", "issue": issue})
                    state.record_event(run_id, now_utc().isoformat(), "WARNING", issue)

        candidates = merge_candidates(fetched)
        report.candidate_count = len(candidates)
        ranked_candidates = filter_and_rank(candidates, config)

        added_item_keys: List[Dict[str, str]] = []
        for ranked in ranked_candidates:
            if len(report.added) >= config.max_new:
                break
            paper = ranked.paper
            try:
                duplicate = False
                reason = None
                if client:
                    duplicate, reason = client.dedupe_check(paper)
                if duplicate:
                    report.skipped.append({"title": paper.title, "source_id": paper.source_id, "reason": reason or "duplicate"})
                    state.remember_paper(
                        config.profile_name,
                        paper.source,
                        paper.source_id,
                        paper.doi,
                        normalize_title(paper.title),
                        now_utc().isoformat(),
                        None,
                        "duplicate",
                    )
                    continue

                summary_outcome = _summarize_with_fallback(paper, config)
                report.summary_provider_stats[summary_outcome.provider] = report.summary_provider_stats.get(summary_outcome.provider, 0) + 1
                pdf_url, pdf_status = source_pdf_url(paper)
                code_links = discover_code_links(paper, config.enable_github_search, config.github_token)
                paper.raw_metadata["ingested_at"] = now_utc().isoformat()
                note_html = render_note_html(
                    paper=paper,
                    summary=summary_outcome,
                    pdf_url=pdf_url,
                    pdf_status=pdf_status,
                    code_links=code_links,
                    config=config,
                    ranked=ranked,
                )
                tags = _tags_for_paper(paper, config.profile_name, summary_outcome, pdf_url, code_links)
                if config.dry_run:
                    zotero_key = "<dry-run>"
                else:
                    zotero_key = client.add_paper(
                        paper=paper,
                        note_html=note_html,
                        tags=tags,
                        collection_key=collection_key,
                        pdf_url=pdf_url,
                    )
                report.added.append(
                    {
                        "title": paper.title,
                        "source_id": paper.source_id,
                        "zotero_key": zotero_key,
                        "pdf_sourced": bool(pdf_url),
                        "pdf_source": pdf_status,
                        "code_links_count": len(code_links),
                        "code_links": code_links,
                        "summary_provider": summary_outcome.provider,
                        "summary_fallback_used": summary_outcome.fallback_used,
                        "score": ranked.score,
                        "matched_reasons": ranked.matched_reasons,
                        "source": paper.source,
                    }
                )
                if not pdf_url:
                    report.attention.append({"title": paper.title, "source_id": paper.source_id, "issue": f"PDF could not be auto-sourced ({pdf_status})"})
                if not code_links:
                    report.attention.append({"title": paper.title, "source_id": paper.source_id, "issue": "No code/implementation link found automatically"})
                if summary_outcome.fallback_used:
                    report.attention.append({"title": paper.title, "source_id": paper.source_id, "issue": f"Summary provider fallback used: {summary_outcome.provider_error}"})
                state.remember_paper(
                    config.profile_name,
                    paper.source,
                    paper.source_id,
                    paper.doi,
                    normalize_title(paper.title),
                    now_utc().isoformat(),
                    zotero_key if zotero_key != "<dry-run>" else None,
                    "added",
                )
                if config.attach_real_pdfs and client and pdf_url and zotero_key != "<dry-run>":
                    added_item_keys.append({"key": zotero_key, "title": paper.title, "pdf_url": pdf_url})
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed processing paper %s", paper.title)
                report.failures.append({"title": paper.title, "source_id": paper.source_id, "error": str(exc)})
                state.record_event(run_id, now_utc().isoformat(), "ERROR", f"Paper failure: {paper.title}", {"error": str(exc)})

        if config.attach_real_pdfs:
            pdf_import = {"imported": [], "skipped": [], "failures": []}
            if config.dry_run:
                pdf_import["skipped"].append({"item_key": "<dry-run>", "title": "<dry-run>", "reason": "real PDF import disabled in dry-run"})
            elif client:
                for item in added_item_keys:
                    try:
                        imported = import_real_pdf_for_parent(
                            client,
                            parent_key=item["key"],
                            title=item["title"],
                            pdf_url=item["pdf_url"],
                            download_dir=str(config.state_path() / "downloads" / config.profile_name),
                            dry_run=False,
                        )
                        pdf_import["imported"].append(imported)
                    except Exception as exc:  # noqa: BLE001
                        pdf_import["failures"].append({"item_key": item["key"], "title": item["title"], "error": str(exc)})
                        report.attention.append({"title": item["title"], "source_id": item["key"], "issue": f"Real PDF import failed: {exc}"})
            report.pdf_import = pdf_import

    except Exception as exc:  # noqa: BLE001
        logger.exception("Global run failure")
        report.failures.append({"title": "<global>", "source_id": "<global>", "error": str(exc)})
        state.record_event(run_id, now_utc().isoformat(), "ERROR", "Global run failure", {"error": str(exc)})

    md_path, json_path = save_report(report, config.report_dir)
    finished_at = now_utc().isoformat()
    status = "ok" if not report.failures else "failed"
    state.finish_run(
        run_id,
        finished_at,
        status,
        added_count=len(report.added),
        skipped_count=len(report.skipped),
        failure_count=len(report.failures),
        report_md_path=md_path,
        report_json_path=json_path,
    )
    logger.info("Run finished status=%s added=%s skipped=%s failures=%s", status, len(report.added), len(report.skipped), len(report.failures))
    return report
