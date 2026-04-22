"""Report routes: full HTML report and PDF export."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from huisChecker.report import build_full_report

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


@router.get("/report", response_class=HTMLResponse, response_model=None)
async def report(request: Request) -> Response:
    address_id = request.query_params.get("id", "").strip()
    if not address_id:
        return templates.TemplateResponse(
            request,
            "report.html",
            context={"report": None, "missing_id": True},
            status_code=400,
        )
    full = build_full_report(address_id)
    if full is None:
        raise HTTPException(status_code=404, detail="Adres niet gevonden")
    return templates.TemplateResponse(
        request, "report.html", context={"report": full}
    )


@router.get("/report.pdf", response_model=None)
async def report_pdf(request: Request) -> Response:
    address_id = request.query_params.get("id", "").strip()
    if not address_id:
        raise HTTPException(status_code=400, detail="Adres-id ontbreekt")
    full = build_full_report(address_id)
    if full is None:
        raise HTTPException(status_code=404, detail="Adres niet gevonden")

    rendered = templates.get_template("report.html").render(
        request=request, report=full
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
