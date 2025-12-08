# DocuSenseLM: Build, Install, Test, Publish

Goal: produce a clean Windows build, install it, test it, and ship versioned artifacts to GitHub.

## Prerequisites (one-time)
- Windows Developer Mode ON (or run build shell as Administrator) to avoid winCodeSign symlink errors.
- Node/npm installed.
- Environment variable `OPENAI_API_KEY` set to the key only (no `OPENAI_API_KEY=` prefix).
- User config at `C:\Users\engin\AppData\Roaming\DocuSenseLM\config.yaml` has `api.openai_api_key: ""`.

## Clean start before each build
- Kill any DocuSenseLM/electron processes.
- Delete signer cache: `Remove-Item "$env:LOCALAPPDATA\electron-builder\Cache\winCodeSign" -Recurse -Force`
- Ensure `release` folder is removed if present.

## Build (unpacked + installer)
Local (for quick test, no admin):
```
npm run build:windows
```
Outputs in `release\`:
- Unpacked app: `release\win-unpacked\DocuSenseLM.exe`
- Resources include `resources\python\`, `resources\web-dist\`, `resources\config.default.yaml`, `resources\prompts.default.yaml`
- Installer: `release\DocuSenseLM Setup.exe` (built reliably in CI; may fail locally if symlinks blocked)

CI (recommended for installer):
- Workflow: `.github/workflows/build-windows.yml`
- Runs on Windows runner, builds nsis + dir, uploads artifacts:
  - Installer: `release/*.exe` or `*.msi`
  - Unpacked: `release/win-unpacked/**`

## Local install & test
1) If present, run `release\DocuSenseLM Setup.exe`; otherwise run `release\win-unpacked\DocuSenseLM.exe`.
2) In app: Settings → Reset to defaults (should succeed).
3) Upload a document and run a chat query that references it.
4) Confirm the app uses your env API key (config stays blank).

## Version bump
- Edit `package.json` version (e.g., 1.0.14).
- Rebuild: `npm run build:windows`
- Verify app “About” shows the new version.
- Tag and push: `git tag v1.0.14 && git push && git push --tags`

## GitHub artifacts (recommended)
- Add a workflow to build on push/tag:
  - Install deps
  - `npm run build:windows`
  - Upload artifacts: `release\DocuSenseLM Setup.exe` (if present) and `release\win-unpacked` (zip).
  - On tag, create a release and attach artifacts.

## Quick checklist (per build)
- [ ] Dev Mode on (or elevated shell) and signer cache cleared
- [ ] `npm run build:windows` completes; `release\win-unpacked` contains python + defaults
- [ ] App runs from `release\win-unpacked\DocuSenseLM.exe`
- [ ] Reset defaults works; upload + chat works
- [ ] Version matches `package.json`
- [ ] (Optional) Installer built and runs
- [ ] (Optional) Artifacts uploaded in GitHub workflow


