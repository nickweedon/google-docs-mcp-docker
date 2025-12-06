# Google Docs MCP Server - Docker

Docker configuration for running the [Google Docs MCP Server](https://github.com/a-bonus/google-docs-mcp) in a container.

This server provides Model Context Protocol (MCP) tools for interacting with Google Docs and Google Drive, enabling AI assistants like Claude to read, write, and manage your documents.

## Features

### Document Creation
- **Create blank documents** - Create new Google Documents from scratch
- **Import from Markdown** - Create Google Docs with content imported from markdown, including support for:
  - Headings (# to ######)
  - Bold, italic, and bold+italic formatting
  - Bullet and numbered lists
  - Links and inline code
  - Code blocks with monospace formatting
  - Horizontal rules

### Document Operations
- **Read documents** - Export content as text, JSON, or markdown
- **Edit documents** - Insert, append, and delete text
- **Format text** - Apply character and paragraph styles (bold, italic, colors, fonts, alignment, etc.)
- **Manage structure** - Insert tables, page breaks, and images
- **Handle tabs** - List and work with multi-tab documents

### Comments
- List, add, reply to, resolve, and delete comments on documents

### Drive Integration
- List, search, and get document metadata
- Create and manage folders
- Upload files and images

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

The first time you run the server, you need to authenticate with Google to generate a token. The authentication uses a loopback OAuth flow - the container starts a temporary web server on port 3000 to receive the OAuth callback.

**Important:** Create an empty token.json file before running if it doesn't exist:
```bash
touch credentials/token.json
```

Run the container with port 3000 exposed:

```bash
docker run -it --rm \
  -p 3000:3000 \
  -v $(pwd)/credentials:/workspace/credentials \
  workspace-google-docs-mcp:latest
```

**Note:** On Windows, use full paths instead of `$(pwd)`:
```bash
docker run -it --rm ^
  -p 3000:3000 ^
  -v C:/path/to/google-docs-mcp/credentials:/workspace/credentials ^
  workspace-google-docs-mcp:latest
```

1. The server will output an authorization URL
2. Copy the URL and open it in your browser
3. Log in with your Google account (the one added as a Test User)
4. Click "Allow" to grant permissions
5. Google will redirect to `http://localhost:3000` - the container captures this automatically
6. You'll see "Authentication Successful!" in your browser
7. The `token.json` file will be saved to your `credentials/` directory
8. Press Ctrl+C to stop the container

Alternatively, use docker-compose with the auth profile:
```bash
docker-compose --profile auth run --rm -p 3000:3000 auth
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
        "3000:3000",
        "-v",
        "C:/path/to/google-docs-mcp/credentials:/workspace/credentials",
        "workspace-google-docs-mcp:latest"
      ]
    }
  }
}
```

**Configuration notes:**
- `-p 3000:3000` - Exposes port 3000 for OAuth token refresh callbacks
- The `-v` mount maps your local `credentials/` directory (containing both `credentials.json` and `token.json`) to `/workspace/credentials/` in the container

**Note:** Adjust the path (`C:/path/to/google-docs-mcp/credentials`) to match your local credentials directory. On Linux/macOS, use Unix-style paths (e.g., `/home/user/google-docs-mcp/credentials`).

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

## Commands

| Command | Description |
|---------|-------------|
| `docker-compose build` | Build the Docker image |
| `docker-compose up -d` | Start the server in background |
| `docker-compose down` | Stop the server |
| `docker-compose logs -f` | View server logs |
| `docker-compose --profile auth run --rm auth` | Run auth service interactively |

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
