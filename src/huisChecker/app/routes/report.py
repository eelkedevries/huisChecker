"""Report routes: full HTML report and PDF export."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from huisChecker.analytics.store import track
from huisChecker.payment.token import validate_token
from huisChecker.report import build_full_report

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

def _has_access(address_id: str, token: str) -> bool:
    if (
        os.getenv("APP_ENV", "development") == "development"
        and os.getenv("REPORT_FREE_ACCESS", "1") == "1"
    ):
        return True
    return validate_token(token) == address_id


@router.get("/report", response_class=HTMLResponse, response_model=None)
async def report(request: Request, id: str = "", token: str = "") -> Response:
    address_id = id.strip()
    if not address_id:
        return templates.TemplateResponse(
            request,
            "report.html",
            context={"report": None, "missing_id": True},
            status_code=400,
        )

    if not _has_access(address_id, token):
        return RedirectResponse(url=f"/checkout/{address_id}", status_code=303)

    full = build_full_report(address_id)
    if full is None:
        raise HTTPException(status_code=404, detail="Adres niet gevonden")

    track("report_viewed", address_id)
    return templates.TemplateResponse(
        request, "report.html", context={"report": full, "token": token}
    )


@router.get("/report.pdf", response_model=None)
async def report_pdf(request: Request, id: str = "", token: str = "") -> Response:
    address_id = id.strip()
    if not address_id:
        raise HTTPException(status_code=400, detail="Adres-id ontbreekt")

    if not _has_access(address_id, token):
        raise HTTPException(status_code=403, detail="Geen toegang")

    full = build_full_report(address_id)
    if full is None:
        raise HTTPException(status_code=404, detail="Adres niet gevonden")

    rendered = templates.get_template("report.html").render(
        request=request, report=full, token=token
    )

    pdf_bytes = _render_pdf(rendered, base_url=str(request.base_url))
    if pdf_bytes is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "PDF-export is niet beschikbaar in deze omgeving. "
                "Installeer `weasyprint` of gebruik 'Printen → Opslaan als PDF' in de browser."
            ),
        )

    track("pdf_downloaded", address_id)
    filename = f"huisChecker-{address_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _render_pdf(html: str, *, base_url: str) -> bytes | None:
    """Return PDF bytes, or None when WeasyPrint (or its system libs) are unavailable."""
    try:
        from weasyprint import HTML  # type: ignore[import-not-found]
    except Exception:
        return None
    try:
        return HTML(string=html, base_url=base_url).write_pdf()
    except Exception:
        return None
