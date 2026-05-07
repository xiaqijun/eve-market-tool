"""EVE Market Tool — FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from app.api.v1.router import api_v1_router
from app.tasks.scheduler import init_scheduler, shutdown_scheduler, start_scheduler

_jinja_env = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    auto_reload=False,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_scheduler()
    await start_scheduler()
    yield
    await shutdown_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(
        title="EVE Market Tool",
        description="EVE Online Market Trading Management System",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.include_router(api_v1_router)
    app.mount("/static", StaticFiles(directory="static"), name="static")
    return app


app = create_app()


def _render(template_name: str, request: Request) -> HTMLResponse:
    template = _jinja_env.get_template(template_name)
    return HTMLResponse(template.render(request=request))


@app.get("/")
async def root(request: Request):
    try:
        return _render("dashboard/overview.html", request)
    except Exception as e:
        return {
            "app": "EVE Market Tool",
            "version": "0.1.0",
            "status": "running",
            "template_error": str(e),
        }


@app.get("/arbitrage")
async def arbitrage_page(request: Request):
    return _render("dashboard/arbitrage.html", request)


@app.get("/trading")
async def trading_page(request: Request):
    return _render("dashboard/trading.html", request)


@app.get("/alerts")
async def alerts_page(request: Request):
    return _render("dashboard/alerts.html", request)


@app.get("/manufacturing")
async def manufacturing_page(request: Request):
    return _render("dashboard/manufacturing.html", request)
