"""
Unit Tests for ExifTool GPS Extraction

Tests the GPS extraction logic in the ExifTool MCP server without
requiring a running MCP server or real media files. Subprocess calls
are mocked to simulate ExifTool output.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_exiftool_json(fields: dict) -> str:
    """Return JSON output that mimics `exiftool -json`."""
    return json.dumps([fields])


def _mock_run(stdout: str = "", returncode: int = 0, stderr: str = ""):
    mock = MagicMock()
    mock.stdout = stdout
    mock.returncode = returncode
    mock.stderr = stderr
    return mock


# ---------------------------------------------------------------------------
# Tests for _run_exiftool helper
# ---------------------------------------------------------------------------

class TestRunExiftool:
    """Unit tests for the internal _run_exiftool helper."""

    def test_returns_parsed_json_on_success(self):
        from src.mcp_servers.exiftool_server.server import _run_exiftool

        payload = {"GPSLatitude": 37.7749, "GPSLongitude": -122.4194}
        with patch("subprocess.run", return_value=_mock_run(_make_exiftool_json(payload))):
            result = _run_exiftool(["-json"], "/fake/video.mp4")

        assert result == payload

    def test_returns_none_on_nonzero_exit(self):
        from src.mcp_servers.exiftool_server.server import _run_exiftool

        with patch("subprocess.run", return_value=_mock_run(returncode=1, stderr="File not found")):
            result = _run_exiftool(["-json"], "/nonexistent/video.mp4")

        assert result is None

    def test_returns_none_on_empty_json_array(self):
        from src.mcp_servers.exiftool_server.server import _run_exiftool

        with patch("subprocess.run", return_value=_mock_run("[]")):
            result = _run_exiftool(["-json"], "/fake/video.mp4")

        assert result is None

    def test_returns_none_on_timeout(self):
        import subprocess
        from src.mcp_servers.exiftool_server.server import _run_exiftool

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("exiftool", 30)):
            result = _run_exiftool(["-json"], "/fake/video.mp4")

        assert result is None

    def test_returns_raw_output_when_no_json_flag(self):
        from src.mcp_servers.exiftool_server.server import _run_exiftool

        with patch("subprocess.run", return_value=_mock_run("12.00\n")):
            result = _run_exiftool(["-ver"], "/fake/video.mp4")

        assert result == {"output": "12.00"}


# ---------------------------------------------------------------------------
# Tests for extract_gps MCP tool
# ---------------------------------------------------------------------------

class TestExtractGps:
    """Unit tests for the extract_gps MCP tool."""

    def test_extracts_gps_from_video_with_coordinates(self):
        from src.mcp_servers.exiftool_server.server import extract_gps

        payload = {
            "GPSLatitude": 48.8566,
            "GPSLongitude": 2.3522,
            "GPSAltitude": 35.0,
            "GPSDateTime": "2024:06:15 10:30:00Z",
        }

        with patch("subprocess.run", return_value=_mock_run(_make_exiftool_json(payload))):
            result = extract_gps("/fake/video.mp4")

        assert result["latitude"] == pytest.approx(48.8566)
        assert result["longitude"] == pytest.approx(2.3522)
        assert result["altitude"] == pytest.approx(35.0)
        assert result["source"] == "exiftool"
        assert "error" not in result

    def test_returns_error_when_no_gps_in_video(self):
        from src.mcp_servers.exiftool_server.server import extract_gps

        # Video with metadata but no GPS fields
        payload = {"Make": "GoPro", "Model": "HERO12 Black"}

        with patch("subprocess.run", return_value=_mock_run(_make_exiftool_json(payload))):
            result = extract_gps("/fake/no_gps_video.mp4")

        assert "error" in result
        assert result.get("has_metadata") is True

    def test_returns_error_when_exiftool_fails(self):
        from src.mcp_servers.exiftool_server.server import extract_gps

        with patch("subprocess.run", return_value=_mock_run(returncode=1, stderr="No such file")):
            result = extract_gps("/nonexistent/video.mp4")

        assert "error" in result
        assert "has_metadata" not in result

    def test_uses_datetimeoriginal_as_fallback_timestamp(self):
        from src.mcp_servers.exiftool_server.server import extract_gps

        payload = {
            "GPSLatitude": 51.5074,
            "GPSLongitude": -0.1278,
            "DateTimeOriginal": "2024:06:15 08:00:00",
        }

        with patch("subprocess.run", return_value=_mock_run(_make_exiftool_json(payload))):
            result = extract_gps("/fake/video.mp4")

        assert result["timestamp"] == "2024:06:15 08:00:00"


# ---------------------------------------------------------------------------
# Tests for GPS track detection in video files
# ---------------------------------------------------------------------------

class TestVideoGpsTrack:
    """Tests that verify whether a video file contains an embedded GPS track."""

    def test_video_has_gps_track(self):
        """Simulates a drone video with a GPS track embedded in metadata."""
        from src.mcp_servers.exiftool_server.server import extract_gps

        # DJI drone videos typically include GPSLatitude/Longitude in their metadata
        payload = {
            "GPSLatitude": 34.0522,
            "GPSLongitude": -118.2437,
            "GPSAltitude": 120.5,
            "GPSDateTime": "2024:06:15 14:22:00Z",
            "Make": "DJI",
            "Model": "Mini 3 Pro",
        }

        with patch("subprocess.run", return_value=_mock_run(_make_exiftool_json(payload))):
            result = extract_gps("/fake/drone_video.mp4")

        has_gps_track = "error" not in result
        assert has_gps_track, "Video should have GPS track"
        assert result["latitude"] is not None
        assert result["longitude"] is not None

    def test_video_has_no_gps_track(self):
        """Simulates a regular video without GPS data."""
        from src.mcp_servers.exiftool_server.server import extract_gps

        payload = {
            "Make": "Apple",
            "Model": "iPhone 15",
            "CreateDate": "2024:06:15 09:00:00",
        }

        with patch("subprocess.run", return_value=_mock_run(_make_exiftool_json(payload))):
            result = extract_gps("/fake/regular_video.mp4")

        has_gps_track = "error" not in result
        assert not has_gps_track, "Video should NOT have GPS track"

    def test_real_video_file(self, request):
        """
        Tests GPS track detection against a real video file.

        Usage:
            pytest tests/test_exiftool_gps.py::TestVideoGpsTrack::test_real_video_file \
                --video /path/to/your/video.mp4
        """
        video_path = request.config.getoption("--video", default=None)
        if not video_path:
            pytest.skip("Pass --video /path/to/video.mp4 to run this test")

        path = Path(video_path)
        if not path.exists():
            pytest.fail(f"Video file not found: {video_path}")

        # Use real exiftool (no mock) — requires exiftool to be installed
        from src.mcp_servers.exiftool_server.server import extract_gps

        result = extract_gps(str(path.resolve()))

        has_gps = "error" not in result
        print(f"\nFile : {path.name}")
        print(f"Has GPS track: {has_gps}")
        if has_gps:
            print(f"  Latitude : {result['latitude']}")
            print(f"  Longitude: {result['longitude']}")
            print(f"  Altitude : {result.get('altitude')}")
            print(f"  Timestamp: {result.get('timestamp')}")
        else:
            print(f"  Reason: {result.get('error')}")

        # The test passes either way — it's informational
        assert isinstance(has_gps, bool)


# ---------------------------------------------------------------------------
# pytest CLI option for real-file testing
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--video",
        action="store",
        default=None,
        help="Path to a video file for real exiftool GPS detection test",
    )
