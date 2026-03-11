# 🌍 GeoBox - AI-Powered Geospatial Metadata Intelligence for Box

**AI Dev Days Hackathon 2026 Project**

Modernizing ExifTool with Azure AI and Microsoft Agent Framework to automatically extract and validate GPS metadata from photos and videos stored in Box.

---

## 🎯 Project Overview

GeoBox uses **ExifTool** + **Azure OpenAI** + **Box Platform** to automatically:

1. **Extract GPS data** from photos and videos uploaded to Box
2. **Validate coordinates** using AI reasoning (detect errors, impossible locations)
3. **Enrich Box files** with GPS metadata visible directly in Box preview
4. **Generate GPX tracks** from drone/action camera videos

**Target Users:** GIS professionals, field crews, surveyors, drone operators

---

## 🏆 Hackathon Hero Technologies Used

- ✅ **Microsoft Agent Framework** - Multi-agent system (Extraction + Validation agents)
- ✅ **Azure MCP** - Tool servers for ExifTool, Box, and Geospatial operations
- ✅ **Microsoft Foundry** - Enterprise workflow orchestration
- ✅ **Azure OpenAI** - GPS validation and anomaly detection
- ✅ **Azure Container Apps** - Serverless container hosting

---

## 🏗️ Architecture (Multi-Agent + MCP)

```
Box Upload → Webhook → GeoBox Orchestrator (Agent Framework)
                              ↓
                        MCP Client
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
            ExifTool MCP Server   Geospatial MCP Server
            (GPS Extraction)      (Reverse Geocode, Elevation)
                    ↓
            Box Metadata API (GPS enriched)
```

**Key Components:**
- **GeoBox Orchestrator**: Microsoft Agent Framework agent with Azure OpenAI GPT-4o
- **ExifTool MCP Server**: Model Context Protocol server exposing GPS extraction tools
- **MCP Client**: Connects orchestrator to MCP tools via HTTP
- **Box Integration**: Webhooks + Metadata API
- **Azure Container Apps**: 3 separate apps (Orchestrator + ExifTool MCP + Geo MCP), scale-to-zero

**See detailed architecture**: [architecture.md](docs/architecture.md)

---

## 📦 Project Structure

```
geo-box-azure-hackathon/
├── Containerfile              # Main app container (Orchestrator)
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
│
├── src/
│   ├── main.py               # FastAPI app (Agent Framework + fallback)
│   ├── config.py             # Configuration management
│   ├── box_client.py         # Box SDK wrapper
│   │
│   ├── agents/
│   │   ├── extraction_agent.py    # ExifTool GPS extraction (fallback)
│   │   ├── validation_agent.py    # Azure OpenAI validation (fallback)
│   │   └── orchestrator_agent.py  # Agent Framework orchestrator
│   │
│   └── mcp_servers/
│       ├── exiftool_server/
│       │   ├── server.py           # MCP tool definitions
│       │   ├── http_server.py      # HTTP wrapper for Azure
│       │   ├── sse_server.py       # Streamable HTTP for Agent Framework
│       │   ├── Containerfile       # MCP server container
│       │   └── requirements.txt    # MCP server dependencies
│       └── geo_server/
│           ├── http_server.py      # Reverse geocode + elevation API
│           ├── Containerfile       # Geo MCP container
│           └── requirements.txt    # Geo server dependencies
│
├── iac/
│   └── main.bicep            # Infrastructure as Code (3 Container Apps)
│
├── scripts/
│   ├── deploy-with-bicep.ps1 # Deploy both containers to Azure
│   └── create_box_template.py # Box metadata template setup
│
├── tests/
│   ├── test_integration.py        # Integration + unit tests
│   └── test_exiftool_gps.py       # ExifTool extraction tests
│
└── docs/
    ├── architecture.md            # Detailed architecture docs
    ├── deployment_guide.md        # Azure deployment guide
    └── BOX_SETUP.md              # Box platform configuration
```

---

## 🚀 Quick Start (Local Development with Podman)

### Prerequisites

- **Podman** installed ([Download](https://podman.io/getting-started/installation))
- **podman-compose** installed: `pip install podman-compose`
- **Azure OpenAI** API access
- **Box Developer** account

### 1. Clone and Setup

```powershell
# Clone the repo
git clone https://github.com/your-username/geo-box-azure-hackathon.git
cd geo-box-azure-hackathon

# Copy environment template
copy .env.example .env

# Edit .env with your Azure OpenAI credentials
notepad .env
```

### 2. Configure Box

1. Create Box JWT app at [Box Developer Console](https://app.box.com/developers/console)
2. Download JWT config JSON
3. Save as `config/box_config.json`
4. Create metadata template "geoBoxIntelligence" in Box Admin Console

### 3. Build with Podman

```powershell
.\scripts\build.ps1
```

### 4. Run Locally

```powershell
.\scripts\run-local.ps1
```

GeoBox will be available at: **http://localhost:8080**

### 5. Test Health Check

```powershell
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "exiftool_version": "12.70",
  "box_connected": true,
  "agents": {
    "extraction": "ready",
    "validation": "ready"
  }
}
```

---

## ☁️ Deploy to Azure

### Prerequisites

- Azure CLI installed: `az login`
- Azure subscription with credits

### Deploy

```powershell
.\scripts\deploy-azure.ps1 `
  -ResourceGroup "geobox-rg" `
  -Location "eastus" `
  -RegistryName "geoboxregistry" `
  -AppName "geobox-app"
```

This script will:
1. Create Azure Resource Group
2. Create Azure Container Registry
3. Build and push container image
4. Create Azure Container Apps environment
5. Deploy GeoBox with scale-to-zero configuration

**Cost:** ~$0-5 for entire hackathon (within free tier!)

---

## 🔧 Configuration

### Environment Variables (.env)

```ini
# Azure OpenAI
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o

# Box
BOX_CONFIG_PATH=./config/box_config.json
BOX_METADATA_TEMPLATE=geoBoxIntelligence

# Application
LOG_LEVEL=INFO
```

### Box Metadata Template

Create this template in Box Admin Console:

**Template Key:** `geoBoxIntelligence`
**Scope:** `enterprise`

**Fields:**
- `latitude` (float) - GPS latitude
- `longitude` (float) - GPS longitude
- `altitude` (float) - GPS altitude in meters
- `gps_timestamp` (string) - When GPS was recorded
- `validation_status` (enum) - `valid`, `flagged`, `no_gps`, `error`
- `confidence` (float) - AI confidence score (0-1)
- `ai_notes` (string) - AI validation notes
- `processing_date` (string) - When processed

---

## 📸 Usage

### 1. Upload Photo/Video to Box

Use Box Mobile app or desktop to upload geotagged photos/videos.

### 2. Automatic Processing

GeoBox webhook receives upload event and:
1. Downloads file
2. Extracts GPS with ExifTool
3. Validates GPS with Azure OpenAI
4. Writes metadata back to Box
5. (For videos) Generates and uploads GPX track file

### 3. View Results in Box

Click the file in Box → Preview panel shows GPS metadata:

```
📍 Location
  Latitude:  43.0731°N
  Longitude: -89.4012°W
  Altitude:  275m

🤖 AI Validation
  Status: Valid ✅
  Confidence: 95%
  Notes: Location validated in Madison, WI
```

---

## 🧪 Testing

### Run Unit Tests

```powershell
podman-compose run geobox pytest tests/
```

### Test with Sample Photo

```powershell
# Upload test photo to Box folder with webhook configured
# Watch logs:
podman logs -f geobox-dev
```

---

## 🛠️ Development

### View Logs

```powershell
podman logs -f geobox-dev
```

### Rebuild After Code Changes

```powershell
.\scripts\build.ps1
podman-compose restart
```

### Enter Container Shell

```powershell
podman exec -it geobox-dev /bin/bash

# Test ExifTool directly
exiftool -ver
exiftool -GPSLatitude -GPSLongitude /path/to/photo.jpg
```

---

## 📊 Supported File Formats

| Type | Formats | GPS Source | Output |
|------|---------|------------|--------|
| **Photos** | JPEG, PNG, HEIC, RAW | EXIF GPS tags | Box metadata |
| **Videos** | MP4, MOV, AVI | GPS track in metadata | Box metadata + GPX file |
| **Drone Videos** | DJI, GoPro formats | Telemetry data | Box metadata + GPX file |

---

## 🎯 Hackathon Demo

### Demo Script (5 minutes)

**Act 1: The Problem** (30 sec)
- Show field crew photos with buried GPS data
- Current process: Manual ExifTool commands

**Act 2: Upload to Box** (45 sec)
- Box Mobile app upload (3 photos)
- Show webhook triggered in logs

**Act 3: AI Processing** (60 sec)
- Real-time logs showing:
  - ExifTool extraction
  - AI validation
  - Metadata writing

**Act 4: Results** (90 sec)
- Open file in Box
- Show GPS metadata panel
- Box AI search: "photos in downtown Madison"
- Download GeoJSON for GIS import

**Closing** (30 sec)
- "From buried EXIF to searchable metadata in 2 minutes"
- "ExifTool + Azure AI + Box Platform"

---

## 💰 Cost Breakdown (5 weeks)

| Service | Cost |
|---------|------|
| Azure Container Apps | $0 (free tier) |
| Azure OpenAI | ~$10-15 |
| Azure Container Registry | ~$6 |
| **TOTAL** | **~$16-21** |

Your $200 Azure credits: **$180 remaining** ✅

---

## 🤝 Contributing

This is a hackathon project, but contributions welcome!

1. Fork the repo
2. Create feature branch
3. Make changes
4. Test with Podman
5. Submit PR

---

## 📚 Resources

- [ExifTool Documentation](https://exiftool.org/)
- [Box Platform API](https://developer.box.com/)
- [Azure OpenAI](https://learn.microsoft.com/azure/ai-services/openai/)
- [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
- [Podman Documentation](https://docs.podman.io/)

---

## 📝 License

MIT License - see LICENSE file

---

## 👤 Author

**Mahtab Alam** - AI Dev Days Hackathon 2026

Built with ❤️ for the GIS community

---

## 🎓 Acknowledgments

- ExifTool by Phil Harvey
- Box Platform team
- Microsoft Azure AI team
- GIS community for inspiration
