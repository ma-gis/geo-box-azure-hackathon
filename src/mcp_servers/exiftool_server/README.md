# ExifTool MCP Server

A Model Context Protocol (MCP) server that exposes ExifTool GPS extraction functionality as tools for AI agents.

## Features

This MCP server provides the following tools:

### 1. `get_exiftool_version()`
Returns the installed ExifTool version.

**Example:**
```json
{
  "tool": "get_exiftool_version",
  "arguments": {}
}
```

### 2. `extract_gps(file_path: str)`
Extracts GPS coordinates from photo or video files.

**Arguments:**
- `file_path` (string): Absolute path to the media file

**Returns:**
```json
{
  "latitude": 37.7749,
  "longitude": -122.4194,
  "altitude": 10.5,
  "timestamp": "2024-01-15T10:30:00Z",
  "source": "exiftool",
  "file_path": "/path/to/file.jpg"
}
```

### 3. `extract_all_metadata(file_path: str)`
Extracts all EXIF/XMP metadata from a media file.

**Arguments:**
- `file_path` (string): Absolute path to the media file

**Returns:**
Complete EXIF metadata dictionary with all available fields.

### 4. `generate_gpx_track(video_path: str, track_name: str)`
Generates GPX track from video GPS metadata (partial implementation).

**Arguments:**
- `video_path` (string): Absolute path to the video file
- `track_name` (string, optional): Name for the GPX track

## Running Locally

### Prerequisites
- Python 3.11+
- ExifTool installed (`apt-get install libimage-exiftool-perl` on Ubuntu)

### Installation
```bash
cd src/mcp_servers/exiftool_server
pip install -r requirements.txt
```

### Run Server - stdio mode (for MCP clients)
```bash
python server.py
```

The server will listen for MCP protocol messages on stdin/stdout. Use this mode when integrating with MCP-compatible clients.

### Run Server - HTTP mode (for Azure/HTTP clients)
```bash
python http_server.py
# Or using uvicorn:
uvicorn http_server:app --host 0.0.0.0 --port 8081
```

The server will expose a REST API at `http://localhost:8081`. Use this mode for:
- Azure Container Apps deployment
- HTTP-based agent integrations
- Testing with curl/Postman

**HTTP Endpoints:**
- `GET /health` - Health check
- `GET /tools` - List available tools
- `POST /tools/extract_gps` - Extract GPS from file
- `POST /tools/extract_all_metadata` - Extract all metadata
- `POST /tools/generate_gpx_track` - Generate GPX track
- `GET /tools/get_exiftool_version` - Get ExifTool version

## Running in Container

### Build Container
```bash
podman build -t exiftool-mcp-server -f src/mcp_servers/exiftool_server/Containerfile src/mcp_servers/exiftool_server/
```

### Run Container
```bash
podman run -it exiftool-mcp-server
```

## Deployment to Azure

See `/infra` directory for Bicep templates to deploy this MCP server to Azure Container Apps.

## Architecture

```
┌─────────────────────────────────────┐
│   ExifTool MCP Server               │
│                                     │
│  ┌───────────────────────────────┐ │
│  │ FastMCP Server                │ │
│  │ (MCP Protocol Handler)        │ │
│  └────────────┬──────────────────┘ │
│               │                     │
│  ┌────────────▼──────────────────┐ │
│  │ MCP Tools:                    │ │
│  │ - get_exiftool_version()      │ │
│  │ - extract_gps()               │ │
│  │ - extract_all_metadata()      │ │
│  │ - generate_gpx_track()        │ │
│  └────────────┬──────────────────┘ │
│               │                     │
│  ┌────────────▼──────────────────┐ │
│  │ ExifTool CLI Wrapper          │ │
│  │ (subprocess calls)            │ │
│  └───────────────────────────────┘ │
└─────────────────────────────────────┘
```

## Integration with GeoBox

The ExifTool MCP server is designed to be called by the GeoBox Orchestrator agent:

```
GeoBox Orchestrator Agent
    ↓
MCP Client (Agent Framework)
    ↓
ExifTool MCP Server (this server)
    ↓
ExifTool CLI
```

## Development

### Testing Tools

Test individual tools using the MCP inspector or by sending MCP protocol messages:

```python
import json

# Example tool call message
message = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "extract_gps",
        "arguments": {
            "file_path": "/tmp/test.jpg"
        }
    }
}
```

### Logging

The server uses structured logging via `structlog`. Logs include:
- Tool invocations
- ExifTool command execution
- Errors and warnings

## Future Enhancements

- [ ] Full GPX track generation for drone videos
- [ ] Support for DJI-specific GPS formats
- [ ] HTTP/SSE transport mode (currently stdio only)
- [ ] Caching for repeated file requests
- [ ] Batch processing support
