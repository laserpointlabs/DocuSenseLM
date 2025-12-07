import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';
import { spawn, ChildProcess } from 'child_process';
import fs from 'fs';

const isDev = !app.isPackaged;

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;
const API_PORT = 14242;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
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
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startPythonBackend() {
  let pythonExecutable = process.platform === 'win32' ? 'python' : 'python3';
  
  if (isDev) {
      // Try to use venv if available
      const venvPath = process.platform === 'win32' 
          ? path.join(__dirname, '../python/venv/Scripts/python.exe')
          : path.join(__dirname, '../python/venv/bin/python');
      
      if (fs.existsSync(venvPath)) {
          console.log(`Using venv python: ${venvPath}`);
          pythonExecutable = venvPath;
      }
  }

  const scriptPath = isDev
    ? path.join(__dirname, '../python/server.py')
    : path.join(process.resourcesPath, 'python/server.py');

  console.log(`Starting Python backend on port ${API_PORT}...`);
  
  pythonProcess = spawn(pythonExecutable, [scriptPath], {
    env: { ...process.env, PORT: API_PORT.toString(), PYTHONUNBUFFERED: '1' },
    stdio: 'pipe' 
  });

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
