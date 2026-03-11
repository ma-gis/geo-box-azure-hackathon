---
name: deploy-azure
description: Automate the deployment of GeoBox to Azure. This skill builds container images using Podman, pushes them to Azure Container Registry (ACR), and deploys infrastructure using Bicep templates.
allowed-tools: Bash, Read, Glob
---

# Skill Instructions

## Steps
1. **Determine Deployment Scope**: Identify what to deploy based on arguments (`all`, `orchestrator`, `exiftool-mcp`, `geo-mcp`, `infra`).
2. **Authenticate with ACR**: Use Podman to log in to the Azure Container Registry.
3. **Build and Push Images**: Build container images for the specified components and push them to ACR.
4. **Deploy Infrastructure**: Use Bicep templates to deploy or update Azure resources.

## Context
- **Registry**: `geoboxsgqptyt4577n4.azurecr.io`
- **Resource Group**: `geobox-rg`
- **Applications**:
  - Orchestrator: `geobox-app-dev`
  - ExifTool MCP: `geobox-mcp-exiftool-dev`
  - Geo MCP: `geobox-mcp-geo-dev`
- **Azure OpenAI Endpoint**: `https://geobox-azure-openai.services.ai.azure.com/`

## Example Usage
- Deploy all components: `/deploy-azure all`
- Deploy only the orchestrator: `/deploy-azure orchestrator`