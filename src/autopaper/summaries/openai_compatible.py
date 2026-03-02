from __future__ import annotations

import json
from typing import Any, Dict

import requests

from autopaper.config import RuntimeConfig
from autopaper.models import PaperRecord, SummaryPayload
from autopaper.summaries.base import SummaryProviderError
from autopaper.utils import normalize_whitespace

USER_AGENT = "auto-paper-populator/0.3"


class OpenAICompatibleSummarizer:
    name = "openai_compatible"

    def summarize(self, paper: PaperRecord, config: RuntimeConfig) -> SummaryPayload:
        if not config.llm_base_url or not config.llm_api_key or not config.llm_model:
            raise SummaryProviderError("Missing OpenAI-compatible LLM configuration")

        url = config.llm_base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = url + "/chat/completions"

        payload = {
            "model": config.llm_model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You summarize research papers for Zotero notes. Return strict JSON with keys: "
                        "five_bullet_summary, research_question, method, dataset, metrics, key_findings, "
                        "limitations, practical_relevance, deeper_breakdown, replication_checklist, confidence_notes."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "title": paper.title,
                            "abstract": paper.abstract,
                            "authors": paper.authors,
                            "published_at": paper.published_at,
                            "source": paper.source,
                            "keywords": paper.keywords,
                        }
                    ),
                },
            ],
        }
        response = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {config.llm_api_key}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            timeout=config.llm_timeout_seconds,
        )
        response.raise_for_status()
        result = response.json()
        try:
            content = result["choices"][0]["message"]["content"]
            parsed: Dict[str, Any] = json.loads(content)
        except Exception as exc:  # noqa: BLE001
            raise SummaryProviderError(f"Invalid JSON summary response: {exc}") from exc
        try:
            return SummaryPayload(
                five_bullet_summary=[normalize_whitespace(x) for x in parsed["five_bullet_summary"]],
                research_question=normalize_whitespace(parsed["research_question"]),
                method=normalize_whitespace(parsed["method"]),
                dataset=normalize_whitespace(parsed["dataset"]),
                metrics=normalize_whitespace(parsed["metrics"]),
                key_findings=normalize_whitespace(parsed["key_findings"]),
                limitations=normalize_whitespace(parsed["limitations"]),
                practical_relevance=normalize_whitespace(parsed["practical_relevance"]),
                deeper_breakdown=[normalize_whitespace(x) for x in parsed["deeper_breakdown"]],
                replication_checklist=[normalize_whitespace(x) for x in parsed["replication_checklist"]],
                confidence_notes=[normalize_whitespace(x) for x in parsed.get("confidence_notes", [])],
            )
        except KeyError as exc:
            raise SummaryProviderError(f"Missing summary field: {exc}") from exc
