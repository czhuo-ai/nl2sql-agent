"""数据库连接与执行：duckdb 只读连接 + 超时保护。"""
from __future__ import annotations

import threading
from typing import Any

import duckdb

from .config import CFG
from .safety import clean

SCHEMA = """\
CREATE TABLE jobs (
  job_id        VARCHAR,   -- 岗位唯一 id
  title         VARCHAR,   -- 岗位名称
  company       VARCHAR,   -- 公司名
  city          VARCHAR,   -- 城市，例如 深圳
  district      VARCHAR,   -- 区，例如 南山区、龙岗区（可能为空）
  area_full     VARCHAR,   -- 原始地区串，例如 深圳·南山区·科技园
  salary_raw    VARCHAR,   -- 原始薪资串，例如 10-15K、15-30K·14薪、200-250元/天
  salary_min_k  DOUBLE,    -- 月薪下限（单位 K=千元），日薪为 NULL 以外的每日元数需看 salary_kind
  salary_max_k  DOUBLE,    -- 月薪上限（单位 K）
  salary_kind   VARCHAR,   -- 'monthly' 月薪 / 'daily' 日薪 / NULL 未标
  salary_months INTEGER,   -- 年发薪月数，例如 14；未写为 NULL
  daily_min_yuan DOUBLE,   -- 日薪下限（元/天），仅 salary_kind=daily 的行有值
  daily_max_yuan DOUBLE,   -- 日薪上限（元/天）
  keyword       VARCHAR,   -- 抓取这条岗位时用的搜索关键词
  reject_reason VARCHAR,   -- 被筛选规则排除的原因；空串 '' = 通过筛选
  experience    VARCHAR,   -- 经验要求，例如 1-3年、3-5年、经验不限（可能为空）
  degree        VARCHAR,   -- 学历要求，例如 本科、大专（可能为空）
  tags_text     VARCHAR    -- 全部标签空格拼接
);
CREATE TABLE job_tags (job_id VARCHAR, tag VARCHAR);
"""

NOTES = """\
- 数据是 2026 年 11 月在深圳用 BOSS 直聘抓的 119 条 AI/后端/测试/数据类岗位。
- reject_reason 是被筛掉的原因，取值只有这些（注意其中有空格）：
  ''（空串，通过筛选，21 条）、'关键词不匹配'（41 条）、'薪资低于 15K'（33 条）、'命中排除词「实习」'（19 条）、'命中排除词「销售」'（4 条）。
- 重要：默认查询全部 119 条，不要自己加 reject_reason 条件；只有问题里明确出现「通过筛选 / 符合筛选条件 / 筛过的」时才加 WHERE reject_reason = ''。
- job_tags 是标签明细表，常见标签：本科、大专、1-3年、3-5年、五险一金、Java、Python。
- keyword 是抓取时用的搜索词，只有 8 个取值：算法工程师、大模型、AI应用、Java开发、Python、后端开发、测试开发、数据分析。
  「AI 岗位」「大模型岗位」这类说法按 keyword 过滤，不要用 title LIKE。
- salary_min_k / salary_max_k 单位是 K（千元/月），只对 salary_kind='monthly' 的行有值；日薪岗位 salary_kind='daily'，金额在 daily_min_yuan / daily_max_yuan（元/天）。
- district 有 35 行为空（只写了「深圳」或完全没写），按区统计时要把空串单独说明。
- 只有 jobs / job_tags 两张表，没有别的视图；「全部/所有岗位」一律查 jobs。
- 只有深圳的数据，别按其他城市过滤。
"""


def connect(read_only: bool = True):
    return duckdb.connect(str(CFG.db_path), read_only=read_only)


def run_sql(sql: str, timeout_s: float = 8.0) -> tuple[list[str], list[list[Any]]]:
    """执行查询，超过 timeout_s 抛 TimeoutError。"""
    con = connect()
    box: dict[str, Any] = {}

    def work() -> None:
        try:
            cur = con.execute(clean(sql))
            cols = [d[0] for d in cur.description]
            box["data"] = (cols, [list(r) for r in cur.fetchall()])
        except Exception as e:  # noqa: BLE001
            box["err"] = e

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        con.interrupt()
        raise TimeoutError(f"查询超过 {timeout_s:.0f} 秒")
    if "err" in box:
        raise box["err"]
    return box["data"]


def sample_rows(n: int = 3) -> str:
    cols, rows = run_sql(f"SELECT * FROM jobs LIMIT {n}")
    lines = [" | ".join(cols)]
    for r in rows:
        lines.append(" | ".join("" if v is None else str(v) for v in r))
    return "\n".join(lines)
