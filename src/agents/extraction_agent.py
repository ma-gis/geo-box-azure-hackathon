"""
Extraction Agent - Extracts GPS metadata using ExifTool
"""

import subprocess
import json
import structlog
from typing import Dict, Optional
from datetime import datetime

logger = structlog.get_logger()

class ExtractionAgent:
    """Agent responsible for extracting GPS metadata from photos/videos using ExifTool"""

    def get_exiftool_version(self) -> str:
        """Get installed ExifTool version"""
        try:
            result = subprocess.run(
                ['exiftool', '-ver'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        except Exception as e:
            logger.error("exiftool_version_check_failed", error=str(e))
            raise

    def extract_gps(self, file_path: str) -> Optional[Dict]:
        """
        Extract GPS coordinates from photo or video using ExifTool

        Args:
            file_path: Path to the media file

        Returns:
            Dict with GPS data or None if no GPS found
        """
        try:
            logger.info("extracting_gps", file_path=file_path)

            # Run ExifTool to extract GPS data
            result = subprocess.run([
                'exiftool',
                '-GPSLatitude',
                '-GPSLongitude',
                '-GPSAltitude',
                '-GPSDateTime',
                '-DateTimeOriginal',
                '-CreateDate',
                '-n',  # Numeric output for GPS coordinates
                '-json',
                file_path
            ], capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.error("exiftool_failed",
                            file_path=file_path,
                            stderr=result.stderr)
                return None

            # Parse JSON output
            data = json.loads(result.stdout)[0]

            # Extract GPS coordinates
            latitude = data.get('GPSLatitude')
            longitude = data.get('GPSLongitude')

            if latitude is None or longitude is None:
                logger.info("no_gps_in_file", file_path=file_path)
                return None

            # Build GPS data dictionary
            gps_data = {
                'latitude': float(latitude),
                'longitude': float(longitude),
                'altitude': data.get('GPSAltitude'),
                'timestamp': data.get('GPSDateTime') or data.get('DateTimeOriginal') or data.get('CreateDate'),
                'source': 'exiftool',
                'raw_data': data  # Keep raw data for debugging
            }

            logger.info("gps_extracted_successfully",
                       latitude=gps_data['latitude'],
                       longitude=gps_data['longitude'])

            return gps_data

        except subprocess.TimeoutExpired:
            logger.error("exiftool_timeout", file_path=file_path)
            return None
        except json.JSONDecodeError as e:
            logger.error("exiftool_json_parse_error",
                        file_path=file_path,
                        error=str(e))
            return None
        except Exception as e:
            logger.error("extraction_error",
                        file_path=file_path,
                        error=str(e),
                        exc_info=True)
            return None

    def generate_gpx(self, video_path: str, video_name: str) -> Optional[str]:
        """
        Generate GPX track file from video GPS metadata

        Args:
            video_path: Path to video file
            video_name: Name of video file

        Returns:
            GPX file content as string, or None if no GPS track
        """
        try:
            logger.info("generating_gpx", video_path=video_path)

            # Extract GPS track from video
            # ExifTool can extract GPS track points from video metadata
            result = subprocess.run([
                'exiftool',
                '-ee',  # Extract embedded data
                '-G3',  # Show group names
                '-a',   # Allow duplicate tags
                '-gps*',  # GPS tags only
                '-json',
                video_path
            ], capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                logger.warning("gpx_extraction_failed", video_path=video_path)
                return None

            data = json.loads(result.stdout)[0]

            # Check if we have GPS track data
            # (This depends on video format - DJI drones, GoPro, etc. store differently)
            # For now, return None - full implementation would parse the specific format

            logger.info("gpx_generation_not_implemented")
            return None

        except Exception as e:
            logger.error("gpx_generation_error",
                        video_path=video_path,
                        error=str(e))
            return None

    def get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        return datetime.utcnow().isoformat() + 'Z'
