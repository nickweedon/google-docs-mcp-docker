"""Tests for new bulk operation preparation functions in api/documents.py."""

import pytest
from fastmcp.exceptions import ToolError
from unittest.mock import patch, MagicMock

# Import the preparation functions from documents module
from google_docs_mcp.api.documents import (
    _prepare_create_bullet_list_request,
    _prepare_replace_all_text_request,
    _prepare_insert_table_row_request,
    _prepare_delete_table_row_request,
    _prepare_insert_table_column_request,
    _prepare_delete_table_column_request,
    _prepare_update_table_cell_style_request,
    _prepare_merge_table_cells_request,
    _prepare_unmerge_table_cells_request,
    _prepare_create_named_range_request,
    _prepare_delete_named_range_request,
    _prepare_insert_footnote_request,
    _prepare_insert_table_of_contents_request,
    _prepare_insert_horizontal_rule_request,
    _prepare_insert_section_break_request,
)


class TestCreateBulletListPrepFunction:
    """Tests for _prepare_create_bullet_list_request function."""

    def test_prepare_basic_bullet_list(self):
        """Test preparing a basic bullet list request."""
        op_dict = {
            "start_index": 10,
            "end_index": 50,
            "list_type": "UNORDERED",
            "nesting_level": 0,
        }

        request = _prepare_create_bullet_list_request(op_dict, None)

        assert "createParagraphBullets" in request
        assert request["createParagraphBullets"]["range"]["startIndex"] == 10
        assert request["createParagraphBullets"]["range"]["endIndex"] == 50

    def test_prepare_bullet_list_with_tab(self):
        """Test preparing bullet list request with tab ID."""
        op_dict = {
            "start_index": 1,
            "end_index": 20,
            "list_type": "ORDERED_DECIMAL",
            "tab_id": "tab123",
        }

        request = _prepare_create_bullet_list_request(op_dict, "default_tab")

        assert request["createParagraphBullets"]["range"]["tabId"] == "tab123"

    def test_prepare_bullet_list_default_tab(self):
        """Test preparing bullet list with default tab."""
        op_dict = {"start_index": 1, "end_index": 10}

        request = _prepare_create_bullet_list_request(op_dict, "default_tab")

        assert request["createParagraphBullets"]["range"]["tabId"] == "default_tab"


class TestReplaceAllTextPrepFunction:
    """Tests for _prepare_replace_all_text_request function."""

    def test_prepare_replace_all_text_basic(self):
        """Test preparing basic replace all text request."""
        op_dict = {"find_text": "old", "replace_text": "new", "match_case": True}

        request = _prepare_replace_all_text_request(op_dict, None)

        assert "replaceAllText" in request
        assert request["replaceAllText"]["containsText"]["text"] == "old"
        assert request["replaceAllText"]["replaceText"] == "new"
        assert request["replaceAllText"]["containsText"]["matchCase"] is True

    def test_prepare_replace_all_text_case_insensitive(self):
        """Test preparing case-insensitive replace request."""
        op_dict = {"find_text": "Test", "replace_text": "TEST", "match_case": False}

        request = _prepare_replace_all_text_request(op_dict, None)

        assert request["replaceAllText"]["containsText"]["matchCase"] is False

    def test_prepare_replace_all_text_missing_find_text(self):
        """Test error when find_text is missing."""
        op_dict = {"replace_text": "new"}

        with pytest.raises(ToolError, match="find_text is required"):
            _prepare_replace_all_text_request(op_dict, None)


class TestTableRowPrepFunctions:
    """Tests for table row operation preparation functions."""

    def test_prepare_insert_table_row(self):
        """Test preparing insert table row request."""
        op_dict = {
            "table_start_index": 100,
            "row_index": 2,
            "insert_below": False,
        }

        request = _prepare_insert_table_row_request(op_dict)

        assert "insertTableRow" in request
        assert (
            request["insertTableRow"]["tableCellLocation"]["tableStartLocation"][
                "index"
            ]
            == 100
        )
        assert request["insertTableRow"]["tableCellLocation"]["rowIndex"] == 2
        assert request["insertTableRow"]["insertBelow"] is False

    def test_prepare_delete_table_row(self):
        """Test preparing delete table row request."""
        op_dict = {"table_start_index": 100, "row_index": 3}

        request = _prepare_delete_table_row_request(op_dict)

        assert "deleteTableRow" in request
        assert (
            request["deleteTableRow"]["tableCellLocation"]["tableStartLocation"][
                "index"
            ]
            == 100
        )
        assert request["deleteTableRow"]["tableCellLocation"]["rowIndex"] == 3


class TestTableColumnPrepFunctions:
    """Tests for table column operation preparation functions."""

    def test_prepare_insert_table_column(self):
        """Test preparing insert table column request."""
        op_dict = {
            "table_start_index": 100,
            "column_index": 1,
            "insert_right": False,
        }

        request = _prepare_insert_table_column_request(op_dict)

        assert "insertTableColumn" in request
        assert request["insertTableColumn"]["tableCellLocation"]["columnIndex"] == 1
        assert request["insertTableColumn"]["insertRight"] is False

    def test_prepare_delete_table_column(self):
        """Test preparing delete table column request."""
        op_dict = {"table_start_index": 100, "column_index": 2}

        request = _prepare_delete_table_column_request(op_dict)

        assert "deleteTableColumn" in request
        assert request["deleteTableColumn"]["tableCellLocation"]["columnIndex"] == 2


class TestTableCellStylePrepFunction:
    """Tests for _prepare_update_table_cell_style_request function."""

    def test_prepare_cell_style_with_background(self):
        """Test preparing cell style update with background color."""
        op_dict = {
            "table_start_index": 100,
            "row_index": 1,
            "column_index": 2,
            "background_color": "#FF0000",
        }

        request = _prepare_update_table_cell_style_request(op_dict)

        assert "updateTableCellStyle" in request
        assert "backgroundColor" in request["updateTableCellStyle"]["tableCellStyle"]

    def test_prepare_cell_style_with_padding(self):
        """Test preparing cell style update with padding."""
        op_dict = {
            "table_start_index": 100,
            "row_index": 0,
            "column_index": 0,
            "padding_top": 10.0,
            "padding_bottom": 10.0,
        }

        request = _prepare_update_table_cell_style_request(op_dict)

        assert "paddingTop" in request["updateTableCellStyle"]["tableCellStyle"]
        assert "paddingBottom" in request["updateTableCellStyle"]["tableCellStyle"]

    def test_prepare_cell_style_no_styles(self):
        """Test when no style properties provided."""
        op_dict = {"table_start_index": 100, "row_index": 0, "column_index": 0}

        request = _prepare_update_table_cell_style_request(op_dict)

        assert request is None


class TestTableCellMergingPrepFunctions:
    """Tests for table cell merging preparation functions."""

    def test_prepare_merge_table_cells(self):
        """Test preparing merge cells request."""
        op_dict = {
            "table_start_index": 100,
            "start_row": 0,
            "start_column": 0,
            "row_span": 2,
            "column_span": 3,
        }

        request = _prepare_merge_table_cells_request(op_dict)

        assert "mergeTableCells" in request
        table_range = request["mergeTableCells"]["tableRange"]
        assert table_range["tableCellLocation"]["rowIndex"] == 0
        assert table_range["tableCellLocation"]["columnIndex"] == 0
        assert table_range["rowSpan"] == 2
        assert table_range["columnSpan"] == 3

    def test_prepare_unmerge_table_cells(self):
        """Test preparing unmerge cells request."""
        op_dict = {"table_start_index": 100, "row_index": 1, "column_index": 1}

        request = _prepare_unmerge_table_cells_request(op_dict)

        assert "unmergeTableCells" in request
        location = request["unmergeTableCells"]["tableCellLocation"]
        assert location["rowIndex"] == 1
        assert location["columnIndex"] == 1


class TestNamedRangePrepFunctions:
    """Tests for named range preparation functions."""

    def test_prepare_create_named_range(self):
        """Test preparing create named range request."""
        op_dict = {"name": "section1", "start_index": 10, "end_index": 50}

        request = _prepare_create_named_range_request(op_dict, None)

        assert "createNamedRange" in request
        assert request["createNamedRange"]["name"] == "section1"
        assert request["createNamedRange"]["range"]["startIndex"] == 10
        assert request["createNamedRange"]["range"]["endIndex"] == 50

    def test_prepare_create_named_range_missing_name(self):
        """Test error when name is missing."""
        op_dict = {"start_index": 10, "end_index": 50}

        with pytest.raises(ToolError, match="name is required"):
            _prepare_create_named_range_request(op_dict, None)

    def test_prepare_delete_named_range(self):
        """Test preparing delete named range request."""
        op_dict = {"named_range_id": "range123"}

        request = _prepare_delete_named_range_request(op_dict)

        assert "deleteNamedRange" in request
        assert request["deleteNamedRange"]["namedRangeId"] == "range123"

    def test_prepare_delete_named_range_missing_id(self):
        """Test error when range ID is missing."""
        op_dict = {}

        with pytest.raises(ToolError, match="named_range_id is required"):
            _prepare_delete_named_range_request(op_dict)


class TestContentElementPrepFunctions:
    """Tests for content element preparation functions."""

    def test_prepare_insert_footnote(self):
        """Test preparing insert footnote request."""
        op_dict = {"index": 50, "footnote_text": "This is a footnote"}

        request = _prepare_insert_footnote_request(op_dict)

        assert "insertInlineImage" in request
        assert request["insertInlineImage"]["location"]["index"] == 50
        assert request["insertInlineImage"]["footnoteText"] == "This is a footnote"

    def test_prepare_insert_table_of_contents(self):
        """Test preparing insert TOC request."""
        op_dict = {"index": 10}

        request = _prepare_insert_table_of_contents_request(op_dict)

        assert "insertTableOfContents" in request
        assert request["insertTableOfContents"]["location"]["index"] == 10

    def test_prepare_insert_horizontal_rule(self):
        """Test preparing insert horizontal rule request."""
        op_dict = {"index": 25}

        request = _prepare_insert_horizontal_rule_request(op_dict)

        assert "insertHorizontalRule" in request
        assert request["insertHorizontalRule"]["location"]["index"] == 25

    def test_prepare_insert_section_break(self):
        """Test preparing insert section break request."""
        op_dict = {"index": 100, "section_type": "NEXT_PAGE"}

        request = _prepare_insert_section_break_request(op_dict)

        assert "insertSectionBreak" in request
        assert request["insertSectionBreak"]["location"]["index"] == 100
        assert request["insertSectionBreak"]["sectionType"] == "NEXT_PAGE"
