#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手动为记账本灌入演示数据。

用法：python seed_demo.py
写入当月 + 上月两个月的记录，方便直接看图表效果。
复用 app.py 里的建表逻辑，所以不需要先启动服务。
"""

from __future__ import annotations

from app import connect, init_db
from demo_data import seed


def main() -> None:
    init_db()
    conn = connect()
    try:
        inserted = seed(conn)
        total, count = conn.execute(
            "SELECT ROUND(SUM(amount), 2), COUNT(*) FROM records"
        ).fetchone()
    finally:
        conn.close()
    print(f"已写入 {inserted} 条演示记录，当前库内共 {count} 条，合计 ¥{total}")


if __name__ == "__main__":
    main()
