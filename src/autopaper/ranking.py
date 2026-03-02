from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from autopaper.config import RuntimeConfig
from autopaper.models import PaperRecord, RankedPaper
from autopaper.utils import normalize_title, now_utc, parse_iso_datetime, stable_fingerprint, unique_preserve_order

METHOD_TERMS = [
    "time series",
    "timeseries",
    "forecast",
    "prediction",
    "analysis",
    "reasoning",
    "foundation model",
    "transformer",
    "retrieval",
    "rag",
    "agent",
    "tool",
    "orchestration",
]

DOMAIN_TERMS = [
    "livestock",
    "cattle",
    "beef",
    "dairy",
    "pasture",
    "forage",
    "paddock",
    "grazing",
    "body weight",
    "average daily gain",
    "adg",
    "dmd",
    "digestibility",
    "digital twin",
    "biophysical",
    "mechanistic",
]

OUTCOME_TERMS = [
    "body weight",
    "average daily gain",
    "adg",
    "growth curve",
    "brody",
    "cohort",
    "breed",
    "pasture",
    "forage",
    "paddock",
    "biomass",
    "regeneration",
    "digestibility",
    "dmd",
    "grazing",
    "stocking",
    "supplement",
]

DECISION_SUPPORT_TERMS = [
    "decision support",
    "scenario",
    "what-if",
    "uncertainty",
    "calibration",
    "provenance",
    "recommendation",
    "constraint",
    "audit",
    "plausibility",
]

HYBRID_PRIORITY_TERMS = [
    "hybrid",
    "mechanistic",
    "biophysical",
    "constraint",
    "digital twin",
    "benchmark",
    "cohort",
    "uncertainty",
    "scenario",
    "recommendation",
]

PURE_VISION_TERMS = [
    "semantic segmentation",
    "point cloud",
    "3d image",
    "computer vision",
    "body measurements",
    "heart girth",
    "morphometric",
]

NON_TARGET_ENVIRONMENT_TERMS = [
    "carbon monitoring",
    "atmospheric co2",
    "air quality",
    "pollution",
    "martian",
    "phobos",
    "deimos",
]



def merge_candidates(papers: Iterable[PaperRecord]) -> List[PaperRecord]:
    seen: Dict[str, PaperRecord] = {}
    for paper in papers:
        key = stable_fingerprint(paper.doi or "", paper.source_id or "", normalize_title(paper.title))
        if key not in seen:
            seen[key] = paper
            continue
        existing = seen[key]
        if parse_iso_datetime(paper.published_at) > parse_iso_datetime(existing.published_at):
            seen[key] = paper
    return sorted(seen.values(), key=lambda p: parse_iso_datetime(p.published_at), reverse=True)



def _contains_any(text: str, terms: Iterable[str]) -> List[str]:
    return [term for term in terms if term and term.lower() in text]



def _recency_score(paper: PaperRecord) -> float:
    age_days = max((now_utc() - parse_iso_datetime(paper.published_at)).days, 0)
    return max(0.0, 1.0 - min(age_days, 365) / 365)



def _text_for_paper(paper: PaperRecord) -> str:
    raw_extra = " ".join(
        str(value)
        for key, value in paper.raw_metadata.items()
        if key != "matched_query" and isinstance(value, str)
    )
    return f"{paper.title} {paper.abstract} {raw_extra}".lower()



def filter_and_rank(candidates: List[PaperRecord], config: RuntimeConfig) -> List[RankedPaper]:
    ranked: List[RankedPaper] = []
    for paper in candidates:
        text = _text_for_paper(paper)
        title = paper.title.lower()

        if config.exclude_terms and any(term.lower() in text for term in config.exclude_terms):
            continue
        if config.include_terms and not any(term.lower() in text for term in config.include_terms):
            continue
        if not any(token in text for token in ["time series", "timeseries", "forecast", "prediction"]):
            continue

        method_hits = _contains_any(text, METHOD_TERMS)
        domain_hits = _contains_any(text, DOMAIN_TERMS)
        outcome_hits = _contains_any(text, OUTCOME_TERMS)
        decision_hits = _contains_any(text, DECISION_SUPPORT_TERMS)
        hybrid_hits = _contains_any(text, HYBRID_PRIORITY_TERMS)
        boost_hits = _contains_any(text, config.boost_terms)
        penalty_hits = _contains_any(text, config.penalty_terms)
        pure_vision_hits = _contains_any(text, PURE_VISION_TERMS)
        non_target_env_hits = _contains_any(text, NON_TARGET_ENVIRONMENT_TERMS)

        method_score = min(len(unique_preserve_order(method_hits + boost_hits)) / 6.0, 1.0)
        domain_score = min(len(unique_preserve_order(domain_hits + hybrid_hits + boost_hits)) / 6.0, 1.0)
        outcome_score = min(len(unique_preserve_order(outcome_hits + boost_hits)) / 5.0, 1.0)
        decision_score = min(len(unique_preserve_order(decision_hits + hybrid_hits + boost_hits)) / 5.0, 1.0)
        recency_score = _recency_score(paper)

        score = (
            0.35 * method_score
            + 0.25 * domain_score
            + 0.20 * outcome_score
            + 0.10 * decision_score
            + 0.10 * recency_score
        ) * 10.0

        if any(token in title for token in ["classification", "segmentation"]):
            score -= 0.5
        if "multivariate" in title:
            score += 0.35
        if any(term in text for term in ["decision support", "digital twin", "scenario", "recommendation"]):
            score += 0.45
        if outcome_hits and (decision_hits or hybrid_hits or domain_hits):
            score += 0.55
        if not outcome_hits and not any(
            term in text
            for term in [
                "decision support",
                "digital twin",
                "recommendation",
                "scenario",
                "mechanistic",
                "biophysical",
                "orchestration",
                "tool-augmented",
            ]
        ):
            score -= 1.0
        if pure_vision_hits and not (decision_hits or hybrid_hits):
            score -= 1.0
        if non_target_env_hits and not outcome_hits:
            score -= 1.5
        score -= min(len(penalty_hits), 5) * 0.75
        if len((paper.abstract or "").split()) < 40:
            score -= 0.5

        matched_reasons = unique_preserve_order(method_hits + domain_hits + outcome_hits + decision_hits + hybrid_hits + boost_hits)
        if score >= config.min_relevance_score:
            ranked.append(RankedPaper(paper=paper, score=round(score, 2), matched_reasons=matched_reasons))

    ranked.sort(key=lambda row: (row.score, parse_iso_datetime(row.paper.published_at)), reverse=True)
    return ranked
