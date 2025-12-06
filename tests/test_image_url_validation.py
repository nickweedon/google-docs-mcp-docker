"""
Tests for image URL validation functionality.

Tests the _validate_image_url function and its integration with insert_image operations.
"""

import pytest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

from google_docs_mcp.api.helpers import _validate_image_url, insert_inline_image
from google_docs_mcp.api.documents import _prepare_insert_image_request
from fastmcp.exceptions import ToolError


class TestValidateImageUrl:
    """Tests for the _validate_image_url function."""

    @patch('urllib.request.urlopen')
    def test_valid_image_url(self, mock_urlopen):
        """Should pass validation for a valid, accessible image URL."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers.get.return_value = 'image/png'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Should not raise any exception
        _validate_image_url("https://example.com/image.png")

        # Verify HEAD request was made
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args[0][0]
        assert call_args.get_method() == 'HEAD'
        # Header names are case-insensitive, stored as 'User-agent'
        assert 'User-agent' in call_args.headers or 'User-Agent' in call_args.headers

    @patch('urllib.request.urlopen')
    def test_valid_image_url_jpeg(self, mock_urlopen):
        """Should accept JPEG images."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers.get.return_value = 'image/jpeg'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        _validate_image_url("https://example.com/photo.jpg")

    @patch('urllib.request.urlopen')
    def test_valid_image_url_without_content_type(self, mock_urlopen):
        """Should accept URLs without explicit Content-Type header."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers.get.return_value = ''  # No Content-Type
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Should pass - we don't strictly require Content-Type
        _validate_image_url("https://example.com/image.png")

    def test_invalid_url_format(self):
        """Should raise error for invalid URL format."""
        with pytest.raises(ToolError) as exc_info:
            _validate_image_url("not-a-valid-url")

        assert "Invalid image URL format" in str(exc_info.value)

    def test_url_without_scheme(self):
        """Should raise error for URL without scheme."""
        with pytest.raises(ToolError) as exc_info:
            _validate_image_url("example.com/image.png")

        assert "Invalid image URL format" in str(exc_info.value)

    def test_url_with_ftp_scheme(self):
        """Should raise error for non-HTTP(S) schemes."""
        with pytest.raises(ToolError) as exc_info:
            _validate_image_url("ftp://example.com/image.png")

        assert "Invalid image URL format" in str(exc_info.value)

    @patch('urllib.request.urlopen')
    def test_url_returns_404(self, mock_urlopen):
        """Should raise error when URL returns 404."""
        mock_urlopen.side_effect = HTTPError(
            "https://example.com/missing.png",
            404,
            "Not Found",
            {},
            None
        )

        with pytest.raises(ToolError) as exc_info:
            _validate_image_url("https://example.com/missing.png")

        assert "HTTP 404 error" in str(exc_info.value)
        assert "publicly accessible" in str(exc_info.value)

    @patch('urllib.request.urlopen')
    def test_url_returns_403(self, mock_urlopen):
        """Should raise error when URL returns 403 Forbidden."""
        mock_urlopen.side_effect = HTTPError(
            "https://example.com/forbidden.png",
            403,
            "Forbidden",
            {},
            None
        )

        with pytest.raises(ToolError) as exc_info:
            _validate_image_url("https://example.com/forbidden.png")

        assert "HTTP 403 error" in str(exc_info.value)

    @patch('urllib.request.urlopen')
    def test_url_returns_500(self, mock_urlopen):
        """Should raise error when URL returns 500 Server Error."""
        mock_urlopen.side_effect = HTTPError(
            "https://example.com/error.png",
            500,
            "Internal Server Error",
            {},
            None
        )

        with pytest.raises(ToolError) as exc_info:
            _validate_image_url("https://example.com/error.png")

        assert "HTTP 500 error" in str(exc_info.value)

    @patch('urllib.request.urlopen')
    def test_url_network_error(self, mock_urlopen):
        """Should raise error for network errors."""
        mock_urlopen.side_effect = URLError("Network unreachable")

        with pytest.raises(ToolError) as exc_info:
            _validate_image_url("https://example.com/image.png")

        assert "Cannot access image URL" in str(exc_info.value)
        assert "publicly accessible" in str(exc_info.value)

    @patch('urllib.request.urlopen')
    def test_url_timeout(self, mock_urlopen):
        """Should raise error for timeout."""
        mock_urlopen.side_effect = TimeoutError("Connection timeout")

        with pytest.raises(ToolError) as exc_info:
            _validate_image_url("https://example.com/image.png")

        assert "Timeout accessing image URL" in str(exc_info.value)

    @patch('urllib.request.urlopen')
    def test_url_non_image_content_type(self, mock_urlopen):
        """Should raise error when Content-Type is not an image."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers.get.return_value = 'text/html'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(ToolError) as exc_info:
            _validate_image_url("https://example.com/page.html")

        assert "does not point to an image" in str(exc_info.value)
        assert "text/html" in str(exc_info.value)

    @patch('urllib.request.urlopen')
    def test_url_pdf_content_type(self, mock_urlopen):
        """Should raise error for PDF files."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers.get.return_value = 'application/pdf'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(ToolError) as exc_info:
            _validate_image_url("https://example.com/document.pdf")

        assert "does not point to an image" in str(exc_info.value)

    @patch('urllib.request.urlopen')
    def test_url_non_200_status(self, mock_urlopen):
        """Should raise error for non-200 status codes."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 302  # Redirect
        mock_response.headers.get.return_value = 'image/png'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(ToolError) as exc_info:
            _validate_image_url("https://example.com/redirect")

        assert "status 302" in str(exc_info.value)


class TestInsertInlineImageWithValidation:
    """Tests for insert_inline_image with URL validation."""

    @patch('google_docs_mcp.api.helpers.execute_batch_update_sync')
    @patch('urllib.request.urlopen')
    def test_insert_image_with_valid_url(self, mock_urlopen, mock_execute):
        """Should insert image when URL is valid."""
        # Mock URL validation
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers.get.return_value = 'image/png'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Mock batch update
        mock_execute.return_value = {"documentId": "doc123"}

        # Mock docs client
        mock_docs = MagicMock()

        result = insert_inline_image(
            mock_docs,
            "doc123",
            "https://example.com/image.png",
            100
        )

        # Verify validation was called
        mock_urlopen.assert_called_once()

        # Verify batch update was called
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]
        requests = call_args[2]
        assert requests[0]["insertInlineImage"]["uri"] == "https://example.com/image.png"

    @patch('urllib.request.urlopen')
    def test_insert_image_with_inaccessible_url(self, mock_urlopen):
        """Should raise error before calling API when URL is inaccessible."""
        # Mock URL validation failure
        mock_urlopen.side_effect = HTTPError(
            "https://example.com/missing.png",
            404,
            "Not Found",
            {},
            None
        )

        mock_docs = MagicMock()

        with pytest.raises(ToolError) as exc_info:
            insert_inline_image(
                mock_docs,
                "doc123",
                "https://example.com/missing.png",
                100
            )

        assert "HTTP 404 error" in str(exc_info.value)


class TestPrepareInsertImageRequestWithValidation:
    """Tests for _prepare_insert_image_request with URL validation."""

    @patch('urllib.request.urlopen')
    def test_prepare_with_valid_url(self, mock_urlopen):
        """Should prepare request when URL is valid."""
        # Mock URL validation
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers.get.return_value = 'image/jpeg'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        op_dict = {
            "image_url": "https://example.com/photo.jpg",
            "index": 50
        }

        request = _prepare_insert_image_request(op_dict)

        assert request["insertInlineImage"]["uri"] == "https://example.com/photo.jpg"
        assert request["insertInlineImage"]["location"]["index"] == 50

    @patch('urllib.request.urlopen')
    def test_prepare_with_404_url(self, mock_urlopen):
        """Should raise error when URL returns 404."""
        # Mock URL validation failure
        mock_urlopen.side_effect = HTTPError(
            "https://cdn-shop.adafruit.com/970x728/997-02.jpg",
            404,
            "Not Found",
            {},
            None
        )

        op_dict = {
            "image_url": "https://cdn-shop.adafruit.com/970x728/997-02.jpg",
            "index": 686
        }

        with pytest.raises(ToolError) as exc_info:
            _prepare_insert_image_request(op_dict)

        assert "HTTP 404 error" in str(exc_info.value)
        assert "publicly accessible" in str(exc_info.value)

    @patch('urllib.request.urlopen')
    def test_prepare_with_invalid_content_type(self, mock_urlopen):
        """Should raise error when URL is not an image."""
        # Mock URL validation failure
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.headers.get.return_value = 'text/html'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        op_dict = {
            "image_url": "https://example.com/page.html",
            "index": 100
        }

        with pytest.raises(ToolError) as exc_info:
            _prepare_insert_image_request(op_dict)

        assert "does not point to an image" in str(exc_info.value)

    def test_prepare_with_empty_url(self):
        """Should raise error when URL is empty."""
        op_dict = {
            "image_url": "",
            "index": 100
        }

        with pytest.raises(ToolError) as exc_info:
            _prepare_insert_image_request(op_dict)

        assert "image_url is required" in str(exc_info.value)
