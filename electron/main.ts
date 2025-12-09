import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';
import { spawn, ChildProcess } from 'child_process';
import fs from 'fs';
import { autoUpdater } from 'electron-updater';
import http from 'http';

const isDev = !app.isPackaged;

// Helper function to check if running from dist directory
function isDistBuild(): boolean {
  return __dirname.includes('dist') || __dirname.includes('win-unpacked');
}

// Enable remote debugging for MCP server
// Always enable for debugging
app.commandLine.appendSwitch('remote-debugging-port', '9222');

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;
const API_PORT = 14242;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    icon: path.join(__dirname, '../../build/icon.png'), // Linux/Windows
    show: false, // Don't show until ready
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  const distBuild = isDistBuild();
  if (isDev && !distBuild) {
    // True dev mode - Vite dev server is running
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
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
    if (mainWindow) {
      mainWindow.show();
    }
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
  
  // Poll health endpoint to verify backend started
  let healthCheckAttempts = 0;
  const maxHealthChecks = 30; // 30 seconds max
  const healthCheckInterval = setInterval(() => {
    healthCheckAttempts++;
    const req = http.get(`http://127.0.0.1:${API_PORT}/health`, (res) => {
      if (res.statusCode === 200) {
        console.log(`✓ Python backend health check passed after ${healthCheckAttempts} attempts`);
        clearInterval(healthCheckInterval);
        if (mainWindow) {
          mainWindow.webContents.send('python-ready');
        }
      }
      res.resume(); // Consume response
    });
    
    req.on('error', (error) => {
      if (healthCheckAttempts >= maxHealthChecks) {
        console.error(`✗ Python backend health check failed after ${maxHealthChecks} attempts`);
        console.error(`Last error: ${error.message}`);
        clearInterval(healthCheckInterval);
        if (mainWindow) {
          mainWindow.webContents.send('python-error', `Backend failed to start - health check timeout: ${error.message}`);
        }
      }
      // Otherwise continue polling
    });
    
    req.setTimeout(1000, () => {
      req.destroy();
    });
  }, 1000);
}

app.whenReady().then(() => {
  startPythonBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
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
