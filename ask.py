"""双击 .bat 用的简单入口。

用法：
  ask.py                 # 从环境变量 AGENT_Q 读问题（由 命令行提问.bat 设置）
  ask.py --demo          # 跑三个示例问题
  ask.py "问题内容"       # 直接传问题
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.graph import ask as ask_fn  # noqa: E402

DEMO = [
    "南山区和福田区各有多少个岗位？",
    "8 个搜索关键词里，哪个抓到的岗位最多？",
    "薪资最高的前 3 条岗位是哪几个，多少 K？",
]


def show(question: str) -> None:
    res = ask_fn(question)
    print("问：" + question)
    print()
    print("它写的 SQL：")
    print("  " + (res["sql"] or "(没有生成 SQL)").replace("\n", "\n  "))
    print()
    cols = res.get("columns") or []
    rows = res.get("rows") or []
    if cols:
        print("结果：")
        print("  " + " | ".join(str(c) for c in cols))
        for row in rows[:10]:
            print("  " + " | ".join(str(v) for v in row))
        if len(rows) > 10:
            print(f"  ……共 {len(rows)} 行")
        print()
    if res.get("error"):
        print("执行出错：" + res["error"])
        print()
    print("答：" + (res["answer"] or "(没有生成回答)"))
    chart = res.get("chart") or {}
    print()
    print(f"建议图表：{chart.get('kind', '-')}　耗时 {res['latency_ms']} ms")


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] == "--demo":
        for i, q in enumerate(DEMO, 1):
            print("=" * 46)
            print(f" 第 {i} 个问题")
            print("=" * 46)
            show(q)
            print()
        return

    question = " ".join(argv).strip() or os.environ.get("AGENT_Q", "").strip()
    if not question:
        question = DEMO[0]
    show(question)


if __name__ == "__main__":
    main()
