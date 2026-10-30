#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为记账本生成一批演示数据。

用法：python seed_demo.py
会写入当月的 30 条左右记录，外加上月若干条，方便直接看图表效果。
固定随机种子，重复执行结果一致；已有数据不会被清空。
"""

from __future__ import annotations

import calendar
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"

# 分类 -> (金额区间, 出现权重, 备注候选)
PRESETS = {
    "餐饮": ((12, 68), 10, ["午饭", "晚饭", "外卖", "食堂", "咖啡"]),
    "交通": ((3, 26), 6, ["地铁", "公交", "打车", "共享单车"]),
    "购物": ((25, 320), 4, ["日用品", "超市", "衣服", "网购"]),
    "居住": ((80, 1500), 1, ["房租", "水电费", "物业费"]),
    "娱乐": ((20, 160), 3, ["电影", "游戏", "演出"]),
    "学习": ((15, 260), 3, ["教材", "网课", "文具", "打印"]),
    "医疗": ((10, 180), 1, ["药品", "门诊"]),
    "其他": ((5, 90), 2, ["快递", "话费", ""]),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date       TEXT    NOT NULL,
    amount     REAL    NOT NULL CHECK (amount > 0),
    category   TEXT    NOT NULL,
    note       TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_records_date ON records(date);
"""


def pick_category(rng: random.Random) -> str:
    names = list(PRESETS)
    weights = [PRESETS[n][1] for n in names]
    return rng.choices(names, weights=weights, k=1)[0]


def build_rows(rng: random.Random, month: date, days: int) -> list[tuple]:
    rows = []
    for day in range(1, days + 1):
        the_day = date(month.year, month.month, day)
        if the_day > date.today():
            break
        for _ in range(rng.choices([0, 1, 2, 3], weights=[1, 6, 5, 2], k=1)[0]):
            category = pick_category(rng)
            low, high = PRESETS[category][0]
            amount = round(rng.uniform(low, high), 2)
            note = rng.choice(PRESETS[category][2])
            rows.append(
                (
                    the_day.isoformat(),
                    amount,
                    category,
                    note,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
            )
    return rows


def main() -> None:
    rng = random.Random(20261030)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)

        today = date.today()
        this_month = date(today.year, today.month, 1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        rows = build_rows(rng, this_month, last_day)

        prev = this_month - timedelta(days=1)
        prev_days = calendar.monthrange(prev.year, prev.month)[1]
        rows += build_rows(rng, date(prev.year, prev.month, 1), prev_days)

        conn.executemany(
            "INSERT INTO records (date, amount, category, note, created_at) VALUES (?,?,?,?,?)",
            rows,
        )
        conn.commit()

        total, count = conn.execute(
            "SELECT ROUND(SUM(amount), 2), COUNT(*) FROM records"
        ).fetchone()
        print(f"已写入 {len(rows)} 条演示记录，当前库内共 {count} 条，合计 ¥{total}")
        print(f"数据文件：{DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
