"""
Resource-based operations for Google Docs MCP Server.

Handles uploading files and images using resource identifiers from
the mcp_mapped_resource_lib library for sharing blobs across MCP servers
via mapped Docker volumes.
"""

import os
from typing import Any

from fastmcp.exceptions import ToolError
from googleapiclient.http import MediaFileUpload
from mcp_mapped_resource_lib import BlobStorage

from google_docs_mcp.auth import get_drive_client
from google_docs_mcp.utils import log


def _get_blob_storage() -> BlobStorage:
    """
    Get or create the BlobStorage instance.

    Configuration is controlled via environment variables:
    - BLOB_STORAGE_ROOT: Required. Path to blob storage directory
    - BLOB_STORAGE_MAX_SIZE_MB: Optional. Max file size in MB (default: 100)
    - BLOB_STORAGE_TTL_HOURS: Optional. Time-to-live for blobs in hours (default: 24)

    Returns:
        BlobStorage instance configured for this MCP server

    Raises:
        ToolError: If BLOB_STORAGE_ROOT environment variable is not set
    """
    storage_root = os.environ.get("BLOB_STORAGE_ROOT")
    if not storage_root:
        raise ToolError(
            "BLOB_STORAGE_ROOT environment variable not set. "
            "Please configure the blob storage directory."
        )

    # Get configurable settings from environment variables with defaults
    max_size_mb = int(os.environ.get("BLOB_STORAGE_MAX_SIZE_MB", "100"))
    ttl_hours = int(os.environ.get("BLOB_STORAGE_TTL_HOURS", "24"))

    log(f"Initializing blob storage: root={storage_root}, max_size={max_size_mb}MB, ttl={ttl_hours}h")

    # Create storage with configurable settings
    # Allow all common image and document types
    return BlobStorage(
        storage_root=storage_root,
        max_size_mb=max_size_mb,
        default_ttl_hours=ttl_hours,
        allowed_mime_types=[
            "image/*",
            "application/pdf",
            "text/*",
            "application/vnd.openxmlformats-officedocument.*",
            "application/msword",
            "application/vnd.ms-excel",
            "application/vnd.ms-powerpoint",
        ],
        enable_deduplication=True,
    )


def upload_image_to_drive_from_resource(
    resource_id: str,
    name: str | None = None,
    parent_folder_id: str | None = None,
) -> str:
    """
    Upload an image to Google Drive from a resource identifier.

    The resource identifier references a blob in the mapped blob storage
    volume that is shared across MCP servers.

    Args:
        resource_id: Resource identifier (e.g., "blob://1733437200-a3f9d8c2b1e4f6a7.png")
        name: Name for the file in Drive (if not provided, uses resource filename)
        parent_folder_id: Optional parent folder ID (None for root)

    Returns:
        Success message with file ID and link

    Raises:
        ToolError: For permission, upload, or resource not found errors
    """
    drive = get_drive_client()
    storage = _get_blob_storage()

    log(f'Uploading image from resource "{resource_id}" to Drive')

    try:
        # Extract blob ID from resource identifier
        if resource_id.startswith("blob://"):
            blob_id = resource_id[7:]  # Remove "blob://" prefix
        else:
            blob_id = resource_id

        # Get metadata to verify it exists and is an image
        metadata = storage.get_metadata(blob_id)
        if not metadata:
            raise ToolError(f"Resource not found: {resource_id}")

        mime_type = metadata.get("mime_type", "application/octet-stream")
        if not mime_type.startswith("image/"):
            raise ToolError(
                f"Resource is not an image (MIME type: {mime_type}). "
                f"Use upload_file_to_drive_from_resource instead."
            )

        # Get the file path for upload
        file_path = storage.get_file_path(blob_id)
        if not file_path or not os.path.exists(file_path):
            raise ToolError(f"Resource file not found: {resource_id}")

        # Use resource filename if name not provided
        if not name:
            name = metadata.get("filename", blob_id)

        # Prepare metadata
        file_metadata: dict[str, Any] = {"name": name}
        if parent_folder_id:
            file_metadata["parents"] = [parent_folder_id]

        # Create media upload from file
        media = MediaFileUpload(
            file_path,
            mimetype=mime_type,
            resumable=True
        )

        # Upload file
        response = (
            drive.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id,name,webViewLink,mimeType,size"
            )
            .execute()
        )

        size_kb = int(response.get("size", 0)) / 1024

        return (
            f"Successfully uploaded image \"{response.get('name')}\" from resource {resource_id} "
            f"({size_kb:.1f} KB)\n"
            f"ID: {response.get('id')}\n"
            f"Type: {response.get('mimeType')}\n"
            f"Link: {response.get('webViewLink')}"
        )

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error uploading image from resource: {error_message}")
        if "404" in error_message:
            raise ToolError("Parent folder not found. Check the parent folder ID.")
        if "403" in error_message:
            raise ToolError("Permission denied. Make sure you have write access to Drive.")
        raise ToolError(f"Failed to upload image from resource: {error_message}")


def upload_file_to_drive_from_resource(
    resource_id: str,
    name: str | None = None,
    parent_folder_id: str | None = None,
) -> str:
    """
    Upload a file to Google Drive from a resource identifier.

    The resource identifier references a blob in the mapped blob storage
    volume that is shared across MCP servers.

    Args:
        resource_id: Resource identifier (e.g., "blob://1733437200-a3f9d8c2b1e4f6a7.pdf")
        name: Name for the file in Drive (if not provided, uses resource filename)
        parent_folder_id: Optional parent folder ID (None for root)

    Returns:
        Success message with file ID and link

    Raises:
        ToolError: For permission, upload, or resource not found errors
    """
    drive = get_drive_client()
    storage = _get_blob_storage()

    log(f'Uploading file from resource "{resource_id}" to Drive')

    try:
        # Extract blob ID from resource identifier
        if resource_id.startswith("blob://"):
            blob_id = resource_id[7:]  # Remove "blob://" prefix
        else:
            blob_id = resource_id

        # Get metadata to verify it exists
        metadata = storage.get_metadata(blob_id)
        if not metadata:
            raise ToolError(f"Resource not found: {resource_id}")

        mime_type = metadata.get("mime_type", "application/octet-stream")

        # Get the file path for upload
        file_path = storage.get_file_path(blob_id)
        if not file_path or not os.path.exists(file_path):
            raise ToolError(f"Resource file not found: {resource_id}")

        # Use resource filename if name not provided
        if not name:
            name = metadata.get("filename", blob_id)

        # Prepare metadata
        file_metadata: dict[str, Any] = {"name": name}
        if parent_folder_id:
            file_metadata["parents"] = [parent_folder_id]

        # Create media upload from file
        media = MediaFileUpload(
            file_path,
            mimetype=mime_type,
            resumable=True
        )

        # Upload file
        response = (
            drive.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id,name,webViewLink,mimeType,size"
            )
            .execute()
        )

        size_kb = int(response.get("size", 0)) / 1024

        return (
            f"Successfully uploaded file \"{response.get('name')}\" from resource {resource_id} "
            f"({size_kb:.1f} KB)\n"
            f"ID: {response.get('id')}\n"
            f"Type: {response.get('mimeType')}\n"
            f"Link: {response.get('webViewLink')}"
        )

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error uploading file from resource: {error_message}")
        if "404" in error_message:
            raise ToolError("Parent folder not found. Check the parent folder ID.")
        if "403" in error_message:
            raise ToolError("Permission denied. Make sure you have write access to Drive.")
        raise ToolError(f"Failed to upload file from resource: {error_message}")


def insert_image_from_resource(
    document_id: str,
    resource_id: str,
    index: int,
    width: float | None = None,
    height: float | None = None,
) -> str:
    """
    Insert an image into a Google Doc from a resource identifier.

    The resource must first be uploaded to Google Drive, then inserted into the document.

    Args:
        document_id: The ID of the Google Document
        resource_id: Resource identifier (e.g., "blob://1733437200-a3f9d8c2b1e4f6a7.png")
        index: The index (1-based) where the image should be inserted
        width: Width of the image in points
        height: Height of the image in points

    Returns:
        Success message with details about the inserted image

    Raises:
        ToolError: For permission, upload, or resource not found errors
    """
    from google_docs_mcp.auth import get_docs_client

    docs = get_docs_client()
    drive = get_drive_client()
    storage = _get_blob_storage()

    log(f'Inserting image from resource "{resource_id}" into document {document_id}')

    try:
        # Extract blob ID from resource identifier
        if resource_id.startswith("blob://"):
            blob_id = resource_id[7:]  # Remove "blob://" prefix
        else:
            blob_id = resource_id

        # Get metadata to verify it exists and is an image
        metadata = storage.get_metadata(blob_id)
        if not metadata:
            raise ToolError(f"Resource not found: {resource_id}")

        mime_type = metadata.get("mime_type", "application/octet-stream")
        if not mime_type.startswith("image/"):
            raise ToolError(
                f"Resource is not an image (MIME type: {mime_type}). "
                f"Only images can be inserted into documents."
            )

        # Get the file path for upload
        file_path = storage.get_file_path(blob_id)
        if not file_path or not os.path.exists(file_path):
            raise ToolError(f"Resource file not found: {resource_id}")

        # Upload image to Drive temporarily
        filename = metadata.get("filename", blob_id)
        file_metadata: dict[str, Any] = {"name": f"temp-{filename}"}

        media = MediaFileUpload(
            file_path,
            mimetype=mime_type,
            resumable=True
        )

        upload_response = (
            drive.files()
            .create(
                body=file_metadata,
                media_body=media,
                fields="id"
            )
            .execute()
        )

        file_id = upload_response.get("id")

        # Get the Drive image URL
        # Google Docs requires a specific URL format for images
        image_url = f"https://drive.google.com/uc?id={file_id}"

        # Insert image into document
        request = {
            "insertInlineImage": {
                "uri": image_url,
                "location": {"index": index}
            }
        }

        if width is not None or height is not None:
            object_size = {}
            if width is not None:
                object_size["width"] = {"magnitude": width, "unit": "PT"}
            if height is not None:
                object_size["height"] = {"magnitude": height, "unit": "PT"}
            request["insertInlineImage"]["objectSize"] = object_size

        docs.documents().batchUpdate(
            documentId=document_id,
            body={"requests": [request]}
        ).execute()

        # Note: We're leaving the temp file in Drive for now
        # It could be cleaned up later if needed

        size_info = f" ({width}x{height} points)" if width or height else ""
        return (
            f"Successfully inserted image from resource {resource_id} "
            f"at index {index}{size_info}\n"
            f"Temporary Drive file ID: {file_id}"
        )

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error inserting image from resource: {error_message}")
        if "404" in error_message:
            raise ToolError(f"Document not found (ID: {document_id}).")
        if "403" in error_message:
            raise ToolError("Permission denied. Make sure you have access to this document.")
        raise ToolError(f"Failed to insert image from resource: {error_message}")
