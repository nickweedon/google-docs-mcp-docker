"""
Comment operations for Google Docs MCP Server.

Handles listing, creating, and managing comments on documents.
"""

import json
import sys
from typing import Any

from google_docs_mcp.auth import get_docs_client, get_drive_client, get_auth_client
from google_docs_mcp.types import CommentInfo, UserError
from googleapiclient.discovery import build


def _log(message: str) -> None:
    """Log a message to stderr (MCP protocol compatibility)."""
    print(message, file=sys.stderr)


def list_comments(document_id: str) -> str:
    """
    List all comments in a Google Document.

    Args:
        document_id: The ID of the Google Document

    Returns:
        Formatted string with comment information

    Raises:
        UserError: For permission/not found errors
    """
    _log(f"Listing comments for document {document_id}")

    try:
        # Use Drive API v3 for comments
        auth_client = get_auth_client()
        drive = build("drive", "v3", credentials=auth_client)

        response = (
            drive.comments()
            .list(
                fileId=document_id,
                fields="comments(id,content,quotedFileContent,author,createdTime,resolved)",
                pageSize=100,
            )
            .execute()
        )

        comments = response.get("comments", [])

        if not comments:
            return "No comments found in this document."

        # Format comments for display
        result_parts = []
        for index, comment in enumerate(comments):
            author = comment.get("author", {}).get("displayName", "Unknown")
            created = comment.get("createdTime", "Unknown date")
            if created != "Unknown date":
                # Simplify date format
                created = created[:10]  # Just get YYYY-MM-DD

            status = " [RESOLVED]" if comment.get("resolved") else ""

            # Get quoted text
            quoted_content = comment.get("quotedFileContent", {})
            quoted_text = quoted_content.get("value", "")
            anchor = ""
            if quoted_text:
                truncated = (
                    quoted_text[:100] + "..." if len(quoted_text) > 100 else quoted_text
                )
                anchor = f' (anchored to: "{truncated}")'

            content = comment.get("content", "")
            comment_id = comment.get("id", "")

            result_parts.append(
                f"\n{index + 1}. **{author}** ({created}){status}{anchor}\n"
                f"   {content}\n"
                f"   Comment ID: {comment_id}"
            )

        return f"Found {len(comments)} comment{'s' if len(comments) != 1 else ''}:\n{''.join(result_parts)}"

    except Exception as e:
        error_message = str(e)
        _log(f"Error listing comments: {error_message}")
        raise UserError(f"Failed to list comments: {error_message}")


def get_comment(document_id: str, comment_id: str) -> str:
    """
    Get a specific comment with its full thread of replies.

    Args:
        document_id: The ID of the Google Document
        comment_id: The ID of the comment to retrieve

    Returns:
        Formatted string with comment and replies

    Raises:
        UserError: For permission/not found errors
    """
    _log(f"Getting comment {comment_id} from document {document_id}")

    try:
        auth_client = get_auth_client()
        drive = build("drive", "v3", credentials=auth_client)

        response = (
            drive.comments()
            .get(
                fileId=document_id,
                commentId=comment_id,
                fields="id,content,quotedFileContent,author,createdTime,resolved,replies(id,content,author,createdTime)",
            )
            .execute()
        )

        author = response.get("author", {}).get("displayName", "Unknown")
        created = response.get("createdTime", "Unknown date")
        if created != "Unknown date":
            created = created[:10]

        status = " [RESOLVED]" if response.get("resolved") else ""
        quoted_text = response.get("quotedFileContent", {}).get("value", "")
        anchor = f'\nAnchored to: "{quoted_text}"' if quoted_text else ""
        content = response.get("content", "")

        result = f"**{author}** ({created}){status}{anchor}\n{content}"

        # Add replies
        replies = response.get("replies", [])
        if replies:
            result += "\n\n**Replies:**"
            for index, reply in enumerate(replies):
                reply_author = reply.get("author", {}).get("displayName", "Unknown")
                reply_date = reply.get("createdTime", "Unknown date")
                if reply_date != "Unknown date":
                    reply_date = reply_date[:10]
                reply_content = reply.get("content", "")
                result += f"\n{index + 1}. **{reply_author}** ({reply_date})\n   {reply_content}"

        return result

    except Exception as e:
        error_message = str(e)
        _log(f"Error getting comment: {error_message}")
        raise UserError(f"Failed to get comment: {error_message}")


def add_comment(
    document_id: str, start_index: int, end_index: int, comment_text: str
) -> str:
    """
    Add a comment anchored to a specific text range.

    NOTE: Due to Google API limitations, comments created programmatically
    appear in the "All Comments" list but may not be visibly anchored to text
    in the document UI.

    Args:
        document_id: The ID of the Google Document
        start_index: Starting index of text range (inclusive, 1-based)
        end_index: Ending index of text range (exclusive)
        comment_text: Content of the comment

    Returns:
        Success message with comment ID

    Raises:
        UserError: For permission/not found errors
    """
    _log(f"Adding comment to range {start_index}-{end_index} in doc {document_id}")

    if end_index <= start_index:
        raise UserError("End index must be greater than start index.")

    try:
        # First get the quoted text from the document
        docs = get_docs_client()
        doc = docs.documents().get(documentId=document_id).execute()

        # Extract quoted text
        quoted_text = ""
        content = doc.get("body", {}).get("content", [])

        for element in content:
            paragraph = element.get("paragraph", {})
            for pe in paragraph.get("elements", []):
                text_run = pe.get("textRun", {})
                if text_run:
                    element_start = pe.get("startIndex", 0)
                    element_end = pe.get("endIndex", 0)
                    text = text_run.get("content", "")

                    # Check if this element overlaps with our range
                    if element_end > start_index and element_start < end_index:
                        start_offset = max(0, start_index - element_start)
                        end_offset = min(len(text), end_index - element_start)
                        quoted_text += text[start_offset:end_offset]

        # Use Drive API v3 for comments
        auth_client = get_auth_client()
        drive = build("drive", "v3", credentials=auth_client)

        response = (
            drive.comments()
            .create(
                fileId=document_id,
                fields="id,content,quotedFileContent,author,createdTime,resolved",
                body={
                    "content": comment_text,
                    "quotedFileContent": {
                        "value": quoted_text,
                        "mimeType": "text/html",
                    },
                    "anchor": json.dumps(
                        {
                            "r": document_id,
                            "a": [
                                {
                                    "txt": {
                                        "o": start_index - 1,  # 0-based
                                        "l": end_index - start_index,
                                        "ml": end_index - start_index,
                                    }
                                }
                            ],
                        }
                    ),
                },
            )
            .execute()
        )

        return f"Comment added successfully. Comment ID: {response.get('id')}"

    except UserError:
        raise
    except Exception as e:
        error_message = str(e)
        _log(f"Error adding comment: {error_message}")
        raise UserError(f"Failed to add comment: {error_message}")


def reply_to_comment(document_id: str, comment_id: str, reply_text: str) -> str:
    """
    Add a reply to an existing comment.

    Args:
        document_id: The ID of the Google Document
        comment_id: The ID of the comment to reply to
        reply_text: Content of the reply

    Returns:
        Success message with reply ID

    Raises:
        UserError: For permission/not found errors
    """
    _log(f"Adding reply to comment {comment_id} in doc {document_id}")

    try:
        auth_client = get_auth_client()
        drive = build("drive", "v3", credentials=auth_client)

        response = (
            drive.replies()
            .create(
                fileId=document_id,
                commentId=comment_id,
                fields="id,content,author,createdTime",
                body={"content": reply_text},
            )
            .execute()
        )

        return f"Reply added successfully. Reply ID: {response.get('id')}"

    except Exception as e:
        error_message = str(e)
        _log(f"Error adding reply: {error_message}")
        raise UserError(f"Failed to add reply: {error_message}")


def resolve_comment(document_id: str, comment_id: str) -> str:
    """
    Mark a comment as resolved.

    NOTE: Due to Google API limitations, the resolved status may not persist
    in the Google Docs UI for all document types.

    Args:
        document_id: The ID of the Google Document
        comment_id: The ID of the comment to resolve

    Returns:
        Success message

    Raises:
        UserError: For permission/not found errors
    """
    _log(f"Resolving comment {comment_id} in doc {document_id}")

    try:
        auth_client = get_auth_client()
        drive = build("drive", "v3", credentials=auth_client)

        # Get current comment content (required by API)
        current = (
            drive.comments()
            .get(fileId=document_id, commentId=comment_id, fields="content")
            .execute()
        )

        # Update with resolved status
        drive.comments().update(
            fileId=document_id,
            commentId=comment_id,
            fields="id,resolved",
            body={"content": current.get("content"), "resolved": True},
        ).execute()

        # Verify
        verify = (
            drive.comments()
            .get(fileId=document_id, commentId=comment_id, fields="resolved")
            .execute()
        )

        if verify.get("resolved"):
            return f"Comment {comment_id} has been marked as resolved."
        else:
            return (
                f"Attempted to resolve comment {comment_id}, but the resolved status "
                f"may not persist in the Google Docs UI due to API limitations. "
                f"The comment can be resolved manually in the Google Docs interface."
            )

    except Exception as e:
        error_message = str(e)
        _log(f"Error resolving comment: {error_message}")
        raise UserError(f"Failed to resolve comment: {error_message}")


def delete_comment(document_id: str, comment_id: str) -> str:
    """
    Delete a comment from a document.

    Args:
        document_id: The ID of the Google Document
        comment_id: The ID of the comment to delete

    Returns:
        Success message

    Raises:
        UserError: For permission/not found errors
    """
    _log(f"Deleting comment {comment_id} from doc {document_id}")

    try:
        auth_client = get_auth_client()
        drive = build("drive", "v3", credentials=auth_client)

        drive.comments().delete(fileId=document_id, commentId=comment_id).execute()

        return f"Comment {comment_id} has been deleted."

    except Exception as e:
        error_message = str(e)
        _log(f"Error deleting comment: {error_message}")
        raise UserError(f"Failed to delete comment: {error_message}")
