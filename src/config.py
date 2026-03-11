"""
Configuration management for GeoBox
"""

from pydantic_settings import BaseSettings
from typing import Dict, Optional
import json
from pathlib import Path

class Settings(BaseSettings):
    """Application settings"""

    # Azure OpenAI
    AZURE_OPENAI_API_KEY: Optional[str] = None  # Optional: use managed identity if absent
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-4o"

    # Box Configuration
    BOX_CONFIG_PATH: str = "./config/box_config.json"      # file path (local dev fallback)
    BOX_CONFIG_JSON: Optional[str] = None                   # full JSON string (production secret)
    BOX_METADATA_TEMPLATE: str = "geoBoxIntelligence"
    BOX_ENTERPRISE_SCOPE: str = "enterprise_909145061"      # Box enterprise scope for metadata API
    BOX_WEBHOOK_SIGNATURE_KEY: Optional[str] = None         # HMAC key for webhook verification

    # MCP Servers
    GEO_SERVER_URL: str = "http://localhost:8082"
    MCP_API_KEY: Optional[str] = None  # Shared secret for MCP gateway auth (optional)

    # Application
    APP_NAME: str = "GeoBox"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True

    def get_box_config(self) -> Dict:
        """Load Box JWT configuration.

        Priority:
          1. BOX_CONFIG_JSON env var (full JSON string — production)
          2. BOX_CONFIG_PATH file path (local dev fallback)
        """
        if self.BOX_CONFIG_JSON:
            return json.loads(self.BOX_CONFIG_JSON)

        config_path = Path(self.BOX_CONFIG_PATH)
        if not config_path.exists():
            raise FileNotFoundError(f"Box config not found: {self.BOX_CONFIG_PATH}")

        with open(config_path, 'r') as f:
            return json.load(f)

# Global settings instance
settings = Settings()
