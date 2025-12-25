"""Tests for new helper functions in api/helpers.py."""

import pytest
from src.google_docs_mcp.api import helpers
from src.google_docs_mcp.types import TableInfo


class TestListHelpers:
    """Tests for list and bullet helper functions."""

    def test_build_create_paragraph_bullets_request_unordered(self):
        """Test building createParagraphBullets request for unordered list."""
        request = helpers.build_create_paragraph_bullets_request(
            start_index=10,
            end_index=50,
            list_type="UNORDERED",
            nesting_level=0,
        )

        assert "createParagraphBullets" in request
        assert request["createParagraphBullets"]["range"]["startIndex"] == 10
        assert request["createParagraphBullets"]["range"]["endIndex"] == 50
        assert request["createParagraphBullets"]["bulletPreset"] == "BULLET_DISC_CIRCLE_SQUARE"

    def test_build_create_paragraph_bullets_request_ordered(self):
        """Test building createParagraphBullets request for ordered list."""
        request = helpers.build_create_paragraph_bullets_request(
            start_index=1,
            end_index=20,
            list_type="ORDERED_DECIMAL",
            nesting_level=1,
        )

        assert "createParagraphBullets" in request
        assert request["createParagraphBullets"]["bulletPreset"] == "NUMBERED_DECIMAL_ALPHA_ROMAN"

    def test_build_create_paragraph_bullets_request_with_tab(self):
        """Test building request with tab ID."""
        request = helpers.build_create_paragraph_bullets_request(
            start_index=1,
            end_index=10,
            list_type="UNORDERED",
            tab_id="tab123",
        )

        assert request["createParagraphBullets"]["range"]["tabId"] == "tab123"


class TestTextReplaceHelpers:
    """Tests for text replace helper functions."""

    def test_build_replace_all_text_request_basic(self):
        """Test building replaceAllText request."""
        request = helpers.build_replace_all_text_request(
            find_text="old",
            replace_text="new",
            match_case=True,
        )

        assert "replaceAllText" in request
        assert request["replaceAllText"]["containsText"]["text"] == "old"
        assert request["replaceAllText"]["replaceText"] == "new"
        assert request["replaceAllText"]["containsText"]["matchCase"] is True

    def test_build_replace_all_text_request_case_insensitive(self):
        """Test building request with case insensitive matching."""
        request = helpers.build_replace_all_text_request(
            find_text="Test",
            replace_text="TEST",
            match_case=False,
        )

        assert request["replaceAllText"]["containsText"]["matchCase"] is False

    def test_build_replace_all_text_request_with_tab(self):
        """Test building request with tab ID."""
        request = helpers.build_replace_all_text_request(
            find_text="old",
            replace_text="new",
            tab_id="tab456",
        )

        assert request["replaceAllText"]["tabId"] == "tab456"


class TestTableOperationHelpers:
    """Tests for table operation helper functions."""

    def test_build_insert_table_row_request_above(self):
        """Test building insertTableRow request (insert above)."""
        request = helpers.build_insert_table_row_request(
            table_start_index=100,
            row_index=2,
            insert_below=False,
        )

        assert "insertTableRow" in request
        assert request["insertTableRow"]["tableCellLocation"]["tableStartLocation"]["index"] == 100
        assert request["insertTableRow"]["tableCellLocation"]["rowIndex"] == 2
        assert request["insertTableRow"]["insertBelow"] is False

    def test_build_insert_table_row_request_below(self):
        """Test building insertTableRow request (insert below)."""
        request = helpers.build_insert_table_row_request(
            table_start_index=50,
            row_index=1,
            insert_below=True,
        )

        assert request["insertTableRow"]["insertBelow"] is True

    def test_build_delete_table_row_request(self):
        """Test building deleteTableRow request."""
        request = helpers.build_delete_table_row_request(
            table_start_index=100,
            row_index=3,
        )

        assert "deleteTableRow" in request
        assert request["deleteTableRow"]["tableCellLocation"]["tableStartLocation"]["index"] == 100
        assert request["deleteTableRow"]["tableCellLocation"]["rowIndex"] == 3

    def test_build_insert_table_column_request_left(self):
        """Test building insertTableColumn request (insert left)."""
        request = helpers.build_insert_table_column_request(
            table_start_index=100,
            column_index=1,
            insert_right=False,
        )

        assert "insertTableColumn" in request
        assert request["insertTableColumn"]["tableCellLocation"]["columnIndex"] == 1
        assert request["insertTableColumn"]["insertRight"] is False

    def test_build_insert_table_column_request_right(self):
        """Test building insertTableColumn request (insert right)."""
        request = helpers.build_insert_table_column_request(
            table_start_index=100,
            column_index=2,
            insert_right=True,
        )

        assert request["insertTableColumn"]["insertRight"] is True

    def test_build_delete_table_column_request(self):
        """Test building deleteTableColumn request."""
        request = helpers.build_delete_table_column_request(
            table_start_index=100,
            column_index=2,
        )

        assert "deleteTableColumn" in request
        assert request["deleteTableColumn"]["tableCellLocation"]["columnIndex"] == 2

    def test_build_update_table_cell_style_request_background(self):
        """Test building updateTableCellStyle request with background color."""
        request = helpers.build_update_table_cell_style_request(
            table_start_index=100,
            row_index=1,
            column_index=2,
            background_color="#FF0000",
        )

        assert "updateTableCellStyle" in request
        assert "backgroundColor" in request["updateTableCellStyle"]["tableCellStyle"]
        rgb = request["updateTableCellStyle"]["tableCellStyle"]["backgroundColor"]["color"]["rgbColor"]
        assert rgb["red"] == 1.0
        assert rgb["green"] == 0.0
        assert rgb["blue"] == 0.0

    def test_build_update_table_cell_style_request_padding(self):
        """Test building request with padding."""
        request = helpers.build_update_table_cell_style_request(
            table_start_index=100,
            row_index=0,
            column_index=0,
            padding_top=10.0,
            padding_bottom=10.0,
        )

        assert "paddingTop" in request["updateTableCellStyle"]["tableCellStyle"]
        assert request["updateTableCellStyle"]["tableCellStyle"]["paddingTop"]["magnitude"] == 10.0
        assert "paddingTop,paddingBottom" in request["updateTableCellStyle"]["fields"]

    def test_build_update_table_cell_style_request_borders(self):
        """Test building request with borders."""
        request = helpers.build_update_table_cell_style_request(
            table_start_index=100,
            row_index=0,
            column_index=0,
            border_top_color="#000000",
            border_top_width=2.0,
        )

        assert "borderTop" in request["updateTableCellStyle"]["tableCellStyle"]
        border = request["updateTableCellStyle"]["tableCellStyle"]["borderTop"]
        assert border["width"]["magnitude"] == 2.0
        assert border["dashStyle"] == "SOLID"

    def test_build_update_table_cell_style_request_all_borders(self):
        """Test building request with all borders."""
        request = helpers.build_update_table_cell_style_request(
            table_start_index=100,
            row_index=0,
            column_index=0,
            border_top_color="#000000",
            border_top_width=2.0,
            border_bottom_color="#FF0000",
            border_bottom_width=1.0,
            border_left_color="#00FF00",
            border_left_width=1.5,
            border_right_color="#0000FF",
            border_right_width=2.5,
        )

        cell_style = request["updateTableCellStyle"]["tableCellStyle"]
        assert "borderTop" in cell_style
        assert "borderBottom" in cell_style
        assert "borderLeft" in cell_style
        assert "borderRight" in cell_style

    def test_build_update_table_cell_style_request_all_padding(self):
        """Test building request with all padding sides."""
        request = helpers.build_update_table_cell_style_request(
            table_start_index=100,
            row_index=0,
            column_index=0,
            padding_top=10.0,
            padding_bottom=10.0,
            padding_left=5.0,
            padding_right=5.0,
        )

        cell_style = request["updateTableCellStyle"]["tableCellStyle"]
        assert cell_style["paddingTop"]["magnitude"] == 10.0
        assert cell_style["paddingBottom"]["magnitude"] == 10.0
        assert cell_style["paddingLeft"]["magnitude"] == 5.0
        assert cell_style["paddingRight"]["magnitude"] == 5.0
        assert "paddingTop,paddingBottom,paddingLeft,paddingRight" in request["updateTableCellStyle"]["fields"]

    def test_build_update_table_cell_style_request_no_styles(self):
        """Test that None is returned when no styles provided."""
        request = helpers.build_update_table_cell_style_request(
            table_start_index=100,
            row_index=0,
            column_index=0,
        )

        assert request is None

    def test_build_merge_table_cells_request(self):
        """Test building mergeTableCells request."""
        request = helpers.build_merge_table_cells_request(
            table_start_index=100,
            start_row=0,
            start_column=0,
            row_span=2,
            column_span=3,
        )

        assert "mergeTableCells" in request
        table_range = request["mergeTableCells"]["tableRange"]
        assert table_range["tableCellLocation"]["rowIndex"] == 0
        assert table_range["tableCellLocation"]["columnIndex"] == 0
        assert table_range["rowSpan"] == 2
        assert table_range["columnSpan"] == 3

    def test_build_unmerge_table_cells_request(self):
        """Test building unmergeTableCells request."""
        request = helpers.build_unmerge_table_cells_request(
            table_start_index=100,
            row_index=1,
            column_index=1,
        )

        assert "unmergeTableCells" in request
        location = request["unmergeTableCells"]["tableCellLocation"]
        assert location["rowIndex"] == 1
        assert location["columnIndex"] == 1


class TestNamedRangeHelpers:
    """Tests for named range helper functions."""

    def test_build_create_named_range_request_basic(self):
        """Test building createNamedRange request."""
        request = helpers.build_create_named_range_request(
            name="section1",
            start_index=10,
            end_index=50,
        )

        assert "createNamedRange" in request
        assert request["createNamedRange"]["name"] == "section1"
        assert request["createNamedRange"]["range"]["startIndex"] == 10
        assert request["createNamedRange"]["range"]["endIndex"] == 50

    def test_build_create_named_range_request_with_tab(self):
        """Test building request with tab ID."""
        request = helpers.build_create_named_range_request(
            name="section1",
            start_index=1,
            end_index=10,
            tab_id="tab789",
        )

        assert request["createNamedRange"]["range"]["tabId"] == "tab789"

    def test_build_delete_named_range_request(self):
        """Test building deleteNamedRange request."""
        request = helpers.build_delete_named_range_request(
            named_range_id="range123"
        )

        assert "deleteNamedRange" in request
        assert request["deleteNamedRange"]["namedRangeId"] == "range123"


class TestContentElementHelpers:
    """Tests for content element helper functions."""

    def test_build_insert_footnote_request(self):
        """Test building insertFootnote request."""
        request = helpers.build_insert_footnote_request(
            index=50,
            footnote_text="This is a footnote"
        )

        assert "insertInlineImage" in request
        assert request["insertInlineImage"]["location"]["index"] == 50
        assert request["insertInlineImage"]["footnoteText"] == "This is a footnote"

    def test_build_insert_table_of_contents_request(self):
        """Test building insertTableOfContents request."""
        request = helpers.build_insert_table_of_contents_request(index=10)

        assert "insertTableOfContents" in request
        assert request["insertTableOfContents"]["location"]["index"] == 10

    def test_build_insert_horizontal_rule_request(self):
        """Test building insertHorizontalRule request."""
        request = helpers.build_insert_horizontal_rule_request(index=25)

        assert "insertHorizontalRule" in request
        assert request["insertHorizontalRule"]["location"]["index"] == 25

    def test_build_insert_section_break_request_continuous(self):
        """Test building insertSectionBreak request (continuous)."""
        request = helpers.build_insert_section_break_request(
            index=100,
            section_type="CONTINUOUS"
        )

        assert "insertSectionBreak" in request
        assert request["insertSectionBreak"]["location"]["index"] == 100
        assert request["insertSectionBreak"]["sectionType"] == "CONTINUOUS"

    def test_build_insert_section_break_request_next_page(self):
        """Test building insertSectionBreak request (next page)."""
        request = helpers.build_insert_section_break_request(
            index=100,
            section_type="NEXT_PAGE"
        )

        assert request["insertSectionBreak"]["sectionType"] == "NEXT_PAGE"
