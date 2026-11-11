"""智谱（OpenAI 兼容）最小客户端：chat + token 统计。

只依赖标准库 urllib，避免额外安装 openai 包。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .config import CFG

USAGE = {"prompt": 0, "completion": 0, "calls": 0}


def _post(path: str, payload: dict, retries: int = 3) -> dict:
    url = CFG.api_base.rstrip("/") + path
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last: Exception | None = None
    for i in range(retries):
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {CFG.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=CFG.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            usage = data.get("usage") or {}
            USAGE["prompt"] += int(usage.get("prompt_tokens") or 0)
            USAGE["completion"] += int(usage.get("completion_tokens") or 0)
            USAGE["calls"] += 1
            return data
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            last = RuntimeError(f"HTTP {e.code}: {detail}")
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (i + 1))
                continue
            raise last
        except Exception as e:  # 网络抖动
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"调用模型失败：{last}")


def chat(
    messages: list[dict[str, Any]],
    model: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 800,
    json_mode: bool = False,
) -> str:
    payload = {
        "model": model or CFG.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _post("/chat/completions", payload)
    return data["choices"][0]["message"]["content"]
