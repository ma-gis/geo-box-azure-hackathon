#!/usr/bin/env bash
# Watch GeoBox Azure Container App logs in real-time

echo "🔍 Watching GeoBox logs..."
echo "📍 App: geobox-app-dev"
echo "📍 Resource Group: geobox-rg"
echo ""
echo "Press Ctrl+C to stop"
echo "----------------------------------------"

az containerapp logs show \
    --name geobox-app-dev \
    --resource-group geobox-rg \
    --follow true \
    --tail 50 \
    --type console
