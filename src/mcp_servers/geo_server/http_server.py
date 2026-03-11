"""
Geospatial MCP Server (HTTP)

Provides geographic enrichment tools that the GeoBox orchestrator calls after
GPS coordinates have been extracted from a file:

  - reverse_geocode(lat, lon)   → place name, country, city, region  (Nominatim / OSM)
  - get_elevation(lat, lon)     → elevation in meters                 (Open-Elevation API)
  - check_land_or_water(lat, lon) → "land" | "water" | "unknown"      (Nominatim OSM type)

All three external APIs are free and require no API key.
Nominatim requires a User-Agent header identifying the project (OSM policy).
"""

import os
import structlog
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from gateway_middleware import MCPGatewayMiddleware

logger = structlog.get_logger()

# External API base URLs (free, no auth required)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"

# OSM policy requires a descriptive User-Agent
NOMINATIM_HEADERS = {
    "User-Agent": "GeoBox/1.0 (AI Dev Days 2026 Hackathon; github.com/geobox-azure)",
    "Accept-Language": "en",
}

# Shared timeout for all external calls (seconds)
HTTP_TIMEOUT = float(os.getenv("GEO_HTTP_TIMEOUT", "10"))

app = FastAPI(
    title="GeoBox Geospatial MCP Server",
    description="Geographic enrichment tools: reverse geocoding, elevation, land/water detection",
    version="1.0.0"
)

# Wire in the MCP Gateway middleware (kill-switch, API key auth, rate limit, audit log)
app.add_middleware(MCPGatewayMiddleware)


# ── Request/Response models ────────────────────────────────────────────────────

class GeoRequest(BaseModel):
    lat: float
    lon: float


class ToolResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None


# ── OSM type → land/water mapping ─────────────────────────────────────────────

_WATER_OSM_TYPES = frozenset({
    "water", "bay", "river", "lake", "ocean", "sea", "strait",
    "reservoir", "pond", "lagoon", "fjord", "sound", "inlet",
})

_LAND_OSM_CATEGORIES = frozenset({
    "boundary", "place", "natural", "landuse", "highway",
    "building", "amenity", "shop", "tourism", "leisure",
})


def _classify_land_or_water(nominatim_data: dict) -> str:
    """Classify a Nominatim result as land, water, or unknown."""
    osm_type = nominatim_data.get("type", "")
    category = nominatim_data.get("category", "")

    if osm_type in _WATER_OSM_TYPES:
        return "water"
    if category in _LAND_OSM_CATEGORIES:
        return "land"
    # Fall back: any result with an address is almost certainly land
    if nominatim_data.get("address"):
        return "land"
    return "unknown"


# ── Internal Nominatim helper (reused by geocode + land/water) ─────────────────

async def _nominatim_reverse(lat: float, lon: float) -> dict:
    """Call Nominatim reverse geocoding and return raw JSON."""
    async with httpx.AsyncClient(headers=NOMINATIM_HEADERS, timeout=HTTP_TIMEOUT) as client:
        response = await client.get(
            NOMINATIM_URL,
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 10},
        )
        response.raise_for_status()
        return response.json()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check — confirms server is running (no external call needed)."""
    return {"status": "healthy", "service": "geo-mcp-server"}


@app.get("/tools")
async def list_tools():
    """List available geospatial MCP tools."""
    return {
        "tools": [
            {
                "name": "reverse_geocode",
                "description": "Get place name, country, city, and region for GPS coordinates",
                "endpoint": "/tools/reverse_geocode",
                "method": "POST",
                "parameters": {"lat": "float", "lon": "float"},
            },
            {
                "name": "reverse_geocode_full",
                "description": "Get place name, country, city, region, AND land/water classification in one call (preferred over calling reverse_geocode + check_land_or_water separately)",
                "endpoint": "/tools/reverse_geocode_full",
                "method": "POST",
                "parameters": {"lat": "float", "lon": "float"},
            },
            {
                "name": "get_elevation",
                "description": "Get terrain elevation in meters for GPS coordinates",
                "endpoint": "/tools/get_elevation",
                "method": "POST",
                "parameters": {"lat": "float", "lon": "float"},
            },
            {
                "name": "check_land_or_water",
                "description": "Determine if GPS coordinates are on land or water",
                "endpoint": "/tools/check_land_or_water",
                "method": "POST",
                "parameters": {"lat": "float", "lon": "float"},
            },
        ]
    }


@app.post("/tools/reverse_geocode", response_model=ToolResponse)
async def reverse_geocode(request: GeoRequest):
    """
    Reverse-geocode GPS coordinates to a human-readable place name.

    Uses OpenStreetMap Nominatim (free, no API key required).
    Returns display name, country, city/town/village, and region/state.
    """
    try:
        logger.info("reverse_geocode_called", lat=request.lat, lon=request.lon)

        data = await _nominatim_reverse(request.lat, request.lon)

        addr = data.get("address", {})
        city = (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("hamlet")
            or addr.get("suburb")
            or ""
        )
        display_name = data.get("display_name", "")

        result = {
            "display_name": display_name[:200],      # cap length for Box field
            "country": addr.get("country", ""),
            "country_code": addr.get("country_code", "").upper(),
            "city": city,
            "region": addr.get("state") or addr.get("province") or addr.get("county") or "",
            "postcode": addr.get("postcode", ""),
            "osm_type": data.get("type", ""),
        }

        logger.info("reverse_geocode_success",
                   lat=request.lat, lon=request.lon,
                   country=result["country"], city=result["city"])

        return ToolResponse(success=True, data=result)

    except httpx.TimeoutException:
        logger.warning("reverse_geocode_timeout", lat=request.lat, lon=request.lon)
        return ToolResponse(
            success=False,
            data={"display_name": "", "country": "", "city": "", "region": ""},
            error="Nominatim request timed out",
        )
    except Exception as e:
        logger.error("reverse_geocode_failed", lat=request.lat, lon=request.lon, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/reverse_geocode_full", response_model=ToolResponse)
async def reverse_geocode_full(request: GeoRequest):
    """
    Combined reverse geocoding + land/water classification in a single Nominatim call.

    Returns everything from reverse_geocode plus land_or_water classification.
    Use this instead of calling reverse_geocode and check_land_or_water separately
    to respect OSM's 1 request/second rate limit.
    """
    try:
        logger.info("reverse_geocode_full_called", lat=request.lat, lon=request.lon)

        data = await _nominatim_reverse(request.lat, request.lon)

        addr = data.get("address", {})
        city = (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("hamlet")
            or addr.get("suburb")
            or ""
        )
        display_name = data.get("display_name", "")
        classification = _classify_land_or_water(data)

        result = {
            "display_name": display_name[:200],
            "country": addr.get("country", ""),
            "country_code": addr.get("country_code", "").upper(),
            "city": city,
            "region": addr.get("state") or addr.get("province") or addr.get("county") or "",
            "postcode": addr.get("postcode", ""),
            "osm_type": data.get("type", ""),
            "osm_category": data.get("category", ""),
            "land_or_water": classification,
        }

        logger.info("reverse_geocode_full_success",
                   lat=request.lat, lon=request.lon,
                   country=result["country"], city=result["city"],
                   land_or_water=classification)

        return ToolResponse(success=True, data=result)

    except httpx.TimeoutException:
        logger.warning("reverse_geocode_full_timeout", lat=request.lat, lon=request.lon)
        return ToolResponse(
            success=False,
            data={"display_name": "", "country": "", "city": "", "region": "",
                  "land_or_water": "unknown", "osm_type": "", "osm_category": ""},
            error="Nominatim request timed out",
        )
    except Exception as e:
        logger.error("reverse_geocode_full_failed", lat=request.lat, lon=request.lon, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_elevation", response_model=ToolResponse)
async def get_elevation(request: GeoRequest):
    """
    Get terrain elevation in meters for GPS coordinates.

    Uses Open-Elevation API (free, no API key required).
    Returns elevation_m as a float, or null if unavailable.
    """
    try:
        logger.info("get_elevation_called", lat=request.lat, lon=request.lon)

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(
                ELEVATION_URL,
                params={"locations": f"{request.lat},{request.lon}"},
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])
        elevation_m = results[0].get("elevation") if results else None

        logger.info("get_elevation_success",
                   lat=request.lat, lon=request.lon, elevation_m=elevation_m)

        return ToolResponse(
            success=True,
            data={"elevation_m": elevation_m},
        )

    except httpx.TimeoutException:
        logger.warning("get_elevation_timeout", lat=request.lat, lon=request.lon)
        return ToolResponse(
            success=False,
            data={"elevation_m": None},
            error="Elevation API request timed out",
        )
    except Exception as e:
        logger.error("get_elevation_failed", lat=request.lat, lon=request.lon, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/check_land_or_water", response_model=ToolResponse)
async def check_land_or_water(request: GeoRequest):
    """
    Determine whether GPS coordinates are on land or water.

    Uses OpenStreetMap Nominatim to classify the location type.
    Returns "land", "water", or "unknown".
    """
    try:
        logger.info("check_land_or_water_called", lat=request.lat, lon=request.lon)

        data = await _nominatim_reverse(request.lat, request.lon)
        classification = _classify_land_or_water(data)

        logger.info("check_land_or_water_success",
                   lat=request.lat, lon=request.lon,
                   classification=classification,
                   osm_type=data.get("type", ""))

        return ToolResponse(
            success=True,
            data={
                "classification": classification,
                "osm_type": data.get("type", ""),
                "osm_category": data.get("category", ""),
            },
        )

    except httpx.TimeoutException:
        logger.warning("check_land_or_water_timeout", lat=request.lat, lon=request.lon)
        return ToolResponse(
            success=False,
            data={"classification": "unknown", "osm_type": "", "osm_category": ""},
            error="Nominatim request timed out",
        )
    except Exception as e:
        logger.error("check_land_or_water_failed", lat=request.lat, lon=request.lon, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8082"))
    uvicorn.run(app, host="0.0.0.0", port=port)
