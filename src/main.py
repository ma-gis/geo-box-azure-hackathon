"""
GeoBox - AI-Powered Geospatial Metadata Intelligence for Box

Main FastAPI application with Microsoft Agent Framework and MCP integration.
Uses the orchestrator agent for GPS extraction, with automatic fallback to
direct extraction if the orchestrator is unavailable.
"""

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers
import structlog
from typing import Dict, Optional
import os
import hmac
import hashlib
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
import uuid

from src.agents.orchestrator_agent import GeoBoxOrchestrator
from src.agents.extraction_agent import ExtractionAgent  # Fallback only
from src.box_client import BoxClientManager
from src.config import settings

# Initialize structured logging
logger = structlog.get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="GeoBox API",
    description="AI-Powered Geospatial Metadata Intelligence with Multi-Agent Architecture",
    version="2.0.0"
)

# Initialize Box client
box_manager = BoxClientManager()

# Initialize fallback extraction agent (for non-agent operations)
extraction_agent_fallback = ExtractionAgent()

# Orchestrator will be initialized as singleton on startup
orchestrator: Optional[GeoBoxOrchestrator] = None

# Processing statistics (module-level counters)
stats = {
    "total_processed": 0,
    "gps_found": 0,
    "gps_missing": 0,
    "errors": 0,
    "last_update_time": None
}

@app.on_event("startup")
async def startup_event():
    """Initialize orchestrator agent on startup"""
    global orchestrator

    # Validate required configuration
    missing_config = []
    if not settings.AZURE_OPENAI_API_KEY:
        missing_config.append("AZURE_OPENAI_API_KEY")
    if not settings.AZURE_OPENAI_ENDPOINT:
        missing_config.append("AZURE_OPENAI_ENDPOINT")
    if not settings.AZURE_OPENAI_DEPLOYMENT_NAME:
        missing_config.append("AZURE_OPENAI_DEPLOYMENT_NAME")

    if missing_config:
        logger.warning("missing_configuration",
                      fields=missing_config,
                      message="Agent Framework mode will be unavailable")

    # Get MCP server URL from environment
    mcp_exiftool_url = os.getenv("MCP_EXIFTOOL_URL", "http://geobox-mcp-exiftool-dev/sse")
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")

    logger.info("startup_event",
               mcp_url=mcp_exiftool_url,
               deployment=deployment_name,
               orchestrator_available=not missing_config)

    # Only initialize orchestrator if config is available
    if missing_config:
        logger.warning("orchestrator_disabled_due_to_missing_config",
                      missing=missing_config,
                      fallback_mode="enabled")
        orchestrator = None
        return

    try:
        orchestrator = GeoBoxOrchestrator(
            mcp_exiftool_url=mcp_exiftool_url,
            azure_openai_deployment=deployment_name,
        )
        await orchestrator.__aenter__()
        logger.info("orchestrator_initialized_successfully")
    except Exception as e:
        logger.error("orchestrator_initialization_failed",
                    error=str(e),
                    fallback_mode="enabled")
        # Continue without orchestrator - will use fallback mode
        orchestrator = None

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup orchestrator on shutdown"""
    global orchestrator

    if orchestrator:
        logger.info("shutting_down_orchestrator")
        try:
            await orchestrator.__aexit__(None, None, None)
        except Exception as e:
            logger.error("orchestrator_shutdown_error", error=str(e))

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "GeoBox",
        "version": "2.0.0 (Week 3 - Agent Framework)",
        "status": "running",
        "description": "AI-Powered Geospatial Metadata Intelligence with Multi-Agent Architecture",
        "architecture": {
            "orchestrator": "Microsoft Agent Framework",
            "mcp_servers": ["ExifTool MCP Server"],
            "agents": ["GeoBox Orchestrator", "Extraction Agent (fallback)"]
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check orchestrator health
        orchestrator_health = {}
        if orchestrator:
            orchestrator_health = await orchestrator.health_check()
        else:
            orchestrator_health = {
                'status': 'not_initialized',
                'fallback_mode': True
            }

        # Check ExifTool availability (fallback)
        exiftool_version = extraction_agent_fallback.get_exiftool_version()

        # Check Box connectivity
        box_status = box_manager.check_connection()

        return {
            "status": "healthy",
            "mode": "agent_framework" if orchestrator else "fallback",
            "orchestrator": orchestrator_health,
            "exiftool_version_fallback": exiftool_version,
            "box_connected": box_status,
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

def _validate_box_signature(body: bytes, headers: Headers) -> bool:
    """
    Validate Box webhook signature using HMAC-SHA256.

    Box signs webhooks by computing:
        base64(HMAC-SHA256(key, delivery_timestamp + body_bytes))

    Returns True if the signature is valid (or if no key is configured).
    Returns False if a key is configured but the signature does not match.

    Box sends `box-signature-primary` (and optionally `box-signature-secondary`
    for key rotation). We accept if either matches.
    """
    key = settings.BOX_WEBHOOK_SIGNATURE_KEY
    if not key:
        # No key configured — skip validation (backward compatible)
        return True

    timestamp = headers.get("box-delivery-timestamp", "")
    sig_primary = headers.get("box-signature-primary", "")
    sig_secondary = headers.get("box-signature-secondary", "")

    if not timestamp:
        logger.warning("webhook_signature_missing_timestamp")
        return False

    # Compute expected HMAC over (delivery_timestamp + body_bytes)
    message = timestamp.encode() + body
    mac = hmac.new(key.encode(), message, hashlib.sha256)
    expected = base64.b64encode(mac.digest()).decode()

    if sig_primary and hmac.compare_digest(sig_primary, expected):
        return True
    if sig_secondary and hmac.compare_digest(sig_secondary, expected):
        return True

    return False


@app.post("/webhook/box")
async def handle_box_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle Box webhook events for file uploads
    Triggers GPS extraction and metadata enrichment using Agent Framework
    """
    try:
        # Read raw body first — HMAC validation requires the original bytes
        body_bytes = await request.body()

        # Validate Box webhook signature (no-op if key not configured)
        if not _validate_box_signature(body_bytes, request.headers):
            logger.warning("webhook_signature_invalid",
                          path=str(request.url),
                          client=str(request.client))
            # Return 200 so Box doesn't retry — but skip processing
            return {"status": "rejected", "reason": "invalid_signature"}

        # Parse payload from the already-read bytes
        payload = json.loads(body_bytes)

        # Generate request ID for correlation across webhook and background task
        request_id = str(uuid.uuid4())

        logger.info("webhook_received",
                   request_id=request_id,
                   event_type=payload.get('trigger'),
                   source_type=payload.get('source', {}).get('type'),
                   file_name=payload.get('source', {}).get('name'),
                   file_id=payload.get('source', {}).get('id'))

        # Verify it's a file upload event
        if payload.get('trigger') != 'FILE.UPLOADED':
            return {"status": "ignored", "reason": "Not a file upload event"}

        # Extract file info
        file_info = payload.get('source', {})
        file_id = file_info.get('id')
        file_name = file_info.get('name', '')

        # Extract file extension from filename
        file_type = ''
        if file_name and '.' in file_name:
            file_type = file_name.rsplit('.', 1)[-1].lower()
        else:
            file_type = file_info.get('extension', '').lower()

        # Check if file type is supported
        supported_types = ['jpg', 'jpeg', 'png', 'heic', 'mp4', 'mov', 'avi']

        logger.info("file_type_detected",
                   request_id=request_id,
                   file_name=file_name,
                   file_type=file_type,
                   supported=file_type in supported_types)

        if file_type not in supported_types:
            logger.info("unsupported_file_type",
                       request_id=request_id,
                       file_name=file_name,
                       file_type=file_type)
            return {"status": "skipped", "reason": f"Unsupported file type: {file_type}"}

        # Process in background to avoid webhook timeout
        background_tasks.add_task(
            process_file,
            request_id=request_id,
            file_id=file_id,
            file_name=file_name,
            file_type=file_type
        )

        return {
            "status": "accepted",
            "file_id": file_id,
            "file_name": file_name,
            "message": "Processing started (Agent Framework mode)" if orchestrator else "Processing started (fallback mode)"
        }

    except Exception as e:
        logger.error("webhook_processing_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

def _build_box_metadata(result: Dict, geo: Optional[Dict] = None) -> Dict:
    """
    Convert a structured orchestrator result into a Box metadata dict.

    Rules:
    - No underscores in field keys (Box removes them automatically)
    - validationstatus must be an array (MultiSelect field)
    - Numeric fields must be floats

    Args:
        result: Parsed orchestrator result (from _parse_agent_response)
        geo:    Optional geo enrichment dict (from _enrich_with_geo)
    """
    gps_found = result.get("gps_found", False)
    valid = result.get("valid", False)
    parse_success = result.get("success", False)

    if not parse_success:
        status = ["error"]
    elif gps_found and valid:
        status = ["valid"]
    elif gps_found:
        status = ["processed"]  # GPS found but failed validation
    else:
        status = ["no_gps"]

    # Build ainotes: combine agent notes with geo enrichment summary
    agent_notes = result.get("notes", "")
    geo_notes = _build_geo_notes(geo or {})
    combined_notes = f"{agent_notes} {geo_notes}".strip()

    metadata: Dict = {
        "validationstatus": status,
        "processingdate": datetime.now(timezone.utc).isoformat(),
        "ainotes": combined_notes[:500],
    }

    if result.get("confidence") is not None:
        metadata["confidence"] = float(result["confidence"])

    if gps_found:
        if result.get("latitude") is not None:
            metadata["latitude"] = float(result["latitude"])
        if result.get("longitude") is not None:
            metadata["longitude"] = float(result["longitude"])
        if result.get("altitude") is not None:
            metadata["altitude"] = float(result["altitude"])
        if result.get("gps_timestamp"):
            metadata["gpstimestamp"] = str(result["gps_timestamp"])

    return metadata


def _build_geo_notes(geo: Optional[Dict]) -> str:
    """
    Build a compact geo enrichment summary to embed in ainotes.

    Keeps all geo data visible in Box without requiring new template fields.
    Example: "Location: San Francisco, CA, US. Terrain: land. Elevation: 16m."
    """
    if not geo:
        return ""

    parts = []

    city = geo.get("city", "")
    region = geo.get("region", "")
    country = geo.get("country", "")
    location_parts = [p for p in [city, region, country] if p]
    if location_parts:
        parts.append(f"Location: {', '.join(location_parts)}.")

    land_or_water = geo.get("land_or_water", "")
    if land_or_water and land_or_water != "unknown":
        parts.append(f"Terrain: {land_or_water}.")

    elevation_m = geo.get("elevation_m")
    if elevation_m is not None:
        parts.append(f"Elevation: {elevation_m:.0f}m.")

    return " ".join(parts)


async def process_file(request_id: str, file_id: str, file_name: str, file_type: str):
    """
    Background task to process uploaded file using Agent Framework:
    1. Download from Box
    2. Use Orchestrator Agent to extract & validate GPS via MCP
    3. Write metadata back to Box
    """
    temp_path = None
    stats["total_processed"] += 1
    stats["last_update_time"] = datetime.now(timezone.utc).isoformat()

    try:
        logger.info("processing_started",
                   request_id=request_id,
                   file_id=file_id,
                   file_name=file_name,
                   mode="agent_framework" if orchestrator else "fallback")

        # Step 1: Download file from Box
        safe_name = Path(file_name).name  # Strip any directory components
        temp_path = Path("/tmp/geobox") / f"{file_id}_{safe_name}"
        temp_path.parent.mkdir(parents=True, exist_ok=True)

        box_manager.download_file(file_id, str(temp_path))
        logger.info("file_downloaded", request_id=request_id, file_id=file_id, path=str(temp_path))

        # Step 2: Process with Orchestrator Agent (or fallback)
        if orchestrator:
            # AGENT FRAMEWORK MODE: Use orchestrator + MCP
            result = await orchestrator.process_file(
                file_path=str(temp_path),
                file_name=file_name,
                file_type=file_type
            )

            logger.info("orchestrator_processing_complete",
                       request_id=request_id,
                       file_id=file_id,
                       success=result.get('success'),
                       gps_found=result.get('gps_found'))

            # Parse agent result
            if not result.get('success'):
                logger.error("orchestrator_processing_failed",
                            request_id=request_id,
                            file_id=file_id,
                            error=result.get('error'))

                box_manager.apply_metadata(file_id, {
                    'validationstatus': ['error'],
                    'ainotes': f"Agent processing error: {result.get('error')}",
                    'processingdate': extraction_agent_fallback.get_timestamp()
                })
                return

            if not result.get('gps_found'):
                logger.warning("no_gps_found_by_agent", request_id=request_id, file_id=file_id)
                stats["gps_missing"] += 1

                box_manager.apply_metadata(file_id, {
                    'validationstatus': ['no_gps'],
                    'ainotes': 'No GPS data found in file (Agent Framework)',
                    'processingdate': extraction_agent_fallback.get_timestamp()
                })
                return

            # Build and apply real Box metadata from structured agent result + geo enrichment
            metadata = _build_box_metadata(result, geo=result.get("geo"))
            box_manager.apply_metadata(file_id, metadata)
            stats["gps_found"] += 1

            logger.info("metadata_applied_from_agent_result",
                       request_id=request_id,
                       file_id=file_id,
                       status=metadata.get("validationstatus"),
                       lat=metadata.get("latitude"),
                       lon=metadata.get("longitude"),
                       confidence=metadata.get("confidence"))

        else:
            # FALLBACK MODE: Use direct agents (Week 1/2 implementation)
            logger.info("using_fallback_mode", request_id=request_id, file_id=file_id)

            gps_data = extraction_agent_fallback.extract_gps(str(temp_path))

            if not gps_data:
                logger.warning("no_gps_found_fallback", request_id=request_id, file_id=file_id)
                stats["gps_missing"] += 1

                box_manager.apply_metadata(file_id, {
                    'validationstatus': ['no_gps'],
                    'ainotes': 'No GPS data found in file (fallback mode)',
                    'processingdate': extraction_agent_fallback.get_timestamp()
                })
                return

            # Apply GPS metadata (fallback mode - no AI validation)
            metadata = {
                'latitude': float(gps_data['latitude']),
                'longitude': float(gps_data['longitude']),
                'validationstatus': ['valid'],  # No validation in fallback
                'confidence': 1.0,  # Full confidence without AI
                'ainotes': 'Processed in fallback mode (no AI validation)',
                'processingdate': extraction_agent_fallback.get_timestamp()
            }

            if gps_data.get('altitude') is not None:
                metadata['altitude'] = float(gps_data['altitude'])

            if gps_data.get('timestamp'):
                metadata['gpstimestamp'] = str(gps_data['timestamp'])

            box_manager.apply_metadata(file_id, metadata)
            stats["gps_found"] += 1
            logger.info("metadata_applied_fallback", request_id=request_id, file_id=file_id)

        logger.info("processing_completed", request_id=request_id, file_id=file_id)

    except Exception as e:
        stats["errors"] += 1
        logger.error("processing_failed",
                    request_id=request_id,
                    file_id=file_id,
                    error=str(e),
                    exc_info=True)

        # Try to write error to Box metadata
        try:
            box_manager.apply_metadata(file_id, {
                'validationstatus': ['error'],
                'ainotes': f'Processing error: {str(e)}',
                'processingdate': extraction_agent_fallback.get_timestamp()
            })
        except:
            pass

    finally:
        # Clean up temporary file
        if temp_path and temp_path.exists():
            temp_path.unlink()
            logger.debug("temp_file_cleaned", request_id=request_id, path=str(temp_path))

@app.get("/stats")
async def get_stats():
    """Get processing statistics"""
    return {
        "total_processed": stats["total_processed"],
        "gps_found": stats["gps_found"],
        "gps_missing": stats["gps_missing"],
        "errors": stats["errors"],
        "last_update_time": stats["last_update_time"],
        "mode": "agent_framework" if orchestrator else "fallback"
    }

@app.get("/debug/orchestrator")
async def debug_orchestrator():
    """Debug orchestrator status"""
    if not orchestrator:
        return {
            "status": "not_initialized",
            "message": "Orchestrator not available - running in fallback mode"
        }

    try:
        health = await orchestrator.health_check()
        return {
            "status": "initialized",
            "health": health
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
