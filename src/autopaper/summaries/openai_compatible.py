from __future__ import annotations

import json
import re
from typing import Any, Dict

import requests

from autopaper.config import RuntimeConfig
from autopaper.models import PaperRecord, SummaryPayload
from autopaper.summaries.base import SummaryProviderError
from autopaper.utils import normalize_whitespace

USER_AGENT = "auto-paper-populator/0.3"


def _extract_json_object(text: str) -> Dict[str, Any]:
    content = (text or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
        content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [normalize_whitespace(str(item)) for item in value if normalize_whitespace(str(item))]
    text = normalize_whitespace(str(value))
    return [text] if text else []


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(_as_list(value))
    return normalize_whitespace(str(value))


class OpenAICompatibleSummarizer:
    name = "openai_compatible"

    def summarize(self, paper: PaperRecord, config: RuntimeConfig) -> SummaryPayload:
        if not config.llm_base_url or not config.llm_model:
            raise SummaryProviderError("Missing OpenAI-compatible LLM configuration")

        url = config.llm_base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = url + "/chat/completions"

        payload = {
            "model": config.llm_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
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
        headers = {
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        if config.llm_api_key:
            headers["Authorization"] = f"Bearer {config.llm_api_key}"

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=config.llm_timeout_seconds,
        )
        response.raise_for_status()
        result = response.json()
        try:
            content = result["choices"][0]["message"]["content"]
            parsed = _extract_json_object(content)
        except Exception as exc:  # noqa: BLE001
            raise SummaryProviderError(f"Invalid JSON summary response: {exc}") from exc
        try:
            return SummaryPayload(
                five_bullet_summary=_as_list(parsed["five_bullet_summary"]),
                research_question=_as_text(parsed["research_question"]),
                method=_as_text(parsed["method"]),
                dataset=_as_text(parsed["dataset"]),
                metrics=_as_text(parsed["metrics"]),
                key_findings=_as_text(parsed["key_findings"]),
                limitations=_as_text(parsed["limitations"]),
                practical_relevance=_as_text(parsed["practical_relevance"]),
                deeper_breakdown=_as_list(parsed["deeper_breakdown"]),
                replication_checklist=_as_list(parsed["replication_checklist"]),
                confidence_notes=_as_list(parsed.get("confidence_notes", [])),
            )
        except KeyError as exc:
            raise SummaryProviderError(f"Missing summary field: {exc}") from exc
