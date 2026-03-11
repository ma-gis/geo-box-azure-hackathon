# GeoBox Quick Start Guide

Get GeoBox running locally in 10 minutes!

---

## Prerequisites Checklist

- [ ] Podman installed ([Download](https://podman.io/getting-started/installation))
- [ ] `podman-compose` installed: `pip install podman-compose`
- [ ] Azure OpenAI API access
- [ ] Box Developer account
- [ ] Git installed

---

## Step 1: Clone Repository (1 min)

```powershell
cd C:\Users\mahta\repos
git clone https://github.com/yourusername/geo-box-azure-hackathon.git
cd geo-box-azure-hackathon
```

---

## Step 2: Configure Environment (2 min)

### Create .env file

```powershell
copy .env.example .env
notepad .env
```

### Edit .env with your credentials:

```ini
AZURE_OPENAI_API_KEY=your_actual_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

**Where to get these:**
- Azure Portal → Azure OpenAI resource → Keys and Endpoint

---

## Step 3: Configure Box (3 min)

### Create Box App

1. Go to https://app.box.com/developers/console
2. Create Custom App (JWT)
3. Download config JSON
4. Save as `config/box_config.json`

### Create Metadata Template

1. Box Admin Console → Metadata
2. Create template: `geoBoxIntelligence`
3. Add fields (see `docs/BOX_SETUP.md` for details)

---

## Step 4: Build Container (2 min)

```powershell
.\scripts\build.ps1
```

**Expected output:**
```
Building GeoBox container with Podman...
STEP 1/10: FROM python:3.11-slim
...
Build successful!
Image: geobox:latest
```

---

## Step 5: Run Locally (1 min)

```powershell
.\scripts\run-local.ps1
```

**Expected output:**
```
Starting GeoBox with Podman...
GeoBox is running!
API: http://localhost:8080
Health Check: http://localhost:8080/health
```

---

## Step 6: Test (1 min)

### Health Check

```powershell
curl http://localhost:8080/health
```

**Expected response:**
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

### Upload Test Photo

1. Take a geotagged photo with your phone
2. Upload to Box folder (with webhook configured)
3. Watch logs:
   ```powershell
   podman logs -f geobox-dev
   ```
4. Refresh file in Box → Check metadata panel

---

## Common Issues

### ❌ "ExifTool not found"
- **Solution:** Rebuild container: `.\scripts\build.ps1`

### ❌ "Box connection failed"
- **Check:** Is `config/box_config.json` present?
- **Check:** Is Box app authorized in Admin Console?

### ❌ "Azure OpenAI error"
- **Check:** Is API key correct in `.env`?
- **Check:** Is endpoint URL correct?
- **Check:** Do you have GPT-4 deployment?

---

## Next Steps

✅ **GeoBox is running locally!**

**Now try:**
- [ ] Upload geotagged photo to Box → Check metadata
- [ ] Upload video with GPS → Check for GPX file
- [ ] Deploy to Azure: `.\scripts\deploy-with-bicep.ps1`

---

## Useful Commands

```powershell
# View logs
podman logs -f geobox-dev

# Stop container
podman-compose down

# Restart after code changes
.\scripts\build.ps1
podman-compose restart

# Enter container shell
podman exec -it geobox-dev /bin/bash

# Test ExifTool inside container
podman exec geobox-dev exiftool -ver
```

---

**Happy GeoBoxing! 🌍📦**
