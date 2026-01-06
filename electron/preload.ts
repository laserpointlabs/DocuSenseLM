import { contextBridge, ipcRenderer } from 'electron';

// NOTE:
// In dev, React StrictMode can mount components twice, causing duplicate registrations
// of IPC listeners if we attach them directly per component.
// To prevent log spam and duplicate event handling, we attach each IPC listener ONCE
// and fan out to a set of registered callbacks.

type Unsubscribe = () => void;

const startupStatusCallbacks = new Set<(status: string) => void>();
const pythonReadyCallbacks = new Set<() => void>();
const pythonErrorCallbacks = new Set<(error: string) => void>();

// Cache last-known state so late subscribers (or dev StrictMode mount ordering)
// don't miss one-shot events like `python-ready`.
let lastStartupStatus: string | null = null;
let pythonReadySeen = false;
let lastPythonError: string | null = null;

let startupStatusAttached = false;
let pythonReadyAttached = false;
let pythonErrorAttached = false;

function ensureStartupStatusListener() {
  if (startupStatusAttached) return;
  startupStatusAttached = true;
  ipcRenderer.on('startup-status', (_evt, status: string) => {
    lastStartupStatus = status;
    for (const cb of startupStatusCallbacks) {
      try {
        cb(status);
      } catch (e) {
        console.error('startup-status callback failed:', e);
      }
    }
  });
}

function ensurePythonReadyListener() {
  if (pythonReadyAttached) return;
  pythonReadyAttached = true;
  ipcRenderer.on('python-ready', () => {
    pythonReadySeen = true;
    for (const cb of pythonReadyCallbacks) {
      try {
        cb();
      } catch (e) {
        console.error('python-ready callback failed:', e);
      }
    }
  });
}

function ensurePythonErrorListener() {
  if (pythonErrorAttached) return;
  pythonErrorAttached = true;
  ipcRenderer.on('python-error', (_evt, error: string) => {
    lastPythonError = error;
    for (const cb of pythonErrorCallbacks) {
      try {
        cb(error);
      } catch (e) {
        console.error('python-error callback failed:', e);
      }
    }
  });
}

// Expose electron API to renderer using proper contextBridge pattern
contextBridge.exposeInMainWorld('electronAPI', {
  getApiPort: () => ipcRenderer.invoke('get-api-port'),
  getUserDataPath: () => ipcRenderer.invoke('get-user-data-path'),
  openUserDataFolder: () => ipcRenderer.invoke('open-user-data-folder'),
  downloadBackup: () => ipcRenderer.invoke('download-backup'),

  // Subscribe to startup status messages.
  // Returns an unsubscribe function.
  handleStartupStatus: (callback: (status: string) => void): Unsubscribe => {
    ensureStartupStatusListener();
    startupStatusCallbacks.add(callback);
    // Replay last-known status to late subscribers (async to avoid surprises).
    if (lastStartupStatus !== null) {
      const status = lastStartupStatus;
      queueMicrotask(() => {
        try {
          callback(status);
        } catch (e) {
          console.error('startup-status callback failed (replay):', e);
        }
      });
    }
    return () => startupStatusCallbacks.delete(callback);
  },

  // Subscribe to python ready messages.
  // Returns an unsubscribe function.
  handlePythonReady: (callback: () => void): Unsubscribe => {
    ensurePythonReadyListener();
    pythonReadyCallbacks.add(callback);
    // If the backend is already marked ready, call immediately.
    if (pythonReadySeen) {
      queueMicrotask(() => {
        try {
          callback();
        } catch (e) {
          console.error('python-ready callback failed (replay):', e);
        }
      });
    }
    return () => pythonReadyCallbacks.delete(callback);
  },

  // Subscribe to python error messages.
  // Returns an unsubscribe function.
  handlePythonError: (callback: (error: string) => void): Unsubscribe => {
    ensurePythonErrorListener();
    pythonErrorCallbacks.add(callback);
    // Replay last error so UI can surface it even if it subscribed late.
    if (lastPythonError !== null) {
      const error = lastPythonError;
      queueMicrotask(() => {
        try {
          callback(error);
        } catch (e) {
          console.error('python-error callback failed (replay):', e);
        }
      });
    }
    return () => pythonErrorCallbacks.delete(callback);
  },
});
