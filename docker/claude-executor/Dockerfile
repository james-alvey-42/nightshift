# Claude Code Executor Container
# Isolated environment for running Claude Code tasks via NightShift

FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    # Playwright dependencies (for mcp__playwright__)
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Install Claude CLI via npm
# Note: Replace with actual package name if different
RUN npm install -g @anthropic/claude-cli

# Create non-root user (UID will be overridden at runtime)
# Default to 1000 but build script can customize
ARG USER_ID=1000
ARG GROUP_ID=1000

RUN groupadd -g ${GROUP_ID} executor && \
    useradd -m -u ${USER_ID} -g executor -s /bin/bash executor

# Switch to non-root user
USER executor
WORKDIR /work

# Set Claude as entrypoint
ENTRYPOINT ["claude"]
CMD ["--help"]
