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

echo "✅ Installation complete!"
echo "You can now run 'ytknow [URL]' from anywhere."
