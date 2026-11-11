"""LangGraph 五节点：生成 SQL → 安全校验 → 执行 → 图表选择 → 中文解释。

失败会把错误信息回喂给模型重写，最多重试 CFG.max_retry 次。
"""
from __future__ import annotations

import json
import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from . import chart as chart_mod
from . import db
from .config import CFG
from .llm import chat
from .safety import UnsafeSQL, clean, validate

SQL_SYSTEM = f"""你是一个把中文问题翻译成 DuckDB SQL 的助手。只能使用下面的表：

{db.SCHEMA}

补充说明：
{db.NOTES}

输出要求：
- 只输出 JSON：{{"sql": "SELECT ...", "reason": "一句话说明"}}，不要输出别的文字。
- 只写一条 SELECT（可用 WITH），不要写分号结尾。
- 列名用英文别名，方便前端展示；数值列请保留原始单位（K 表示千元）。
- 需要排序时明确 ORDER BY；聚合查询要给别名。
- 不要臆造不存在的表或列。
"""

FIX_SYSTEM = """上次生成的 SQL 出错了，请根据报错修正后重新输出 JSON：{"sql": "...", "reason": "..."}。
只输出 JSON。"""

EXPLAIN_SYSTEM = """你是数据分析师。根据用户问题、执行的 SQL 和查询结果，用中文写 2~3 句结论：\n- 结果有几行就说几行，逐个把关键行的名字和数字念出来，不要只看第一行；
- 先直接回答数字或排名，再补一句解释；
- 不要复述 SQL；
- 结果为空时说明「没有符合条件的岗位」，并提示可能的放宽条件；
- 只描述结果里真实出现的行；表格最多展示 20 行，行数更多时不要推算「其余还有多少家/多少条」；\n- 不要编造结果里没有的信息。"""


class State(TypedDict, total=False):
    question: str
    sql: str
    reason: str
    error: str
    retry: int
    cols: list[str]
    rows: list[list[Any]]
    chart_spec: dict | None
    answer: str
    latency_ms: int


def node_generate(state: State) -> State:
    msgs = [{"role": "system", "content": SQL_SYSTEM}]
    msgs.append({"role": "user", "content": state["question"]})
    if state.get("error"):
        msgs = [
            {"role": "system", "content": SQL_SYSTEM + "\n\n" + FIX_SYSTEM},
            {"role": "user", "content": state["question"]},
            {"role": "assistant", "content": state.get("sql") or ""},
            {"role": "user", "content": f"执行报错：{state['error']}\n请修正。"},
        ]
    raw = chat(msgs, temperature=0.1, max_tokens=700, json_mode=True)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        obj = json.loads(raw[start : end + 1]) if start >= 0 else {"sql": raw}
    return {**state, "sql": clean(obj.get("sql", "")), "reason": obj.get("reason", "")}


def node_validate(state: State) -> State:
    try:
        return {**state, "sql": validate(state["sql"], CFG.max_rows), "error": ""}
    except UnsafeSQL as e:
        return {**state, "error": f"安全校验未通过：{e}", "retry": state.get("retry", 0) + 1}


def node_execute(state: State) -> State:
    try:
        cols, rows = db.run_sql(state["sql"])
        return {**state, "cols": cols, "rows": rows, "error": ""}
    except Exception as e:  # noqa: BLE001
        return {**state, "error": str(e)[:400], "retry": state.get("retry", 0) + 1}


def node_chart(state: State) -> State:
    return {**state, "chart_spec": chart_mod.pick(state.get("cols") or [], state.get("rows") or [])}


def node_explain(state: State) -> State:
    cols = state.get("cols") or []
    rows = (state.get("rows") or [])[:20]
    table = " | ".join(cols) + "\n" + "\n".join(
        " | ".join("" if v is None else str(v) for v in r) for r in rows
    )
    prompt = f"用户问题：{state['question']}\n\n执行结果（最多 20 行）：\n{table}"
    text = chat(
        [{"role": "system", "content": EXPLAIN_SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=400,
    )
    return {**state, "answer": text.strip()}


def _after_validate(state: State) -> str:
    if state.get("error"):
        return "generate" if state.get("retry", 0) <= CFG.max_retry else END
    return "execute"


def _after_execute(state: State) -> str:
    if state.get("error"):
        return "generate" if state.get("retry", 0) <= CFG.max_retry else END
    return "chart"


def build():
    g = StateGraph(State)
    g.add_node("generate", node_generate)
    g.add_node("validate", node_validate)
    g.add_node("execute", node_execute)
    g.add_node("chart", node_chart)
    g.add_node("explain", node_explain)
    g.set_entry_point("generate")
    g.add_edge("generate", "validate")
    g.add_conditional_edges("validate", _after_validate, {"generate": "generate", "execute": "execute", END: END})
    g.add_conditional_edges("execute", _after_execute, {"generate": "generate", "chart": "chart", END: END})
    g.add_edge("chart", "explain")
    g.add_edge("explain", END)
    return g.compile()


GRAPH = build()


def ask(question: str) -> dict:
    t0 = time.time()
    out = GRAPH.invoke({"question": question, "retry": 0})
    ms = int((time.time() - t0) * 1000)
    return {
        "question": question,
        "answer": out.get("answer") or "",
        "sql": out.get("sql") or "",
        "reason": out.get("reason") or "",
        "columns": out.get("cols") or [],
        "rows": out.get("rows") or [],
        "chart": out.get("chart_spec"),
        "error": out.get("error") or "",
        "latency_ms": ms,
    }
