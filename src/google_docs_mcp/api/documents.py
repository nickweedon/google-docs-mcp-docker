"""
Document operations for Google Docs MCP Server.

Handles reading, writing, and formatting document content.
"""

from typing import Any
import re

from fastmcp.exceptions import ToolError

from google_docs_mcp.auth import get_docs_client, get_drive_client
from google_docs_mcp.types import TextStyleArgs, ParagraphStyleArgs
from google_docs_mcp.api import helpers
from google_docs_mcp.utils import log


def _export_document_as_markdown(
    document_id: str,
    tab_id: str | None = None,
    max_length: int | None = None
) -> str:
    """
    Export a Google Document as markdown using Drive API's native export.

    Uses Google Drive API's native markdown export (July 2024+).

    Args:
        document_id: The ID of the Google Document
        tab_id: Optional tab ID (warning: Drive API exports entire document)
        max_length: Maximum character limit for output

    Returns:
        Markdown string content

    Raises:
        ToolError: For API errors
    """
    drive = get_drive_client()

    # Warn if tab_id is specified since Drive API exports entire document
    if tab_id:
        log(f"Warning: tab_id '{tab_id}' specified but Drive API markdown export will export the entire document")

    try:
        # Export document as markdown using Drive API
        markdown_bytes = (
            drive.files()
            .export(fileId=document_id, mimeType='text/markdown')
            .execute()
        )

        markdown_content = markdown_bytes.decode('utf-8')
        total_length = len(markdown_content)
        log(f"Exported document {document_id} as markdown using native Drive API: {total_length} characters")

        # Apply max_length truncation if needed
        if max_length and total_length > max_length:
            truncated = markdown_content[:max_length]
            return (
                f"{truncated}\n\n... [Markdown truncated to {max_length} chars "
                f"of {total_length} total. Use maxLength parameter to adjust limit "
                f"or remove it to get full content.]"
            )

        return markdown_content

    except Exception as e:
        error_message = str(e)
        log(f"Error exporting document as markdown: {error_message}")
        if "404" in error_message:
            raise ToolError("Document not found. Check the document ID.")
        if "403" in error_message:
            raise ToolError("Permission denied. Make sure you have read access to the document.")
        raise ToolError(f"Failed to export document as markdown: {error_message}")


def read_document(
    document_id: str,
    format: str = "text",
    max_length: int | None = None,
    tab_id: str | None = None,
) -> str:
    """
    Read the content of a Google Document.

    Args:
        document_id: The ID of the Google Document
        format: Output format ('text', 'json', 'markdown')
        max_length: Maximum character limit for output
        tab_id: Specific tab ID to read from

    Returns:
        Document content in the specified format

    Raises:
        UserError: For permission/not found errors
    """
    import json

    docs = get_docs_client()
    log(
        f"Reading Google Doc: {document_id}, Format: {format}"
        f"{f', Tab: {tab_id}' if tab_id else ''}"
    )

    try:
        needs_tabs_content = bool(tab_id)

        if format in ("json", "markdown"):
            fields = "*"
        else:
            fields = "body(content(paragraph(elements(textRun(content)))))"

        res = (
            docs.documents()
            .get(
                documentId=document_id,
                includeTabsContent=needs_tabs_content,
                fields="*" if needs_tabs_content else fields,
            )
            .execute()
        )

        log(f"Fetched doc: {document_id}{f' (tab: {tab_id})' if tab_id else ''}")

        # Determine content source
        content_source: dict
        if tab_id:
            target_tab = helpers.find_tab_by_id(res, tab_id)
            if not target_tab:
                raise ToolError(f'Tab with ID "{tab_id}" not found in document.')
            if not target_tab.get("documentTab"):
                raise ToolError(
                    f'Tab "{tab_id}" does not have content (may not be a document tab).'
                )
            content_source = {"body": target_tab["documentTab"].get("body", {})}
            tab_title = target_tab.get("tabProperties", {}).get("title", "Untitled")
            log(f"Using content from tab: {tab_title}")
        else:
            content_source = res

        if format == "json":
            json_content = json.dumps(content_source, indent=2)
            if max_length and len(json_content) > max_length:
                return (
                    json_content[:max_length]
                    + f"\n... [JSON truncated: {len(json_content)} total chars]"
                )
            return json_content

        if format == "markdown":
            # Use native Drive API export for markdown
            return _export_document_as_markdown(document_id, tab_id, max_length)

        # Default: Text format
        text_content = ""
        element_count = 0
        body = content_source.get("body", {})

        for element in body.get("content", []):
            element_count += 1

            # Handle paragraphs
            paragraph = element.get("paragraph", {})
            for pe in paragraph.get("elements", []):
                text_run = pe.get("textRun", {})
                if text_run.get("content"):
                    text_content += text_run["content"]

            # Handle tables
            table = element.get("table", {})
            for row in table.get("tableRows", []):
                for cell in row.get("tableCells", []):
                    for cell_element in cell.get("content", []):
                        cell_para = cell_element.get("paragraph", {})
                        for pe in cell_para.get("elements", []):
                            text_run = pe.get("textRun", {})
                            if text_run.get("content"):
                                text_content += text_run["content"]

        if not text_content.strip():
            return "Document found, but appears empty."

        total_length = len(text_content)
        log(
            f"Document contains {total_length} characters across {element_count} elements"
        )

        if max_length and total_length > max_length:
            truncated = text_content[:max_length]
            log(f"Truncating content from {total_length} to {max_length} characters")
            return (
                f"Content (truncated to {max_length} chars of {total_length} total):\n"
                f"---\n{truncated}\n\n... [Document continues for "
                f"{total_length - max_length} more characters. Use maxLength parameter "
                f"to adjust limit or remove it to get full content.]"
            )

        return f"Content ({total_length} characters):\n---\n{text_content}"

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error reading doc {document_id}: {error_message}")
        if "404" in error_message:
            raise ToolError(f"Doc not found (ID: {document_id}).")
        if "403" in error_message:
            raise ToolError(f"Permission denied for doc (ID: {document_id}).")
        raise ToolError(f"Failed to read doc: {error_message}")


def list_document_tabs(document_id: str, include_content: bool = False) -> str:
    """
    List all tabs in a Google Document.

    Args:
        document_id: The ID of the Google Document
        include_content: Whether to include content summary for each tab

    Returns:
        Formatted string with tab information

    Raises:
        UserError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Listing tabs for document: {document_id}")

    try:
        fields = (
            "title,tabs"
            if include_content
            else "title,tabs(tabProperties,childTabs)"
        )

        res = (
            docs.documents()
            .get(documentId=document_id, includeTabsContent=True, fields=fields)
            .execute()
        )

        doc_title = res.get("title", "Untitled Document")
        all_tabs = helpers.get_all_tabs(res)

        if not all_tabs:
            return f'Document "{doc_title}" appears to have no tabs (unexpected).'

        is_single_tab = len(all_tabs) == 1

        result = f'**Document:** "{doc_title}"\n'
        result += f"**Total tabs:** {len(all_tabs)}"
        result += " (single-tab document)\n\n" if is_single_tab else "\n\n"

        if not is_single_tab:
            result += "**Tab Structure:**\n"
            result += "-" * 50 + "\n\n"

        for index, tab in enumerate(all_tabs):
            level = tab.level
            indent = "  " * level

            if is_single_tab:
                result += "**Default Tab:**\n"
                result += f"- Tab ID: {tab.tab_id}\n"
                result += f"- Title: {tab.title or '(Untitled)'}\n"
            else:
                prefix = "└─ " if level > 0 else ""
                result += f'{indent}{prefix}**Tab {index + 1}:** "{tab.title}"\n'
                result += f"{indent}   - ID: {tab.tab_id}\n"
                result += f"{indent}   - Index: {tab.index if tab.index is not None else 'N/A'}\n"

                if tab.parent_tab_id:
                    result += f"{indent}   - Parent Tab ID: {tab.parent_tab_id}\n"

            if include_content and tab.text_length is not None:
                content_info = (
                    f"{tab.text_length:,} characters" if tab.text_length > 0 else "Empty"
                )
                result += f"{indent}   - Content: {content_info}\n"

            if not is_single_tab:
                result += "\n"

        if not is_single_tab:
            result += "\nTip: Use tab IDs with other tools to target specific tabs."

        return result

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error listing tabs for doc {document_id}: {error_message}")
        if "404" in error_message:
            raise ToolError(f"Document not found (ID: {document_id}).")
        if "403" in error_message:
            raise ToolError(f"Permission denied for document (ID: {document_id}).")
        raise ToolError(f"Failed to list tabs: {error_message}")


def append_to_document(
    document_id: str,
    text_to_append: str,
    add_newline_if_needed: bool = True,
    tab_id: str | None = None,
) -> str:
    """
    Append text to the end of a Google Document.

    Args:
        document_id: The ID of the Google Document
        text_to_append: The text to add to the end
        add_newline_if_needed: Whether to add a newline before appended text
        tab_id: Specific tab ID to append to

    Returns:
        Success message

    Raises:
        UserError: For permission/not found errors
    """
    docs = get_docs_client()
    log(
        f"Appending to Google Doc: {document_id}"
        f"{f' (tab: {tab_id})' if tab_id else ''}"
    )

    try:
        needs_tabs_content = bool(tab_id)

        doc_info = (
            docs.documents()
            .get(
                documentId=document_id,
                includeTabsContent=needs_tabs_content,
                fields="tabs" if needs_tabs_content else "body(content(endIndex)),documentStyle(pageSize)",
            )
            .execute()
        )

        end_index = 1
        body_content: list = []

        if tab_id:
            target_tab = helpers.find_tab_by_id(doc_info, tab_id)
            if not target_tab:
                raise ToolError(f'Tab with ID "{tab_id}" not found in document.')
            if not target_tab.get("documentTab"):
                raise ToolError(
                    f'Tab "{tab_id}" does not have content (may not be a document tab).'
                )
            body_content = (
                target_tab.get("documentTab", {}).get("body", {}).get("content", [])
            )
        else:
            body_content = doc_info.get("body", {}).get("content", [])

        if body_content:
            last_element = body_content[-1]
            if last_element.get("endIndex"):
                end_index = last_element["endIndex"] - 1

        text_to_insert = (
            ("\n" if add_newline_if_needed and end_index > 1 else "") + text_to_append
        )

        if not text_to_insert:
            return "Nothing to append."

        location: dict[str, Any] = {"index": end_index}
        if tab_id:
            location["tabId"] = tab_id

        request = {"insertText": {"location": location, "text": text_to_insert}}
        helpers.execute_batch_update_sync(docs, document_id, [request])

        log(
            f"Successfully appended to doc: {document_id}"
            f"{f' (tab: {tab_id})' if tab_id else ''}"
        )
        return (
            f"Successfully appended text to "
            f"{f'tab {tab_id} in ' if tab_id else ''}document {document_id}."
        )

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error appending to doc {document_id}: {error_message}")
        raise ToolError(f"Failed to append to doc: {error_message}")


def insert_text(
    document_id: str,
    text_to_insert: str,
    index: int,
    tab_id: str | None = None,
) -> str:
    """
    Insert text at a specific index in a document.

    Args:
        document_id: The ID of the Google Document
        text_to_insert: The text to insert
        index: The index where text should be inserted (1-based)
        tab_id: Specific tab ID to insert into

    Returns:
        Success message

    Raises:
        UserError: For permission/not found errors
    """
    docs = get_docs_client()
    log(
        f"Inserting text in doc {document_id} at index {index}"
        f"{f' (tab: {tab_id})' if tab_id else ''}"
    )

    try:
        if tab_id:
            doc_info = (
                docs.documents()
                .get(
                    documentId=document_id,
                    includeTabsContent=True,
                    fields="tabs(tabProperties,documentTab)",
                )
                .execute()
            )
            target_tab = helpers.find_tab_by_id(doc_info, tab_id)
            if not target_tab:
                raise ToolError(f'Tab with ID "{tab_id}" not found in document.')
            if not target_tab.get("documentTab"):
                raise ToolError(
                    f'Tab "{tab_id}" does not have content (may not be a document tab).'
                )

            location: dict[str, Any] = {"index": index, "tabId": tab_id}
            request = {"insertText": {"location": location, "text": text_to_insert}}
            helpers.execute_batch_update_sync(docs, document_id, [request])
        else:
            helpers.insert_text(docs, document_id, text_to_insert, index)

        return (
            f"Successfully inserted text at index {index}"
            f"{f' in tab {tab_id}' if tab_id else ''}."
        )

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error inserting text in doc {document_id}: {error_message}")
        raise ToolError(f"Failed to insert text: {error_message}")


def delete_range(
    document_id: str,
    start_index: int,
    end_index: int,
    tab_id: str | None = None,
) -> str:
    """
    Delete content within a specified range.

    Args:
        document_id: The ID of the Google Document
        start_index: Starting index (inclusive, 1-based)
        end_index: Ending index (exclusive)
        tab_id: Specific tab ID to delete from

    Returns:
        Success message

    Raises:
        UserError: For permission/not found errors or invalid range
    """
    docs = get_docs_client()
    log(
        f"Deleting range {start_index}-{end_index} in doc {document_id}"
        f"{f' (tab: {tab_id})' if tab_id else ''}"
    )

    if end_index <= start_index:
        raise ToolError("End index must be greater than start index for deletion.")

    try:
        if tab_id:
            doc_info = (
                docs.documents()
                .get(
                    documentId=document_id,
                    includeTabsContent=True,
                    fields="tabs(tabProperties,documentTab)",
                )
                .execute()
            )
            target_tab = helpers.find_tab_by_id(doc_info, tab_id)
            if not target_tab:
                raise ToolError(f'Tab with ID "{tab_id}" not found in document.')
            if not target_tab.get("documentTab"):
                raise ToolError(
                    f'Tab "{tab_id}" does not have content (may not be a document tab).'
                )

        range_dict: dict[str, Any] = {
            "startIndex": start_index,
            "endIndex": end_index,
        }
        if tab_id:
            range_dict["tabId"] = tab_id

        request = {"deleteContentRange": {"range": range_dict}}
        helpers.execute_batch_update_sync(docs, document_id, [request])

        return (
            f"Successfully deleted content in range {start_index}-{end_index}"
            f"{f' in tab {tab_id}' if tab_id else ''}."
        )

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error deleting range in doc {document_id}: {error_message}")
        raise ToolError(f"Failed to delete range: {error_message}")


def apply_text_style(
    document_id: str,
    style: TextStyleArgs,
    start_index: int | None = None,
    end_index: int | None = None,
    text_to_find: str | None = None,
    match_instance: int = 1,
) -> str:
    """
    Apply text formatting to a range or found text.

    Args:
        document_id: The ID of the Google Document
        style: Text style arguments to apply
        start_index: Starting index (if targeting by range)
        end_index: Ending index (if targeting by range)
        text_to_find: Text to find and format (if targeting by text)
        match_instance: Which instance of text to target (default 1)

    Returns:
        Success message

    Raises:
        UserError: For permission/not found errors
    """
    docs = get_docs_client()
    log(
        f"Applying text style in doc {document_id}. "
        f"Target: range={start_index}-{end_index}, text='{text_to_find}'"
    )

    try:
        # Determine target range
        if text_to_find:
            text_range = helpers.find_text_range(
                docs, document_id, text_to_find, match_instance
            )
            if not text_range:
                raise ToolError(
                    f'Could not find instance {match_instance} of text "{text_to_find}".'
                )
            start_index = text_range.start_index
            end_index = text_range.end_index
            log(
                f'Found text "{text_to_find}" (instance {match_instance}) '
                f"at range {start_index}-{end_index}"
            )

        if start_index is None or end_index is None:
            raise ToolError("Target range could not be determined.")
        if end_index <= start_index:
            raise ToolError("End index must be greater than start index for styling.")

        # Build the request
        request_info = helpers.build_update_text_style_request(
            start_index, end_index, style
        )
        if not request_info:
            return "No valid text styling options were provided."

        helpers.execute_batch_update_sync(docs, document_id, [request_info["request"]])
        return (
            f"Successfully applied text style ({', '.join(request_info['fields'])}) "
            f"to range {start_index}-{end_index}."
        )

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error applying text style in doc {document_id}: {error_message}")
        raise ToolError(f"Failed to apply text style: {error_message}")


def apply_paragraph_style(
    document_id: str,
    style: ParagraphStyleArgs,
    start_index: int | None = None,
    end_index: int | None = None,
    text_to_find: str | None = None,
    match_instance: int = 1,
    index_within_paragraph: int | None = None,
) -> str:
    """
    Apply paragraph formatting to a paragraph.

    Args:
        document_id: The ID of the Google Document
        style: Paragraph style arguments to apply
        start_index: Starting index (if targeting by range)
        end_index: Ending index (if targeting by range)
        text_to_find: Text to find (styles paragraph containing it)
        match_instance: Which instance of text to target (default 1)
        index_within_paragraph: Index within target paragraph

    Returns:
        Success message

    Raises:
        UserError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Applying paragraph style to document {document_id}")

    try:
        # Determine target range
        if text_to_find:
            log(f'Finding text "{text_to_find}" (instance {match_instance})')
            text_range = helpers.find_text_range(
                docs, document_id, text_to_find, match_instance
            )
            if not text_range:
                raise ToolError(f'Could not find "{text_to_find}" in the document.')

            log(
                f"Found text at range {text_range.start_index}-{text_range.end_index}, "
                f"now locating containing paragraph"
            )

            paragraph_range = helpers.get_paragraph_range(
                docs, document_id, text_range.start_index
            )
            if not paragraph_range:
                raise ToolError(
                    "Found the text but could not determine the paragraph boundaries."
                )

            start_index = paragraph_range.start_index
            end_index = paragraph_range.end_index
            log(f"Text is contained within paragraph at range {start_index}-{end_index}")

        elif index_within_paragraph is not None:
            log(f"Finding paragraph containing index {index_within_paragraph}")
            paragraph_range = helpers.get_paragraph_range(
                docs, document_id, index_within_paragraph
            )
            if not paragraph_range:
                raise ToolError(
                    f"Could not find paragraph containing index {index_within_paragraph}."
                )

            start_index = paragraph_range.start_index
            end_index = paragraph_range.end_index
            log(f"Located paragraph at range {start_index}-{end_index}")

        if start_index is None or end_index is None:
            raise ToolError(
                "Could not determine target paragraph range from the provided information."
            )
        if end_index <= start_index:
            raise ToolError(
                f"Invalid paragraph range: end index ({end_index}) must be "
                f"greater than start index ({start_index})."
            )

        # Build and apply the paragraph style request
        log(f"Building paragraph style request for range {start_index}-{end_index}")
        request_info = helpers.build_update_paragraph_style_request(
            start_index, end_index, style
        )

        if not request_info:
            return "No valid paragraph styling options were provided."

        log(f"Applying styles: {', '.join(request_info['fields'])}")
        helpers.execute_batch_update_sync(docs, document_id, [request_info["request"]])

        return (
            f"Successfully applied paragraph styles "
            f"({', '.join(request_info['fields'])}) to the paragraph."
        )

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error applying paragraph style in doc {document_id}: {error_message}")
        raise ToolError(f"Failed to apply paragraph style: {error_message}")


def insert_table(document_id: str, rows: int, columns: int, index: int) -> str:
    """
    Insert a new table into a document.

    Args:
        document_id: The ID of the Google Document
        rows: Number of rows
        columns: Number of columns
        index: Position to insert the table (1-based)

    Returns:
        Success message

    Raises:
        UserError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Inserting {rows}x{columns} table in doc {document_id} at index {index}")

    try:
        helpers.create_table(docs, document_id, rows, columns, index)
        return f"Successfully inserted a {rows}x{columns} table at index {index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error inserting table in doc {document_id}: {error_message}")
        raise ToolError(f"Failed to insert table: {error_message}")


def insert_page_break(document_id: str, index: int) -> str:
    """
    Insert a page break at a specific position.

    Args:
        document_id: The ID of the Google Document
        index: Position to insert the page break (1-based)

    Returns:
        Success message

    Raises:
        UserError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Inserting page break in doc {document_id} at index {index}")

    try:
        request = {"insertPageBreak": {"location": {"index": index}}}
        helpers.execute_batch_update_sync(docs, document_id, [request])
        return f"Successfully inserted page break at index {index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error inserting page break in doc {document_id}: {error_message}")
        raise ToolError(f"Failed to insert page break: {error_message}")


def insert_image_from_url(
    document_id: str,
    image_url: str,
    index: int,
    width: float | None = None,
    height: float | None = None,
) -> str:
    """
    Insert an inline image from a URL.

    Args:
        document_id: The ID of the Google Document
        image_url: Publicly accessible URL to the image
        index: Position to insert the image (1-based)
        width: Optional width in points
        height: Optional height in points

    Returns:
        Success message

    Raises:
        UserError: For permission/not found errors or invalid URL
    """
    docs = get_docs_client()
    log(f"Inserting image from URL {image_url} at index {index} in doc {document_id}")

    try:
        helpers.insert_inline_image(docs, document_id, image_url, index, width, height)

        size_info = ""
        if width and height:
            size_info = f" with size {width}x{height}pt"

        return f"Successfully inserted image from URL at index {index}{size_info}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error inserting image in doc {document_id}: {error_message}")
        raise ToolError(f"Failed to insert image: {error_message}")


def bulk_update_document(
    document_id: str, operations: list[dict], default_tab_id: str | None = None
) -> str:
    """
    Execute multiple document operations in batched API calls.

    Args:
        document_id: Target document ID
        operations: List of operation dictionaries with 'type' field
        default_tab_id: Optional default tab for operations without explicit tab_id

    Returns:
        Human-readable summary of operations performed

    Raises:
        ToolError: If operations are invalid or execution fails
    """
    docs = get_docs_client()
    log(
        f"Processing bulk update with {len(operations)} operations for doc {document_id}"
    )

    if not operations:
        return "No operations to execute."

    if len(operations) > 500:
        raise ToolError(
            f"Too many operations ({len(operations)}). Maximum is 500 operations per call."
        )

    try:
        # Step 1: Determine if we need to fetch the document for text-finding operations
        needs_document = any(
            op.get("text_to_find") or op.get("index_within_paragraph")
            for op in operations
        )

        document = None
        if needs_document:
            log(f"Fetching document {document_id} for text-finding operations")
            document = (
                docs.documents()
                .get(documentId=document_id, includeTabsContent=True, fields="*")
                .execute()
            )

        # Step 2: Parse and validate operations, preparing requests
        requests = []
        operation_summaries = []

        for i, op_dict in enumerate(operations):
            op_type = op_dict.get("type")
            if not op_type:
                raise ToolError(f"Operation {i + 1} missing 'type' field")

            try:
                if op_type == "insert_text":
                    request = _prepare_insert_text_request(op_dict, default_tab_id)
                    requests.append(request)
                    operation_summaries.append(f"insert_text at index {op_dict.get('index', 1)}")

                elif op_type == "delete_range":
                    request = _prepare_delete_range_request(op_dict, default_tab_id)
                    requests.append(request)
                    operation_summaries.append(
                        f"delete_range {op_dict.get('start_index')}-{op_dict.get('end_index')}"
                    )

                elif op_type == "apply_text_style":
                    request = _prepare_apply_text_style_request(
                        op_dict, document, default_tab_id
                    )
                    requests.append(request)
                    operation_summaries.append("apply_text_style")

                elif op_type == "apply_paragraph_style":
                    request = _prepare_apply_paragraph_style_request(
                        op_dict, document, default_tab_id
                    )
                    requests.append(request)
                    operation_summaries.append("apply_paragraph_style")

                elif op_type == "insert_table":
                    request = _prepare_insert_table_request(op_dict)
                    requests.append(request)
                    operation_summaries.append(
                        f"insert_table {op_dict.get('rows')}x{op_dict.get('columns')}"
                    )

                elif op_type == "insert_page_break":
                    request = _prepare_insert_page_break_request(op_dict)
                    requests.append(request)
                    operation_summaries.append(f"insert_page_break at index {op_dict.get('index')}")

                elif op_type == "insert_image_from_url":
                    request = _prepare_insert_image_request(op_dict)
                    requests.append(request)
                    operation_summaries.append(f"insert_image at index {op_dict.get('index')}")

                elif op_type == "create_bullet_list":
                    request = _prepare_create_bullet_list_request(op_dict, default_tab_id)
                    requests.append(request)
                    operation_summaries.append(f"create_bullet_list {op_dict.get('list_type', 'UNORDERED')}")

                elif op_type == "replace_all_text":
                    request = _prepare_replace_all_text_request(op_dict, default_tab_id)
                    requests.append(request)
                    operation_summaries.append(f"replace_all_text '{op_dict.get('find_text')}'")

                elif op_type == "insert_table_row":
                    request = _prepare_insert_table_row_request(op_dict)
                    requests.append(request)
                    operation_summaries.append("insert_table_row")

                elif op_type == "delete_table_row":
                    request = _prepare_delete_table_row_request(op_dict)
                    requests.append(request)
                    operation_summaries.append("delete_table_row")

                elif op_type == "insert_table_column":
                    request = _prepare_insert_table_column_request(op_dict)
                    requests.append(request)
                    operation_summaries.append("insert_table_column")

                elif op_type == "delete_table_column":
                    request = _prepare_delete_table_column_request(op_dict)
                    requests.append(request)
                    operation_summaries.append("delete_table_column")

                elif op_type == "update_table_cell_style":
                    request = _prepare_update_table_cell_style_request(op_dict)
                    if request:  # May be None if no styles provided
                        requests.append(request)
                        operation_summaries.append("update_table_cell_style")

                elif op_type == "merge_table_cells":
                    request = _prepare_merge_table_cells_request(op_dict)
                    requests.append(request)
                    operation_summaries.append("merge_table_cells")

                elif op_type == "unmerge_table_cells":
                    request = _prepare_unmerge_table_cells_request(op_dict)
                    requests.append(request)
                    operation_summaries.append("unmerge_table_cells")

                elif op_type == "create_named_range":
                    request = _prepare_create_named_range_request(op_dict, default_tab_id)
                    requests.append(request)
                    operation_summaries.append(f"create_named_range '{op_dict.get('name')}'")

                elif op_type == "delete_named_range":
                    request = _prepare_delete_named_range_request(op_dict)
                    requests.append(request)
                    operation_summaries.append("delete_named_range")

                elif op_type == "insert_footnote":
                    request = _prepare_insert_footnote_request(op_dict)
                    requests.append(request)
                    operation_summaries.append("insert_footnote")

                elif op_type == "insert_table_of_contents":
                    request = _prepare_insert_table_of_contents_request(op_dict)
                    requests.append(request)
                    operation_summaries.append("insert_table_of_contents")

                elif op_type == "insert_horizontal_rule":
                    request = _prepare_insert_horizontal_rule_request(op_dict)
                    requests.append(request)
                    operation_summaries.append("insert_horizontal_rule")

                elif op_type == "insert_section_break":
                    request = _prepare_insert_section_break_request(op_dict)
                    requests.append(request)
                    operation_summaries.append(f"insert_section_break {op_dict.get('section_type', 'CONTINUOUS')}")

                else:
                    raise ToolError(
                        f"Unknown operation type '{op_type}' in operation {i + 1}"
                    )

            except Exception as e:
                raise ToolError(f"Error preparing operation {i + 1} ({op_type}): {str(e)}")

        # Step 3: Chunk requests into batches of 50
        request_chunks = helpers.chunk_requests(requests, chunk_size=50)
        log(
            f"Executing {len(requests)} requests in {len(request_chunks)} batch(es)"
        )

        # Step 4: Execute batches sequentially
        for chunk_idx, chunk in enumerate(request_chunks):
            log(f"Executing batch {chunk_idx + 1}/{len(request_chunks)} with {len(chunk)} requests")
            helpers.execute_batch_update_sync(docs, document_id, chunk)

        # Step 5: Return summary
        summary_lines = [
            f"✓ Successfully executed {len(operations)} operations in {len(request_chunks)} batch(es):",
            "",
        ]

        # Group operation summaries by type
        operation_counts: dict[str, int] = {}
        for summary in operation_summaries:
            op_type = summary.split()[0]
            operation_counts[op_type] = operation_counts.get(op_type, 0) + 1

        for op_type, count in sorted(operation_counts.items()):
            summary_lines.append(f"  - {count}× {op_type}")

        return "\n".join(summary_lines)

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error in bulk update for doc {document_id}: {error_message}")
        raise ToolError(f"Bulk update failed: {error_message}")


# --- Helper functions for preparing bulk operation requests ---


def _prepare_insert_text_request(op_dict: dict, default_tab_id: str | None) -> dict:
    """Prepare insertText request from operation dict."""
    text = op_dict.get("text", "")
    index = op_dict.get("index", 1)
    tab_id = op_dict.get("tab_id", default_tab_id)

    location: dict[str, Any] = {"index": index}
    if tab_id:
        location["tabId"] = tab_id

    return {"insertText": {"text": text, "location": location}}


def _prepare_delete_range_request(op_dict: dict, default_tab_id: str | None) -> dict:
    """Prepare deleteContentRange request from operation dict."""
    start_index = op_dict.get("start_index", 1)
    end_index = op_dict.get("end_index", 1)
    tab_id = op_dict.get("tab_id", default_tab_id)

    if end_index <= start_index:
        raise ToolError(
            f"Invalid range: end_index ({end_index}) must be greater than start_index ({start_index})"
        )

    range_obj: dict[str, Any] = {"startIndex": start_index, "endIndex": end_index}
    if tab_id:
        range_obj["tabId"] = tab_id

    return {"deleteContentRange": {"range": range_obj}}


def _prepare_apply_text_style_request(
    op_dict: dict, document: dict | None, default_tab_id: str | None
) -> dict:
    """Prepare updateTextStyle request from operation dict."""
    # Determine the range to apply styling to
    start_index = op_dict.get("start_index")
    end_index = op_dict.get("end_index")
    text_to_find = op_dict.get("text_to_find")
    match_instance = op_dict.get("match_instance", 1)

    if text_to_find:
        # Text-based targeting - find the text first
        if not document:
            raise ToolError("Document data required for text-finding operations")

        text_range = helpers.find_text_range(
            get_docs_client(), document["documentId"], text_to_find, match_instance
        )
        if not text_range:
            raise ToolError(
                f"Text '{text_to_find}' (instance {match_instance}) not found in document"
            )
        start_index = text_range.start_index
        end_index = text_range.end_index
    elif start_index is None or end_index is None:
        raise ToolError(
            "Either (start_index, end_index) or text_to_find must be provided for apply_text_style"
        )

    # Build text style args from operation dict
    style_args = TextStyleArgs(
        bold=op_dict.get("bold"),
        italic=op_dict.get("italic"),
        underline=op_dict.get("underline"),
        strikethrough=op_dict.get("strikethrough"),
        font_size=op_dict.get("font_size"),
        font_family=op_dict.get("font_family"),
        foreground_color=op_dict.get("foreground_color"),
        background_color=op_dict.get("background_color"),
        link_url=op_dict.get("link_url"),
    )

    tab_id = op_dict.get("tab_id", default_tab_id)
    result = helpers.build_update_text_style_request(
        start_index, end_index, style_args
    )
    request = result["request"]

    # Add tab_id to the range if specified
    if tab_id:
        request["updateTextStyle"]["range"]["tabId"] = tab_id

    return request


def _prepare_apply_paragraph_style_request(
    op_dict: dict, document: dict | None, default_tab_id: str | None
) -> dict:
    """Prepare updateParagraphStyle request from operation dict."""
    # Determine the range to apply styling to
    start_index = op_dict.get("start_index")
    end_index = op_dict.get("end_index")
    text_to_find = op_dict.get("text_to_find")
    match_instance = op_dict.get("match_instance", 1)
    index_within_paragraph = op_dict.get("index_within_paragraph")

    if text_to_find:
        # Text-based targeting
        if not document:
            raise ToolError("Document data required for text-finding operations")

        text_range = helpers.find_text_range(
            get_docs_client(), document["documentId"], text_to_find, match_instance
        )
        if not text_range:
            raise ToolError(
                f"Text '{text_to_find}' (instance {match_instance}) not found in document"
            )

        # Find paragraph containing the text
        tab_id = op_dict.get("tab_id", default_tab_id)
        para_range = helpers.get_paragraph_range_from_document(
            document, text_range.start_index, tab_id
        )
        if not para_range:
            raise ToolError(
                f"Could not find paragraph containing text '{text_to_find}'"
            )
        start_index = para_range.start_index
        end_index = para_range.end_index

    elif index_within_paragraph is not None:
        # Index-based targeting
        if not document:
            raise ToolError("Document data required for index_within_paragraph operations")

        tab_id = op_dict.get("tab_id", default_tab_id)
        para_range = helpers.get_paragraph_range_from_document(
            document, index_within_paragraph, tab_id
        )
        if not para_range:
            raise ToolError(
                f"Could not find paragraph containing index {index_within_paragraph}"
            )
        start_index = para_range.start_index
        end_index = para_range.end_index

    elif start_index is None or end_index is None:
        raise ToolError(
            "Either (start_index, end_index), text_to_find, or index_within_paragraph "
            "must be provided for apply_paragraph_style"
        )

    # Build paragraph style args from operation dict
    style_args = ParagraphStyleArgs(
        alignment=op_dict.get("alignment"),
        indent_start=op_dict.get("indent_start"),
        indent_end=op_dict.get("indent_end"),
        space_above=op_dict.get("space_above"),
        space_below=op_dict.get("space_below"),
        named_style_type=op_dict.get("named_style_type"),
        keep_with_next=op_dict.get("keep_with_next"),
    )

    tab_id = op_dict.get("tab_id", default_tab_id)
    result = helpers.build_update_paragraph_style_request(
        start_index, end_index, style_args
    )
    request = result["request"]

    # Add tab_id to the range if specified
    if tab_id:
        request["updateParagraphStyle"]["range"]["tabId"] = tab_id

    return request


def _prepare_insert_table_request(op_dict: dict) -> dict:
    """Prepare insertTable request from operation dict."""
    rows = op_dict.get("rows", 1)
    columns = op_dict.get("columns", 1)
    index = op_dict.get("index", 1)

    if rows < 1 or columns < 1:
        raise ToolError(f"Table must have at least 1 row and 1 column (got {rows}x{columns})")

    return {
        "insertTable": {
            "rows": rows,
            "columns": columns,
            "location": {"index": index},
        }
    }


def _prepare_insert_page_break_request(op_dict: dict) -> dict:
    """Prepare insertPageBreak request from operation dict."""
    index = op_dict.get("index", 1)
    return {"insertPageBreak": {"location": {"index": index}}}


def _prepare_insert_image_request(op_dict: dict) -> dict:
    """Prepare insertInlineImage request from operation dict."""
    image_url = op_dict.get("image_url", "")
    index = op_dict.get("index", 1)
    width = op_dict.get("width")
    height = op_dict.get("height")

    if not image_url:
        raise ToolError("image_url is required for insert_image_from_url operation")

    # Validate URL is accessible (imported from helpers)
    helpers._validate_image_url(image_url)

    # If this is a Google Drive URL, ensure it has public permissions
    if 'drive.google.com' in image_url:
        # Extract file ID from various Drive URL formats
        file_id_match = re.search(r'[?&]id=([^&]+)', image_url)
        if file_id_match:
            file_id = file_id_match.group(1)
            log(f"Setting public permissions for Google Drive file {file_id}")

            try:
                drive = get_drive_client()
                # Make the file publicly readable so Google Docs can access it
                permission = {
                    "type": "anyone",
                    "role": "reader"
                }
                drive.permissions().create(
                    fileId=file_id,
                    body=permission
                ).execute()
                log(f"Successfully set public permissions for Drive file {file_id}")
            except Exception as e:
                log(f"Warning: Could not set public permissions for Drive file {file_id}: {e}")
                raise ToolError(
                    f"Failed to set public permissions on Google Drive file {file_id}. "
                    "Please ensure the file is publicly accessible or share it with 'Anyone with the link'."
                )

    location = {"index": index}
    uri = image_url

    object_size = None
    if width is not None and height is not None:
        object_size = {
            "height": {"magnitude": height, "unit": "PT"},
            "width": {"magnitude": width, "unit": "PT"},
        }

    request: dict[str, Any] = {
        "insertInlineImage": {"uri": uri, "location": location}
    }

    if object_size:
        request["insertInlineImage"]["objectSize"] = object_size

    return request


# --- New Document Operations ---


def create_bullet_list(
    document_id: str,
    start_index: int,
    end_index: int,
    list_type: str = "UNORDERED",
    nesting_level: int = 0,
    tab_id: str | None = None,
) -> str:
    """
    Create a bulleted or numbered list from a range of paragraphs.

    Args:
        document_id: The ID of the Google Document
        start_index: Starting index of the range (inclusive, 1-based)
        end_index: Ending index of the range (exclusive)
        list_type: Type of list ("UNORDERED", "ORDERED_DECIMAL", etc.)
        nesting_level: Nesting level (0-8)
        tab_id: Specific tab ID to target

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Creating {list_type} list in range {start_index}-{end_index}")

    try:
        request = helpers.build_create_paragraph_bullets_request(
            start_index, end_index, list_type, nesting_level, tab_id
        )

        helpers.execute_batch_update_sync(docs, document_id, [request])

        return f"Successfully created {list_type} list at range {start_index}-{end_index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error creating list: {error_message}")
        if "404" in error_message:
            raise ToolError("Document not found. Check the document ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        raise ToolError(f"Failed to create list: {error_message}")


def replace_all_text(
    document_id: str,
    find_text: str,
    replace_text: str,
    match_case: bool = True,
    tab_id: str | None = None,
) -> str:
    """
    Find and replace all instances of text in the document.

    Args:
        document_id: The ID of the Google Document
        find_text: Text to find
        replace_text: Text to replace it with
        match_case: Whether to match case when finding
        tab_id: Optional tab ID to limit replacement to specific tab

    Returns:
        Success message with replacement count

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Replacing all '{find_text}' with '{replace_text}' (match_case={match_case})")

    try:
        request = helpers.build_replace_all_text_request(
            find_text, replace_text, match_case, tab_id
        )

        result = helpers.execute_batch_update_sync(docs, document_id, [request])

        # Extract replacement count from response if available
        replacements = 0
        if result and "replies" in result:
            for reply in result.get("replies", []):
                if "replaceAllText" in reply:
                    replacements = reply["replaceAllText"].get("occurrencesChanged", 0)

        return f"Successfully replaced {replacements} occurrence(s) of '{find_text}' with '{replace_text}'."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error replacing text: {error_message}")
        if "404" in error_message:
            raise ToolError("Document not found. Check the document ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        raise ToolError(f"Failed to replace text: {error_message}")


def insert_table_row(
    document_id: str,
    table_start_index: int,
    row_index: int,
    insert_below: bool = False,
) -> str:
    """
    Insert a new row into an existing table.

    Args:
        document_id: The ID of the Google Document
        table_start_index: The index where the table starts
        row_index: The row index (0-based) where to insert
        insert_below: True to insert below the row, False to insert above

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Inserting table row at table {table_start_index}, row {row_index}")

    try:
        request = helpers.build_insert_table_row_request(
            table_start_index, row_index, insert_below
        )

        helpers.execute_batch_update_sync(docs, document_id, [request])

        position = "below" if insert_below else "above"
        return f"Successfully inserted row {position} row {row_index} in table at index {table_start_index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error inserting table row: {error_message}")
        if "404" in error_message:
            raise ToolError("Document or table not found. Check the document ID and table index.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        if "400" in error_message:
            raise ToolError(
                f"Invalid request: {error_message}. Check that the table exists at index {table_start_index} "
                f"and row index {row_index} is valid."
            )
        raise ToolError(f"Failed to insert table row: {error_message}")


def delete_table_row(
    document_id: str,
    table_start_index: int,
    row_index: int,
) -> str:
    """
    Delete a row from an existing table.

    Args:
        document_id: The ID of the Google Document
        table_start_index: The index where the table starts
        row_index: The row index (0-based) to delete

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Deleting table row at table {table_start_index}, row {row_index}")

    try:
        request = helpers.build_delete_table_row_request(table_start_index, row_index)

        helpers.execute_batch_update_sync(docs, document_id, [request])

        return f"Successfully deleted row {row_index} from table at index {table_start_index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error deleting table row: {error_message}")
        if "404" in error_message:
            raise ToolError("Document or table not found. Check the document ID and table index.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        if "400" in error_message:
            raise ToolError(
                f"Invalid request: {error_message}. Check that the table exists at index {table_start_index} "
                f"and row index {row_index} is valid."
            )
        raise ToolError(f"Failed to delete table row: {error_message}")


def insert_table_column(
    document_id: str,
    table_start_index: int,
    column_index: int,
    insert_right: bool = False,
) -> str:
    """
    Insert a new column into an existing table.

    Args:
        document_id: The ID of the Google Document
        table_start_index: The index where the table starts
        column_index: The column index (0-based) where to insert
        insert_right: True to insert right, False to insert left

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Inserting table column at table {table_start_index}, column {column_index}")

    try:
        request = helpers.build_insert_table_column_request(
            table_start_index, column_index, insert_right
        )

        helpers.execute_batch_update_sync(docs, document_id, [request])

        position = "right of" if insert_right else "left of"
        return f"Successfully inserted column {position} column {column_index} in table at index {table_start_index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error inserting table column: {error_message}")
        if "404" in error_message:
            raise ToolError("Document or table not found. Check the document ID and table index.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        if "400" in error_message:
            raise ToolError(
                f"Invalid request: {error_message}. Check that the table exists at index {table_start_index} "
                f"and column index {column_index} is valid."
            )
        raise ToolError(f"Failed to insert table column: {error_message}")


def delete_table_column(
    document_id: str,
    table_start_index: int,
    column_index: int,
) -> str:
    """
    Delete a column from an existing table.

    Args:
        document_id: The ID of the Google Document
        table_start_index: The index where the table starts
        column_index: The column index (0-based) to delete

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Deleting table column at table {table_start_index}, column {column_index}")

    try:
        request = helpers.build_delete_table_column_request(table_start_index, column_index)

        helpers.execute_batch_update_sync(docs, document_id, [request])

        return f"Successfully deleted column {column_index} from table at index {table_start_index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error deleting table column: {error_message}")
        if "404" in error_message:
            raise ToolError("Document or table not found. Check the document ID and table index.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        if "400" in error_message:
            raise ToolError(
                f"Invalid request: {error_message}. Check that the table exists at index {table_start_index} "
                f"and column index {column_index} is valid."
            )
        raise ToolError(f"Failed to delete table column: {error_message}")


def update_table_cell_style(
    document_id: str,
    table_start_index: int,
    row_index: int,
    column_index: int,
    background_color: str | None = None,
    padding_top: float | None = None,
    padding_bottom: float | None = None,
    padding_left: float | None = None,
    padding_right: float | None = None,
    border_top_color: str | None = None,
    border_top_width: float | None = None,
    border_bottom_color: str | None = None,
    border_bottom_width: float | None = None,
    border_left_color: str | None = None,
    border_left_width: float | None = None,
    border_right_color: str | None = None,
    border_right_width: float | None = None,
) -> str:
    """
    Style a table cell (background, padding, borders).

    Args:
        document_id: The ID of the Google Document
        table_start_index: The index where the table starts
        row_index: Row index (0-based)
        column_index: Column index (0-based)
        background_color: Background color hex (e.g., "#FF0000")
        padding_top: Top padding in points
        padding_bottom: Bottom padding in points
        padding_left: Left padding in points
        padding_right: Right padding in points
        border_top_color: Top border color hex
        border_top_width: Top border width in points
        border_bottom_color: Bottom border color hex
        border_bottom_width: Bottom border width in points
        border_left_color: Left border color hex
        border_left_width: Left border width in points
        border_right_color: Right border color hex
        border_right_width: Right border width in points

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Styling table cell at table {table_start_index}, row {row_index}, column {column_index}")

    try:
        request = helpers.build_update_table_cell_style_request(
            table_start_index,
            row_index,
            column_index,
            background_color,
            padding_top,
            padding_bottom,
            padding_left,
            padding_right,
            border_top_color,
            border_top_width,
            border_bottom_color,
            border_bottom_width,
            border_left_color,
            border_left_width,
            border_right_color,
            border_right_width,
        )

        if request is None:
            return "No style properties provided. No changes made."

        helpers.execute_batch_update_sync(docs, document_id, [request])

        return f"Successfully styled cell at row {row_index}, column {column_index} in table at index {table_start_index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error styling table cell: {error_message}")
        if "404" in error_message:
            raise ToolError("Document or table not found. Check the document ID and table index.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        if "400" in error_message:
            raise ToolError(
                f"Invalid request: {error_message}. Check that the table exists at index {table_start_index} "
                f"and cell position ({row_index}, {column_index}) is valid."
            )
        raise ToolError(f"Failed to style table cell: {error_message}")


def merge_table_cells(
    document_id: str,
    table_start_index: int,
    start_row: int,
    start_column: int,
    row_span: int,
    column_span: int,
) -> str:
    """
    Merge table cells.

    Args:
        document_id: The ID of the Google Document
        table_start_index: The index where the table starts
        start_row: Starting row index (0-based)
        start_column: Starting column index (0-based)
        row_span: Number of rows to merge
        column_span: Number of columns to merge

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Merging table cells at table {table_start_index}, from ({start_row},{start_column}) spanning {row_span}x{column_span}")

    try:
        request = helpers.build_merge_table_cells_request(
            table_start_index, start_row, start_column, row_span, column_span
        )

        helpers.execute_batch_update_sync(docs, document_id, [request])

        return f"Successfully merged {row_span}x{column_span} cells starting at ({start_row},{start_column}) in table at index {table_start_index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error merging table cells: {error_message}")
        if "404" in error_message:
            raise ToolError("Document or table not found. Check the document ID and table index.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        if "400" in error_message:
            raise ToolError(
                f"Invalid request: {error_message}. Check that the table exists at index {table_start_index} "
                f"and the merge range is valid."
            )
        raise ToolError(f"Failed to merge table cells: {error_message}")


def unmerge_table_cells(
    document_id: str,
    table_start_index: int,
    row_index: int,
    column_index: int,
) -> str:
    """
    Unmerge previously merged table cells.

    Args:
        document_id: The ID of the Google Document
        table_start_index: The index where the table starts
        row_index: Row index (0-based) of the merged cell
        column_index: Column index (0-based) of the merged cell

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Unmerging table cells at table {table_start_index}, cell ({row_index},{column_index})")

    try:
        request = helpers.build_unmerge_table_cells_request(
            table_start_index, row_index, column_index
        )

        helpers.execute_batch_update_sync(docs, document_id, [request])

        return f"Successfully unmerged cells at ({row_index},{column_index}) in table at index {table_start_index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error unmerging table cells: {error_message}")
        if "404" in error_message:
            raise ToolError("Document or table not found. Check the document ID and table index.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        if "400" in error_message:
            raise ToolError(
                f"Invalid request: {error_message}. Check that the table exists at index {table_start_index} "
                f"and cell ({row_index},{column_index}) is merged."
            )
        raise ToolError(f"Failed to unmerge table cells: {error_message}")


def create_named_range(
    document_id: str,
    name: str,
    start_index: int,
    end_index: int,
    tab_id: str | None = None,
) -> str:
    """
    Create a named range for cross-referencing.

    Args:
        document_id: The ID of the Google Document
        name: Name for the range
        start_index: Starting index (inclusive, 1-based)
        end_index: Ending index (exclusive)
        tab_id: Optional tab ID

    Returns:
        Success message with named range ID

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Creating named range '{name}' at range {start_index}-{end_index}")

    try:
        request = helpers.build_create_named_range_request(
            name, start_index, end_index, tab_id
        )

        result = helpers.execute_batch_update_sync(docs, document_id, [request])

        # Extract named range ID from response
        named_range_id = ""
        if result and "replies" in result:
            for reply in result.get("replies", []):
                if "createNamedRange" in reply:
                    named_range_id = reply["createNamedRange"].get("namedRangeId", "")

        return f"Successfully created named range '{name}' at range {start_index}-{end_index}. Range ID: {named_range_id}"

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error creating named range: {error_message}")
        if "404" in error_message:
            raise ToolError("Document not found. Check the document ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        raise ToolError(f"Failed to create named range: {error_message}")


def delete_named_range(
    document_id: str,
    named_range_id: str,
) -> str:
    """
    Delete a named range.

    Args:
        document_id: The ID of the Google Document
        named_range_id: ID of the named range to delete

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Deleting named range {named_range_id}")

    try:
        request = helpers.build_delete_named_range_request(named_range_id)

        helpers.execute_batch_update_sync(docs, document_id, [request])

        return f"Successfully deleted named range {named_range_id}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error deleting named range: {error_message}")
        if "404" in error_message:
            raise ToolError("Document or named range not found. Check the document ID and named range ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        raise ToolError(f"Failed to delete named range: {error_message}")


def insert_footnote(
    document_id: str,
    index: int,
    footnote_text: str,
) -> str:
    """
    Insert a footnote at the specified index.

    Args:
        document_id: The ID of the Google Document
        index: Index where to insert footnote (1-based)
        footnote_text: Text content of the footnote

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Inserting footnote at index {index}")

    try:
        request = helpers.build_insert_footnote_request(index, footnote_text)

        helpers.execute_batch_update_sync(docs, document_id, [request])

        return f"Successfully inserted footnote at index {index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error inserting footnote: {error_message}")
        if "404" in error_message:
            raise ToolError("Document not found. Check the document ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        raise ToolError(f"Failed to insert footnote: {error_message}")


def insert_table_of_contents(
    document_id: str,
    index: int,
) -> str:
    """
    Insert a table of contents at the specified index.

    The table of contents is auto-generated from document headings.

    Args:
        document_id: The ID of the Google Document
        index: Index where to insert TOC (1-based)

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Inserting table of contents at index {index}")

    try:
        request = helpers.build_insert_table_of_contents_request(index)

        helpers.execute_batch_update_sync(docs, document_id, [request])

        return f"Successfully inserted table of contents at index {index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error inserting table of contents: {error_message}")
        if "404" in error_message:
            raise ToolError("Document not found. Check the document ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        raise ToolError(f"Failed to insert table of contents: {error_message}")


def insert_horizontal_rule(
    document_id: str,
    index: int,
) -> str:
    """
    Insert a horizontal rule (divider line) at the specified index.

    Args:
        document_id: The ID of the Google Document
        index: Index where to insert rule (1-based)

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Inserting horizontal rule at index {index}")

    try:
        request = helpers.build_insert_horizontal_rule_request(index)

        helpers.execute_batch_update_sync(docs, document_id, [request])

        return f"Successfully inserted horizontal rule at index {index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error inserting horizontal rule: {error_message}")
        if "404" in error_message:
            raise ToolError("Document not found. Check the document ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        raise ToolError(f"Failed to insert horizontal rule: {error_message}")


def insert_section_break(
    document_id: str,
    index: int,
    section_type: str = "CONTINUOUS",
) -> str:
    """
    Insert a section break at the specified index.

    Args:
        document_id: The ID of the Google Document
        index: Index where to insert section break (1-based)
        section_type: Type of section break (CONTINUOUS, NEXT_PAGE, EVEN_PAGE, ODD_PAGE)

    Returns:
        Success message

    Raises:
        ToolError: For permission/not found errors
    """
    docs = get_docs_client()
    log(f"Inserting {section_type} section break at index {index}")

    try:
        request = helpers.build_insert_section_break_request(index, section_type)

        helpers.execute_batch_update_sync(docs, document_id, [request])

        return f"Successfully inserted {section_type} section break at index {index}."

    except ToolError:
        raise
    except Exception as e:
        error_message = str(e)
        log(f"Error inserting section break: {error_message}")
        if "404" in error_message:
            raise ToolError("Document not found. Check the document ID.")
        if "403" in error_message:
            raise ToolError(
                "Permission denied. Ensure you have edit access to the document."
            )
        raise ToolError(f"Failed to insert section break: {error_message}")


# --- Bulk Operation Preparation Functions for New Operations ---


def _prepare_create_bullet_list_request(op_dict: dict, default_tab_id: str | None) -> dict:
    """Prepare createParagraphBullets request from operation dict."""
    start_index = op_dict.get("start_index", 1)
    end_index = op_dict.get("end_index", 1)
    list_type = op_dict.get("list_type", "UNORDERED")
    nesting_level = op_dict.get("nesting_level", 0)
    tab_id = op_dict.get("tab_id", default_tab_id)

    return helpers.build_create_paragraph_bullets_request(
        start_index, end_index, list_type, nesting_level, tab_id
    )


def _prepare_replace_all_text_request(op_dict: dict, default_tab_id: str | None) -> dict:
    """Prepare replaceAllText request from operation dict."""
    find_text = op_dict.get("find_text", "")
    replace_text = op_dict.get("replace_text", "")
    match_case = op_dict.get("match_case", True)
    tab_id = op_dict.get("tab_id", default_tab_id)

    if not find_text:
        raise ToolError("find_text is required for replace_all_text operation")

    return helpers.build_replace_all_text_request(
        find_text, replace_text, match_case, tab_id
    )


def _prepare_insert_table_row_request(op_dict: dict) -> dict:
    """Prepare insertTableRow request from operation dict."""
    table_start_index = op_dict.get("table_start_index", 1)
    row_index = op_dict.get("row_index", 0)
    insert_below = op_dict.get("insert_below", False)

    return helpers.build_insert_table_row_request(
        table_start_index, row_index, insert_below
    )


def _prepare_delete_table_row_request(op_dict: dict) -> dict:
    """Prepare deleteTableRow request from operation dict."""
    table_start_index = op_dict.get("table_start_index", 1)
    row_index = op_dict.get("row_index", 0)

    return helpers.build_delete_table_row_request(table_start_index, row_index)


def _prepare_insert_table_column_request(op_dict: dict) -> dict:
    """Prepare insertTableColumn request from operation dict."""
    table_start_index = op_dict.get("table_start_index", 1)
    column_index = op_dict.get("column_index", 0)
    insert_right = op_dict.get("insert_right", False)

    return helpers.build_insert_table_column_request(
        table_start_index, column_index, insert_right
    )


def _prepare_delete_table_column_request(op_dict: dict) -> dict:
    """Prepare deleteTableColumn request from operation dict."""
    table_start_index = op_dict.get("table_start_index", 1)
    column_index = op_dict.get("column_index", 0)

    return helpers.build_delete_table_column_request(table_start_index, column_index)


def _prepare_update_table_cell_style_request(op_dict: dict) -> dict | None:
    """Prepare updateTableCellStyle request from operation dict."""
    table_start_index = op_dict.get("table_start_index", 1)
    row_index = op_dict.get("row_index", 0)
    column_index = op_dict.get("column_index", 0)

    return helpers.build_update_table_cell_style_request(
        table_start_index,
        row_index,
        column_index,
        background_color=op_dict.get("background_color"),
        padding_top=op_dict.get("padding_top"),
        padding_bottom=op_dict.get("padding_bottom"),
        padding_left=op_dict.get("padding_left"),
        padding_right=op_dict.get("padding_right"),
        border_top_color=op_dict.get("border_top_color"),
        border_top_width=op_dict.get("border_top_width"),
        border_bottom_color=op_dict.get("border_bottom_color"),
        border_bottom_width=op_dict.get("border_bottom_width"),
        border_left_color=op_dict.get("border_left_color"),
        border_left_width=op_dict.get("border_left_width"),
        border_right_color=op_dict.get("border_right_color"),
        border_right_width=op_dict.get("border_right_width"),
    )


def _prepare_merge_table_cells_request(op_dict: dict) -> dict:
    """Prepare mergeTableCells request from operation dict."""
    table_start_index = op_dict.get("table_start_index", 1)
    start_row = op_dict.get("start_row", 0)
    start_column = op_dict.get("start_column", 0)
    row_span = op_dict.get("row_span", 1)
    column_span = op_dict.get("column_span", 1)

    return helpers.build_merge_table_cells_request(
        table_start_index, start_row, start_column, row_span, column_span
    )


def _prepare_unmerge_table_cells_request(op_dict: dict) -> dict:
    """Prepare unmergeTableCells request from operation dict."""
    table_start_index = op_dict.get("table_start_index", 1)
    row_index = op_dict.get("row_index", 0)
    column_index = op_dict.get("column_index", 0)

    return helpers.build_unmerge_table_cells_request(
        table_start_index, row_index, column_index
    )


def _prepare_create_named_range_request(op_dict: dict, default_tab_id: str | None) -> dict:
    """Prepare createNamedRange request from operation dict."""
    name = op_dict.get("name", "")
    start_index = op_dict.get("start_index", 1)
    end_index = op_dict.get("end_index", 1)
    tab_id = op_dict.get("tab_id", default_tab_id)

    if not name:
        raise ToolError("name is required for create_named_range operation")

    return helpers.build_create_named_range_request(
        name, start_index, end_index, tab_id
    )


def _prepare_delete_named_range_request(op_dict: dict) -> dict:
    """Prepare deleteNamedRange request from operation dict."""
    named_range_id = op_dict.get("named_range_id", "")

    if not named_range_id:
        raise ToolError("named_range_id is required for delete_named_range operation")

    return helpers.build_delete_named_range_request(named_range_id)


def _prepare_insert_footnote_request(op_dict: dict) -> dict:
    """Prepare insertFootnote request from operation dict."""
    index = op_dict.get("index", 1)
    footnote_text = op_dict.get("footnote_text", "")

    return helpers.build_insert_footnote_request(index, footnote_text)


def _prepare_insert_table_of_contents_request(op_dict: dict) -> dict:
    """Prepare insertTableOfContents request from operation dict."""
    index = op_dict.get("index", 1)

    return helpers.build_insert_table_of_contents_request(index)


def _prepare_insert_horizontal_rule_request(op_dict: dict) -> dict:
    """Prepare insertHorizontalRule request from operation dict."""
    index = op_dict.get("index", 1)

    return helpers.build_insert_horizontal_rule_request(index)


def _prepare_insert_section_break_request(op_dict: dict) -> dict:
    """Prepare insertSectionBreak request from operation dict."""
    index = op_dict.get("index", 1)
    section_type = op_dict.get("section_type", "CONTINUOUS")

    return helpers.build_insert_section_break_request(index, section_type)
