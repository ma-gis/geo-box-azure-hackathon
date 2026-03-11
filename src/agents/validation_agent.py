"""
Validation Agent - Validates GPS coordinates using Azure OpenAI
"""

import structlog
from typing import Dict
from openai import AzureOpenAI
import json

from src.config import settings

logger = structlog.get_logger()

class ValidationAgent:
    """Agent responsible for validating GPS coordinates using AI reasoning"""

    def __init__(self):
        """Initialize Azure OpenAI client"""
        try:
            # Check if Azure OpenAI credentials are configured
            if not settings.AZURE_OPENAI_API_KEY or settings.AZURE_OPENAI_API_KEY == "your_azure_openai_api_key_here":
                logger.warning("azure_openai_not_configured",
                             message="Azure OpenAI validation disabled - credentials not configured")
                self.client = None
                return

            self.client = AzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version="2024-02-01",
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
            )
            logger.info("validation_agent_initialized")

        except Exception as e:
            logger.error("validation_agent_init_failed", error=str(e))
            self.client = None

    async def validate_gps(self, gps_data: Dict, file_name: str) -> Dict:
        """
        Validate GPS coordinates using Azure OpenAI

        Args:
            gps_data: Dictionary containing latitude, longitude, altitude
            file_name: Name of the file being processed

        Returns:
            Dictionary with validation results:
            {
                'valid': bool,
                'confidence': float (0-1),
                'notes': str
            }
        """
        try:
            # If Azure OpenAI not configured, return basic range validation
            if self.client is None:
                lat = gps_data.get('latitude', 0)
                lon = gps_data.get('longitude', 0)
                basic_valid = (-90 <= lat <= 90) and (-180 <= lon <= 180)
                return {
                    'valid': basic_valid,
                    'confidence': 0.7,
                    'notes': 'Basic range validation only (Azure OpenAI not configured)'
                }

            logger.info("validating_gps",
                       latitude=gps_data.get('latitude'),
                       longitude=gps_data.get('longitude'))

            # Build validation prompt
            prompt = self._build_validation_prompt(gps_data, file_name)

            # Call Azure OpenAI
            response = self.client.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a geospatial data validation expert. Analyze GPS coordinates and determine if they are valid and plausible."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=500
            )

            # Parse AI response
            result = json.loads(response.choices[0].message.content)

            logger.info("gps_validation_complete",
                       valid=result.get('valid'),
                       confidence=result.get('confidence'))

            return {
                'valid': result.get('valid', False),
                'confidence': result.get('confidence', 0.0),
                'notes': result.get('notes', 'No validation notes provided')
            }

        except Exception as e:
            logger.warning("validation_fallback",
                          error=str(e)[:200],  # Truncate long error messages
                          message="Azure OpenAI unavailable - using basic range validation")

            # Fallback to basic range validation when AI is unavailable
            lat = gps_data.get('latitude', 0)
            lon = gps_data.get('longitude', 0)
            basic_valid = (-90 <= lat <= 90) and (-180 <= lon <= 180)

            return {
                'valid': basic_valid,
                'confidence': 0.7,
                'notes': 'Basic range validation (Azure OpenAI quota/deployment unavailable)'
            }

    def _build_validation_prompt(self, gps_data: Dict, file_name: str) -> str:
        """Build validation prompt for OpenAI"""

        latitude = gps_data.get('latitude')
        longitude = gps_data.get('longitude')
        altitude = gps_data.get('altitude', 'unknown')

        prompt = f"""
Validate the following GPS coordinates extracted from a file:

File: {file_name}
Latitude: {latitude}
Longitude: {longitude}
Altitude: {altitude}

Please check:
1. Are the coordinates in valid range? (Latitude: -90 to 90, Longitude: -180 to 180)
2. Are the coordinates plausible? (Not in middle of ocean unless it's a boat/ship photo)
3. Any obvious errors or anomalies?

Return a JSON response with:
{{
    "valid": true or false,
    "confidence": 0.0 to 1.0 (how confident you are in this validation),
    "notes": "Brief explanation of your validation decision"
}}

Examples:
- Coordinates in a city: valid=true, confidence=0.95
- Coordinates in ocean (for land photo): valid=false, confidence=0.8
- Coordinates at 0,0 (null island): valid=false, confidence=0.99
- Coordinates out of range: valid=false, confidence=1.0
"""

        return prompt
