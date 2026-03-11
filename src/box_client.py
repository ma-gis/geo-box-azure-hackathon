"""
Box Client Manager - Handles all Box API operations
Updated for Box SDK v10+ (box_sdk_gen)
"""

import os
import tempfile
import structlog
from box_sdk_gen import BoxClient, BoxJWTAuth, JWTConfig
from typing import Dict, Optional
from pathlib import Path
import io

from src.config import settings

logger = structlog.get_logger()

class BoxClientManager:
    """Manages Box API client and operations"""

    def __init__(self):
        """Initialize Box client with JWT authentication.

        Priority:
          1. BOX_CONFIG_JSON env var (full JSON string — production)
          2. BOX_CONFIG_PATH file path (local dev fallback)
        """
        try:
            if settings.BOX_CONFIG_JSON:
                # Production: load JWT config from JSON string (injected as secret)
                jwt_config = JWTConfig.from_config_json_string(settings.BOX_CONFIG_JSON)
                logger.info("box_config_loaded_from_env")
            else:
                # Local dev: load from config file
                config_path = Path(settings.BOX_CONFIG_PATH)
                if not config_path.exists():
                    logger.warning("box_config_not_found",
                                 path=settings.BOX_CONFIG_PATH,
                                 message="Box integration disabled - config file not found")
                    self.client = None
                    return
                jwt_config = JWTConfig.from_config_file(config_file_path=str(config_path))
                logger.info("box_config_loaded_from_file", path=settings.BOX_CONFIG_PATH)

            auth = BoxJWTAuth(config=jwt_config)
            self.client = BoxClient(auth=auth)

            # Test authentication
            user = self.client.users.get_user_me()
            logger.info("box_client_initialized", user=user.name)

        except Exception as e:
            logger.error("box_client_init_failed", error=str(e))
            self.client = None

    def check_connection(self) -> bool:
        """Check if Box connection is working"""
        try:
            if self.client is None:
                return False
            self.client.users.get_user_me()
            return True
        except:
            return False

    def download_file(self, file_id: str, local_path: str) -> None:
        """
        Download file from Box to local path

        Args:
            file_id: Box file ID
            local_path: Local file path to save to
        """
        try:
            logger.info("downloading_file", file_id=file_id, path=local_path)

            # Download file content
            file_content = self.client.downloads.download_file(file_id)

            # Write to local path
            with open(local_path, 'wb') as f:
                f.write(file_content.read())

            logger.info("file_downloaded", file_id=file_id)

        except Exception as e:
            logger.error("file_download_failed",
                        file_id=file_id,
                        error=str(e))
            raise

    def apply_metadata(self, file_id: str, metadata: Dict) -> None:
        """
        Apply metadata to Box file

        Args:
            file_id: Box file ID
            metadata: Dictionary of metadata key-value pairs
        """
        try:
            logger.info("applying_metadata",
                       file_id=file_id,
                       metadata_keys=list(metadata.keys()),
                       metadata_sample={k: str(v)[:100] for k, v in metadata.items()})

            # Create metadata (for now, delete and recreate if exists)
            try:
                # Try to delete existing metadata first
                try:
                    self.client.file_metadata.delete_file_metadata_by_id(
                        file_id=file_id,
                        scope=settings.BOX_ENTERPRISE_SCOPE,
                        template_key=settings.BOX_METADATA_TEMPLATE
                    )
                    logger.debug("existing_metadata_deleted", file_id=file_id)
                except Exception:
                    # No existing metadata, that's fine
                    pass

                # Create new metadata
                self.client.file_metadata.create_file_metadata_by_id(
                    file_id=file_id,
                    scope=settings.BOX_ENTERPRISE_SCOPE,
                    template_key=settings.BOX_METADATA_TEMPLATE,
                    request_body=metadata
                )
                logger.info("metadata_created", file_id=file_id)

            except Exception as create_error:
                logger.error("metadata_create_failed",
                           file_id=file_id,
                           error=str(create_error))
                raise create_error

        except Exception as e:
            logger.error("metadata_apply_failed",
                        file_id=file_id,
                        error=str(e))
            raise

    def get_parent_folder_id(self, file_id: str) -> str:
        """Get parent folder ID of a file"""
        try:
            file = self.client.files.get_file_by_id(file_id=file_id, fields=['parent'])
            return file.parent.id
        except Exception as e:
            logger.error("get_parent_folder_failed",
                        file_id=file_id,
                        error=str(e))
            raise

    def upload_file(self, content: str, file_name: str, folder_id: str) -> str:
        """
        Upload file to Box

        Args:
            content: File content as string
            file_name: Name for the uploaded file
            folder_id: Box folder ID to upload to

        Returns:
            Uploaded file ID
        """
        try:
            logger.info("uploading_file",
                       file_name=file_name,
                       folder_id=folder_id)

            # Convert content to bytes
            file_bytes = content.encode('utf-8')
            file_stream = io.BytesIO(file_bytes)

            # Upload using Box SDK v10+
            from box_sdk_gen import UploadFileAttributes, UploadFileAttributesParentField

            attributes = UploadFileAttributes(
                name=file_name,
                parent=UploadFileAttributesParentField(id=folder_id)
            )

            uploaded_files = self.client.uploads.upload_file(
                attributes=attributes,
                file=file_stream
            )

            uploaded_file = uploaded_files.entries[0]

            logger.info("file_uploaded",
                       file_id=uploaded_file.id,
                       file_name=file_name)

            return uploaded_file.id

        except Exception as e:
            logger.error("file_upload_failed",
                        file_name=file_name,
                        error=str(e))
            raise
