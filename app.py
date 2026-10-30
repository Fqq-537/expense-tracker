#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记账本 —— 零依赖全栈示例。

技术栈：Python 3 标准库（http.server + sqlite3）+ 原生 HTML / CSS / JavaScript。
不依赖任何第三方包，克隆下来执行 `python app.py` 即可运行。

启动后访问 http://127.0.0.1:8000
"""

from __future__ import annotations

import calendar
import json
import mimetypes
import os
import re
import sqlite3
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = Path(os.environ.get("EXPENSE_DB", BASE_DIR / "app.db"))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))

CATEGORIES = ["餐饮", "交通", "购物", "居住", "娱乐", "学习", "医疗", "其他"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
MAX_BODY = 64 * 1024
MAX_NOTE = 40

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


# ---------------------------------------------------------------- 数据层

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def month_bound(month: str) -> tuple[str, str]:
    """返回该月的首尾日期，用于 date 范围查询（能走索引）。"""
    year, mon = int(month[:4]), int(month[5:7])
    last_day = calendar.monthrange(year, mon)[1]
    return f"{month}-01", f"{month}-{last_day:02d}"


def list_records(month: str | None, category: str | None) -> list[dict]:
    sql = "SELECT id, date, amount, category, note, created_at FROM records"
    where, params = [], []
    if month:
        start, end = month_bound(month)
        where.append("date BETWEEN ? AND ?")
        params += [start, end]
    if category:
        where.append("category = ?")
        params.append(category)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date DESC, id DESC LIMIT 500"

    conn = connect()
    try:
        return [dict(row) for row in conn.execute(sql, params)]
    finally:
        conn.close()


def create_record(payload: dict) -> dict:
    conn = connect()
    try:
        cur = conn.execute(
            "INSERT INTO records (date, amount, category, note, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                payload["date"],
                payload["amount"],
                payload["category"],
                payload["note"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, date, amount, category, note, created_at FROM records WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def delete_record(record_id: int) -> bool:
    conn = connect()
    try:
        cur = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def summarize(month: str) -> dict:
    start, end = month_bound(month)
    conn = connect()
    try:
        total, count = conn.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM records"
            " WHERE date BETWEEN ? AND ?",
            (start, end),
        ).fetchone()
        biggest = conn.execute(
            "SELECT COALESCE(MAX(amount), 0) FROM records WHERE date BETWEEN ? AND ?",
            (start, end),
        ).fetchone()[0]
        by_category = [
            {"category": r[0], "amount": round(r[1], 2), "count": r[2]}
            for r in conn.execute(
                "SELECT category, SUM(amount), COUNT(*) FROM records"
                " WHERE date BETWEEN ? AND ? GROUP BY category ORDER BY 2 DESC",
                (start, end),
            )
        ]
        by_day = [
            {"date": r[0], "amount": round(r[1], 2)}
            for r in conn.execute(
                "SELECT date, SUM(amount) FROM records"
                " WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date",
                (start, end),
            )
        ]
    finally:
        conn.close()

    for item in by_category:
        item["pct"] = round(item["amount"] / total * 100, 1) if total else 0.0

    days_in_month = calendar.monthrange(int(month[:4]), int(month[5:7]))[1]
    today = date.today()
    elapsed = min(today.day, days_in_month) if month == today.strftime("%Y-%m") else days_in_month

    return {
        "month": month,
        "total": round(total, 2),
        "count": count,
        "avg_per_day": round(total / elapsed, 2) if elapsed else 0.0,
        "max_single": round(biggest, 2),
        "days_in_month": days_in_month,
        "days_elapsed": elapsed,
        "by_category": by_category,
        "by_day": by_day,
    }


# ---------------------------------------------------------------- 校验

class BadRequest(Exception):
    pass


def parse_record_body(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BadRequest("请求体不是合法的 JSON")

    if not isinstance(data, dict):
        raise BadRequest("请求体必须是 JSON 对象")

    day = str(data.get("date", "")).strip()
    if not DATE_RE.match(day):
        raise BadRequest("日期格式应为 YYYY-MM-DD")
    try:
        date.fromisoformat(day)
    except ValueError:
        raise BadRequest("日期不存在，请检查年月日")

    try:
        amount = round(float(data.get("amount")), 2)
    except (TypeError, ValueError):
        raise BadRequest("金额必须是数字")
    if amount <= 0:
        raise BadRequest("金额必须大于 0")
    if amount > 1_000_000:
        raise BadRequest("金额过大，请检查")

    category = str(data.get("category", "")).strip()
    if category not in CATEGORIES:
        raise BadRequest("分类不在允许范围内")

    note = str(data.get("note", "") or "").strip()
    if len(note) > MAX_NOTE:
        raise BadRequest(f"备注不能超过 {MAX_NOTE} 个字符")

    return {"date": day, "amount": amount, "category": category, "note": note}


# ---------------------------------------------------------------- HTTP 层

class Handler(BaseHTTPRequestHandler):
    server_version = "ExpenseTracker/1.0"
    protocol_version = "HTTP/1.1"

    # ---- 响应工具 ----
    def _send_json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int) -> None:
        self._send_json({"error": message}, status)

    def _send_file(self, path: Path) -> None:
        ctype, _ = mimetypes.guess_type(path.name)
        if ctype is None:
            ctype = "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise BadRequest("Content-Length 不合法")
        if length > MAX_BODY:
            raise BadRequest("请求体过大")
        return self.rfile.read(length) if length else b""

    # ---- 路由 ----
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)

        if route == "/api/meta":
            self._send_json(
                {
                    "categories": CATEGORIES,
                    "today": date.today().isoformat(),
                    "month": date.today().strftime("%Y-%m"),
                }
            )
            return

        if route == "/api/records":
            month = query.get("month", [None])[0]
            category = query.get("category", [None])[0]
            if month and not MONTH_RE.match(month):
                self._send_error_json("月份格式应为 YYYY-MM", 400)
                return
            self._send_json({"records": list_records(month, category)})
            return

        if route == "/api/summary":
            month = query.get("month", [None])[0] or date.today().strftime("%Y-%m")
            if not MONTH_RE.match(month):
                self._send_error_json("月份格式应为 YYYY-MM", 400)
                return
            self._send_json(summarize(month))
            return

        if route.startswith("/api/"):
            self._send_error_json("接口不存在", 404)
            return

        self._serve_static(route)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/records":
            self._send_error_json("接口不存在", 404)
            return
        try:
            payload = parse_record_body(self._read_body())
            record = create_record(payload)
        except BadRequest as exc:
            self._send_error_json(str(exc), 400)
            return
        except sqlite3.Error as exc:
            self._send_error_json(f"数据库写入失败：{exc}", 500)
            return
        self._send_json(record, 201)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        match = re.fullmatch(r"/api/records/(\d+)", parsed.path)
        if not match:
            self._send_error_json("接口不存在", 404)
            return
        if delete_record(int(match.group(1))):
            self._send_json({"deleted": True})
        else:
            self._send_error_json("记录不存在", 404)

    # ---- 静态资源 ----
    def _serve_static(self, route: str) -> None:
        rel = route.lstrip("/") or "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        target = (STATIC_DIR / rel).resolve()
        try:
            target.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self._send_error_json("非法路径", 403)
            return
        if not target.is_file():
            self._send_error_json("页面不存在", 404)
            return
        self._send_file(target)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("记账本已启动")
    print(f"  数据库：{DB_PATH}")
    print(f"  打开浏览器访问 http://{HOST}:{PORT}")
    print("  按 Ctrl + C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
