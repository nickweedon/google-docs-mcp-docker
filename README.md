# Google Docs MCP Server - Docker

Docker configuration for running the [Google Docs MCP Server](https://github.com/a-bonus/google-docs-mcp) in a container.

This server provides Model Context Protocol (MCP) tools for interacting with Google Docs and Google Drive, enabling AI assistants like Claude to read, write, and manage your documents.

## Features

### Document Creation
- **Create blank documents** - Create new Google Documents from scratch
- **Import from Markdown** - Create Google Docs with content imported from markdown using Google Drive API's native markdown import (July 2024+). Supports standard markdown syntax with formatting handled by Google's native parser.

### Document Operations
- **Read documents** - Export content as text, JSON, or markdown (markdown export uses Google Drive API's native export)
- **Edit documents** - Insert, append, and delete text
- **Format text** - Apply character and paragraph styles (bold, italic, colors, fonts, alignment, etc.)
- **Manage structure** - Insert tables, page breaks, and images
- **Handle tabs** - List and work with multi-tab documents
- **Bulk operations** - Execute multiple document operations in a single batched API call for 5-10x faster performance

### Comments
- List, add, reply to, resolve, and delete comments on documents

### Drive Integration
- List, search, and get document metadata
- Create and manage folders
- Upload files and images
- **Resource-based uploads** - Upload files and images using resource identifiers from shared blob storage (for integration with other MCP servers)

## Prerequisites

- Docker and Docker Compose installed
- A Google Account
- Google Cloud Project with OAuth credentials

## Setup Instructions

### Step 1: Obtain Google Cloud Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)

2. **Create or select a project:**
   - Click the project dropdown and select "NEW PROJECT"
   - Name it (e.g., "Google Docs MCP") and click "CREATE"

3. **Enable required APIs:**
   - Go to "APIs & Services" > "Library"
   - Search for and enable **Google Docs API**
   - Search for and enable **Google Drive API**

4. **Configure OAuth Consent Screen:**
   - Go to "APIs & Services" > "OAuth consent screen"
   - Select "External" and click "CREATE"
   - Fill in:
     - App name: e.g., "Google Docs MCP Server"
     - User support email: your email
     - Developer contact: your email
   - Click "SAVE AND CONTINUE"
   - Click "ADD OR REMOVE SCOPES" and add:
     - `https://www.googleapis.com/auth/documents`
     - `https://www.googleapis.com/auth/drive.file`
   - Click "UPDATE" then "SAVE AND CONTINUE"
   - Add your Google email as a **Test User**
   - Click "SAVE AND CONTINUE"

5. **Create OAuth Credentials:**
   - Go to "APIs & Services" > "Credentials"
   - Click "+ CREATE CREDENTIALS" > "OAuth client ID"
   - Select "Desktop app" as the application type
   - Name it (e.g., "MCP Docker Client")
   - Click "CREATE"
   - **Download the JSON file**

### Step 2: Configure Credentials

1. Create a `credentials` directory in this project:
   ```bash
   mkdir -p credentials
   ```

2. Copy your downloaded OAuth JSON file:
   ```bash
   cp ~/Downloads/client_secret_*.json credentials/credentials.json
   ```

### Step 3: Build the Docker Image

```bash
docker-compose build
```

### Step 4: Authenticate with Google (First-Time Setup)

The first time you run the server, you need to authenticate with Google to generate a token. The authentication uses a loopback OAuth flow with **automatic port discovery**.

**How it works:**
- The container discovers its published port via Docker API
- OAuth callback redirects to the discovered host port automatically
- No manual port configuration needed

**Important:** Create an empty token.json file before running if it doesn't exist:
```bash
touch credentials/token.json
```

Run the container (Docker will assign an ephemeral port automatically):

```bash
docker run -it --rm \
  -p 3000 \
  -v $(pwd)/credentials:/workspace/credentials \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  workspace-google-docs-mcp:latest
```

**Note:** On Windows, use full paths instead of `$(pwd)`:
```bash
docker run -it --rm ^
  -p 3000 ^
  -v C:/path/to/google-docs-mcp/credentials:/workspace/credentials ^
  -v /var/run/docker.sock:/var/run/docker.sock:ro ^
  workspace-google-docs-mcp:latest
```

1. The container will detect its published port via Docker API and display it in the logs
2. The server will output an authorization URL
3. Copy the URL and open it in your browser
4. Log in with your Google account (the one added as a Test User)
5. Click "Allow" to grant permissions
6. Google will redirect to the discovered port - the container captures this automatically
7. You'll see "Authentication Successful!" in your browser
8. The `token.json` file will be saved to your `credentials/` directory
9. Press Ctrl+C to stop the container

Alternatively, use docker-compose:
```bash
docker-compose up
```

### Step 5: Run the Server

```bash
docker-compose up -d
```

The MCP server is now running and ready to accept connections.

## Claude Desktop Integration

Add this to your Claude Desktop config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

### Docker Installation

Run the MCP server in a Docker container. This requires mounting the credentials and token files:

```json
{
  "mcpServers": {
    "google-docs": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-p",
        "3000",
        "-v",
        "C:/path/to/google-docs-mcp/credentials:/workspace/credentials",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock:ro",
        "-v",
        "blob-storage:/mnt/blob-storage",
        "-e",
        "BLOB_STORAGE_ROOT=/mnt/blob-storage",
        "-e",
        "BLOB_STORAGE_MAX_SIZE_MB=100",
        "-e",
        "BLOB_STORAGE_TTL_HOURS=24",
        "workspace-google-docs-mcp:latest"
      ]
    }
  }
}
```

**Configuration notes:**
- `-p 3000` - Ephemeral port binding (Docker assigns available host port automatically)
- The first `-v` mount maps your local `credentials/` directory (containing both `credentials.json` and `token.json`) to `/workspace/credentials/` in the container
- The second `-v` mount provides Docker socket access for automatic port discovery
  - **Windows:** Docker Desktop automatically translates `/var/run/docker.sock` to the Windows named pipe
  - **Linux/macOS:** Uses the native Docker socket at `/var/run/docker.sock`
  - **Important:** Ensure "Expose daemon on tcp://localhost:2375 without TLS" is NOT enabled in Docker Desktop settings (it's a security risk and not needed)
- The third `-v` mount creates a shared blob storage volume for resource-based file uploads (optional, only needed if using resource-based upload features)
- The `-e` flags set environment variables for blob storage configuration (optional, defaults shown)

**Note:** Adjust the path (`C:/path/to/google-docs-mcp/credentials`) to match your local credentials directory. On Linux/macOS, use Unix-style paths (e.g., `/home/user/google-docs-mcp/credentials`).

**Optional:** Remove the blob storage volume mount and environment variables if you don't need resource-based upload features.

### Using a Running Container

If you prefer to keep the container running in the background with `docker-compose up -d`:

```json
{
  "mcpServers": {
    "google-docs": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "google-docs-mcp-server",
        "uv",
        "run",
        "google-docs-mcp"
      ]
    }
  }
}
```

**Note:** The container must be running before starting Claude Desktop.

Restart Claude Desktop after updating the configuration.

## File Structure

```
.
├── Dockerfile                      # Docker image definition (dev + production)
├── docker-compose.yml              # Docker Compose for production
├── docker-compose.devcontainer.yml # Docker Compose for VS Code devcontainer
├── .devcontainer/
│   └── devcontainer.json           # VS Code devcontainer configuration
├── src/
│   └── google_docs_mcp/            # Python source code
│       ├── server.py               # Main MCP server entry point
│       ├── auth.py                 # OAuth2 authentication (loopback flow)
│       └── api/                    # API modules (documents, comments, drive)
├── tests/                          # Test files
├── credentials/                    # Your Google OAuth credentials (gitignored)
│   ├── credentials.json            # OAuth client credentials
│   └── token.json                  # OAuth access token (generated after auth)
├── pyproject.toml                  # Python project configuration
├── .gitignore                      # Git ignore rules
└── README.md                       # This file
```

## Development

### VS Code Devcontainer (Recommended)

The project includes a devcontainer configuration for VS Code:

1. Open the project in VS Code
2. When prompted, click "Reopen in Container" (or use Command Palette: "Dev Containers: Reopen in Container")
3. VS Code will build the container and install dependencies automatically

The devcontainer includes:
- Python 3.12 with uv package manager
- Docker CLI (Docker-outside-of-Docker support)
- Node.js 20 and Claude Code CLI
- VS Code extensions: Python, Pylance, debugpy, Ruff, Claude Code
- Port 3000 forwarded for OAuth loopback callback

### Local Development (without container)

```bash
# Install dependencies
uv sync

# Run the server
uv run google-docs-mcp

# Run tests
uv run pytest
```

## OAuth Port Discovery

This server uses Docker API to automatically discover its published port for OAuth callbacks. This enables:

- **Ephemeral port bindings** - Docker can assign any available host port
- **No port conflicts** - Multiple instances can run simultaneously
- **Automatic configuration** - No manual port setup required

### How It Works

1. **Container starts** with ephemeral port binding (e.g., `-p 3000`)
2. **Docker assigns** an available host port (e.g., 32768)
3. **Server discovers** the mapping via Docker API (reads `/proc/self/cgroup` and queries Docker socket)
4. **OAuth redirect URI** uses the discovered host port (`http://localhost:32768`)
5. **Authentication succeeds** automatically

### Requirements

- Docker socket must be mounted: `-v /var/run/docker.sock:/var/run/docker.sock:ro`
- Python `docker` package must be installed (included in dependencies)

### Fallback Behavior

If Docker API is unavailable (socket not mounted or not running in Docker):
- Falls back to default port 3000
- Logs a warning to stderr
- Continues normally with static port

### Troubleshooting

**"Docker API unavailable" or "Connection aborted" error:**

*Windows with Docker Desktop:*
1. Ensure Docker Desktop is running and fully started
2. In Docker Desktop Settings → General, verify "Expose daemon on tcp://localhost:2375 without TLS" is **OFF** (unchecked)
3. The socket mount `-v /var/run/docker.sock:/var/run/docker.sock:ro` should work automatically (Docker Desktop translates it)
4. If the error persists, try restarting Docker Desktop
5. As a workaround, you can omit the Docker socket mount - the server will fall back to port 3000 (but you'll need to use `-p 3000:3000` instead of `-p 3000`)

*Linux/macOS:*
- Ensure Docker socket is mounted in your configuration
- Check socket permissions: `ls -l /var/run/docker.sock`
- Add your user to the docker group: `sudo usermod -aG docker $USER` (then log out and back in)

**"No port mapping found" warning:**
- Verify port is published in docker run/compose configuration
- Check with: `docker port <container_name>`

**Authentication still fails:**
- Check container logs: `docker logs <container_name>`
- Verify OAuth credentials in Google Cloud Console
- Ensure redirect URI matches what Google expects

## Commands

| Command | Description |
|---------|-------------|
| `docker-compose build` | Build the Docker image |
| `docker-compose up -d` | Start the server in background |
| `docker-compose down` | Stop the server |
| `docker-compose logs -f` | View server logs |
| `docker-compose --profile auth run --rm auth` | Run auth service interactively |

## Resource-Based File Uploads

This MCP server integrates with [mcp_mapped_resource_lib](https://github.com/nickweedon/mcp_mapped_resource_lib) to support **resource-based file uploads**. This enables efficient file sharing between multiple MCP servers through a shared Docker volume.

### Why Use Resource-Based Uploads?

Traditional MCP file transfers require encoding files as base64 and passing them through the MCP protocol, which can be inefficient for large files. With resource-based uploads:

1. **Other MCP servers** upload files to a shared blob storage volume and return a resource identifier (e.g., `blob://1733437200-a3f9d8c2b1e4f6a7.png`)
2. **This server** can directly access those files via the resource identifier and upload them to Google Drive
3. **No file data** is transferred through the MCP protocol - only the small resource identifier

### Available Resource-Based Tools

- `upload_image_to_drive_from_resource` - Upload an image to Drive using a resource ID
- `upload_file_to_drive_from_resource` - Upload any file to Drive using a resource ID
- `insert_image_from_resource` - Insert an image into a document using a resource ID

### Setup for Resource-Based Uploads

#### 1. Configure Blob Storage Volume

Add a shared volume for blob storage in your `docker-compose.yml`:

```yaml
services:
  google-docs-mcp:
    # ... existing config ...
    volumes:
      - ./credentials:/workspace/credentials
      - blob-storage:/mnt/blob-storage  # Add this line
    environment:
      - PYTHONUNBUFFERED=1
      - BLOB_STORAGE_ROOT=/mnt/blob-storage  # Required
      - BLOB_STORAGE_MAX_SIZE_MB=100         # Optional: max file size (default: 100)
      - BLOB_STORAGE_TTL_HOURS=24            # Optional: time-to-live (default: 24)

volumes:
  blob-storage:
    driver: local
```

**Configuration Options:**
- `BLOB_STORAGE_ROOT` - **Required**. Path to the blob storage directory
- `BLOB_STORAGE_MAX_SIZE_MB` - Optional. Maximum file size in MB (default: 100)
- `BLOB_STORAGE_TTL_HOURS` - Optional. Time-to-live for blobs in hours (default: 24). Blobs older than this will be automatically cleaned up.

#### 2. Update Claude Desktop Config

When using resource-based uploads, update your `claude_desktop_config.json` to mount the blob storage volume:

```json
{
  "mcpServers": {
    "google-docs": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-p",
        "3000:3000",
        "-v",
        "C:/path/to/google-docs-mcp/credentials:/workspace/credentials",
        "-v",
        "blob-storage:/mnt/blob-storage",
        "-e",
        "BLOB_STORAGE_ROOT=/mnt/blob-storage",
        "-e",
        "BLOB_STORAGE_MAX_SIZE_MB=100",
        "-e",
        "BLOB_STORAGE_TTL_HOURS=24",
        "workspace-google-docs-mcp:latest"
      ]
    }
  }
}
```

**Note:** Replace `C:/path/to/google-docs-mcp/credentials` with your actual credentials path. On Linux/macOS, use Unix-style paths.

**Configuration:**
- Adjust `BLOB_STORAGE_MAX_SIZE_MB` to set the maximum file size (in MB)
- Adjust `BLOB_STORAGE_TTL_HOURS` to control how long blobs are retained before automatic cleanup

#### 3. Share Volume with Other MCP Servers

Other MCP servers can use the same volume. Example configuration:

```json
{
  "mcpServers": {
    "google-docs": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-p", "3000:3000",
        "-v", "C:/path/to/google-docs-mcp/credentials:/workspace/credentials",
        "-v", "blob-storage:/mnt/blob-storage",
        "-e", "BLOB_STORAGE_ROOT=/mnt/blob-storage",
        "-e", "BLOB_STORAGE_MAX_SIZE_MB=100",
        "-e", "BLOB_STORAGE_TTL_HOURS=24",
        "workspace-google-docs-mcp:latest"
      ]
    },
    "other-mcp-server": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "blob-storage:/mnt/blob-storage:ro",
        "other-mcp-server:latest"
      ]
    }
  }
}
```

**Important:** The volume name (`blob-storage`) must be the same across all MCP servers that need to share resources.

### Example Usage

With another MCP server that has blob upload capabilities:

1. **Other MCP server** uploads a file to blob storage:
   ```
   User: Upload this image to blob storage
   Other Server: Uploaded! Resource ID: blob://1733437200-a3f9d8c2b1e4f6a7.png
   ```

2. **This server** uploads to Google Drive using the resource ID:
   ```
   User: Upload that image to my Google Drive using resource blob://1733437200-a3f9d8c2b1e4f6a7.png
   Google Docs Server: Successfully uploaded image "photo.png" from resource blob://1733437200-a3f9d8c2b1e4f6a7.png
   ```

### Resource ID Format

Resource identifiers follow the pattern: `blob://TIMESTAMP-HASH.EXT`

- `TIMESTAMP` - Unix timestamp when the file was uploaded
- `HASH` - SHA256 hash (truncated) for uniqueness
- `EXT` - Original file extension

Example: `blob://1733437200-a3f9d8c2b1e4f6a7.png`

## Bulk Operations

The `bulk_update_google_doc` tool allows you to execute multiple document operations in a single batched API call, providing **5-10x performance improvement** over individual tool calls.

### Why Use Bulk Operations?

When making multiple changes to a document (formatting, inserting content, adding tables, etc.), each individual tool call requires a separate network round-trip to Google's API. This creates significant latency:

**Before (individual calls):**
- 10 formatting operations = 10 API calls = ~5-10 seconds

**After (bulk operations):**
- 10 formatting operations = 1 batched API call = ~0.5-1 second

### Supported Operations

The bulk tool supports all document manipulation operations:

1. **insert_text** - Insert text at a specific index
2. **delete_range** - Delete content in a range
3. **apply_text_style** - Apply character-level formatting (bold, italic, colors, etc.)
4. **apply_paragraph_style** - Apply paragraph-level formatting (alignment, headings, spacing, etc.)
5. **insert_table** - Insert a table
6. **insert_page_break** - Insert a page break
7. **insert_image_from_url** - Insert an image from a URL

### Example Usage

Here's an example of creating a formatted document with a title, introduction, table, and styled text in a single API call:

```json
{
  "document_id": "your-document-id-here",
  "operations": [
    {
      "type": "insert_text",
      "text": "Project Status Report\n\n",
      "index": 1
    },
    {
      "type": "apply_paragraph_style",
      "start_index": 1,
      "end_index": 23,
      "named_style_type": "HEADING_1",
      "alignment": "CENTER"
    },
    {
      "type": "insert_text",
      "text": "Executive Summary\n\n",
      "index": 23
    },
    {
      "type": "apply_paragraph_style",
      "start_index": 23,
      "end_index": 42,
      "named_style_type": "HEADING_2"
    },
    {
      "type": "insert_text",
      "text": "This report provides an overview of project progress and key metrics.\n\n",
      "index": 42
    },
    {
      "type": "insert_text",
      "text": "Key Metrics\n\n",
      "index": 113
    },
    {
      "type": "apply_paragraph_style",
      "start_index": 113,
      "end_index": 126,
      "named_style_type": "HEADING_2"
    },
    {
      "type": "insert_table",
      "rows": 4,
      "columns": 3,
      "index": 126
    },
    {
      "type": "insert_text",
      "text": "\n\nConclusion\n",
      "index": 127
    },
    {
      "type": "apply_text_style",
      "text_to_find": "Conclusion",
      "match_instance": 1,
      "bold": true,
      "font_size": 14
    }
  ]
}
```

### Operation Parameters

Each operation is a dictionary with a `type` field and operation-specific parameters:

#### insert_text
- `text` (string): Text to insert
- `index` (integer): Position to insert at (1-based)
- `tab_id` (string, optional): Tab ID for multi-tab documents

#### delete_range
- `start_index` (integer): Start of range (1-based, inclusive)
- `end_index` (integer): End of range (1-based, exclusive)
- `tab_id` (string, optional): Tab ID

#### apply_text_style
Range targeting (choose one):
- `start_index` and `end_index` (integers): Direct range specification
- `text_to_find` (string) and `match_instance` (integer): Find specific text

Style properties:
- `bold`, `italic`, `underline`, `strikethrough` (boolean)
- `font_size` (float): Font size in points
- `font_family` (string): Font name (e.g., "Arial", "Times New Roman")
- `foreground_color`, `background_color` (string): Hex color (e.g., "#FF0000")
- `link_url` (string): URL for hyperlink

#### apply_paragraph_style
Range targeting (choose one):
- `start_index` and `end_index` (integers): Direct range specification
- `text_to_find` (string) and `match_instance` (integer): Find text, format its paragraph
- `index_within_paragraph` (integer): Format paragraph containing this index

Style properties:
- `alignment` (string): "START", "END", "CENTER", "JUSTIFIED"
- `indent_start`, `indent_end` (float): Indentation in points
- `space_above`, `space_below` (float): Spacing in points
- `named_style_type` (string): "NORMAL_TEXT", "HEADING_1" through "HEADING_6", "TITLE", "SUBTITLE"
- `keep_with_next` (boolean): Keep paragraph with next

#### insert_table
- `rows` (integer): Number of rows
- `columns` (integer): Number of columns
- `index` (integer): Position to insert (1-based)

#### insert_page_break
- `index` (integer): Position to insert (1-based)

#### insert_image_from_url
- `image_url` (string): Publicly accessible image URL
- `index` (integer): Position to insert (1-based)
- `width`, `height` (float, optional): Dimensions in points

### Limitations

- Maximum 500 operations per call (automatically batched into groups of 50 for Google API)
- Operations are executed in the order provided
- All operations must be valid before any are executed (fail-fast validation)

### Tips for Best Performance

1. **Group related operations**: Combine all changes to a document in a single bulk call
2. **Use index-based targeting when possible**: Text-finding operations require fetching the document first
3. **Order matters**: Structure your operations to account for index changes (e.g., insert text before applying formatting to that text)

## Markdown Support

This server uses Google Drive API's native markdown import/export (available since July 2024), which provides reliable conversion with Google's official parser.

### Known Limitations

- **Images in markdown export**: Images are exported as base64 data URLs (a known Google limitation). For sharing documents, use the original Google Docs file.
- **Tab support**: The markdown export API exports the entire document. Individual tab export is not supported - if you specify a tab_id, you'll get a warning and the entire document will be exported.
- **Conversion fidelity**: Formatting quality depends on Google's implementation. Complex Google Docs features may not have exact markdown equivalents.
- **API requirement**: Requires Google Drive API access in addition to Google Docs API (both should be enabled during setup).

## Security Notes

- **Never commit** `credentials.json` or `token.json` to version control
- The `.gitignore` file is configured to exclude these files
- Treat these files like passwords - they grant access to your Google account
- The token.json file allows the server to access your Google account without re-authentication

## Troubleshooting

**"credentials.json not found" error:**
- Ensure you've placed `credentials.json` in the `credentials/` directory
- Check the file is named exactly `credentials.json`

**Authentication fails:**
- Verify you added your email as a Test User in Google Cloud Console
- Ensure you enabled both Google Docs API and Google Drive API

**Docker container won't start:**
- Check that both `credentials.json` and `token.json` exist in `credentials/`
- Run `docker-compose logs` to see error messages

**Claude Desktop shows "Failed to connect":**
- Ensure the container is running: `docker-compose ps`
- Verify the container name is `google-docs-mcp-server`
- Try restarting Claude Desktop

## License

This Docker configuration is provided under the MIT License.
The underlying [google-docs-mcp](https://github.com/a-bonus/google-docs-mcp) server is licensed separately.
