# 记账本 Expense Tracker

一个零依赖的全栈小应用：记一笔支出，自动算出当月总额、日均、分类占比和每日走势。

**前端**原生 HTML/CSS/JavaScript · **后端** Python 标准库 `http.server` · **数据库** SQLite

> 不需要 `pip install` 任何东西，克隆下来一条命令就能跑。

## 运行

```bash
python app.py
```

然后浏览器打开 <http://127.0.0.1:8000>

要求 Python 3.9 及以上（Windows / macOS / Linux 均可）。第一次启动会自动在项目目录创建 `app.db` 并建表。

想看带数据的效果，可以先灌一批演示记录（当月 + 上月，约 100 条，固定随机种子可复现）：

```bash
python seed_demo.py
```

不想跑也可以直接从空库开始，自己一条条记。

想换端口：

```bash
PORT=9000 python app.py        # macOS / Linux
set PORT=9000 && python app.py # Windows CMD
$env:PORT=9000; python app.py  # Windows PowerShell
```

## 功能

- **记一笔**：日期、金额、分类、备注，提交后立即入库并刷新页面数据
- **月度看板**：本月支出总额、笔数、日均、最大单笔
- **分类占比**：按分类汇总，横向条形图，带百分比
- **每日走势**：按天聚合的柱状图，悬停显示当天金额
- **明细列表**：按日期倒序，支持逐条删除
- **月份切换**：右上角选月份，回看任意历史月份

## 目录结构

```
expense-tracker/
├── app.py              # 后端：HTTP 路由 + REST API + SQLite 建表与查询
├── seed_demo.py        # 可选：灌入一批演示数据
├── static/
│   ├── index.html      # 页面骨架
│   ├── style.css       # 样式
│   └── app.js          # 前端逻辑：请求接口、渲染看板
├── app.db              # SQLite 数据文件（首次运行自动生成，不入库）
└── README.md
```

后端一个文件 367 行；前端三个文件共 727 行（其中样式 386 行、逻辑 244 行、结构 97 行）。含演示数据脚本，全部代码约 1,200 行。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/meta` | 分类清单、今天日期、当前月份 |
| `GET` | `/api/records?month=YYYY-MM&category=餐饮` | 记录列表（`month`、`category` 均可省略） |
| `POST` | `/api/records` | 新增记录，body：`{"date","amount","category","note"}` |
| `DELETE` | `/api/records/{id}` | 删除一条记录 |
| `GET` | `/api/summary?month=YYYY-MM` | 月度汇总：总额、笔数、日均、分类占比、每日金额 |

新增示例：

```bash
curl -X POST http://127.0.0.1:8000/api/records \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-10-30","amount":32.5,"category":"餐饮","note":"午饭"}'
```

## 数据表

```sql
CREATE TABLE records (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date       TEXT    NOT NULL,              -- YYYY-MM-DD
    amount     REAL    NOT NULL CHECK (amount > 0),
    category   TEXT    NOT NULL,
    note       TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL
);
CREATE INDEX idx_records_date ON records(date);
```

## 几个实现上的取舍

- **为什么用标准库而不是 Flask**：这个项目要能被任何人直接跑起来，多一个依赖就多一道"装不上"的门槛。`http.server` 加一个 `ThreadingHTTPServer` 足够应付这种流量，路由用字符串匹配就够了。
- **按 `date BETWEEN 起始日 AND 终止日` 查询，而不是 `substr(date,1,7) = '2026-10'`**：前者能走 `idx_records_date` 索引，后者会让索引失效。
- **每次请求单独开连接**：`sqlite3` 的连接对象不能跨线程共享，而 `ThreadingHTTPServer` 是多线程的，所以采用"请求内开、用完即关"，靠 SQLite 自身的文件锁保证一致性。
- **校验放在后端**：日期格式、金额范围、分类白名单、备注长度都在 `parse_record_body` 里过一遍，前端只做基本提示。
- **静态文件做了路径穿越防护**：`_serve_static` 里用 `relative_to` 校验解析后的路径必须落在 `static/` 目录内，避免 `../../` 读到别处的文件。

## 开发方式

与 AI 结对编程完成：先定下"零依赖 + 标准库 + SQLite"的约束，再按对话逐步加功能（先跑通增删查，再加汇总接口，最后做图表和样式），每一步都本地跑一遍验证。初版在一小时内成型，之后的改动都是在这个基础上迭代的。
