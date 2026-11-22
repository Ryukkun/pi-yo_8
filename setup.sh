#!/bin/bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]:-$0}")"

echo "=== pi-yo_8 Setup ==="

# 1. Deno
if [ -f "$HOME/.deno/env" ]; then
    # shellcheck disable=SC1091
    source "$HOME/.deno/env"
fi

if ! command -v deno >/dev/null 2>&1; then
    echo "[1/4] Installing Deno..."
    curl -fsSL https://deno.land/install.sh | sh -s -- -y
    if [ -f "$HOME/.deno/env" ]; then
        # shellcheck disable=SC1091
        source "$HOME/.deno/env"
    fi
    export PATH="$HOME/.deno/bin:$PATH"
else
    echo "[1/4] Deno is already installed: $(deno --version | head -n 1)"
fi

# 2. uv
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
    echo "[2/4] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
else
    echo "[2/4] uv is already installed: $(uv --version)"
fi

# 3. Docker & bgutil-ytdlp-pot-provider server
if ! command -v docker >/dev/null 2>&1; then
    echo "[3/4] ERROR: docker is not installed. Please install Docker first." >&2
    exit 1
fi

CONTAINER_NAME="bgutil-provider"
IMAGE_NAME="brainicism/bgutil-ytdlp-pot-provider"

if docker ps -q -f "name=^${CONTAINER_NAME}$" | grep -q .; then
    echo "[3/4] Docker container '${CONTAINER_NAME}' is already running."
elif docker ps -aq -f "name=^${CONTAINER_NAME}$" | grep -q .; then
    echo "[3/4] Starting existing Docker container '${CONTAINER_NAME}'..."
    docker start "${CONTAINER_NAME}"
else
    echo "[3/4] Creating and starting Docker container '${CONTAINER_NAME}'..."
    docker run --name "${CONTAINER_NAME}" \
        --restart unless-stopped \
        -d --init \
        -p 127.0.0.1:4416:4416 \
        "${IMAGE_NAME}"
fi

# 4. Python dependencies
echo "[4/4] Syncing Python dependencies with uv..."
uv sync

echo "=== Setup complete! ==="
