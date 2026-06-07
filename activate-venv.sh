#!/bin/bash
# Helper script to ensure we're using the virtual environment
# Source this script before running any Python commands in the project

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PATH="$ROOT_DIR/venv"

if [ ! -d "$VENV_PATH" ]; then
    echo "❌ Virtual environment not found at $VENV_PATH"
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
    echo "✅ Virtual environment created"
fi

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

echo "✅ Activated virtual environment: $VENV_PATH"
echo "Python: $(which python)"
echo "pip: $(which pip)"