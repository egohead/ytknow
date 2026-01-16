#!/bin/bash

# YouTube to Knowledge - Installation Script (v2)
# Handles PEP 668 (externally-managed-environment) using a local venv.

set -e

echo "🚀 Installing YouTube to Knowledge (ytknow)..."

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "📥 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install dependencies via Homebrew
echo "📦 Installing yt-dlp and ffmpeg..."
brew install yt-dlp ffmpeg

# Setup Virtual Environment
echo "🐍 Setting up Python Virtual Environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "📦 Installing Python dependencies into venv..."
pip install --upgrade pip
echo "📦 Installing ytknow package in editable mode..."
pip install -e .

# Remove legacy manual wrapper if it exists
LEGACY_PATH="/usr/local/bin/ytknow"
if [ -f "$LEGACY_PATH" ]; then
    echo "🗑️ Removing legacy wrapper at $LEGACY_PATH..."
    sudo rm "$LEGACY_PATH"
fi

# Symlink the correct binary from venv
VENV_BIN="$(pwd)/.venv/bin/ytknow"
echo "🔗 linking $VENV_BIN to $LEGACY_PATH"
sudo ln -sf "$VENV_BIN" "$LEGACY_PATH"

echo "✅ Installation complete!"
echo "You can now run 'ytknow [URL]' from anywhere."
