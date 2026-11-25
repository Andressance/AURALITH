const { app, BrowserWindow, shell, Menu, nativeImage, ipcMain } = require("electron");
const net = require("net");
const path = require("path");
const fs = require("fs");

// The window only shows a web page, so the GPU is not needed. On some Windows machines the
// GPU process crashes at launch, which left the app with no visible window.
app.disableHardwareAcceleration();

// A second launch should focus the open window, not start a hidden copy.
if (!app.requestSingleInstanceLock()) {
  app.quit();
}
app.on("second-instance", () => {
  if (!mainWindow) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.focus();
});

const settingsPath = path.join(app.getPath("userData"), "auralith-desktop.json");
function loadSettings() {
  try {
    return JSON.parse(fs.readFileSync(settingsPath, "utf8"));
  } catch {
    return {};
  }
}
function saveSettings(settings) {
  fs.mkdirSync(path.dirname(settingsPath), { recursive: true });
  fs.writeFileSync(settingsPath, JSON.stringify(settings));
}
const settings = loadSettings();
let appUrl = process.env.AURALITH_URL || settings.url || "";
const applicationId = process.env.DISCORD_APPLICATION_ID || "";
let mainWindow;
let discordSocket;
let rpcNonce = 0;
let discordReady = false;
let lastPresenceKey = "";

function showSetupPage(failedUrl = "", errorDescription = "") {
  if (!mainWindow) return;
  mainWindow.loadFile(path.join(__dirname, "setup.html"));
  mainWindow.webContents.once("did-finish-load", () => {
    mainWindow.webContents.executeJavaScript(`(() => {
      document.getElementById("url").value = ${JSON.stringify(settings.url || process.env.AURALITH_URL || "")};
      const failed = ${JSON.stringify(failedUrl)};
      const detail = ${JSON.stringify(errorDescription)};
      if (failed) {
        document.getElementById("status").textContent = "No se pudo abrir " + failed + (detail ? ": " + detail : "");
        document.getElementById("status").className = "error";
      }
    })()`).catch(() => {});
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 760,
    minHeight: 520,
    title: "Auralith",
    icon: nativeImage.createFromPath(path.join(__dirname, "assets", "icon.png")),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, "preload.js")
    }
  });

  if (appUrl) {
    mainWindow.loadURL(appUrl).catch(() => showSetupPage());
  } else {
    showSetupPage();
  }
  mainWindow.webContents.on("did-fail-load", (_event, errorCode, errorDescription, failedUrl, isMainFrame) => {
    if (isMainFrame && errorCode !== -3) showSetupPage(failedUrl, errorDescription);
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { deny: true };
  });
  // If the renderer dies, reload instead of leaving an empty window behind.
  mainWindow.webContents.on("render-process-gone", (_event, details) => {
    if (details.reason !== "clean-exit" && mainWindow) mainWindow.reload();
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  Menu.setApplicationMenu(null);
  setInterval(syncPresence, 1500);
}

function rpcWrite(opcode, payload) {
  if (!discordSocket || discordSocket.destroyed) return;
  const body = Buffer.from(JSON.stringify(payload));
  const header = Buffer.alloc(8);
  header.writeInt32LE(opcode, 0);
  header.writeInt32LE(body.length, 4);
  discordSocket.write(Buffer.concat([header, body]));
}

function connectDiscord(pipeIndex = 0) {
  if (!applicationId) return;
  if (pipeIndex > 9) return;

  discordSocket = net.createConnection(`\\\\?\\pipe\\discord-ipc-${pipeIndex}`);
  discordSocket.once("connect", () => {
    rpcWrite(0, {
      v: 1,
      client_id: applicationId
    });
  });
  discordSocket.on("data", (chunk) => {
    let offset = 0;
    while (offset + 8 <= chunk.length) {
      const opcode = chunk.readInt32LE(offset);
      const length = chunk.readInt32LE(offset + 4);
      offset += 8;
      if (offset + length > chunk.length) break;
      const payload = JSON.parse(chunk.subarray(offset, offset + length).toString());
      offset += length;
      if (opcode === 1 && payload.cmd === "DISPATCH" && payload.evt === "READY") {
        discordReady = true;
      }
    }
  });
  discordSocket.on("error", () => {
    discordReady = false;
    discordSocket.destroy();
    discordSocket = null;
  });
  discordSocket.on("close", () => {
    if (app.isReady()) setTimeout(() => connectDiscord(pipeIndex + 1), 5000);
  });
}

async function syncPresence() {
  if (!applicationId || !discordReady || !mainWindow) return;
  const state = await mainWindow.webContents.executeJavaScript(`(() => {
    const audio = document.querySelector("audio");
    const title = document.querySelector(".now-playing strong")?.textContent?.trim();
    const artist = document.querySelector(".now-playing span")?.textContent?.trim();
    const playButton = document.querySelector(".player-toggle");
    if (!title || !artist) return null;
    const playing = playButton?.textContent?.includes("Ⅱ") || false;
    const current = Number.isFinite(audio?.currentTime) ? audio.currentTime : 0;
    const duration = Number.isFinite(audio?.duration) ? audio.duration : 0;
    return { title, artist, playing, current, duration };
  })()`).catch(() => null);

  if (!state) {
    if (lastPresenceKey) {
      lastPresenceKey = "";
      rpcWrite(1, { cmd: "SET_ACTIVITY", args: { pid: process.pid, activity: null }, nonce: String(++rpcNonce) });
    }
    return;
  }

  const now = Math.floor(Date.now() / 1000);
  const timestamps = state.playing && state.duration > state.current
    ? { start: now - Math.floor(state.current), end: now + Math.floor(state.duration - state.current) }
    : undefined;
  const key = `${state.title}|${state.artist}|${state.playing}|${Math.floor(state.current)}`;
  if (key === lastPresenceKey) return;
  lastPresenceKey = key;

  rpcWrite(1, {
    cmd: "SET_ACTIVITY",
    args: {
      pid: process.pid,
      activity: {
        type: 2,
        details: state.title,
        state: state.artist,
        timestamps,
        assets: {
          large_image: "auralith",
          large_text: "Auralith",
          small_image: state.playing ? "playing" : "paused",
          small_text: state.playing ? "Reproduciendo" : "En pausa"
        },
        buttons: [
          { label: "Abrir Auralith", url: appUrl }
        ]
      }
    },
    nonce: String(++rpcNonce)
  });
}

app.whenReady().then(() => {
  createWindow();
  connectDiscord();
});

ipcMain.handle("auralith:save-url", (_event, rawUrl) => {
  try {
    const parsed = new URL(rawUrl);
    if (!["http:", "https:"].includes(parsed.protocol)) throw new Error("Unsupported protocol");
    appUrl = parsed.toString().replace(/\/$/, "");
    saveSettings({ ...loadSettings(), url: appUrl });
    mainWindow.loadURL(appUrl);
    return { ok: true };
  } catch (cause) {
    return { ok: false, error: cause.message };
  }
});

app.on("window-all-closed", () => {
  app.quit();
});
