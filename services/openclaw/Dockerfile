FROM node:22-slim

# Install basic dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    python3 \
    python3-pip \
    python3-requests \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r openclaw && useradd -r -g openclaw -d /home/openclaw -m openclaw
USER openclaw
WORKDIR /home/openclaw

# Install OpenClaw globally in the user's home (npm prefix)
ENV NPM_CONFIG_PREFIX=/home/openclaw/.npm-global
ENV PATH=$PATH:/home/openclaw/.npm-global/bin
RUN npm install -g openclaw@latest

# Prepare OpenClaw home, state, and workspace directories
RUN mkdir -p /home/openclaw/.openclaw/state /home/openclaw/.openclaw/.openclaw/workspace/skills

# Copy custom skills (alpha-k, pm-agent) into openclaw workspace skills directory
COPY --chown=openclaw:openclaw skills/ /home/openclaw/.openclaw/.openclaw/workspace/skills/

# Environment variables for OpenClaw (can be overridden by docker-compose)
ENV OPENCLAW_HOME=/home/openclaw/.openclaw
ENV OPENCLAW_STATE_DIR=/home/openclaw/.openclaw/state

# Expose UI port (default)
EXPOSE 18789

# Entry point starts the gateway
# Note: In a real environment, you might need to run 'openclaw onboard' first,
# but we aim for non-interactive startup using environment variables.
# Entry point starts the gateway in foreground mode
CMD ["openclaw", "gateway", "--allow-unconfigured", "--bind", "lan"]
