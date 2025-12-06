"""
Tests for Google Docs API helper functions.

Ported from tests/helpers.test.js
"""

import pytest
from unittest.mock import MagicMock, patch

from google_docs_mcp.api.helpers import find_text_range, get_paragraph_range_from_document
from google_docs_mcp.types import TextRange


class TestFindTextRange:
    """Tests for text range finding functionality."""

    def test_find_text_within_single_text_run(self, mock_docs_client):
        """Should find text within a single text run correctly."""
        # Mock the docs.documents.get method
        mock_docs_client.documents.return_value.get.return_value.execute.return_value = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {
                                    "startIndex": 1,
                                    "endIndex": 25,
                                    "textRun": {"content": "This is a test sentence."},
                                }
                            ]
                        }
                    }
                ]
            }
        }

        # Test finding "test" in the sample text
        result = find_text_range(mock_docs_client, "doc123", "test", 1)

        assert result is not None
        assert result.start_index == 11
        assert result.end_index == 15

        # Verify the API was called correctly
        mock_docs_client.documents.return_value.get.assert_called_once()

    def test_find_nth_instance_of_text(self, mock_docs_client):
        """Should find the nth instance of text correctly."""
        # Mock with a document that has repeated text
        mock_docs_client.documents.return_value.get.return_value.execute.return_value = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {
                                    "startIndex": 1,
                                    "endIndex": 41,
                                    "textRun": {
                                        "content": "Test test test. This is a test sentence."
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        }

        # Find the 3rd instance of "test" (case-sensitive, so should find lowercase)
        result = find_text_range(mock_docs_client, "doc123", "test", 3)

        assert result is not None
        assert result.start_index == 27
        assert result.end_index == 31

    def test_return_none_if_text_not_found(self, mock_docs_client):
        """Should return None if text is not found."""
        mock_docs_client.documents.return_value.get.return_value.execute.return_value = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {
                                    "startIndex": 1,
                                    "endIndex": 27,
                                    "textRun": {"content": "This is a sample sentence."},
                                }
                            ]
                        }
                    }
                ]
            }
        }

        # Try to find text that doesn't exist
        result = find_text_range(mock_docs_client, "doc123", "test", 1)

        assert result is None

    def test_handle_text_spanning_multiple_runs(self, mock_docs_client):
        """Should handle text spanning multiple text runs."""
        mock_docs_client.documents.return_value.get.return_value.execute.return_value = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {
                                    "startIndex": 1,
                                    "endIndex": 6,
                                    "textRun": {"content": "This "},
                                },
                                {
                                    "startIndex": 6,
                                    "endIndex": 11,
                                    "textRun": {"content": "is a "},
                                },
                                {
                                    "startIndex": 11,
                                    "endIndex": 20,
                                    "textRun": {"content": "test case"},
                                },
                            ]
                        }
                    }
                ]
            }
        }

        # Find text that spans runs: "a test"
        result = find_text_range(mock_docs_client, "doc123", "a test", 1)

        assert result is not None
        assert result.start_index == 9
        assert result.end_index == 15

    def test_handle_empty_document(self, mock_docs_client):
        """Should handle empty documents gracefully."""
        mock_docs_client.documents.return_value.get.return_value.execute.return_value = {
            "body": {"content": []}
        }

        result = find_text_range(mock_docs_client, "doc123", "test", 1)

        assert result is None

    def test_handle_document_without_body(self, mock_docs_client):
        """Should handle documents without body content."""
        mock_docs_client.documents.return_value.get.return_value.execute.return_value = {}

        result = find_text_range(mock_docs_client, "doc123", "test", 1)

        assert result is None

    def test_return_none_for_instance_beyond_available(self, mock_docs_client):
        """Should return None when requested instance doesn't exist."""
        mock_docs_client.documents.return_value.get.return_value.execute.return_value = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {
                                    "startIndex": 1,
                                    "endIndex": 25,
                                    "textRun": {"content": "This is a test sentence."},
                                }
                            ]
                        }
                    }
                ]
            }
        }

        # Try to find 5th instance when only 1 exists
        result = find_text_range(mock_docs_client, "doc123", "test", 5)

        assert result is None


class TestBuildUpdateTextStyleRequest:
    """Tests for text style request building."""

    def test_build_bold_style_request(self):
        """Should build a request for bold formatting."""
        from google_docs_mcp.api.helpers import build_update_text_style_request
        from google_docs_mcp.types import TextStyleArgs

        style = TextStyleArgs(bold=True)
        result = build_update_text_style_request(1, 10, style)

        assert result is not None
        assert "request" in result
        assert "fields" in result
        assert "bold" in result["fields"]
        assert result["request"]["updateTextStyle"]["textStyle"]["bold"] is True

    def test_build_multiple_styles_request(self):
        """Should build a request with multiple styles."""
        from google_docs_mcp.api.helpers import build_update_text_style_request
        from google_docs_mcp.types import TextStyleArgs

        style = TextStyleArgs(bold=True, italic=True, font_size=14)
        result = build_update_text_style_request(1, 10, style)

        assert result is not None
        assert "bold" in result["fields"]
        assert "italic" in result["fields"]
        assert "fontSize" in result["fields"]

    def test_return_none_for_empty_style(self):
        """Should return None when no styles are provided."""
        from google_docs_mcp.api.helpers import build_update_text_style_request
        from google_docs_mcp.types import TextStyleArgs

        style = TextStyleArgs()  # No styles set
        result = build_update_text_style_request(1, 10, style)

        assert result is None


class TestBuildUpdateParagraphStyleRequest:
    """Tests for paragraph style request building."""

    def test_build_alignment_request(self):
        """Should build a request for paragraph alignment."""
        from google_docs_mcp.api.helpers import build_update_paragraph_style_request
        from google_docs_mcp.types import ParagraphStyleArgs

        style = ParagraphStyleArgs(alignment="CENTER")
        result = build_update_paragraph_style_request(1, 10, style)

        assert result is not None
        assert "alignment" in result["fields"]
        assert result["request"]["updateParagraphStyle"]["paragraphStyle"]["alignment"] == "CENTER"

    def test_build_named_style_request(self):
        """Should build a request for named style (heading)."""
        from google_docs_mcp.api.helpers import build_update_paragraph_style_request
        from google_docs_mcp.types import ParagraphStyleArgs

        style = ParagraphStyleArgs(named_style_type="HEADING_1")
        result = build_update_paragraph_style_request(1, 10, style)

        assert result is not None
        assert "namedStyleType" in result["fields"]
        assert (
            result["request"]["updateParagraphStyle"]["paragraphStyle"]["namedStyleType"]
            == "HEADING_1"
        )

    def test_return_none_for_empty_paragraph_style(self):
        """Should return None when no paragraph styles are provided."""
        from google_docs_mcp.api.helpers import build_update_paragraph_style_request
        from google_docs_mcp.types import ParagraphStyleArgs

        style = ParagraphStyleArgs()  # No styles set
        result = build_update_paragraph_style_request(1, 10, style)

        assert result is None


class TestGetParagraphRangeFromDocument:
    """Tests for get_paragraph_range_from_document function."""

    def test_find_paragraph_in_body_content(self):
        """Should find paragraph containing an index in body content."""
        document = {
            "body": {
                "content": [
                    {"startIndex": 0, "endIndex": 1},  # Section break
                    {
                        "startIndex": 1,
                        "endIndex": 55,
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "First paragraph content here."}}
                            ]
                        }
                    },
                    {
                        "startIndex": 55,
                        "endIndex": 100,
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Second paragraph content."}}
                            ]
                        }
                    }
                ]
            }
        }

        result = get_paragraph_range_from_document(document, 10)

        assert result is not None
        assert result.start_index == 1
        assert result.end_index == 55

    def test_find_paragraph_in_tabs_structure(self):
        """Should find paragraph in document with tabs structure."""
        document = {
            "tabs": [
                {
                    "tabProperties": {"tabId": "t.0"},
                    "documentTab": {
                        "body": {
                            "content": [
                                {"startIndex": 0, "endIndex": 1},
                                {
                                    "startIndex": 1,
                                    "endIndex": 55,
                                    "paragraph": {
                                        "elements": [
                                            {"textRun": {"content": "Tab content here."}}
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                }
            ]
        }

        result = get_paragraph_range_from_document(document, 25)

        assert result is not None
        assert result.start_index == 1
        assert result.end_index == 55

    def test_find_paragraph_in_specific_tab(self):
        """Should find paragraph in a specific tab when tab_id is provided."""
        document = {
            "tabs": [
                {
                    "tabProperties": {"tabId": "t.0"},
                    "documentTab": {
                        "body": {
                            "content": [
                                {"startIndex": 0, "endIndex": 1},
                                {
                                    "startIndex": 1,
                                    "endIndex": 30,
                                    "paragraph": {}
                                }
                            ]
                        }
                    }
                },
                {
                    "tabProperties": {"tabId": "t.1"},
                    "documentTab": {
                        "body": {
                            "content": [
                                {"startIndex": 0, "endIndex": 1},
                                {
                                    "startIndex": 1,
                                    "endIndex": 100,
                                    "paragraph": {}
                                }
                            ]
                        }
                    }
                }
            ]
        }

        result = get_paragraph_range_from_document(document, 50, tab_id="t.1")

        assert result is not None
        assert result.start_index == 1
        assert result.end_index == 100

    def test_return_none_for_index_outside_paragraphs(self):
        """Should return None when index is not within any paragraph."""
        document = {
            "body": {
                "content": [
                    {"startIndex": 0, "endIndex": 1},  # Section break
                    {
                        "startIndex": 1,
                        "endIndex": 55,
                        "paragraph": {}
                    }
                ]
            }
        }

        # Index 500 is way beyond any content
        result = get_paragraph_range_from_document(document, 500)

        assert result is None

    def test_return_none_for_empty_document(self):
        """Should return None for document with no content."""
        document = {"body": {"content": []}}

        result = get_paragraph_range_from_document(document, 10)

        assert result is None

    def test_return_none_for_document_without_body(self):
        """Should return None for document without body."""
        document = {}

        result = get_paragraph_range_from_document(document, 10)

        assert result is None

    def test_find_paragraph_in_table_cell(self):
        """Should find paragraph inside a table cell."""
        document = {
            "body": {
                "content": [
                    {"startIndex": 0, "endIndex": 1},
                    {
                        "startIndex": 1,
                        "endIndex": 200,
                        "table": {
                            "tableRows": [
                                {
                                    "tableCells": [
                                        {
                                            "content": [
                                                {
                                                    "startIndex": 5,
                                                    "endIndex": 50,
                                                    "paragraph": {
                                                        "elements": [
                                                            {"textRun": {"content": "Cell content"}}
                                                        ]
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ]
            }
        }

        result = get_paragraph_range_from_document(document, 25)

        assert result is not None
        assert result.start_index == 5
        assert result.end_index == 50

    def test_handles_non_paragraph_elements(self):
        """Should skip non-paragraph elements like section breaks."""
        document = {
            "body": {
                "content": [
                    {
                        "startIndex": 0,
                        "endIndex": 1,
                        "sectionBreak": {}  # Not a paragraph
                    },
                    {
                        "startIndex": 1,
                        "endIndex": 55,
                        "paragraph": {}
                    }
                ]
            }
        }

        # Index 0 is within section break, not a paragraph
        result = get_paragraph_range_from_document(document, 0)

        assert result is None

        # Index 10 is within the paragraph
        result = get_paragraph_range_from_document(document, 10)

        assert result is not None
        assert result.start_index == 1
        assert result.end_index == 55
