import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';
import { spawn, ChildProcess } from 'child_process';
import fs from 'fs';
import { autoUpdater } from 'electron-updater';

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
      let pythonBasePath: string;
      if (distBuild) {
          // Running from dist\win-unpacked - Python is in resources folder
          pythonBasePath = path.join(process.resourcesPath, 'python');
      } else {
          // Packaged app - use resourcesPath
          pythonBasePath = path.join(process.resourcesPath, 'python');
      }
      
      const venvPath = process.platform === 'win32' 
          ? path.join(pythonBasePath, 'venv', 'Scripts', 'python.exe')
          : path.join(pythonBasePath, 'venv', 'bin', 'python');
      
      scriptPath = path.join(pythonBasePath, 'server.py');
      
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
  
  // Spawn the Python process
  pythonProcess = spawn(pythonExecutable, [scriptPath], {
    env,
    stdio: 'pipe',
    detached: false
  });
  
  pythonProcess.on('error', (error) => {
      console.error(`Failed to start Python process: ${error.message}`);
      console.error(`Error details:`, error);
      if (mainWindow) {
          mainWindow.webContents.send('python-error', `Failed to start Python backend: ${error.message}`);
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
      });
  }

  pythonProcess.on('close', (code, signal) => {
    console.log(`Python process exited with code ${code}, signal ${signal}`);
    if (code !== 0 && code !== null) {
        console.error(`Python backend crashed with exit code ${code}`);
        if (mainWindow) {
            mainWindow.webContents.send('python-error', `Python backend crashed with exit code ${code}`);
        }
    }
  });
  
  pythonProcess.on('exit', (code, signal) => {
    console.log(`Python process exit event - code: ${code}, signal: ${signal}`);
  });
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
