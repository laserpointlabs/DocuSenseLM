import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';
import { spawn, ChildProcess } from 'child_process';
import fs from 'fs';
import { autoUpdater } from 'electron-updater';

const isDev = !app.isPackaged;

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;
const API_PORT = 14242;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    show: false, // Don't show until ready
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
    // Check for updates
    autoUpdater.checkForUpdatesAndNotify();
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

  console.log(`Starting Python backend on port ${API_PORT}...`);
  
  const env = { 
      ...process.env, 
      PORT: API_PORT.toString(), 
      PYTHONUNBUFFERED: '1',
      USER_DATA_DIR: userDataPath 
  };

  if (isDev) {
      let pythonExecutable = process.platform === 'win32' ? 'python' : 'python3';
      // Try to use venv if available
      const venvPath = process.platform === 'win32' 
          ? path.join(__dirname, '../python/venv/Scripts/python.exe')
          : path.join(__dirname, '../python/venv/bin/python');
      
      if (fs.existsSync(venvPath)) {
          console.log(`Using venv python: ${venvPath}`);
          pythonExecutable = venvPath;
      }
      const scriptPath = path.join(__dirname, '../python/server.py');
      
      pythonProcess = spawn(pythonExecutable, [scriptPath], {
        env,
        stdio: 'pipe' 
      });
  } else {
      const executableName = process.platform === 'win32' ? 'server.exe' : 'server';
      // In packaged app, we expect the executable in python/ directory in resources
      const executablePath = path.join(process.resourcesPath, 'python', executableName);
      console.log(`Executable Path: ${executablePath}`);
      
      pythonProcess = spawn(executablePath, [], {
        env,
        stdio: 'pipe' 
      });
  }

  if (pythonProcess.stdout) {
      pythonProcess.stdout.on('data', (data) => {
        console.log(`[Python]: ${data}`);
      });
  }
  
  if (pythonProcess.stderr) {
      pythonProcess.stderr.on('data', (data) => {
        console.error(`[Python Err]: ${data}`);
      });
  }

  pythonProcess.on('close', (code) => {
    console.log(`Python process exited with code ${code}`);
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
