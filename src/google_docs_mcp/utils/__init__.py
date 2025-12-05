"""
Google Docs MCP Server utility modules.
"""

import sys


def log(message: str) -> None:
    """Log a message to stderr (MCP protocol compatibility).

    The MCP protocol uses stdout for JSON-RPC communication,
    so all logging must go to stderr to avoid corrupting the protocol.
    """
    print(message, file=sys.stderr)
