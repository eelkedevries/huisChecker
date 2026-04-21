"""Methodology route."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

router = APIRouter()


@router.get("/methodology", response_class=HTMLResponse)
async def methodology(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "methodology.html")
