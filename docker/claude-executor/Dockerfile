# Claude Code Executor Container
# Isolated environment for running Claude Code tasks via NightShift

FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    python3.13 \
    python3.13-venv \
    python3-pip \
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

# Install Claude Code via npm
RUN npm install -g @anthropic-ai/claude-code

# Create non-root user (UID will be overridden at runtime)
# Default to 1000 but build script can customize
ARG USER_ID=1000
ARG GROUP_ID=1000

# Handle case where UID/GID already exists (like node user in base image)
RUN if getent passwd ${USER_ID} > /dev/null 2>&1; then \
        echo "UID ${USER_ID} exists, using existing user"; \
        USER_NAME=$(getent passwd ${USER_ID} | cut -d: -f1); \
        usermod -d /home/executor -m -s /bin/bash $USER_NAME; \
        ln -sf /home/$USER_NAME /home/executor; \
    else \
        groupadd -g ${GROUP_ID} executor && \
        useradd -m -u ${USER_ID} -g executor -s /bin/bash executor; \
    fi

# Switch to non-root user (use the UID directly for compatibility)
USER ${USER_ID}:${GROUP_ID}
WORKDIR /work

# Set Claude as entrypoint
ENTRYPOINT ["claude"]
CMD ["--help"]
