"""把 BOSS 抓取的真实招聘数据（jobs.json）建成 duckdb 分析库。

用法：
    python data/build_db.py
产物：
    data/jobs.duckdb   表 jobs / job_tags
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
LOCAL_SRC = HERE / "jobs.json"
SRC = LOCAL_SRC if LOCAL_SRC.exists() else Path(
    r"C:\Users\18310\Documents\deepseek-harness\default-workspace\boss\data\jobs.json"
)
DB = HERE / "jobs.duckdb"

DEGREES = ("博士", "硕士", "本科", "大专", "中专", "高中", "学历不限")
EXP_RE = re.compile(r"^(\d+)-(\d+)年$|^经验不限$|^应届|^\d+年以内$|^\d+年以上$|^在校")


def parse_salary(raw: str) -> dict:
    """'10-15K·14薪' / '200-250元/天' / '15K以上' / '' → 结构化字段。"""
    out = {"min": None, "max": None, "kind": None, "months": None, "daily_min": None, "daily_max": None}
    if not raw:
        return out
    months = re.search(r"·(\d+)薪", raw)
    if months:
        out["months"] = int(months.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(K|千|元/天|元/月)?", raw)
    if m:
        lo, hi, unit = float(m.group(1)), float(m.group(2)), m.group(3) or "K"
        if "天" in unit:
            out.update(kind="daily", daily_min=lo, daily_max=hi)
        elif "月" in unit:
            out.update(min=lo / 1000, max=hi / 1000, kind="monthly")
        else:
            out.update(min=lo, max=hi, kind="monthly")
        return out
    m = re.search(r"(\d+(?:\.\d+)?)\s*(K|千)\s*以上", raw)
    if m:
        out.update(min=float(m.group(1)), max=None, kind="monthly")
    return out


def split_area(area: str) -> tuple[str, str]:
    parts = [p for p in (area or "").split("·") if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    district = parts[1]
    # BOSS 用私有区字符做字体混淆，个别行会把薪资串混进地区，这里丢掉脏值
    if not district.endswith(("区", "县", "市")) or any(0xE000 <= ord(ch) <= 0xF8FF for ch in district):
        return parts[0], ""
    return parts[0], district


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    jobs = data["jobs"]
    rows, tag_rows = [], []
    for j in jobs:
        sal = parse_salary(j.get("salary") or "")
        city, district = split_area(j.get("area") or "")
        tags = j.get("tags") or []
        exp = next((t for t in tags if EXP_RE.search(t)), "")
        degree = next((t for t in tags if t in DEGREES), "")
        rows.append(
            (
                j["id"],
                j.get("title") or "",
                j.get("company") or "",
                city,
                district,
                j.get("area") or "",
                j.get("salary") or "",
                sal["min"],
                sal["max"],
                sal["kind"],
                sal["months"],
                sal["daily_min"],
                sal["daily_max"],
                j.get("keyword") or "",
                j.get("reject") or "",
                exp,
                degree,
                " ".join(tags),
            )
        )
        for t in tags:
            tag_rows.append((j["id"], t))

    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    con.execute(
        """
        CREATE TABLE jobs (
            job_id       VARCHAR PRIMARY KEY,
            title        VARCHAR,
            company      VARCHAR,
            city         VARCHAR,
            district     VARCHAR,
            area_full    VARCHAR,
            salary_raw   VARCHAR,
            salary_min_k DOUBLE,     -- 月薪下限（K）
            salary_max_k DOUBLE,     -- 月薪上限（K）
            salary_kind  VARCHAR,    -- monthly / daily / NULL
            salary_months INTEGER,   -- 发薪月数，如 14
            daily_min_yuan DOUBLE,   -- 日薪下限（元/天），仅 salary_kind = daily
            daily_max_yuan DOUBLE,   -- 日薪上限（元/天）
            keyword      VARCHAR,    -- 抓取时用的搜索词
            reject_reason VARCHAR,   -- 被筛掉的原因，空串=通过
            experience   VARCHAR,
            degree       VARCHAR,
            tags_text    VARCHAR
        )
        """
    )
    con.execute("CREATE TABLE job_tags (job_id VARCHAR, tag VARCHAR)")
    con.executemany("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.executemany("INSERT INTO job_tags VALUES (?,?)", tag_rows)

    con.commit()
    n_jobs = con.execute("SELECT count(*) FROM jobs").fetchone()[0]
    n_tags = con.execute("SELECT count(*) FROM job_tags").fetchone()[0]
    n_ok = con.execute("SELECT count(*) FROM jobs WHERE reject_reason=''").fetchone()[0]
    con.close()
    print(f"OK {DB}  jobs={n_jobs} tags={n_tags} passed={n_ok}")


if __name__ == "__main__":
    sys.exit(main())
