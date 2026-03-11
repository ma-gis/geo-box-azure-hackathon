# Copilot Instructions

## Overview
This file contains project-specific instructions and skills for GitHub Copilot. It ensures that Copilot aligns with the project's conventions, workflows, and architecture.

---

## Skills

### Deploy to Azure
**Description**: Automate the deployment of GeoBox to Azure. This skill builds container images using Podman, pushes them to Azure Container Registry (ACR), and deploys infrastructure using Bicep templates.

**Allowed Tools**: Bash, Read, Glob

**Steps**:
1. **Determine Deployment Scope**: Identify what to deploy based on arguments (`all`, `orchestrator`, `exiftool-mcp`, `geo-mcp`, `infra`).
2. **Authenticate with ACR**: Use Podman to log in to the Azure Container Registry.
3. **Build and Push Images**: Build container images for the specified components and push them to ACR.
4. **Deploy Infrastructure**: Use Bicep templates to deploy or update Azure resources.

**Context**:
- **Registry**: `geoboxsgqptyt4577n4.azurecr.io`
- **Resource Group**: `geobox-rg`
- **Applications**:
  - Orchestrator: `geobox-app-dev`
  - ExifTool MCP: `geobox-mcp-exiftool-dev`
  - Geo MCP: `geobox-mcp-geo-dev`
- **Azure OpenAI Endpoint**: `https://geobox-azure-openai.services.ai.azure.com/`

**Example Usage**:
- Deploy all components: `/deploy-azure all`
- Deploy only the orchestrator: `/deploy-azure orchestrator`

---

## Project Conventions

### Coding Standards
- Follow PEP 8 with 4-space indentation.
- Use `snake_case` for functions and variables.
- Use `PascalCase` for classes.
- Add type hints to all functions.

### Testing Guidelines
- Use `pytest` for unit and integration tests.
- Place tests in the `tests/` directory.
- Name test files as `test_<module>.py`.

### Commit Guidelines
- Use prefixes like `feat:`, `fix:`, `add:`.
- Keep commits scoped to one logical change.

---

## Architecture

### Key Components
- **GeoBox Orchestrator**: Microsoft Agent Framework orchestrator.
- **ExifTool MCP Server**: Handles GPS extraction.
- **Geo MCP Server**: Handles geospatial operations.

### Deployment
- **Azure Container Apps**: Orchestrator, ExifTool MCP, Geo MCP.
- **IaC**: Bicep templates for infrastructure.

---

## Troubleshooting

### Common Issues
1. **Orchestrator Initialization Failure**:
   - Check MCP server health.
   - Verify Azure OpenAI credentials.

2. **Metadata Not Applying**:
   - Ensure field keys have no underscores.
   - Validate field types (e.g., `float`, `string`).

3. **MCP Server Not Responding**:
   - Verify internal ingress configuration.
   - Check ExifTool installation in the container.

---

## References
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Box Platform API](https://developer.box.com/)
- [ExifTool Documentation](https://exiftool.org/)

---

## Critical Project Quirks

### 1. Box Metadata Field Keys - NO UNDERSCORES!
**CRITICAL**: Box automatically removes underscores from metadata field keys.

```python
# ❌ WRONG - These will fail
metadata = {
    'validation_status': 'valid',  # Box expects 'validationstatus'
    'gps_timestamp': '2024-01-01'  # Box expects 'gpstimestamp'
}

# ✅ CORRECT - No underscores
metadata = {
    'validationstatus': ['valid'],  # Also note: MultiSelect = ARRAY!
    'gpstimestamp': '2024-01-01'
}
```

**Field Types**:
- `latitude`, `longitude`, `altitude`, `confidence` → `float`
- `validationstatus` → `array` (MultiSelect field)
- `ainotes`, `processingdate`, `gpstimestamp` → `string`

### 2. Auto-Detection Mode
The app (`src/main.py`) automatically uses the Agent Framework orchestrator when Azure OpenAI is configured. Falls back to the direct extraction agent if initialization fails. No mode selection env var needed.

### 3. MCP Server URL
**Local**: `http://localhost:8081`
**Azure**: `http://geobox-mcp-exiftool-dev:8081` (internal Container Apps network)

### 4. Azure OpenAI Credentials
Agent Framework requires either:
- `AzureCliCredential()` - For local dev (must run `az login`)
- `ManagedIdentityCredential()` - For production Azure deployment