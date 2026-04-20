from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ProviderMeta:
    id: str
    display_name: str
    env_var: str
    signup_url: str
    docs_url: str
    summary: str
    best_for: str
    tradeoffs: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SearchRequest:
    query: str
    provider: str
    limit: int = 5
    region: str | None = None
    language: str | None = None
    answer: bool = True
    topic: str = "general"
    search_depth: str = "basic"
    timeout: float = 20.0
    model: str = "sonar"


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    score: float | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SearchResponse:
    provider: str
    query: str
    answer: str | None
    results: list[SearchResult]
    warnings: list[str] = field(default_factory=list)
    raw: dict[str, Any] | None = None
    auth_source: str | None = None

    def to_dict(self, include_raw: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": True,
            "provider": self.provider,
            "query": self.query,
            "answer": self.answer,
            "results": [item.to_dict() for item in self.results],
            "warnings": self.warnings,
        }
        if self.auth_source:
            payload["auth_source"] = self.auth_source
        if include_raw and self.raw is not None:
            payload["raw"] = self.raw
        return payload
