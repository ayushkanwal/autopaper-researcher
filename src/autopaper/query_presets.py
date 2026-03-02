from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class QueryPreset:
    name: str
    description: str
    queries: List[str]
    sources: List[str]
    boost_terms: List[str] = field(default_factory=list)
    penalty_terms: List[str] = field(default_factory=list)
    include_terms: List[str] = field(default_factory=list)
    exclude_terms: List[str] = field(default_factory=list)
    collection_name: str = "autopaper-ingested"
    min_relevance_score: int = 8


PRESETS: Dict[str, QueryPreset] = {
    "livestock_decision_support_v2": QueryPreset(
        name="livestock_decision_support_v2",
        description="Livestock and pasture decision-support preset focused on hybrid forecasting, digital twins, retrieval, and orchestration.",
        sources=["arxiv", "pubmed", "openalex"],
        collection_name="autopaper-ingested",
        min_relevance_score=8,
        queries=[
            'all:"multivariate time series" AND (all:forecasting OR all:prediction OR all:reasoning OR all:analysis) AND (all:llm OR all:"foundation model" OR all:agent OR all:"tool-augmented" OR all:retrieval OR all:rag OR all:orchestration)',
            'all:"time series" AND (all:"decision support" OR all:"scenario planning" OR all:recommendation OR all:uncertainty OR all:calibration OR all:"anomaly detection")',
            'all:"hybrid model" AND (all:"time series" OR all:forecasting) AND (all:mechanistic OR all:biophysical OR all:constraint OR all:"digital twin")',
            '(livestock OR "beef cattle" OR "dairy cattle" OR grazing) AND ("body weight" OR "average daily gain" OR ADG OR growth OR "growth curve" OR Brody) AND (prediction OR forecasting OR benchmark OR cohort OR "decision support")',
            '(pasture OR forage OR paddock OR grazing) AND (growth OR regeneration OR biomass OR digestibility OR DMD) AND (prediction OR forecasting OR "decision support" OR "remote sensing")',
            '("digital twin" AND (livestock OR cattle OR grazing OR pasture)) OR ("precision livestock farming" AND (forecasting OR model OR "decision support"))',
            '((retrieval OR rag OR "case-based") AND ("time series" OR forecasting)) AND (reasoning OR agent OR tool OR orchestration)',
            '((livestock OR pasture OR grazing) AND (uncertainty OR calibration OR scenario OR anomaly OR recommendation)) AND ("decision support" OR forecasting OR prediction)',
        ],
        boost_terms=[
            "multivariate",
            "retrieval",
            "rag",
            "tool-augmented",
            "agentic",
            "orchestration",
            "digital twin",
            "livestock",
            "cattle",
            "pasture",
            "paddock",
            "forage",
            "adg",
            "body weight",
            "dmd",
            "biophysical",
            "mechanistic",
            "hybrid",
            "constraint",
            "uncertainty",
            "calibration",
            "anomaly detection",
            "scenario",
            "recommendation",
            "decision support",
            "what-if",
            "brody",
            "cohort",
            "growth curve",
        ],
        penalty_terms=[
            "stock price",
            "cryptocurrency",
            "traffic flow",
            "electric load",
            "ecg",
            "eeg",
            "image-only",
            "vision-only",
            "semantic segmentation",
            "point cloud",
            "heart girth",
            "body measurements",
            "morphometric",
        ],
        include_terms=["time series", "forecast", "prediction"],
        exclude_terms=[],
    ),
    "livestock_decision_support_v1": QueryPreset(
        name="livestock_decision_support_v1",
        description="Earlier livestock and pasture preset focused on multivariate time series, digital twins, retrieval, and tool orchestration.",
        sources=["arxiv", "pubmed", "openalex"],
        collection_name="autopaper-ingested",
        min_relevance_score=8,
        queries=[
            'all:"multivariate time series" AND (all:forecasting OR all:prediction OR all:analysis) AND (all:llm OR all:"foundation model" OR all:agent OR all:"tool-augmented" OR all:retrieval OR all:rag)',
            'all:"time series" AND (all:"decision support" OR all:agentic OR all:tool OR all:orchestration OR all:"temporal reasoning")',
            'all:"time series foundation model" AND (all:multivariate OR all:"zero-shot" OR all:retrieval OR all:adaptation)',
            'all:"multimodal time series" AND (all:forecasting OR all:reasoning)',
            '(livestock OR "beef cattle" OR "dairy cattle" OR grazing) AND ("body weight" OR "average daily gain" OR ADG OR growth) AND (prediction OR forecasting OR model OR "decision support")',
            '(pasture OR forage OR paddock OR grazing) AND (growth OR regeneration OR biomass OR digestibility OR DMD) AND (prediction OR forecasting OR "remote sensing")',
            '("digital twin" AND (livestock OR cattle OR grazing)) OR ("precision livestock farming" AND (forecasting OR model OR "decision support"))',
            '(livestock OR grazing) AND (methane OR emissions OR sustainability OR stocking) AND (model OR forecasting OR "decision support")',
        ],
        boost_terms=[
            "multivariate",
            "retrieval",
            "rag",
            "tool-augmented",
            "agentic",
            "orchestration",
            "digital twin",
            "livestock",
            "cattle",
            "pasture",
            "paddock",
            "forage",
            "adg",
            "body weight",
            "dmd",
            "biophysical",
            "mechanistic",
            "uncertainty",
            "calibration",
            "anomaly detection",
            "scenario",
            "decision support",
            "what-if",
            "brody",
        ],
        penalty_terms=[
            "stock price",
            "cryptocurrency",
            "traffic flow",
            "electric load",
            "ecg",
            "eeg",
            "image-only",
        ],
        include_terms=["time series", "forecast", "prediction"],
        exclude_terms=[],
    ),
    "general_time_series_v1": QueryPreset(
        name="general_time_series_v1",
        description="General multi-source time-series discovery preset for researchers across domains.",
        sources=["arxiv", "pubmed", "openalex"],
        collection_name="autopaper-ingested",
        min_relevance_score=6,
        queries=[
            'all:"time series" AND (all:forecasting OR all:prediction OR all:analysis)',
            'all:"multivariate time series" AND (all:forecasting OR all:reasoning OR all:foundation model)',
            'all:"time series" AND (all:retrieval OR all:tool-augmented OR all:agentic OR all:rag)',
        ],
        boost_terms=["time series", "forecasting", "prediction", "multivariate", "retrieval", "agentic"],
        penalty_terms=["stock price", "cryptocurrency"],
        include_terms=["time series"],
        exclude_terms=[],
    ),
}

DEFAULT_PRESET = "general_time_series_v1"


def get_preset(name: str) -> QueryPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        known = ", ".join(sorted(PRESETS))
        raise KeyError(f"Unknown query preset '{name}'. Available presets: {known}") from exc


def list_presets() -> List[QueryPreset]:
    return [PRESETS[key] for key in sorted(PRESETS)]
