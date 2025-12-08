#!/bin/bash

# Local build script for DocuSenseLM
# This builds the app locally for testing

echo "🏗️  Building DocuSenseLM locally..."

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf dist/

# Build the web app
echo "🌐 Building web app..."
npm run build:web

# Build the Electron app
echo "⚡ Building Electron app..."
npm run build:electron

# Create Linux AppImage
echo "🐧 Creating Linux AppImage..."
npx electron-builder --linux

# Create Windows installer (if on Windows or using wine)
echo "🪟 Creating Windows installer..."
if command -v wine &> /dev/null; then
    echo "Using wine for Windows build..."
    npx electron-builder --win
else
    echo "Skipping Windows build (wine not available)"
fi

echo "✅ Build complete!"
echo ""
echo "📦 Generated files:"
ls -la dist/ | grep -E "\.(AppImage|exe)$"
echo ""
echo "🚀 To test auto-updates:"
echo "1. Install the current version (1.0.4)"
echo "2. Create a new version (1.0.5) with changes"
echo "3. Build and test update detection"
