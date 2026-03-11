# Build GeoBox container with Podman
# PowerShell script for Windows

Write-Host "Building GeoBox container with Podman..." -ForegroundColor Green

# Navigate to project root
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptPath
Set-Location $projectRoot

# Build the container
podman build -t geobox:latest -f Containerfile .

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nBuild successful!" -ForegroundColor Green
    Write-Host "Image: geobox:latest" -ForegroundColor Cyan

    # Show image info
    podman images geobox:latest
} else {
    Write-Host "`nBuild failed!" -ForegroundColor Red
    exit 1
}
