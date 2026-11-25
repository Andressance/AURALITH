export const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export function text(value, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

export function assetUrl(path) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

export function titleInitial(title) {
  const value = text(title).trim();
  return value ? value.slice(0, 1).toUpperCase() : "♫";
}

export function hideBrokenImage(event) {
  event.currentTarget.style.display = "none";
}

export function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return "0:00";
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`;
}
