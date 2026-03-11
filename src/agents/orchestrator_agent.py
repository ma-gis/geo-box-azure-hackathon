"""
GeoBox Orchestrator Agent (Week 3 - Agent Framework Integration)

This agent orchestrates the GPS extraction and metadata enrichment workflow
using Microsoft Agent Framework and MCP tools.

It replaces the hardcoded workflow in main.py with agent-driven decision making.
"""

import os
import re
import json
import time
import asyncio
import structlog
import httpx
from typing import Dict, Optional
from azure.core.credentials import AzureKeyCredential, AccessToken
from azure.identity.aio import AzureCliCredential, ManagedIdentityCredential
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.azure import AzureOpenAIChatClient

logger = structlog.get_logger()


class _StaticBearerCredential:
    """Wraps a static bearer token as an AsyncTokenCredential (for containers)."""

    def __init__(self, token: str):
        self._token = AccessToken(token, int(time.time()) + 3600)

    async def get_token(self, *scopes, **kwargs) -> AccessToken:
        return self._token

    async def close(self):
        pass


class GeoBoxOrchestrator:
    """
    Orchestrator agent that coordinates GPS extraction workflow using Agent Framework
    """

    def __init__(
        self,
        mcp_exiftool_url: str,
        azure_openai_endpoint: Optional[str] = None,
        azure_openai_deployment: str = "gpt-4o",
    ):
        """
        Initialize the GeoBox orchestrator agent

        Args:
            mcp_exiftool_url: URL of the ExifTool MCP server (e.g., http://localhost:8081)
            azure_openai_endpoint: Azure OpenAI endpoint (optional, uses env var if not provided)
            azure_openai_deployment: Azure OpenAI deployment name
        """
        self.mcp_exiftool_url = mcp_exiftool_url
        self.azure_openai_endpoint = azure_openai_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_openai_deployment = azure_openai_deployment
        self.agent = None
        self.mcp_server = None
        self.credential = None

    def _get_credential(self):
        """
        Get the best available Azure TokenCredential.
        Priority order:
          1. AZURE_BEARER_TOKEN env var — static token for containers (expires ~1h)
          2. MSI/IDENTITY env vars — Managed Identity (Azure production with MSI enabled)
          3. AzureCliCredential — local dev (requires az login)
        Note: AzureKeyCredential is NOT a TokenCredential and cannot be used here.
        Use AzureOpenAIChatClient with api_key when an API key is available.
        """
        bearer_token = os.getenv("AZURE_BEARER_TOKEN")
        if bearer_token:
            logger.info("using_static_bearer_token_credential")
            return _StaticBearerCredential(bearer_token)

        if os.getenv("MSI_ENDPOINT") or os.getenv("IDENTITY_ENDPOINT"):
            logger.info("using_managed_identity_credential")
            return ManagedIdentityCredential()

        logger.info("using_azure_cli_credential")
        return AzureCliCredential()

    async def __aenter__(self):
        """Async context manager entry - initialize agent and MCP connections"""
        logger.info("initializing_geobox_orchestrator",
                   mcp_url=self.mcp_exiftool_url)

        try:
            # Create Azure credential
            self.credential = self._get_credential()

            # Create MCP tool connection to ExifTool server.
            # If MCP_API_KEY is set, pass it via a custom httpx client so the
            # gateway middleware on the ExifTool MCP server can authenticate.
            mcp_api_key = os.getenv("MCP_API_KEY", "")
            mcp_http_client = None
            if mcp_api_key:
                mcp_http_client = httpx.AsyncClient(
                    headers={"X-API-Key": mcp_api_key}
                )

            self.mcp_server = MCPStreamableHTTPTool(
                name="exiftool-mcp",
                description="ExifTool GPS extraction and metadata tools",
                url=self.mcp_exiftool_url,
                http_client=mcp_http_client,
            )
            await self.mcp_server.__aenter__()

            # Create Agent Framework chat client using AzureOpenAIChatClient.
            # This works with plain Azure OpenAI (no AI Foundry project needed)
            # and accepts both API key and credential-based auth.
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            chat_client = AzureOpenAIChatClient(
                endpoint=self.azure_openai_endpoint,
                deployment_name=self.azure_openai_deployment,
                api_key=api_key if api_key else None,
                credential=self.credential if not api_key else None,
            )
            logger.info("agent_client_initialized",
                       client_type="AzureOpenAIChatClient",
                       using_api_key=bool(api_key))

            self.agent = Agent(
                chat_client,
                self._get_agent_instructions(),
                name="GeoBoxOrchestrator",
                tools=self.mcp_server,
            )
            await self.agent.__aenter__()

            logger.info("geobox_orchestrator_initialized")
            return self

        except Exception as e:
            logger.error("orchestrator_initialization_failed", error=str(e), exc_info=True)
            # Cleanup on failure
            if self.mcp_server:
                await self.mcp_server.__aexit__(None, None, None)
            if self.agent:
                await self.agent.__aexit__(None, None, None)
            if self.credential and hasattr(self.credential, 'close'):
                await self.credential.close()
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources"""
        logger.info("shutting_down_geobox_orchestrator")

        if self.agent:
            await self.agent.__aexit__(exc_type, exc_val, exc_tb)

        if self.mcp_server:
            await self.mcp_server.__aexit__(exc_type, exc_val, exc_tb)

        if self.credential and hasattr(self.credential, 'close'):
            await self.credential.close()

    def _get_agent_instructions(self) -> str:
        """
        Get the system instructions for the orchestrator agent

        These instructions guide the agent's decision-making process
        """
        return """You are the GeoBox Orchestrator, an AI agent responsible for processing photos and videos to extract and validate GPS metadata.

Your workflow for each file:

1. **Extract GPS Data**: Use the extract_gps tool to get GPS coordinates from the uploaded file
   - The tool takes a file_path parameter
   - It returns latitude, longitude, altitude (optional), and timestamp

2. **Validate GPS Data**: Check if the extracted GPS coordinates are plausible
   - Latitude must be between -90 and 90
   - Longitude must be between -180 and 180
   - Reject Null Island coordinates (0.0, 0.0) — these indicate a missing GPS fix
   - If coordinates are outside valid ranges, set valid=false

3. **Return Structured Result**: You MUST respond with ONLY a valid JSON object — no prose,
   no markdown fences, no explanation text before or after. Use exactly this schema:

{
  "gps_found": true or false,
  "latitude": <number or null>,
  "longitude": <number or null>,
  "altitude": <number or null>,
  "gps_timestamp": "<ISO8601 string or null>",
  "confidence": <number between 0.0 and 1.0>,
  "valid": true or false,
  "notes": "<one sentence explaining the result>"
}

Guidelines:
- Always call extract_gps first before drawing conclusions
- If GPS extraction fails or returns no data, set gps_found=false, valid=false, confidence=0.0
- If no GPS data is found, that is a valid outcome (not an error) — set notes accordingly
- Focus on GPS extraction only — do not attempt to write Box metadata

Key Tools Available:
- extract_gps(file_path: str) - Extracts GPS coordinates from photo/video
- extract_all_metadata(file_path: str) - Gets all EXIF metadata (use if GPS extraction needs more context)
- get_exiftool_version() - Checks ExifTool availability (for debugging)
"""

    @staticmethod
    def _parse_agent_response(agent_text: str) -> Dict:
        """
        Parse the structured JSON response from the agent.

        Tolerates markdown code fences the model may wrap around the JSON.
        Falls back gracefully if the response is not valid JSON.

        Args:
            agent_text: Raw text response from the agent

        Returns:
            Parsed result dict with GPS fields, or an error dict
        """
        # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
        clean = re.sub(r"```(?:json)?\s*", "", agent_text).strip()
        # Remove trailing fence
        clean = re.sub(r"```\s*$", "", clean).strip()

        try:
            data = json.loads(clean)
            return {
                "success": True,
                "gps_found": bool(data.get("gps_found", False)),
                "latitude": float(data["latitude"]) if data.get("latitude") is not None else None,
                "longitude": float(data["longitude"]) if data.get("longitude") is not None else None,
                "altitude": float(data["altitude"]) if data.get("altitude") is not None else None,
                "gps_timestamp": data.get("gps_timestamp"),
                "confidence": float(data.get("confidence", 0.5)),
                "valid": bool(data.get("valid", False)),
                "notes": str(data.get("notes", "")),
                "agent_response": agent_text,
            }
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("agent_response_parse_failed",
                          error=str(e),
                          raw_length=len(agent_text))
            return {
                "success": False,
                "gps_found": False,
                "latitude": None,
                "longitude": None,
                "altitude": None,
                "gps_timestamp": None,
                "confidence": 0.0,
                "valid": False,
                "notes": f"Agent response could not be parsed as JSON: {e}",
                "agent_response": agent_text,
            }

    async def _enrich_with_geo(self, lat: float, lon: float) -> Dict:
        """
        Call the Geospatial MCP server to enrich GPS coordinates with:
          - Reverse-geocoded place name (Nominatim / OSM)
          - Terrain elevation in metres (Open-Elevation)
          - Land vs. water classification (Nominatim OSM type)

        Returns a dict with geo enrichment data, or an empty dict if the
        geo server is unavailable (non-fatal — GPS data is still valid).

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
        """
        geo_url = os.getenv("GEO_SERVER_URL", "http://localhost:8082")
        timeout = float(os.getenv("GEO_HTTP_TIMEOUT", "10"))

        # Pass gateway auth headers so the Geo MCP middleware can validate them.
        # X-Request-ID correlates this enrichment call to the parent file-processing request.
        request_id = str(__import__("uuid").uuid4())
        geo_headers: dict = {"X-Request-ID": request_id}
        mcp_api_key = os.getenv("MCP_API_KEY", "")
        if mcp_api_key:
            geo_headers["X-API-Key"] = mcp_api_key

        try:
            async with httpx.AsyncClient(timeout=timeout, headers=geo_headers) as client:
                # Use reverse_geocode_full to get geocoding + land/water in ONE Nominatim call,
                # then run elevation in parallel. This respects OSM's 1 req/sec rate limit.
                geocode_resp, elevation_resp = await asyncio.gather(
                    client.post(f"{geo_url}/tools/reverse_geocode_full",
                                json={"lat": lat, "lon": lon}),
                    client.post(f"{geo_url}/tools/get_elevation",
                                json={"lat": lat, "lon": lon}),
                    return_exceptions=True,
                )

            def _safe_json(resp) -> dict:
                """Extract .data from a ToolResponse, or empty dict on error."""
                if isinstance(resp, Exception):
                    return {}
                try:
                    body = resp.json()
                    return body.get("data", {}) if body.get("success") else {}
                except Exception:
                    return {}

            geocode = _safe_json(geocode_resp)
            elevation = _safe_json(elevation_resp)

            result = {
                "location_name": geocode.get("display_name", ""),
                "country": geocode.get("country", ""),
                "city": geocode.get("city", ""),
                "region": geocode.get("region", ""),
                "elevation_m": elevation.get("elevation_m"),
                "land_or_water": geocode.get("land_or_water", "unknown"),
            }

            logger.info("geo_enrichment_complete",
                       lat=lat, lon=lon,
                       country=result["country"],
                       city=result["city"],
                       land_or_water=result["land_or_water"],
                       elevation_m=result["elevation_m"])

            return result

        except Exception as e:
            logger.warning("geo_enrichment_failed",
                          lat=lat, lon=lon,
                          error=str(e),
                          message="Continuing without geo enrichment")
            return {}

    async def process_file(
        self,
        file_path: str,
        file_name: str,
        file_type: str
    ) -> Dict:
        """
        Process a file using the agent workflow

        Args:
            file_path: Local path to the downloaded file
            file_name: Original filename
            file_type: MIME type (image/jpeg, video/mp4, etc.)

        Returns:
            Dict containing processing result:
            {
                'success': bool,
                'gps_found': bool,
                'gps_data': {...} or None,
                'valid': bool,
                'agent_response': str,
                'error': str or None
            }
        """
        logger.info("orchestrator_processing_file",
                   file_name=file_name,
                   file_type=file_type)

        try:
            # Construct the agent prompt
            prompt = f"""Process this file and extract GPS metadata:

File Name: {file_name}
File Type: {file_type}
File Path: {file_path}

Please:
1. Extract GPS coordinates using the extract_gps tool
2. Validate the coordinates are within valid ranges
3. Provide a structured summary of the result
"""

            # Run the agent with MCP tools (tools registered at init time)
            result = await self.agent.run(prompt)

            # Parse the agent's response
            agent_text = result.text if hasattr(result, 'text') else str(result)

            logger.info("orchestrator_agent_completed",
                       file_name=file_name,
                       response_length=len(agent_text))

            # Parse structured JSON from agent response
            parsed = self._parse_agent_response(agent_text)

            logger.info("orchestrator_result_parsed",
                       file_name=file_name,
                       gps_found=parsed.get("gps_found"),
                       valid=parsed.get("valid"),
                       confidence=parsed.get("confidence"),
                       parse_success=parsed.get("success"))

            # Geo enrichment: reverse geocode + elevation + land/water
            # Only call when we have valid GPS coordinates
            geo = {}
            if parsed.get("gps_found") and parsed.get("latitude") is not None and parsed.get("longitude") is not None:
                geo = await self._enrich_with_geo(
                    lat=parsed["latitude"],
                    lon=parsed["longitude"],
                )

            return {
                **parsed,
                'file_name': file_name,
                'file_path': file_path,
                'geo': geo,
            }

        except Exception as e:
            logger.error("orchestrator_processing_failed",
                        file_name=file_name,
                        error=str(e),
                        exc_info=True)

            return {
                'success': False,
                'agent_response': None,
                'file_name': file_name,
                'file_path': file_path,
                'gps_found': False,
                'error': str(e)
            }

    async def health_check(self) -> Dict:
        """
        Check health of orchestrator and MCP connections.

        Uses a lightweight HTTP GET to the MCP server's /health endpoint
        instead of a full LLM round-trip, keeping /health fast and cheap.

        Returns:
            Dict with health status
        """
        # Derive the MCP base URL (strip /sse suffix if present)
        mcp_base = self.mcp_exiftool_url.removesuffix("/sse")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{mcp_base}/health")
                resp.raise_for_status()
                mcp_healthy = True
        except Exception as e:
            logger.warning("mcp_health_ping_failed",
                           url=f"{mcp_base}/health", error=str(e))
            mcp_healthy = False

        return {
            'status': 'healthy' if mcp_healthy else 'degraded',
            'orchestrator': 'initialized',
            'mcp_server_url': self.mcp_exiftool_url,
            'mcp_tools_available': mcp_healthy,
        }


# Example usage
async def example_usage():
    """Example of how to use the GeoBox orchestrator"""
    import asyncio

    # Configuration
    mcp_url = os.getenv("MCP_EXIFTOOL_URL", "http://localhost:8081/sse")

    async with GeoBoxOrchestrator(mcp_exiftool_url=mcp_url) as orchestrator:
        # Health check
        health = await orchestrator.health_check()
        print("Health:", health)

        # Process a file
        result = await orchestrator.process_file(
            file_path="/tmp/test.jpg",
            file_name="test.jpg",
            file_type="image/jpeg"
        )
        print("Result:", result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
