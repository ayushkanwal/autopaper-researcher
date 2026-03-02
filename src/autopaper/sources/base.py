from __future__ import annotations

from typing import Protocol

from autopaper.models import PaperRecord


class SourceAdapter(Protocol):
    name: str

    def search(self, query: str, max_results: int) -> list[PaperRecord]:
        ...
