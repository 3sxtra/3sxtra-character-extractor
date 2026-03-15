#!/bin/bash
# SF3:3rd Strike Character Editor Launcher
# Cross-platform launcher for macOS and Linux

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting SF3:3rd Strike Character Editor..."
echo

# Check if uv is available
if command -v uv &> /dev/null; then
    echo "[INFO] Syncing dependencies with uv..."
    uv sync
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to sync dependencies."
        exit 1
    fi
    echo "[INFO] Starting Character Editor..."
    uv run python run_character_editor.py
else
    echo "[INFO] uv not found. Using Python directly..."
    echo "[INFO] Make sure dependencies are installed: pip install -r requirements.txt"
    python3 run_character_editor.py
fi
