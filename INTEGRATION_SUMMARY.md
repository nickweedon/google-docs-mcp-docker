# MCP Mapped Resource Library Integration Summary

## Overview

This document summarizes the integration of `mcp_mapped_resource_lib` into the Google Docs MCP Server, enabling resource-based file uploads through shared Docker volumes.

## What Was Added

### 1. New Dependencies

- **mcp-mapped-resource-lib** - pip-installable library for blob storage operations
- **python-magic** - Dependency for MIME type detection (auto-installed)

### 2. New Module: `src/google_docs_mcp/api/resources.py`

Contains three main functions:

- `upload_image_to_drive_from_resource()` - Upload images to Google Drive using resource IDs
- `upload_file_to_drive_from_resource()` - Upload any file to Google Drive using resource IDs
- `insert_image_from_resource()` - Insert images into documents using resource IDs

### 3. New MCP Tool Methods

Added to `src/google_docs_mcp/server.py`:

- `upload_image_to_drive_from_resource` - Tool for uploading images
- `upload_file_to_drive_from_resource` - Tool for uploading files
- `insert_image_from_resource` - Tool for inserting images into documents

### 4. Docker Configuration Updates

**docker-compose.yml:**
- Added `blob-storage` named volume
- Mounted volume at `/mnt/blob-storage`
- Set `BLOB_STORAGE_ROOT=/mnt/blob-storage` environment variable

**docker-compose.devcontainer.yml:**
- Added same blob storage volume and configuration for development

### 5. Documentation Updates

**README.md:**
- Added "Resource-Based File Uploads" section with:
  - Explanation of why to use resource-based uploads
  - Setup instructions for Docker volumes
  - Claude Desktop config examples
  - Example usage workflow
  - Resource ID format documentation

**CLAUDE.md:**
- Added `api/resources.py` to separation of concerns
- Added three new tools to available tools list
- Added `BLOB_STORAGE_ROOT` to environment variables table
- Added `mcp-mapped-resource-lib` to development notes

## How It Works

### Traditional Upload Flow (Base64)
```
Other MCP Server → Encode file as base64 → Send through MCP protocol →
This server → Decode base64 → Upload to Google Drive
```

### Resource-Based Upload Flow
```
Other MCP Server → Upload to shared volume → Return resource ID →
User passes resource ID to this server →
This server → Read from shared volume → Upload to Google Drive
```

## Benefits

1. **Efficiency** - No base64 encoding/decoding overhead
2. **Scalability** - Large files don't bloat the MCP protocol
3. **Interoperability** - Multiple MCP servers can share resources
4. **Simplicity** - Only small resource identifiers passed through MCP

## Resource ID Format

Resource identifiers follow the pattern: `blob://TIMESTAMP-HASH.EXT`

Example: `blob://1733437200-a3f9d8c2b1e4f6a7.png`

Components:
- `TIMESTAMP` - Unix timestamp when file was uploaded
- `HASH` - SHA256 hash (truncated) for uniqueness
- `EXT` - Original file extension

## Configuration Requirements

### Environment Variables

```bash
BLOB_STORAGE_ROOT=/mnt/blob-storage          # Required
BLOB_STORAGE_MAX_SIZE_MB=100                 # Optional (default: 100)
BLOB_STORAGE_TTL_HOURS=24                    # Optional (default: 24)
```

**Required:**
- `BLOB_STORAGE_ROOT` - Path to blob storage directory. Must be set for resource-based tools to function.

**Optional:**
- `BLOB_STORAGE_MAX_SIZE_MB` - Maximum file size in MB (default: 100). Files larger than this will be rejected.
- `BLOB_STORAGE_TTL_HOURS` - Time-to-live for blobs in hours (default: 24). Blobs older than this will be automatically cleaned up by the library's lazy cleanup mechanism.

### Docker Volume

The volume name must be consistent across all MCP servers that need to share resources:

```yaml
volumes:
  blob-storage:
    driver: local
```

### Claude Desktop Config

When using with Claude Desktop, mount the volume and configure environment variables:

```json
{
  "mcpServers": {
    "google-docs": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "blob-storage:/mnt/blob-storage",
        "-e", "BLOB_STORAGE_ROOT=/mnt/blob-storage",
        "-e", "BLOB_STORAGE_MAX_SIZE_MB=100",
        "-e", "BLOB_STORAGE_TTL_HOURS=24",
        "workspace-google-docs-mcp:latest"
      ]
    }
  }
}
```

Adjust the `MAX_SIZE_MB` and `TTL_HOURS` values as needed for your use case.

## Testing

All existing tests pass (98 tests):
- ✓ Bulk operations tests
- ✓ Style operations tests
- ✓ Helper function tests
- ✓ Image URL validation tests
- ✓ Type validation tests

New resource module tested:
- ✓ Module imports successfully
- ✓ BlobStorage initializes correctly
- ✓ Configuration works as expected

## Files Modified

1. `/workspace/pyproject.toml` - Added dependency
2. `/workspace/src/google_docs_mcp/server.py` - Added import and 3 new tools
3. `/workspace/docker-compose.yml` - Added volume and environment variable
4. `/workspace/docker-compose.devcontainer.yml` - Added volume and environment variable
5. `/workspace/README.md` - Added comprehensive documentation section
6. `/workspace/CLAUDE.md` - Updated project documentation

## Files Created

1. `/workspace/src/google_docs_mcp/api/resources.py` - New module with 3 functions

## Backwards Compatibility

✓ All existing functionality remains unchanged
✓ Resource-based tools are optional (only used when explicitly called)
✓ Existing upload tools (base64-based) continue to work
✓ No breaking changes to existing APIs

## Next Steps for Users

1. Rebuild Docker image: `docker-compose build`
2. Update Claude Desktop config with blob storage volume
3. Ensure other MCP servers that will share resources also mount the same volume
4. Use the new resource-based tools when transferring files between MCP servers
