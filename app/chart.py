"""从查询结果自动判断该画什么图：趋势 / 对比 / 占比 / 单值。

返回 {"kind": "...", "x": 列名, "y": 列名} 或 None。图表绘制在前端用这些字段完成，
服务端只给结论，不生成图片文件。
"""
from __future__ import annotations

import math
from typing import Any


def _numeric(rows: list[list[Any]], i: int) -> bool:
    for r in rows:
        v = r[i]
        if v is None:
            continue
        if not isinstance(v, (int, float)):
            return False
        if isinstance(v, float) and math.isnan(v):
            continue
    return True


def pick(cols: list[str], rows: list[list[Any]]) -> dict | None:
    if not cols or not rows:
        return None
    if len(cols) == 1 and len(rows) == 1:
        return {"kind": "single", "x": None, "y": cols[0]}

    num_cols = [i for i in range(len(cols)) if _numeric(rows, i)]
    if not num_cols:
        return None
    y = num_cols[-1]
    x = next((i for i in range(len(cols)) if i != y and not _numeric(rows, i)), 0)

    name = cols[x].lower()
    if any(k in name for k in ("date", "day", "month", "time", "年", "月", "日")):
        return {"kind": "trend", "x": cols[x], "y": cols[y]}
    if len(rows) <= 8 and y in num_cols:
        total = sum(abs(float(r[y] or 0)) for r in rows) or 1.0
        top = max(abs(float(r[y] or 0)) for r in rows)
        if top / total > 0.45 and len(rows) >= 2:
            return {"kind": "share", "x": cols[x], "y": cols[y]}
    return {"kind": "compare", "x": cols[x], "y": cols[y]}
