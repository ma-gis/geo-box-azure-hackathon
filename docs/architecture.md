# GeoBox Architecture: Multi-Agent & MCP Implementation

## Overview

GeoBox is a **multi-agent system** built on Microsoft Agent Framework and Model Context Protocol (MCP) servers, deployed as 3 Azure Container Apps. It automatically extracts GPS metadata from photos and videos uploaded to Box, enriches them with reverse geocoding and elevation data, and writes the results back as Box metadata.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       Box Platform                              │
│                   (Photo/Video Uploads)                         │
└───────────┬─────────────────────────────────┬───────────────────┘
            │ Webhook Event                   ▲ Box Metadata API
            ↓                                 │ (write GPS + geo)
┌───────────────────────────────────────────────────────────────────┐
│       Azure Container App: GeoBox Orchestrator (geobox-app-dev)  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ FastAPI Webhook Handler (main.py)                           │ │
│  │ - POST /webhook/box  — receive Box events                   │ │
│  │ - GET /health         — health check                        │ │
│  │ - GET /stats          — processing statistics               │ │
│  │ - GET /debug/orchestrator — debug state                     │ │
│  └────────────────────┬────────────────────────────────────────┘ │
│                       │                                          │
│  ┌────────────────────▼────────────────────────────────────────┐ │
│  │ GeoBox Orchestrator Agent (orchestrator_agent.py)           │ │
│  │ Microsoft Agent Framework + Azure OpenAI GPT-4o             │ │
│  │ - Agent-driven workflow decisions                           │ │
│  │ - Calls MCP tools for GPS extraction                        │ │
│  │ - Calls Geo MCP for reverse geocoding + elevation           │ │
│  │ - Validates GPS coordinates                                 │ │
│  │ - Writes metadata to Box                                    │ │
│  └─────┬──────────────────────────────────┬────────────────────┘ │
│        │                                  │                      │
└────────┼──────────────────────────────────┼──────────────────────┘
         │ MCP /sse                         │ httpx (REST)
         │ (MCPStreamableHTTPTool)          │
         │ Internal network                 │ Internal network
         ↓                                  ↓
┌──────────────────────────┐   ┌──────────────────────────────────┐
│ Azure Container App:     │   │ Azure Container App:             │
│ ExifTool MCP Server      │   │ Geo MCP Server                   │
│ (geobox-mcp-exiftool-dev)│   │ (geobox-mcp-geo-dev)             │
│                          │   │                                   │
│ MCP Tools:               │   │ REST Endpoints:                   │
│ - extract_gps            │   │ - reverse_geocode(lat,lon)        │
│ - extract_all_metadata   │   │   → Nominatim (OpenStreetMap)     │
│ - generate_gpx_track     │   │ - get_elevation(lat,lon)          │
│ - get_exiftool_version   │   │   → Open-Elevation API            │
│                          │   │                                   │
│ ┌──────────────────────┐ │   └──────────────────────────────────┘
│ │ ExifTool CLI          │ │
│ │ (subprocess)          │ │
│ └──────────────────────┘ │
└──────────────────────────┘

         Azure File Share (geobox-tmp)
         Mounted at /tmp/geobox
         Shared by: Orchestrator + ExifTool MCP

┌──────────────────────────────────────────────────────────────────┐
│ Supporting Services                                              │
│ - Azure Container Registry (ACR): 3 images                       │
│ - Azure OpenAI (GPT-4o): API key auth                            │
│ - Log Analytics: logs from all 3 container apps                  │
└──────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. GeoBox Orchestrator Agent
**File**: `src/agents/orchestrator_agent.py`

**Technology**: Microsoft Agent Framework + Azure OpenAI

**Responsibilities**:
- Receives file processing requests
- Decides workflow steps autonomously
- Calls MCP tools for GPS extraction
- Calls Geo MCP for reverse geocoding and elevation
- Validates GPS coordinates
- Writes metadata back to Box
- Returns structured results

**Agent Instructions**:
```
You are the GeoBox Orchestrator, an AI agent responsible for processing
photos and videos to extract and validate GPS metadata.

Your workflow for each file:
1. Extract GPS Data using extract_gps tool
2. Validate GPS coordinates are plausible
3. Enrich with reverse geocoding and elevation
4. Return structured result
```

**Key Features**:
- **Agent-driven workflow**: AI decides the best approach for each file
- **Tool calling**: Uses MCP tools via Agent Framework
- **Graceful degradation**: Falls back if MCP server unavailable
- **Structured logging**: Detailed tracing for debugging

### 2. ExifTool MCP Server
**Files**:
- `src/mcp_servers/exiftool_server/server.py` — MCP tool definitions (extract_gps, etc.)
- `src/mcp_servers/exiftool_server/sse_server.py` — Streamable HTTP transport for Agent Framework
- `src/mcp_servers/exiftool_server/http_server.py` — REST API wrapper
- `src/mcp_servers/exiftool_server/gateway_middleware.py` — Auth + rate limiting

**Technology**: MCP Python SDK + FastAPI

**Deployment**: Separate Azure Container App (internal ingress only)

**Tools Exposed**:

| Tool | Input | Output | Purpose |
|------|-------|--------|---------|
| `extract_gps` | `file_path: str` | GPS data dict | Extract coordinates from file |
| `extract_all_metadata` | `file_path: str` | Full EXIF dict | Get all metadata fields |
| `generate_gpx_track` | `video_path: str` | GPX content | Generate track from drone video |
| `get_exiftool_version` | - | Version string | Check ExifTool availability |

**HTTP Endpoints** (for Azure Container Apps):
```
GET  /health                      - Health check
GET  /tools                       - List available tools
POST /tools/extract_gps           - Extract GPS from file
POST /tools/extract_all_metadata  - Extract all metadata
POST /tools/generate_gpx_track    - Generate GPX track
GET  /tools/get_exiftool_version  - Get ExifTool version
```

### 3. Geo MCP Server
**Files**:
- `src/mcp_servers/geo_server/http_server.py` — REST API (Nominatim + Open-Elevation)
- `src/mcp_servers/geo_server/gateway_middleware.py` — Auth + rate limiting

**Technology**: FastAPI + httpx

**Deployment**: Separate Azure Container App (internal ingress only, port 8082)

**Endpoints**:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/reverse_geocode` | POST | Reverse geocode via Nominatim (OpenStreetMap) |
| `/get_elevation` | POST | Get elevation via Open-Elevation API |
| `/health` | GET | Health check |

### 4. FastAPI Main Application
**File**: `src/main.py`

The application automatically uses the Agent Framework orchestrator when Azure OpenAI credentials are configured. If initialization fails, it falls back to the direct extraction agent.

**Endpoints**:
- `POST /webhook/box` - Receive Box upload events
- `GET /health` - Health check with orchestrator status
- `GET /stats` - Processing statistics
- `GET /` - Service info
- `GET /debug/orchestrator` - Debug orchestrator state

## Technology Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Orchestrator** | Microsoft Agent Framework | 1.0.0-beta | Multi-agent workflows |
| **MCP Protocol** | MCP Python SDK | 1.26.0 | Tool standardization |
| **AI Model** | Azure OpenAI GPT-4o | - | Agent decision-making |
| **API Framework** | FastAPI | 0.109.0 | HTTP server |
| **Container** | Podman | - | Containerization |
| **Cloud** | Azure Container Apps | - | Deployment |
| **GPS Tool** | ExifTool | Latest | GPS extraction |
| **Geocoding** | Nominatim (OSM) | - | Reverse geocoding |
| **Elevation** | Open-Elevation | - | Elevation lookup |

## Data Flow

```
1. User uploads photo/video to Box
2. Box sends webhook event to orchestrator (POST /webhook/box)
3. Orchestrator downloads file from Box → /tmp/geobox/
4. Orchestrator agent calls ExifTool MCP (/sse) to extract GPS
5. Orchestrator agent calls Geo MCP to reverse geocode + get elevation
6. Orchestrator writes GPS + geo metadata back to Box via Box Metadata API
```

## Deployment

### Infrastructure (Bicep)

GeoBox deploys **3 Azure Container Apps**:

1. **geobox-app-dev** (Orchestrator)
   - External ingress (receives Box webhooks)
   - Runs main.py
   - Env vars: `MCP_EXIFTOOL_URL`, `MCP_GEO_URL`, Azure OpenAI creds
   - Shared volume mount: `/tmp/geobox`

2. **geobox-mcp-exiftool-dev** (ExifTool MCP Server)
   - Internal ingress only
   - Runs sse_server.py (Streamable HTTP transport)
   - Port 8081
   - Shared volume mount: `/tmp/geobox`

3. **geobox-mcp-geo-dev** (Geo MCP Server)
   - Internal ingress only
   - Runs http_server.py (Nominatim + Open-Elevation)
   - Port 8082

### Deployment Command

```powershell
./scripts/deploy-with-bicep.ps1 `
    -ResourceGroup "geobox-rg" `
    -Location "eastus" `
    -Environment "dev" `
    -AzureOpenAIApiKey $Env:AZURE_OPENAI_API_KEY `
    -AzureOpenAIEndpoint $Env:AZURE_OPENAI_ENDPOINT
```

This script:
1. Creates all Azure resources via Bicep
2. Builds all 3 container images
3. Pushes to Azure Container Registry
4. Restarts all container apps

## Configuration

### Environment Variables

**Orchestrator Container**:
```bash
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=xxx
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
MCP_EXIFTOOL_URL=http://geobox-mcp-exiftool-dev/sse
MCP_GEO_URL=http://geobox-mcp-geo-dev
LOG_LEVEL=INFO
```

**ExifTool MCP Server Container**:
```bash
LOG_LEVEL=INFO
```

**Geo MCP Server Container**:
```bash
LOG_LEVEL=INFO
```

### Fallback Mode

The app automatically falls back to the direct extraction agent if the orchestrator cannot be initialized (e.g., missing Azure OpenAI credentials or unreachable MCP server). No configuration change is needed.

## Monitoring & Debugging

### Check Orchestrator Status
```bash
curl https://<your-app>.azurecontainerapps.io/debug/orchestrator
```

### View Orchestrator Logs
```bash
az containerapp logs show \
    --name geobox-app-dev \
    --resource-group geobox-rg \
    --tail 100
```

### View MCP Server Logs
```bash
# ExifTool MCP
az containerapp logs show \
    --name geobox-mcp-exiftool-dev \
    --resource-group geobox-rg \
    --tail 100

# Geo MCP
az containerapp logs show \
    --name geobox-mcp-geo-dev \
    --resource-group geobox-rg \
    --tail 100
```

### Test MCP Server Directly

From orchestrator container (internal network):
```bash
# ExifTool MCP health check
curl http://geobox-mcp-exiftool-dev/health

# ExifTool MCP list tools
curl http://geobox-mcp-exiftool-dev/tools

# Geo MCP health check
curl http://geobox-mcp-geo-dev/health

# Extract GPS (requires test file)
curl -X POST http://geobox-mcp-exiftool-dev/tools/extract_gps \
    -H "Content-Type: application/json" \
    -d '{"file_path": "/tmp/geobox/test.jpg"}'
```

## Future Enhancements

### Planned MCP Servers

1. **Box MCP Server** (`src/mcp_servers/box_server/`)
   - `create_metadata(file_id, template, data)` - Box API
   - `upload_file(content, name, folder)` - Box upload
   - `search_by_gps(min_lat, max_lat, min_lon, max_lon)` - Box search

### Multi-Agent Workflows

- **Specialized Agents**: Extraction Agent, Validation Agent, Enrichment Agent
- **Agent Collaboration**: Agents communicate via Agent Framework
- **Workflow Orchestration**: Complex multi-step workflows with checkpoints

### Microsoft Foundry Integration

- **Foundry Workflows**: YAML-based workflow definitions
- **Visual Workflow Designer**: Azure AI Foundry portal
- **CI/CD Integration**: Automated workflow testing

## Performance & Cost

### Resource Usage

| Component | CPU | Memory | Replicas | Cost/Month |
|-----------|-----|--------|----------|------------|
| Orchestrator | 0.25 | 0.5Gi | 0-10 (scale to zero) | ~$5-10 |
| ExifTool MCP Server | 0.25 | 0.5Gi | 0-5 (scale to zero) | ~$3-5 |
| Geo MCP Server | 0.25 | 0.5Gi | 0-5 (scale to zero) | ~$3-5 |
| **Total** | | | | **~$11-20** |

### Latency

- **Direct mode (fallback)**: ~2-3 seconds per file
- **Multi-agent mode**: ~3-5 seconds per file (additional network hops + AI inference)

### Scaling

- **Horizontal**: Each container app scales independently
- **Vertical**: Adjust CPU/memory via Bicep parameters
- **Cost optimization**: Scale-to-zero when idle

## Testing

Run integration tests:
```bash
pytest tests/test_integration.py -v
```

Manual test script:
```bash
python tests/test_integration.py
```

## Troubleshooting

### Issue: Orchestrator fails to initialize

**Symptom**: "orchestrator_initialization_failed" in logs

**Causes**:
1. MCP server unreachable
2. Azure OpenAI credentials missing/invalid
3. No quota for GPT model

**Solution**:
- Check MCP_EXIFTOOL_URL is correct
- Verify Azure OpenAI credentials
- Request quota increase in Azure portal
- App will fall back to direct extraction mode automatically

### Issue: MCP server not responding

**Symptom**: "mcp_tools_available": false

**Causes**:
1. MCP server container not running
2. Internal network connectivity issue
3. ExifTool not installed in container

**Solution**:
```bash
# Check if MCP server is running
az containerapp replica list \
    --name geobox-mcp-exiftool-dev \
    --resource-group geobox-rg

# Exec into MCP server container
az containerapp exec \
    --name geobox-mcp-exiftool-dev \
    --resource-group geobox-rg \
    --command "/bin/bash"

# Verify ExifTool
exiftool -ver
```

### Issue: Agent not calling tools

**Symptom**: Agent responds but doesn't use MCP tools

**Causes**:
1. Agent instructions unclear
2. GPT model too conservative
3. MCP tools not registered correctly

**Solution**:
- Review agent instructions in orchestrator_agent.py
- Check MCP tool registration in logs
- Increase temperature parameter (more creative tool usage)

## References

- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/)
- [ExifTool Documentation](https://exiftool.org/)

---

**Status**: Production deployment complete
