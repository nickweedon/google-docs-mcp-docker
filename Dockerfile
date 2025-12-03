# Google Docs MCP Server Docker Image
# This Dockerfile builds the google-docs-mcp server from local source
# Source files include patches:
# - auth.ts: Uses loopback OAuth flow instead of deprecated OOB flow
# - googleDocsApiHelpers.ts: Uses console.error instead of console.log for MCP protocol compatibility

FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files first for better caching
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

# Copy source files and configuration
COPY src/ ./src/
COPY tsconfig.json index.js ./

# Build the TypeScript code
RUN npm run build

# Create directory for credentials (will be mounted as volume)
RUN mkdir -p /app/credentials

# Expose port 3000 for OAuth loopback callback during authentication
EXPOSE 3000

# Set environment variable to indicate Docker environment
ENV DOCKER_ENV=true

# Default command runs the MCP server
CMD ["node", "./dist/server.js"]
