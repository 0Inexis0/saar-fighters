import {state} from './missile.js';

const qs = (sel) => document.querySelector(sel);

export const logEl = qs("#log");
export const display = qs("#display");
export const pillTime = qs("#pillTime");
export const systemTime = qs("#systemTime");
export const securityLevel = qs("#securityLevel");
export const fuelLevel = qs("#fuelLevel");
export const fuelValue = qs("#fuelValue");
export const guidanceLevel = qs("#guidanceLevel");
export const guidanceValue = qs("#guidanceValue");
export const commsLevel = qs("#commsLevel");
export const commsValue = qs("#commsValue");
export const powerLevel = qs("#powerLevel");
export const powerValue = qs("#powerValue");
export const targetStatus = qs("#targetStatus");
export const weatherStatus = qs("#weatherStatus");
export const satelliteStatus = qs("#satelliteStatus");
export const radarStatus = qs("#radarStatus");
export const impactEstimate = qs("#impactEstimate");

export function fmt(t) {
  const m = Math.floor(t / 60).toString().padStart(2, "0");
  const s = Math.floor(t % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

export function formatCoordinate(value, axis) {
  const abs = Math.abs(value).toFixed(1);
  const suffix = axis === "lat" ? (value >= 0 ? "N" : "S") : value >= 0 ? "E" : "W";
  return `${abs}°${suffix}`;
}

export function formatEta(seconds) {
  const totalSeconds = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
  const remainingSeconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainingSeconds}`;
}

export function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const toRad = (deg) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c);
}

export function setLamp(el, on) {
  el.style.opacity = on ? 1 : 0.35;
}

export function setDisplay(txt) {
  display.textContent = txt;
  pillTime.textContent = txt;
}

export function writeLog(line) {
  const ts = new Date().toLocaleTimeString();
  logEl.textContent += `[${ts}] ${line}\n`;
  logEl.scrollTop = logEl.scrollHeight;
}

export function updateSystemTime() {
  const now = new Date();
  const timeStr = now.toLocaleTimeString();
  systemTime.textContent = timeStr;
}

export function updateSystemStatus() {
  if (state.phase !== "counting" && state.phase !== "armed") {
    fuelLevel.style.width = state.systemStatus.fuel + "%";
    fuelValue.textContent = Math.round(state.systemStatus.fuel) + "%";
    powerLevel.style.width = state.systemStatus.power + "%";
    powerValue.textContent = Math.round(state.systemStatus.power) + "%";
  }
  targetStatus.textContent = state.systemStatus.target;
  weatherStatus.textContent = state.systemStatus.weather;
  satelliteStatus.textContent = state.systemStatus.satellite;
  radarStatus.textContent = state.systemStatus.radar;
  if (state.phase !== "counting") {
    guidanceValue.textContent = state.systemStatus.guidance;
    commsValue.textContent = state.systemStatus.comms;
  }
}

export function updateSecurityLevel() {
  const levels = ["CLASSIFIED", "TOP SECRET", "EYES ONLY", "RESTRICTED"];
  const randomLevel = levels[Math.floor(Math.random() * levels.length)];
  securityLevel.textContent = randomLevel;
}

export function simulateSystemActivity() {
  if (Math.random() < 0.1) {
    const statuses = ["ONLINE", "STANDBY", "ACTIVE", "READY"];
    state.systemStatus.guidance = statuses[Math.floor(Math.random() * statuses.length)];
  }
  if (Math.random() < 0.05) {
    const commsStatuses = ["ACTIVE", "STANDBY", "SCANNING", "CONNECTED"];
    state.systemStatus.comms = commsStatuses[Math.floor(Math.random() * commsStatuses.length)];
  }
  if (Math.random() < 0.03) {
    const weatherStatuses = ["CLEAR", "OVERCAST", "STORM", "FOG"];
    state.systemStatus.weather = weatherStatuses[Math.floor(Math.random() * weatherStatuses.length)];
  }
}

export function setImpactEstimate(text) {
  if (!impactEstimate) return;
  if (text) {
    impactEstimate.textContent = text;
    impactEstimate.classList.add("active");
  } else {
    impactEstimate.textContent = "";
    impactEstimate.classList.remove("active");
  }
}

export function startSystemUpdates() {
  setInterval(updateSystemTime, 1000);
  state.systemUpdateInterval = setInterval(() => {
    updateSystemStatus();
    simulateSystemActivity();
  }, 2000);
  setInterval(updateSecurityLevel, 10000);
}
