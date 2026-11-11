"""HTTP 服务：把自然语言问题变成 SQL、执行、给结论和图表建议。"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import db
from .graph import ask as ask_fn

app = FastAPI(title="招聘数据问答 Agent", version="1.0.0")


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=300)


@app.get("/health")
def health() -> dict:
    try:
        cols, rows = db.run_sql("SELECT COUNT(*) AS n FROM jobs")
        return {"status": "ok", "jobs": rows[0][0]}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"数据库不可用：{e}")


@app.get("/schema")
def schema() -> dict:
    return {"schema": db.SCHEMA, "notes": db.NOTES, "sample": db.sample_rows(3)}


@app.post("/ask")
def ask(body: AskIn) -> dict:
    r = ask_fn(body.question)
    return {
        "answer": r["answer"],
        "sql": r["sql"],
        "columns": r["columns"],
        "rows": r["rows"][:50],
        "chart": r["chart"],
        "error": r["error"],
        "latency_ms": r["latency_ms"],
    }


PAGE = """<!doctype html>
<meta charset="utf-8"><title>招聘数据问答</title>
<style>
 body{font:15px/1.7 -apple-system,"Segoe UI",sans-serif;max-width:820px;margin:44px auto;padding:0 20px;color:#1b1f24}
 textarea{width:100%;height:72px;padding:10px;font:inherit;border:1px solid #d0d7de;border-radius:8px}
 button{margin-top:10px;padding:8px 18px;border:0;border-radius:8px;background:#1f6feb;color:#fff;font:inherit;cursor:pointer}
 pre{background:#0d1117;color:#c9d1d9;padding:12px;border-radius:8px;overflow:auto;font-size:12.5px}
 table{border-collapse:collapse;margin-top:10px;font-size:13.5px}
 td,th{border:1px solid #d0d7de;padding:4px 8px}
 .ans{margin-top:16px;padding:12px 14px;background:#f6f8fa;border-radius:10px}
</style>
<h2>招聘数据问答（119 条真实岗位）</h2>
<textarea id="q" placeholder="比如：每个关键词下通过筛选的岗位平均薪资是多少？"></textarea>
<button onclick="go()">提问</button>
<div id="out"></div>
<script>
async function go(){
  const q=document.getElementById('q').value.trim(); if(!q) return;
  const out=document.getElementById('out'); out.textContent='分析中…';
  const t0=performance.now();
  const r=await fetch('/ask',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({question:q})});
  const d=await r.json();
  const head=`<tr>${d.columns.map(c=>`<th>${c}</th>`).join('')}</tr>`;
  const body=d.rows.map(r=>`<tr>${r.map(v=>`<td>${v===null?'':v}</td>`).join('')}</tr>`).join('');
  out.innerHTML=`<div class="ans">${d.answer||d.error}</div><pre>${d.sql}</pre>`+
    `<table>${head}${body}</table><div style="font-size:12px;color:#57606a;margin-top:8px">`+
    `${Math.round(performance.now()-t0)} ms · chart=${JSON.stringify(d.chart)}</div>`;
}
</script>"""


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return PAGE


def main() -> None:
    import uvicorn

    uvicorn.run("app.api:app", host="127.0.0.1", port=8010, reload=False)


if __name__ == "__main__":
    main()
