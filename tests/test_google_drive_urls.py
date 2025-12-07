"""Tests for Google Drive URL handling in image validation."""

import pytest
from unittest.mock import MagicMock, patch
from google_docs_mcp.api.helpers import _validate_image_url
from fastmcp.exceptions import ToolError


class TestGoogleDriveURLHandling:
    """Test that Google Drive URLs are handled correctly."""

    def test_reject_drive_view_url_with_helpful_message(self):
        """Test that Drive view URLs are rejected with a helpful suggestion."""
        url = "https://drive.google.com/uc?export=view&id=123abc"

        with pytest.raises(ToolError) as exc_info:
            _validate_image_url(url)

        error_msg = str(exc_info.value)
        assert "download format" in error_msg.lower()
        assert "export=download" in error_msg

    def test_accept_drive_download_url(self):
        """Test that Drive download URLs skip content-type validation."""
        url = "https://drive.google.com/uc?export=download&id=123abc"

        # Mock the URL request to return HTML (which would normally fail)
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_response.getcode.return_value = 200
            mock_response.headers.get.return_value = 'text/html; charset=utf-8'
            mock_urlopen.return_value = mock_response

            # Should not raise because we skip validation for Drive download URLs
            _validate_image_url(url)

    def test_non_drive_html_url_rejected(self):
        """Test that non-Drive URLs returning HTML are still rejected."""
        url = "https://example.com/image.jpg"

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_response.getcode.return_value = 200
            mock_response.headers.get.return_value = 'text/html'
            mock_urlopen.return_value = mock_response

            with pytest.raises(ToolError) as exc_info:
                _validate_image_url(url)

            assert "does not point to an image" in str(exc_info.value)
            assert "text/html" in str(exc_info.value)

    def test_drive_url_with_invalid_format_provides_guidance(self):
        """Test that Drive URLs with wrong content type get helpful error."""
        url = "https://drive.google.com/file/d/123abc/view"

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_response.getcode.return_value = 200
            mock_response.headers.get.return_value = 'text/html'
            mock_urlopen.return_value = mock_response

            with pytest.raises(ToolError) as exc_info:
                _validate_image_url(url)

            error_msg = str(exc_info.value)
            assert "drive.google.com" in error_msg.lower()
            assert "export=download" in error_msg
