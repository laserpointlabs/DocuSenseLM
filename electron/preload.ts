import { contextBridge, ipcRenderer } from 'electron';

console.log('Preload script executing...');

// Expose electron API to renderer using proper contextBridge pattern
contextBridge.exposeInMainWorld('electronAPI', {
  getApiPort: () => ipcRenderer.invoke('get-api-port'),

  // Handle startup status messages
  handleStartupStatus: (callback: (status: string) => void) => {
    console.log('Setting up startup-status listener in preload');
    ipcRenderer.on('startup-status', (_, status) => {
      console.log('Preload received startup-status:', status);
      callback(status);
    });
  },

  // Handle python ready messages
  handlePythonReady: (callback: () => void) => {
    console.log('Setting up python-ready listener in preload');
    ipcRenderer.on('python-ready', () => {
      console.log('Preload received python-ready');
      callback();
    });
  },

  // Handle python error messages
  handlePythonError: (callback: (error: string) => void) => {
    console.log('Setting up python-error listener in preload');
    ipcRenderer.on('python-error', (_, error) => {
      console.log('Preload received python-error:', error);
      callback(error);
    });
  }
});

console.log('Preload script completed, electronAPI exposed to renderer');

