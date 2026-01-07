## DocuSenseLM Auto-Update Implementation (Windows / `electron-updater`)

This document is the **source of truth** for how DocuSenseLM handles **auto-updates on Windows** (NSIS installer) using [`electron-updater`](https://www.electron.build/auto-update).

It exists because this was historically fragile: we had update installs that stalled, `latest.yml` pointing at the wrong installer name, and the NSIS installer getting stuck in “app cannot be closed” loops due to lingering processes.

---

## Goals (what “best practice” means for us)

- **No manual uninstall/reinstall** needed for typical upgrades.
- **User-first UX**:
  - On startup, we may **check quietly**.
  - We **do not** show a “No updates available” popup during background checks.
  - We **do** show “You’re up to date” when the user explicitly clicks **Help → Check for Updates…**.
  - We **never download** silently; the user confirms download (VS Code-like behavior).
  - Once downloaded, we show a clear **Restart and install** prompt.
- **Robust Windows installer behavior**:
  - When installing an update, the app must release file handles and exit cleanly.
  - The Python backend (child process) must be shut down to prevent NSIS loops.
- **Release metadata correctness**:
  - `latest.yml` must reference the **exact installer filename** uploaded to GitHub Releases.

---

## Key files

- **Updater implementation**: `electron/main.ts`
- **Build metadata + artifact naming**:
  - `package.json` → `build.win.artifactName` / `build.nsis.artifactName` / `build.publish`
  - `electron-builder.config.js` (mirrors critical build fields; also sets PE metadata like `FileDescription`)
- **CI release pipeline**: `.github/workflows/build.yml`
- **Updater smoke test**: `tests/smoke/startup.spec.ts`
- **Functional ingestion E2E**: `tests/test_lite_e2e.py`

---

## Architecture overview (how updates work end-to-end)

### What `electron-updater` uses on Windows

At runtime (installed app):

- **`app-update.yml`**: a config file in the packaged app’s `resources` directory that tells `electron-updater` where to look for updates (GitHub provider, repo, etc.).
- **GitHub Release assets**:
  - `latest.yml` (metadata that includes the correct installer filename + checksum)
  - `DocuSenseLM-Setup-<version>.exe` (NSIS installer)
  - `.blockmap` files (used by differential downloads)

The combination of **`app-update.yml` + `latest.yml`** is what makes update checks and downloads work.

### When the updater is enabled (guardrails)

We only enable updates when it’s actually safe and meaningful.

In `electron/main.ts`, `canUseAutoUpdater()`:

- Requires `app.isPackaged === true`
- Requires `process.resourcesPath/app-update.yml` to exist

This avoids confusing “it doesn’t update” behavior in **dev** or **win-unpacked** builds where `app-update.yml` may not exist.

---

## Runtime flow (what happens when a user runs the app)

### 1) Startup background check (quiet)

In production/dist builds, we do a **quiet check** shortly after creating the window:

- `autoUpdater.checkForUpdates()` is called with a short delay.
- If no update exists: we **log only** (no modal dialog).
- If an update exists: we prompt the user to download.

This is implemented in `createWindow()` and `setupAutoUpdater()` in `electron/main.ts`.

### 2) User-initiated check (explicit feedback)

In the app menu (**Help → Check for Updates…**), we run:

- `manualUpdateCheckInProgress = true`
- `autoUpdater.checkForUpdates()`

If no update exists:

- We show a dialog: **“No updates available / You’re up to date”**

If an update exists:

- We show the “Update available → Download?” prompt (see below).

---

## Updater UX state machine (what the user sees)

We use a small state machine in `electron/main.ts`:

- `idle`
- `checking`
- `available`
- `downloading`
- `downloaded`
- `error`

State updates are centralized via `setUpdateState(...)`, which also logs transitions to `main.log`.

### “Update available” prompt (user confirms download)

On `update-available`:

- We set state → `available`
- We show a dialog:
  - Buttons: **Download**, **Later**
- If the user chooses **Download**:
  - We set state → `downloading`
  - Call `autoUpdater.downloadUpdate()`

This matches the “don’t surprise-download” behavior users expect.

### Download progress feedback

On `download-progress`:

- We update state → `downloading` and track `percent`
- We set Windows taskbar progress via `BrowserWindow.setProgressBar(...)`

This prevents the “nothing is happening” feeling during larger updates.

### “Restart and install” prompt (user confirms install)

On `update-downloaded`:

- We set state → `downloaded`
- We show a dialog:
  - Buttons: **Restart and install**, **Later**
- If the user chooses **Restart and install**:
  - We run `quitAndInstallUpdateNow()`

---

## The hardest Windows edge case: NSIS “app cannot be closed” loops

### Root cause

NSIS updates need the running app to fully exit and release file handles. We spawn a Python backend, so **even if the Electron window closes**, the Python child can keep handles open and cause NSIS to repeatedly prompt:

> “DocuSenseLM cannot be closed. Please close it manually…”

### The fix: aggressive shutdown before install

`quitAndInstallUpdateNow()` in `electron/main.ts` does three things before invoking the installer:

- **Aggressively closes windows**
  - Destroys all `BrowserWindow`s and removes close listeners to avoid blocking shutdown.
- **Stops the Python backend**
  - First attempts a graceful kill
  - Then force-kills after a short grace period (so handles are released).
- **Calls `autoUpdater.quitAndInstall(false, true)`**
  - And if the app still won’t quit, it falls back to `process.exit(0)` after a short delay.

This is intentionally defensive: preventing the installer loop is more important than a “perfectly graceful” exit in the update path.

### Extra safeguard: `before-quit-for-update`

`electron-updater` emits `before-quit-for-update`. Some versions of typings don’t include it, so we attach via `(autoUpdater as any)` and:

- mark `quittingForUpdate = true`
- kill Python again (belt-and-suspenders)

---

## “latest.yml mismatch” (the other historical root cause)

### What broke

When electron-builder generates `latest.yml`, it writes the expected installer name. If our **uploaded asset name** differs (dots/spaces vs hyphens, etc.), updates break because `electron-updater` tries to download a file that doesn’t exist.

### The fix

We force a stable installer name in both config surfaces:

- `package.json`
  - `build.win.artifactName = "DocuSenseLM-Setup-${version}.${ext}"`
  - `build.nsis.artifactName = "DocuSenseLM-Setup-${version}.${ext}"`
- `electron-builder.config.js`
  - `win.artifactName = "DocuSenseLM-Setup-${version}.${ext}"`
  - `nsis.artifactName = "DocuSenseLM-Setup-${version}.${ext}"`

With this, `latest.yml` and the `.exe` asset always match exactly.

---

## CI/CD release flow (how updates get published)

The GitHub Actions workflow `.github/workflows/build.yml` does:

- **Build job (Windows)**:
  - Builds the app and creates artifacts in `release/`
  - Runs:
    - Backend API E2E (`pytest tests/test_lite_e2e.py -v`)
    - Electron startup smoke test (`tests/smoke/startup.spec.ts`)
  - Uploads artifacts (`release/*.*`) for the release job

- **Release job (Ubuntu finalizer)**:
  - Downloads build artifacts
  - Publishes a GitHub Release and uploads:
    - `**/*.exe`
    - `**/*.blockmap`
    - `**/*.yml` (includes `latest.yml`)

Important note:

- The build step uses `electron-builder --publish never`
  - We do **not** rely on electron-builder to publish the GitHub Release.
  - We publish via `softprops/action-gh-release` so release creation is centralized and more reliable.

---

## Debugging updates (what to check when something goes wrong)

### Logs

The Electron main process writes logs to:

- `userData/logs/main.log`

The exact `userData` path is logged on startup as:

- `User Data Path: ...`

### What to look for

- **Updater enabled?**
  - Look for missing `app-update.yml` (if missing, `canUseAutoUpdater()` disables updater).
- **State transitions**
  - `Auto-updater state: checking/available/downloading/downloaded/error`
- **Download progress**
  - Percent updates and taskbar progress logs
- **Shutdown / install**
  - “Update install requested…”
  - “Stopping Python backend…”
  - “Force-killing Python backend…”
  - “before-quit-for-update”

### Common failure modes (and how to identify them quickly)

- **`latest.yml` points to a non-existent installer**
  - Symptom: update download fails with 404 / missing asset
  - Fix: verify artifact naming is stable (`DocuSenseLM-Setup-${version}.exe`)
- **Installer loop “cannot be closed”**
  - Symptom: NSIS repeatedly prompts to close app
  - Fix: ensure Python child is being killed before quit-and-install
- **Auto-updater disabled**
  - Symptom: menu item disabled or no update checks
  - Fix: installed build must include `app-update.yml` in resources

---

## Test checklist (user-level)

### Basic updater UX

- Start the installed app:
  - No “You’re up to date” popup on startup
- Use **Help → Check for Updates…**:
  - If current: shows “No updates available”
  - If update exists:
    - shows “Update available → Download?”
    - download progress is visible in taskbar
    - shows “Update ready → Restart and install”

### Update install correctness

- Choose **Restart and install**
- Confirm:
  - App exits without hanging
  - Installer runs without “cannot be closed” loops
  - New version launches successfully after install

### CI guardrails

- `tests/test_lite_e2e.py` passes (ingestion flow)
- `tests/smoke/startup.spec.ts` passes (app launches; backend becomes healthy)


