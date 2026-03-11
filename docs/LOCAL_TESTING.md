# Local Testing with Podman

This guide covers all local testing scenarios for GeoBox using Podman.

---

## Prerequisites

### Required
- ✅ Podman installed (`podman --version`)
- ✅ Python 3.11+ (`python --version`)
- ✅ ExifTool installed (for non-container testing)

### Optional
- podman-compose (for multi-container setup)
- Azure CLI (for Azure authentication)

---

## Testing Scenarios

### 1. Quick Test - Python Only (No Containers)
**Best for:** Rapid development, debugging
**Mode:** ✅ Full multi-agent (if Azure OpenAI + MCP servers are running)

### 2. Single Container - Orchestrator Only
**Best for:** Testing main app logic
**Mode:** ⚠️ Limited (no MCP servers — falls back to direct extraction)

### 3. Multi-Container - Full Architecture ⭐ RECOMMENDED
**Best for:** End-to-end testing, production-like environment
**Mode:** ✅ Full multi-agent support

---

## Scenario 1: Python-Only Testing (Fastest)

### Setup Environment

```powershell
# Install dependencies
python -m pip install -r requirements.txt

# Copy and configure .env
copy src\.env.example .env
# Edit .env with your Azure credentials
```

### Run ExifTool MCP Server (Terminal 1)

```powershell
cd src/mcp_servers/exiftool_server
python sse_server.py
```

**Output:**
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8081
```

### Run Geo MCP Server (Terminal 2)

```powershell
cd src/mcp_servers/geo_server
python http_server.py
```

**Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8082
```

### Run Orchestrator (Terminal 3)

```powershell
$env:MCP_EXIFTOOL_URL = "http://localhost:8081/sse"
$env:GEO_SERVER_URL   = "http://localhost:8082"
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
$env:AZURE_OPENAI_API_KEY  = "your-key"

python -m uvicorn src.main:app --reload --port 8080
```

### Test It

```powershell
# Health check
curl http://localhost:8080/health

# Check orchestrator status
curl http://localhost:8080/debug/orchestrator

# ExifTool MCP
curl http://localhost:8081/health
curl http://localhost:8081/tools

# Geo MCP
curl http://localhost:8082/health
```

**Pros:**
- ✅ Fastest iteration cycle
- ✅ Hot reload with --reload
- ✅ Easy debugging with breakpoints

**Cons:**
- ❌ Requires ExifTool installed locally
- ❌ Not testing containerized environment

---

## Scenario 2: Single Container (Orchestrator)

### Build Container

```powershell
powershell -Command "podman build -t geobox:latest -f Containerfile ."
```

### Run Container

```powershell
# Create network
powershell -Command "podman network create geobox-network"

# Run orchestrator
powershell -Command "podman run -d ``
    --name geobox-dev ``
    --network geobox-network ``
    -p 8080:8080 ``
    -e AZURE_OPENAI_ENDPOINT=$env:AZURE_OPENAI_ENDPOINT ``
    -e AZURE_OPENAI_API_KEY=$env:AZURE_OPENAI_API_KEY ``
    geobox:latest"
```

**Note:** Without MCP servers, orchestrator will use fallback mode automatically.

### Test It

```powershell
podman logs -f geobox-dev
curl http://localhost:8080/health

podman stop geobox-dev
podman rm geobox-dev
```

---

## Scenario 3: Multi-Container (Full Multi-Agent) ⭐ RECOMMENDED

### Option A: Using the Test Script (Easiest)

```powershell
# Build and start all 3 containers
.\scripts\test-local.ps1 -Rebuild

# Start without rebuilding
.\scripts\test-local.ps1

# Start in fallback mode (no MCP servers)
.\scripts\test-local.ps1 -FallbackMode

# Stop everything
.\scripts\stop-local.ps1
```

### Option B: Using podman-compose

```powershell
# Start all services
podman-compose up -d

# View logs
podman-compose logs -f

# Stop all services
podman-compose down
```

The `podman-compose.yml` at the project root defines all 3 services.

### Option C: Manual Multi-Container (Most Control)

#### Step 1: Build All Containers

```powershell
# ExifTool MCP server
powershell -Command "podman build -t exiftool-mcp:latest -f src/mcp_servers/exiftool_server/Containerfile src/mcp_servers/exiftool_server/"

# Geo MCP server
powershell -Command "podman build -t geo-mcp:latest -f src/mcp_servers/geo_server/Containerfile src/mcp_servers/geo_server/"

# Orchestrator
powershell -Command "podman build -t geobox:latest -f Containerfile ."
```

#### Step 2: Create Network

```powershell
powershell -Command "podman network create geobox-network"
```

#### Step 3: Run ExifTool MCP Server

```powershell
powershell -Command "podman run -d ``
    --name geobox-mcp-exiftool-dev ``
    --network geobox-network ``
    -p 8081:8081 ``
    -e LOG_LEVEL=INFO ``
    exiftool-mcp:latest"
```

#### Step 4: Run Geo MCP Server

```powershell
powershell -Command "podman run -d ``
    --name geobox-mcp-geo-dev ``
    --network geobox-network ``
    -p 8082:8082 ``
    -e LOG_LEVEL=INFO ``
    geo-mcp:latest"
```

#### Step 5: Run Orchestrator

```powershell
powershell -Command "podman run -d ``
    --name geobox-orchestrator-dev ``
    --network geobox-network ``
    -p 8080:8080 ``
    -e MCP_EXIFTOOL_URL=http://geobox-mcp-exiftool-dev:8081/sse ``
    -e GEO_SERVER_URL=http://geobox-mcp-geo-dev:8082 ``
    -e AZURE_OPENAI_ENDPOINT=$env:AZURE_OPENAI_ENDPOINT ``
    -e AZURE_OPENAI_API_KEY=$env:AZURE_OPENAI_API_KEY ``
    -e LOG_LEVEL=INFO ``
    geobox:latest"
```

#### Step 6: Test It

```powershell
# Check all containers are running
podman ps

# Test MCP servers
curl http://localhost:8081/health
curl http://localhost:8081/tools
curl http://localhost:8082/health

# Test orchestrator
curl http://localhost:8080/health
curl http://localhost:8080/debug/orchestrator

# View logs
podman logs -f geobox-orchestrator-dev
podman logs -f geobox-mcp-exiftool-dev
podman logs -f geobox-mcp-geo-dev
```

#### Step 7: Cleanup

```powershell
podman stop geobox-orchestrator-dev geobox-mcp-exiftool-dev geobox-mcp-geo-dev
podman rm geobox-orchestrator-dev geobox-mcp-exiftool-dev geobox-mcp-geo-dev
podman network rm geobox-network
```

---

## Testing with Sample Files

### Create Test Image with GPS

```powershell
# Using exiftool (if installed locally)
exiftool `
    -GPSLatitude=37.7749 `
    -GPSLatitudeRef=N `
    -GPSLongitude=122.4194 `
    -GPSLongitudeRef=W `
    -GPSAltitude=10 `
    test-input.jpg -o test-gps.jpg
```

### Upload to Box

1. Upload `test-gps.jpg` to your Box folder
2. Watch the logs for webhook processing:

```powershell
podman logs -f geobox-orchestrator-dev
podman logs -f geobox-mcp-exiftool-dev
```

### Direct API Testing (Bypass Box)

Since Box webhooks won't work locally, test the processing logic directly:

```powershell
# Copy test file into orchestrator container
podman cp test-gps.jpg geobox-orchestrator-dev:/tmp/geobox/test-gps.jpg

# Exec into container and test
podman exec -it geobox-orchestrator-dev python -c "
from src.agents.orchestrator_agent import GeoBoxOrchestrator
import asyncio

async def test():
    async with GeoBoxOrchestrator('http://geobox-mcp-exiftool-dev:8081/sse') as orch:
        result = await orch.process_file('/tmp/geobox/test-gps.jpg', 'test.jpg', 'image/jpeg')
        print(result)

asyncio.run(test())
"
```

---

## Quick Reference

### Start Testing (Multi-Agent mode)
```powershell
.\scripts\test-local.ps1 -Rebuild
```

### Start Testing (Fallback mode — no MCP servers)
```powershell
.\scripts\test-local.ps1 -FallbackMode
```

### View Logs
```powershell
podman logs -f geobox-orchestrator-dev
podman logs -f geobox-mcp-exiftool-dev
podman logs -f geobox-mcp-geo-dev
```

### Stop Everything
```powershell
.\scripts\stop-local.ps1
```

### Rebuild Containers
```powershell
.\scripts\test-local.ps1 -Rebuild
```

---

## Troubleshooting

### Issue: MCP server not responding

```powershell
# Check if container is running
podman ps | Select-String mcp

# Check logs
podman logs geobox-mcp-exiftool-dev
podman logs geobox-mcp-geo-dev

# Test directly
curl http://localhost:8081/health
curl http://localhost:8082/health
```

### Issue: Orchestrator can't reach MCP server

**Cause**: Containers not on same network

**Solution**:
```powershell
podman network inspect geobox-network
.\scripts\test-local.ps1 -Rebuild
```

### Issue: ExifTool not found in container

**Cause**: Container build failed

**Solution**:
```powershell
powershell -Command "podman build --no-cache -t geobox:latest -f Containerfile ."
```

### Issue: Port already in use

```powershell
netstat -ano | findstr :8080
taskkill /PID <PID> /F
```

---

## Performance Tips

1. **Use Hot Reload for Development** — Python-only mode with `--reload` is fastest
2. **Use `-Rebuild` only when needed** — skipping rebuild saves several minutes
3. **Keep Containers Running** — use `podman restart` instead of stop/start

---

**See also:**
- [deployment_guide.md](deployment_guide.md) — Azure deployment
- [BOX_SETUP.md](BOX_SETUP.md) — Box webhook configuration
