# EVE Market Tool

EVE Online 市场交易管理系统 — 基于 FastAPI + PostgreSQL 的全功能市场数据分析平台。

## 功能

- **跨区域套利** — 比较 Jita / Amarr / Dodixie / Rens / Hek 五大贸易中心价格，发现套利机会
- **空间站短线交易** — 同一空间站内低买高卖差价发现，追踪交易盈亏
- **制造利润分析** — 蓝图材料成本 vs 市场售价，找到有利可图的制造项目
- **市场数据看板** — 订单量、总交易额、价格趋势图表、热门商品监控
- **EVE SSO 认证** — 通过 EVE Online 官方 OAuth2 登录
- **价格提醒** — 设置价格告警阈值，自动检测触发

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python 3.12) |
| 数据库 | PostgreSQL 17 + SQLAlchemy 2.0 (async) |
| 异步驱动 | asyncpg |
| 数据迁移 | Alembic |
| 后台任务 | APScheduler |
| ESI 客户端 | httpx + 令牌桶限流 + ETag 缓存 |
| 认证 | EVE SSO OAuth2 + python-jose JWT |
| 前端 | Jinja2 + htmx + Alpine.js + Chart.js + Pico CSS |

## 快速开始

### 1. 启动 PostgreSQL

```bash
docker-compose up -d db
```

### 2. 配置环境

```bash
cp .env.example .env
# 编辑 .env 填入 EVE SSO Client ID/Secret（可选）
```

### 3. 安装依赖

```bash
uv venv
uv pip install -e ".[dev]"
```

### 4. 数据库迁移

```bash
uv run alembic upgrade head
```

### 5. 启动应用

```bash
uv run uvicorn app.main:app --reload
```

访问 **http://localhost:8000** 查看前端看板。

### 6. API 文档

- Swagger UI: **http://localhost:8000/docs**
- ReDoc: **http://localhost:8000/redoc**

## 项目结构

```
app/
├── api/v1/endpoints/   # REST API 端点 (32 条路由)
├── core/               # 配置、数据库、ESI 客户端、安全
├── models/             # SQLAlchemy ORM 模型 (16 张表)
├── schemas/            # Pydantic v2 请求/响应模型
├── services/           # 业务逻辑层
├── repositories/       # 数据访问层 (DAO)
├── tasks/              # APScheduler 定时任务
└── templates/          # Jinja2 前端模板
```

## API 端点

### 套利 (`/api/v1/arbitrage`)
- `GET /opportunities` — 套利机会列表
- `GET /items/{type_id}/comparison` — 单物品价格对比
- `POST /scan` — 触发套利扫描

### 交易 (`/api/v1/trading`)
- `GET /opportunities` — 站内差价发现
- `POST /trades` — 创建追踪交易
- `GET /summary` — 盈亏汇总

### 制造 (`/api/v1/manufacturing`)
- `POST /analyze` — 蓝图利润分析
- `GET /top` — 最有利可图的制造项目

### 看板 (`/api/v1/dashboard`)
- `GET /overview` — 市场总览
- `GET /trends/{type_id}` — 价格趋势
- `GET /hot-items` — 热门商品

### 认证 (`/api/v1/auth`)
- `GET /login` — EVE SSO 登录
- `GET /callback` — SSO 回调

## 后台任务

| 任务 | 频率 |
|------|------|
| 市场订单抓取 | 每 5 分钟 |
| 宇宙均价更新 | 每 5 分钟 |
| 套利机会计算 | 每 5 分钟 |
| 热门商品检测 | 每 5 分钟 |
| 价格提醒评估 | 每 5 分钟 |
| 旧数据清理 | 每日 |

## 数据保留策略

- 48 小时内：保留所有订单快照
- 48 小时-30 天：每小时保留一份
- 30 天以上：每天保留一份

## 测试

```bash
uv run pytest tests/ -v
```
