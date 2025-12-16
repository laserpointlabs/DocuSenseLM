import { app, BrowserWindow, ipcMain, shell } from 'electron';
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
      // Disable web security in dev mode to avoid CSP issues with Vite
      webSecurity: !(isDev && !distBuild),
    },
  });

  if (isDev && !distBuild) {
    // True dev mode - Vite dev server is running
    console.log('Dev mode: Loading from http://localhost:5173');
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
    // Show window immediately in dev mode
    mainWindow.show();
  } else {
    // Production or dist build - load from file system
    const htmlPath = distBuild
      ? path.join(process.resourcesPath, 'web-dist', 'index.html')
      : path.join(__dirname, '../dist/index.html');
    console.log(`Loading HTML from: ${htmlPath}`);
    mainWindow.loadFile(htmlPath);
    // Check for updates only if packaged
    if (app.isPackaged) {
      autoUpdater.checkForUpdatesAndNotify();
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

  // Log console messages from renderer
  mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    const levelStr = ['log', 'warning', 'error', 'debug', 'info'][level] || 'unknown';
    console.log(`[Renderer ${levelStr}]: ${message} (${sourceId}:${line})`);
  });

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
        console.error(`[Python Stderr]: ${output}`);
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

  // Send initial status update - but wait for window to be ready
  console.log('Python backend starting, will send status updates when window is ready...');

  const performHealthCheck = () => {
    healthCheckAttempts++;
    console.log(`Health check attempt ${healthCheckAttempts}/${maxHealthChecks} (delay: ${currentDelay}ms)`);

    const req = http.get(`http://127.0.0.1:${API_PORT}/health`, (res) => {
      if (res.statusCode === 200) {
        console.log(`✓ Python backend health check passed after ${healthCheckAttempts} attempts`);

        // Send final status and ready message
        if (mainWindow) {
          mainWindow.webContents.send('startup-status', 'Backend ready!');
          mainWindow.webContents.send('python-ready');
        }
        return; // Success - stop checking
      }
      res.resume(); // Consume response
      scheduleNextCheck();
    });

    req.on('error', (error) => {
      console.log(`Health check attempt ${healthCheckAttempts} failed: ${error.message}`);

      if (healthCheckAttempts >= maxHealthChecks) {
        console.error(`✗ Python backend health check failed after ${maxHealthChecks} attempts`);
        console.error(`Last error: ${error.message}`);
        if (mainWindow) {
          mainWindow.webContents.send('startup-status', 'Backend startup failed');
          mainWindow.webContents.send('python-error', `Backend failed to start after ${maxHealthChecks} attempts: ${error.message}`);
        }
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
    // Exponential backoff with jitter
    currentDelay = Math.min(currentDelay * 1.5 + Math.random() * 1000, maxDelay);
    console.log(`Scheduling next health check in ${Math.round(currentDelay)}ms`);
    setTimeout(performHealthCheck, currentDelay);
  };

  // Start the first health check
  performHealthCheck();
}

app.whenReady().then(() => {
  console.log('App is ready, creating window first...');
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
