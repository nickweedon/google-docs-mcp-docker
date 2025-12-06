"""
Tests for bulk operations functionality.

Tests the bulk_update_document function and associated helper functions.
"""

import pytest
from unittest.mock import MagicMock, patch

from google_docs_mcp.api.documents import (
    bulk_update_document,
    _prepare_insert_text_request,
    _prepare_delete_range_request,
    _prepare_insert_table_request,
    _prepare_insert_page_break_request,
    _prepare_insert_image_request,
    _prepare_apply_text_style_request,
    _prepare_apply_paragraph_style_request,
)
from google_docs_mcp.api.helpers import chunk_requests
from fastmcp.exceptions import ToolError


class TestChunkRequests:
    """Tests for the chunk_requests helper function."""

    def test_chunk_requests_within_limit(self):
        """Should not chunk when requests are within limit."""
        requests = [{"request": i} for i in range(30)]
        chunks = chunk_requests(requests, chunk_size=50)

        assert len(chunks) == 1
        assert len(chunks[0]) == 30

    def test_chunk_requests_exactly_at_limit(self):
        """Should create one chunk when exactly at limit."""
        requests = [{"request": i} for i in range(50)]
        chunks = chunk_requests(requests, chunk_size=50)

        assert len(chunks) == 1
        assert len(chunks[0]) == 50

    def test_chunk_requests_over_limit(self):
        """Should split into multiple chunks when over limit."""
        requests = [{"request": i} for i in range(75)]
        chunks = chunk_requests(requests, chunk_size=50)

        assert len(chunks) == 2
        assert len(chunks[0]) == 50
        assert len(chunks[1]) == 25

    def test_chunk_requests_many_chunks(self):
        """Should handle many chunks correctly."""
        requests = [{"request": i} for i in range(123)]
        chunks = chunk_requests(requests, chunk_size=50)

        assert len(chunks) == 3
        assert len(chunks[0]) == 50
        assert len(chunks[1]) == 50
        assert len(chunks[2]) == 23

    def test_chunk_requests_empty_list(self):
        """Should handle empty list."""
        requests = []
        chunks = chunk_requests(requests, chunk_size=50)

        assert len(chunks) == 0

    def test_chunk_requests_custom_size(self):
        """Should respect custom chunk size."""
        requests = [{"request": i} for i in range(25)]
        chunks = chunk_requests(requests, chunk_size=10)

        assert len(chunks) == 3
        assert len(chunks[0]) == 10
        assert len(chunks[1]) == 10
        assert len(chunks[2]) == 5

    def test_chunk_requests_invalid_size(self):
        """Should raise error for invalid chunk size."""
        requests = [{"request": i} for i in range(10)]

        with pytest.raises(ValueError):
            chunk_requests(requests, chunk_size=0)

        with pytest.raises(ValueError):
            chunk_requests(requests, chunk_size=-1)


class TestPrepareInsertTextRequest:
    """Tests for _prepare_insert_text_request function."""

    def test_basic_insert_text(self):
        """Should prepare basic insert text request."""
        op_dict = {"text": "Hello World", "index": 1}
        request = _prepare_insert_text_request(op_dict, None)

        assert request == {
            "insertText": {"text": "Hello World", "location": {"index": 1}}
        }

    def test_insert_text_with_tab_id(self):
        """Should include tab_id when provided."""
        op_dict = {"text": "Hello", "index": 5, "tab_id": "tab123"}
        request = _prepare_insert_text_request(op_dict, None)

        assert request["insertText"]["location"]["tabId"] == "tab123"

    def test_insert_text_with_default_tab_id(self):
        """Should use default tab_id when not specified in operation."""
        op_dict = {"text": "Hello", "index": 5}
        request = _prepare_insert_text_request(op_dict, "default_tab")

        assert request["insertText"]["location"]["tabId"] == "default_tab"

    def test_insert_text_operation_overrides_default(self):
        """Should use operation tab_id over default."""
        op_dict = {"text": "Hello", "index": 5, "tab_id": "op_tab"}
        request = _prepare_insert_text_request(op_dict, "default_tab")

        assert request["insertText"]["location"]["tabId"] == "op_tab"


class TestPrepareDeleteRangeRequest:
    """Tests for _prepare_delete_range_request function."""

    def test_basic_delete_range(self):
        """Should prepare basic delete range request."""
        op_dict = {"start_index": 1, "end_index": 10}
        request = _prepare_delete_range_request(op_dict, None)

        assert request == {
            "deleteContentRange": {
                "range": {"startIndex": 1, "endIndex": 10}
            }
        }

    def test_delete_range_with_tab_id(self):
        """Should include tab_id when provided."""
        op_dict = {"start_index": 1, "end_index": 10, "tab_id": "tab123"}
        request = _prepare_delete_range_request(op_dict, None)

        assert request["deleteContentRange"]["range"]["tabId"] == "tab123"

    def test_delete_range_invalid_indices(self):
        """Should raise error when end_index <= start_index."""
        op_dict = {"start_index": 10, "end_index": 10}

        with pytest.raises(ToolError) as exc_info:
            _prepare_delete_range_request(op_dict, None)

        assert "end_index" in str(exc_info.value)
        assert "start_index" in str(exc_info.value)

    def test_delete_range_reversed_indices(self):
        """Should raise error when indices are reversed."""
        op_dict = {"start_index": 20, "end_index": 10}

        with pytest.raises(ToolError):
            _prepare_delete_range_request(op_dict, None)


class TestPrepareInsertTableRequest:
    """Tests for _prepare_insert_table_request function."""

    def test_basic_insert_table(self):
        """Should prepare basic table insert request."""
        op_dict = {"rows": 3, "columns": 2, "index": 1}
        request = _prepare_insert_table_request(op_dict)

        assert request == {
            "insertTable": {"rows": 3, "columns": 2, "location": {"index": 1}}
        }

    def test_insert_table_invalid_rows(self):
        """Should raise error for invalid row count."""
        op_dict = {"rows": 0, "columns": 2, "index": 1}

        with pytest.raises(ToolError) as exc_info:
            _prepare_insert_table_request(op_dict)

        assert "at least 1 row" in str(exc_info.value)

    def test_insert_table_invalid_columns(self):
        """Should raise error for invalid column count."""
        op_dict = {"rows": 2, "columns": 0, "index": 1}

        with pytest.raises(ToolError) as exc_info:
            _prepare_insert_table_request(op_dict)

        assert "at least 1" in str(exc_info.value)


class TestPrepareInsertPageBreakRequest:
    """Tests for _prepare_insert_page_break_request function."""

    def test_basic_insert_page_break(self):
        """Should prepare page break insert request."""
        op_dict = {"index": 10}
        request = _prepare_insert_page_break_request(op_dict)

        assert request == {"insertPageBreak": {"location": {"index": 10}}}


class TestPrepareInsertImageRequest:
    """Tests for _prepare_insert_image_request function."""

    @patch('urllib.request.urlopen')
    def test_basic_insert_image(self, mock_urlopen):
        """Should prepare basic image insert request."""
        # Mock URL validation
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers.get.return_value = 'image/png'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        op_dict = {
            "image_url": "https://example.com/image.png",
            "index": 1,
        }
        request = _prepare_insert_image_request(op_dict)

        assert request["insertInlineImage"]["uri"] == "https://example.com/image.png"
        assert request["insertInlineImage"]["location"]["index"] == 1
        assert "objectSize" not in request["insertInlineImage"]

    @patch('urllib.request.urlopen')
    def test_insert_image_with_dimensions(self, mock_urlopen):
        """Should include dimensions when provided."""
        # Mock URL validation
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers.get.return_value = 'image/png'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        op_dict = {
            "image_url": "https://example.com/image.png",
            "index": 1,
            "width": 200,
            "height": 150,
        }
        request = _prepare_insert_image_request(op_dict)

        assert "objectSize" in request["insertInlineImage"]
        assert request["insertInlineImage"]["objectSize"]["width"]["magnitude"] == 200
        assert request["insertInlineImage"]["objectSize"]["height"]["magnitude"] == 150

    def test_insert_image_missing_url(self):
        """Should raise error when image_url is missing."""
        op_dict = {"index": 1}

        with pytest.raises(ToolError) as exc_info:
            _prepare_insert_image_request(op_dict)

        assert "image_url is required" in str(exc_info.value)

    def test_insert_image_invalid_url(self):
        """Should raise error for invalid URL."""
        op_dict = {"image_url": "not-a-url", "index": 1}

        with pytest.raises(ToolError) as exc_info:
            _prepare_insert_image_request(op_dict)

        assert "Invalid image URL" in str(exc_info.value)


class TestBulkUpdateDocument:
    """Tests for bulk_update_document function."""

    @patch("google_docs_mcp.api.documents.get_docs_client")
    def test_empty_operations(self, mock_get_docs):
        """Should handle empty operations list."""
        result = bulk_update_document("doc123", [])

        assert "No operations" in result
        mock_get_docs.assert_called_once()

    @patch("google_docs_mcp.api.documents.get_docs_client")
    def test_too_many_operations(self, mock_get_docs):
        """Should reject too many operations."""
        operations = [{"type": "insert_text", "text": "x", "index": 1}] * 501

        with pytest.raises(ToolError) as exc_info:
            bulk_update_document("doc123", operations)

        assert "Too many operations" in str(exc_info.value)
        assert "500" in str(exc_info.value)

    @patch("google_docs_mcp.api.documents.helpers.execute_batch_update_sync")
    @patch("google_docs_mcp.api.documents.get_docs_client")
    def test_single_insert_text_operation(self, mock_get_docs, mock_execute_batch):
        """Should execute single insert_text operation."""
        mock_execute_batch.return_value = {}

        operations = [{"type": "insert_text", "text": "Hello", "index": 1}]

        result = bulk_update_document("doc123", operations)

        assert "Successfully executed 1 operations" in result
        assert "1× insert_text" in result
        mock_execute_batch.assert_called_once()

        # Verify the request structure
        call_args = mock_execute_batch.call_args
        requests = call_args[0][2]  # Third argument is the requests list
        assert len(requests) == 1
        assert "insertText" in requests[0]

    @patch("google_docs_mcp.api.documents.helpers.execute_batch_update_sync")
    @patch("google_docs_mcp.api.documents.get_docs_client")
    def test_multiple_mixed_operations(self, mock_get_docs, mock_execute_batch):
        """Should execute multiple mixed operations."""
        mock_execute_batch.return_value = {}

        operations = [
            {"type": "insert_text", "text": "Title\n", "index": 1},
            {"type": "insert_table", "rows": 2, "columns": 3, "index": 7},
            {"type": "insert_page_break", "index": 20},
        ]

        result = bulk_update_document("doc123", operations)

        assert "Successfully executed 3 operations" in result
        assert "1× insert_page_break" in result
        assert "1× insert_table" in result
        assert "1× insert_text" in result

        # Verify batch update was called once (all operations fit in one batch)
        mock_execute_batch.assert_called_once()

        # Verify the requests
        call_args = mock_execute_batch.call_args
        requests = call_args[0][2]
        assert len(requests) == 3

    @patch("google_docs_mcp.api.documents.helpers.execute_batch_update_sync")
    @patch("google_docs_mcp.api.documents.get_docs_client")
    def test_operations_exceeding_batch_limit(self, mock_get_docs, mock_execute_batch):
        """Should split operations into multiple batches when exceeding 50 requests."""
        mock_execute_batch.return_value = {}

        # Create 75 operations
        operations = [
            {"type": "insert_text", "text": f"Text {i}", "index": i + 1}
            for i in range(75)
        ]

        result = bulk_update_document("doc123", operations)

        assert "Successfully executed 75 operations" in result
        assert "2 batch(es)" in result

        # Verify batch update was called twice
        assert mock_execute_batch.call_count == 2

        # First batch should have 50 requests
        first_call_requests = mock_execute_batch.call_args_list[0][0][2]
        assert len(first_call_requests) == 50

        # Second batch should have 25 requests
        second_call_requests = mock_execute_batch.call_args_list[1][0][2]
        assert len(second_call_requests) == 25

    @patch("google_docs_mcp.api.documents.get_docs_client")
    def test_unknown_operation_type(self, mock_get_docs):
        """Should raise error for unknown operation type."""
        operations = [{"type": "unknown_operation", "data": "something"}]

        with pytest.raises(ToolError) as exc_info:
            bulk_update_document("doc123", operations)

        assert "Unknown operation type" in str(exc_info.value)
        assert "unknown_operation" in str(exc_info.value)

    @patch("google_docs_mcp.api.documents.get_docs_client")
    def test_missing_operation_type(self, mock_get_docs):
        """Should raise error when operation is missing type field."""
        operations = [{"text": "Hello", "index": 1}]

        with pytest.raises(ToolError) as exc_info:
            bulk_update_document("doc123", operations)

        assert "missing 'type' field" in str(exc_info.value)

    @patch("google_docs_mcp.api.documents.helpers.execute_batch_update_sync")
    @patch("google_docs_mcp.api.documents.get_docs_client")
    def test_operation_with_default_tab_id(self, mock_get_docs, mock_execute_batch):
        """Should apply default tab_id to operations without explicit tab_id."""
        mock_execute_batch.return_value = {}

        operations = [{"type": "insert_text", "text": "Hello", "index": 1}]

        result = bulk_update_document("doc123", operations, default_tab_id="tab_default")

        # Verify the request includes the default tab_id
        call_args = mock_execute_batch.call_args
        requests = call_args[0][2]
        assert requests[0]["insertText"]["location"]["tabId"] == "tab_default"

    @patch("google_docs_mcp.api.documents.helpers.execute_batch_update_sync")
    @patch("google_docs_mcp.api.documents.get_docs_client")
    def test_delete_range_operation(self, mock_get_docs, mock_execute_batch):
        """Should execute delete_range operation."""
        mock_execute_batch.return_value = {}

        operations = [{"type": "delete_range", "start_index": 5, "end_index": 15}]

        result = bulk_update_document("doc123", operations)

        assert "Successfully executed 1 operations" in result
        assert "1× delete_range" in result

        # Verify the request
        call_args = mock_execute_batch.call_args
        requests = call_args[0][2]
        assert "deleteContentRange" in requests[0]
        assert requests[0]["deleteContentRange"]["range"]["startIndex"] == 5
        assert requests[0]["deleteContentRange"]["range"]["endIndex"] == 15

    @patch("google_docs_mcp.api.documents.helpers.execute_batch_update_sync")
    @patch("google_docs_mcp.api.documents.get_docs_client")
    def test_operation_count_grouping(self, mock_get_docs, mock_execute_batch):
        """Should correctly group and count operation types in summary."""
        mock_execute_batch.return_value = {}

        operations = [
            {"type": "insert_text", "text": "A", "index": 1},
            {"type": "insert_text", "text": "B", "index": 2},
            {"type": "insert_text", "text": "C", "index": 3},
            {"type": "insert_table", "rows": 2, "columns": 2, "index": 10},
            {"type": "insert_table", "rows": 3, "columns": 3, "index": 20},
        ]

        result = bulk_update_document("doc123", operations)

        assert "Successfully executed 5 operations" in result
        assert "3× insert_text" in result
        assert "2× insert_table" in result
