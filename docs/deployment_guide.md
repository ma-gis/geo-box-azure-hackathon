# GeoBox Deployment Guide

This guide covers deploying GeoBox with its full multi-agent architecture (3 Azure Container Apps).

## Architecture Overview

```
┌─────────────────────────────────────────┐
│  GeoBox Orchestrator (geobox-app-dev)   │
│  - Agent Framework + FastAPI            │
│  - External ingress (Box webhooks)      │
└─────────┬───────────────┬───────────────┘
          │ MCP /sse      │ httpx (REST)
          ↓               ↓
┌──────────────────┐  ┌───────────────────┐
│ ExifTool MCP     │  │ Geo MCP Server    │
│ (exiftool-dev)   │  │ (geo-dev)         │
│ Internal only    │  │ Internal only     │
└──────────────────┘  └───────────────────┘
          │
   Azure File Share (/tmp/geobox)
   Shared by Orchestrator + ExifTool MCP
```

## Prerequisites

- Azure CLI installed and logged in (`az login`)
- Podman installed (this project uses Podman, not Docker)
- Azure subscription with Container Apps quota
- PowerShell (for deployment script)
- Azure OpenAI endpoint and API key

## Deployment Steps

### 1. Deploy Infrastructure with Bicep

The infrastructure includes:
- Azure Container Registry (ACR)
- Container Apps Environment
- Log Analytics Workspace
- Azure File Share (`geobox-tmp`)
- All 3 Container Apps (Orchestrator, ExifTool MCP, Geo MCP)

```powershell
# From project root
./scripts/deploy-with-bicep.ps1 `
    -ResourceGroup "geobox-rg" `
    -Location "eastus" `
    -Environment "dev" `
    -AzureOpenAIApiKey "your-key" `
    -AzureOpenAIEndpoint "https://your-endpoint.openai.azure.com/"
```

This script will:
1. Create resource group
2. Deploy Bicep template (creates all Azure resources)
3. Build and push all 3 container images to ACR via Podman
4. Restart all container apps

### 2. Verify Deployment

Check orchestrator health:
```bash
curl https://<your-app-url>/health
```

Check MCP servers (internal — exec into orchestrator container):
```bash
curl http://geobox-mcp-exiftool-dev/health
curl http://geobox-mcp-geo-dev/health
```

### 3. Configure Box Webhook

Point your Box webhook to:
```
https://<your-app-url>/webhook/box
```

See [BOX_SETUP.md](BOX_SETUP.md) for detailed webhook configuration.

## Manual Deployment (Alternative)

### Build Containers Locally

```powershell
# Build orchestrator
powershell -Command "podman build -t geobox:latest -f Containerfile ."

# Build ExifTool MCP server
powershell -Command "podman build -t exiftool-mcp-server:latest -f src/mcp_servers/exiftool_server/Containerfile src/mcp_servers/exiftool_server/"

# Build Geo MCP server
powershell -Command "podman build -t geo-mcp-server:latest -f src/mcp_servers/geo_server/Containerfile src/mcp_servers/geo_server/"
```

### Login and Push to Azure Container Registry

```powershell
# Get ACR password
$ACR_NAME = "geoboxsgqptyt4577n4"
$ACR_PASS = az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv

# Login
powershell -Command "podman login $ACR_NAME.azurecr.io -u $ACR_NAME -p $ACR_PASS"

# Tag and push all 3 images
powershell -Command "podman tag geobox:latest $ACR_NAME.azurecr.io/geobox:latest"
powershell -Command "podman push $ACR_NAME.azurecr.io/geobox:latest"

powershell -Command "podman tag exiftool-mcp-server:latest $ACR_NAME.azurecr.io/exiftool-mcp-server:latest"
powershell -Command "podman push $ACR_NAME.azurecr.io/exiftool-mcp-server:latest"

powershell -Command "podman tag geo-mcp-server:latest $ACR_NAME.azurecr.io/geo-mcp-server:latest"
powershell -Command "podman push $ACR_NAME.azurecr.io/geo-mcp-server:latest"
```

> **Note:** `podman push` exits with code 1 even on success — look for `Writing manifest to image destination` as the success indicator.

### Deploy Bicep Template

```bash
az deployment group create \
    --name geobox-deployment \
    --resource-group geobox-rg \
    --template-file iac/main.bicep \
    --parameters \
        location=eastus \
        environment=dev \
        azureOpenAIApiKey=<key> \
        azureOpenAIEndpoint=<endpoint>
```

## Monitoring & Debugging

### View Logs

**Orchestrator logs:**
```bash
az containerapp logs show \
    --name geobox-app-dev \
    --resource-group geobox-rg \
    --tail 100
```

**ExifTool MCP logs:**
```bash
az containerapp logs show \
    --name geobox-mcp-exiftool-dev \
    --resource-group geobox-rg \
    --tail 100
```

**Geo MCP logs:**
```bash
az containerapp logs show \
    --name geobox-mcp-geo-dev \
    --resource-group geobox-rg \
    --tail 100
```

### Check Container App Status

```bash
az containerapp show \
    --name geobox-app-dev \
    --resource-group geobox-rg \
    --query properties.runningStatus
```

### Test MCP Servers Directly

From within the Container Apps Environment (internal network, port 80):

```bash
# ExifTool MCP
curl http://geobox-mcp-exiftool-dev/health
curl http://geobox-mcp-exiftool-dev/tools

# Geo MCP
curl http://geobox-mcp-geo-dev/health

# Extract GPS (requires test file in shared volume)
curl -X POST http://geobox-mcp-exiftool-dev/tools/extract_gps \
    -H "Content-Type: application/json" \
    -d '{"file_path": "/tmp/geobox/test.jpg"}'
```

## Cost

All 3 container apps are configured with:
- **Scale to zero**: No cost when idle
- **Minimal resources**: 0.25 CPU, 0.5Gi memory each

| Component | Cost/Month |
|-----------|------------|
| Orchestrator | ~$5-10 |
| ExifTool MCP | ~$3-5 |
| Geo MCP | ~$3-5 |
| **Total** | **~$11-20** |

## Troubleshooting

### MCP Server Not Responding

1. Check if container is running:
```bash
az containerapp replica list \
    --name geobox-mcp-exiftool-dev \
    --resource-group geobox-rg
```

2. Check for errors in logs
3. Verify ExifTool is installed in container:
```bash
az containerapp exec \
    --name geobox-mcp-exiftool-dev \
    --resource-group geobox-rg \
    --command "/bin/bash"

# Then run:
exiftool -ver
```

### Orchestrator Can't Reach MCP Server

- Verify all 3 apps are in the same Container Apps Environment
- Internal hostnames use port 80 (not target port): `http://geobox-mcp-exiftool-dev`
- Verify ingress configuration (should be `external: false`)

### Container Build Fails

- Check ExifTool installation in Containerfile
- Verify Python dependencies in requirements.txt
- Ensure Podman is running: `podman info`

## Updating Deployment

### Update Code Only

```powershell
# Rebuild and push a specific image, then restart
powershell -Command "podman build -t geobox:latest -f Containerfile ."
powershell -Command "podman tag geobox:latest $ACR_NAME.azurecr.io/geobox:latest"
powershell -Command "podman push $ACR_NAME.azurecr.io/geobox:latest"

az containerapp update \
    --name geobox-app-dev \
    --resource-group geobox-rg \
    --image $ACR_NAME.azurecr.io/geobox:latest
```

### Update Infrastructure

```bash
az deployment group create \
    --name geobox-deployment-$(date +%Y%m%d%H%M%S) \
    --resource-group geobox-rg \
    --template-file iac/main.bicep \
    --parameters <params>
```

## Resources

- [Azure Container Apps Documentation](https://learn.microsoft.com/en-us/azure/container-apps/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
