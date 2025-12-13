"""
Tests for native markdown import/export functionality.

Tests the Google Drive API native markdown support for both
importing markdown to Google Docs and exporting Google Docs to markdown.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from googleapiclient.http import MediaInMemoryUpload

from google_docs_mcp.api.drive import create_google_doc_from_markdown
from google_docs_mcp.api.documents import _export_document_as_markdown
from fastmcp.exceptions import ToolError


class TestMarkdownImport:
    """Tests for native markdown import via Drive API."""

    @patch('google_docs_mcp.api.drive.get_drive_client')
    def test_create_doc_from_markdown_basic(self, mock_get_drive):
        """Test basic markdown import creates document correctly."""
        # Setup mock
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive

        mock_response = {
            'id': 'test-doc-id-123',
            'name': 'Test Document',
            'webViewLink': 'https://docs.google.com/document/d/test-doc-id-123/edit'
        }

        mock_drive.files().create().execute.return_value = mock_response

        # Execute
        markdown_content = "# Test Heading\n\nThis is **bold** text."
        result = create_google_doc_from_markdown(
            title="Test Document",
            markdown_content=markdown_content
        )

        # Verify
        assert 'test-doc-id-123' in result
        assert 'Test Document' in result
        assert 'Successfully created' in result

        # Verify API call - get the actual call arguments
        # The call chain is files().create(...), so we look at the create call
        call_args_list = mock_drive.files().create.call_args_list
        # Find the call with arguments (not the intermediate () call)
        actual_call = [call for call in call_args_list if call[1]][0]
        call_kwargs = actual_call[1]

        # Check metadata
        assert call_kwargs['body']['name'] == 'Test Document'
        assert call_kwargs['body']['mimeType'] == 'application/vnd.google-apps.document'
        assert call_kwargs['supportsAllDrives'] is True
        assert call_kwargs['fields'] == 'id,name,webViewLink'

        # Check media upload
        media = call_kwargs['media_body']
        assert isinstance(media, MediaInMemoryUpload)

    @patch('google_docs_mcp.api.drive.get_drive_client')
    def test_create_doc_with_parent_folder(self, mock_get_drive):
        """Test markdown import with parent folder ID."""
        # Setup mock
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive

        mock_response = {
            'id': 'test-doc-id-456',
            'name': 'Doc in Folder',
            'webViewLink': 'https://docs.google.com/document/d/test-doc-id-456/edit'
        }

        mock_drive.files().create().execute.return_value = mock_response

        # Execute
        result = create_google_doc_from_markdown(
            title="Doc in Folder",
            markdown_content="Test content",
            parent_folder_id="folder-123"
        )

        # Verify
        assert 'test-doc-id-456' in result

        # Verify parent folder was set
        create_call = mock_drive.files().create
        call_kwargs = create_call.call_args[1]
        assert call_kwargs['body']['parents'] == ['folder-123']

    @patch('google_docs_mcp.api.drive.get_drive_client')
    def test_create_doc_permission_error(self, mock_get_drive):
        """Test handling of permission errors during import."""
        # Setup mock to raise permission error
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive
        mock_drive.files().create().execute.side_effect = Exception("403 Permission denied")

        # Execute and verify error
        with pytest.raises(ToolError) as exc_info:
            create_google_doc_from_markdown(
                title="Test",
                markdown_content="Test"
            )

        assert "Permission denied" in str(exc_info.value)

    @patch('google_docs_mcp.api.drive.get_drive_client')
    def test_create_doc_folder_not_found(self, mock_get_drive):
        """Test handling of folder not found errors."""
        # Setup mock to raise 404 error
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive
        mock_drive.files().create().execute.side_effect = Exception("404 Not found")

        # Execute and verify error
        with pytest.raises(ToolError) as exc_info:
            create_google_doc_from_markdown(
                title="Test",
                markdown_content="Test",
                parent_folder_id="nonexistent-folder"
            )

        assert "Parent folder not found" in str(exc_info.value)


class TestMarkdownExport:
    """Tests for native markdown export via Drive API."""

    @patch('google_docs_mcp.api.documents.get_drive_client')
    def test_export_document_as_markdown_basic(self, mock_get_drive):
        """Test basic markdown export from document."""
        # Setup mock
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive

        markdown_bytes = b"# Test Heading\n\nThis is **bold** text."
        mock_drive.files().export().execute.return_value = markdown_bytes

        # Execute
        result = _export_document_as_markdown(document_id="doc-123")

        # Verify
        assert result == "# Test Heading\n\nThis is **bold** text."

        # Verify API call - get the actual call arguments
        call_args_list = mock_drive.files().export.call_args_list
        # Find the call with arguments (not the intermediate () call)
        actual_call = [call for call in call_args_list if call[1]][0]
        call_kwargs = actual_call[1]

        assert call_kwargs['fileId'] == 'doc-123'
        assert call_kwargs['mimeType'] == 'text/markdown'

    @patch('google_docs_mcp.api.documents.get_drive_client')
    def test_export_with_max_length(self, mock_get_drive):
        """Test markdown export with max_length truncation."""
        # Setup mock
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive

        long_markdown = "A" * 1000
        mock_drive.files().export().execute.return_value = long_markdown.encode('utf-8')

        # Execute with max_length
        result = _export_document_as_markdown(
            document_id="doc-123",
            max_length=100
        )

        # Verify truncation
        assert len(result) > 100  # Includes truncation message
        assert "Markdown truncated to 100 chars" in result
        assert "1000 total" in result

    @patch('google_docs_mcp.api.documents.get_drive_client')
    def test_export_permission_error(self, mock_get_drive):
        """Test handling of permission errors during export."""
        # Setup mock to raise permission error
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive
        mock_drive.files().export().execute.side_effect = Exception("403 Permission denied")

        # Execute and verify error
        with pytest.raises(ToolError) as exc_info:
            _export_document_as_markdown(document_id="doc-123")

        assert "Permission denied" in str(exc_info.value)

    @patch('google_docs_mcp.api.documents.get_drive_client')
    def test_export_document_not_found(self, mock_get_drive):
        """Test handling of document not found errors."""
        # Setup mock to raise 404 error
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive
        mock_drive.files().export().execute.side_effect = Exception("404 Not found")

        # Execute and verify error
        with pytest.raises(ToolError) as exc_info:
            _export_document_as_markdown(document_id="nonexistent-doc")

        assert "Document not found" in str(exc_info.value)

    @patch('google_docs_mcp.api.documents.get_drive_client')
    @patch('google_docs_mcp.api.documents.log')
    def test_export_with_tab_id_warning(self, mock_log, mock_get_drive):
        """Test that warning is logged when tab_id is specified."""
        # Setup mock
        mock_drive = MagicMock()
        mock_get_drive.return_value = mock_drive

        markdown_bytes = b"# Test"
        mock_drive.files().export().execute.return_value = markdown_bytes

        # Execute with tab_id
        result = _export_document_as_markdown(
            document_id="doc-123",
            tab_id="tab-456"
        )

        # Verify warning was logged
        warning_logged = any(
            'tab_id' in str(call) and 'entire document' in str(call)
            for call in mock_log.call_args_list
        )
        assert warning_logged, "Expected warning about tab_id exporting entire document"
