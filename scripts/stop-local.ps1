# Stop local GeoBox containers

Write-Host "🛑 Stopping GeoBox containers..." -ForegroundColor Yellow

# Stop containers
podman stop geobox-orchestrator-dev 2>$null
podman stop geobox-mcp-exiftool-dev 2>$null
podman stop geobox-mcp-geo-dev 2>$null

# Remove containers
podman rm geobox-orchestrator-dev 2>$null
podman rm geobox-mcp-exiftool-dev 2>$null
podman rm geobox-mcp-geo-dev 2>$null

Write-Host "✅ Containers stopped and removed" -ForegroundColor Green

# Optionally show remaining containers
Write-Host "`n📊 Running containers:"
podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
