# 自然语言数据分析 Agent（NL2SQL）· 个人项目

把中文问题翻译成 SQL、执行、给出结论和图表建议的 Agent。
数据是真实抓取的 **119 条深圳招聘岗位**（我自己用 BOSS 直聘抓的），DuckDB 建 `jobs` + `job_tags` 两张表。

## 一句话结果

| 指标 | 数值 | 说明 |
| --- | --- | --- |
| 数据量 | 119 条岗位 / 820 条标签 | 8 个搜索关键词各约 15 条 |
| 评测集 | 30 题（自然语言 + gold SQL） | 覆盖计数、分组、占比、排序、多表 |
| 单次通过率 | **83.3%（25/30）** | 结果集与 gold SQL 逐行比对 |
| 首版通过率 | 26.7%（8/30） | 同一评测集，见下方迭代记录 |
| 延迟 p50 / p95 | **1.67 s / 2.11 s** | 单次问答含 1 次 SQL 生成 + 1 次解释 |
| 失败回喂重写 | 最多 2 次 | 语法/安全校验/执行报错都会回喂模型 |

## Agent 结构（LangGraph 五节点）

```
读表结构与取值提示 → 生成 SQL（JSON） → 安全校验 → 执行 → 图表建议 → 中文解释
                        ↑                    │         │
                        └──── 报错回喂 ───────┴─────────┘
```

- **安全校验**（`app/safety.py`）：只允许单条 SELECT、表白名单、禁用 DDL/DML 关键字、强制 LIMIT。
- **执行**：DuckDB 只读连接，8 秒超时，超时直接 `interrupt()`。
- **图表建议**（`app/chart.py`）：按结果形状判定 trend / share / compare / single，前端据此选图。
- **解释**：把最多 20 行结果交给模型，要求逐行念出关键数字，不许编造。

## 迭代记录（同一套 30 题）

| 版本 | 通过率 | 改了什么 |
| --- | --- | --- |
| v1 | 26.7% | 只给 DDL，模型大量误用「通过筛选」视图，把 119 条算成 21 条 |
| v2 | 50.0% | schema 说明里补 keyword 取值、薪资单位、空值分布 |
| v3 | 46.7% | 去掉 `v_passed` 视图，改成显式条件（模型仍过度过滤） |
| v4 | 66.7% | 写明 reject_reason 的 5 个取值与「默认不过滤」规则 |
| v5 | 80.0% | 评测改成数值容差比较（0.2%），消除 ROUND 写法差异 |
| final | **83.3%** | 把「只输出某几列」写进问题，减少列数歧义 |

剩下 5 题失败的原因都很具体：把「杭州」当成了默认城市、用 title LIKE 代替 keyword 过滤、
以及一个多表交集问题的写法差异。这些失败样例都留在 `eval/report-final.json` 里。

## 目录

```
data/build_db.py   从 jobs.json 建 DuckDB（解析薪资区间、年发薪月数、日薪、经验/学历）
app/db.py           DuckDB 连接、超时执行、表结构与取值说明（SCHEMA / NOTES）
app/graph.py       LangGraph 五节点状态机
app/safety.py      SQL 白名单与 LIMIT 强制
app/chart.py       图表类型判定
app/cli.py         ask / eval / schema
app/api.py         FastAPI：/ask /schema /health + 网页问答页
eval/questions.jsonl  30 题（问题 + gold SQL）
eval/report-final.json 每题的 SQL、结果、耗时、是否通过
```

## 跑起来

**环境**：Python 3.11+、一个 OpenAI 兼容的对话接口（本项目实测用智谱 `glm-4-air`）。
数据已经放进仓库（`data/jobs.json`，119 条真实岗位），不需要额外下载。

```bash
# 1) Python 依赖
pip install -r requirements.txt

# 2) 建 DuckDB（薪资区间、年发薪月数、日薪、经验/学历都在这一步解析出来）
python data/build_db.py

# 3) 提问
python -m app.cli ask "南山区和福田区各有多少个岗位？"

# 4) 复现 83.3% 的评测
python -m app.cli eval --out eval/report-final.json

# 5) 网页版
python -m app.api            # http://127.0.0.1:8010
```

配置：`ZHIPU_API_KEY`（或在 `~/.modlens/config.json` 里）、`LLM_MODEL`、`LLM_BASE_URL`。
`data/jobs.duckdb` 被 `.gitignore` 排除，克隆后跑第 2 步即可重建（1 秒）。

## 示例输出

三个真实问答的原文（含引用、SQL、耗时）在 [`examples/demo.md`](examples/demo.md)。

## 测试

不依赖模型 key 的离线单测（SQL 安全校验），CI 在 Python 3.11 / 3.12 上跑：

```bash
python -m unittest discover -s tests -v
```

覆盖：注释与分号清理、自动追加 LIMIT、拒绝非 SELECT、拒绝多语句、拒绝危险关键字、
拒绝白名单外的表、允许 WITH 开头的 CTE。
## 限制

- 只有 119 条数据、2 张表，复杂多表问题覆盖不足。
- 薪资来自 BOSS 页面文本，个别远程岗位写了夸张区间（如 1000K），未做清洗，因为它就是原始数据。
- 模型只见过这张 schema，换库需要重写 SCHEMA / NOTES 提示。
