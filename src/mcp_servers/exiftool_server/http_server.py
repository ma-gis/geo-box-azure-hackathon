"""
HTTP wrapper for ExifTool MCP Server

This wrapper allows the MCP server to be accessed over HTTP (for Azure Container Apps)
instead of stdio. It provides a REST API that translates HTTP requests to MCP tool calls.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import structlog

# Import the MCP tools
from server import extract_gps, extract_all_metadata, generate_gpx_track, get_exiftool_version

logger = structlog.get_logger()

app = FastAPI(
    title="ExifTool MCP Server (HTTP)",
    description="HTTP API for ExifTool MCP tools",
    version="1.0.0"
)

# Request/Response models
class ExtractGPSRequest(BaseModel):
    file_path: str

class ExtractAllMetadataRequest(BaseModel):
    file_path: str

class GenerateGPXRequest(BaseModel):
    video_path: str
    track_name: Optional[str] = None

class ToolResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None

# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        version = get_exiftool_version()
        return {
            "status": "healthy",
            "service": "exiftool-mcp-server",
            "exiftool_version": version
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

# MCP tool endpoints
@app.post("/tools/extract_gps", response_model=ToolResponse)
async def api_extract_gps(request: ExtractGPSRequest):
    """Extract GPS coordinates from a file"""
    try:
        logger.info("http_extract_gps_called", file_path=request.file_path)
        result = extract_gps(request.file_path)

        # Check if there was an error in the result
        if 'error' in result:
            return ToolResponse(
                success=False,
                data=result,
                error=result['error']
            )

        return ToolResponse(success=True, data=result)

    except Exception as e:
        logger.error("http_extract_gps_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/extract_all_metadata", response_model=ToolResponse)
async def api_extract_all_metadata(request: ExtractAllMetadataRequest):
    """Extract all metadata from a file"""
    try:
        logger.info("http_extract_all_metadata_called", file_path=request.file_path)
        result = extract_all_metadata(request.file_path)

        if 'error' in result:
            return ToolResponse(
                success=False,
                data=result,
                error=result['error']
            )

        return ToolResponse(success=True, data=result)

    except Exception as e:
        logger.error("http_extract_all_metadata_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tools/generate_gpx_track", response_model=ToolResponse)
async def api_generate_gpx_track(request: GenerateGPXRequest):
    """Generate GPX track from video"""
    try:
        logger.info("http_generate_gpx_track_called", video_path=request.video_path)
        result = generate_gpx_track(request.video_path, request.track_name)

        if 'error' in result:
            return ToolResponse(
                success=False,
                data=result,
                error=result['error']
            )

        return ToolResponse(success=True, data=result)

    except Exception as e:
        logger.error("http_generate_gpx_track_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tools/get_exiftool_version")
async def api_get_exiftool_version():
    """Get ExifTool version"""
    try:
        version = get_exiftool_version()
        return ToolResponse(
            success=True,
            data={"version": version}
        )
    except Exception as e:
        logger.error("http_get_exiftool_version_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tools")
async def list_tools():
    """List available MCP tools"""
    return {
        "tools": [
            {
                "name": "get_exiftool_version",
                "description": "Get the installed ExifTool version",
                "endpoint": "/tools/get_exiftool_version",
                "method": "GET"
            },
            {
                "name": "extract_gps",
                "description": "Extract GPS coordinates from a photo or video file",
                "endpoint": "/tools/extract_gps",
                "method": "POST",
                "parameters": {"file_path": "string"}
            },
            {
                "name": "extract_all_metadata",
                "description": "Extract all EXIF/XMP metadata from a media file",
                "endpoint": "/tools/extract_all_metadata",
                "method": "POST",
                "parameters": {"file_path": "string"}
            },
            {
                "name": "generate_gpx_track",
                "description": "Generate a GPX track file from video GPS metadata",
                "endpoint": "/tools/generate_gpx_track",
                "method": "POST",
                "parameters": {
                    "video_path": "string",
                    "track_name": "string (optional)"
                }
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
