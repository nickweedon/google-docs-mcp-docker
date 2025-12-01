# Google Docs MCP Server - Docker

Docker configuration for running the [Google Docs MCP Server](https://github.com/a-bonus/google-docs-mcp) in a container.

This server provides Model Context Protocol (MCP) tools for interacting with Google Docs and Google Drive, enabling AI assistants like Claude to read, write, and manage your documents.

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

The first time you run the server, you need to authenticate with Google to generate a token:

```bash
docker-compose run --rm google-docs-mcp
```

1. The server will output an authorization URL
2. Copy the URL and open it in your browser
3. Log in with your Google account (the one added as a Test User)
4. Click "Allow" to grant permissions
5. The browser will redirect to `localhost` with an error - this is expected
6. Copy the `code` parameter from the URL (between `code=` and `&scope=`)
7. Paste the code into the terminal and press Enter
8. A `token.json` file will be created

Copy the token to your credentials directory:
```bash
docker cp google-docs-mcp-server:/app/token.json credentials/token.json
```

Or if using the auth service:
```bash
docker-compose --profile auth run --rm auth
# After authentication, the token is saved to ./credentials/token.json
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
        "-v",
        "C:/docker/google-docs-mcp/credentials.json:/app/credentials.json:ro",
        "-v",
        "C:/docker/google-docs-mcp/token.json:/app/token.json:ro",
        "google-docs-mcp-google-docs-mcp:latest"
      ]
    }
  }
}
```

**Volume mappings:**
- `credentials.json` - Google OAuth client credentials (read-only)
- `token.json` - OAuth access token (read-only, generated during authentication)

**Note:** Adjust the paths (`C:/docker/...`) to match your local file locations. On Linux/macOS, use Unix-style paths (e.g., `/home/user/docker/google-docs-mcp/...`).

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
        "node",
        "./dist/server.js"
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
├── Dockerfile           # Docker image definition
├── docker-compose.yml   # Docker Compose configuration
├── credentials/         # Your Google OAuth credentials (gitignored)
│   ├── credentials.json # OAuth client credentials
│   └── token.json       # OAuth access token (generated after auth)
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## Commands

| Command | Description |
|---------|-------------|
| `docker-compose build` | Build the Docker image |
| `docker-compose up -d` | Start the server in background |
| `docker-compose down` | Stop the server |
| `docker-compose logs -f` | View server logs |
| `docker-compose run --rm google-docs-mcp` | Run interactively (for auth) |

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
