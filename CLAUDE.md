# EVE Market Tool

EVE Online market trading management system. FastAPI + PostgreSQL async stack.

## Commands

```bash
# Install dependencies
uv venv && uv pip install -e ".[dev]"

# Run dev server
uv run uvicorn app.main:app --reload

# Database migrations
uv run alembic upgrade head

# Tests
uv run pytest tests/ -v

# Lint
uv run ruff check app/
```

## Architecture

- **app/api/v1/endpoints/** — FastAPI route handlers (8 modules, ~29 routes)
- **app/api/deps.py** — Shared dependencies: `get_db`, `get_current_user`, `get_current_user_optional`
- **app/core/** — Config (pydantic-settings), DB engine (async SQLAlchemy), ESI client (httpx + token bucket + ETag cache), security (JWT + EVE SSO)
- **app/models/** — SQLAlchemy ORM models (14 models)
- **app/schemas/** — Pydantic v2 request/response schemas
- **app/services/** — Business logic (arbitrage, trading, manufacturing, market fetcher, dashboard, alerts, SDE loader)
- **app/repositories/** — Data access layer (DAO)
- **app/tasks/** — APScheduler periodic jobs (7 jobs, 5-min interval)
- **app/templates/** — Jinja2 + htmx + Alpine.js + Chart.js frontend
- **scripts/** — Deploy and one-time utility scripts (gitignored)
- **tests/unit/** — Unit tests (JWT, ESI client, manufacturing)

## Key patterns

- All DB access is async (asyncpg + SQLAlchemy 2.0 async sessions)
- ESI client has built-in rate limiting (token bucket, 12000 tokens/5min), ETag caching, auto-pagination, and tenacity retry
- Services use raw SQL (via `sqlalchemy.text`) for complex aggregations, ORM for simple CRUD
- Frontend is server-rendered Jinja2 with htmx for partial updates and Alpine.js for interactivity
- Chart.js for price trend charts (via `/api/v1/dashboard/trends/{id}/chart` HTML endpoint)
- Jinja2 `Environment` is a module-level singleton in `app/main.py`
- Manufacturing cost uses real ESI industry cost indices (`/industry/systems/`), 1-hour cache
- Arbitrage pagination is DB-level (COUNT + OFFSET/LIMIT), not in-memory

## Authentication

EVE SSO OAuth2 flow: `/api/v1/auth/login` → SSO → `/api/v1/auth/callback` → JWT issued.
Protected endpoints use `get_current_user` dependency (reads `Authorization: Bearer <token>`).
Public endpoints: dashboard, arbitrage list, items search, trading opportunities.

## Config

Settings loaded from `.env` via pydantic-settings in `app/core/config.py`. Key vars:
- `DATABASE_URL` — PostgreSQL async connection string
- `ESI_USER_AGENT` — Required by ESI API (set contact email)
- `SECRET_KEY` — JWT signing key
- `EVE_CLIENT_ID` / `EVE_CLIENT_SECRET` / `EVE_CALLBACK_URL` — EVE SSO (optional)

## Trade hub regions

The 5 tracked regions: Jita (10000002), Amarr (10000043), Dodixie (10000032), Rens (10000030), Hek (10000042). Defined in `app/core/config.py` as `hub_region_ids`.

## Database

PostgreSQL 17 + Alembic migrations. Key tables:
- `market_order_snapshot` — Raw ESI order data (partitioned by fetch time)
- `latest_fetch_cache` — Points to most recent fetch per region
- `hot_item_cache` — Pre-computed volume anomalies
- `arbitrage_opportunity` — Cross-region arbitrage results
- `station_trade` — User trade tracking
- `price_alert` — User price alerts
- `blueprint` / `blueprint_material` — Manufacturing data from SDE

## Conventions

- Python 3.12+, type hints everywhere
- Ruff for linting (line length 100)
- No comments unless the "why" is non-obvious
- Commit messages: conventional commits style (feat/fix/chore)
