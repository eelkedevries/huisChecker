"""Map layer endpoints.

Read-only JSON API used by the shared map partial. Kept as thin wrappers
over `huisChecker.layers.service` so tests can call the service directly.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from huisChecker.layers.service import (
    available_keys,
    layer_metadata,
    load_styled_geojson,
    registry_payload,
)

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/layers.json")
async def layers_index(keys: str | None = None) -> JSONResponse:
    selected = _parse_keys(keys) if keys else None
    try:
        payload = registry_payload(selected)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse({"layers": payload, "available": list(available_keys())})


@router.get("/layers/{key}.json")
async def layer_info(key: str) -> JSONResponse:
    try:
        return JSONResponse(layer_metadata(key))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/layers/{key}.geojson")
async def layer_geojson(key: str) -> JSONResponse:
    try:
        data = load_styled_geojson(key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if data is None:
        raise HTTPException(status_code=404, detail=f"no data for layer: {key}")
    return JSONResponse(data)


def _parse_keys(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())
