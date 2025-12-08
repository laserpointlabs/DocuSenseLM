# DocuSenseLM Build Process Documentation

## Overview

DocuSenseLM uses a comprehensive CI/CD pipeline built on GitHub Actions to automatically build cross-platform desktop applications for Linux and Windows. This document outlines the complete build process, from local development to production releases.

## Architecture

- **Framework:** Electron + React + TypeScript
- **Build Tool:** electron-builder
- **CI/CD:** GitHub Actions
- **Platforms:** Linux (AppImage) and Windows (NSIS installer)
- **Auto-Updates:** electron-updater with GitHub releases

## Prerequisites

### Local Development
- Node.js 20+
- npm or yarn
- Python 3.12+ (for backend services)
- Git

### CI/CD Requirements
- GitHub repository with Actions enabled
- `GH_TOKEN` secret configured (see setup below)

## Local Build Process

### Quick Start
```bash
# Install dependencies
npm install

# Build for current platform
npm run build:linux    # Linux AppImage
npm run build:windows  # Windows installer

# Or build all platforms
npm run build  # Full production build
```

### Build Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build:web` | Build React frontend only |
| `npm run build:electron` | Compile Electron TypeScript |
| `npm run build:linux` | Build Linux AppImage |
| `npm run build:windows` | Build Windows installer |
| `npm run build` | Full production build |

### Output Locations

Built applications are saved in the `dist/` directory:
- `DocuSenseLM-X.Y.Z.AppImage` (Linux)
- `DocuSenseLM Setup X.Y.Z.exe` (Windows)

## CI/CD Pipeline

### Workflow Configuration

The CI/CD pipeline is defined in `.github/workflows/build.yml`:

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'  # Triggers on version tags

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]

    steps:
      - name: Check out Git repository
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install Node dependencies
        run: npm ci

      - name: Build and Release Electron App
        env:
          GH_TOKEN: ${{ secrets.GH_TOKEN }}
        run: |
          npm run build:web
          npm run build:electron
          npx electron-builder --${{ matrix.os == 'ubuntu-latest' && 'linux' || 'win' }} --publish never

      - name: Upload Build Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: DocuSenseLM-${{ matrix.os == 'ubuntu-latest' && 'linux' || 'windows' }}-${{ github.ref_name }}
          path: dist/*.*
          retention-days: 30
```

### Triggering Builds

Builds are automatically triggered when you push a version tag:

```bash
# Create and push a version tag
git tag v1.0.14
git push origin v1.0.14
```

### Build Matrix

The pipeline runs on two platforms simultaneously:

| Platform | Runner | Output Format | Duration |
|----------|--------|---------------|----------|
| Linux | `ubuntu-latest` | AppImage | ~1-2 minutes |
| Windows | `windows-latest` | NSIS installer | ~2-3 minutes |

## Artifact Management

### Downloading Artifacts

After successful builds, artifacts are available for 30 days:

1. Go to: https://github.com/laserpointlabs/DocuSenseLM/actions
2. Click on the latest successful workflow run
3. Scroll to "Artifacts" section
4. Download:
   - `DocuSenseLM-linux-vX.Y.Z` (contains AppImage)
   - `DocuSenseLM-windows-vX.Y.Z` (contains .exe installer)

### Artifact Contents

**Linux Artifact:**
- `DocuSenseLM-X.Y.Z.AppImage` - Self-contained Linux application

**Windows Artifact:**
- `DocuSenseLM Setup X.Y.Z.exe` - NSIS installer
- `DocuSenseLM Setup X.Y.Z.exe.blockmap` - Update metadata

## Publishing Releases

### Automatic Publishing

To enable automatic publishing to GitHub Releases:

1. Set `--publish always` in the workflow
2. Ensure `GH_TOKEN` has release permissions
3. Builds will automatically create GitHub releases

### Manual Publishing

For manual releases:

1. Download artifacts from Actions
2. Go to GitHub Releases
3. Create new release
4. Upload the installer files

## Auto-Update System

### Configuration

Auto-updates are configured in `electron-builder.config.js`:

```javascript
publish: {
  provider: "github",
  owner: "laserpointlabs",
  repo: "DocuSenseLM"
}
```

### Update Process

1. **Build new version** with higher version number
2. **Publish release** with installer files
3. **Running applications** automatically detect updates
4. **Users download and install** updates seamlessly

### Testing Updates

To test auto-updates:

1. Install version X.Y.Z
2. Build and release version X.Y.(Z+1)
3. Run the installed application
4. Check for updates (Help → Check for Updates)
5. Verify update download and installation

## Troubleshooting

### Common Issues

**Build Fails with Icon Errors:**
- Ensure icon files exist in `build/` directory
- Linux builds don't require 256x256 icons
- Check electron-builder configuration

**Publishing Fails:**
- Verify `GH_TOKEN` secret is set
- Ensure token has `repo` and `workflow` permissions
- Check GitHub repository permissions

**Artifacts Not Uploading:**
- Confirm `actions/upload-artifact` step is present
- Check artifact naming and path patterns
- Verify build completed successfully

### Debug Commands

```bash
# Check build status
gh run list --limit 5

# View build logs
gh run view <run-id> --log

# Download artifacts via CLI
gh run download <run-id>
```

## Version Management

### Version Bumping

Update version in multiple places:

1. `package.json` - `"version": "X.Y.Z"`
2. `src/App.tsx` - `const APP_VERSION = "X.Y.Z"`
3. Create git tag: `git tag vX.Y.Z`

### Semantic Versioning

- **MAJOR:** Breaking changes (X.0.0)
- **MINOR:** New features (X.Y.0)
- **PATCH:** Bug fixes (X.Y.Z)

## Security Considerations

### Token Management
- `GH_TOKEN` should have minimal required permissions
- Rotate tokens regularly
- Never commit tokens to repository

### Artifact Security
- Artifacts are signed by GitHub Actions
- Verify checksums when distributing
- Use HTTPS for all downloads

## Performance Optimization

### Build Times
- Linux builds: ~1-2 minutes
- Windows builds: ~2-3 minutes
- Parallel execution saves time

### Caching
- Node.js dependencies are cached
- Build artifacts retained for 30 days

## Future Enhancements

### Planned Improvements
- macOS builds (currently disabled due to macOS runner costs)
- Automated testing integration
- Code signing for Windows executables
- Multi-architecture builds (ARM64)

### Extended Platforms
```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest, macos-latest]
    arch: [x64, arm64]  # Future: ARM64 support
```

---

## Quick Reference

**Build locally:**
```bash
npm run build:linux   # Linux
npm run build:windows # Windows
```

**Trigger CI build:**
```bash
git tag v1.0.15
git push origin v1.0.15
```

**Download artifacts:**
GitHub Actions → Latest run → Artifacts section

**Test updates:**
Install old version → Build new version → Check for updates

---

*Last updated: December 2025*
*DocuSenseLM Build Process v1.0.13*
