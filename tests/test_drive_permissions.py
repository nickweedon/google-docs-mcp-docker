"""Tests for Google Drive permissions handling when inserting images."""

import pytest
from unittest.mock import MagicMock, patch, call
from google_docs_mcp.api.helpers import insert_inline_image
from google_docs_mcp.api.documents import _prepare_insert_image_request
from fastmcp.exceptions import ToolError


class TestDrivePermissionsInHelpers:
    """Test that Drive permissions are set when inserting images via helpers."""

    @patch('google_docs_mcp.auth.get_drive_client')
    @patch('google_docs_mcp.api.helpers._validate_image_url')
    @patch('google_docs_mcp.api.helpers.execute_batch_update_sync')
    def test_insert_image_sets_drive_permissions(
        self, mock_execute, mock_validate, mock_get_drive
    ):
        """Test that inserting a Drive image sets public permissions."""
        # Setup
        mock_docs = MagicMock()
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive

        url = "https://drive.google.com/uc?export=download&id=test123"

        # Execute
        insert_inline_image(mock_docs, "doc123", url, 1, 100, 100)

        # Verify Drive permissions were set
        mock_get_drive.assert_called_once()
        mock_drive.permissions().create.assert_called_once()

        # Check the permission structure
        call_args = mock_drive.permissions().create.call_args
        assert call_args[1]['fileId'] == 'test123'
        assert call_args[1]['body'] == {
            'type': 'anyone',
            'role': 'reader'
        }

        # Verify the permission was executed
        mock_drive.permissions().create().execute.assert_called_once()

    @patch('google_docs_mcp.auth.get_drive_client')
    @patch('google_docs_mcp.api.helpers._validate_image_url')
    @patch('google_docs_mcp.api.helpers.execute_batch_update_sync')
    def test_insert_image_handles_permission_failure(
        self, mock_execute, mock_validate, mock_get_drive
    ):
        """Test that permission failures raise helpful errors."""
        # Setup
        mock_docs = MagicMock()
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive

        # Make permissions().create() raise an error
        mock_drive.permissions().create().execute.side_effect = Exception("Permission denied")

        url = "https://drive.google.com/uc?export=download&id=test123"

        # Execute and verify error
        with pytest.raises(ToolError) as exc_info:
            insert_inline_image(mock_docs, "doc123", url, 1)

        error_msg = str(exc_info.value)
        assert "Failed to set public permissions" in error_msg
        assert "test123" in error_msg

    @patch('google_docs_mcp.api.helpers._validate_image_url')
    @patch('google_docs_mcp.api.helpers.execute_batch_update_sync')
    def test_insert_image_skips_permissions_for_non_drive_urls(
        self, mock_execute, mock_validate
    ):
        """Test that non-Drive URLs don't trigger permission logic."""
        mock_docs = MagicMock()
        url = "https://example.com/image.jpg"

        # Execute
        insert_inline_image(mock_docs, "doc123", url, 1)

        # Verify validation was called but no Drive client was needed
        mock_validate.assert_called_once_with(url)
        mock_execute.assert_called_once()


class TestDrivePermissionsInBulkOperations:
    """Test that Drive permissions are set when preparing bulk operations."""

    @patch('google_docs_mcp.api.documents.get_drive_client')
    @patch('google_docs_mcp.api.helpers._validate_image_url')
    def test_prepare_insert_image_sets_drive_permissions(
        self, mock_validate, mock_get_drive
    ):
        """Test that preparing a Drive image insert sets public permissions."""
        # Setup
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive

        op_dict = {
            "image_url": "https://drive.google.com/uc?export=download&id=bulk456",
            "index": 10,
            "width": 200,
            "height": 150
        }

        # Execute
        request = _prepare_insert_image_request(op_dict)

        # Verify Drive permissions were set
        mock_get_drive.assert_called_once()
        mock_drive.permissions().create.assert_called_once()

        # Check the permission structure
        call_args = mock_drive.permissions().create.call_args
        assert call_args[1]['fileId'] == 'bulk456'
        assert call_args[1]['body'] == {
            'type': 'anyone',
            'role': 'reader'
        }

        # Verify the request structure
        assert request['insertInlineImage']['uri'] == op_dict['image_url']
        assert request['insertInlineImage']['location']['index'] == 10
        assert request['insertInlineImage']['objectSize']['width']['magnitude'] == 200
        assert request['insertInlineImage']['objectSize']['height']['magnitude'] == 150

    @patch('google_docs_mcp.api.documents.get_drive_client')
    @patch('google_docs_mcp.api.helpers._validate_image_url')
    def test_prepare_insert_image_handles_permission_failure(
        self, mock_validate, mock_get_drive
    ):
        """Test that permission failures in bulk operations raise helpful errors."""
        # Setup
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive

        # Make permissions().create() raise an error
        mock_drive.permissions().create().execute.side_effect = Exception("403 Forbidden")

        op_dict = {
            "image_url": "https://drive.google.com/uc?export=download&id=bulk456",
            "index": 10
        }

        # Execute and verify error
        with pytest.raises(ToolError) as exc_info:
            _prepare_insert_image_request(op_dict)

        error_msg = str(exc_info.value)
        assert "Failed to set public permissions" in error_msg
        assert "bulk456" in error_msg

    @patch('google_docs_mcp.api.helpers._validate_image_url')
    def test_prepare_insert_image_skips_permissions_for_non_drive_urls(
        self, mock_validate
    ):
        """Test that non-Drive URLs in bulk ops don't trigger permission logic."""
        op_dict = {
            "image_url": "https://example.com/image.png",
            "index": 5
        }

        # Execute
        request = _prepare_insert_image_request(op_dict)

        # Verify validation was called
        mock_validate.assert_called_once_with(op_dict['image_url'])

        # Verify the request was created correctly
        assert request['insertInlineImage']['uri'] == op_dict['image_url']
        assert request['insertInlineImage']['location']['index'] == 5

    @patch('google_docs_mcp.api.documents.get_drive_client')
    @patch('google_docs_mcp.api.helpers._validate_image_url')
    def test_prepare_handles_drive_url_without_id_parameter(
        self, mock_validate, mock_get_drive
    ):
        """Test that Drive URLs without proper ID format are handled gracefully."""
        # Setup - URL without proper ?id= format
        op_dict = {
            "image_url": "https://drive.google.com/file/d/123/view",
            "index": 5
        }

        # Execute - should not crash even if ID extraction fails
        request = _prepare_insert_image_request(op_dict)

        # Drive client should not be called if no ID was found
        mock_get_drive.assert_not_called()

        # Request should still be created
        assert request['insertInlineImage']['uri'] == op_dict['image_url']
