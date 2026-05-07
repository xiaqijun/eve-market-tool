# EVE Market Tool

EVE Online 市场交易管理系统 — 基于 FastAPI + PostgreSQL 的全功能市场数据分析平台。

## 一键部署

```bash
curl -fsSL https://raw.githubusercontent.com/xiaqijun/eve-market-tool/main/install.sh | bash
```

支持自定义参数：`--port 9000 --dir /opt/eve`

更新已有部署：

```bash
curl -fsSL https://raw.githubusercontent.com/xiaqijun/eve-market-tool/main/install.sh | bash -s -- --update
```

## 功能

- **跨区域套利** — 比较 Jita / Amarr / Dodixie / Rens / Hek 五大贸易中心价格，发现套利机会
- **空间站短线交易** — 同一空间站内低买高卖差价发现，追踪交易盈亏
- **制造利润分析** — 蓝图材料成本 vs 市场售价，使用 ESI 真实系统成本指数计算制造费用
- **市场数据看板** — 订单量、总交易额、价格趋势图表（Chart.js）、热门商品监控
- **EVE SSO 认证** — 通过 EVE Online 官方 OAuth2 登录，JWT 会话管理
- **价格提醒** — 设置价格告警阈值，自动检测触发

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python 3.12) |
| 数据库 | PostgreSQL 17 + SQLAlchemy 2.0 (async) |
| 异步驱动 | asyncpg |
| 数据迁移 | Alembic |
| 后台任务 | APScheduler |
| ESI 客户端 | httpx + 令牌桶限流 + ETag 缓存 + tenacity 重试 |
| 认证 | EVE SSO OAuth2 + python-jose JWT |
| 前端 | Jinja2 + htmx + Alpine.js + Chart.js |

## 快速开始（本地开发）

### 1. 启动 PostgreSQL

```bash
docker compose up -d db
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

## 部署

### Docker Compose（推荐）

```bash
cp .env.production .env
# 编辑 .env 填入密码和 SSO 凭据
docker compose up -d --build
docker compose exec app alembic upgrade head
```

### 远程服务器

```bash
bash scripts/deploy.sh <SERVER_IP> [SSH_USER]
```

或使用 Python 脚本（需设置环境变量）：

```bash
export DEPLOY_SERVER_IP=1.2.3.4
export DEPLOY_SSH_PASSWORD=your_password
python scripts/deploy_auto.py
```

## 认证

EVE SSO OAuth2 登录流程：

1. 用户访问 `/api/v1/auth/login`，跳转到 EVE 官方登录页
2. 登录后回调 `/api/v1/auth/callback`，获取角色信息并创建本地 JWT
3. 前端在后续请求中携带 `Authorization: Bearer <token>`

受保护的端点（告警、交易）需要登录。公开端点（看板、套利列表、物品搜索）无需认证。

## 项目结构

```
app/
├── api/
│   ├── deps.py              # 共享依赖 (get_db, get_current_user)
│   └── v1/endpoints/        # REST API 端点 (8 模块, ~29 条路由)
├── core/                    # 配置、数据库、ESI 客户端、安全
├── models/                  # SQLAlchemy ORM 模型
├── schemas/                 # Pydantic v2 请求/响应模型
├── services/                # 业务逻辑层
├── repositories/            # 数据访问层 (DAO)
├── tasks/                   # APScheduler 定时任务 (7 个)
├── templates/               # Jinja2 前端模板
└── main.py                  # FastAPI 入口 + Jinja2 单例
tests/
└── unit/                    # 单元测试
scripts/                     # 部署和工具脚本 (gitignored)
install.sh                   # 一键部署脚本
```

## API 端点

### 认证 (`/api/v1/auth`)

- `GET /login` — EVE SSO 登录跳转
- `GET /callback` — SSO 回调，获取 JWT
- `GET /me` — 当前用户信息（需登录）

### 套利 (`/api/v1/arbitrage`)

- `GET /opportunities` — 套利机会列表（数据库分页）
- `GET /opportunities/{id}` — 单条套利详情
- `GET /items/{type_id}/comparison` — 单物品跨区域价格对比
- `POST /scan` — 触发套利扫描

### 交易 (`/api/v1/trading`)

- `GET /opportunities` — 站内差价发现（公开）
- `GET /trades` — 我的交易记录（需登录）
- `POST /trades` — 创建追踪交易
- `PUT /trades/{id}` — 更新交易状态
- `GET /summary` — 盈亏汇总

### 制造 (`/api/v1/manufacturing`)

- `GET /blueprints` — 蓝图搜索
- `POST /analyze` — 蓝图利润分析（支持指定生产星系）
- `GET /analyses` — 历史分析记录
- `GET /top` — 最有利可图的制造项目

### 看板 (`/api/v1/dashboard`)

- `GET /overview` — 市场总览
- `GET /trends/{type_id}` — 价格趋势数据（JSON）
- `GET /trends/{type_id}/chart` — 价格趋势图表（HTML + Chart.js）
- `GET /hot-items` — 热门商品
- `GET /region-summary` — 区域统计

### 价格提醒 (`/api/v1/alerts`)

- `GET /` — 我的告警列表（需登录）
- `POST /` — 创建告警
- `PUT /{id}` — 更新告警
- `DELETE /{id}` — 删除告警

### 物品 & 区域

- `GET /api/v1/items/search?q=` — 物品搜索
- `GET /api/v1/regions/` — 区域列表

## 后台任务

| 任务 | 频率 |
|------|------|
| 市场订单抓取 | 每 5 分钟 |
| 宇宙均价更新 | 每 5 分钟 |
| 套利机会计算 | 每 5 分钟 |
| 热门商品检测 | 每 5 分钟 |
| 价格提醒评估 | 每 5 分钟 |
| 物品名称解析 | 每 5 分钟 |
| 旧数据清理 | 每日 03:07 |

## 数据保留策略

- 48 小时内：保留所有订单快照
- 48 小时–30 天：每小时保留一份
- 30 天以上：每天保留一份

## 测试

```bash
uv run pytest tests/ -v
```

## License

MIT
