#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""演示数据生成。

单独抽出来，是因为有两个场景要用：`seed_demo.py` 手动灌数据，
以及空库首次启动时自动灌一批，避免打开就是一片空白。
固定随机种子，同样的月份每次生成结果一致。
"""

from __future__ import annotations

import calendar
import random
from datetime import date, datetime, timedelta

# 分类 -> (金额区间, 出现权重, 备注候选)
PRESETS: dict[str, tuple[tuple[int, int], int, list[str]]] = {
    "餐饮": ((12, 68), 10, ["午饭", "晚饭", "外卖", "食堂", "咖啡"]),
    "交通": ((3, 26), 6, ["地铁", "公交", "打车", "共享单车"]),
    "购物": ((25, 320), 4, ["日用品", "超市", "衣服", "网购"]),
    "居住": ((80, 1500), 1, ["房租", "水电费", "物业费"]),
    "娱乐": ((20, 160), 3, ["电影", "游戏", "演出"]),
    "学习": ((15, 260), 3, ["教材", "网课", "文具", "打印"]),
    "医疗": ((10, 180), 1, ["药品", "门诊"]),
    "其他": ((5, 90), 2, ["快递", "话费", ""]),
}

SEED = 20261030


def _pick_category(rng: random.Random) -> str:
    names = list(PRESETS)
    weights = [PRESETS[n][1] for n in names]
    return rng.choices(names, weights=weights, k=1)[0]


def build_rows(
    rng: random.Random,
    first_day: date,
    days: int,
    stop: date | None = None,
) -> list[tuple]:
    """为一个月份生成记录，stop 用于截断到今天（不给则整月都生成）。"""
    rows = []
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for day in range(1, days + 1):
        the_day = date(first_day.year, first_day.month, day)
        if stop and the_day > stop:
            break
        times = rng.choices([0, 1, 2, 3], weights=[1, 6, 5, 2], k=1)[0]
        for _ in range(times):
            category = _pick_category(rng)
            low, high = PRESETS[category][0]
            rows.append(
                (
                    the_day.isoformat(),
                    round(rng.uniform(low, high), 2),
                    category,
                    rng.choice(PRESETS[category][2]),
                    stamp,
                )
            )
    return rows


def seed(conn, today: date | None = None) -> int:
    """写入当月 + 上月两个月的演示数据，返回写入条数。"""
    today = today or date.today()
    rng = random.Random(SEED)

    first = date(today.year, today.month, 1)
    days_this = calendar.monthrange(first.year, first.month)[1]
    rows = build_rows(rng, first, days_this, stop=today)

    prev_last = first - timedelta(days=1)
    prev_first = date(prev_last.year, prev_last.month, 1)
    days_prev = calendar.monthrange(prev_first.year, prev_first.month)[1]
    rows += build_rows(rng, prev_first, days_prev)

    conn.executemany(
        "INSERT INTO records (date, amount, category, note, created_at) VALUES (?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return len(rows)
