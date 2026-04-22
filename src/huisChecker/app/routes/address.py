"""Address search and free preview routes."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from huisChecker.address.preview import build_preview
from huisChecker.address.search import resolve_address, search_addresses
from huisChecker.analytics.store import track

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

router = APIRouter()


@router.get("/address", response_class=HTMLResponse, response_model=None)
async def address_search(request: Request) -> Response:
    query = request.query_params.get("q", "").strip()
    if not query:
        return templates.TemplateResponse(
            request, "address.html", context={"query": "", "candidates": [], "no_query": True}
        )
    candidates = search_addresses(query)
    track("address_search")
    if len(candidates) == 1:
        return RedirectResponse(url=f"/address/{candidates[0].id}", status_code=303)
    return templates.TemplateResponse(
        request,
        "address.html",
        context={"query": query, "candidates": candidates, "no_query": False},
    )


@router.get("/address/{address_id}", response_class=HTMLResponse)
async def address_preview(request: Request, address_id: str) -> HTMLResponse:
    # Ensure the address is resolved (cache miss will call PDOK and persist).
    resolve_address(address_id)
    preview = build_preview(address_id)
    if preview is not None:
        track("preview_viewed", address_id)
    if preview is None:
        return templates.TemplateResponse(
            request,
            "address.html",
            context={
                "query": address_id,
                "candidates": [],
                "no_query": False,
                "not_found": True,
            },
            status_code=404,
        )
    return templates.TemplateResponse(
        request, "address_preview.html", context={"preview": preview}
    )
