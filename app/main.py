"""EVE Market Tool — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_v1_router
from app.tasks.scheduler import init_scheduler, shutdown_scheduler, start_scheduler


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
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(api_v1_router)
    app.mount("/static", StaticFiles(directory="static"), name="static")
    return app


app = create_app()


@app.get("/")
async def root(request: Request):
    """Dashboard overview page — rendered via Jinja2."""
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path

    env = Environment(
        loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
        cache_size=0,
        auto_reload=False,
    )
    try:
        template = env.get_template("dashboard/overview.html")
        html = template.render(request=request)
        return HTMLResponse(html)
    except Exception as e:
        # Fallback: return JSON if template fails
        return {
            "app": "EVE Market Tool",
            "version": "0.1.0",
            "status": "running",
            "template_error": str(e),
        }


@app.get("/arbitrage")
async def arbitrage_page(request: Request):
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path
    env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / "templates")))
    template = env.get_template("dashboard/arbitrage.html")
    return HTMLResponse(template.render(request=request))


@app.get("/trading")
async def trading_page(request: Request):
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path
    env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / "templates")))
    template = env.get_template("dashboard/trading.html")
    return HTMLResponse(template.render(request=request))


@app.get("/alerts")
async def alerts_page(request: Request):
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path
    env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / "templates")))
    template = env.get_template("dashboard/alerts.html")
    return HTMLResponse(template.render(request=request))


@app.get("/manufacturing")
async def manufacturing_page(request: Request):
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path
    env = Environment(loader=FileSystemLoader(str(Path(__file__).parent / "templates")))
    template = env.get_template("dashboard/manufacturing.html")
    return HTMLResponse(template.render(request=request))
