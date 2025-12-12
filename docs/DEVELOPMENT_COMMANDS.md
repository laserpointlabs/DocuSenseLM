# Development Commands Guide

## Quick Start

**To start development:**
```bash
npm run dev
```

This single command:
1. ✅ Builds the Electron main process (`build:electron`)
2. ✅ Starts the Vite dev server (frontend)
3. ✅ Launches Electron with hot reloading

**You do NOT need to run builds manually** - `npm run dev` handles everything automatically!

## Primary Development Commands

### `npm run dev`
**Full stack development** - The main command you'll use daily.

- Builds Electron TypeScript (`dist-electron/`)
- Starts Vite dev server on `http://localhost:5173`
- Launches Electron app with DevTools open
- Enables Hot Module Replacement (HMR) for instant updates
- Automatically rebuilds Electron when `electron/` files change

**Usage:** Just run this and start coding! Changes to React components update instantly.

---

### `npm run dev:web`
**Frontend-only development** - For React/UI work without Electron.

- Starts only the Vite dev server
- Access at `http://localhost:5173` in your browser
- Useful for quick UI testing without Electron overhead

**When to use:** When you're only working on React components and don't need Electron features.

---

### `npm run dev:electron`
**Electron-only** - Assumes Vite is already running elsewhere.

- Builds Electron TypeScript
- Waits for Vite server to be ready
- Launches Electron

**When to use:** If you've already started `dev:web` in another terminal and just want to launch Electron.

---

## Build Commands

### `npm run build:electron`
**Build Electron main process only**

- Compiles TypeScript in `electron/` to `dist-electron/`
- Fast rebuild (usually < 1 second)
- Automatically run by `npm run dev`, but useful if you need to rebuild manually

**When to use:** After modifying `electron/main.ts`, `electron/preload.ts`, or other Electron files.

---

### `npm run build:web`
**Build frontend for production**

- Compiles TypeScript
- Bundles React app with Vite
- Outputs to `web-dist/`

**When to use:** Testing production frontend build, or before packaging.

---

### `npm run build`
**Full production build**

- Builds everything (TypeScript, Vite, Electron)
- Packages with electron-builder
- Creates distributable installer

**When to use:** Creating a release build for distribution.

---

## Workflow Examples

### Typical Development Session

```bash
# 1. Start development (one command does it all!)
npm run dev

# 2. Make changes to React components
#    → Changes appear instantly via HMR

# 3. Make changes to Electron main process
#    → Stop dev server (Ctrl+C), restart `npm run dev`
#    → Or run `npm run build:electron` in another terminal
```

### Frontend-Only Workflow

```bash
# Terminal 1: Start frontend
npm run dev:web

# Terminal 2: (Optional) Launch Electron separately
npm run dev:electron
```

### Quick Electron Rebuild

```bash
# If you only changed electron/ files and dev server is running
npm run build:electron
# Electron will pick up changes on next reload
```

---

## Troubleshooting Commands

### Kill All Node/Electron Processes
```powershell
# Windows PowerShell
taskkill /F /IM node.exe /T
taskkill /F /IM electron.exe /T
```

### Clean and Restart
```bash
# Stop dev server (Ctrl+C), then:
npm run build:electron  # Rebuild Electron
npm run dev              # Start fresh
```

---

## Important Notes

### ✅ What `npm run dev` Handles Automatically

- Electron TypeScript compilation
- Vite dev server startup
- Electron window launch
- Hot Module Replacement
- Python backend spawning

### ⚠️ When You Need to Restart

**Restart `npm run dev` when you change:**
- `electron/main.ts` (main process code)
- `electron/preload.ts` (preload script)
- `electron/` directory files
- `package.json` scripts
- `vite.config.ts` (Vite config)

**No restart needed for:**
- `src/` React components (HMR handles it)
- `index.html` (Vite reloads automatically)
- CSS/styling changes (HMR handles it)

### 🔄 Hot Module Replacement (HMR)

When working in `src/`:
- Save a file → Changes appear instantly
- No page refresh needed
- State is preserved (usually)

---

## Command Reference Summary

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `npm run dev` | **Main dev command** | Daily development |
| `npm run dev:web` | Frontend only | UI-only work |
| `npm run dev:electron` | Electron only | If Vite already running |
| `npm run build:electron` | Rebuild Electron | After Electron changes |
| `npm run build:web` | Build frontend | Production frontend test |
| `npm run build` | Full production | Release builds |

---

## Tips

1. **Always use `npm run dev`** - It's the simplest way to develop
2. **Keep DevTools open** - Electron opens them automatically, check console for errors
3. **Watch the terminal** - Vite shows compilation errors and HMR status
4. **Python backend starts automatically** - No need to start it manually
5. **Port conflicts?** - Make sure nothing else is using port 5173 (Vite) or 14242 (Python)

---

## Date

Last Updated: December 12, 2025
