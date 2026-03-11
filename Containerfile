# Containerfile for GeoBox (Podman-compatible)
# Base image with Python
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies and ExifTool
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libimage-exiftool-perl \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Verify ExifTool installation
RUN exiftool -ver && echo "ExifTool installed successfully"

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Box JWT config is injected at runtime via BOX_CONFIG_JSON env var (Container Apps secret).
# For local dev, mount config/box_config.json via BOX_CONFIG_PATH.

# Create temp directory for file processing
RUN mkdir -p /tmp/geobox

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application (consolidated into src.main — supports both agent framework and fallback)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
