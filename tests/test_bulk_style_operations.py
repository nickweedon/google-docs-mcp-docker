"""
Tests for bulk style operations (text and paragraph styling).

Tests the _prepare_apply_text_style_request and _prepare_apply_paragraph_style_request
functions with focus on tab_id handling.
"""

import pytest
from unittest.mock import MagicMock, patch

from google_docs_mcp.api.documents import (
    _prepare_apply_text_style_request,
    _prepare_apply_paragraph_style_request,
)
from fastmcp.exceptions import ToolError


class TestPrepareApplyTextStyleRequest:
    """Tests for _prepare_apply_text_style_request function."""

    def test_basic_text_style_by_range(self):
        """Should prepare text style request with range."""
        op_dict = {
            "start_index": 1,
            "end_index": 10,
            "bold": True,
            "italic": True,
        }

        request = _prepare_apply_text_style_request(op_dict, None, None)

        assert "updateTextStyle" in request
        assert request["updateTextStyle"]["range"]["startIndex"] == 1
        assert request["updateTextStyle"]["range"]["endIndex"] == 10
        assert request["updateTextStyle"]["textStyle"]["bold"] == True
        assert request["updateTextStyle"]["textStyle"]["italic"] == True
        assert "tabId" not in request["updateTextStyle"]["range"]

    def test_text_style_with_tab_id(self):
        """Should include tab_id in range when provided."""
        op_dict = {
            "start_index": 1,
            "end_index": 10,
            "bold": True,
            "tab_id": "tab123",
        }

        request = _prepare_apply_text_style_request(op_dict, None, None)

        assert request["updateTextStyle"]["range"]["tabId"] == "tab123"

    def test_text_style_with_default_tab_id(self):
        """Should use default tab_id when not specified in operation."""
        op_dict = {
            "start_index": 1,
            "end_index": 10,
            "bold": True,
        }

        request = _prepare_apply_text_style_request(op_dict, None, "default_tab")

        assert request["updateTextStyle"]["range"]["tabId"] == "default_tab"

    def test_text_style_operation_overrides_default_tab_id(self):
        """Should use operation tab_id over default."""
        op_dict = {
            "start_index": 1,
            "end_index": 10,
            "bold": True,
            "tab_id": "op_tab",
        }

        request = _prepare_apply_text_style_request(op_dict, None, "default_tab")

        assert request["updateTextStyle"]["range"]["tabId"] == "op_tab"

    def test_text_style_with_color(self):
        """Should handle foreground and background colors."""
        op_dict = {
            "start_index": 1,
            "end_index": 10,
            "foreground_color": "#FF0000",
            "background_color": "#FFFF00",
        }

        request = _prepare_apply_text_style_request(op_dict, None, None)

        assert "foregroundColor" in request["updateTextStyle"]["textStyle"]
        assert "backgroundColor" in request["updateTextStyle"]["textStyle"]

    def test_text_style_with_font(self):
        """Should handle font size and family."""
        op_dict = {
            "start_index": 1,
            "end_index": 10,
            "font_size": 14,
            "font_family": "Arial",
        }

        request = _prepare_apply_text_style_request(op_dict, None, None)

        assert request["updateTextStyle"]["textStyle"]["fontSize"]["magnitude"] == 14
        assert request["updateTextStyle"]["textStyle"]["weightedFontFamily"]["fontFamily"] == "Arial"

    def test_text_style_missing_range(self):
        """Should raise error when range is not provided."""
        op_dict = {
            "bold": True,
        }

        with pytest.raises(ToolError) as exc_info:
            _prepare_apply_text_style_request(op_dict, None, None)

        assert "start_index" in str(exc_info.value) or "end_index" in str(exc_info.value)

    @patch("google_docs_mcp.api.helpers.find_text_range")
    @patch("google_docs_mcp.api.documents.get_docs_client")
    def test_text_style_by_text_search(self, mock_get_docs, mock_find_text):
        """Should find text and apply styling."""
        # Mock finding text
        from google_docs_mcp.types import TextRange
        mock_find_text.return_value = TextRange(start_index=5, end_index=15)

        document = {"documentId": "doc123"}
        op_dict = {
            "text_to_find": "Hello World",
            "bold": True,
        }

        request = _prepare_apply_text_style_request(op_dict, document, None)

        assert request["updateTextStyle"]["range"]["startIndex"] == 5
        assert request["updateTextStyle"]["range"]["endIndex"] == 15
        assert request["updateTextStyle"]["textStyle"]["bold"] == True


class TestPrepareApplyParagraphStyleRequest:
    """Tests for _prepare_apply_paragraph_style_request function."""

    def test_basic_paragraph_style_by_range(self):
        """Should prepare paragraph style request with range."""
        op_dict = {
            "start_index": 1,
            "end_index": 55,
            "alignment": "CENTER",
            "named_style_type": "TITLE",
        }

        request = _prepare_apply_paragraph_style_request(op_dict, None, None)

        assert "updateParagraphStyle" in request
        assert request["updateParagraphStyle"]["range"]["startIndex"] == 1
        assert request["updateParagraphStyle"]["range"]["endIndex"] == 55
        assert request["updateParagraphStyle"]["paragraphStyle"]["alignment"] == "CENTER"
        assert request["updateParagraphStyle"]["paragraphStyle"]["namedStyleType"] == "TITLE"
        assert "tabId" not in request["updateParagraphStyle"]["range"]

    def test_paragraph_style_with_tab_id(self):
        """Should include tab_id in range when provided."""
        op_dict = {
            "start_index": 1,
            "end_index": 55,
            "alignment": "CENTER",
            "tab_id": "tab123",
        }

        request = _prepare_apply_paragraph_style_request(op_dict, None, None)

        assert request["updateParagraphStyle"]["range"]["tabId"] == "tab123"

    def test_paragraph_style_with_default_tab_id(self):
        """Should use default tab_id when not specified in operation."""
        op_dict = {
            "start_index": 1,
            "end_index": 55,
            "alignment": "CENTER",
        }

        request = _prepare_apply_paragraph_style_request(op_dict, None, "default_tab")

        assert request["updateParagraphStyle"]["range"]["tabId"] == "default_tab"

    def test_paragraph_style_operation_overrides_default_tab_id(self):
        """Should use operation tab_id over default."""
        op_dict = {
            "start_index": 1,
            "end_index": 55,
            "alignment": "CENTER",
            "tab_id": "op_tab",
        }

        request = _prepare_apply_paragraph_style_request(op_dict, None, "default_tab")

        assert request["updateParagraphStyle"]["range"]["tabId"] == "op_tab"

    def test_paragraph_style_with_spacing(self):
        """Should handle paragraph spacing."""
        op_dict = {
            "start_index": 1,
            "end_index": 55,
            "space_above": 36.0,
            "space_below": 18.0,
        }

        request = _prepare_apply_paragraph_style_request(op_dict, None, None)

        assert "spaceAbove" in request["updateParagraphStyle"]["paragraphStyle"]
        assert "spaceBelow" in request["updateParagraphStyle"]["paragraphStyle"]

    def test_paragraph_style_with_indentation(self):
        """Should handle paragraph indentation."""
        op_dict = {
            "start_index": 1,
            "end_index": 55,
            "indent_start": 36.0,
            "indent_end": 18.0,
        }

        request = _prepare_apply_paragraph_style_request(op_dict, None, None)

        assert "indentStart" in request["updateParagraphStyle"]["paragraphStyle"]
        assert "indentEnd" in request["updateParagraphStyle"]["paragraphStyle"]

    def test_paragraph_style_missing_range(self):
        """Should raise error when range is not provided and no other targeting method."""
        op_dict = {
            "alignment": "CENTER",
        }

        with pytest.raises(ToolError) as exc_info:
            _prepare_apply_paragraph_style_request(op_dict, None, None)

        assert "start_index" in str(exc_info.value) or "end_index" in str(exc_info.value) or "text_to_find" in str(exc_info.value)

    @patch("google_docs_mcp.api.helpers.get_paragraph_range_from_document")
    @patch("google_docs_mcp.api.helpers.find_text_range")
    @patch("google_docs_mcp.api.documents.get_docs_client")
    def test_paragraph_style_by_text_search(self, mock_get_docs, mock_find_text, mock_get_para):
        """Should find text, locate containing paragraph, and apply styling."""
        from google_docs_mcp.types import TextRange

        # Mock finding text
        mock_find_text.return_value = TextRange(start_index=10, end_index=20)

        # Mock finding paragraph (returns TextRange with paragraph boundaries)
        mock_get_para.return_value = TextRange(start_index=1, end_index=55)

        document = {"documentId": "doc123"}
        op_dict = {
            "text_to_find": "Title Text",
            "alignment": "CENTER",
            "named_style_type": "TITLE",
        }

        request = _prepare_apply_paragraph_style_request(op_dict, document, None)

        # Should apply to the paragraph range, not the text range
        assert request["updateParagraphStyle"]["range"]["startIndex"] == 1
        assert request["updateParagraphStyle"]["range"]["endIndex"] == 55
        assert request["updateParagraphStyle"]["paragraphStyle"]["alignment"] == "CENTER"

    @patch("google_docs_mcp.api.helpers.get_paragraph_range_from_document")
    def test_paragraph_style_by_index(self, mock_get_para):
        """Should find paragraph containing index and apply styling."""
        from google_docs_mcp.types import TextRange

        # Mock finding paragraph (returns TextRange with paragraph boundaries)
        mock_get_para.return_value = TextRange(start_index=1, end_index=55)

        document = {"documentId": "doc123"}
        op_dict = {
            "index_within_paragraph": 25,
            "alignment": "CENTER",
        }

        request = _prepare_apply_paragraph_style_request(op_dict, document, None)

        assert request["updateParagraphStyle"]["range"]["startIndex"] == 1
        assert request["updateParagraphStyle"]["range"]["endIndex"] == 55
