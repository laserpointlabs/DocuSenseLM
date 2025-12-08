# Build and Release Guide

## Overview

DocuSenseLM is packaged as a desktop application using Electron. The Python backend is bundled as source code with its virtual environment for maximum compatibility.

## Prerequisites

### Development Machine
- **Node.js** 20.x or higher
- **Python** 3.12
- **npm** (comes with Node.js)

### Platform-Specific Tools
- **Linux**: AppImageTool (automatically handled by electron-builder)
- **Windows**: NSIS (automatically handled by electron-builder)
- **Mac**: DMG tools (automatically handled by electron-builder)

## Local Build (Current Platform)

```bash
# 1. Install dependencies
npm install

# 2. Set up Python environment
cd python
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..

# 3. Build the application
npm run build
```

The built application will be in the `dist/` directory:
- **Linux**: `DocuSenseLM-1.0.0.AppImage`
- **Windows**: `DocuSenseLM Setup 1.0.0.exe`
- **Mac**: `DocuSenseLM-1.0.0.dmg`

## Multi-Platform Builds (GitHub Actions)

For building all platforms (Linux, Windows, Mac) simultaneously:

1. Push a Git tag starting with `v`:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. GitHub Actions will automatically:
   - Build for Linux, Windows, and Mac in parallel
   - Create a GitHub Release
   - Upload installers as release assets

3. The workflow file is located at `.github/workflows/build.yml`

## Architecture

### Python Backend Packaging

Instead of using PyInstaller (which had dependency issues with `fastmcp`), we bundle the Python source code and virtual environment directly:

```
resources/
  python/
    venv/          # Complete Python virtual environment
    server.py      # Main server script
    *.py           # Other Python files
    requirements.txt
```

**Benefits:**
- No PyInstaller compatibility issues
- Easier debugging
- Faster builds
- Works with all Python dependencies

**Drawbacks:**
- Slightly larger file size (~200MB vs ~70MB with PyInstaller)
- Requires bundling the entire venv

### Electron Configuration

The `electron/main.ts` automatically detects whether it's running in development or production:

**Development Mode:**
- Uses local Python venv
- Loads from `http://localhost:5173` (Vite dev server)

**Production Mode:**
- Uses bundled Python venv from `resources/python/venv`
- Loads from `app.asar`

## Auto-Updates

The application uses `electron-updater` to check for updates on startup (production mode only).

**Configuration** (in `package.json`):
```json
"publish": {
  "provider": "github",
  "owner": "jdehart",
  "repo": "DocuSenseLM"
}
```

When a new release is published on GitHub, users will be notified automatically.

## Testing the Build

### Manual Testing

1. **Build the app:**
   ```bash
   npm run build
   ```

2. **Run the AppImage** (Linux):
   ```bash
   ./dist/DocuSenseLM-1.0.0.AppImage
   ```

3. **Verify backend is running:**
   ```bash
   curl http://localhost:14242/health
   # Should return: {"status":"ok","version":"1.0.1","rag":"enabled"}
   ```

4. **Check the UI:**
   - The app should show the DocuSenseLM interface
   - Navigate to Documents tab to see loaded documents
   - Try the chat interface

### Development Mode Testing

```bash
npm run electron:dev
```

This starts both the Vite dev server and Electron in development mode.

## Troubleshooting

### Python Backend Not Starting

Check the Electron console (Ctrl+Shift+I in dev mode) for errors:
- Look for messages like "Python exists: true/false"
- Check Python stderr output

### Missing Dependencies

If you get module not found errors:
```bash
cd python
source venv/bin/activate
pip install -r requirements.txt
```

### Build Failures

Clear build artifacts:
```bash
rm -rf dist/ dist-electron/ python/build/ python/dist/
npm run build
```

## File Size Considerations

Current AppImage size: ~200MB

**Breakdown:**
- Electron runtime: ~120MB
- Python venv (with all deps): ~70MB
- Application code: ~10MB

**To reduce size** (if needed):
- Use PyInstaller successfully (requires fixing hidden imports)
- Strip unnecessary packages from Python venv
- Remove development dependencies from venv

## Security Notes

1. **Code Signing** (for distribution):
   - **Mac**: Requires Apple Developer ID ($99/year)
   - **Windows**: Requires code signing certificate (~$200-400/year)
   - **Linux**: Not required

2. **Permissions:**
   - The app accesses the file system for document storage
   - Network access for OpenAI API calls
   - Local storage in `~/.config/docusenselm` (Linux)

## Release Checklist

Before creating a release:

- [ ] Update version in `package.json`
- [ ] Update version in `python/server.py` (if applicable)
- [ ] Test the build locally
- [ ] Verify all features work in packaged app
- [ ] Update CHANGELOG.md
- [ ] Create git tag and push
- [ ] Wait for GitHub Actions to complete
- [ ] Test downloaded release artifacts
- [ ] Publish release notes

## Support

For build issues, check:
1. Electron logs (in the app)
2. Python logs (stderr output)
3. GitHub Actions logs (for CI builds)

