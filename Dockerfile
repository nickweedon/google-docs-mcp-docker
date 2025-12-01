# Google Docs MCP Server Docker Image
# This Dockerfile builds the google-docs-mcp server from source

FROM node:20-alpine

# Install git for cloning the repository
RUN apk add --no-cache git

# Set working directory
WORKDIR /app

# Clone the repository
RUN git clone https://github.com/a-bonus/google-docs-mcp.git .

# Install dependencies
RUN npm install

# Build the TypeScript code
RUN npm run build

# Create directory for credentials (will be mounted as volume)
RUN mkdir -p /app/credentials

# The server expects credentials.json and token.json in the app directory
# These will be symlinked from the credentials volume at runtime

# Expose port for SSE transport (if needed in future)
# The default MCP server uses stdio, but SSE might be used for remote connections
EXPOSE 3000

# Set environment variable to indicate Docker environment
ENV DOCKER_ENV=true

# Default command runs the MCP server
# Note: For initial auth, you may need to run interactively
CMD ["node", "./dist/server.js"]
