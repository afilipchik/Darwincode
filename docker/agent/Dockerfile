FROM python:3.12-slim

ARG TARGETARCH

# System tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential jq ca-certificates sudo \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 (for Claude Code CLI and JS projects)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Python tools
RUN pip install --no-cache-dir pytest ruff uv

# Java (OpenJDK 21) + Maven
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jdk-headless maven \
    && rm -rf /var/lib/apt/lists/*
RUN ARCH=$(dpkg --print-architecture) && \
    ln -s /usr/lib/jvm/java-21-openjdk-${ARCH} /usr/lib/jvm/java-21-openjdk
ENV JAVA_HOME="/usr/lib/jvm/java-21-openjdk"

# Go (minimal, no docs)
RUN GO_ARCH=$(case "${TARGETARCH}" in arm64) echo "arm64";; *) echo "amd64";; esac) && \
    curl -fsSL "https://go.dev/dl/go1.23.6.linux-${GO_ARCH}.tar.gz" | tar -C /usr/local -xzf -
ENV PATH="/usr/local/go/bin:${PATH}"

# Rust (minimal profile — no docs, no clippy, no rustfmt to save ~1GB)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --profile minimal --default-toolchain stable && \
    rm -rf /root/.rustup/toolchains/*/share/doc
ENV PATH="/root/.cargo/bin:${PATH}"

# Create non-root agent user (claude CLI refuses --dangerously-skip-permissions as root)
RUN useradd -m -s /bin/bash agent && \
    echo "agent ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Copy rust/cargo to agent user
RUN cp -r /root/.rustup /home/agent/.rustup && \
    cp -r /root/.cargo /home/agent/.cargo && \
    chown -R agent:agent /home/agent/.rustup /home/agent/.cargo

# Git config for agent user
RUN su - agent -c 'git config --global user.email "darwincode-agent@darwincode"' && \
    su - agent -c 'git config --global user.name "Darwincode Agent"'

# Workspace setup (owned by agent user)
RUN mkdir -p /workspace/results /workspace/transcript /workspace/repo && \
    chown -R agent:agent /workspace

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PATH="/home/agent/.cargo/bin:${PATH}"

USER agent
WORKDIR /workspace
ENTRYPOINT ["/entrypoint.sh"]
