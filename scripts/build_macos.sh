#!/bin/bash

# Build script for CTBC Repository Daily Reload (macOS)
set -e

echo "🔨 Building CTBC Repository Daily Reload..."

# Install dependencies using uv
echo "📦 Installing dependencies with uv..."
uv sync
uv add pyinstaller

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf dist/ build/ *.spec
rm -f main

# Build main executable
echo "🔧 Building main sync executable..."
uv run pyinstaller \
  --onefile \
  --name main \
  --add-data config:config \
  --hidden-import=github \
  --hidden-import=dotenv \
  --hidden-import=requests \
  --clean \
  sync_repos.py

# Build cleanup tool executable
uv run pyinstaller \
  --onefile \
  --name cleanup_tool \
  --add-data config:config \
  --hidden-import=github \
  --hidden-import=dotenv \
  --hidden-import=requests \
  --clean \
  cleanup_tool.py

# Move executables to root directory
mv dist/main ./main
mv dist/cleanup_tool ./cleanup_tool

# Clean up build artifacts
echo "🧹 Cleaning up build artifacts..."
rm -rf dist/ build/ *.spec
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

echo ""
echo "✅ Build complete!"
echo "📦 Executables created:"
echo "  ./main          - Main sync tool"
echo "  ./cleanup_tool   - Cleanup tool"
echo ""
echo "Usage:"
echo "  ./main          # Sync repositories to IQ Server"
echo ""
echo "⚠️  Make sure to configure config/.env before running!"
echo ""