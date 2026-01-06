import { app, BrowserWindow, ipcMain, shell, dialog, Menu } from 'electron';
import path from 'path';
import { spawn, ChildProcess } from 'child_process';
import fs from 'fs';
import { autoUpdater } from 'electron-updater';
import http from 'http';

const isDev = !app.isPackaged;

// Helper function to check if running from dist directory
// In dev mode, __dirname is dist-electron, but we want to treat that as dev
// Only treat as dist build if it's in a release/win-unpacked directory or packaged
function isDistBuild(): boolean {
  // If packaged, it's definitely a dist build
  if (app.isPackaged) return true;
  // dist-electron is dev mode, not a dist build
  if (__dirname.includes('dist-electron')) return false;
  // Check if we're in a release directory (built app)
  return __dirname.includes('win-unpacked') || __dirname.includes('release');
}

// Enable remote debugging for MCP server
// Always enable for debugging
app.commandLine.appendSwitch('remote-debugging-port', '9222');

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;
const API_PORT = 14242;

// --- Auto-update UX (packaged builds only) ---
let updateCheckInProgress = false;
let updateDownloaded = false;

function canUseAutoUpdater(): boolean {
  if (!app.isPackaged) return false;
  // electron-updater expects app-update.yml in packaged apps; win-unpacked builds often don't have it.
  // Avoid confusing errors and startup delays by disabling auto-updater when it's missing.
  try {
    const updateCfg = path.join(process.resourcesPath, 'app-update.yml');
    return fs.existsSync(updateCfg);
  } catch {
    return false;
  }
}

function migrateLegacyUserDataIfNeeded(userDataPath: string) {
  // Older builds may have used a different userData folder name (e.g. "DocuSenseLM").
  // If the new path is empty, copy over config.yaml so users keep their API key.
  try {
    const roaming = process.env.APPDATA;
    if (!roaming) return;

    const legacyPath = path.join(roaming, 'DocuSenseLM');
    const currentPath = userDataPath;

    const legacyCfg = path.join(legacyPath, 'config.yaml');
    const currentCfg = path.join(currentPath, 'config.yaml');

    if (!fs.existsSync(legacyCfg)) return;
    if (fs.existsSync(currentCfg)) return;

    fs.mkdirSync(currentPath, { recursive: true });
    fs.copyFileSync(legacyCfg, currentCfg);
    console.log(`[migrate] Copied legacy config.yaml from ${legacyPath} -> ${currentPath}`);
  } catch (e) {
    console.warn(`[migrate] Skipped legacy userData migration: ${e}`);
  }
}

function setupAutoUpdater() {
  if (!canUseAutoUpdater()) return;

  // Give users control: check on startup, but don't download until they confirm.
  autoUpdater.autoDownload = false;

  autoUpdater.on('error', (err) => {
    updateCheckInProgress = false;
    const msg = (err && (err as any).message) ? (err as any).message : String(err);
    console.error(`Auto-updater error: ${msg}`);
    // Avoid noisy dialogs for transient connectivity issues; user can manually re-check.
  });

  autoUpdater.on('checking-for-update', () => {
    updateCheckInProgress = true;
  });

  autoUpdater.on('update-not-available', async () => {
    updateCheckInProgress = false;
    updateDownloaded = false;
    await dialog.showMessageBox({
      type: 'info',
      title: 'No updates',
      message: 'You are already running the latest version.',
    });
  });

  autoUpdater.on('update-available', async () => {
    updateCheckInProgress = false;
    const result = await dialog.showMessageBox({
      type: 'info',
      title: 'Update available',
      message: 'A new version is available. Do you want to download it now?',
      buttons: ['Download', 'Later'],
      defaultId: 0,
      cancelId: 1,
    });
    if (result.response === 0) {
      try {
        updateCheckInProgress = true;
        await autoUpdater.downloadUpdate();
      } finally {
        updateCheckInProgress = false;
      }
    }
  });

  autoUpdater.on('update-downloaded', async () => {
    updateDownloaded = true;
    updateCheckInProgress = false;
    const result = await dialog.showMessageBox({
      type: 'info',
      title: 'Update ready',
      message: 'The update has been downloaded. Restart to install it now?',
      buttons: ['Restart and install', 'Later'],
      defaultId: 0,
      cancelId: 1,
    });
    if (result.response === 0) {
      autoUpdater.quitAndInstall();
    }
  });
}

function buildAppMenu() {
  const template: Electron.MenuItemConstructorOptions[] = [
    ...(process.platform === 'darwin'
      ? [{
          label: app.name,
          submenu: [
            { role: 'about' },
            { type: 'separator' },
            { role: 'quit' },
          ],
        } as Electron.MenuItemConstructorOptions]
      : []),
    {
      label: 'File',
      submenu: [
        { role: 'quit' },
      ],
    },
    {
      // Give users a way to open DevTools and reload in packaged builds where F12/Ctrl+Shift+I may be unavailable.
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { type: 'separator' },
        { role: 'toggleDevTools' },
      ],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'Check for Updates…',
          enabled: canUseAutoUpdater(),
          click: async () => {
            if (!canUseAutoUpdater()) return;
            if (updateCheckInProgress) {
              await dialog.showMessageBox({
                type: 'info',
                title: 'Checking…',
                message: 'An update check is already in progress.',
              });
              return;
            }
            if (updateDownloaded) {
              const result = await dialog.showMessageBox({
                type: 'info',
                title: 'Update ready',
                message: 'An update is already downloaded. Restart to install?',
                buttons: ['Restart and install', 'Later'],
                defaultId: 0,
                cancelId: 1,
              });
              if (result.response === 0) autoUpdater.quitAndInstall();
              return;
            }
            try {
              updateCheckInProgress = true;
              await autoUpdater.checkForUpdates();
            } finally {
              updateCheckInProgress = false;
            }
          },
        },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

function createWindow() {
  const distBuild = isDistBuild();
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    icon: path.join(__dirname, '../../build/icon.png'), // Linux/Windows
    show: false, // Don't show until ready
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      // Keep Electron security features enabled (even in dev) to avoid noisy security warnings
      // and to keep behavior closer to production.
      webSecurity: true,
    },
  });

  if (isDev && !distBuild) {
    // True dev mode - Vite dev server is running
    console.log('Dev mode: Loading from http://localhost:5173');
    mainWindow.loadURL('http://localhost:5173');
    // Don't auto-open DevTools by default; it can emit noisy protocol warnings on startup.
    // Set ELECTRON_OPEN_DEVTOOLS=1 to open automatically.
    if (process.env.ELECTRON_OPEN_DEVTOOLS === '1') {
      mainWindow.webContents.openDevTools({ mode: 'detach' });
    }
    // Show window immediately in dev mode
    mainWindow.show();
  } else {
    // Production or dist build - load from file system
    const htmlPath = distBuild
      ? path.join(process.resourcesPath, 'web-dist', 'index.html')
      : path.join(__dirname, '../dist/index.html');
    console.log(`Loading HTML from: ${htmlPath}`);
    mainWindow.loadFile(htmlPath);
    // Auto-updates are only meaningful for packaged apps installed from an installer (e.g. NSIS).
    // Check quietly on startup; user controls download/install via dialogs.
    if (canUseAutoUpdater()) {
      setTimeout(() => {
        autoUpdater.checkForUpdates().catch(() => {});
      }, 2000);
    }
  }

  mainWindow.once('ready-to-show', () => {
    console.log('Window ready-to-show event fired');
    if (mainWindow) {
      mainWindow.show();
    }
  });

  // Log any navigation/load errors
  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    console.error(`Failed to load: ${validatedURL}`);
    console.error(`Error: ${errorCode} - ${errorDescription}`);
  });

  // Log console messages from renderer (skip in dev to reduce noise; Vite already shows console output)
  if (!isDev || distBuild) {
    mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
      const levelStr = ['log', 'warning', 'error', 'debug', 'info'][level] || 'unknown';
      console.log(`[Renderer ${levelStr}]: ${message} (${sourceId}:${line})`);
    });
  }

  // Log all console output (only in production, skip in dev to avoid conflicts with Vite HMR)
  if (!isDev || distBuild) {
    mainWindow.webContents.on('did-finish-load', () => {
      mainWindow?.webContents.executeJavaScript(`
        if (typeof window.__electronConsoleOverridden === 'undefined') {
          window.__electronConsoleOverridden = true;
          const originalLog = console.log;
          const originalError = console.error;
          const originalWarn = console.warn;
          console.log = (...args) => { originalLog(...args); window.electron?.log('log', args.join(' ')); };
          console.error = (...args) => { originalError(...args); window.electron?.log('error', args.join(' ')); };
          console.warn = (...args) => { originalWarn(...args); window.electron?.log('warn', args.join(' ')); };
        }
      `).catch(() => {});
    });
  }

  // Send startup messages only after renderer finished loading (IPC ready)
  mainWindow.webContents.once('did-finish-load', () => {
    console.log('Window did-finish-load event fired - sending startup messages');
    if (!mainWindow) return;
    const send = (msg: string, delay: number) => {
      setTimeout(() => {
        if (mainWindow) {
          mainWindow.webContents.send('startup-status', msg);
        }
      }, delay);
    };
    send('Starting application...', 200);
    send('Initializing Python backend...', 1200);
    send('Loading configuration...', 2200);
    send('Connecting to services...', 3800);
    send('Starting API server...', 5200);
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ... rest of file


function startPythonBackend() {
  // Get OS-specific user data path
  // Windows: %APPDATA%/nda-tool-lite
  // Linux: ~/.config/nda-tool-lite
  // Mac: ~/Library/Application Support/nda-tool-lite
  const userDataPath = app.getPath('userData');
  migrateLegacyUserDataIfNeeded(userDataPath);
  console.log(`User Data Path: ${userDataPath}`);
  console.log(`isDev: ${isDev}`);
  console.log(`process.resourcesPath: ${process.resourcesPath}`);
  console.log(`__dirname: ${__dirname}`);
  console.log(`isDistBuild(): ${isDistBuild()}`);

  console.log(`Starting Python backend on port ${API_PORT}...`);

  const env = {
      ...process.env,
      PORT: API_PORT.toString(),
      PYTHONUNBUFFERED: '1',
      // Reduce noisy dependency DeprecationWarnings that look like "startup errors".
      // Developers can override by explicitly setting PYTHONWARNINGS in their shell.
      PYTHONWARNINGS: process.env.PYTHONWARNINGS ?? 'ignore::DeprecationWarning,ignore::PendingDeprecationWarning',
      USER_DATA_DIR: userDataPath
  };

  // Determine Python executable and script path
  let pythonExecutable: string;
  let scriptPath: string;

  const distBuild = isDistBuild();
  console.log(`DEBUG: isDev=${isDev}, distBuild=${distBuild}, condition=${isDev && !distBuild}`);
  console.log(`DEBUG: Current working directory: ${process.cwd()}`);
  console.log(`DEBUG: Resources path: ${process.resourcesPath}`);
  if (isDev && !distBuild) {
      // Development mode - use project Python
      pythonExecutable = process.platform === 'win32' ? 'python' : 'python3';
      const venvPath = process.platform === 'win32'
          ? path.join(__dirname, '../python/venv/Scripts/python.exe')
          : path.join(__dirname, '../python/venv/bin/python');

      if (fs.existsSync(venvPath)) {
          console.log(`Using venv python: ${venvPath}`);
          pythonExecutable = venvPath;
      }
      scriptPath = path.join(__dirname, '../python/server.py');
      console.log(`Dev mode - Script: ${scriptPath}`);
  } else {
      // Production or dist build mode - use packaged Python source
      // In packaged apps, extraResources are always in process.resourcesPath
      const pythonBasePath = path.join(process.resourcesPath, 'python');
      scriptPath = path.join(pythonBasePath, 'server.py');

      // Check for Python embeddable distribution first (CI builds - relocatable)
      const embedPython = process.platform === 'win32'
          ? path.join(pythonBasePath, 'python_embed', 'python.exe')
          : path.join(pythonBasePath, 'python_embed', 'bin', 'python3');

      if (fs.existsSync(embedPython)) {
          console.log(`Production mode - Using Python embeddable distribution`);
          console.log(`Embed Python: ${embedPython}`);
          console.log(`Script: ${scriptPath}`);
          pythonExecutable = embedPython;
      } else {
          // Fall back to venv-based approach (local builds)
          const venvPath = process.platform === 'win32'
              ? path.join(pythonBasePath, 'venv', 'Scripts', 'python.exe')
              : path.join(pythonBasePath, 'venv', 'bin', 'python');

          console.log(`Production/Dist mode - Python base: ${pythonBasePath}`);
          console.log(`Production/Dist mode - Python venv: ${venvPath}`);
          console.log(`Production/Dist mode - Script: ${scriptPath}`);
          console.log(`Python venv exists: ${fs.existsSync(venvPath)}`);
          console.log(`Script exists: ${fs.existsSync(scriptPath)}`);

          if (!fs.existsSync(scriptPath)) {
              console.error(`ERROR: Python script not found at ${scriptPath}`);
              if (mainWindow) {
                  mainWindow.webContents.send('python-error', `Python script not found at ${scriptPath}`);
              }
              return;
          }

          // Try venv first, fall back to system Python if venv doesn't exist
          if (fs.existsSync(venvPath)) {
              console.log(`Using Python venv: ${venvPath}`);
              pythonExecutable = venvPath;
          } else {
              console.log(`Python venv not found, using system Python`);
              pythonExecutable = process.platform === 'win32' ? 'python' : 'python3';
          }
      }
  }

  // Verify paths before spawning
  console.log(`About to spawn Python:`);
  console.log(`  Executable: ${pythonExecutable}`);
  console.log(`  Script: ${scriptPath || '(standalone exe, no script)'}`);
  console.log(`  Executable exists: ${fs.existsSync(pythonExecutable)}`);
  if (scriptPath) {
      console.log(`  Script exists: ${fs.existsSync(scriptPath)}`);
  }
  console.log(`  Working directory: ${process.cwd()}`);
  console.log(`  Resources path: ${process.resourcesPath}`);

  if (!fs.existsSync(pythonExecutable)) {
      const errorMsg = `Python executable not found at ${pythonExecutable}`;
      console.error(`ERROR: ${errorMsg}`);
      if (mainWindow) {
          mainWindow.webContents.send('python-error', errorMsg);
      }
      return;
  }

  if (scriptPath && !fs.existsSync(scriptPath)) {
      const errorMsg = `Python script not found at ${scriptPath}`;
      console.error(`ERROR: ${errorMsg}`);
      if (mainWindow) {
          mainWindow.webContents.send('python-error', errorMsg);
      }
      return;
  }

  // Spawn the Python process
  console.log(`Spawning Python process...`);

  const args = scriptPath ? [scriptPath] : [];
  const workingDir = scriptPath ? path.dirname(scriptPath) : path.dirname(pythonExecutable);

  pythonProcess = spawn(pythonExecutable, args, {
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false,
    cwd: workingDir
  });

  pythonProcess.on('error', (error) => {
      const errorMsg = `Failed to start Python process: ${error.message}`;
      console.error(`ERROR: ${errorMsg}`);
      console.error(`Error details:`, error);
      console.error(`Python executable: ${pythonExecutable}`);
      console.error(`Script path: ${scriptPath}`);
      if (mainWindow) {
          mainWindow.webContents.send('python-error', errorMsg);
      }
  });

  if (pythonProcess.stdout) {
      pythonProcess.stdout.on('data', (data) => {
        const output = data.toString();
        console.log(`[Python Stdout]: ${output}`);
      });
  }

  if (pythonProcess.stderr) {
      pythonProcess.stderr.on('data', (data) => {
        const output = data.toString();
        // Many libraries (uvicorn, chromadb, etc.) write non-error logs to stderr.
        // Only treat as an actual error if it looks like one, otherwise log normally.
        const looksLikeError =
          /\bTraceback\b/.test(output) ||
          /\bERROR\b/.test(output) ||
          /\bException\b/.test(output);
        if (looksLikeError) {
          console.error(`[Python]: ${output}`);
        } else {
          console.log(`[Python]: ${output}`);
        }
        // Also send stderr to renderer for debugging
        if (mainWindow) {
            mainWindow.webContents.send('python-stderr', output);
        }
      });
  }

  pythonProcess.on('close', (code, signal) => {
    console.log(`Python process exited with code ${code}, signal ${signal}`);
    if (code !== 0 && code !== null) {
        const errorMsg = `Python backend crashed with exit code ${code}`;
        console.error(`ERROR: ${errorMsg}`);
        if (mainWindow) {
            mainWindow.webContents.send('python-error', errorMsg);
        }
    }
  });

  pythonProcess.on('exit', (code, signal) => {
    console.log(`Python process exit event - code: ${code}, signal: ${signal}`);
  });

  // Log process info
  console.log(`Python process spawned with PID: ${pythonProcess.pid}`);

  // Poll health endpoint to verify backend started with exponential backoff
  let healthCheckAttempts = 0;
  const maxHealthChecks = 60; // Increased to 60 attempts max (up to ~4 minutes with backoff)
  let currentDelay = 1000; // Start with 1 second
  const maxDelay = 10000; // Cap delay at 10 seconds
  let healthCheckStopped = false;
  let healthCheckTimeout: NodeJS.Timeout | null = null;

  // Send initial status update - but wait for window to be ready
  console.log('Python backend starting, will send status updates when window is ready...');

  const performHealthCheck = () => {
    if (healthCheckStopped) return;
    healthCheckAttempts++;
    // Avoid scary-looking "error spam" during normal startup.
    // Log only occasionally; the renderer has its own loading UI.
    if (healthCheckAttempts === 1 || healthCheckAttempts % 5 === 0) {
      console.log(`Health check attempt ${healthCheckAttempts}/${maxHealthChecks} (delay: ${Math.round(currentDelay)}ms)`);
    }

    const req = http.get(`http://127.0.0.1:${API_PORT}/health`, (res) => {
      if (res.statusCode === 200) {
        console.log(`✓ Python backend health check passed after ${healthCheckAttempts} attempts`);

        // Send final status and ready message
        if (mainWindow) {
          mainWindow.webContents.send('startup-status', 'Backend ready!');
          mainWindow.webContents.send('python-ready');
        }
        healthCheckStopped = true;
        if (healthCheckTimeout) {
          clearTimeout(healthCheckTimeout);
          healthCheckTimeout = null;
        }
        return; // Success - stop checking
      }
      res.resume(); // Consume response
      scheduleNextCheck();
    });

    req.on('error', (error) => {
      // Normal while the backend is still booting (e.g. ECONNREFUSED).
      if (healthCheckAttempts === 1 || healthCheckAttempts % 5 === 0) {
        console.log(`Backend not ready yet (attempt ${healthCheckAttempts}/${maxHealthChecks}): ${error.message}`);
      }

      if (healthCheckAttempts >= maxHealthChecks) {
        console.error(`✗ Python backend health check failed after ${maxHealthChecks} attempts`);
        console.error(`Last error: ${error.message}`);
        if (mainWindow) {
          mainWindow.webContents.send('startup-status', 'Backend startup failed');
          mainWindow.webContents.send('python-error', `Backend failed to start after ${maxHealthChecks} attempts: ${error.message}`);
        }
        healthCheckStopped = true;
        return; // Stop checking
      }

      scheduleNextCheck();
    });

    req.setTimeout(5000, () => { // Increased timeout to 5 seconds per request
      req.destroy();
      scheduleNextCheck();
    });
  };

  const scheduleNextCheck = () => {
    if (healthCheckStopped) return;
    // Exponential backoff with jitter
    currentDelay = Math.min(currentDelay * 1.5 + Math.random() * 1000, maxDelay);
    if (healthCheckTimeout) clearTimeout(healthCheckTimeout);
    healthCheckTimeout = setTimeout(performHealthCheck, currentDelay);
  };

  // Start the first health check
  performHealthCheck();
}

app.whenReady().then(() => {
  console.log('App is ready, creating window first...');
  setupAutoUpdater();
  buildAppMenu();
  createWindow();
  console.log('Starting backend...');
  startPythonBackend();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
}).catch((error) => {
  console.error('Failed to initialize app:', error);
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});

ipcMain.handle('get-api-port', () => API_PORT);
ipcMain.handle('get-user-data-path', () => app.getPath('userData'));
ipcMain.handle('open-user-data-folder', async () => {
  const p = app.getPath('userData');
  // openPath returns an empty string on success, otherwise an error message
  const result = await shell.openPath(p);
  return { success: result === "", path: p, error: result || null };
});

// Download backup without opening a new window. This uses Electron's download manager,
// so we can reliably know when the user finished saving the file.
ipcMain.handle('download-backup', async () => {
  if (!mainWindow) {
    return { success: false, error: 'Main window not ready' };
  }

  const url = `http://localhost:${API_PORT}/backup`;

  try {
    const wc = mainWindow.webContents;
    const ses = wc.session;

    return await new Promise<{ success: boolean; filename?: string; error?: string }>((resolve) => {
      const onWillDownload = (_event: Electron.Event, item: Electron.DownloadItem) => {
        // Only handle the backup download we just initiated.
        if (item.getURL() !== url) return;

        const filename = item.getFilename();

        console.log('[Backup Download] will-download triggered for:', filename);

        // Set a temporary path immediately to prevent Electron's default save dialog
        const tempPath = path.join(app.getPath('temp'), filename);
        console.log('[Backup Download] Setting temp path:', tempPath);
        item.setSavePath(tempPath);

        // Track both the download completion and user's save choice
        let downloadComplete = false;
        let downloadState: 'completed' | 'cancelled' | 'interrupted' = 'cancelled';
        let userChosenPath: string | null = null;
        let dialogComplete = false;

        const tryFinalize = () => {
          // Only finalize when BOTH download and dialog are done
          if (!downloadComplete || !dialogComplete) return;

          ses.removeListener('will-download', onWillDownload);

          if (downloadState === 'completed' && userChosenPath) {
            // Move file from temp to user's chosen location
            console.log('[Backup Download] Finalizing: moving from', tempPath, 'to', userChosenPath);
            try {
              if (fs.existsSync(userChosenPath)) {
                console.log('[Backup Download] Removing existing file at destination');
                fs.unlinkSync(userChosenPath); // Remove existing file
              }
              if (!fs.existsSync(tempPath)) {
                throw new Error('Temp file does not exist');
              }
              fs.renameSync(tempPath, userChosenPath);
              console.log('[Backup Download] File saved successfully');
              resolve({ success: true, filename });
            } catch (e: any) {
              console.error('[Backup Download] Error saving file:', e);
              resolve({ success: false, error: `Failed to save file: ${e.message}` });
              try { fs.unlinkSync(tempPath); } catch {}
            }
          } else {
            // Download failed or user canceled
            try {
              if (fs.existsSync(tempPath)) {
                fs.unlinkSync(tempPath);
              }
            } catch (e) {
              console.error('Failed to clean up temp file:', e);
            }
            resolve({ success: false, error: downloadState === 'completed' ? 'User canceled' : `Download ${downloadState}` });
          }
        };

        // Show save dialog
        dialog.showSaveDialog(mainWindow!, {
          title: 'Save Backup',
          defaultPath: path.join(app.getPath('downloads'), filename),
          filters: [{ name: 'ZIP', extensions: ['zip'] }],
        }).then(({ canceled, filePath }) => {
          if (!canceled && filePath) {
            userChosenPath = filePath;
          }
          dialogComplete = true;
          tryFinalize();
        }).catch((e) => {
          console.error('Save dialog error:', e);
          dialogComplete = true;
          tryFinalize();
        });

        // Track download completion
        item.once('done', (_e, state) => {
          console.log('[Backup Download] Download done, state:', state);
          console.log('[Backup Download] Temp file exists:', fs.existsSync(tempPath));
          if (fs.existsSync(tempPath)) {
            console.log('[Backup Download] Temp file size:', fs.statSync(tempPath).size);
          }
          downloadComplete = true;
          downloadState = state as 'completed' | 'cancelled' | 'interrupted';
          tryFinalize();
        });
      };

      ses.on('will-download', onWillDownload);
      wc.downloadURL(url);
    });
  } catch (e: any) {
    return { success: false, error: e?.message || String(e) };
  }
});
