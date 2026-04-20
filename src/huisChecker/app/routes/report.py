"""Report route."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

router = APIRouter()


@router.get("/report", response_class=HTMLResponse)
async def report(request: Request) -> HTMLResponse:
    address_id = request.query_params.get("id", "")
    return templates.TemplateResponse("report.html", {"request": request, "address_id": address_id})
