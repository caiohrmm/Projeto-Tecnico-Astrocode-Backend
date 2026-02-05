"""Cloudinary service for image upload and management."""

import logging
import uuid

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile, status

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class CloudinaryService:
    """Service for interacting with Cloudinary API."""

    # Allowed image content types
    ALLOWED_CONTENT_TYPES = {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }

    # Maximum file size: 10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes

    def __init__(self) -> None:
        """Initialize Cloudinary service with credentials from settings."""
        settings = get_settings()

        cloud_name = settings.cloudinary_cloud_name or ""
        api_key = settings.cloudinary_api_key or ""
        api_secret = settings.cloudinary_api_secret or ""

        if not all([cloud_name, api_key, api_secret]):
            logger.warning(
                "Cloudinary credentials not fully configured. "
                "Image upload functionality will be limited."
            )
            self.is_configured = False
        else:
            # Clean credentials (remove quotes, whitespace, etc.)
            cloud_name = cloud_name.strip().strip('"').strip("'")
            api_key = api_key.strip().strip('"').strip("'").lstrip("-")
            api_secret = api_secret.strip().strip('"').strip("'").lstrip("-")

            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
            )
            self.is_configured = True

    def is_service_configured(self) -> bool:
        """Check if Cloudinary is properly configured."""
        return self.is_configured

    def validate_image_file(self, file: UploadFile) -> None:
        """
        Validate image file before upload.

        Args:
            file: UploadFile instance to validate

        Raises:
            HTTPException: If file is invalid (wrong type or too large)
        """
        # Check content type
        if file.content_type not in self.ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid file type. Allowed types: "
                    f"{', '.join(self.ALLOWED_CONTENT_TYPES)}"
                ),
            )

        # Check file size (read first chunk to check)
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        if file_size > self.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {self.MAX_FILE_SIZE / (1024 * 1024):.1f}MB",
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty",
            )

    def upload_property_main_image(
        self,
        file: UploadFile,
        property_id: uuid.UUID,
    ) -> str:
        """
        Upload property main image to Cloudinary.

        The image is stored in a folder structure: properties/{property_id}/
        and optimized for web delivery.

        Args:
            file: UploadFile instance containing the image
            property_id: UUID of the property

        Returns:
            Secure URL of the uploaded image

        Raises:
            HTTPException: If upload fails or service is not configured
        """
        if not self.is_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cloudinary service is not configured. Please contact administrator.",
            )

        # Validate file
        self.validate_image_file(file)

        try:
            # Read file content
            file_content = file.file.read()
            file.file.seek(0)  # Reset for potential reuse

            # Upload to Cloudinary
            upload_result = cloudinary.uploader.upload(
                file_content,
                folder=f"properties/{property_id}",
                public_id="main_image",
                resource_type="image",
                overwrite=True,  # Replace existing main_image if it exists
                transformation=[
                    {"width": 1200, "height": 800, "crop": "limit"},  # Max dimensions
                    {"quality": "auto"},  # Auto quality optimization
                    {"format": "auto"},  # Auto format (webp when supported)
                ],
            )

            # Extract secure URL
            secure_url = upload_result.get("secure_url")
            if not secure_url:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to get image URL from Cloudinary",
                )

            logger.info(
                f"Successfully uploaded main image for property {property_id}. "
                f"URL: {secure_url}"
            )

            return secure_url

        except Exception as cloudinary_error:
            # Cloudinary SDK may raise various exceptions
            error_message = str(cloudinary_error)
            logger.error(f"Cloudinary upload error: {error_message}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload image to Cloudinary: {error_message}",
            )
        except Exception as e:
            logger.error(f"Unexpected error during image upload: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error during image upload: {str(e)}",
            )


# Singleton instance
_cloudinary_service: CloudinaryService | None = None


def get_cloudinary_service() -> CloudinaryService:
    """
    Get or create Cloudinary service singleton instance.

    Returns:
        CloudinaryService instance
    """
    global _cloudinary_service
    if _cloudinary_service is None:
        _cloudinary_service = CloudinaryService()
    return _cloudinary_service

