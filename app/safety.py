"""查询安全校验：只允许单条 SELECT，限制表与函数，强制加 LIMIT。"""
from __future__ import annotations

import re

ALLOWED_TABLES = {"jobs", "job_tags", "v_passed"}
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|export|import|install|load|pragma|vacuum|call|set)\b",
    re.IGNORECASE,
)
COMMENT = re.compile(r"(--[^\n]*)|(/\*.*?\*/)", re.S)


class UnsafeSQL(ValueError):
    pass


def clean(sql: str) -> str:
    s = COMMENT.sub(" ", sql or "").strip()
    s = s.rstrip(";").strip()
    return re.sub(r"\s+", " ", s)


def validate(sql: str, max_rows: int = 200) -> str:
    s = clean(sql)
    if not s:
        raise UnsafeSQL("SQL 为空")
    if ";" in s:
        raise UnsafeSQL("只允许单条语句")
    low = s.lower()
    if not (low.startswith("select") or low.startswith("with")):
        raise UnsafeSQL("只允许 SELECT 查询")
    bad = FORBIDDEN.search(s)
    if bad:
        raise UnsafeSQL(f"包含不允许的关键字 {bad.group(0).upper()}")
    for t in ALLOWED_TABLES:
        if re.search(rf"\b{t}\b", low):
            break
    else:
        raise UnsafeSQL("查询里没有出现白名单表（jobs / job_tags / v_passed）")
    if not re.search(r"\blimit\b", low):
        s = f"{s} LIMIT {max_rows}"
    return s
