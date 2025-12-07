import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electron', {
  getApiPort: () => ipcRenderer.invoke('get-api-port'),
});

