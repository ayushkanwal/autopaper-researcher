from __future__ import annotations

from typing import Protocol

from autopaper.config import RuntimeConfig
from autopaper.models import PaperRecord, SummaryPayload


class Summarizer(Protocol):
    name: str

    def summarize(self, paper: PaperRecord, config: RuntimeConfig) -> SummaryPayload:
        ...


class SummaryProviderError(RuntimeError):
    pass



def build_summarizer_by_name(name: str) -> Summarizer:
    if name == "offline":
        from .offline import OfflineSummarizer

        return OfflineSummarizer()
    if name == "openai_compatible":
        from .openai_compatible import OpenAICompatibleSummarizer

        return OpenAICompatibleSummarizer()
    if name == "command":
        from .command import CommandSummarizer

        return CommandSummarizer()
    raise SummaryProviderError(f"Unsupported summarizer: {name}")


def build_summarizer(config: RuntimeConfig) -> Summarizer:
    return build_summarizer_by_name(config.summarizer)
