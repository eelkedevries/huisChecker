"""Address preview route."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

router = APIRouter()


@router.get("/address", response_class=HTMLResponse)
async def address_preview(request: Request) -> HTMLResponse:
    query = request.query_params.get("q", "")
    return templates.TemplateResponse(request, "address.html", context={"query": query})
