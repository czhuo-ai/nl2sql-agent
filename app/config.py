from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def _modlens_key() -> str:
    cfg = Path.home() / ".modlens" / "config.json"
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        return data.get("providers", {}).get("openai", {}).get("apiKey", "")
    except Exception:
        return ""


@dataclass
class Config:
    api_base: str = os.getenv("LLM_BASE", "https://open.bigmodel.cn/api/paas/v4")
    api_key: str = os.getenv("LLM_API_KEY") or _modlens_key()
    llm_model: str = os.getenv("LLM_MODEL", "glm-4-air")
    db_path: Path = ROOT / "data" / "jobs.duckdb"
    max_rows: int = 200
    max_retry: int = 2
    timeout_s: float = 30.0


CFG = Config()
