"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from huisChecker.app.routes import address, explore, home, methodology, report
from huisChecker.app.routes import map as map_routes

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(title="huisChecker", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(home.router)
app.include_router(explore.router)
app.include_router(address.router)
app.include_router(report.router)
app.include_router(methodology.router)
app.include_router(map_routes.router)
