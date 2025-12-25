"""
Helper functions for Google Docs API operations.

Ported from googleDocsApiHelpers.ts
"""

from typing import Any

from fastmcp.exceptions import ToolError

from google_docs_mcp.types import (
    TextStyleArgs,
    ParagraphStyleArgs,
    TextRange,
    TabInfo,
    hex_to_rgb_color,
    NotImplementedError,
)
from google_docs_mcp.utils import log


# --- Constants ---
MAX_BATCH_UPDATE_REQUESTS = 50


# --- Core Helper to Execute Batch Updates ---
def execute_batch_update_sync(docs, document_id: str, requests: list[dict]) -> dict | None:
    """
    Execute a batch update request on a Google Document.

    Args:
        docs: Google Docs API client
        document_id: The document ID
        requests: List of update requests

    Returns:
        Batch update response data

    Raises:
        ToolError: For client-facing errors
        Exception: For internal errors
    """
    if not requests:
        return {}

    if len(requests) > MAX_BATCH_UPDATE_REQUESTS:
        log(
            f"Attempting batch update with {len(requests)} requests, "
            f"exceeding typical limits. May fail."
        )

    try:
        response = (
            docs.documents()
            .batchUpdate(documentId=document_id, body={"requests": requests})
            .execute()
        )
        return response
    except Exception as e:
        error_message = str(e)
        log(f"Google API batchUpdate Error for doc {document_id}: {error_message}")

        # Handle common API errors
        if "404" in error_message:
            raise ToolError(f"Document not found (ID: {document_id}). Check the ID.")
        if "403" in error_message:
            raise ToolError(
                f"Permission denied for document (ID: {document_id}). "
                f"Ensure the authenticated user has edit access."
            )
        if "400" in error_message:
            raise ToolError(f"Invalid request sent to Google Docs API: {error_message}")

        raise Exception(f"Google API Error: {error_message}")


# --- Text Finding Helper ---
def find_text_range(
    docs, document_id: str, text_to_find: str, instance: int = 1
) -> TextRange | None:
    """
    Find a specific instance of text within a document.

    Args:
        docs: Google Docs API client
        document_id: The document ID
        text_to_find: The text string to locate
        instance: Which instance to find (1-based)

    Returns:
        TextRange with start and end indices, or None if not found

    Raises:
        UserError: For permission/not found errors
    """
    try:
        # Request detailed document structure
        res = (
            docs.documents()
            .get(
                documentId=document_id,
                fields="body(content(paragraph(elements(startIndex,endIndex,textRun(content))),table,sectionBreak,tableOfContents,startIndex,endIndex))",
            )
            .execute()
        )

        body = res.get("body", {})
        content = body.get("content", [])

        if not content:
            log(f"No content found in document {document_id}")
            return None

        # Collect text segments with their indices
        full_text = ""
        segments: list[dict] = []

        def collect_text_from_content(content_list: list) -> None:
            nonlocal full_text

            for element in content_list:
                # Handle paragraph elements
                paragraph = element.get("paragraph", {})
                if paragraph.get("elements"):
                    for pe in paragraph["elements"]:
                        text_run = pe.get("textRun", {})
                        if (
                            text_run.get("content")
                            and pe.get("startIndex") is not None
                            and pe.get("endIndex") is not None
                        ):
                            text_content = text_run["content"]
                            full_text += text_content
                            segments.append(
                                {
                                    "text": text_content,
                                    "start": pe["startIndex"],
                                    "end": pe["endIndex"],
                                }
                            )

                # Handle table elements
                table = element.get("table", {})
                if table.get("tableRows"):
                    for row in table["tableRows"]:
                        for cell in row.get("tableCells", []):
                            if cell.get("content"):
                                collect_text_from_content(cell["content"])

        collect_text_from_content(content)

        # Sort segments by starting position
        segments.sort(key=lambda x: x["start"])

        log(
            f"Document {document_id} contains {len(segments)} text segments "
            f"and {len(full_text)} characters in total."
        )

        # Find the specified instance of the text
        start_index = -1
        end_index = -1
        found_count = 0
        search_start_index = 0

        while found_count < instance:
            current_index = full_text.find(text_to_find, search_start_index)
            if current_index == -1:
                log(
                    f'Search text "{text_to_find}" not found for instance '
                    f"{found_count + 1} (requested: {instance})"
                )
                break

            found_count += 1
            log(
                f'Found instance {found_count} of "{text_to_find}" '
                f"at position {current_index} in full text"
            )

            if found_count == instance:
                target_start = current_index
                target_end = current_index + len(text_to_find)
                current_pos = 0

                log(f"Target text range in full text: {target_start}-{target_end}")

                for seg in segments:
                    seg_start = current_pos
                    seg_length = len(seg["text"])
                    seg_end = seg_start + seg_length

                    # Map from reconstructed text position to actual document indices
                    if (
                        start_index == -1
                        and target_start >= seg_start
                        and target_start < seg_end
                    ):
                        start_index = seg["start"] + (target_start - seg_start)
                        log(
                            f"Mapped start to segment {seg['start']}-{seg['end']}, "
                            f"position {start_index}"
                        )

                    if target_end > seg_start and target_end <= seg_end:
                        end_index = seg["start"] + (target_end - seg_start)
                        log(
                            f"Mapped end to segment {seg['start']}-{seg['end']}, "
                            f"position {end_index}"
                        )
                        break

                    current_pos = seg_end

                if start_index == -1 or end_index == -1:
                    log(
                        f'Failed to map text "{text_to_find}" instance {instance} '
                        f"to actual document indices"
                    )
                    start_index = -1
                    end_index = -1
                    search_start_index = current_index + 1
                    found_count -= 1
                    continue

                log(
                    f'Successfully mapped "{text_to_find}" to document range '
                    f"{start_index}-{end_index}"
                )
                return TextRange(start_index=start_index, end_index=end_index)

            # Prepare for next search iteration
            search_start_index = current_index + 1

        log(
            f'Could not find instance {instance} of text "{text_to_find}" '
            f"in document {document_id}"
        )
        return None

    except Exception as e:
        error_message = str(e)
        log(
            f'Error finding text "{text_to_find}" in doc {document_id}: {error_message}'
        )
        if "404" in error_message:
            raise ToolError(
                f"Document not found while searching text (ID: {document_id})."
            )
        if "403" in error_message:
            raise ToolError(
                f"Permission denied while searching text in doc {document_id}."
            )
        raise Exception(f"Failed to retrieve doc for text searching: {error_message}")


# --- Paragraph Boundary Helper ---
def get_paragraph_range(
    docs, document_id: str, index_within: int
) -> TextRange | None:
    """
    Find the paragraph boundaries containing a specific index.

    Args:
        docs: Google Docs API client
        document_id: The document ID
        index_within: An index within the target paragraph

    Returns:
        TextRange with paragraph start and end indices, or None if not found

    Raises:
        UserError: For permission/not found errors
    """
    try:
        log(f"Finding paragraph containing index {index_within} in document {document_id}")

        res = (
            docs.documents()
            .get(
                documentId=document_id,
                fields="body(content(startIndex,endIndex,paragraph,table,sectionBreak,tableOfContents))",
            )
            .execute()
        )

        body = res.get("body", {})
        content = body.get("content", [])

        if not content:
            log(f"No content found in document {document_id}")
            return None

        def find_paragraph_in_content(
            content_list: list,
        ) -> TextRange | None:
            for element in content_list:
                start_idx = element.get("startIndex")
                end_idx = element.get("endIndex")

                if start_idx is not None and end_idx is not None:
                    if index_within >= start_idx and index_within < end_idx:
                        # If it's a paragraph, we've found our target
                        if element.get("paragraph"):
                            log(
                                f"Found paragraph containing index {index_within}, "
                                f"range: {start_idx}-{end_idx}"
                            )
                            return TextRange(start_index=start_idx, end_index=end_idx)

                        # If it's a table, search cells recursively
                        table = element.get("table", {})
                        if table.get("tableRows"):
                            log(
                                f"Index {index_within} is within a table, searching cells..."
                            )
                            for row in table["tableRows"]:
                                for cell in row.get("tableCells", []):
                                    if cell.get("content"):
                                        result = find_paragraph_in_content(
                                            cell["content"]
                                        )
                                        if result:
                                            return result

                        log(
                            f"Index {index_within} is within element "
                            f"({start_idx}-{end_idx}) but not in a paragraph"
                        )

            return None

        result = find_paragraph_in_content(content)

        if not result:
            log(f"Could not find paragraph containing index {index_within}")
        else:
            log(
                f"Returning paragraph range: {result.start_index}-{result.end_index}"
            )

        return result

    except Exception as e:
        error_message = str(e)
        log(
            f"Error getting paragraph range for index {index_within} "
            f"in doc {document_id}: {error_message}"
        )
        if "404" in error_message:
            raise ToolError(
                f"Document not found while finding paragraph (ID: {document_id})."
            )
        if "403" in error_message:
            raise ToolError(
                f"Permission denied while accessing doc {document_id}."
            )
        raise Exception(f"Failed to find paragraph: {error_message}")


def get_paragraph_range_from_document(
    document: dict, index_within: int, tab_id: str | None = None
) -> TextRange | None:
    """
    Find the paragraph boundaries containing a specific index using pre-fetched document data.

    This is more efficient than get_paragraph_range() when you already have the document data,
    as it avoids an additional API call.

    Args:
        document: The full document data dict (from docs.documents().get())
        index_within: An index within the target paragraph
        tab_id: Optional tab ID to search within (uses first tab if not specified)

    Returns:
        TextRange with paragraph start and end indices, or None if not found
    """
    log(f"Finding paragraph containing index {index_within} in document data")

    # Get the body content - handle both tab-based and direct body structure
    body = None
    tabs = document.get("tabs", [])

    if tabs:
        # Document has tabs structure
        if tab_id:
            # Find the specific tab
            for tab in tabs:
                tab_props = tab.get("tabProperties", {})
                if tab_props.get("tabId") == tab_id:
                    body = tab.get("documentTab", {}).get("body", {})
                    break
        if not body and tabs:
            # Use first tab
            body = tabs[0].get("documentTab", {}).get("body", {})
    else:
        # Legacy document structure without tabs
        body = document.get("body", {})

    if not body:
        log("No body content found in document data")
        return None

    content = body.get("content", [])

    if not content:
        log("No content found in document body")
        return None

    def find_paragraph_in_content(content_list: list) -> TextRange | None:
        for element in content_list:
            start_idx = element.get("startIndex")
            end_idx = element.get("endIndex")

            if start_idx is not None and end_idx is not None:
                if index_within >= start_idx and index_within < end_idx:
                    # If it's a paragraph, we've found our target
                    # Use "in" check because element.get("paragraph") returns {}
                    # which is falsy even when the key exists
                    if "paragraph" in element:
                        log(
                            f"Found paragraph containing index {index_within}, "
                            f"range: {start_idx}-{end_idx}"
                        )
                        return TextRange(start_index=start_idx, end_index=end_idx)

                    # If it's a table, search cells recursively
                    if "table" in element:
                        table = element["table"]
                        if table.get("tableRows"):
                            log(f"Index {index_within} is within a table, searching cells...")
                            for row in table["tableRows"]:
                                for cell in row.get("tableCells", []):
                                    if cell.get("content"):
                                        result = find_paragraph_in_content(cell["content"])
                                        if result:
                                            return result

                    log(
                        f"Index {index_within} is within element "
                        f"({start_idx}-{end_idx}) but not in a paragraph"
                    )

        return None

    result = find_paragraph_in_content(content)

    if not result:
        log(f"Could not find paragraph containing index {index_within}")
    else:
        log(f"Returning paragraph range: {result.start_index}-{result.end_index}")

    return result


# --- Style Request Builders ---
def build_update_text_style_request(
    start_index: int, end_index: int, style: TextStyleArgs
) -> dict | None:
    """
    Build an updateTextStyle request for the Google Docs API.

    Args:
        start_index: Starting index of text range
        end_index: Ending index of text range
        style: Text style arguments to apply

    Returns:
        Dictionary with 'request' and 'fields' keys, or None if no styles

    Raises:
        UserError: If color format is invalid
    """
    text_style: dict[str, Any] = {}
    fields_to_update: list[str] = []

    if style.bold is not None:
        text_style["bold"] = style.bold
        fields_to_update.append("bold")

    if style.italic is not None:
        text_style["italic"] = style.italic
        fields_to_update.append("italic")

    if style.underline is not None:
        text_style["underline"] = style.underline
        fields_to_update.append("underline")

    if style.strikethrough is not None:
        text_style["strikethrough"] = style.strikethrough
        fields_to_update.append("strikethrough")

    if style.font_size is not None:
        text_style["fontSize"] = {"magnitude": style.font_size, "unit": "PT"}
        fields_to_update.append("fontSize")

    if style.font_family is not None:
        text_style["weightedFontFamily"] = {"fontFamily": style.font_family}
        fields_to_update.append("weightedFontFamily")

    if style.foreground_color is not None:
        rgb_color = hex_to_rgb_color(style.foreground_color)
        if not rgb_color:
            raise ToolError(
                f"Invalid foreground hex color format: {style.foreground_color}"
            )
        text_style["foregroundColor"] = {"color": {"rgbColor": rgb_color}}
        fields_to_update.append("foregroundColor")

    if style.background_color is not None:
        rgb_color = hex_to_rgb_color(style.background_color)
        if not rgb_color:
            raise ToolError(
                f"Invalid background hex color format: {style.background_color}"
            )
        text_style["backgroundColor"] = {"color": {"rgbColor": rgb_color}}
        fields_to_update.append("backgroundColor")

    if style.link_url is not None:
        text_style["link"] = {"url": style.link_url}
        fields_to_update.append("link")

    if not fields_to_update:
        return None

    request = {
        "updateTextStyle": {
            "range": {"startIndex": start_index, "endIndex": end_index},
            "textStyle": text_style,
            "fields": ",".join(fields_to_update),
        }
    }

    return {"request": request, "fields": fields_to_update}


def build_update_paragraph_style_request(
    start_index: int, end_index: int, style: ParagraphStyleArgs
) -> dict | None:
    """
    Build an updateParagraphStyle request for the Google Docs API.

    Args:
        start_index: Starting index of paragraph range
        end_index: Ending index of paragraph range
        style: Paragraph style arguments to apply

    Returns:
        Dictionary with 'request' and 'fields' keys, or None if no styles
    """
    paragraph_style: dict[str, Any] = {}
    fields_to_update: list[str] = []

    log(
        f"Building paragraph style request for range {start_index}-{end_index} "
        f"with options: {style}"
    )

    if style.alignment is not None:
        paragraph_style["alignment"] = style.alignment
        fields_to_update.append("alignment")
        log(f"Setting alignment to {style.alignment}")

    if style.indent_start is not None:
        paragraph_style["indentStart"] = {
            "magnitude": style.indent_start,
            "unit": "PT",
        }
        fields_to_update.append("indentStart")
        log(f"Setting left indent to {style.indent_start}pt")

    if style.indent_end is not None:
        paragraph_style["indentEnd"] = {"magnitude": style.indent_end, "unit": "PT"}
        fields_to_update.append("indentEnd")
        log(f"Setting right indent to {style.indent_end}pt")

    if style.space_above is not None:
        paragraph_style["spaceAbove"] = {"magnitude": style.space_above, "unit": "PT"}
        fields_to_update.append("spaceAbove")
        log(f"Setting space above to {style.space_above}pt")

    if style.space_below is not None:
        paragraph_style["spaceBelow"] = {"magnitude": style.space_below, "unit": "PT"}
        fields_to_update.append("spaceBelow")
        log(f"Setting space below to {style.space_below}pt")

    if style.named_style_type is not None:
        paragraph_style["namedStyleType"] = style.named_style_type
        fields_to_update.append("namedStyleType")
        log(f"Setting named style to {style.named_style_type}")

    if style.keep_with_next is not None:
        paragraph_style["keepWithNext"] = style.keep_with_next
        fields_to_update.append("keepWithNext")
        log(f"Setting keepWithNext to {style.keep_with_next}")

    if not fields_to_update:
        log("No paragraph styling options were provided")
        return None

    request = {
        "updateParagraphStyle": {
            "range": {"startIndex": start_index, "endIndex": end_index},
            "paragraphStyle": paragraph_style,
            "fields": ",".join(fields_to_update),
        }
    }

    log(f"Created paragraph style request with fields: {', '.join(fields_to_update)}")
    return {"request": request, "fields": fields_to_update}


# --- Specific Feature Helpers ---
def create_table(
    docs, document_id: str, rows: int, columns: int, index: int
) -> dict | None:
    """
    Insert a new table into a document.

    Args:
        docs: Google Docs API client
        document_id: The document ID
        rows: Number of rows
        columns: Number of columns
        index: Position to insert the table

    Returns:
        Batch update response

    Raises:
        UserError: If table dimensions are invalid
    """
    if rows < 1 or columns < 1:
        raise ToolError("Table must have at least 1 row and 1 column.")

    request = {
        "insertTable": {
            "location": {"index": index},
            "rows": rows,
            "columns": columns,
        }
    }

    return execute_batch_update_sync(docs, document_id, [request])


def insert_text(docs, document_id: str, text: str, index: int) -> dict | None:
    """
    Insert text at a specific position in a document.

    Args:
        docs: Google Docs API client
        document_id: The document ID
        text: Text to insert
        index: Position to insert text

    Returns:
        Batch update response
    """
    if not text:
        return {}

    request = {"insertText": {"location": {"index": index}, "text": text}}

    return execute_batch_update_sync(docs, document_id, [request])


def _validate_image_url(image_url: str) -> None:
    """
    Validate that an image URL is accessible before sending to Google Docs API.

    Args:
        image_url: The URL to validate

    Raises:
        ToolError: If the URL is invalid or inaccessible
    """
    import urllib.request
    from urllib.parse import urlparse
    from urllib.error import HTTPError, URLError

    # Validate URL format
    try:
        result = urlparse(image_url)
        if not all([result.scheme, result.netloc]):
            raise ValueError("Invalid URL")
        if result.scheme not in ('http', 'https'):
            raise ValueError("URL must use http or https")
    except Exception:
        raise ToolError(f"Invalid image URL format: {image_url}")

    # Check for Google Drive URLs and provide helpful guidance
    if 'drive.google.com' in result.netloc:
        # For Drive URLs with the /uc endpoint, convert to download format
        if '/uc' in image_url:
            # Extract file ID and create proper download URL
            import re
            file_id_match = re.search(r'[?&]id=([^&]+)', image_url)
            if file_id_match:
                file_id = file_id_match.group(1)
                # Return the download URL format that works with Google Docs
                suggested_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                if 'export=download' not in image_url:
                    raise ToolError(
                        f"Google Drive sharing URLs must use the download format. "
                        f"Try this URL instead: {suggested_url}"
                    )

    # Check if URL is accessible
    try:
        # Create a HEAD request to check accessibility without downloading the full image
        req = urllib.request.Request(image_url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0 (compatible; GoogleDocsBot/1.0)')

        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            content_type = response.headers.get('Content-Type', '')

            if status_code != 200:
                raise ToolError(
                    f"Image URL returned status {status_code}: {image_url}. "
                    "The image must be publicly accessible."
                )

            # Verify it's an image (skip for Google Drive download URLs as they may redirect)
            is_drive_download = 'drive.google.com/uc' in image_url and 'export=download' in image_url
            if not is_drive_download and content_type and not content_type.startswith('image/'):
                # Provide helpful error for Google Drive URLs with wrong format
                if 'drive.google.com' in image_url:
                    raise ToolError(
                        f"URL does not point to an image (Content-Type: {content_type}): {image_url}. "
                        "Google Drive sharing links require public access and the download format. "
                        "Make sure the file is shared publicly and use: "
                        "https://drive.google.com/uc?export=download&id=FILE_ID"
                    )
                raise ToolError(
                    f"URL does not point to an image (Content-Type: {content_type}): {image_url}. "
                    "Expected image/* content type."
                )

    except HTTPError as e:
        raise ToolError(
            f"Image URL returned HTTP {e.code} error: {image_url}. "
            "Please verify the URL is correct and publicly accessible."
        )
    except URLError as e:
        raise ToolError(
            f"Cannot access image URL: {image_url}. "
            f"Error: {str(e.reason)}. "
            "The image must be publicly accessible on the internet."
        )
    except TimeoutError:
        raise ToolError(
            f"Timeout accessing image URL: {image_url}. "
            "The server did not respond in time."
        )
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(
            f"Failed to validate image URL: {image_url}. "
            f"Error: {str(e)}"
        )


def insert_inline_image(
    docs,
    document_id: str,
    image_url: str,
    index: int,
    width: float | None = None,
    height: float | None = None,
) -> dict | None:
    """
    Insert an inline image from a URL.

    Args:
        docs: Google Docs API client
        document_id: The document ID
        image_url: Publicly accessible URL to the image
        index: Position to insert the image
        width: Optional width in points
        height: Optional height in points

    Returns:
        Batch update response

    Raises:
        ToolError: If URL is invalid or inaccessible
    """
    # Validate URL is accessible before attempting insertion
    _validate_image_url(image_url)

    # If this is a Google Drive URL, ensure it has public permissions
    if 'drive.google.com' in image_url:
        import re
        from google_docs_mcp.auth import get_drive_client

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

    request: dict[str, Any] = {
        "insertInlineImage": {"location": {"index": index}, "uri": image_url}
    }

    if width and height:
        request["insertInlineImage"]["objectSize"] = {
            "height": {"magnitude": height, "unit": "PT"},
            "width": {"magnitude": width, "unit": "PT"},
        }

    return execute_batch_update_sync(docs, document_id, [request])


# --- Tab Management Helpers ---
def get_all_tabs(doc: dict) -> list[TabInfo]:
    """
    Get all tabs from a document in a flat list with hierarchy info.

    Args:
        doc: Google Document response object

    Returns:
        List of TabInfo objects with nesting level information
    """
    all_tabs: list[TabInfo] = []
    tabs = doc.get("tabs", [])

    if not tabs:
        return all_tabs

    def add_tab_and_children(tab: dict, level: int) -> None:
        props = tab.get("tabProperties", {})
        doc_tab = tab.get("documentTab")

        text_length = None
        if doc_tab:
            text_length = get_tab_text_length(doc_tab)

        tab_info = TabInfo(
            tab_id=props.get("tabId", ""),
            title=props.get("title", "Untitled"),
            index=props.get("index"),
            parent_tab_id=props.get("parentTabId"),
            level=level,
            text_length=text_length,
        )
        all_tabs.append(tab_info)

        for child_tab in tab.get("childTabs", []):
            add_tab_and_children(child_tab, level + 1)

    for tab in tabs:
        add_tab_and_children(tab, 0)

    return all_tabs


def get_tab_text_length(document_tab: dict) -> int:
    """
    Get the text length from a DocumentTab.

    Args:
        document_tab: The DocumentTab object

    Returns:
        Total character count
    """
    total_length = 0
    body = document_tab.get("body", {})
    content = body.get("content", [])

    for element in content:
        # Handle paragraphs
        paragraph = element.get("paragraph", {})
        if paragraph.get("elements"):
            for pe in paragraph["elements"]:
                text_run = pe.get("textRun", {})
                if text_run.get("content"):
                    total_length += len(text_run["content"])

        # Handle tables
        table = element.get("table", {})
        if table.get("tableRows"):
            for row in table["tableRows"]:
                for cell in row.get("tableCells", []):
                    for cell_element in cell.get("content", []):
                        cell_paragraph = cell_element.get("paragraph", {})
                        for pe in cell_paragraph.get("elements", []):
                            text_run = pe.get("textRun", {})
                            if text_run.get("content"):
                                total_length += len(text_run["content"])

    return total_length


def find_tab_by_id(doc: dict, tab_id: str) -> dict | None:
    """
    Find a specific tab by ID in a document.

    Args:
        doc: Google Document response object
        tab_id: The tab ID to search for

    Returns:
        The tab object if found, None otherwise
    """
    tabs = doc.get("tabs", [])
    if not tabs:
        return None

    def search_tabs(tabs_list: list) -> dict | None:
        for tab in tabs_list:
            props = tab.get("tabProperties", {})
            if props.get("tabId") == tab_id:
                return tab
            # Recursively search child tabs
            child_tabs = tab.get("childTabs", [])
            if child_tabs:
                found = search_tabs(child_tabs)
                if found:
                    return found
        return None

    return search_tabs(tabs)


# --- Not Implemented Helpers ---
def detect_and_format_lists(
    docs, document_id: str, start_index: int | None = None, end_index: int | None = None
) -> dict:
    """
    Detect and format lists in a document.

    NOT IMPLEMENTED.
    """
    log("detect_and_format_lists is not implemented.")
    raise NotImplementedError(
        "Automatic list detection and formatting is not yet implemented."
    )


def find_paragraphs_matching_style(
    docs, document_id: str, style_criteria: dict
) -> list[TextRange]:
    """
    Find paragraphs matching style criteria.

    NOT IMPLEMENTED.
    """
    log("find_paragraphs_matching_style is not implemented.")
    raise NotImplementedError(
        "Finding paragraphs by style criteria is not yet implemented."
    )


# --- Bulk Operations Helpers ---
def chunk_requests(requests: list[dict], chunk_size: int = 50) -> list[list[dict]]:
    """
    Split requests into chunks of specified size.

    Args:
        requests: List of request dictionaries
        chunk_size: Maximum number of requests per chunk (default: 50)

    Returns:
        List of request chunks
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    return [requests[i : i + chunk_size] for i in range(0, len(requests), chunk_size)]


# --- List & Bullet Helpers ---
def build_create_paragraph_bullets_request(
    start_index: int,
    end_index: int,
    list_type: str = "UNORDERED",
    nesting_level: int = 0,
    tab_id: str | None = None,
) -> dict:
    """
    Build a createParagraphBullets request.

    Args:
        start_index: Starting index of range (inclusive, 1-based)
        end_index: Ending index of range (exclusive)
        list_type: Type of list (UNORDERED, ORDERED_DECIMAL, etc.)
        nesting_level: Nesting level (0-8)
        tab_id: Optional tab ID

    Returns:
        Request dictionary for Google Docs API
    """
    # Map list types to bullet presets
    bullet_presets = {
        "UNORDERED": "BULLET_DISC_CIRCLE_SQUARE",
        "ORDERED_DECIMAL": "NUMBERED_DECIMAL_ALPHA_ROMAN",
        "ORDERED_ALPHA": "NUMBERED_UPPERLETTER_ALPHAROMAN",
        "ORDERED_ROMAN": "NUMBERED_UPPERROMAN_UPPERLETTER_DECIMAL",
    }

    request: dict[str, Any] = {
        "createParagraphBullets": {
            "range": {"startIndex": start_index, "endIndex": end_index},
            "bulletPreset": bullet_presets.get(list_type, "BULLET_DISC_CIRCLE_SQUARE"),
        }
    }

    if tab_id:
        request["createParagraphBullets"]["range"]["tabId"] = tab_id

    return request


# --- Text Replace Helpers ---
def build_replace_all_text_request(
    find_text: str,
    replace_text: str,
    match_case: bool = True,
    tab_id: str | None = None,
) -> dict:
    """
    Build a replaceAllText request.

    Args:
        find_text: Text to find
        replace_text: Text to replace it with
        match_case: Whether to match case
        tab_id: Optional tab ID

    Returns:
        Request dictionary for Google Docs API
    """
    request: dict[str, Any] = {
        "replaceAllText": {
            "containsText": {"text": find_text, "matchCase": match_case},
            "replaceText": replace_text,
        }
    }

    if tab_id:
        request["replaceAllText"]["tabId"] = tab_id

    return request


# --- Table Finding Helper ---
def find_table_at_index(docs, document_id: str, search_index: int) -> Any:
    """
    Locate a table containing or near the specified index.

    Scans document structure for table elements and returns table
    boundaries and dimensions.

    Args:
        docs: Google Docs API client
        document_id: The document ID
        search_index: An index that should be within the table

    Returns:
        TableInfo with table boundaries and dimensions, or None if not found

    Raises:
        ToolError: For API errors
    """
    from google_docs_mcp.types import TableInfo

    try:
        # Fetch document structure with minimal fields
        res = (
            docs.documents()
            .get(documentId=document_id, fields="body(content(table,startIndex,endIndex))")
            .execute()
        )

        # Scan for table elements
        for element in res.get("body", {}).get("content", []):
            if "table" in element:
                table_start = element.get("startIndex", 0)
                table_end = element.get("endIndex", 0)

                # Check if search_index falls within table boundaries
                if table_start <= search_index < table_end:
                    table = element["table"]
                    table_rows = table.get("tableRows", [])
                    rows = len(table_rows)
                    columns = (
                        len(table_rows[0].get("tableCells", [])) if rows > 0 else 0
                    )

                    return TableInfo(
                        start_index=table_start,
                        end_index=table_end,
                        rows=rows,
                        columns=columns,
                    )

        return None

    except Exception as e:
        error_message = str(e)
        log(f"Error finding table at index {search_index}: {error_message}")
        raise ToolError(f"Failed to find table: {error_message}")


# --- Table Operation Helpers ---
def build_insert_table_row_request(
    table_start_index: int, row_index: int, insert_below: bool = False
) -> dict:
    """
    Build an insertTableRow request.

    Args:
        table_start_index: Index where the table starts
        row_index: Row index (0-based)
        insert_below: True to insert below, False to insert above

    Returns:
        Request dictionary for Google Docs API
    """
    return {
        "insertTableRow": {
            "tableCellLocation": {
                "tableStartLocation": {"index": table_start_index},
                "rowIndex": row_index,
                "columnIndex": 0,
            },
            "insertBelow": insert_below,
        }
    }


def build_delete_table_row_request(table_start_index: int, row_index: int) -> dict:
    """
    Build a deleteTableRow request.

    Args:
        table_start_index: Index where the table starts
        row_index: Row index (0-based)

    Returns:
        Request dictionary for Google Docs API
    """
    return {
        "deleteTableRow": {
            "tableCellLocation": {
                "tableStartLocation": {"index": table_start_index},
                "rowIndex": row_index,
                "columnIndex": 0,
            }
        }
    }


def build_insert_table_column_request(
    table_start_index: int, column_index: int, insert_right: bool = False
) -> dict:
    """
    Build an insertTableColumn request.

    Args:
        table_start_index: Index where the table starts
        column_index: Column index (0-based)
        insert_right: True to insert right, False to insert left

    Returns:
        Request dictionary for Google Docs API
    """
    return {
        "insertTableColumn": {
            "tableCellLocation": {
                "tableStartLocation": {"index": table_start_index},
                "rowIndex": 0,
                "columnIndex": column_index,
            },
            "insertRight": insert_right,
        }
    }


def build_delete_table_column_request(table_start_index: int, column_index: int) -> dict:
    """
    Build a deleteTableColumn request.

    Args:
        table_start_index: Index where the table starts
        column_index: Column index (0-based)

    Returns:
        Request dictionary for Google Docs API
    """
    return {
        "deleteTableColumn": {
            "tableCellLocation": {
                "tableStartLocation": {"index": table_start_index},
                "rowIndex": 0,
                "columnIndex": column_index,
            }
        }
    }


def build_update_table_cell_style_request(
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
) -> dict | None:
    """
    Build an updateTableCellStyle request.

    Args:
        table_start_index: Index where the table starts
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
        Request dictionary or None if no styles provided
    """
    table_cell_style: dict[str, Any] = {}
    fields: list[str] = []

    # Background color
    if background_color:
        rgb = hex_to_rgb_color(background_color)
        if rgb:
            table_cell_style["backgroundColor"] = {"color": {"rgbColor": rgb}}
            fields.append("backgroundColor")

    # Padding
    if padding_top is not None:
        table_cell_style["paddingTop"] = {"magnitude": padding_top, "unit": "PT"}
        fields.append("paddingTop")
    if padding_bottom is not None:
        table_cell_style["paddingBottom"] = {"magnitude": padding_bottom, "unit": "PT"}
        fields.append("paddingBottom")
    if padding_left is not None:
        table_cell_style["paddingLeft"] = {"magnitude": padding_left, "unit": "PT"}
        fields.append("paddingLeft")
    if padding_right is not None:
        table_cell_style["paddingRight"] = {"magnitude": padding_right, "unit": "PT"}
        fields.append("paddingRight")

    # Borders
    if border_top_color and border_top_width is not None:
        rgb = hex_to_rgb_color(border_top_color)
        if rgb:
            table_cell_style["borderTop"] = {
                "color": {"rgbColor": rgb},
                "width": {"magnitude": border_top_width, "unit": "PT"},
                "dashStyle": "SOLID",
            }
            fields.append("borderTop")

    if border_bottom_color and border_bottom_width is not None:
        rgb = hex_to_rgb_color(border_bottom_color)
        if rgb:
            table_cell_style["borderBottom"] = {
                "color": {"rgbColor": rgb},
                "width": {"magnitude": border_bottom_width, "unit": "PT"},
                "dashStyle": "SOLID",
            }
            fields.append("borderBottom")

    if border_left_color and border_left_width is not None:
        rgb = hex_to_rgb_color(border_left_color)
        if rgb:
            table_cell_style["borderLeft"] = {
                "color": {"rgbColor": rgb},
                "width": {"magnitude": border_left_width, "unit": "PT"},
                "dashStyle": "SOLID",
            }
            fields.append("borderLeft")

    if border_right_color and border_right_width is not None:
        rgb = hex_to_rgb_color(border_right_color)
        if rgb:
            table_cell_style["borderRight"] = {
                "color": {"rgbColor": rgb},
                "width": {"magnitude": border_right_width, "unit": "PT"},
                "dashStyle": "SOLID",
            }
            fields.append("borderRight")

    # Return None if no styles provided
    if not fields:
        return None

    return {
        "updateTableCellStyle": {
            "tableCellLocation": {
                "tableStartLocation": {"index": table_start_index},
                "rowIndex": row_index,
                "columnIndex": column_index,
            },
            "tableCellStyle": table_cell_style,
            "fields": ",".join(fields),
        }
    }


def build_merge_table_cells_request(
    table_start_index: int,
    start_row: int,
    start_column: int,
    row_span: int,
    column_span: int,
) -> dict:
    """
    Build a mergeTableCells request.

    Args:
        table_start_index: Index where the table starts
        start_row: Starting row index (0-based)
        start_column: Starting column index (0-based)
        row_span: Number of rows to merge
        column_span: Number of columns to merge

    Returns:
        Request dictionary for Google Docs API
    """
    return {
        "mergeTableCells": {
            "tableRange": {
                "tableCellLocation": {
                    "tableStartLocation": {"index": table_start_index},
                    "rowIndex": start_row,
                    "columnIndex": start_column,
                },
                "rowSpan": row_span,
                "columnSpan": column_span,
            }
        }
    }


def build_unmerge_table_cells_request(
    table_start_index: int, row_index: int, column_index: int
) -> dict:
    """
    Build an unmergeTableCells request.

    Args:
        table_start_index: Index where the table starts
        row_index: Row index (0-based)
        column_index: Column index (0-based)

    Returns:
        Request dictionary for Google Docs API
    """
    return {
        "unmergeTableCells": {
            "tableCellLocation": {
                "tableStartLocation": {"index": table_start_index},
                "rowIndex": row_index,
                "columnIndex": column_index,
            }
        }
    }


# --- Named Range Helpers ---
def build_create_named_range_request(
    name: str, start_index: int, end_index: int, tab_id: str | None = None
) -> dict:
    """
    Build a createNamedRange request.

    Args:
        name: Name for the range
        start_index: Starting index (inclusive, 1-based)
        end_index: Ending index (exclusive)
        tab_id: Optional tab ID

    Returns:
        Request dictionary for Google Docs API
    """
    request: dict[str, Any] = {
        "createNamedRange": {
            "name": name,
            "range": {"startIndex": start_index, "endIndex": end_index},
        }
    }

    if tab_id:
        request["createNamedRange"]["range"]["tabId"] = tab_id

    return request


def build_delete_named_range_request(named_range_id: str) -> dict:
    """
    Build a deleteNamedRange request.

    Args:
        named_range_id: ID of the named range to delete

    Returns:
        Request dictionary for Google Docs API
    """
    return {"deleteNamedRange": {"namedRangeId": named_range_id}}


# --- Content Element Helpers ---
def build_insert_footnote_request(index: int, footnote_text: str) -> dict:
    """
    Build an insertFootnote request.

    Args:
        index: Index where to insert footnote (1-based)
        footnote_text: Text content of the footnote

    Returns:
        Request dictionary for Google Docs API
    """
    return {
        "insertInlineImage": {
            "location": {"index": index},
            "footnoteText": footnote_text,
        }
    }


def build_insert_table_of_contents_request(index: int) -> dict:
    """
    Build an insertTableOfContents request.

    Args:
        index: Index where to insert TOC (1-based)

    Returns:
        Request dictionary for Google Docs API
    """
    return {"insertTableOfContents": {"location": {"index": index}}}


def build_insert_horizontal_rule_request(index: int) -> dict:
    """
    Build an insertHorizontalRule request.

    Args:
        index: Index where to insert rule (1-based)

    Returns:
        Request dictionary for Google Docs API
    """
    return {"insertHorizontalRule": {"location": {"index": index}}}


def build_insert_section_break_request(index: int, section_type: str = "CONTINUOUS") -> dict:
    """
    Build an insertSectionBreak request.

    Args:
        index: Index where to insert section break (1-based)
        section_type: Type of section break (CONTINUOUS, NEXT_PAGE, etc.)

    Returns:
        Request dictionary for Google Docs API
    """
    return {
        "insertSectionBreak": {
            "location": {"index": index},
            "sectionType": section_type,
        }
    }
