"""
Google Drive operations for Google Docs MCP Server.

Handles listing, searching, and managing files/folders in Drive.
"""

import base64
from datetime import datetime, timedelta
from typing import Any

from fastmcp.exceptions import ToolError
from googleapiclient.http import MediaInMemoryUpload
from mcp.types import ImageContent

from google_docs_mcp.auth import get_drive_client
from google_docs_mcp.utils import log


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
    log(f"Listing Google Docs. Query: {query or 'none'}, Max: {max_results}, Order: {order_by}")

    try:
        query_string = "mimeType='application/vnd.google-apps.document' and trashed=false"
        uses_fulltext = False

        if query:
            query_string += f" and (name contains '{query}' or fullText contains '{query}')"
            uses_fulltext = True

        # Build list parameters - orderBy is not allowed with fullText queries
        list_params = {
            "q": query_string,
            "pageSize": max_results,
            "fields": "files(id,name,modifiedTime,createdTime,size,webViewLink,owners(displayName,emailAddress))",
        }

        if not uses_fulltext:
            list_params["orderBy"] = order_by

        response = drive.files().list(**list_params).execute()

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
        log(f"Error listing Google Docs: {error_message}")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Make sure you have granted Google Drive access."
            )
        raise ToolError(f"Failed to list documents: {error_message}")


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
    log(f'Searching Google Docs for: "{search_query}" in {search_in}')

    try:
        query_string = "mimeType='application/vnd.google-apps.document' and trashed=false"
        uses_fulltext = False

        if search_in == "name":
            query_string += f" and name contains '{search_query}'"
        elif search_in == "content":
            query_string += f" and fullText contains '{search_query}'"
            uses_fulltext = True
        else:  # both
            query_string += f" and (name contains '{search_query}' or fullText contains '{search_query}')"
            uses_fulltext = True

        if modified_after:
            query_string += f" and modifiedTime > '{modified_after}'"

        # Build list parameters - orderBy is not allowed with fullText queries
        list_params = {
            "q": query_string,
            "pageSize": max_results,
            "fields": "files(id,name,modifiedTime,createdTime,webViewLink,owners(displayName),parents)",
        }

        if not uses_fulltext:
            list_params["orderBy"] = "modifiedTime desc"

        response = drive.files().list(**list_params).execute()

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
        log(f"Error searching Google Docs: {error_message}")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Make sure you have granted Google Drive access."
            )
        raise ToolError(f"Failed to search documents: {error_message}")


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
    log(f"Getting recent Google Docs: {max_results} results, {days_back} days back")

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
        log(f"Error getting recent Google Docs: {error_message}")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Make sure you have granted Google Drive access."
            )
        raise ToolError(f"Failed to get recent documents: {error_message}")


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
    log(f"Getting info for document: {document_id}")

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
            raise ToolError(f"Document with ID {document_id} not found.")

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

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error getting document info: {error_message}")
        if "404" in error_message:
            raise ToolError(f"Document not found (ID: {document_id}).")
        if "403" in error_message:
            raise ToolError("Permission denied. Make sure you have access to this document.")
        raise ToolError(f"Failed to get document info: {error_message}")


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
    log(
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
        log(f"Error creating folder: {error_message}")
        if "404" in error_message:
            raise ToolError("Parent folder not found. Check the parent folder ID.")
        if "403" in error_message:
            raise ToolError("Permission denied. Make sure you have write access.")
        raise ToolError(f"Failed to create folder: {error_message}")


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
    log(f"Listing contents of folder: {folder_id}")

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
        log(f"Error listing folder contents: {error_message}")
        if "404" in error_message:
            raise ToolError(f"Folder not found (ID: {folder_id}).")
        if "403" in error_message:
            raise ToolError("Permission denied. Make sure you have access to this folder.")
        raise ToolError(f"Failed to list folder contents: {error_message}")


def upload_image_to_drive(
    image: ImageContent,
    name: str,
    parent_folder_id: str | None = None,
) -> str:
    """
    Upload an image to Google Drive from ImageContent.

    Args:
        image: MCP ImageContent object with base64-encoded data and MIME type
        name: Name for the file in Drive
        parent_folder_id: Optional parent folder ID (None for root)

    Returns:
        Success message with file ID and link

    Raises:
        UserError: For permission or upload errors
    """
    drive = get_drive_client()
    mime_type = image.mimeType
    log(f'Uploading image "{name}" (type: {mime_type}) to Drive')

    try:
        # Decode base64 data from ImageContent
        binary_data = base64.b64decode(image.data)

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
        log(f"Error uploading image: {error_message}")
        if "404" in error_message:
            raise ToolError("Parent folder not found. Check the parent folder ID.")
        if "403" in error_message:
            raise ToolError("Permission denied. Make sure you have write access to Drive.")
        raise ToolError(f"Failed to upload image: {error_message}")


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
    log(f'Uploading file "{name}" (type: {mime_type}) to Drive')

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
        log(f"Error uploading file: {error_message}")
        if "404" in error_message:
            raise ToolError("Parent folder not found. Check the parent folder ID.")
        if "403" in error_message:
            raise ToolError("Permission denied. Make sure you have write access to Drive.")
        raise ToolError(f"Failed to upload file: {error_message}")


def create_google_doc(
    title: str,
    parent_folder_id: str | None = None,
) -> str:
    """
    Create a new blank Google Document.

    Args:
        title: Title for the new document
        parent_folder_id: Optional parent folder ID (None for root)

    Returns:
        Success message with document ID and link

    Raises:
        UserError: For permission errors
    """
    drive = get_drive_client()
    log(f'Creating new Google Doc: "{title}"')

    try:
        metadata: dict[str, Any] = {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
        }

        if parent_folder_id:
            metadata["parents"] = [parent_folder_id]

        response = (
            drive.files()
            .create(requestBody=metadata, fields="id,name,webViewLink")
            .execute()
        )

        return (
            f"Successfully created Google Document \"{response.get('name')}\"\n"
            f"ID: {response.get('id')}\n"
            f"Link: {response.get('webViewLink')}"
        )

    except Exception as e:
        error_message = str(e)
        log(f"Error creating Google Doc: {error_message}")
        if "404" in error_message:
            raise ToolError("Parent folder not found. Check the parent folder ID.")
        if "403" in error_message:
            raise ToolError("Permission denied. Make sure you have write access to Drive.")
        raise ToolError(f"Failed to create document: {error_message}")


def create_google_doc_from_markdown(
    title: str,
    markdown_content: str,
    parent_folder_id: str | None = None,
) -> str:
    """
    Create a new Google Document with content from markdown.

    Uses Google Drive API's native markdown import (July 2024+).

    Args:
        title: Title for the new document
        markdown_content: Markdown content to import into the document
        parent_folder_id: Optional parent folder ID (None for root)

    Returns:
        Success message with document ID and link

    Raises:
        UserError: For permission errors
    """
    from googleapiclient.http import MediaInMemoryUpload

    drive = get_drive_client()
    log(f'Creating new Google Doc from markdown: "{title}"')

    try:
        # Prepare file metadata
        metadata: dict[str, Any] = {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
        }

        if parent_folder_id:
            metadata["parents"] = [parent_folder_id]

        # Prepare markdown content as media upload
        markdown_bytes = markdown_content.encode('utf-8')
        media = MediaInMemoryUpload(
            markdown_bytes,
            mimetype='text/markdown',
            resumable=True
        )

        # Create document with markdown import
        response = (
            drive.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id,name,webViewLink",
                supportsAllDrives=True
            )
            .execute()
        )

        document_id = response.get("id")
        log(f"Created document {document_id} from markdown using native Drive API import")

        return (
            f"Successfully created Google Document \"{response.get('name')}\" from markdown\n"
            f"ID: {document_id}\n"
            f"Link: {response.get('webViewLink')}"
        )

    except Exception as e:
        error_message = str(e)
        log(f"Error creating Google Doc from markdown: {error_message}")
        if "404" in error_message:
            raise ToolError("Parent folder not found. Check the parent folder ID.")
        if "403" in error_message:
            raise ToolError("Permission denied. Make sure you have write access to Drive.")
        raise ToolError(f"Failed to create document from markdown: {error_message}")


# --- New Drive File Management Operations ---


def move_file(
    file_id: str,
    new_parent_folder_id: str,
    remove_from_current_parents: bool = True,
) -> str:
    """
    Move a file to a different folder.

    Args:
        file_id: The ID of the file to move
        new_parent_folder_id: The ID of the destination folder
        remove_from_current_parents: Whether to remove from current folders

    Returns:
        Success message with new location

    Raises:
        ToolError: For permission/not found errors
    """
    drive = get_drive_client()
    log(f"Moving file {file_id} to folder {new_parent_folder_id}")

    try:
        # Get current parents if needed
        current_parents = None
        if remove_from_current_parents:
            file_metadata = drive.files().get(
                fileId=file_id,
                fields="parents"
            ).execute()
            current_parents = ",".join(file_metadata.get("parents", []))

        # Move file
        update_params = {
            "fileId": file_id,
            "addParents": new_parent_folder_id,
            "fields": "id,name,parents"
        }

        if current_parents:
            update_params["removeParents"] = current_parents

        response = drive.files().update(**update_params).execute()

        return (
            f"Successfully moved file \"{response.get('name')}\" "
            f"to folder {new_parent_folder_id}\n"
            f"File ID: {response.get('id')}"
        )

    except Exception as e:
        error_message = str(e)
        log(f"Error moving file: {error_message}")
        if "404" in error_message:
            raise ToolError("File or folder not found. Check the file ID and folder ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the file and folder."
            )
        raise ToolError(f"Failed to move file: {error_message}")


def copy_file(
    file_id: str,
    new_name: str | None = None,
    parent_folder_id: str | None = None,
) -> str:
    """
    Create a copy of a file.

    Args:
        file_id: The ID of the file to copy
        new_name: Name for the copy (if not provided, uses "Copy of [original name]")
        parent_folder_id: Parent folder ID for the copy (if not provided, uses same folder)

    Returns:
        Success message with copy details

    Raises:
        ToolError: For permission/not found errors
    """
    drive = get_drive_client()
    log(f"Copying file {file_id}")

    try:
        body = {}
        if new_name:
            body["name"] = new_name
        if parent_folder_id:
            body["parents"] = [parent_folder_id]

        response = drive.files().copy(
            fileId=file_id,
            body=body,
            fields="id,name,webViewLink"
        ).execute()

        return (
            f"Successfully created copy: \"{response.get('name')}\"\n"
            f"File ID: {response.get('id')}\n"
            f"Link: {response.get('webViewLink')}"
        )

    except Exception as e:
        error_message = str(e)
        log(f"Error copying file: {error_message}")
        if "404" in error_message:
            raise ToolError("File not found. Check the file ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have read access to the file."
            )
        raise ToolError(f"Failed to copy file: {error_message}")


def trash_file(file_id: str) -> str:
    """
    Move a file to trash.

    Args:
        file_id: The ID of the file to trash

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    drive = get_drive_client()
    log(f"Trashing file {file_id}")

    try:
        response = drive.files().update(
            fileId=file_id,
            body={"trashed": True},
            fields="id,name,trashed"
        ).execute()

        return f"Successfully moved \"{response.get('name')}\" to trash. File ID: {file_id}"

    except Exception as e:
        error_message = str(e)
        log(f"Error trashing file: {error_message}")
        if "404" in error_message:
            raise ToolError("File not found. Check the file ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the file."
            )
        raise ToolError(f"Failed to trash file: {error_message}")


def restore_file(file_id: str) -> str:
    """
    Restore a file from trash.

    Args:
        file_id: The ID of the file to restore

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    drive = get_drive_client()
    log(f"Restoring file {file_id} from trash")

    try:
        response = drive.files().update(
            fileId=file_id,
            body={"trashed": False},
            fields="id,name,trashed"
        ).execute()

        return f"Successfully restored \"{response.get('name')}\" from trash. File ID: {file_id}"

    except Exception as e:
        error_message = str(e)
        log(f"Error restoring file: {error_message}")
        if "404" in error_message:
            raise ToolError("File not found. Check the file ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the file."
            )
        raise ToolError(f"Failed to restore file: {error_message}")


def permanently_delete_file(file_id: str) -> str:
    """
    Permanently delete a file (cannot be recovered).

    Args:
        file_id: The ID of the file to delete

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    drive = get_drive_client()
    log(f"Permanently deleting file {file_id}")

    try:
        drive.files().delete(fileId=file_id).execute()

        return f"Successfully permanently deleted file {file_id}. This action cannot be undone."

    except Exception as e:
        error_message = str(e)
        log(f"Error deleting file: {error_message}")
        if "404" in error_message:
            raise ToolError("File not found. Check the file ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the file."
            )
        raise ToolError(f"Failed to delete file: {error_message}")


def star_file(file_id: str) -> str:
    """
    Star/favorite a file.

    Args:
        file_id: The ID of the file to star

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    drive = get_drive_client()
    log(f"Starring file {file_id}")

    try:
        response = drive.files().update(
            fileId=file_id,
            body={"starred": True},
            fields="id,name,starred"
        ).execute()

        return f"Successfully starred \"{response.get('name')}\". File ID: {file_id}"

    except Exception as e:
        error_message = str(e)
        log(f"Error starring file: {error_message}")
        if "404" in error_message:
            raise ToolError("File not found. Check the file ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have access to the file."
            )
        raise ToolError(f"Failed to star file: {error_message}")


def unstar_file(file_id: str) -> str:
    """
    Remove star from a file.

    Args:
        file_id: The ID of the file to unstar

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    drive = get_drive_client()
    log(f"Unstarring file {file_id}")

    try:
        response = drive.files().update(
            fileId=file_id,
            body={"starred": False},
            fields="id,name,starred"
        ).execute()

        return f"Successfully unstarred \"{response.get('name')}\". File ID: {file_id}"

    except Exception as e:
        error_message = str(e)
        log(f"Error unstarring file: {error_message}")
        if "404" in error_message:
            raise ToolError("File not found. Check the file ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have access to the file."
            )
        raise ToolError(f"Failed to unstar file: {error_message}")


# --- Drive Permissions Management ---


def share_document(
    document_id: str,
    email_address: str,
    role: str = "reader",
    send_notification_email: bool = True,
    email_message: str | None = None,
) -> str:
    """
    Share a document with a specific user.

    Args:
        document_id: The ID of the document to share
        email_address: Email address of the user to share with
        role: Permission role ("reader", "writer", "commenter")
        send_notification_email: Whether to send email notification
        email_message: Optional custom message for notification

    Returns:
        Success message with permission details

    Raises:
        ToolError: For permission errors or invalid email
    """
    drive = get_drive_client()
    log(f"Sharing document {document_id} with {email_address} as {role}")

    try:
        permission = {
            "type": "user",
            "role": role,
            "emailAddress": email_address
        }

        create_params = {
            "fileId": document_id,
            "body": permission,
            "sendNotificationEmail": send_notification_email,
            "fields": "id,emailAddress,role"
        }

        if email_message and send_notification_email:
            create_params["emailMessage"] = email_message

        response = drive.permissions().create(**create_params).execute()

        return (
            f"Successfully shared document with {response.get('emailAddress')} "
            f"as {response.get('role')}\n"
            f"Permission ID: {response.get('id')}"
        )

    except Exception as e:
        error_message = str(e)
        log(f"Error sharing document: {error_message}")
        if "404" in error_message:
            raise ToolError("Document not found. Check the document ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have permission to share this document."
            )
        if "400" in error_message:
            raise ToolError(
                f"Invalid request: {error_message}. Check the email address and role."
            )
        raise ToolError(f"Failed to share document: {error_message}")


def list_permissions(document_id: str) -> str:
    """
    List all permissions on a document.

    Args:
        document_id: The ID of the document

    Returns:
        Formatted list of permissions

    Raises:
        ToolError: For permission/not found errors
    """
    drive = get_drive_client()
    log(f"Listing permissions for document {document_id}")

    try:
        response = drive.permissions().list(
            fileId=document_id,
            fields="permissions(id,emailAddress,role,type,displayName)"
        ).execute()

        permissions = response.get("permissions", [])

        if not permissions:
            return "No permissions found for this document."

        lines = [f"Permissions for document {document_id}:", ""]
        for perm in permissions:
            perm_type = perm.get("type", "unknown")
            role = perm.get("role", "unknown")
            email = perm.get("emailAddress", perm.get("displayName", "N/A"))
            perm_id = perm.get("id", "")

            lines.append(f"- {email} ({perm_type}): {role} [ID: {perm_id}]")

        return "\n".join(lines)

    except Exception as e:
        error_message = str(e)
        log(f"Error listing permissions: {error_message}")
        if "404" in error_message:
            raise ToolError("Document not found. Check the document ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have permission to view this document's permissions."
            )
        raise ToolError(f"Failed to list permissions: {error_message}")


def remove_permission(
    document_id: str,
    permission_id: str,
) -> str:
    """
    Remove a user's access to a document.

    Args:
        document_id: The ID of the document
        permission_id: The ID of the permission to remove

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    drive = get_drive_client()
    log(f"Removing permission {permission_id} from document {document_id}")

    try:
        drive.permissions().delete(
            fileId=document_id,
            permissionId=permission_id
        ).execute()

        return f"Successfully removed permission {permission_id} from document {document_id}."

    except Exception as e:
        error_message = str(e)
        log(f"Error removing permission: {error_message}")
        if "404" in error_message:
            raise ToolError("Document or permission not found. Check the document ID and permission ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have permission to manage sharing for this document."
            )
        raise ToolError(f"Failed to remove permission: {error_message}")


def update_permission(
    document_id: str,
    permission_id: str,
    new_role: str,
) -> str:
    """
    Change a permission's role.

    Args:
        document_id: The ID of the document
        permission_id: The ID of the permission to update
        new_role: New permission role ("reader", "writer", "commenter")

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    drive = get_drive_client()
    log(f"Updating permission {permission_id} to {new_role} for document {document_id}")

    try:
        response = drive.permissions().update(
            fileId=document_id,
            permissionId=permission_id,
            body={"role": new_role},
            fields="id,emailAddress,role"
        ).execute()

        return (
            f"Successfully updated permission for {response.get('emailAddress', 'user')} "
            f"to {response.get('role')}\n"
            f"Permission ID: {response.get('id')}"
        )

    except Exception as e:
        error_message = str(e)
        log(f"Error updating permission: {error_message}")
        if "404" in error_message:
            raise ToolError("Document or permission not found. Check the document ID and permission ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have permission to manage sharing for this document."
            )
        if "400" in error_message:
            raise ToolError(
                f"Invalid request: {error_message}. Check the role value."
            )
        raise ToolError(f"Failed to update permission: {error_message}")
