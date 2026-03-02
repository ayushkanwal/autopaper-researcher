from __future__ import annotations

from autopaper.config import RuntimeConfig
from autopaper.models import PaperRecord, SummaryPayload
from autopaper.utils import split_sentences


class OfflineSummarizer:
    name = "offline"

    def summarize(self, paper: PaperRecord, config: RuntimeConfig) -> SummaryPayload:
        sentences = split_sentences(paper.abstract)
        bullets = sentences[:5] if sentences else [f"Paper title: {paper.title}"]

        def infer_field(keywords: list[str], fallback: str) -> str:
            for sentence in sentences:
                lowered = sentence.lower()
                if any(token in lowered for token in keywords):
                    return sentence
            return fallback

        confidence_notes = [
            "Offline summary derived from title, abstract, and metadata only.",
            "Claims should be verified against the full text before reuse in research writing.",
        ]

        return SummaryPayload(
            five_bullet_summary=bullets,
            research_question=infer_field(
                ["we investigate", "this paper", "we study", "we address", "problem"],
                "Investigate improved methods for time-series analysis, prediction, or decision support.",
            ),
            method=infer_field(
                ["we propose", "we present", "model", "approach", "framework", "agent"],
                "Method details are not fully described in the abstract.",
            ),
            dataset=infer_field(
                ["dataset", "datasets", "benchmark", "benchmarks", "real-world", "synthetic"],
                "Dataset details are not specified in the abstract.",
            ),
            metrics=infer_field(
                ["mae", "mse", "rmse", "mape", "accuracy", "f1", "auc", "metric"],
                "Metrics are not explicitly listed in the abstract.",
            ),
            key_findings=infer_field(
                ["outperform", "improve", "results", "state-of-the-art", "sota", "achieve"],
                "Key findings should be confirmed from the full text.",
            ),
            limitations=infer_field(
                ["however", "limitation", "future work", "challenge", "cost", "trade-off"],
                "Limitations are not explicitly discussed in the abstract.",
            ),
            practical_relevance=(
                "Useful for research and decision systems requiring robust time-series forecasting, explanation, "
                "or context-aware recommendation support."
            ),
            deeper_breakdown=sentences[:10] if sentences else [],
            replication_checklist=[
                "Data source and preprocessing steps identified",
                "Train/validation/test split clarified",
                "Primary baselines listed",
                "Evaluation metrics and horizon settings extracted",
                "Compute or training budget requirements noted",
            ],
            confidence_notes=confidence_notes,
        )
