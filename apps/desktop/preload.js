const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("auralithDesktop", {
  saveUrl: (url) => ipcRenderer.invoke("auralith:save-url", url)
});
