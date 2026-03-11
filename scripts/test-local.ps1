# Test GeoBox locally with Podman
# Full multi-agent multi-container setup

param(
    [switch]$Rebuild,
    [switch]$FallbackMode
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 GeoBox Local Testing (Podman)" -ForegroundColor Green
Write-Host ("=" * 50)

# Check prerequisites
Write-Host "`n📋 Checking prerequisites..." -ForegroundColor Cyan

if (-not (Get-Command podman -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Podman not found! Please install Podman first." -ForegroundColor Red
    exit 1
}

Write-Host "✅ Podman: $(podman --version)"

# Load environment variables
if (Test-Path ".env") {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.+)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
        }
    }
    Write-Host "✅ Environment loaded from .env"
} else {
    Write-Host "⚠️  No .env file found (using environment variables)" -ForegroundColor Yellow
}

# Create network
Write-Host "`n🌐 Creating network..." -ForegroundColor Cyan
podman network exists geobox-network 2>$null
if ($LASTEXITCODE -ne 0) {
    podman network create geobox-network
    Write-Host "✅ Network created: geobox-network"
} else {
    Write-Host "✅ Network exists: geobox-network"
}

# Stop existing containers
Write-Host "`n🛑 Stopping existing containers..." -ForegroundColor Cyan
podman stop geobox-orchestrator-dev 2>$null
podman stop geobox-mcp-exiftool-dev 2>$null
podman stop geobox-mcp-geo-dev 2>$null
podman rm geobox-orchestrator-dev 2>$null
podman rm geobox-mcp-exiftool-dev 2>$null
podman rm geobox-mcp-geo-dev 2>$null

# Build containers
if ($Rebuild) {
    Write-Host "`n🔨 Building containers..." -ForegroundColor Cyan

    Write-Host "  Building ExifTool MCP server..."
    podman build -t exiftool-mcp:latest `
        -f src/mcp_servers/exiftool_server/Containerfile `
        src/mcp_servers/exiftool_server/

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ ExifTool MCP server build failed!" -ForegroundColor Red
        exit 1
    }

    Write-Host "  Building Geospatial MCP server..."
    podman build -t geo-mcp:latest `
        -f src/mcp_servers/geo_server/Containerfile `
        src/mcp_servers/geo_server/

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Geo MCP server build failed!" -ForegroundColor Red
        exit 1
    }

    Write-Host "  Building orchestrator..."
    podman build -t geobox:latest -f Containerfile .

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Orchestrator build failed!" -ForegroundColor Red
        exit 1
    }

    Write-Host "✅ Containers built"
}

# Determine mode
$mode = if ($FallbackMode) { "fallback" } else { "multi-agent" }
Write-Host "`n⚙️  Mode: $mode" -ForegroundColor Cyan

# Start MCP servers (only in multi-agent mode)
if ($mode -eq "multi-agent") {
    Write-Host "`n🚀 Starting ExifTool MCP server..." -ForegroundColor Cyan
    podman run -d `
        --name geobox-mcp-exiftool-dev `
        --network geobox-network `
        -p 8081:8081 `
        -e LOG_LEVEL=INFO `
        exiftool-mcp:latest

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ ExifTool MCP server failed to start!" -ForegroundColor Red
        exit 1
    }

    Write-Host "✅ ExifTool MCP server started: http://localhost:8081"

    Write-Host "`n🚀 Starting Geospatial MCP server..." -ForegroundColor Cyan
    podman run -d `
        --name geobox-mcp-geo-dev `
        --network geobox-network `
        -p 8082:8082 `
        -e LOG_LEVEL=INFO `
        geo-mcp:latest

    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Geospatial MCP server failed to start!" -ForegroundColor Red
        exit 1
    }

    Write-Host "✅ Geospatial MCP server started: http://localhost:8082"

    # Wait for MCP servers to be ready
    Write-Host "⏳ Waiting for MCP servers..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
}

# Start orchestrator
Write-Host "`n🚀 Starting orchestrator..." -ForegroundColor Cyan

$mcpUrl    = if ($mode -eq "multi-agent") { "http://geobox-mcp-exiftool-dev:8081/sse" } else { "" }
$geoUrl    = if ($mode -eq "multi-agent") { "http://geobox-mcp-geo-dev:8082" } else { "" }

podman run -d `
    --name geobox-orchestrator-dev `
    --network geobox-network `
    -p 8080:8080 `
    -e MCP_EXIFTOOL_URL=$mcpUrl `
    -e GEO_SERVER_URL=$geoUrl `
    -e AZURE_OPENAI_ENDPOINT=$env:AZURE_OPENAI_ENDPOINT `
    -e AZURE_OPENAI_API_KEY=$env:AZURE_OPENAI_API_KEY `
    -e LOG_LEVEL=INFO `
    -v "${PWD}/config:/app/config:Z" `
    geobox:latest

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Orchestrator failed to start!" -ForegroundColor Red
    podman logs geobox-orchestrator-dev
    exit 1
}

Write-Host "✅ Orchestrator started: http://localhost:8080"

# Wait for orchestrator to be ready
Write-Host "`n⏳ Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Health checks
Write-Host "`n🏥 Health checks..." -ForegroundColor Cyan

if ($mode -eq "multi-agent") {
    try {
        $mcpHealth = Invoke-RestMethod -Uri http://localhost:8081/health -ErrorAction Stop
        Write-Host "✅ ExifTool MCP server: healthy"
    } catch {
        Write-Host "❌ ExifTool MCP server: not responding" -ForegroundColor Red
        Write-Host "   Check logs: podman logs geobox-mcp-exiftool-dev" -ForegroundColor Yellow
    }

    try {
        $geoHealth = Invoke-RestMethod -Uri http://localhost:8082/health -ErrorAction Stop
        Write-Host "✅ Geospatial MCP server: healthy"
    } catch {
        Write-Host "❌ Geospatial MCP server: not responding" -ForegroundColor Red
        Write-Host "   Check logs: podman logs geobox-mcp-geo-dev" -ForegroundColor Yellow
    }
}

try {
    $orchHealth = Invoke-RestMethod -Uri http://localhost:8080/health -ErrorAction Stop
    Write-Host "✅ Orchestrator: healthy"
} catch {
    Write-Host "❌ Orchestrator: not responding" -ForegroundColor Red
    Write-Host "   Check logs: podman logs geobox-orchestrator-dev" -ForegroundColor Yellow
}

# Show status
Write-Host "`n" + ("=" * 50)
Write-Host "🎉 GeoBox is running!" -ForegroundColor Green
Write-Host ("=" * 50)

Write-Host "`n📍 Services:"
Write-Host "  Orchestrator: http://localhost:8080" -ForegroundColor Cyan
Write-Host "  Health:       http://localhost:8080/health" -ForegroundColor Cyan

if ($mode -eq "multi-agent") {
    Write-Host "  ExifTool MCP: http://localhost:8081" -ForegroundColor Cyan
    Write-Host "  ExifTool Tools: http://localhost:8081/tools" -ForegroundColor Cyan
    Write-Host "  Geo MCP:      http://localhost:8082" -ForegroundColor Cyan
    Write-Host "  Geo Tools:    http://localhost:8082/tools" -ForegroundColor Cyan
}

Write-Host "`n📝 View logs:"
Write-Host "  podman logs -f geobox-orchestrator-dev" -ForegroundColor Yellow

if ($mode -eq "multi-agent") {
    Write-Host "  podman logs -f geobox-mcp-exiftool-dev" -ForegroundColor Yellow
    Write-Host "  podman logs -f geobox-mcp-geo-dev" -ForegroundColor Yellow
}

Write-Host "`n🛑 Stop services:"
Write-Host "  .\scripts\stop-local.ps1" -ForegroundColor Yellow

Write-Host ""
