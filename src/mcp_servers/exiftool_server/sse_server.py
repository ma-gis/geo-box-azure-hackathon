"""
ExifTool MCP Server with Streamable HTTP Transport

This version uses Streamable HTTP transport compatible with
Microsoft Agent Framework's MCPStreamableHTTPTool.
"""

import subprocess
import json
import structlog
import contextlib
from typing import Dict, Optional
from datetime import datetime

# MCP SDK imports for streamable HTTP server
from mcp.server import Server
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
import uvicorn

logger = structlog.get_logger()

# Create MCP server
mcp_server = Server("exiftool-mcp-server")

# Helper functions (same as before)
def _run_exiftool(args: list[str], file_path: str, timeout: int = 30) -> Optional[Dict]:
    """Run ExifTool and return parsed JSON output"""
    try:
        result = subprocess.run(
            ['exiftool'] + args + [file_path],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode != 0:
            logger.error("exiftool_failed", stderr=result.stderr)
            return None

        if '-json' in args:
            data = json.loads(result.stdout)
            return data[0] if data else None
        else:
            return {'output': result.stdout.strip()}

    except Exception as e:
        logger.error("exiftool_error", error=str(e))
        return None

# Register MCP tools
@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="get_exiftool_version",
            description="Get the installed ExifTool version",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        Tool(
            name="extract_gps",
            description="Extract GPS coordinates from a photo or video file",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the media file"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="extract_all_metadata",
            description="Extract all EXIF/XMP metadata from a media file",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the media file"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="generate_gpx_track",
            description="Generate GPX track from video GPS metadata",
            inputSchema={
                "type": "object",
                "properties": {
                    "video_path": {
                        "type": "string",
                        "description": "Absolute path to the video file"
                    },
                    "track_name": {
                        "type": "string",
                        "description": "Optional name for the GPX track"
                    }
                },
                "required": ["video_path"]
            }
        )
    ]

@mcp_server.list_prompts()
async def list_prompts():
    """List available prompts - required by MCP protocol"""
    # No prompts defined for this server, return empty list
    return []

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    logger.info("mcp_tool_called", tool=name, args=arguments)

    try:
        if name == "get_exiftool_version":
            result = subprocess.run(['exiftool', '-ver'], capture_output=True, text=True)
            version = result.stdout.strip()
            return [TextContent(type="text", text=version)]

        elif name == "extract_gps":
            file_path = arguments.get("file_path")
            data = _run_exiftool([
                '-GPSLatitude', '-GPSLongitude', '-GPSAltitude',
                '-GPSDateTime', '-DateTimeOriginal', '-CreateDate',
                '-n', '-json'
            ], file_path)

            if not data:
                return [TextContent(type="text", text=json.dumps({
                    "error": "Failed to extract metadata",
                    "file_path": file_path
                }))]

            lat = data.get('GPSLatitude')
            lon = data.get('GPSLongitude')

            if lat is None or lon is None:
                return [TextContent(type="text", text=json.dumps({
                    "error": "No GPS coordinates found",
                    "file_path": file_path
                }))]

            gps_data = {
                "latitude": float(lat),
                "longitude": float(lon),
                "altitude": data.get('GPSAltitude'),
                "timestamp": data.get('GPSDateTime') or data.get('DateTimeOriginal') or data.get('CreateDate'),
                "source": "exiftool"
            }

            return [TextContent(type="text", text=json.dumps(gps_data))]

        elif name == "extract_all_metadata":
            file_path = arguments.get("file_path")
            data = _run_exiftool(['-json'], file_path)

            if not data:
                return [TextContent(type="text", text=json.dumps({
                    "error": "Failed to extract metadata"
                }))]

            return [TextContent(type="text", text=json.dumps(data))]

        elif name == "generate_gpx_track":
            video_path = arguments.get("video_path")
            track_name = arguments.get("track_name", "track")

            data = _run_exiftool(['-ee', '-G3', '-a', '-gps*', '-json'], video_path, timeout=60)

            if not data:
                return [TextContent(type="text", text=json.dumps({
                    "error": "Failed to extract GPS track"
                }))]

            return [TextContent(type="text", text=json.dumps({
                "error": "GPX generation not yet fully implemented",
                "raw_data": data
            }))]

        else:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Unknown tool: {name}"
            }))]

    except Exception as e:
        logger.error("tool_call_error", tool=name, error=str(e))
        return [TextContent(type="text", text=json.dumps({
            "error": str(e)
        }))]

# Create MCP session manager
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
import contextlib

session_manager = StreamableHTTPSessionManager(
    app=mcp_server,
    stateless=True,  # Stateless mode for simpler handling
    json_response=False  # Use SSE for responses
)

# MCP endpoint handler - directly use ASGI interface
async def mcp_endpoint(scope, receive, send):
    """Handle MCP streamable HTTP requests (ASGI app)"""
    await session_manager.handle_request(scope, receive, send)

# Lifespan context manager for proper session manager lifecycle
@contextlib.asynccontextmanager
async def lifespan(app):
    """Manage session manager lifecycle"""
    logger.info("starting_mcp_session_manager")
    async with session_manager.run():
        logger.info("mcp_session_manager_ready")
        yield
    logger.info("mcp_session_manager_stopped")

# Health check endpoint
async def health(request):
    """Health check"""
    from starlette.responses import JSONResponse
    try:
        result = subprocess.run(['exiftool', '-ver'], capture_output=True, text=True)
        return JSONResponse({
            "status": "healthy",
            "service": "exiftool-mcp-server",
            "exiftool_version": result.stdout.strip(),
            "transport": "StreamableHTTP"
        })
    except Exception as e:
        return JSONResponse({
            "status": "unhealthy",
            "error": str(e)
        }, status_code=500)

# Create Starlette app
from starlette.routing import Route, Mount
from gateway_middleware import MCPGatewayMiddleware

app = Starlette(
    routes=[
        Mount("/sse", app=mcp_endpoint),  # Mount MCP ASGI app
        Route("/health", endpoint=health),  # Health check
    ],
    lifespan=lifespan  # Use lifespan context manager
)

# Wire in the MCP Gateway middleware (kill-switch, API key auth, rate limit, audit log)
app.add_middleware(MCPGatewayMiddleware)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
