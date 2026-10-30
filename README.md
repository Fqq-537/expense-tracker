# 记账本 Expense Tracker

一个零依赖的全栈小应用：记一笔支出，自动算出当月总额、日均、分类占比和每日走势。

**前端**原生 HTML/CSS/JavaScript · **后端** Python 标准库 `http.server` · **数据库** SQLite

> 不需要 `pip install` 任何东西，克隆下来一条命令就能跑。

**在线演示**：<https://expense-tracker-24491.app.workbuddy.host/?sharecode=YKOZKDSERZ>
浏览器直接打开就能用，不用装 Python（数据存在容器里，重启会回到初始演示数据）。

## 运行

三步：

```bash
git clone https://github.com/Fqq-537/expense-tracker.git
cd expense-tracker
python app.py
```

然后浏览器打开 <http://127.0.0.1:8000>

> Windows 上如果 `python` 没反应，换成 `py app.py`。
> 已经有这个目录的话，前两行不用做，直接在目录里跑第三行。

要求 Python 3.9 及以上（Windows / macOS / Linux 均可）。第一次启动会自动在项目目录创建 `app.db` 并建表。

**如果库是空的，首次启动会自动写入一批演示数据**（当月 + 上月，约 100 条），这样打开就能看到图表效果。想从零开始记自己的账，加个参数：

```bash
python app.py --empty
```

也可以随时手动补数据：`python seed_demo.py`。

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

## 设计思路

想解决的就是一件小事：**记一笔支出要足够快，月底又要能一眼看出钱花在哪**。围绕这点定了四个原则：

1. **只做单表，不拆分类表**
   分类是固定的七项白名单（餐饮、交通、购物、居住、学习、娱乐、其他），拆成独立表只会多一次 `JOIN`，换不来任何收益。所有数据压在 `records` 一张表里，日期上建索引——月度查询、分类汇总、按天聚合都走同一条索引。

2. **接口按"读什么"来切，而不是按"表"来切**
   前端一进页面需要三样东西：分类清单、本月汇总、本月明细。所以接口就是 `/api/meta`、`/api/summary`、`/api/records` 三个，一次请求拿一整块可渲染的数据，前端不用自己再拼。汇总（总额 / 笔数 / 日均 / 分类占比 / 每日金额）在 SQL 里用 `GROUP BY` 一次算完，不把原始记录全丢给前端循环。

3. **前端是原生 JS，一个页面一个状态**
   没有框架、没有构建步骤、没有 CDN。页面只有"当前月份"一个状态，改了月份就重新拉一次数据重渲染整块看板。图表用 `div` 宽度画条形图、用高度画柱状图，省掉图表库几百 KB 的体积——数据量只有几十条，不需要 Canvas。

4. **零依赖是硬约束，不是顺手**
   这个项目的第一使用场景是"别人拿到就能跑"，多一个 `pip install` 就多一次装不上的可能。所以后端只用 `http.server` + `sqlite3`，连模板引擎都不用，静态文件直接读盘返回。

## 目录结构

```
expense-tracker/
├── app.py              # 后端：HTTP 路由 + REST API + SQLite 建表与查询
├── demo_data.py        # 演示数据生成（固定随机种子）
├── seed_demo.py        # 手动灌演示数据的命令行入口
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
