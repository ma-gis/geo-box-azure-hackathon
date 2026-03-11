# Deploy GeoBox to Azure Container Apps
# PowerShell script

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup = "geobox-rg",

    [Parameter(Mandatory=$true)]
    [string]$Location = "eastus",

    [Parameter(Mandatory=$true)]
    [string]$RegistryName = "geoboxregistry",

    [Parameter(Mandatory=$true)]
    [string]$AppName = "geobox-app"
)

Write-Host "Deploying GeoBox to Azure..." -ForegroundColor Green

# Check if logged in to Azure
$account = az account show 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Not logged in to Azure. Running 'az login'..." -ForegroundColor Yellow
    az login
}

Write-Host "`nStep 1: Creating Resource Group..." -ForegroundColor Cyan
az group create --name $ResourceGroup --location $Location

Write-Host "`nStep 2: Creating Azure Container Registry..." -ForegroundColor Cyan
az acr create --resource-group $ResourceGroup --name $RegistryName --sku Basic

Write-Host "`nStep 3: Building and pushing image to ACR..." -ForegroundColor Cyan
az acr build --registry $RegistryName --image geobox:v1 --file Containerfile .

Write-Host "`nStep 4: Creating Container Apps environment..." -ForegroundColor Cyan
$envName = "geobox-env"
az containerapp env create `
    --name $envName `
    --resource-group $ResourceGroup `
    --location $Location

Write-Host "`nStep 5: Deploying Container App..." -ForegroundColor Cyan
$imageName = "$RegistryName.azurecr.io/geobox:v1"

az containerapp create `
    --name $AppName `
    --resource-group $ResourceGroup `
    --environment $envName `
    --image $imageName `
    --target-port 8080 `
    --ingress external `
    --min-replicas 0 `
    --max-replicas 10 `
    --registry-server "$RegistryName.azurecr.io" `
    --env-vars `
        "AZURE_OPENAI_API_KEY=$env:AZURE_OPENAI_API_KEY" `
        "AZURE_OPENAI_ENDPOINT=$env:AZURE_OPENAI_ENDPOINT" `
        "AZURE_OPENAI_DEPLOYMENT_NAME=$env:AZURE_OPENAI_DEPLOYMENT_NAME"

Write-Host "`nDeployment complete!" -ForegroundColor Green

# Get app URL
$appUrl = az containerapp show `
    --name $AppName `
    --resource-group $ResourceGroup `
    --query properties.configuration.ingress.fqdn `
    --output tsv

Write-Host "`nGeoBox URL: https://$appUrl" -ForegroundColor Cyan
Write-Host "Health Check: https://$appUrl/health" -ForegroundColor Cyan
