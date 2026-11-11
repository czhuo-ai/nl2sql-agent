"""不依赖模型与网络：SQL 安全校验的单元测试。

跑法：
    python -m pytest -q          （或 python -m unittest discover -s tests -v）
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.safety import UnsafeSQL, clean, validate  # noqa: E402


class TestClean(unittest.TestCase):
    def test_strips_comments_and_trailing_semicolon(self):
        sql = "SELECT count(*) FROM jobs -- 统计\n"
        self.assertEqual(clean(sql), "SELECT count(*) FROM jobs")

    def test_removes_block_comment(self):
        self.assertEqual(clean("SELECT 1 /* x */ FROM jobs;"), "SELECT 1 FROM jobs")


class TestValidate(unittest.TestCase):
    def test_appends_limit(self):
        out = validate("SELECT district, count(*) FROM jobs GROUP BY district")
        self.assertTrue(out.endswith("LIMIT 200"))

    def test_keeps_existing_limit(self):
        out = validate("SELECT * FROM jobs LIMIT 10")
        self.assertEqual(out.count("LIMIT"), 1)

    def test_rejects_non_select(self):
        with self.assertRaises(UnsafeSQL):
            validate("UPDATE jobs SET title = 'x'")

    def test_rejects_multiple_statements(self):
        with self.assertRaises(UnsafeSQL):
            validate("SELECT 1 FROM jobs; DROP TABLE jobs")

    def test_rejects_forbidden_keyword(self):
        with self.assertRaises(UnsafeSQL):
            validate("SELECT * FROM jobs WHERE title LIKE '%delete%' AND 1=1 LIMIT 5")

    def test_rejects_unknown_table(self):
        with self.assertRaises(UnsafeSQL):
            validate("SELECT * FROM users LIMIT 5")

    def test_allows_cte(self):
        sql = "WITH t AS (SELECT keyword, count(*) c FROM jobs GROUP BY keyword) SELECT * FROM t LIMIT 5"
        self.assertIn("WITH", validate(sql))


if __name__ == "__main__":
    unittest.main()
