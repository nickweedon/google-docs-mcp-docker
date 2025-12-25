"""
Type definitions and utilities for Google Docs MCP Server.
"""

import re
from dataclasses import dataclass, field
from typing import TypedDict

# --- Hex Color Regex ---
HEX_COLOR_REGEX = re.compile(r"^#?([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


def validate_hex_color(color: str) -> bool:
    """Validate if a string is a valid hex color."""
    return bool(HEX_COLOR_REGEX.match(color))


def hex_to_rgb_color(hex_color: str) -> dict[str, float] | None:
    """
    Convert a hex color string to RGB color dict for Google Docs API.

    Args:
        hex_color: Hex color string (e.g., "#FF0000" or "F00")

    Returns:
        Dictionary with 'red', 'green', 'blue' values (0.0-1.0) or None if invalid.
    """
    if not hex_color:
        return None

    hex_clean = hex_color.lstrip("#")

    # Expand 3-digit hex to 6-digit
    if len(hex_clean) == 3:
        hex_clean = hex_clean[0] * 2 + hex_clean[1] * 2 + hex_clean[2] * 2

    if len(hex_clean) != 6:
        return None

    try:
        bigint = int(hex_clean, 16)
    except ValueError:
        return None

    r = ((bigint >> 16) & 255) / 255
    g = ((bigint >> 8) & 255) / 255
    b = (bigint & 255) / 255

    return {"red": r, "green": g, "blue": b}


# --- Text Style Arguments ---
@dataclass
class TextStyleArgs:
    """Arguments for text styling operations."""

    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strikethrough: bool | None = None
    font_size: float | None = None
    font_family: str | None = None
    foreground_color: str | None = None
    background_color: str | None = None
    link_url: str | None = None


# --- Paragraph Style Arguments ---
@dataclass
class ParagraphStyleArgs:
    """Arguments for paragraph styling operations."""

    alignment: str | None = None  # START, END, CENTER, JUSTIFIED
    indent_start: float | None = None
    indent_end: float | None = None
    space_above: float | None = None
    space_below: float | None = None
    named_style_type: str | None = None
    keep_with_next: bool | None = None


# --- Response Types ---
@dataclass
class TextRange:
    """Represents a range of text in a document."""

    start_index: int
    end_index: int


@dataclass
class TabInfo:
    """Information about a document tab."""

    tab_id: str
    title: str
    index: int | None = None
    parent_tab_id: str | None = None
    level: int = 0
    text_length: int | None = None


# --- Bulk Operation Types ---
@dataclass
class InsertTextOperation:
    """Operation to insert text at a specific index."""

    type: str = field(default="insert_text", init=False)
    text: str = ""
    index: int = 1
    tab_id: str | None = None


@dataclass
class DeleteRangeOperation:
    """Operation to delete a range of content."""

    type: str = field(default="delete_range", init=False)
    start_index: int = 1
    end_index: int = 1
    tab_id: str | None = None


@dataclass
class ApplyTextStyleOperation:
    """Operation to apply character-level text styling."""

    type: str = field(default="apply_text_style", init=False)
    # Range-based targeting
    start_index: int | None = None
    end_index: int | None = None
    # Text-based targeting
    text_to_find: str | None = None
    match_instance: int | None = None
    # Style properties (from TextStyleArgs)
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strikethrough: bool | None = None
    font_size: float | None = None
    font_family: str | None = None
    foreground_color: str | None = None
    background_color: str | None = None
    link_url: str | None = None


@dataclass
class ApplyParagraphStyleOperation:
    """Operation to apply paragraph-level styling."""

    type: str = field(default="apply_paragraph_style", init=False)
    # Range-based targeting
    start_index: int | None = None
    end_index: int | None = None
    # Text-based targeting
    text_to_find: str | None = None
    match_instance: int | None = None
    # Index-based targeting
    index_within_paragraph: int | None = None
    # Style properties (from ParagraphStyleArgs)
    alignment: str | None = None
    indent_start: float | None = None
    indent_end: float | None = None
    space_above: float | None = None
    space_below: float | None = None
    named_style_type: str | None = None
    keep_with_next: bool | None = None


@dataclass
class InsertTableOperation:
    """Operation to insert a table."""

    type: str = field(default="insert_table", init=False)
    rows: int = 1
    columns: int = 1
    index: int = 1


@dataclass
class InsertPageBreakOperation:
    """Operation to insert a page break."""

    type: str = field(default="insert_page_break", init=False)
    index: int = 1


@dataclass
class InsertImageOperation:
    """Operation to insert an image from a URL."""

    type: str = field(default="insert_image_from_url", init=False)
    image_url: str = ""
    index: int = 1
    width: float | None = None
    height: float | None = None


# --- New Operation Types ---
@dataclass
class CreateBulletListOperation:
    """Operation to create a bulleted or numbered list."""

    type: str = field(default="create_bullet_list", init=False)
    start_index: int = 1
    end_index: int = 1
    list_type: str = "UNORDERED"  # UNORDERED, ORDERED_DECIMAL, etc.
    nesting_level: int = 0
    tab_id: str | None = None


@dataclass
class ReplaceAllTextOperation:
    """Operation to find and replace all instances of text."""

    type: str = field(default="replace_all_text", init=False)
    find_text: str = ""
    replace_text: str = ""
    match_case: bool = True
    tab_id: str | None = None


@dataclass
class InsertTableRowOperation:
    """Operation to insert a row into a table."""

    type: str = field(default="insert_table_row", init=False)
    table_start_index: int = 1
    row_index: int = 0
    insert_below: bool = False


@dataclass
class DeleteTableRowOperation:
    """Operation to delete a row from a table."""

    type: str = field(default="delete_table_row", init=False)
    table_start_index: int = 1
    row_index: int = 0


@dataclass
class InsertTableColumnOperation:
    """Operation to insert a column into a table."""

    type: str = field(default="insert_table_column", init=False)
    table_start_index: int = 1
    column_index: int = 0
    insert_right: bool = False


@dataclass
class DeleteTableColumnOperation:
    """Operation to delete a column from a table."""

    type: str = field(default="delete_table_column", init=False)
    table_start_index: int = 1
    column_index: int = 0


@dataclass
class UpdateTableCellStyleOperation:
    """Operation to style a table cell."""

    type: str = field(default="update_table_cell_style", init=False)
    table_start_index: int = 1
    row_index: int = 0
    column_index: int = 0
    background_color: str | None = None
    padding_top: float | None = None
    padding_bottom: float | None = None
    padding_left: float | None = None
    padding_right: float | None = None
    border_top_color: str | None = None
    border_top_width: float | None = None
    border_bottom_color: str | None = None
    border_bottom_width: float | None = None
    border_left_color: str | None = None
    border_left_width: float | None = None
    border_right_color: str | None = None
    border_right_width: float | None = None


@dataclass
class MergeTableCellsOperation:
    """Operation to merge table cells."""

    type: str = field(default="merge_table_cells", init=False)
    table_start_index: int = 1
    start_row: int = 0
    start_column: int = 0
    row_span: int = 1
    column_span: int = 1


@dataclass
class UnmergeTableCellsOperation:
    """Operation to unmerge table cells."""

    type: str = field(default="unmerge_table_cells", init=False)
    table_start_index: int = 1
    row_index: int = 0
    column_index: int = 0


@dataclass
class CreateNamedRangeOperation:
    """Operation to create a named range."""

    type: str = field(default="create_named_range", init=False)
    name: str = ""
    start_index: int = 1
    end_index: int = 1
    tab_id: str | None = None


@dataclass
class DeleteNamedRangeOperation:
    """Operation to delete a named range."""

    type: str = field(default="delete_named_range", init=False)
    named_range_id: str = ""


@dataclass
class InsertFootnoteOperation:
    """Operation to insert a footnote."""

    type: str = field(default="insert_footnote", init=False)
    index: int = 1
    footnote_text: str = ""


@dataclass
class InsertTableOfContentsOperation:
    """Operation to insert a table of contents."""

    type: str = field(default="insert_table_of_contents", init=False)
    index: int = 1


@dataclass
class InsertHorizontalRuleOperation:
    """Operation to insert a horizontal rule."""

    type: str = field(default="insert_horizontal_rule", init=False)
    index: int = 1


@dataclass
class InsertSectionBreakOperation:
    """Operation to insert a section break."""

    type: str = field(default="insert_section_break", init=False)
    index: int = 1
    section_type: str = "CONTINUOUS"  # CONTINUOUS, NEXT_PAGE, etc.


# --- Helper Types ---
@dataclass
class TableInfo:
    """Information about a table in the document."""

    start_index: int
    end_index: int
    rows: int
    columns: int


@dataclass
class TableCellLocation:
    """Location of a specific cell within a table."""

    table_start_index: int
    row_index: int
    column_index: int


# Union type for all bulk operations
BulkOperation = (
    InsertTextOperation
    | DeleteRangeOperation
    | ApplyTextStyleOperation
    | ApplyParagraphStyleOperation
    | InsertTableOperation
    | InsertPageBreakOperation
    | InsertImageOperation
    | CreateBulletListOperation
    | ReplaceAllTextOperation
    | InsertTableRowOperation
    | DeleteTableRowOperation
    | InsertTableColumnOperation
    | DeleteTableColumnOperation
    | UpdateTableCellStyleOperation
    | MergeTableCellsOperation
    | UnmergeTableCellsOperation
    | CreateNamedRangeOperation
    | DeleteNamedRangeOperation
    | InsertFootnoteOperation
    | InsertTableOfContentsOperation
    | InsertHorizontalRuleOperation
    | InsertSectionBreakOperation
)


# --- Custom Exceptions ---
class NotImplementedError(Exception):
    """Raised when a feature is not yet implemented."""

    def __init__(self, message: str = "This feature is not yet implemented."):
        super().__init__(message)
        self.name = "NotImplementedError"
