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


# --- Custom Exceptions ---
class NotImplementedError(Exception):
    """Raised when a feature is not yet implemented."""

    def __init__(self, message: str = "This feature is not yet implemented."):
        super().__init__(message)
        self.name = "NotImplementedError"
