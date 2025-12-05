"""
Google Docs MCP Server

Main MCP server entry point with all tool definitions.
Uses FastMCP framework for MCP protocol implementation.

IMPORTANT: All logging must use stderr (via _log function), never stdout.
The MCP protocol uses stdout for JSON-RPC communication.
"""

import sys
from typing import Annotated

from fastmcp import FastMCP
from mcp.types import ImageContent

from google_docs_mcp.types import TextStyleArgs, ParagraphStyleArgs, UserError
from google_docs_mcp.api import documents, comments, drive


def _log(message: str) -> None:
    """Log a message to stderr (MCP protocol compatibility)."""
    print(message, file=sys.stderr)


# Create MCP server
mcp = FastMCP(
    name="Google Docs MCP Server",
    instructions="""
    This MCP server provides tools for reading, creating, and editing Google Documents.

    Key capabilities:
    - Read document content in text, JSON, or Markdown format
    - Insert, append, and delete text
    - Apply text and paragraph formatting
    - Manage document tabs
    - Handle comments (list, add, reply, resolve, delete)
    - Search and list Google Docs in Drive
    - Create and manage Drive folders

    Document indexing uses 1-based positions (index 1 is start of document).
    """,
)


# === DOCUMENT TOOLS ===


@mcp.tool()
def read_google_doc(
    document_id: Annotated[str, "The ID of the Google Document (from the URL)"],
    format: Annotated[
        str,
        "Output format: 'text' (plain text), 'json' (raw API structure), 'markdown' (experimental)",
    ] = "text",
    max_length: Annotated[
        int | None,
        "Maximum character limit for output. If not specified, returns full content.",
    ] = None,
    tab_id: Annotated[
        str | None,
        "The ID of a specific tab to read. If not specified, reads the first tab.",
    ] = None,
) -> str:
    """
    Read the content of a Google Document.

    Returns the document content in the specified format.
    Use 'text' for plain content, 'json' for full structure, or 'markdown' for formatted output.
    """
    return documents.read_document(document_id, format, max_length, tab_id)


@mcp.tool()
def list_document_tabs(
    document_id: Annotated[str, "The ID of the Google Document"],
    include_content: Annotated[
        bool, "Whether to include a content summary (character count) for each tab"
    ] = False,
) -> str:
    """
    List all tabs in a Google Document, including their hierarchy, IDs, and structure.
    """
    return documents.list_document_tabs(document_id, include_content)


@mcp.tool()
def append_to_google_doc(
    document_id: Annotated[str, "The ID of the Google Document"],
    text_to_append: Annotated[str, "The text to add to the end of the document"],
    add_newline_if_needed: Annotated[
        bool, "Automatically add a newline before the appended text if needed"
    ] = True,
    tab_id: Annotated[
        str | None, "The ID of a specific tab to append to. If not specified, uses first tab."
    ] = None,
) -> str:
    """
    Append text to the very end of a Google Document or specific tab.
    """
    return documents.append_to_document(
        document_id, text_to_append, add_newline_if_needed, tab_id
    )


@mcp.tool()
def insert_text(
    document_id: Annotated[str, "The ID of the Google Document"],
    text_to_insert: Annotated[str, "The text to insert"],
    index: Annotated[int, "The index (1-based) where the text should be inserted"],
    tab_id: Annotated[
        str | None, "The ID of a specific tab. If not specified, uses first tab."
    ] = None,
) -> str:
    """
    Insert text at a specific index within a document or tab.
    """
    return documents.insert_text(document_id, text_to_insert, index, tab_id)


@mcp.tool()
def delete_range(
    document_id: Annotated[str, "The ID of the Google Document"],
    start_index: Annotated[int, "Starting index of the range (inclusive, 1-based)"],
    end_index: Annotated[int, "Ending index of the range (exclusive)"],
    tab_id: Annotated[
        str | None, "The ID of a specific tab. If not specified, uses first tab."
    ] = None,
) -> str:
    """
    Delete content within a specified range from a document or tab.
    """
    return documents.delete_range(document_id, start_index, end_index, tab_id)


@mcp.tool()
def apply_text_style(
    document_id: Annotated[str, "The ID of the Google Document"],
    bold: Annotated[bool | None, "Apply bold formatting"] = None,
    italic: Annotated[bool | None, "Apply italic formatting"] = None,
    underline: Annotated[bool | None, "Apply underline formatting"] = None,
    strikethrough: Annotated[bool | None, "Apply strikethrough formatting"] = None,
    font_size: Annotated[float | None, "Font size in points (e.g., 12)"] = None,
    font_family: Annotated[str | None, "Font family (e.g., 'Arial')"] = None,
    foreground_color: Annotated[
        str | None, "Text color in hex format (e.g., '#FF0000')"
    ] = None,
    background_color: Annotated[
        str | None, "Background color in hex format (e.g., '#FFFF00')"
    ] = None,
    link_url: Annotated[str | None, "Make text a hyperlink to this URL"] = None,
    start_index: Annotated[int | None, "Starting index of range (if targeting by range)"] = None,
    end_index: Annotated[int | None, "Ending index of range (if targeting by range)"] = None,
    text_to_find: Annotated[
        str | None, "Text to find and format (if targeting by text)"
    ] = None,
    match_instance: Annotated[int, "Which instance of text to target (1st, 2nd, etc.)"] = 1,
) -> str:
    """
    Apply character-level formatting (bold, color, font, etc.) to text.

    Target can be specified either by:
    - Range: Provide start_index and end_index
    - Text search: Provide text_to_find and optionally match_instance
    """
    style = TextStyleArgs(
        bold=bold,
        italic=italic,
        underline=underline,
        strikethrough=strikethrough,
        font_size=font_size,
        font_family=font_family,
        foreground_color=foreground_color,
        background_color=background_color,
        link_url=link_url,
    )
    return documents.apply_text_style(
        document_id, style, start_index, end_index, text_to_find, match_instance
    )


@mcp.tool()
def apply_paragraph_style(
    document_id: Annotated[str, "The ID of the Google Document"],
    alignment: Annotated[
        str | None, "Paragraph alignment: 'START', 'END', 'CENTER', 'JUSTIFIED'"
    ] = None,
    indent_start: Annotated[float | None, "Left indentation in points"] = None,
    indent_end: Annotated[float | None, "Right indentation in points"] = None,
    space_above: Annotated[float | None, "Space before paragraph in points"] = None,
    space_below: Annotated[float | None, "Space after paragraph in points"] = None,
    named_style_type: Annotated[
        str | None,
        "Named style: 'NORMAL_TEXT', 'TITLE', 'SUBTITLE', 'HEADING_1' through 'HEADING_6'",
    ] = None,
    keep_with_next: Annotated[
        bool | None, "Keep paragraph with next on same page"
    ] = None,
    start_index: Annotated[int | None, "Starting index of range (if targeting by range)"] = None,
    end_index: Annotated[int | None, "Ending index of range (if targeting by range)"] = None,
    text_to_find: Annotated[
        str | None, "Text to find (styles its containing paragraph)"
    ] = None,
    match_instance: Annotated[int, "Which instance of text to target"] = 1,
    index_within_paragraph: Annotated[
        int | None, "An index within the target paragraph"
    ] = None,
) -> str:
    """
    Apply paragraph-level formatting (alignment, spacing, headings, etc.).

    Target can be specified by:
    - Range: Provide start_index and end_index
    - Text search: Provide text_to_find (styles the containing paragraph)
    - Index: Provide index_within_paragraph
    """
    style = ParagraphStyleArgs(
        alignment=alignment,
        indent_start=indent_start,
        indent_end=indent_end,
        space_above=space_above,
        space_below=space_below,
        named_style_type=named_style_type,
        keep_with_next=keep_with_next,
    )
    return documents.apply_paragraph_style(
        document_id,
        style,
        start_index,
        end_index,
        text_to_find,
        match_instance,
        index_within_paragraph,
    )


@mcp.tool()
def format_matching_text(
    document_id: Annotated[str, "The ID of the Google Document"],
    text_to_find: Annotated[str, "The exact text string to find and format"],
    match_instance: Annotated[int, "Which instance of the text to format (1st, 2nd, etc.)"] = 1,
    bold: Annotated[bool | None, "Apply bold formatting"] = None,
    italic: Annotated[bool | None, "Apply italic formatting"] = None,
    underline: Annotated[bool | None, "Apply underline formatting"] = None,
    strikethrough: Annotated[bool | None, "Apply strikethrough formatting"] = None,
    font_size: Annotated[float | None, "Font size in points"] = None,
    font_family: Annotated[str | None, "Font family name"] = None,
    foreground_color: Annotated[str | None, "Text color in hex format"] = None,
    background_color: Annotated[str | None, "Background color in hex format"] = None,
    link_url: Annotated[str | None, "Make text a hyperlink"] = None,
) -> str:
    """
    Find specific text and apply character formatting to it.

    This is a convenience tool that combines text search with formatting.
    """
    style = TextStyleArgs(
        bold=bold,
        italic=italic,
        underline=underline,
        strikethrough=strikethrough,
        font_size=font_size,
        font_family=font_family,
        foreground_color=foreground_color,
        background_color=background_color,
        link_url=link_url,
    )
    return documents.apply_text_style(
        document_id, style, text_to_find=text_to_find, match_instance=match_instance
    )


@mcp.tool()
def insert_table(
    document_id: Annotated[str, "The ID of the Google Document"],
    rows: Annotated[int, "Number of rows for the new table"],
    columns: Annotated[int, "Number of columns for the new table"],
    index: Annotated[int, "The index (1-based) where the table should be inserted"],
) -> str:
    """
    Insert a new table with specified dimensions at a given index.
    """
    return documents.insert_table(document_id, rows, columns, index)


@mcp.tool()
def insert_page_break(
    document_id: Annotated[str, "The ID of the Google Document"],
    index: Annotated[int, "The index (1-based) where the page break should be inserted"],
) -> str:
    """
    Insert a page break at the specified index.
    """
    return documents.insert_page_break(document_id, index)


@mcp.tool()
def insert_image_from_url(
    document_id: Annotated[str, "The ID of the Google Document"],
    image_url: Annotated[str, "Publicly accessible URL to the image"],
    index: Annotated[int, "The index (1-based) where the image should be inserted"],
    width: Annotated[float | None, "Width of the image in points"] = None,
    height: Annotated[float | None, "Height of the image in points"] = None,
) -> str:
    """
    Insert an inline image from a publicly accessible URL.
    """
    return documents.insert_image_from_url(document_id, image_url, index, width, height)


# === COMMENT TOOLS ===


@mcp.tool()
def list_comments(
    document_id: Annotated[str, "The ID of the Google Document"],
) -> str:
    """
    List all comments in a Google Document.
    """
    return comments.list_comments(document_id)


@mcp.tool()
def get_comment(
    document_id: Annotated[str, "The ID of the Google Document"],
    comment_id: Annotated[str, "The ID of the comment to retrieve"],
) -> str:
    """
    Get a specific comment with its full thread of replies.
    """
    return comments.get_comment(document_id, comment_id)


@mcp.tool()
def add_comment(
    document_id: Annotated[str, "The ID of the Google Document"],
    start_index: Annotated[int, "Starting index of the text range (inclusive, 1-based)"],
    end_index: Annotated[int, "Ending index of the text range (exclusive)"],
    comment_text: Annotated[str, "The content of the comment"],
) -> str:
    """
    Add a comment anchored to a specific text range in the document.

    NOTE: Due to Google API limitations, comments created programmatically
    appear in the 'All Comments' list but may not be visibly anchored in the UI.
    """
    return comments.add_comment(document_id, start_index, end_index, comment_text)


@mcp.tool()
def reply_to_comment(
    document_id: Annotated[str, "The ID of the Google Document"],
    comment_id: Annotated[str, "The ID of the comment to reply to"],
    reply_text: Annotated[str, "The content of the reply"],
) -> str:
    """
    Add a reply to an existing comment.
    """
    return comments.reply_to_comment(document_id, comment_id, reply_text)


@mcp.tool()
def resolve_comment(
    document_id: Annotated[str, "The ID of the Google Document"],
    comment_id: Annotated[str, "The ID of the comment to resolve"],
) -> str:
    """
    Mark a comment as resolved.

    NOTE: Due to Google API limitations, the resolved status may not persist
    in the Google Docs UI for all document types.
    """
    return comments.resolve_comment(document_id, comment_id)


@mcp.tool()
def delete_comment(
    document_id: Annotated[str, "The ID of the Google Document"],
    comment_id: Annotated[str, "The ID of the comment to delete"],
) -> str:
    """
    Delete a comment from a document.
    """
    return comments.delete_comment(document_id, comment_id)


# === GOOGLE DRIVE TOOLS ===


@mcp.tool()
def list_google_docs(
    max_results: Annotated[int, "Maximum number of documents to return (1-100)"] = 20,
    query: Annotated[str | None, "Search query to filter documents by name or content"] = None,
    order_by: Annotated[
        str, "Sort order: 'name', 'modifiedTime', 'createdTime'"
    ] = "modifiedTime",
) -> str:
    """
    List Google Documents from your Google Drive with optional filtering.
    """
    return drive.list_google_docs(max_results, query, order_by)


@mcp.tool()
def search_google_docs(
    search_query: Annotated[str, "Search term to find in document names or content"],
    search_in: Annotated[
        str, "Where to search: 'name', 'content', or 'both'"
    ] = "both",
    max_results: Annotated[int, "Maximum number of results to return (1-50)"] = 10,
    modified_after: Annotated[
        str | None, "Only return documents modified after this date (ISO 8601 format)"
    ] = None,
) -> str:
    """
    Search for Google Documents by name, content, or other criteria.
    """
    return drive.search_google_docs(search_query, search_in, max_results, modified_after)


@mcp.tool()
def get_recent_google_docs(
    max_results: Annotated[int, "Maximum number of recent documents to return (1-50)"] = 10,
    days_back: Annotated[
        int, "Only show documents modified within this many days (1-365)"
    ] = 30,
) -> str:
    """
    Get the most recently modified Google Documents.
    """
    return drive.get_recent_google_docs(max_results, days_back)


@mcp.tool()
def get_document_info(
    document_id: Annotated[str, "The ID of the Google Document"],
) -> str:
    """
    Get detailed information about a specific Google Document.
    """
    return drive.get_document_info(document_id)


@mcp.tool()
def create_folder(
    name: Annotated[str, "Name for the new folder"],
    parent_folder_id: Annotated[
        str | None, "Parent folder ID. If not provided, creates in Drive root."
    ] = None,
) -> str:
    """
    Create a new folder in Google Drive.
    """
    return drive.create_folder(name, parent_folder_id)


@mcp.tool()
def list_folder_contents(
    folder_id: Annotated[str, "ID of the folder to list ('root' for Drive root)"],
    include_subfolders: Annotated[bool, "Whether to include subfolders in results"] = True,
    include_files: Annotated[bool, "Whether to include files in results"] = True,
    max_results: Annotated[int, "Maximum number of items to return (1-100)"] = 50,
) -> str:
    """
    List the contents of a specific folder in Google Drive.
    """
    return drive.list_folder_contents(
        folder_id, include_subfolders, include_files, max_results
    )


@mcp.tool()
def upload_image_to_drive(
    image: Annotated[ImageContent, "Image content to upload to Google Drive"],
    name: Annotated[str, "Name for the image file in Drive (e.g., 'photo.png')"],
    parent_folder_id: Annotated[
        str | None, "Parent folder ID. If not provided, uploads to Drive root."
    ] = None,
) -> str:
    """
    Upload an image to Google Drive.

    Accepts an image as ImageContent (base64-encoded data with MIME type) and uploads it to Google Drive.
    Returns the file ID and web link for the uploaded image.
    """
    return drive.upload_image_to_drive(image, name, parent_folder_id)


@mcp.tool()
def upload_file_to_drive(
    file_data: Annotated[str, "Base64-encoded file data"],
    name: Annotated[str, "Name for the file in Drive"],
    mime_type: Annotated[str, "MIME type of the file (e.g., 'application/pdf', 'text/plain')"],
    parent_folder_id: Annotated[
        str | None, "Parent folder ID. If not provided, uploads to Drive root."
    ] = None,
) -> str:
    """
    Upload a file to Google Drive from base64-encoded data.

    Accepts file data in base64 format and uploads it to Google Drive.
    Supports any file type. Returns the file ID and web link.
    """
    return drive.upload_file_to_drive(file_data, name, mime_type, parent_folder_id)


def main() -> None:
    """Run the Google Docs MCP Server."""
    _log("Starting Google Docs MCP Server...")
    mcp.run()


if __name__ == "__main__":
    main()
