# 三个真实问答（本机跑出来的原文）

命令：`python -m app.cli ask "..."`（数据：`data/jobs.json` 里 119 条真实岗位）

## 1. 分组统计

**问**：南山区和福田区各有多少个岗位？

```sql
SELECT district, COUNT(job_id) AS job_count
FROM jobs
WHERE district IN ('南山区', '福田区')
GROUP BY district
LIMIT 200
```

结果：南山区 36，福田区 11

答：南山区有 36 个岗位，福田区有 11 个岗位，约为福田区的 3 倍多。
建议图表：占比图（share）　耗时 2.1 s

## 2. 分组 + 排序

**问**：8 个搜索关键词里，哪个抓到的岗位最多？

```sql
SELECT keyword, COUNT(*) AS count FROM jobs GROUP BY keyword ORDER BY count DESC LIMIT 200
```

结果：Python 16 · 数据分析 15 · Java开发 15 · AI应用 15 · 算法工程师 15 · 测试开发 15 · 大模型 14 · 后端开发 14

答：Python 抓到的岗位最多，有 16 个。
建议图表：对比柱状图（compare）　耗时 1.9 s

## 3. 能答，但暴露了原始数据的问题

**问**：薪资最高的前 3 条岗位是哪几个，多少 K？

```sql
SELECT title, salary_max_k AS salary_k FROM jobs
WHERE salary_kind = 'monthly'
ORDER BY salary_max_k DESC LIMIT 3
```

结果：AI 应用讲师 200K · VLA/VLM 算法工程师 110K · 运筹优化算法工程师 60K

这一条 SQL 与计算都对，但 200K 是招聘信息里原本就写的夸张数字。没有做清洗，
因为「发现异常值、保留原始数据并单独标注」本身就是这个项目要展示的判断。
