# Deploy GeoBox using Azure Bicep (Infrastructure as Code)
# PowerShell script

param(
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = "geobox-rg",

    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus",

    [Parameter(Mandatory=$false)]
    [string]$Environment = "dev",

    [Parameter(Mandatory=$true)]
    [string]$AzureOpenAIApiKey,

    [Parameter(Mandatory=$true)]
    [string]$AzureOpenAIEndpoint
)

Write-Host "🚀 Deploying GeoBox with Azure Bicep (IaC)" -ForegroundColor Green

# Check if logged in to Azure
$account = az account show 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Not logged in to Azure. Running 'az login'..." -ForegroundColor Yellow
    az login
}

# Show current subscription
$subscription = az account show --query name -o tsv
Write-Host "`nUsing Azure subscription: $subscription" -ForegroundColor Cyan

# Create resource group
Write-Host "`n📦 Creating resource group: $ResourceGroup" -ForegroundColor Cyan
az group create --name $ResourceGroup --location $Location

# Deploy Bicep template
Write-Host "`n🏗️ Deploying infrastructure with Bicep..." -ForegroundColor Cyan
Write-Host "This will create:" -ForegroundColor Yellow
Write-Host "  - Azure Container Registry" -ForegroundColor Yellow
Write-Host "  - Azure Container Apps Environment" -ForegroundColor Yellow
Write-Host "  - Azure Container App (GeoBox Orchestrator)" -ForegroundColor Yellow
Write-Host "  - Azure Container App (ExifTool MCP Server)" -ForegroundColor Yellow
Write-Host "  - Azure Container App (Geospatial MCP Server)" -ForegroundColor Yellow
Write-Host "  - Log Analytics Workspace" -ForegroundColor Yellow

$deploymentName = "geobox-deployment-$(Get-Date -Format 'yyyyMMddHHmmss')"

az deployment group create `
    --name $deploymentName `
    --resource-group $ResourceGroup `
    --template-file "./iac/main.bicep" `
    --parameters `
        location=$Location `
        environment=$Environment `
        azureOpenAIApiKey=$AzureOpenAIApiKey `
        azureOpenAIEndpoint=$AzureOpenAIEndpoint

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Infrastructure deployed successfully!" -ForegroundColor Green

    # Get outputs
    Write-Host "`n📊 Deployment Outputs:" -ForegroundColor Cyan

    $outputs = az deployment group show `
        --name $deploymentName `
        --resource-group $ResourceGroup `
        --query properties.outputs `
        -o json | ConvertFrom-Json

    $registryServer = $outputs.containerRegistryLoginServer.value
    $appUrl = $outputs.containerAppUrl.value
    $mcpExifToolUrl = $outputs.mcpExifToolAppUrl.value
    $mcpGeoUrl = $outputs.mcpGeoAppUrl.value

    Write-Host "Container Registry: $registryServer" -ForegroundColor Yellow
    Write-Host "App URL: $appUrl" -ForegroundColor Yellow
    Write-Host "MCP ExifTool Server: $mcpExifToolUrl (internal)" -ForegroundColor Yellow
    Write-Host "MCP Geo Server:      $mcpGeoUrl (internal)" -ForegroundColor Yellow

    # Build and push container images
    Write-Host "`n🐳 Building and pushing container images..." -ForegroundColor Cyan

    $registryName = $registryServer.Split('.')[0]

    # Build main GeoBox app
    Write-Host "`n  Building GeoBox orchestrator..." -ForegroundColor Cyan
    az acr build `
        --registry $registryName `
        --image geobox:latest `
        --file Containerfile `
        .

    # Build ExifTool MCP server
    Write-Host "`n  Building ExifTool MCP server..." -ForegroundColor Cyan
    az acr build `
        --registry $registryName `
        --image exiftool-mcp-server:latest `
        --file src/mcp_servers/exiftool_server/Containerfile `
        src/mcp_servers/exiftool_server

    # Build Geospatial MCP server
    Write-Host "`n  Building Geospatial MCP server..." -ForegroundColor Cyan
    az acr build `
        --registry $registryName `
        --image geo-mcp-server:latest `
        --file src/mcp_servers/geo_server/Containerfile `
        src/mcp_servers/geo_server

    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ All container images pushed successfully!" -ForegroundColor Green

        # Restart container apps to use new images
        Write-Host "`n🔄 Restarting container apps..." -ForegroundColor Cyan

        $appName = "geobox-app-$Environment"
        $mcpExifToolAppName = "geobox-mcp-exiftool-$Environment"
        $mcpGeoAppName = "geobox-mcp-geo-$Environment"

        Write-Host "  Restarting orchestrator..." -ForegroundColor Cyan
        az containerapp revision restart `
            --name $appName `
            --resource-group $ResourceGroup

        Write-Host "  Restarting ExifTool MCP server..." -ForegroundColor Cyan
        az containerapp revision restart `
            --name $mcpExifToolAppName `
            --resource-group $ResourceGroup

        Write-Host "  Restarting Geospatial MCP server..." -ForegroundColor Cyan
        az containerapp revision restart `
            --name $mcpGeoAppName `
            --resource-group $ResourceGroup

        Write-Host "`n🎉 Deployment Complete!" -ForegroundColor Green
        Write-Host "`nGeoBox Orchestrator:" -ForegroundColor Cyan
        Write-Host "  URL: $appUrl" -ForegroundColor Yellow
        Write-Host "  Health: $appUrl/health" -ForegroundColor Yellow
        Write-Host "  Debug: $appUrl/debug/orchestrator" -ForegroundColor Yellow

        Write-Host "`nMCP Servers (internal only):" -ForegroundColor Cyan
        Write-Host "  ExifTool: $mcpExifToolUrl" -ForegroundColor Yellow
        Write-Host "  Geo:      $mcpGeoUrl" -ForegroundColor Yellow

        Write-Host "`n📝 Next Steps:" -ForegroundColor Cyan
        Write-Host "  1. Configure Box webhook to point to: $appUrl/webhook/box"
        Write-Host "  2. Upload a geotagged photo to Box to test end-to-end"
        Write-Host "  3. Check orchestrator logs: az containerapp logs show --name $appName --resource-group $ResourceGroup --tail 50"
        Write-Host "  4. Check ExifTool MCP logs: az containerapp logs show --name $mcpExifToolAppName --resource-group $ResourceGroup --tail 50"
        Write-Host "  5. Check Geo MCP logs: az containerapp logs show --name $mcpGeoAppName --resource-group $ResourceGroup --tail 50"
    }
} else {
    Write-Host "`n❌ Deployment failed!" -ForegroundColor Red
    exit 1
}
