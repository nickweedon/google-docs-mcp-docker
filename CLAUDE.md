# Google Docs MCP Server - Claude Context

This is an MCP (Model Context Protocol) server for interfacing with Google Docs and Google Drive APIs. It enables AI assistants to read, create, and edit Google Documents.

## Primary Use Case

This MCP Server will be used by Claude Desktop as part of a custom Claude Desktop "Project" that contains instructions to help guide its usage of this MCP server as well as other behavior.

## Debugging

The user's logs relating to usage of this MCP server can be found at /workspace/claude-desktop-logs. More specifically the logs mcp-server-google-docs*.log; you should ONLY look at these files in this directory as the other files will not contain any useful information.
You should consult these logs whenever a prompt refers to recent errors in Claude Desktop.

## Project Structure

This is a TypeScript project using the FastMCP framework.

```
google-docs-mcp/
├── src/
│   ├── server.ts              # Main MCP server with all tool definitions
│   ├── auth.ts                # OAuth2 authentication (loopback flow)
│   ├── googleDocsApiHelpers.ts # Helper functions for Google Docs API
│   └── types.ts               # Zod schemas and TypeScript types
├── tests/
│   ├── helpers.test.js        # Tests for helper functions
│   └── types.test.js          # Tests for type utilities
├── credentials/               # OAuth credentials directory (mounted volume)
│   ├── credentials.json       # Google OAuth client credentials
│   └── token.json            # Stored OAuth tokens
├── dist/                      # Compiled JavaScript output
├── package.json               # Node.js dependencies
├── tsconfig.json              # TypeScript configuration
├── index.js                   # Entry point
├── Dockerfile                 # Docker build configuration
├── docker-compose.yml         # Docker Compose configuration
├── README.md                  # User documentation
└── CLAUDE.md                  # This file - context for Claude
```

## Code Organization Guidelines

1. **Single Server File**: All MCP tools are defined in `server.ts`. This includes:
   - Document reading and writing
   - Text formatting and styling
   - Table operations
   - Image insertion
   - Comment management
   - Drive file listing and search

2. **Helper Functions**: Complex Google Docs API operations are implemented in `googleDocsApiHelpers.ts`:
   - `executeBatchUpdate` - Executes batch API requests
   - `findTextRange` - Locates text in documents
   - `getParagraphRange` - Finds paragraph boundaries
   - `buildUpdateTextStyleRequest` - Builds text styling requests
   - `buildUpdateParagraphStyleRequest` - Builds paragraph styling requests
   - Tab management helpers

3. **Type Definitions**: All Zod schemas and types are in `types.ts`:
   - Parameter schemas for tools
   - Style argument types
   - Custom error classes

4. **Authentication**: The `auth.ts` module handles OAuth2:
   - Loopback OAuth flow (not deprecated OOB)
   - Service account authentication support
   - Token persistence and refresh

## Key Implementation Details

### Authentication Methods

1. **OAuth2 (Default)**: Uses loopback flow on port 3000
   - Requires `credentials.json` with OAuth client config
   - Stores tokens in `token.json`
   - User must authorize via browser

2. **Service Account**: Set `SERVICE_ACCOUNT_PATH` environment variable
   - For automated/server environments
   - No browser interaction needed

### MCP Protocol Compatibility

**CRITICAL**: All logging must use `console.error`, never `console.log`. The MCP protocol uses stdout for JSON-RPC communication. Any `console.log` output will corrupt the protocol and cause connection failures.

### Document Indexing

Google Docs uses 1-based indexing:
- Index 1 is the beginning of the document
- All `startIndex` parameters start from 1
- `endIndex` is exclusive

### Tab Support

Documents can have multiple tabs:
- Use `listDocumentTabs` to discover tabs
- Pass `tabId` parameter to target specific tabs
- Omit `tabId` to use first/default tab

## Available Tools

### Document Operations
- `readGoogleDoc` - Read document content (text/json/markdown)
- `appendToGoogleDoc` - Append text to end of document
- `insertText` - Insert text at specific index
- `deleteRange` - Delete content range

### Tab Management
- `listDocumentTabs` - List all tabs in a document

### Formatting
- `applyTextStyle` - Character formatting (bold, italic, color, etc.)
- `applyParagraphStyle` - Paragraph formatting (alignment, spacing, headings)
- `formatMatchingText` - Find and format specific text

### Structure
- `insertTable` - Insert a new table
- `editTableCell` - Edit table cell content (not implemented)
- `insertPageBreak` - Insert page break

### Images
- `insertImageFromUrl` - Insert image from URL
- `insertLocalImage` - Upload and insert local image

### Comments
- `listComments` - List all comments
- `getComment` - Get comment with replies
- `addComment` - Add new comment
- `replyToComment` - Reply to comment
- `resolveComment` - Mark comment resolved
- `deleteComment` - Delete comment

### Drive Integration
- `listGoogleDocs` - List documents from Drive
- `searchGoogleDocs` - Search documents

## Development Notes

- Uses FastMCP framework for MCP server implementation
- Uses `googleapis` library for Google API calls
- Uses `zod` for schema validation
- Requires Node.js 20+

## Building and Running

### Local Development
```bash
npm install
npm run build
node ./dist/server.js
```

### Docker
```bash
docker-compose up --build
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SERVICE_ACCOUNT_PATH` | Optional: Path to service account JSON key file |
| `DOCKER_ENV` | Set automatically in Docker container |

## Testing

```bash
npm test
```

## Git Commit Guidelines

- Do NOT include "Generated with Claude Code" or similar AI attribution in commit messages
- Do NOT include "Co-Authored-By: Claude" or similar co-author tags
- Write commit messages as if authored solely by the developer
