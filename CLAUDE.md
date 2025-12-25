# Google Docs MCP Server - Claude Context

This is an MCP (Model Context Protocol) server for interfacing with Google Docs and Google Drive APIs. It enables AI assistants to read, create, and edit Google Documents.

## Primary Use Case

This MCP Server will be used by Claude Desktop as part of a custom Claude Desktop "Project" that contains instructions to help guide its usage of this MCP server as well as other behavior.

## Debugging

The user's logs relating to usage of this MCP server can be found at /workspace/claude-desktop-logs. More specifically the logs mcp-server-google-docs*.log; you should ONLY look at these files in this directory as the other files will not contain any useful information.
You should consult these logs whenever a prompt refers to recent errors in Claude Desktop.

## Project Structure

Follow standard Python project conventions with a modular architecture. API methods should be organized into separate modules by domain.

```
google-docs-mcp/
├── src/
│   └── google_docs_mcp/
│       ├── __init__.py         # Package initialization
│       ├── server.py           # Main MCP server entry point
│       ├── auth.py             # OAuth2 authentication (loopback flow)
│       ├── types.py            # Type definitions and utilities
│       ├── api/
│       │   ├── __init__.py     # API module initialization
│       │   ├── documents.py    # Document reading/writing operations
│       │   ├── comments.py     # Comment management operations
│       │   ├── drive.py        # Google Drive operations
│       │   └── helpers.py      # Google Docs API helper functions
│       └── utils/
│           └── __init__.py     # Utility functions
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_types.py           # Tests for type utilities
│   └── test_helpers.py         # Tests for helper functions
├── credentials/                # OAuth credentials directory (mounted volume)
│   ├── credentials.json        # Google OAuth client credentials
│   └── token.json              # Stored OAuth tokens
├── pyproject.toml              # Project configuration and dependencies
├── Dockerfile                  # Docker build configuration (dev + production)
├── docker-compose.yml          # Docker Compose for production
├── docker-compose.devcontainer.yml  # Docker Compose for VS Code devcontainer
├── .devcontainer/
│   └── devcontainer.json       # VS Code devcontainer configuration
├── README.md                   # User documentation
└── CLAUDE.md                   # This file - context for Claude
```

## Code Organization Guidelines

1. **Modular API Methods**: Each API domain (Documents, Comments, Drive) MUST be implemented in its own Python module under `src/google_docs_mcp/api/`.

2. **Separation of Concerns**:
   - `auth.py` - OAuth2 client, authentication, and token management
   - `api/*.py` - Domain-specific API methods only
   - `api/helpers.py` - Shared Google Docs API helper functions
   - `api/resources.py` - Resource-based file operations using mcp_mapped_resource_lib
   - `utils/` - Shared helper functions and utilities
   - `server.py` - MCP server setup and tool registration

3. **Standard Python Conventions**:
   - Use `src/` layout for proper package isolation
   - Include `__init__.py` files in all packages
   - Follow PEP 8 naming conventions
   - Use type hints throughout
   - Keep modules focused and cohesive

4. **Import Structure**: Each API module should import the shared client and helpers. The main server imports and registers tools from each API module.

## Key Implementation Details

### Authentication Methods

1. **OAuth2 (Default)**: Uses loopback flow with automatic port discovery
   - Requires `credentials.json` with OAuth client config
   - Stores tokens in `token.json`
   - User must authorize via browser
   - Automatically discovers published port via Docker API when available

2. **Service Account**: Set `SERVICE_ACCOUNT_PATH` environment variable
   - For automated/server environments
   - No browser interaction needed

### OAuth Loopback Port Discovery

The server uses Docker API to automatically discover its published port for OAuth callbacks:

**Architecture:**
- Container HTTP server listens on `0.0.0.0:3000` (always)
- Docker maps to ephemeral host port (e.g., `32768`)
- Container discovers mapping via Docker API at runtime
- OAuth redirect URI uses discovered host port

**Implementation:**
- `utils/docker.py` - Docker API integration and port discovery
- `auth.py` - Port discovery and OAuth flow integration
- Container ID extracted from `/proc/self/cgroup` or `/proc/self/mountinfo`
- Port mapping queried via Docker SDK for Python

**Requirements:**
- Docker socket mounted: `/var/run/docker.sock:/var/run/docker.sock:ro`
- `docker` Python package in dependencies
- Ephemeral port binding in compose: `ports: ["3000"]`

**Fallback:**
- If Docker API unavailable, falls back to port 3000
- Logs all discovery attempts to stderr
- Never crashes due to port discovery failures

### MCP Protocol Compatibility

**CRITICAL**: All logging must use `stderr` (via `print(..., file=sys.stderr)` or a `_log()` helper), never `stdout` or `print()`. The MCP protocol uses stdout for JSON-RPC communication. Any stdout output will corrupt the protocol and cause connection failures.

### Document Indexing

Google Docs uses 1-based indexing:
- Index 1 is the beginning of the document
- All `startIndex` parameters start from 1
- `endIndex` is exclusive

### Tab Support

Documents can have multiple tabs:
- Use `list_document_tabs` to discover tabs
- Pass `tab_id` parameter to target specific tabs
- Omit `tab_id` to use first/default tab

## MCP Server Implementation Guidelines

### Tool Method Signatures

The following guidelines should be followed when modifying or creating new MCP tool methods/functions:

1. **Never use print() or stdout** - All logging must go to stderr to avoid corrupting the MCP JSON-RPC protocol

2. **Use descriptive parameter annotations** - Every parameter should have an `Annotated` type with a clear description

3. **Provide comprehensive docstrings** - Include description, parameters, returns, and raises sections

4. **Return user-friendly strings** - Tool results should be formatted for human readability with markdown

5. **Handle errors gracefully** - Catch exceptions and convert to UserError with helpful messages

6. **Modular API methods** - Delegate actual API work to domain-specific modules under `api/`

### Example Tool Pattern

```python
@mcp.tool()
def read_google_doc(
    document_id: Annotated[str, "The ID of the Google Document"],
    format: Annotated[str, "Output format: 'text', 'json', 'markdown'"] = "text",
) -> str:
    """
    Read the content of a Google Document.

    Returns the document content in the specified format.
    """
    return documents.read_document(document_id, format)
```

### Design Patterns

1. **Strongly-typed return values** - Use dataclasses for complex return types in API modules
2. **Error handling with UserError** - Convert API errors to user-friendly messages
3. **Logging to stderr** - Use `_log()` helper function throughout
4. **Lazy client initialization** - Initialize Google clients on first use, not at import time

## Available Tools

### Document Creation
- `create_google_doc` - Create a new blank Google Document
- `create_google_doc_from_markdown` - Create a new Google Document from markdown content

### Document Operations
- `read_google_doc` - Read document content (text/json/markdown)
- `append_to_google_doc` - Append text to end of document
- `insert_text` - Insert text at specific index
- `delete_range` - Delete content range

### Tab Management
- `list_document_tabs` - List all tabs in a document

### Formatting
- `apply_text_style` - Character formatting (bold, italic, color, etc.)
- `apply_paragraph_style` - Paragraph formatting (alignment, spacing, headings)
- `format_matching_text` - Find and format specific text

### Structure
- `insert_table` - Insert a new table
- `insert_page_break` - Insert page break

### Images
- `insert_image_from_url` - Insert image from URL

### Comments
- `list_comments` - List all comments
- `get_comment` - Get comment with replies
- `add_comment` - Add new comment
- `reply_to_comment` - Reply to comment
- `resolve_comment` - Mark comment resolved
- `delete_comment` - Delete comment

### Drive Integration
- `list_google_docs` - List documents from Drive
- `search_google_docs` - Search documents
- `get_recent_google_docs` - Get recently modified documents
- `get_document_info` - Get document metadata
- `create_folder` - Create a Drive folder
- `list_folder_contents` - List folder contents
- `upload_image_to_drive` - Upload image to Drive from base64 data
- `upload_file_to_drive` - Upload any file to Drive from base64 data

### Resource-Based File Operations
- `upload_image_to_drive_from_resource` - Upload image to Drive using resource identifier from shared blob storage
- `upload_file_to_drive_from_resource` - Upload any file to Drive using resource identifier from shared blob storage
- `insert_image_from_resource` - Insert image into document using resource identifier from shared blob storage

**Note:** These tools require the `BLOB_STORAGE_ROOT` environment variable to be set and a shared Docker volume for blob storage. See README.md for setup instructions.

## Development Notes

- Uses FastMCP framework for MCP server implementation
- Uses `google-api-python-client` for Google API calls
- Uses `google-auth` and `google-auth-oauthlib` for authentication
- Uses `mcp-mapped-resource-lib` for resource-based file sharing across MCP servers
- Requires Python 3.10+

### FastMCP Documentation

For detailed FastMCP implementation guidance, see:
- [docs/FASTMCP_REFERENCE.md](docs/FASTMCP_REFERENCE.md) - Server implementation (tools, resources, prompts, context, middleware, authentication, deployment)
- [docs/FASTMCP_SDK_REFERENCE.md](docs/FASTMCP_SDK_REFERENCE.md) - Python SDK reference (exceptions, settings, CLI, client, server modules, utilities)

For additional information beyond what's covered in this project's documentation, refer to:
- Official FastMCP documentation: https://gofastmcp.com
- FastMCP GitHub repository: https://github.com/jlowin/fastmcp

## Building and Running

### VS Code Devcontainer (Recommended for Development)

The project includes a devcontainer configuration for VS Code. To use it:

1. Open the project in VS Code
2. When prompted, click "Reopen in Container" (or use Command Palette: "Dev Containers: Reopen in Container")
3. VS Code will build the container and install dependencies automatically

The devcontainer includes:
- Python 3.12 with uv package manager
- Docker CLI (Docker-outside-of-Docker)
- Node.js 20 and Claude Code CLI
- VS Code extensions: Python, Pylance, debugpy, Ruff, Claude Code
- Port 3000 forwarded for OAuth loopback callback
- Claude Desktop logs mounted at `/workspace/claude-desktop-logs`

**Dockerfile Build Args:**
- `CREATE_VSCODE_USER=true` - Creates a non-root vscode user for development
- `INSTALL_MCP=false` - Dependencies installed via `postCreateCommand` instead

### Local Development (without container)
```bash
uv sync
uv run google-docs-mcp
```

### Docker Production
```bash
docker-compose up --build
```

**Dockerfile Build Args for Production:**
- `CREATE_VSCODE_USER=false` - No vscode user needed
- `INSTALL_MCP=true` - Dependencies baked into image

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SERVICE_ACCOUNT_PATH` | Optional: Path to service account JSON key file |
| `DOCKER_ENV` | Set automatically in Docker container |
| `BLOB_STORAGE_ROOT` | Optional: Path to blob storage directory for resource-based file operations (required if using resource-based tools) |
| `BLOB_STORAGE_MAX_SIZE_MB` | Optional: Maximum file size in MB for blob storage (default: 100) |
| `BLOB_STORAGE_TTL_HOURS` | Optional: Time-to-live for blobs in hours, controls automatic cleanup (default: 24) |
| `CONTAINER_NAME` | Optional: Container name for logging (auto-detected from Docker API) |

## Testing

```bash
uv run pytest
```

## Migration from TypeScript

This project was ported from TypeScript to Python in December 2025. Key changes:

| TypeScript | Python |
|------------|--------|
| `server.ts` | `server.py` |
| `auth.ts` | `auth.py` |
| `googleDocsApiHelpers.ts` | `api/helpers.py` |
| `types.ts` (Zod schemas) | `types.py` (dataclasses) |
| `console.error()` | `print(..., file=sys.stderr)` or `_log()` |
| `fastmcp` (npm) | `fastmcp` (PyPI) |
| `googleapis` (npm) | `google-api-python-client` (PyPI) |
| `zod` validation | Type hints + `Annotated` |

The TypeScript source files (`src/*.ts`) have been replaced by Python modules under `src/google_docs_mcp/`.

## Git Commit Guidelines

- Do NOT include "Generated with Claude Code" or similar AI attribution in commit messages
- Do NOT include "Co-Authored-By: Claude" or similar co-author tags
- Write commit messages as if authored solely by the developer
