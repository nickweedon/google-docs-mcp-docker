"""
Pytest configuration and fixtures for Google Docs MCP Server tests.
"""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_docs_client():
    """
    Provide a mock Google Docs API client.
    """
    return MagicMock()


@pytest.fixture
def mock_drive_client():
    """
    Provide a mock Google Drive API client.
    """
    return MagicMock()


@pytest.fixture
def sample_document_content():
    """
    Provide sample document content matching Google Docs API structure.
    """
    return {
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


@pytest.fixture
def sample_document_with_multiple_runs():
    """
    Provide sample document with text split across multiple text runs.
    """
    return {
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


@pytest.fixture
def sample_document_with_repeated_text():
    """
    Provide sample document with repeated text for instance searching.
    """
    return {
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
