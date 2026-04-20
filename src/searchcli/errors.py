from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SearchCliError(Exception):
    code: str
    message: str
    recovery: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    exit_code: int = 2

    def __str__(self) -> str:
        return self.message

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "recovery": self.recovery,
            },
        }
        if self.details:
            payload["error"]["details"] = self.details
        return payload
