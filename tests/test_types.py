"""
Tests for type utilities and color conversion.

Ported from tests/types.test.js
"""

import pytest
from google_docs_mcp.types import validate_hex_color, hex_to_rgb_color


class TestValidateHexColor:
    """Tests for hex color validation."""

    def test_validate_correct_hex_colors_with_hash(self):
        """Should validate correct hex colors with hash prefix."""
        assert validate_hex_color("#FF0000") is True  # 6 digits red
        assert validate_hex_color("#F00") is True  # 3 digits red
        assert validate_hex_color("#00FF00") is True  # 6 digits green
        assert validate_hex_color("#0F0") is True  # 3 digits green

    def test_validate_correct_hex_colors_without_hash(self):
        """Should validate correct hex colors without hash prefix."""
        assert validate_hex_color("FF0000") is True  # 6 digits red
        assert validate_hex_color("F00") is True  # 3 digits red
        assert validate_hex_color("00FF00") is True  # 6 digits green
        assert validate_hex_color("0F0") is True  # 3 digits green

    def test_reject_invalid_hex_colors(self):
        """Should reject invalid hex colors."""
        assert validate_hex_color("") is False  # Empty
        assert validate_hex_color("#XYZ") is False  # Invalid characters
        assert validate_hex_color("#12345") is False  # Invalid length (5)
        assert validate_hex_color("#1234567") is False  # Invalid length (7)
        assert validate_hex_color("invalid") is False  # Not a hex color
        assert validate_hex_color("#12") is False  # Too short


class TestHexToRgbColor:
    """Tests for hex to RGB color conversion."""

    def test_convert_6_digit_hex_with_hash(self):
        """Should convert 6-digit hex colors with hash correctly."""
        result = hex_to_rgb_color("#FF0000")
        assert result == {"red": 1, "green": 0, "blue": 0}  # Red

        result_green = hex_to_rgb_color("#00FF00")
        assert result_green == {"red": 0, "green": 1, "blue": 0}  # Green

        result_blue = hex_to_rgb_color("#0000FF")
        assert result_blue == {"red": 0, "green": 0, "blue": 1}  # Blue

        result_purple = hex_to_rgb_color("#800080")
        # Purple - approximately 0.502
        assert result_purple["red"] == pytest.approx(0.5019607843137255)
        assert result_purple["green"] == 0
        assert result_purple["blue"] == pytest.approx(0.5019607843137255)

    def test_convert_3_digit_hex(self):
        """Should convert 3-digit hex colors correctly."""
        result = hex_to_rgb_color("#F00")
        assert result == {"red": 1, "green": 0, "blue": 0}  # Red from shorthand

        result_white = hex_to_rgb_color("#FFF")
        assert result_white == {"red": 1, "green": 1, "blue": 1}  # White from shorthand

    def test_convert_hex_without_hash(self):
        """Should convert hex colors without hash correctly."""
        result = hex_to_rgb_color("FF0000")
        assert result == {"red": 1, "green": 0, "blue": 0}  # Red without hash

    def test_return_none_for_invalid_hex(self):
        """Should return None for invalid hex colors."""
        assert hex_to_rgb_color("") is None  # Empty
        assert hex_to_rgb_color("#XYZ") is None  # Invalid characters
        assert hex_to_rgb_color("#12345") is None  # Invalid length
        assert hex_to_rgb_color("invalid") is None  # Not a hex color
