"""
GeoBox Integration Tests

Tests for Agent Framework integration, MCP server communication,
and metadata building. Verifies the multi-agent architecture works correctly.
"""

import pytest
import asyncio
import os
from pathlib import Path

# Test prerequisites
pytestmark = pytest.mark.asyncio


class TestMCPServer:
    """Tests for ExifTool MCP Server"""

    async def test_mcp_server_health(self):
        """Test MCP server is reachable and healthy"""
        import httpx

        mcp_url = os.getenv("MCP_EXIFTOOL_URL", "http://localhost:8081")

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{mcp_url}/health")
            assert response.status_code == 200

            health_data = response.json()
            assert health_data["status"] == "healthy"
            assert "exiftool_version" in health_data

    async def test_mcp_server_list_tools(self):
        """Test MCP server exposes tools correctly"""
        import httpx

        mcp_url = os.getenv("MCP_EXIFTOOL_URL", "http://localhost:8081")

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{mcp_url}/tools")
            assert response.status_code == 200

            tools_data = response.json()
            assert "tools" in tools_data

            tool_names = [tool["name"] for tool in tools_data["tools"]]
            assert "extract_gps" in tool_names
            assert "get_exiftool_version" in tool_names


class TestOrchestratorAgent:
    """Tests for GeoBox Orchestrator Agent"""

    async def test_orchestrator_initialization(self):
        """Test orchestrator agent can be initialized"""
        from src.agents.orchestrator_agent import GeoBoxOrchestrator

        mcp_url = os.getenv("MCP_EXIFTOOL_URL", "http://localhost:8081")

        try:
            async with GeoBoxOrchestrator(mcp_exiftool_url=mcp_url) as orchestrator:
                assert orchestrator is not None
                assert orchestrator.agent is not None
                assert orchestrator.mcp_server is not None
        except Exception as e:
            # If initialization fails due to missing Azure credentials, that's expected in test environment
            if "AZURE_OPENAI_ENDPOINT" not in os.environ:
                pytest.skip("Azure OpenAI credentials not configured")
            else:
                raise

    async def test_orchestrator_health_check(self):
        """Test orchestrator health check"""
        from src.agents.orchestrator_agent import GeoBoxOrchestrator

        mcp_url = os.getenv("MCP_EXIFTOOL_URL", "http://localhost:8081")

        try:
            async with GeoBoxOrchestrator(mcp_exiftool_url=mcp_url) as orchestrator:
                health = await orchestrator.health_check()

                assert "status" in health
                assert "mcp_server_url" in health
                assert health["mcp_server_url"] == mcp_url
        except Exception:
            if "AZURE_OPENAI_ENDPOINT" not in os.environ:
                pytest.skip("Azure OpenAI credentials not configured")
            else:
                raise


class TestEndToEndWorkflow:
    """End-to-end tests for GPS extraction workflow"""

    @pytest.fixture
    def sample_image_with_gps(self):
        """Create a sample image with GPS metadata for testing"""
        # TODO: Create a test image with GPS EXIF data
        # For now, skip if test file doesn't exist
        test_file = Path("/tmp/test_gps.jpg")
        if not test_file.exists():
            pytest.skip("Test GPS image not available")
        return str(test_file)

    async def test_full_workflow(self, sample_image_with_gps):
        """Test complete GPS extraction workflow with orchestrator"""
        from src.agents.orchestrator_agent import GeoBoxOrchestrator

        mcp_url = os.getenv("MCP_EXIFTOOL_URL", "http://localhost:8081")

        try:
            async with GeoBoxOrchestrator(mcp_exiftool_url=mcp_url) as orchestrator:
                result = await orchestrator.process_file(
                    file_path=sample_image_with_gps,
                    file_name="test_gps.jpg",
                    file_type="image/jpeg"
                )

                assert result is not None
                assert "success" in result
                assert "agent_response" in result
        except Exception:
            if "AZURE_OPENAI_ENDPOINT" not in os.environ:
                pytest.skip("Azure OpenAI credentials not configured")
            else:
                raise


class TestGeoServer:
    """Tests for the Geospatial MCP Server and geo enrichment helpers."""

    pytestmark = []  # Override module-level asyncio mark — sync tests

    # ── Unit tests for _build_geo_notes (no network, no Azure) ───────────────

    def test_build_geo_notes_full(self):
        """Full geo dict produces a readable summary."""
        from src.main import _build_geo_notes

        geo = {
            "city": "San Francisco",
            "region": "California",
            "country": "United States",
            "land_or_water": "land",
            "elevation_m": 16.0,
        }
        notes = _build_geo_notes(geo)

        assert "San Francisco" in notes
        assert "California" in notes
        assert "United States" in notes
        assert "land" in notes
        assert "16m" in notes

    def test_build_geo_notes_empty(self):
        """Empty geo dict returns empty string — no crash."""
        from src.main import _build_geo_notes

        assert _build_geo_notes({}) == ""
        assert _build_geo_notes(None) == ""  # type: ignore[arg-type]

    def test_build_geo_notes_partial(self):
        """Partial geo data (no city) still works gracefully."""
        from src.main import _build_geo_notes

        geo = {"country": "France", "land_or_water": "land", "elevation_m": 35.0}
        notes = _build_geo_notes(geo)

        assert "France" in notes
        assert "land" in notes
        assert "35m" in notes

    def test_build_geo_notes_water_no_elevation(self):
        """Ocean coordinates: water classification, elevation may be None."""
        from src.main import _build_geo_notes

        geo = {"land_or_water": "water", "elevation_m": None, "country": ""}
        notes = _build_geo_notes(geo)

        assert "water" in notes
        assert "m." not in notes  # elevation not included when None

    def test_build_metadata_includes_geo_notes(self):
        """_build_box_metadata embeds geo notes into ainotes."""
        from src.main import _build_box_metadata

        result = {
            "success": True,
            "gps_found": True,
            "latitude": 37.7749,
            "longitude": -122.4194,
            "altitude": 16.0,
            "gps_timestamp": None,
            "confidence": 0.9,
            "valid": True,
            "notes": "Valid GPS fix.",
        }
        geo = {
            "city": "San Francisco",
            "region": "California",
            "country": "United States",
            "land_or_water": "land",
            "elevation_m": 16.0,
        }
        metadata = _build_box_metadata(result, geo=geo)

        assert "San Francisco" in metadata["ainotes"]
        assert "land" in metadata["ainotes"]
        assert metadata["validationstatus"] == ["valid"]
        # Geo notes embedded in ainotes — no new Box template fields needed
        for key in metadata:
            assert "_" not in key, f"Key '{key}' contains underscore — Box will reject it"

    def test_build_metadata_no_geo_still_works(self):
        """When geo is None/absent, metadata is still built correctly."""
        from src.main import _build_box_metadata

        result = {
            "success": True,
            "gps_found": True,
            "latitude": 51.5074,
            "longitude": -0.1278,
            "altitude": None,
            "gps_timestamp": None,
            "confidence": 0.85,
            "valid": True,
            "notes": "GPS found.",
        }
        metadata = _build_box_metadata(result, geo=None)

        assert metadata["validationstatus"] == ["valid"]
        assert "GPS found." in metadata["ainotes"]
        assert "latitude" in metadata
        assert "longitude" in metadata

    # ── Integration test (requires running geo server) ────────────────────────

    async def test_geo_server_health(self):
        """Geo server health endpoint should return 200."""
        import httpx

        geo_url = os.getenv("GEO_SERVER_URL", "http://localhost:8082")
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{geo_url}/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "healthy"
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip("Geo server not running (start with: uvicorn http_server:app --port 8082)")

    async def test_geo_server_reverse_geocode(self):
        """Reverse geocode San Francisco coordinates."""
        import httpx

        geo_url = os.getenv("GEO_SERVER_URL", "http://localhost:8082")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{geo_url}/tools/reverse_geocode",
                    json={"lat": 37.7749, "lon": -122.4194},
                )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            geo = data["data"]
            assert "Francisco" in geo["display_name"] or "California" in geo.get("region", "")
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip("Geo server not running")

    async def test_geo_server_list_tools(self):
        """Geo server /tools should list all three tools."""
        import httpx

        geo_url = os.getenv("GEO_SERVER_URL", "http://localhost:8082")
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{geo_url}/tools")
            assert resp.status_code == 200
            tool_names = [t["name"] for t in resp.json()["tools"]]
            assert "reverse_geocode" in tool_names
            assert "get_elevation" in tool_names
            assert "check_land_or_water" in tool_names
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip("Geo server not running")


class TestStructuredAgentResponse:
    """Unit tests for JSON response parsing and Box metadata building — no Azure required."""

    pytestmark = []  # Override module-level asyncio mark — these tests are synchronous

    def test_parse_valid_json(self):
        """Agent returns clean JSON — should parse all fields correctly."""
        from src.agents.orchestrator_agent import GeoBoxOrchestrator

        raw = '{"gps_found": true, "latitude": 37.7749, "longitude": -122.4194, "altitude": 16.0, "gps_timestamp": "2024-06-01T12:00:00Z", "confidence": 0.95, "valid": true, "notes": "GPS coordinates found and valid."}'
        result = GeoBoxOrchestrator._parse_agent_response(raw)

        assert result["success"] is True
        assert result["gps_found"] is True
        assert result["latitude"] == pytest.approx(37.7749)
        assert result["longitude"] == pytest.approx(-122.4194)
        assert result["altitude"] == pytest.approx(16.0)
        assert result["gps_timestamp"] == "2024-06-01T12:00:00Z"
        assert result["confidence"] == pytest.approx(0.95)
        assert result["valid"] is True
        assert "GPS" in result["notes"]

    def test_parse_json_with_markdown_fence(self):
        """Agent wraps JSON in markdown code fence — should be stripped correctly."""
        from src.agents.orchestrator_agent import GeoBoxOrchestrator

        raw = '```json\n{"gps_found": false, "latitude": null, "longitude": null, "altitude": null, "gps_timestamp": null, "confidence": 0.0, "valid": false, "notes": "No GPS data in file."}\n```'
        result = GeoBoxOrchestrator._parse_agent_response(raw)

        assert result["success"] is True
        assert result["gps_found"] is False
        assert result["latitude"] is None
        assert result["longitude"] is None
        assert result["confidence"] == pytest.approx(0.0)
        assert result["valid"] is False

    def test_parse_json_with_plain_fence(self):
        """Agent uses plain ``` fence without language tag."""
        from src.agents.orchestrator_agent import GeoBoxOrchestrator

        raw = '```\n{"gps_found": true, "latitude": 51.5074, "longitude": -0.1278, "altitude": null, "gps_timestamp": null, "confidence": 0.8, "valid": true, "notes": "London coordinates."}\n```'
        result = GeoBoxOrchestrator._parse_agent_response(raw)

        assert result["success"] is True
        assert result["latitude"] == pytest.approx(51.5074)
        assert result["longitude"] == pytest.approx(-0.1278)

    def test_parse_malformed_response(self):
        """Agent returns prose instead of JSON — should return error dict without raising."""
        from src.agents.orchestrator_agent import GeoBoxOrchestrator

        raw = "I found GPS coordinates with latitude 37.77 and longitude -122.41 in the file."
        result = GeoBoxOrchestrator._parse_agent_response(raw)

        assert result["success"] is False
        assert result["gps_found"] is False
        assert result["latitude"] is None
        assert result["longitude"] is None
        assert result["confidence"] == pytest.approx(0.0)
        assert "parse" in result["notes"].lower() or "json" in result["notes"].lower()
        assert result["agent_response"] == raw

    def test_build_metadata_with_valid_gps(self):
        """Valid GPS result should produce full Box metadata dict with correct keys."""
        from src.main import _build_box_metadata

        result = {
            "success": True,
            "gps_found": True,
            "latitude": 37.7749,
            "longitude": -122.4194,
            "altitude": 16.0,
            "gps_timestamp": "2024-06-01T12:00:00Z",
            "confidence": 0.95,
            "valid": True,
            "notes": "Valid GPS fix found.",
        }
        metadata = _build_box_metadata(result)

        # Status must be array (MultiSelect)
        assert metadata["validationstatus"] == ["valid"]
        # Coordinates present and typed as float
        assert metadata["latitude"] == pytest.approx(37.7749)
        assert metadata["longitude"] == pytest.approx(-122.4194)
        assert metadata["altitude"] == pytest.approx(16.0)
        assert metadata["gpstimestamp"] == "2024-06-01T12:00:00Z"
        assert metadata["confidence"] == pytest.approx(0.95)
        assert "processingdate" in metadata
        assert "ainotes" in metadata
        # No underscores in any key (Box requirement)
        for key in metadata:
            assert "_" not in key, f"Key '{key}' contains underscore — Box will reject it"

    def test_build_metadata_no_gps(self):
        """No GPS result should produce no_gps status and no coordinate fields."""
        from src.main import _build_box_metadata

        result = {
            "success": True,
            "gps_found": False,
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "gps_timestamp": None,
            "confidence": 0.0,
            "valid": False,
            "notes": "No GPS metadata found in file.",
        }
        metadata = _build_box_metadata(result)

        assert metadata["validationstatus"] == ["no_gps"]
        assert "latitude" not in metadata
        assert "longitude" not in metadata
        assert "altitude" not in metadata
        assert "gpstimestamp" not in metadata

    def test_build_metadata_gps_found_but_invalid(self):
        """GPS found but failed validation — should be 'processed' not 'valid'."""
        from src.main import _build_box_metadata

        result = {
            "success": True,
            "gps_found": True,
            "latitude": 0.0,
            "longitude": 0.0,  # Null Island
            "altitude": None,
            "gps_timestamp": None,
            "confidence": 0.1,
            "valid": False,
            "notes": "Null Island coordinates rejected.",
        }
        metadata = _build_box_metadata(result)

        assert metadata["validationstatus"] == ["processed"]
        # Coordinates still written even when validation fails
        assert metadata["latitude"] == pytest.approx(0.0)
        assert metadata["longitude"] == pytest.approx(0.0)

    def test_build_metadata_parse_error(self):
        """Parse failure (success=False) should produce error status."""
        from src.main import _build_box_metadata

        result = {
            "success": False,
            "gps_found": False,
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "gps_timestamp": None,
            "confidence": 0.0,
            "valid": False,
            "notes": "Agent response could not be parsed as JSON.",
        }
        metadata = _build_box_metadata(result)

        assert metadata["validationstatus"] == ["error"]


class TestFallbackMode:
    """Tests for fallback mode when orchestrator is unavailable"""

    async def test_fallback_extraction(self):
        """Test direct extraction agent still works (fallback mode)"""
        from src.agents.extraction_agent import ExtractionAgent

        agent = ExtractionAgent()

        # Test ExifTool is available
        version = agent.get_exiftool_version()
        assert version is not None
        assert len(version) > 0


# Manual test runner
if __name__ == "__main__":
    print("Running GeoBox Integration Tests")
    print("=" * 50)

    async def run_tests():
        """Run tests manually"""

        # Test 1: MCP Server Health
        print("\n1. Testing MCP Server Health...")
        try:
            test = TestMCPServer()
            await test.test_mcp_server_health()
            print("✓ MCP Server is healthy")
        except Exception as e:
            print(f"✗ MCP Server health check failed: {e}")

        # Test 2: MCP Server Tools
        print("\n2. Testing MCP Server Tools...")
        try:
            test = TestMCPServer()
            await test.test_mcp_server_list_tools()
            print("✓ MCP Server tools available")
        except Exception as e:
            print(f"✗ MCP Server tools check failed: {e}")

        # Test 3: Orchestrator
        print("\n3. Testing Orchestrator Initialization...")
        try:
            test = TestOrchestratorAgent()
            await test.test_orchestrator_initialization()
            print("✓ Orchestrator initialized successfully")
        except Exception as e:
            print(f"✗ Orchestrator initialization failed: {e}")

        # Test 4: Fallback Mode
        print("\n4. Testing Fallback Mode...")
        try:
            test = TestFallbackMode()
            await test.test_fallback_extraction()
            print("✓ Fallback mode works")
        except Exception as e:
            print(f"✗ Fallback mode failed: {e}")

    asyncio.run(run_tests())
    print("\n" + "=" * 50)
    print("Tests completed")
