"""Explore areas routes — province / municipality / postcode4 views."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from huisChecker.explore.service import (
    municipality_list,
    municipality_name,
    postcode4_detail,
    postcode4_list,
    province_list,
    province_name,
)

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

router = APIRouter()


@router.get("/explore", response_class=HTMLResponse)
async def explore(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "explore.html",
        context={"provinces": province_list()},
    )


@router.get("/explore/provincie/{code}", response_class=HTMLResponse)
async def explore_province(request: Request, code: str) -> HTMLResponse:
    municipalities = municipality_list(code)
    if municipalities is None:
        return templates.TemplateResponse(
            request,
            "explore.html",
            context={"provinces": province_list(), "error": "Provincie niet gevonden."},
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "explore_province.html",
        context={
            "province_code": code,
            "province_name": province_name(code),
            "municipalities": municipalities,
        },
    )


@router.get("/explore/gemeente/{code}", response_class=HTMLResponse)
async def explore_municipality(request: Request, code: str) -> HTMLResponse:
    pc4s = postcode4_list(code)
    if pc4s is None:
        return templates.TemplateResponse(
            request,
            "explore.html",
            context={"provinces": province_list(), "error": "Gemeente niet gevonden."},
            status_code=404,
        )
    muni = municipality_name(code)
    province_code = pc4s[0].province_code if pc4s else None
    prov_name = province_name(province_code) if province_code else None
    return templates.TemplateResponse(
        request,
        "explore_municipality.html",
        context={
            "municipality_code": code,
            "municipality_name": muni,
            "province_code": province_code,
            "province_name": prov_name,
            "postcode4s": pc4s,
        },
    )


@router.get("/explore/postcode/{code}", response_class=HTMLResponse)
async def explore_postcode4(request: Request, code: str) -> HTMLResponse:
    area = postcode4_detail(code)
    if area is None:
        return templates.TemplateResponse(
            request,
            "explore.html",
            context={"provinces": province_list(), "error": "Postcodegebied niet gevonden."},
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "explore_postcode4.html",
        context={"area": area},
    )
