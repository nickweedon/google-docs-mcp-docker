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

    Args:
        title: Title for the new document
        markdown_content: Markdown content to import into the document
        parent_folder_id: Optional parent folder ID (None for root)

    Returns:
        Success message with document ID and link

    Raises:
        UserError: For permission errors
    """
    from google_docs_mcp.auth import get_docs_client

    drive = get_drive_client()
    docs = get_docs_client()
    log(f'Creating new Google Doc from markdown: "{title}"')

    try:
        # First, create a blank document
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

        document_id = response.get("id")

        # Convert markdown to Google Docs requests
        requests = _markdown_to_docs_requests(markdown_content)

        if requests:
            # Apply the requests to insert content
            docs.documents().batchUpdate(
                documentId=document_id,
                body={"requests": requests}
            ).execute()

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


def _markdown_to_docs_requests(markdown: str) -> list[dict[str, Any]]:
    """
    Convert markdown content to Google Docs API requests.

    This is a basic markdown parser that supports:
    - Headings (# to ######)
    - Bold (**text** or __text__)
    - Italic (*text* or _text_)
    - Bold+Italic (***text***)
    - Bullet lists (- or * prefix)
    - Numbered lists (1. prefix)
    - Links ([text](url))
    - Inline code (`code`)
    - Code blocks (```code```)
    - Horizontal rules (--- or ***)

    Args:
        markdown: Markdown string to convert

    Returns:
        List of Google Docs API requests to insert and format content
    """
    import re

    requests: list[dict[str, Any]] = []
    current_index = 1  # Google Docs uses 1-based indexing
    lines = markdown.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip empty lines
        if not line.strip():
            i += 1
            continue

        # Code blocks
        if line.strip().startswith('```'):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            i += 1  # Skip closing ```

            code_text = '\n'.join(code_lines) + '\n\n'
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': code_text
                }
            })
            # Apply monospace font to code block
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': current_index + len(code_text) - 2
                    },
                    'textStyle': {
                        'fontFamily': 'Courier New',
                        'fontSize': {'magnitude': 10, 'unit': 'PT'}
                    },
                    'fields': 'fontFamily,fontSize'
                }
            })
            current_index += len(code_text)
            continue

        # Headings
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2) + '\n'

            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': text
                }
            })

            # Apply heading style
            style_type = f'HEADING_{level}' if level <= 6 else 'HEADING_6'
            requests.append({
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': current_index + len(text)
                    },
                    'paragraphStyle': {
                        'namedStyleType': style_type
                    },
                    'fields': 'namedStyleType'
                }
            })

            current_index += len(text)
            i += 1
            continue

        # Horizontal rules
        if re.match(r'^(\*{3,}|-{3,}|_{3,})$', line.strip()):
            # Insert a paragraph break to represent the rule
            hr_text = '\n'
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': hr_text
                }
            })
            current_index += len(hr_text)
            i += 1
            continue

        # Bullet lists
        bullet_match = re.match(r'^[\-\*]\s+(.+)$', line)
        if bullet_match:
            text = bullet_match.group(1) + '\n'
            start_index = current_index

            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': text
                }
            })
            current_index += len(text)

            # Apply inline formatting
            _apply_inline_formatting(requests, text, start_index)

            # Create bullet list
            requests.append({
                'createParagraphBullets': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': current_index
                    },
                    'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                }
            })

            i += 1
            continue

        # Numbered lists
        numbered_match = re.match(r'^\d+\.\s+(.+)$', line)
        if numbered_match:
            text = numbered_match.group(1) + '\n'
            start_index = current_index

            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': text
                }
            })
            current_index += len(text)

            # Apply inline formatting
            _apply_inline_formatting(requests, text, start_index)

            # Create numbered list
            requests.append({
                'createParagraphBullets': {
                    'range': {
                        'startIndex': start_index,
                        'endIndex': current_index
                    },
                    'bulletPreset': 'NUMBERED_DECIMAL_ALPHA_ROMAN'
                }
            })

            i += 1
            continue

        # Regular paragraph
        text = line + '\n'
        start_index = current_index

        requests.append({
            'insertText': {
                'location': {'index': current_index},
                'text': text
            }
        })
        current_index += len(text)

        # Apply inline formatting
        _apply_inline_formatting(requests, text, start_index)

        i += 1

    return requests


def _apply_inline_formatting(
    requests: list[dict[str, Any]],
    text: str,
    start_index: int
) -> None:
    """
    Apply inline formatting (bold, italic, links, code) to text.

    Modifies the requests list in place.

    Args:
        requests: List of requests to append formatting requests to
        text: The text to analyze for formatting
        start_index: The starting index of the text in the document
    """
    import re

    # Bold+Italic (***text***)
    for match in re.finditer(r'\*\*\*(.+?)\*\*\*', text):
        content_start = start_index + match.start()
        content_end = start_index + match.end()
        requests.append({
            'updateTextStyle': {
                'range': {
                    'startIndex': content_start,
                    'endIndex': content_end
                },
                'textStyle': {
                    'bold': True,
                    'italic': True
                },
                'fields': 'bold,italic'
            }
        })
        # Delete the markdown symbols
        requests.append({
            'deleteContentRange': {
                'range': {
                    'startIndex': content_start,
                    'endIndex': content_start + 3
                }
            }
        })
        requests.append({
            'deleteContentRange': {
                'range': {
                    'startIndex': content_end - 6,
                    'endIndex': content_end - 3
                }
            }
        })

    # Bold (**text** or __text__)
    for match in re.finditer(r'(\*\*|__)(.+?)\1', text):
        if '***' in match.group(0):
            continue  # Skip if part of bold+italic
        content_start = start_index + match.start() + 2
        content_end = start_index + match.end() - 2
        requests.append({
            'updateTextStyle': {
                'range': {
                    'startIndex': content_start,
                    'endIndex': content_end
                },
                'textStyle': {
                    'bold': True
                },
                'fields': 'bold'
            }
        })

    # Italic (*text* or _text_)
    for match in re.finditer(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', text):
        content_start = start_index + match.start() + 1
        content_end = start_index + match.end() - 1
        requests.append({
            'updateTextStyle': {
                'range': {
                    'startIndex': content_start,
                    'endIndex': content_end
                },
                'textStyle': {
                    'italic': True
                },
                'fields': 'italic'
            }
        })

    # Links [text](url)
    for match in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', text):
        link_text = match.group(1)
        url = match.group(2)
        content_start = start_index + match.start()
        content_end = content_start + len(link_text)

        requests.append({
            'updateTextStyle': {
                'range': {
                    'startIndex': content_start,
                    'endIndex': content_end
                },
                'textStyle': {
                    'link': {'url': url}
                },
                'fields': 'link'
            }
        })

    # Inline code (`code`)
    for match in re.finditer(r'`([^`]+)`', text):
        content_start = start_index + match.start() + 1
        content_end = start_index + match.end() - 1
        requests.append({
            'updateTextStyle': {
                'range': {
                    'startIndex': content_start,
                    'endIndex': content_end
                },
                'textStyle': {
                    'fontFamily': 'Courier New',
                    'fontSize': {'magnitude': 10, 'unit': 'PT'}
                },
                'fields': 'fontFamily,fontSize'
            }
        })
