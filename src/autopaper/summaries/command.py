from __future__ import annotations

import json
import subprocess
from typing import Any, Dict

from autopaper.config import RuntimeConfig
from autopaper.models import PaperRecord, SummaryPayload
from autopaper.summaries.base import SummaryProviderError
from autopaper.utils import normalize_whitespace, shlex_split


class CommandSummarizer:
    name = "command"

    def summarize(self, paper: PaperRecord, config: RuntimeConfig) -> SummaryPayload:
        if not config.summary_command:
            raise SummaryProviderError("Missing AUTOPAPER_SUMMARY_COMMAND")
        proc = subprocess.run(
            shlex_split(config.summary_command),
            input=json.dumps(
                {
                    "paper": paper.to_dict(),
                    "profile": config.profile_name,
                    "runtime": config.to_public_dict(),
                }
            ),
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise SummaryProviderError(proc.stderr.strip() or f"Summary command failed with exit code {proc.returncode}")
        try:
            parsed: Dict[str, Any] = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise SummaryProviderError("Summary command returned invalid JSON") from exc
        required = [
            "five_bullet_summary",
            "research_question",
            "method",
            "dataset",
            "metrics",
            "key_findings",
            "limitations",
            "practical_relevance",
            "deeper_breakdown",
            "replication_checklist",
            "confidence_notes",
        ]
        missing = [field for field in required if field not in parsed]
        if missing:
            raise SummaryProviderError(f"Summary command missing fields: {', '.join(missing)}")
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
