"""
OAuth2 authentication for Google Docs MCP Server.

Supports two authentication methods:
1. OAuth2 loopback flow (default) - User authorizes via browser
2. Service account authentication - For automated/server environments
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from google_docs_mcp.utils import log
from google_docs_mcp.utils.docker import discover_oauth_port

# Scopes required for Google Docs and Drive access
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

# OAuth loopback port - discovered at runtime in Docker environments
_CONTAINER_PORT = 3000  # Port inside container (never changes)
_discovered_host_port = None  # Cached discovered port


def get_oauth_port() -> int:
    """
    Get the OAuth loopback port (host port in Docker, container port otherwise).

    In Docker environments with ephemeral port bindings, this discovers the
    host port via Docker API. Otherwise, returns the default container port.

    Results are cached after first discovery.

    Returns:
        OAuth port number to use for redirect URI
    """
    global _discovered_host_port

    if _discovered_host_port is not None:
        return _discovered_host_port

    _discovered_host_port = discover_oauth_port(_CONTAINER_PORT)
    return _discovered_host_port

# Calculate paths for credentials
# In Docker: /workspace/credentials/
# In local dev: ./credentials/
if os.getenv("DOCKER_ENV"):
    # Running in Docker container
    CREDENTIALS_DIR = Path("/workspace/credentials")
else:
    # Local development - find project root
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    CREDENTIALS_DIR = PROJECT_ROOT / "credentials"

TOKEN_PATH = CREDENTIALS_DIR / "token.json"
CREDENTIALS_PATH = CREDENTIALS_DIR / "credentials.json"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    def log_message(self, format: str, *args) -> None:
        """Suppress HTTP request logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET request from OAuth callback."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "error" in params:
            error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h1>Authentication Failed</h1>"
                f"<p>Error: {error}</p>"
                f"<p>You can close this window.</p></body></html>".encode()
            )
            self.server.auth_code = None
            self.server.auth_error = error
            return

        if "code" in params:
            code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Authentication Successful!</h1>"
                b"<p>You can close this window and return to the terminal.</p></body></html>"
            )
            self.server.auth_code = code
            self.server.auth_error = None
            return

        # No code or error - favicon request or similar
        self.send_response(404)
        self.end_headers()


def _wait_for_auth_code(port: int, timeout: int = 300) -> str:
    """
    Start a temporary HTTP server and wait for OAuth callback.

    Args:
        port: Port to listen on (container port)
        timeout: Timeout in seconds (default 5 minutes)

    Returns:
        Authorization code from callback

    Raises:
        Exception: If authentication fails or times out
    """
    server = HTTPServer(("0.0.0.0", port), OAuthCallbackHandler)
    server.auth_code = None
    server.auth_error = None
    server.timeout = timeout

    oauth_port = get_oauth_port()
    log(f"Listening for OAuth callback on http://localhost:{oauth_port}")
    if oauth_port != port:
        log(f"(Container port {port} mapped to host port {oauth_port})")

    # Use a simple loop with timeout
    server.handle_request()

    if server.auth_error:
        raise Exception(f"OAuth error: {server.auth_error}")

    if not server.auth_code:
        raise Exception("Authentication timed out or no code received")

    return server.auth_code


def _authorize_with_service_account() -> ServiceAccountCredentials:
    """
    Authorize using a service account key file.

    Returns:
        Service account credentials

    Raises:
        Exception: If service account file not found or invalid
    """
    service_account_path = os.environ.get("SERVICE_ACCOUNT_PATH")
    if not service_account_path:
        raise Exception("SERVICE_ACCOUNT_PATH environment variable not set")

    path = Path(service_account_path)
    if not path.exists():
        raise Exception(
            f"Service account key file not found at path: {service_account_path}"
        )

    try:
        credentials = ServiceAccountCredentials.from_service_account_file(
            str(path), scopes=SCOPES
        )
        log("Service Account authentication successful!")
        return credentials
    except Exception as e:
        log(f"Error loading service account key: {e}")
        raise Exception(
            "Failed to authorize using the service account. "
            "Ensure the key file is valid and the path is correct."
        )


def _load_saved_credentials() -> Credentials | None:
    """
    Load saved OAuth credentials from token file.

    Returns:
        Credentials if found and valid, None otherwise
    """
    if not TOKEN_PATH.exists():
        return None

    try:
        credentials = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        if credentials and credentials.valid:
            return credentials
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            _save_credentials(credentials)
            return credentials
        return None
    except Exception as e:
        log(f"Error loading saved credentials: {e}")
        return None


def _save_credentials(credentials: Credentials) -> None:
    """
    Save OAuth credentials to token file.

    Args:
        credentials: Credentials to save
    """
    try:
        with open(TOKEN_PATH, "w") as f:
            f.write(credentials.to_json())
        log(f"Token stored to {TOKEN_PATH}")
    except Exception as e:
        log(f"Error saving credentials: {e}")


def _load_client_secrets() -> dict:
    """
    Load OAuth client secrets from credentials file.

    Returns:
        Dictionary with client configuration

    Raises:
        Exception: If credentials file not found or invalid
    """
    if not CREDENTIALS_PATH.exists():
        raise Exception(f"Credentials file not found at {CREDENTIALS_PATH}")

    with open(CREDENTIALS_PATH) as f:
        keys = json.load(f)

    key = keys.get("installed") or keys.get("web")
    if not key:
        raise Exception("Could not find client secrets in credentials.json")

    return {
        "client_id": key["client_id"],
        "client_secret": key["client_secret"],
        "redirect_uris": key.get("redirect_uris", ["http://localhost"]),
        "client_type": "web" if "web" in keys else "installed",
    }


def _authenticate() -> Credentials:
    """
    Perform OAuth2 authentication via loopback flow.

    Returns:
        OAuth2 credentials

    Raises:
        Exception: If authentication fails
    """
    oauth_port = get_oauth_port()
    redirect_uri = f"http://localhost:{oauth_port}"
    log(f"Using loopback OAuth flow with redirect URI: {redirect_uri}")

    # Create flow from client secrets file
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CREDENTIALS_PATH), scopes=SCOPES, redirect_uri=redirect_uri
    )

    # Generate authorization URL
    auth_url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )

    log("\n" + "=" * 60)
    log("Authorize this app by visiting this URL in your browser:")
    log("\n" + auth_url + "\n")
    log("=" * 60 + "\n")

    # Wait for callback
    code = _wait_for_auth_code(_CONTAINER_PORT)
    log("Received authorization code, exchanging for tokens...")

    try:
        flow.fetch_token(code=code)
        credentials = flow.credentials
        if credentials.refresh_token:
            _save_credentials(credentials)
        else:
            log("Did not receive refresh token. Token might expire.")
        log("Authentication successful!")
        return credentials
    except Exception as e:
        log(f"Error retrieving access token: {e}")
        raise Exception("Authentication failed")


def authorize() -> Credentials | ServiceAccountCredentials:
    """
    Authorize with Google APIs.

    Checks for service account path first, then falls back to OAuth2 flow.

    Returns:
        Valid credentials for Google API access
    """
    if os.environ.get("SERVICE_ACCOUNT_PATH"):
        log("Service account path detected. Attempting service account authentication...")
        return _authorize_with_service_account()
    else:
        log("No service account path detected. Falling back to standard OAuth 2.0 flow...")
        credentials = _load_saved_credentials()
        if credentials:
            log("Using saved credentials.")
            return credentials
        log("Starting authentication flow...")
        return _authenticate()


# Global clients (initialized lazily)
_auth_client = None
_docs_client = None
_drive_client = None


def get_docs_client():
    """
    Get the Google Docs API client.

    Returns:
        Google Docs API client resource

    Raises:
        Exception: If initialization fails
    """
    global _auth_client, _docs_client

    if _docs_client is not None:
        return _docs_client

    if _auth_client is None:
        log("Attempting to authorize Google API client...")
        _auth_client = authorize()
        log("Google API client authorized successfully.")

    _docs_client = build("docs", "v1", credentials=_auth_client)
    return _docs_client


def get_drive_client():
    """
    Get the Google Drive API client.

    Returns:
        Google Drive API client resource

    Raises:
        Exception: If initialization fails
    """
    global _auth_client, _drive_client

    if _drive_client is not None:
        return _drive_client

    if _auth_client is None:
        log("Attempting to authorize Google API client...")
        _auth_client = authorize()
        log("Google API client authorized successfully.")

    _drive_client = build("drive", "v3", credentials=_auth_client)
    return _drive_client


def get_auth_client():
    """
    Get the authenticated credentials.

    Returns:
        Google auth credentials
    """
    global _auth_client

    if _auth_client is None:
        _auth_client = authorize()

    return _auth_client
