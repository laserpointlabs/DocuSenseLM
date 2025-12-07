# Building and Releasing

## Cross-Platform Builds

This application combines a Node.js/Electron frontend with a Python backend. Because PyInstaller generates platform-specific executables, you cannot easily build all platforms from a single OS.

### Automated Builds (Recommended)

We use **GitHub Actions** to automatically build for Linux, Windows, and Mac.

1.  Push a tag starting with `v` (e.g., `v1.0.0`).
2.  The workflow in `.github/workflows/build.yml` will trigger.
3.  It will build for all 3 platforms in parallel.
4.  Artifacts (installers) will be uploaded to the GitHub Release.

### Local Builds

If you need to build locally:

**Linux:**
```bash
./build_app.sh
```

**Windows / Mac:**
You must run the build commands on a machine running that OS.
1.  Install Node.js and Python 3.12.
2.  Run:
    ```bash
    python -m venv python/venv
    # Activate venv (Windows: python\venv\Scripts\activate, Mac: source python/venv/bin/activate)
    pip install -r python/requirements.txt
    npm install
    npm run build
    ```

## Auto-Updates

The app is configured to use `electron-updater` with GitHub Releases.
1.  Ensure `package.json` has the correct `repository` field.
2.  Publish a new release on GitHub with the artifacts.
3.  The app will check for updates on startup and notify the user.

