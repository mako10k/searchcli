from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from platformdirs import user_config_path

from searchcli.errors import SearchCliError


CONFIG_DIR = user_config_path("searchcli", "searchcli", ensure_exists=True)
CONFIG_PATH = Path(CONFIG_DIR) / "config.json"


@dataclass(slots=True)
class AppConfig:
    default_provider: str = "serper"
    default_format: str = "json"
    timeout_seconds: float = 20.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        return AppConfig()

    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SearchCliError(
            code="config_invalid",
            message=f"設定ファイルを読み込めませんでした: {CONFIG_PATH}",
            recovery=[
                "searchcli config show で現在値を確認する",
                f"問題のある設定ファイルを修正するか削除する: {CONFIG_PATH}",
            ],
            details={"reason": str(exc)},
        ) from exc

    return AppConfig(
        default_provider=raw.get("default_provider", "serper"),
        default_format=raw.get("default_format", "json"),
        timeout_seconds=float(raw.get("timeout_seconds", 20.0)),
    )


def save_config(config: AppConfig) -> Path:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return CONFIG_PATH
