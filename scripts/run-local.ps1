# Run GeoBox locally with Podman
# PowerShell script for Windows

Write-Host "Starting GeoBox with Podman..." -ForegroundColor Green

# Navigate to project root
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptPath
Set-Location $projectRoot

# Check if .env exists
if (-Not (Test-Path ".env")) {
    Write-Host "Error: .env file not found!" -ForegroundColor Red
    Write-Host "Copy .env.example to .env and configure it first." -ForegroundColor Yellow
    exit 1
}

# Stop and remove existing container if running
podman stop geobox-dev 2>$null
podman rm geobox-dev 2>$null

# Run with podman-compose
Write-Host "Starting container with podman-compose..." -ForegroundColor Cyan
podman-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nGeoBox is running!" -ForegroundColor Green
    Write-Host "API: http://localhost:8080" -ForegroundColor Cyan
    Write-Host "Health Check: http://localhost:8080/health" -ForegroundColor Cyan
    Write-Host "`nView logs with: podman logs -f geobox-dev" -ForegroundColor Yellow
} else {
    Write-Host "`nFailed to start container!" -ForegroundColor Red
    exit 1
}
