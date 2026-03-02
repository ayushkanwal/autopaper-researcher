from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PaperRecord:
    source: str
    source_id: str
    title: str
    abstract: str
    authors: List[str]
    published_at: str
    updated_at: str
    doi: Optional[str]
    url: str
    pdf_url: Optional[str]
    keywords: List[str]
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SummaryPayload:
    five_bullet_summary: List[str]
    research_question: str
    method: str
    dataset: str
    metrics: str
    key_findings: str
    limitations: str
    practical_relevance: str
    deeper_breakdown: List[str]
    replication_checklist: List[str]
    confidence_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SummaryOutcome:
    payload: SummaryPayload
    provider: str
    fallback_used: bool = False
    provider_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["payload"] = self.payload.to_dict()
        return data


@dataclass
class RankedPaper:
    paper: PaperRecord
    score: float
    matched_reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paper": self.paper.to_dict(),
            "score": self.score,
            "matched_reasons": self.matched_reasons,
        }


@dataclass
class RunReport:
    timestamp: str
    profile_name: str
    queries: List[str]
    sources: List[str]
    collection_name: str
    focus_mode: str
    candidate_count: int
    added: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)
    attention: List[Dict[str, Any]] = field(default_factory=list)
    failures: List[Dict[str, Any]] = field(default_factory=list)
    pdf_import: Optional[Dict[str, Any]] = None
    scheduler_context: Dict[str, Any] = field(default_factory=dict)
    source_stats: Dict[str, Any] = field(default_factory=dict)
    summary_provider_stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
