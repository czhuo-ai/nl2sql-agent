"""命令行：ask / eval / schema。

    python -m app.cli ask "深圳哪个区岗位最多？"
    python -m app.cli eval  --out eval/report.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from . import db
from .config import ROOT
from .graph import ask as ask_fn
from .llm import USAGE


def _close(a: object, b: object) -> bool:
    """数值比较允许 0.2% 相对误差（不同写法/是否 ROUND 都会造成小数差）。"""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if a is None or b is None:
            return a is b
        if isinstance(a, bool) or isinstance(b, bool):
            return a == b
        tol = max(0.05, abs(float(b)) * 0.002)
        return abs(float(a) - float(b)) <= tol
    return str(a).strip() == str(b).strip()


def _row_close(a: tuple, b: tuple) -> bool:
    return len(a) == len(b) and all(_close(x, y) for x, y in zip(a, b))


def same(actual: list[list], gold: list[list]) -> bool:
    """结果集比较：行数一致且每一行都能一一对应（忽略行序，数值带容差）。"""
    if len(actual) != len(gold):
        return False
    left = [tuple(r) for r in actual]
    for g in (tuple(r) for r in gold):
        hit = next((i for i, a in enumerate(left) if _row_close(a, g)), None)
        if hit is None:
            return False
        left.pop(hit)
    return True


def cmd_ask(args) -> None:
    r = ask_fn(args.question)
    print(f"\n问题：{r['question']}")
    print(f"SQL ：{r['sql']}")
    print(f"行数：{len(r['rows'])}  耗时：{r['latency_ms']} ms")
    for row in r["rows"][:10]:
        print("   ", " | ".join("" if v is None else str(v) for v in row))
    print(f"\n回答：{r['answer']}")
    if r["chart"]:
        print(f"图表：{r['chart']}")


def cmd_eval(args) -> None:
    qs = [json.loads(line) for line in (ROOT / "eval" / "questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    ok, latencies, details = 0, [], []
    for item in qs:
        _, gold_rows = db.run_sql(item["gold"])
        r = ask_fn(item["q"])
        passed = (not r["error"]) and same(r["rows"], gold_rows)
        ok += 1 if passed else 0
        latencies.append(r["latency_ms"])
        details.append(
            {
                "id": item["id"],
                "q": item["q"],
                "passed": passed,
                "sql": r["sql"],
                "gold": item["gold"],
                "actual_rows": r["rows"][:5],
                "gold_rows": gold_rows[:5],
                "error": r["error"],
                "latency_ms": r["latency_ms"],
                "answer": r["answer"],
            }
        )
        print(f"{'PASS' if passed else 'FAIL'} {item['id']} {r['latency_ms']:>6} ms  {item['q'][:36]}")

    report = {
        "n": len(qs),
        "pass": ok,
        "accuracy": round(ok / len(qs), 4),
        "retry_recovered": sum(1 for d in details if d["passed"] and "GROUP BY" in d["sql"]),
        "latency_p50_ms": int(statistics.median(latencies)),
        "latency_p95_ms": int(sorted(latencies)[int(len(latencies) * 0.95) - 1]),
        "tokens": dict(USAGE),
        "model": __import__("app.config", fromlist=["CFG"]).CFG.llm_model,
        "details": details,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n准确率 {report['accuracy']}（{ok}/{len(qs)}）  p50 {report['latency_p50_ms']} ms  p95 {report['latency_p95_ms']} ms")
    print(f"tokens {report['tokens']}")
    print(f"明细 -> {out}")


def cmd_schema(args) -> None:
    print(db.SCHEMA)
    print(db.sample_rows(3))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nl2sql")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask")
    a.add_argument("question")
    a.set_defaults(func=cmd_ask)
    e = sub.add_parser("eval")
    e.add_argument("--out", default="eval/report.json")
    e.set_defaults(func=cmd_eval)
    s = sub.add_parser("schema")
    s.set_defaults(func=cmd_schema)
    args = p.parse_args(argv)
    t0 = time.time()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
