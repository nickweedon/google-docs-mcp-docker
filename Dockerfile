# Google Docs MCP Server Docker Image
# This Dockerfile builds the google-docs-mcp server from source
# with a patched auth.ts that uses loopback OAuth instead of deprecated OOB flow

FROM node:20-alpine

# Install git for cloning the repository
RUN apk add --no-cache git

# Set working directory
WORKDIR /app

# Clone the repository
RUN git clone https://github.com/a-bonus/google-docs-mcp.git .

# Copy our patched auth.ts that uses loopback OAuth flow
# (The original uses deprecated OOB flow which Google blocked)
COPY src/auth.ts /app/src/auth.ts

# Install dependencies
RUN npm install

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
