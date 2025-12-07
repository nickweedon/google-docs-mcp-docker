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


def convert_docs_json_to_markdown(doc_data: dict) -> str:
    """
    Convert Google Docs JSON structure to Markdown format.

    Args:
        doc_data: Document data from Google Docs API

    Returns:
        Markdown string representation
    """
    markdown = ""
    body = doc_data.get("body", {})
    content = body.get("content", [])

    if not content:
        return "Document appears to be empty."

    for element in content:
        if element.get("paragraph"):
            markdown += _convert_paragraph_to_markdown(element["paragraph"])
        elif element.get("table"):
            markdown += _convert_table_to_markdown(element["table"])
        elif element.get("sectionBreak"):
            markdown += "\n---\n\n"

    return markdown.strip()


def _convert_paragraph_to_markdown(paragraph: dict) -> str:
    """Convert a paragraph element to markdown."""
    text = ""
    is_heading = False
    heading_level = 0
    is_list = False

    # Check paragraph style for headings and lists
    style = paragraph.get("paragraphStyle", {})
    named_style = style.get("namedStyleType", "")

    if named_style.startswith("HEADING_"):
        is_heading = True
        try:
            heading_level = int(named_style.replace("HEADING_", ""))
        except ValueError:
            heading_level = 1
    elif named_style == "TITLE":
        is_heading = True
        heading_level = 1
    elif named_style == "SUBTITLE":
        is_heading = True
        heading_level = 2

    # Check for bullet lists
    if paragraph.get("bullet"):
        is_list = True

    # Process text elements
    for element in paragraph.get("elements", []):
        if element.get("textRun"):
            text += _convert_text_run_to_markdown(element["textRun"])

    # Format based on style
    if is_heading and text.strip():
        hashes = "#" * min(heading_level, 6)
        return f"{hashes} {text.strip()}\n\n"
    elif is_list and text.strip():
        return f"- {text.strip()}\n"
    elif text.strip():
        return f"{text.strip()}\n\n"

    return "\n"


def _convert_text_run_to_markdown(text_run: dict) -> str:
    """Convert a text run to markdown with formatting."""
    text = text_run.get("content", "")
    style = text_run.get("textStyle", {})

    if style:
        is_bold = style.get("bold", False)
        is_italic = style.get("italic", False)
        is_underline = style.get("underline", False)
        is_strikethrough = style.get("strikethrough", False)
        link = style.get("link", {})

        if is_bold and is_italic:
            text = f"***{text}***"
        elif is_bold:
            text = f"**{text}**"
        elif is_italic:
            text = f"*{text}*"

        if is_underline and not link:
            text = f"<u>{text}</u>"

        if is_strikethrough:
            text = f"~~{text}~~"

        if link.get("url"):
            text = f"[{text}]({link['url']})"

    return text


def _convert_table_to_markdown(table: dict) -> str:
    """Convert a table to markdown format."""
    rows = table.get("tableRows", [])
    if not rows:
        return ""

    markdown = "\n"
    is_first_row = True

    for row in rows:
        cells = row.get("tableCells", [])
        if not cells:
            continue

        row_text = "|"
        for cell in cells:
            cell_text = ""
            for element in cell.get("content", []):
                paragraph = element.get("paragraph", {})
                for pe in paragraph.get("elements", []):
                    text_run = pe.get("textRun", {})
                    if text_run.get("content"):
                        cell_text += text_run["content"].replace("\n", " ").strip()
            row_text += f" {cell_text} |"

        markdown += row_text + "\n"

        # Add header separator after first row
        if is_first_row:
            separator = "|"
            for _ in cells:
                separator += " --- |"
            markdown += separator + "\n"
            is_first_row = False

    return markdown + "\n"


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
            markdown_content = convert_docs_json_to_markdown(content_source)
            total_length = len(markdown_content)
            log(f"Generated markdown: {total_length} characters")

            if max_length and total_length > max_length:
                truncated = markdown_content[:max_length]
                return (
                    f"{truncated}\n\n... [Markdown truncated to {max_length} chars "
                    f"of {total_length} total. Use maxLength parameter to adjust limit "
                    f"or remove it to get full content.]"
                )

            return markdown_content

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
