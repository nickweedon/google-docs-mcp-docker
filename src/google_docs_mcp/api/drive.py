"""
Google Drive operations for Google Docs MCP Server.

Handles listing, searching, and managing files/folders in Drive.
"""

import base64
import sys
from datetime import datetime, timedelta
from typing import Any

from googleapiclient.http import MediaInMemoryUpload

from google_docs_mcp.auth import get_drive_client
from google_docs_mcp.types import DocumentInfo, UserError


def _log(message: str) -> None:
    """Log a message to stderr (MCP protocol compatibility)."""
    print(message, file=sys.stderr)


def list_google_docs(
    max_results: int = 20,
    query: str | None = None,
    order_by: str = "modifiedTime",
) -> str:
    """
    List Google Documents from Google Drive.

    Args:
        max_results: Maximum number of documents to return (1-100)
        query: Optional search query to filter by name or content
        order_by: Sort order ('name', 'modifiedTime', 'createdTime')

    Returns:
        Formatted string with document information

    Raises:
        UserError: For permission errors
    """
    drive = get_drive_client()
    _log(f"Listing Google Docs. Query: {query or 'none'}, Max: {max_results}, Order: {order_by}")

    try:
        query_string = "mimeType='application/vnd.google-apps.document' and trashed=false"
        if query:
            query_string += f" and (name contains '{query}' or fullText contains '{query}')"

        response = (
            drive.files()
            .list(
                q=query_string,
                pageSize=max_results,
                orderBy=order_by,
                fields="files(id,name,modifiedTime,createdTime,size,webViewLink,owners(displayName,emailAddress))",
            )
            .execute()
        )

        files = response.get("files", [])

        if not files:
            return "No Google Docs found matching your criteria."

        result = f"Found {len(files)} Google Document(s):\n\n"

        for index, file in enumerate(files):
            modified = file.get("modifiedTime", "Unknown")[:10] if file.get("modifiedTime") else "Unknown"
            owner = file.get("owners", [{}])[0].get("displayName", "Unknown")

            result += (
                f"{index + 1}. **{file.get('name')}**\n"
                f"   ID: {file.get('id')}\n"
                f"   Modified: {modified}\n"
                f"   Owner: {owner}\n"
                f"   Link: {file.get('webViewLink')}\n\n"
            )

        return result

    except Exception as e:
        error_message = str(e)
        _log(f"Error listing Google Docs: {error_message}")
        if "403" in error_message:
            raise UserError(
                "Permission denied. Make sure you have granted Google Drive access."
            )
        raise UserError(f"Failed to list documents: {error_message}")


def search_google_docs(
    search_query: str,
    search_in: str = "both",
    max_results: int = 10,
    modified_after: str | None = None,
) -> str:
    """
    Search for Google Documents.

    Args:
        search_query: Search term to find
        search_in: Where to search ('name', 'content', 'both')
        max_results: Maximum number of results (1-50)
        modified_after: Only return docs modified after this date (ISO 8601)

    Returns:
        Formatted string with search results

    Raises:
        UserError: For permission errors
    """
    drive = get_drive_client()
    _log(f'Searching Google Docs for: "{search_query}" in {search_in}')

    try:
        query_string = "mimeType='application/vnd.google-apps.document' and trashed=false"

        if search_in == "name":
            query_string += f" and name contains '{search_query}'"
        elif search_in == "content":
            query_string += f" and fullText contains '{search_query}'"
        else:  # both
            query_string += f" and (name contains '{search_query}' or fullText contains '{search_query}')"

        if modified_after:
            query_string += f" and modifiedTime > '{modified_after}'"

        response = (
            drive.files()
            .list(
                q=query_string,
                pageSize=max_results,
                orderBy="modifiedTime desc",
                fields="files(id,name,modifiedTime,createdTime,webViewLink,owners(displayName),parents)",
            )
            .execute()
        )

        files = response.get("files", [])

        if not files:
            return f'No Google Docs found containing "{search_query}".'

        result = f'Found {len(files)} document(s) matching "{search_query}":\n\n'

        for index, file in enumerate(files):
            modified = file.get("modifiedTime", "Unknown")[:10] if file.get("modifiedTime") else "Unknown"
            owner = file.get("owners", [{}])[0].get("displayName", "Unknown")

            result += (
                f"{index + 1}. **{file.get('name')}**\n"
                f"   ID: {file.get('id')}\n"
                f"   Modified: {modified}\n"
                f"   Owner: {owner}\n"
                f"   Link: {file.get('webViewLink')}\n\n"
            )

        return result

    except Exception as e:
        error_message = str(e)
        _log(f"Error searching Google Docs: {error_message}")
        if "403" in error_message:
            raise UserError(
                "Permission denied. Make sure you have granted Google Drive access."
            )
        raise UserError(f"Failed to search documents: {error_message}")


def get_recent_google_docs(max_results: int = 10, days_back: int = 30) -> str:
    """
    Get the most recently modified Google Documents.

    Args:
        max_results: Maximum number of documents to return (1-50)
        days_back: Only show documents modified within this many days (1-365)

    Returns:
        Formatted string with recent documents

    Raises:
        UserError: For permission errors
    """
    drive = get_drive_client()
    _log(f"Getting recent Google Docs: {max_results} results, {days_back} days back")

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        cutoff_str = cutoff_date.isoformat() + "Z"

        query_string = (
            f"mimeType='application/vnd.google-apps.document' "
            f"and trashed=false and modifiedTime > '{cutoff_str}'"
        )

        response = (
            drive.files()
            .list(
                q=query_string,
                pageSize=max_results,
                orderBy="modifiedTime desc",
                fields="files(id,name,modifiedTime,createdTime,webViewLink,owners(displayName),lastModifyingUser(displayName))",
            )
            .execute()
        )

        files = response.get("files", [])

        if not files:
            return f"No Google Docs found that were modified in the last {days_back} days."

        result = f"{len(files)} recently modified Google Document(s) (last {days_back} days):\n\n"

        for index, file in enumerate(files):
            modified = file.get("modifiedTime", "")
            if modified:
                modified = modified.replace("T", " ").replace("Z", "")[:19]

            last_modifier = file.get("lastModifyingUser", {}).get("displayName", "Unknown")
            owner = file.get("owners", [{}])[0].get("displayName", "Unknown")

            result += (
                f"{index + 1}. **{file.get('name')}**\n"
                f"   ID: {file.get('id')}\n"
                f"   Last Modified: {modified} by {last_modifier}\n"
                f"   Owner: {owner}\n"
                f"   Link: {file.get('webViewLink')}\n\n"
            )

        return result

    except Exception as e:
        error_message = str(e)
        _log(f"Error getting recent Google Docs: {error_message}")
        if "403" in error_message:
            raise UserError(
                "Permission denied. Make sure you have granted Google Drive access."
            )
        raise UserError(f"Failed to get recent documents: {error_message}")


def get_document_info(document_id: str) -> str:
    """
    Get detailed information about a specific Google Document.

    Args:
        document_id: The ID of the Google Document

    Returns:
        Formatted string with document information

    Raises:
        UserError: For permission/not found errors
    """
    drive = get_drive_client()
    _log(f"Getting info for document: {document_id}")

    try:
        response = (
            drive.files()
            .get(
                fileId=document_id,
                fields="id,name,description,mimeType,size,createdTime,modifiedTime,webViewLink,owners(displayName,emailAddress),lastModifyingUser(displayName,emailAddress),shared,parents,version",
            )
            .execute()
        )

        if not response:
            raise UserError(f"Document with ID {document_id} not found.")

        created = response.get("createdTime", "")
        if created:
            created = created.replace("T", " ").replace("Z", "")[:19]

        modified = response.get("modifiedTime", "")
        if modified:
            modified = modified.replace("T", " ").replace("Z", "")[:19]

        owner = response.get("owners", [{}])[0]
        last_modifier = response.get("lastModifyingUser", {})

        result = "**Document Information:**\n\n"
        result += f"**Name:** {response.get('name')}\n"
        result += f"**ID:** {response.get('id')}\n"
        result += "**Type:** Google Document\n"
        result += f"**Created:** {created}\n"
        result += f"**Last Modified:** {modified}\n"

        if owner:
            result += f"**Owner:** {owner.get('displayName', 'Unknown')} ({owner.get('emailAddress', '')})\n"

        if last_modifier:
            result += f"**Last Modified By:** {last_modifier.get('displayName', 'Unknown')} ({last_modifier.get('emailAddress', '')})\n"

        result += f"**Shared:** {'Yes' if response.get('shared') else 'No'}\n"
        result += f"**View Link:** {response.get('webViewLink')}\n"

        if response.get("description"):
            result += f"**Description:** {response.get('description')}\n"

        return result

    except UserError:
        raise
    except Exception as e:
        error_message = str(e)
        _log(f"Error getting document info: {error_message}")
        if "404" in error_message:
            raise UserError(f"Document not found (ID: {document_id}).")
        if "403" in error_message:
            raise UserError("Permission denied. Make sure you have access to this document.")
        raise UserError(f"Failed to get document info: {error_message}")


def create_folder(name: str, parent_folder_id: str | None = None) -> str:
    """
    Create a new folder in Google Drive.

    Args:
        name: Name for the new folder
        parent_folder_id: Parent folder ID (None for root)

    Returns:
        Success message with folder ID and link

    Raises:
        UserError: For permission errors
    """
    drive = get_drive_client()
    _log(
        f'Creating folder "{name}" '
        f'{"in parent " + parent_folder_id if parent_folder_id else "in root"}'
    )

    try:
        metadata: dict[str, Any] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }

        if parent_folder_id:
            metadata["parents"] = [parent_folder_id]

        response = (
            drive.files()
            .create(requestBody=metadata, fields="id,name,parents,webViewLink")
            .execute()
        )

        return (
            f"Successfully created folder \"{response.get('name')}\" "
            f"(ID: {response.get('id')})\n"
            f"Link: {response.get('webViewLink')}"
        )

    except Exception as e:
        error_message = str(e)
        _log(f"Error creating folder: {error_message}")
        if "404" in error_message:
            raise UserError("Parent folder not found. Check the parent folder ID.")
        if "403" in error_message:
            raise UserError("Permission denied. Make sure you have write access.")
        raise UserError(f"Failed to create folder: {error_message}")


def list_folder_contents(
    folder_id: str,
    include_subfolders: bool = True,
    include_files: bool = True,
    max_results: int = 50,
) -> str:
    """
    List the contents of a specific folder.

    Args:
        folder_id: ID of the folder ('root' for Drive root)
        include_subfolders: Whether to include subfolders
        include_files: Whether to include files
        max_results: Maximum number of items to return

    Returns:
        Formatted string with folder contents

    Raises:
        UserError: For permission/not found errors
    """
    drive = get_drive_client()
    _log(f"Listing contents of folder: {folder_id}")

    try:
        query_string = f"'{folder_id}' in parents and trashed=false"

        if not include_subfolders and not include_files:
            return "No items to list when both subfolders and files are excluded."

        if not include_subfolders:
            query_string += " and mimeType != 'application/vnd.google-apps.folder'"
        if not include_files:
            query_string += " and mimeType = 'application/vnd.google-apps.folder'"

        response = (
            drive.files()
            .list(
                q=query_string,
                pageSize=max_results,
                orderBy="folder,name",
                fields="files(id,name,mimeType,modifiedTime,webViewLink)",
            )
            .execute()
        )

        files = response.get("files", [])

        if not files:
            return "Folder is empty or no matching items found."

        result = f"Contents of folder ({len(files)} items):\n\n"

        folders = []
        documents = []

        for file in files:
            if file.get("mimeType") == "application/vnd.google-apps.folder":
                folders.append(file)
            else:
                documents.append(file)

        if folders:
            result += "**Folders:**\n"
            for folder in folders:
                result += f"  📁 {folder.get('name')} (ID: {folder.get('id')})\n"
            result += "\n"

        if documents:
            result += "**Files:**\n"
            for doc in documents:
                modified = doc.get("modifiedTime", "")[:10] if doc.get("modifiedTime") else ""
                result += f"  📄 {doc.get('name')} (Modified: {modified})\n"
                result += f"     ID: {doc.get('id')}\n"

        return result

    except Exception as e:
        error_message = str(e)
        _log(f"Error listing folder contents: {error_message}")
        if "404" in error_message:
            raise UserError(f"Folder not found (ID: {folder_id}).")
        if "403" in error_message:
            raise UserError("Permission denied. Make sure you have access to this folder.")
        raise UserError(f"Failed to list folder contents: {error_message}")


def upload_image_to_drive(
    image_data: str,
    name: str,
    mime_type: str,
    parent_folder_id: str | None = None,
) -> str:
    """
    Upload an image to Google Drive from base64-encoded data.

    Args:
        image_data: Base64-encoded image data
        name: Name for the file in Drive
        mime_type: MIME type of the image (e.g., 'image/png', 'image/jpeg')
        parent_folder_id: Optional parent folder ID (None for root)

    Returns:
        Success message with file ID and link

    Raises:
        UserError: For permission or upload errors
    """
    drive = get_drive_client()
    _log(f'Uploading image "{name}" (type: {mime_type}) to Drive')

    try:
        # Decode base64 data
        binary_data = base64.b64decode(image_data)

        # Prepare metadata
        metadata: dict[str, Any] = {"name": name}
        if parent_folder_id:
            metadata["parents"] = [parent_folder_id]

        # Create media upload
        media = MediaInMemoryUpload(
            binary_data,
            mimetype=mime_type,
            resumable=True
        )

        # Upload file
        response = (
            drive.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id,name,webViewLink,mimeType,size"
            )
            .execute()
        )

        size_kb = int(response.get("size", 0)) / 1024

        return (
            f"Successfully uploaded image \"{response.get('name')}\" "
            f"({size_kb:.1f} KB)\n"
            f"ID: {response.get('id')}\n"
            f"Type: {response.get('mimeType')}\n"
            f"Link: {response.get('webViewLink')}"
        )

    except Exception as e:
        error_message = str(e)
        _log(f"Error uploading image: {error_message}")
        if "404" in error_message:
            raise UserError("Parent folder not found. Check the parent folder ID.")
        if "403" in error_message:
            raise UserError("Permission denied. Make sure you have write access to Drive.")
        raise UserError(f"Failed to upload image: {error_message}")


def upload_file_to_drive(
    file_data: str,
    name: str,
    mime_type: str,
    parent_folder_id: str | None = None,
) -> str:
    """
    Upload a file to Google Drive from base64-encoded data.

    Args:
        file_data: Base64-encoded file data
        name: Name for the file in Drive
        mime_type: MIME type of the file
        parent_folder_id: Optional parent folder ID (None for root)

    Returns:
        Success message with file ID and link

    Raises:
        UserError: For permission or upload errors
    """
    drive = get_drive_client()
    _log(f'Uploading file "{name}" (type: {mime_type}) to Drive')

    try:
        # Decode base64 data
        binary_data = base64.b64decode(file_data)

        # Prepare metadata
        metadata: dict[str, Any] = {"name": name}
        if parent_folder_id:
            metadata["parents"] = [parent_folder_id]

        # Create media upload
        media = MediaInMemoryUpload(
            binary_data,
            mimetype=mime_type,
            resumable=True
        )

        # Upload file
        response = (
            drive.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id,name,webViewLink,mimeType,size"
            )
            .execute()
        )

        size_kb = int(response.get("size", 0)) / 1024

        return (
            f"Successfully uploaded file \"{response.get('name')}\" "
            f"({size_kb:.1f} KB)\n"
            f"ID: {response.get('id')}\n"
            f"Type: {response.get('mimeType')}\n"
            f"Link: {response.get('webViewLink')}"
        )

    except Exception as e:
        error_message = str(e)
        _log(f"Error uploading file: {error_message}")
        if "404" in error_message:
            raise UserError("Parent folder not found. Check the parent folder ID.")
        if "403" in error_message:
            raise UserError("Permission denied. Make sure you have write access to Drive.")
        raise UserError(f"Failed to upload file: {error_message}")
