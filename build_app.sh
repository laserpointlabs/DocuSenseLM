#!/bin/bash

# Build Script for NDA Tool Lite

echo "🚀 Starting Build Process..."

# Warning about cross-platform builds
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "⚠️  Note: You are building on Linux."
    echo "   This will build the Linux AppImage."
    echo "   To build for Windows (.exe) or Mac (.dmg), you generally need to run this on those OSs"
    echo "   because PyInstaller generates OS-specific executables."
    echo "   We recommend using the GitHub Actions workflow (.github/workflows/build.yml) for multi-platform releases."
    echo "   Continuing with Linux build..."
    sleep 3
fi

# 1. Setup Python Environment
echo "🐍 Setting up Python environment..."
if [ ! -d "python/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv python/venv
fi

source python/venv/bin/activate
pip install -r python/requirements.txt

# 2. Build Python Backend
echo "🔨 Building Python executable..."
# Clean previous builds
rm -rf python/dist/server
rm -rf python/build

# Run PyInstaller using the python from venv
python -m PyInstaller --clean \
    --name server \
    --distpath ./python/dist \
    --workpath ./python/build \
    --specpath ./python \
    --onefile \
    --additional-hooks-dir=python \
    --hidden-import=key_value \
    --hidden-import=diskcache \
    --hidden-import=pickletools \
    python/server.py

if [ $? -ne 0 ]; then
    echo "❌ Python build failed!"
    exit 1
fi

echo "✅ Python build successful."

# 3. Setup Node Environment
echo "📦 Installing Node dependencies..."
npm install

# 4. Build Electron App
echo "⚡ Building Electron application..."
npm run build

if [ $? -ne 0 ]; then
    echo "❌ Electron build failed!"
    exit 1
fi

echo "🎉 Build Complete!"
echo "The application installer is located in the 'dist' directory."
