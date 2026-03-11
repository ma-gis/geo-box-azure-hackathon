"""
ExifTool MCP Server

This MCP server exposes ExifTool GPS extraction functionality as Model Context Protocol tools.
It wraps the ExtractionAgent functionality and makes it available for agent orchestration.
"""

import subprocess
import json
import structlog
from typing import Dict, Optional
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# Initialize structured logging
logger = structlog.get_logger()

# Create FastMCP server instance
mcp = FastMCP("exiftool-server")

# Tool implementations (reusing ExtractionAgent logic)

def _run_exiftool(args: list[str], file_path: str, timeout: int = 30) -> Optional[Dict]:
    """
    Internal helper to run ExifTool commands

    Args:
        args: ExifTool command arguments
        file_path: Path to the media file
        timeout: Command timeout in seconds

    Returns:
        Parsed JSON output or None on error
    """
    try:
        result = subprocess.run(
            ['exiftool'] + args + [file_path],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode != 0:
            logger.error("exiftool_command_failed",
                        args=args,
                        file_path=file_path,
                        stderr=result.stderr)
            return None

        # Parse JSON output if requested
        if '-json' in args:
            data = json.loads(result.stdout)
            return data[0] if data else None
        else:
            return {'output': result.stdout.strip()}

    except subprocess.TimeoutExpired:
        logger.error("exiftool_timeout", file_path=file_path, timeout=timeout)
        return None
    except json.JSONDecodeError as e:
        logger.error("exiftool_json_parse_error", error=str(e))
        return None
    except Exception as e:
        logger.error("exiftool_error", error=str(e), exc_info=True)
        return None


@mcp.tool()
def get_exiftool_version() -> str:
    """
    Get the installed ExifTool version

    Returns:
        ExifTool version string
    """
    try:
        result = subprocess.run(
            ['exiftool', '-ver'],
            capture_output=True,
            text=True,
            timeout=5
        )
        version = result.stdout.strip()
        logger.info("exiftool_version_retrieved", version=version)
        return version
    except Exception as e:
        logger.error("exiftool_version_check_failed", error=str(e))
        return f"Error: {str(e)}"


@mcp.tool()
def extract_gps(file_path: str) -> Dict:
    """
    Extract GPS coordinates from a photo or video file using ExifTool

    This tool reads EXIF/XMP metadata from media files and extracts:
    - Latitude and longitude coordinates
    - Altitude (if available)
    - Timestamp (GPS time or file creation time)

    Args:
        file_path: Absolute path to the photo or video file

    Returns:
        Dictionary containing:
        - latitude: GPS latitude in decimal degrees
        - longitude: GPS longitude in decimal degrees
        - altitude: GPS altitude in meters (optional)
        - timestamp: ISO timestamp
        - source: Always "exiftool"
        - error: Error message if extraction failed
    """
    logger.info("mcp_extract_gps_called", file_path=file_path)

    # Run ExifTool to extract GPS data
    data = _run_exiftool([
        '-GPSLatitude',
        '-GPSLongitude',
        '-GPSAltitude',
        '-GPSDateTime',
        '-DateTimeOriginal',
        '-CreateDate',
        '-n',  # Numeric output for GPS coordinates
        '-json'
    ], file_path)

    if not data:
        return {
            'error': 'Failed to extract metadata from file',
            'file_path': file_path
        }

    # Extract GPS coordinates
    latitude = data.get('GPSLatitude')
    longitude = data.get('GPSLongitude')

    if latitude is None or longitude is None:
        logger.info("no_gps_in_file", file_path=file_path)
        return {
            'error': 'No GPS coordinates found in file',
            'file_path': file_path,
            'has_metadata': True
        }

    # Build GPS data dictionary
    gps_data = {
        'latitude': float(latitude),
        'longitude': float(longitude),
        'altitude': data.get('GPSAltitude'),
        'timestamp': data.get('GPSDateTime') or data.get('DateTimeOriginal') or data.get('CreateDate'),
        'source': 'exiftool',
        'file_path': file_path
    }

    logger.info("gps_extracted_successfully",
               latitude=gps_data['latitude'],
               longitude=gps_data['longitude'])

    return gps_data


@mcp.tool()
def extract_all_metadata(file_path: str) -> Dict:
    """
    Extract all EXIF/XMP metadata from a media file

    This tool extracts comprehensive metadata including:
    - Camera settings (aperture, ISO, shutter speed)
    - GPS location data
    - Timestamps
    - Camera make and model
    - Image dimensions

    Args:
        file_path: Absolute path to the media file

    Returns:
        Dictionary containing all extracted metadata fields
    """
    logger.info("mcp_extract_all_metadata_called", file_path=file_path)

    data = _run_exiftool(['-json'], file_path)

    if not data:
        return {
            'error': 'Failed to extract metadata from file',
            'file_path': file_path
        }

    return data


@mcp.tool()
def generate_gpx_track(video_path: str, track_name: Optional[str] = None) -> Dict:
    """
    Generate a GPX track file from video GPS metadata

    Extracts GPS track points from video files (e.g., drone videos, action cameras)
    and formats them as a GPX XML track for use in mapping applications.

    Args:
        video_path: Absolute path to the video file
        track_name: Optional name for the GPX track (defaults to filename)

    Returns:
        Dictionary containing:
        - gpx_content: GPX XML string
        - track_name: Name of the track
        - point_count: Number of GPS points
        - error: Error message if generation failed
    """
    logger.info("mcp_generate_gpx_called", video_path=video_path)

    # Extract GPS track from video
    data = _run_exiftool([
        '-ee',  # Extract embedded data
        '-G3',  # Show group names
        '-a',   # Allow duplicate tags
        '-gps*',  # GPS tags only
        '-json'
    ], video_path, timeout=60)

    if not data:
        return {
            'error': 'Failed to extract GPS track from video',
            'video_path': video_path
        }

    # TODO: Full GPX generation implementation
    # This requires parsing video-specific GPS formats (DJI, GoPro, etc.)
    # For now, return the raw GPS data

    logger.info("gpx_generation_in_progress")
    return {
        'error': 'GPX generation not yet fully implemented',
        'video_path': video_path,
        'raw_gps_data': data,
        'note': 'Use extract_gps for single-point GPS extraction'
    }


# Server configuration and startup
if __name__ == "__main__":
    # Run the MCP server
    # This will listen for MCP protocol messages on stdin/stdout
    mcp.run()
