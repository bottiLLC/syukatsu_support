#!/usr/bin/env bash
cd "$(dirname "$0")"

echo "==================================================="
echo "  App Launcher (Mac/Linux)"
echo "==================================================="
echo ""

# 1. Auto-detect and fix 'uv' command path
if ! command -v uv &> /dev/null; then
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
fi

if ! command -v uv &> /dev/null; then
    echo "[ERROR] Package manager 'uv' not found."
    echo "Please install uv by running the following command in terminal:"
    echo 'curl -LsSf https://astral.sh/uv/install.sh | sh'
    echo ""
    read -p "Press [Enter] key to exit..."
    exit 1
fi

# 2. Auto-detect Python entry point
ENTRY_POINT=""
for file in app.py main.py src/app.py; do
    if [ -f "$file" ]; then
        ENTRY_POINT="$file"
        break
    fi
done

if [ -z "$ENTRY_POINT" ]; then
    echo "[ERROR] Python entry point (app.py / main.py / src/app.py) not found."
    echo ""
    read -p "Press [Enter] key to exit..."
    exit 1
fi

echo "[INFO] Entry point found: $ENTRY_POINT"

# 3. Auto-create .venv and sync package dependencies
if [ ! -d ".venv" ]; then
    echo "[INFO] Virtual environment (.venv) not found. Creating virtual environment..."
    uv venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment (.venv)."
        echo ""
        read -p "Press [Enter] key to exit..."
        exit 1
    fi
    echo "[INFO] Virtual environment created successfully."
fi

if [ -f "pyproject.toml" ]; then
    echo "[INFO] Verifying and syncing package dependencies (uv sync)..."
    uv sync
    if [ $? -ne 0 ]; then
        echo "[ERROR] Dependency sync (uv sync) failed."
        echo "Please check your pyproject.toml configuration."
        echo ""
        read -p "Press [Enter] key to exit..."
        exit 1
    fi
fi

# 4. Launch App
echo ""
echo "[INFO] Launching App..."
echo ""

uv run python "$ENTRY_POINT"

if [ $? -ne 0 ]; then
    echo ""
    echo "[WARNING] Application stopped or encountered an error."
fi

echo ""
read -p "Press [Enter] key to exit..."
