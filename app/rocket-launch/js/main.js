import {SETTINGS, state, timerBadge, codeInput, display, lampReady, lampArmed, lampSafe, resetFlightState, clearFlightTimers, resetMissileSystem, startCountdown, lockTemporarily, maybeUnlock, showHackerLoading, abortMissileFlight} from './missile.js';
import {beep, buzz} from './audio.js';
import {writeLog, setDisplay, setLamp, startSystemUpdates, fuelLevel, fuelValue, powerLevel, powerValue, guidanceLevel, guidanceValue, commsLevel, commsValue, logEl} from './ui.js';
import {clearTarget, updateWorldMap} from './map.js';
import {cancelDisarm} from './missile.js';
import {stopAllAudio} from './audio.js';
import {updateSystemStatus} from './ui.js';

const qs = (sel) => document.querySelector(sel);
export const armBtn = qs("#armBtn");
export const disarmBtn = qs("#disarmBtn");
export const resetBtn = qs("#resetBtn");
export const fsBtn = qs("#fsBtn");
export const clearLog = qs("#clearLog");
export const exportLog = qs("#exportLog");
export const cfgStart = qs("#cfgStart");
export const cfgDisarm = qs("#cfgDisarm");
export const cfgTimer = qs("#cfgTimer");
export const cfgFlight = qs("#cfgFlight");
export const cfgAllowDisarm = qs("#cfgAllowDisarm");
export const cfgAllowFlight = qs("#cfgAllowFlight");
export const cfgLockout = qs("#cfgLockout");
export const applyCfg = qs("#applyCfg");
export const hiddenAdminBtn = qs("#hiddenAdminBtn");
export const logoutAdmin = qs("#logoutAdmin");
export const adminAccess = qs("#adminAccess");

export function normalizeSettings() {
  SETTINGS.launchCode = SETTINGS.launchCode || "8421";
  SETTINGS.disarmCode = SETTINGS.disarmCode || "0000";
  SETTINGS.timerSeconds = Math.max(1, parseInt(SETTINGS.timerSeconds, 10) || 120);
  SETTINGS.flightDurationSeconds = Math.max(1, parseInt(SETTINGS.flightDurationSeconds, 10) || 45);
  SETTINGS.lockAfterWrongAttempts = SETTINGS.lockAfterWrongAttempts !== false;
  SETTINGS.lockThreshold = Math.max(1, parseInt(SETTINGS.lockThreshold, 10) || 3);
  SETTINGS.lockDurationSec = Math.max(1, parseInt(SETTINGS.lockDurationSec, 10) || 30);
  SETTINGS.allowDisarmDuringCountdown = SETTINGS.allowDisarmDuringCountdown !== false;
  SETTINGS.allowDisarmDuringFlight = SETTINGS.allowDisarmDuringFlight !== false;
}

export async function loadConfigFromFile() {
  try {
    const response = await fetch('/api/config');
    if (!response.ok) {
      throw new Error('Config file not found');
    }
    const configData = await response.json();
    if (configData.startCode) SETTINGS.launchCode = configData.startCode;
    if (configData.disarmCode) SETTINGS.disarmCode = configData.disarmCode;
    if (configData.timerSeconds) SETTINGS.timerSeconds = configData.timerSeconds;
    if (configData.flightTimeSeconds) SETTINGS.flightDurationSeconds = configData.flightTimeSeconds;
    if (configData.allowDisarmDuringCountdown !== undefined) SETTINGS.allowDisarmDuringCountdown = configData.allowDisarmDuringCountdown;
    if (configData.allowDisarmDuringFlight !== undefined) SETTINGS.allowDisarmDuringFlight = configData.allowDisarmDuringFlight;
    if (configData.lockoutAfterFailedAttempts !== undefined) SETTINGS.lockAfterWrongAttempts = configData.lockoutAfterFailedAttempts;
    normalizeSettings();
    writeLog("Config geladen");
    return true;
  } catch (error) {
    writeLog("Einstellungen konnten nicht geladen werden. Bitte die Seite neu laden.");
    return false;
  }
}

export async function saveConfigToServer(configData) {
  try {
    const response = await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(configData)
    });
    if (!response.ok) {
      throw new Error('Speichern fehlgeschlagen. Einstellungen wurden nicht übernommen.');
    }
    writeLog("Config gespeichert");
    beep(880, 120);
    return true;
  } catch (error) {
    writeLog("Fehler: " + error.message);
    buzz();
    return false;
  }
}

export function loadUrlParams() {
  try {
    const p = new URLSearchParams(location.search);
    if (p.get("code")) SETTINGS.launchCode = p.get("code");
    if (p.get("disarm")) SETTINGS.disarmCode = p.get("disarm");
    if (p.get("timer")) SETTINGS.timerSeconds = Math.max(1, parseInt(p.get("timer"), 10) || SETTINGS.timerSeconds);
  } catch {}
}

async function initializeApp() {
  normalizeSettings();
  state.ready = await loadConfigFromFile();
  cfgStart.value = SETTINGS.launchCode;
  cfgDisarm.value = SETTINGS.disarmCode;
  cfgTimer.value = SETTINGS.timerSeconds;
  cfgFlight.value = SETTINGS.flightDurationSeconds;
  cfgAllowDisarm.checked = SETTINGS.allowDisarmDuringCountdown;
  cfgAllowFlight.checked = SETTINGS.allowDisarmDuringFlight;
  cfgLockout.checked = SETTINGS.lockAfterWrongAttempts;
}

function resetAll() {
  if (["counting", "launched"].includes(state.phase) && !confirm("Laufende Runde wirklich abbrechen und zurücksetzen?")) return;
  cancelDisarm();
  stopAllAudio();
  if (state.tickHandle) {
    clearInterval(state.tickHandle);
    state.tickHandle = null;
  }
  clearFlightTimers();
  state.phase = "idle";
  state.secondsLeft = SETTINGS.timerSeconds;
  state.wrongAttempts = 0;
  state.lockUntil = 0;
  state.lastCountdownSpoken = null;
  state.systemStatus = {
    fuel: 100,
    guidance: "OFFLINE",
    comms: "OFFLINE",
    power: 0,
    target: "STANDBY",
    weather: "CLEAR",
    satellite: "CONNECTED",
    radar: "ACTIVE",
  };
  state.mapData = {
    targetId: null,
    destroyedTargetId: null,
    targetLabel: "",
    targetCoords: {lat: 0, lon: 0},
    range: 0,
    eta: 0,
    hasTarget: false,
  };
  state.targetDestroyed = false;
  state.multiTargetStrike = false;
  state.flightDurationSec = SETTINGS.flightDurationSeconds;
  state.flightTimeout = null;
  state.flightTicker = null;
  state.flightStartMs = 0;
  state.flightRemaining = 0;

  setDisplay("--:--");
  timerBadge.style.display = "none";
  resetFlightState();
  setLamp(lampReady, true);
  setLamp(lampArmed, false);
  setLamp(lampSafe, false);
  fuelLevel.style.width = "100%";
  fuelValue.textContent = "100%";
  powerLevel.style.width = "0%";
  powerValue.textContent = "0%";
  guidanceLevel.style.width = "0%";
  guidanceValue.textContent = "OFFLINE";
  commsLevel.style.width = "0%";
  commsValue.textContent = "OFFLINE";
  codeInput.value = "";
  clearTarget();
  resetMissileSystem();
  updateSystemStatus();
  writeLog("Reset");
}

function confirmStart() {
  if (!state.ready || !["idle", "disarmed", "complete"].includes(state.phase)) return;
  maybeUnlock();
  if (Date.now() < state.lockUntil) {
    writeLog("Blockiert");
    buzz();
    return;
  }
  const entered = codeInput.value.trim();
  if (!entered) {
    buzz();
    return;
  }
  if (entered === SETTINGS.launchCode) {
    state.secondsLeft = SETTINGS.timerSeconds;
    codeInput.value = "";
    state.wrongAttempts = 0;
    state.phase = "armed";
    writeLog("ARMED");
    setLamp(lampReady, false);
    setLamp(lampArmed, true);
    setLamp(lampSafe, false);
    startCountdown();
  } else {
    state.wrongAttempts++;
    writeLog("Falsch (#" + state.wrongAttempts + ")");
    buzz();
    lockTemporarily();
    display.style.animation = "shake .15s 3";
    setTimeout(() => (display.style.animation = ""), 600);
  }
}

function confirmDisarm() {
  maybeUnlock();
  if (!state.ready || Date.now() < state.lockUntil || state.disarmHandle) return;
  if (!(state.phase === "counting" || state.phase === "armed" || state.phase === "launched")) {
    writeLog("DISARM unmöglich");
    buzz();
    return;
  }
  if (!SETTINGS.allowDisarmDuringCountdown && state.phase === "counting") {
    writeLog("DISARM deaktiviert");
    buzz();
    return;
  }
  if (!SETTINGS.allowDisarmDuringFlight && state.phase === "launched") {
    writeLog("Flug-DISARM deaktiviert");
    buzz();
    return;
  }
  const entered = codeInput.value.trim();
  if (!entered) {
    buzz();
    return;
  }
  if (entered === SETTINGS.disarmCode) {
    codeInput.value = "";
    if (state.phase === "launched") {
      const success = abortMissileFlight();
      if (success) {
        state.phase = "disarmed";
        state.wrongAttempts = 0;
        setLamp(lampReady, true);
        setLamp(lampArmed, false);
        setLamp(lampSafe, false);
        setDisplay("SAFE");
      }
    } else {
      showHackerLoading();
    }
  } else {
    state.wrongAttempts++;
    writeLog("Falsch (#" + state.wrongAttempts + ")");
    buzz();
    lockTemporarily();
    display.style.animation = "shake .15s 3";
    setTimeout(() => (display.style.animation = ""), 600);
  }
}

function authenticateAdmin() {
  if (!adminAccess) return;
  if (state.adminAuthenticated) {
    adminAccess.style.display = "block";
    writeLog("Admin aktiv");
    return;
  }
  const enteredCode = prompt("Spielleitung: Start- oder Entschärfungscode eingeben", "");
  if (enteredCode === null) return;
  const normalized = enteredCode.trim();
  const validCodes = new Set([SETTINGS.launchCode, SETTINGS.disarmCode]);
  if (normalized && validCodes.has(normalized)) {
    state.adminAuthenticated = true;
    adminAccess.style.display = "block";
    adminAccess.scrollIntoView({behavior: "smooth", block: "nearest"});
    writeLog("Admin gewährt");
    beep(880, 120);
  } else {
    writeLog("Admin verweigert");
    buzz();
  }
}

function logoutAdminAccess() {
  if (!adminAccess) return;
  if (!state.adminAuthenticated) return;
  state.adminAuthenticated = false;
  adminAccess.style.display = "none";
  writeLog("Admin beendet");
  beep(640, 100);
}

function setupEventListeners() {
  document.querySelectorAll("[data-key]").forEach((b) => {
    b.addEventListener("click", () => {
      if (codeInput.disabled) return;
      const k = b.getAttribute("data-key");
      if (k === "back") {
        codeInput.value = codeInput.value.slice(0, -1);
        return;
      }
      if (k === "clear") {
        codeInput.value = "";
        return;
      }
      if (codeInput.value.length < 12) codeInput.value += k;
    });
  });

  armBtn.addEventListener("click", () => { confirmStart(); refreshControls(); reportActivity(); });
  disarmBtn.addEventListener("click", () => { confirmDisarm(); refreshControls(); });
  resetBtn.addEventListener("click", () => { resetAll(); refreshControls(); });

  applyCfg.addEventListener("click", async () => {
    if (["counting", "launched"].includes(state.phase) || saving) return;
    const next = {
      startCode: cfgStart.value.trim(), disarmCode: cfgDisarm.value.trim(),
      timerSeconds: Number(cfgTimer.value), flightTimeSeconds: Number(cfgFlight.value),
      allowDisarmDuringCountdown: cfgAllowDisarm.checked,
      allowDisarmDuringFlight: cfgAllowFlight.checked,
      lockoutAfterFailedAttempts: cfgLockout.checked,
    };
    const feedback = qs("#configFeedback");
    if (!/^[0-9]{4,12}$/.test(next.startCode) || !/^[0-9]{4,12}$/.test(next.disarmCode)
        || next.startCode === next.disarmCode) {
      feedback.textContent = "Zwei unterschiedliche Codes mit jeweils 4 bis 12 Ziffern eingeben.";
      return;
    }
    if ([next.timerSeconds, next.flightTimeSeconds].some(value => !Number.isInteger(value) || value < 1 || value > 3600)) {
      feedback.textContent = "Zeiten müssen ganze Sekunden zwischen 1 und 3600 sein.";
      return;
    }
    saving = true;
    refreshControls();
    feedback.textContent = "Wird gespeichert …";
    if (await saveConfigToServer(next)) {
      Object.assign(SETTINGS, {launchCode: next.startCode, disarmCode: next.disarmCode,
        timerSeconds: next.timerSeconds, flightDurationSeconds: next.flightTimeSeconds,
        allowDisarmDuringCountdown: next.allowDisarmDuringCountdown,
        allowDisarmDuringFlight: next.allowDisarmDuringFlight,
        lockAfterWrongAttempts: next.lockoutAfterFailedAttempts});
      state.flightDurationSec = SETTINGS.flightDurationSeconds;
      feedback.textContent = "Gespeichert. Gilt ab der nächsten Runde.";
    } else {
      feedback.textContent = "Speichern fehlgeschlagen. Die bisherigen Einstellungen bleiben aktiv.";
    }
    saving = false;
    refreshControls();
  });

  fsBtn.addEventListener("click", async () => {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen().catch(() => {});
    } else {
      await document.exitFullscreen().catch(() => {});
    }
  });

  clearLog.addEventListener("click", () => {
    logEl.textContent = "";
    writeLog("Log geleert");
  });

  exportLog.addEventListener("click", () => {
    const logContent = logEl.textContent;
    const blob = new Blob([logContent], {type: "text/plain"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `log-${new Date().toISOString().slice(0, 19).replace(/:/g, "-")}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    writeLog("Log exportiert");
  });

  hiddenAdminBtn.addEventListener("click", authenticateAdmin);
  logoutAdmin.addEventListener("click", logoutAdminAccess);
  codeInput.addEventListener("input", () => { codeInput.value = codeInput.value.replace(/\D/g, "").slice(0, 12); });
  codeInput.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (["counting", "launched"].includes(state.phase)) confirmDisarm();
      else confirmStart();
      refreshControls();
      reportActivity();
    }
  });
  window.addEventListener("beforeunload", event => {
    if (["counting", "launched"].includes(state.phase)) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
}

let saving = false;
let ownsConsole = true;
function refreshControls() {
  maybeUnlock();
  const active = ["counting", "launched", "armed"].includes(state.phase);
  const locked = Date.now() < state.lockUntil;
  const blocked = !state.ready || !ownsConsole || saving;
  armBtn.disabled = blocked || locked || active;
  disarmBtn.disabled = blocked || locked || !!state.disarmHandle || !(
    (state.phase === "counting" && SETTINGS.allowDisarmDuringCountdown) ||
    (state.phase === "launched" && SETTINGS.allowDisarmDuringFlight));
  codeInput.disabled = blocked || locked || !!state.disarmHandle;
  for (const button of document.querySelectorAll("[data-key]")) button.disabled = codeInput.disabled;
  for (const field of [cfgStart, cfgDisarm, cfgTimer, cfgFlight, cfgAllowDisarm, cfgAllowFlight, cfgLockout, applyCfg]) {
    field.disabled = blocked || active;
  }
  resetBtn.disabled = blocked;
  hiddenAdminBtn.disabled = !state.ready || !ownsConsole;
  const phases = {idle: "Bereit für die nächste Runde", counting: "Countdown läuft", armed: "Startet …",
    launched: "Rakete im Flug", disarmed: "Runde beendet: erfolgreich entschärft", complete: "Runde beendet: Ziel getroffen"};
  let message = phases[state.phase] || "Bereit";
  if (state.disarmDeadline) message += ` · Entschärfung: ${Math.max(0, Math.ceil((state.disarmDeadline - performance.now()) / 1000))} s`;
  if (locked) message += ` · Codeeingabe gesperrt: ${Math.ceil((state.lockUntil - Date.now()) / 1000)} s`;
  if (!state.ready) message = "Einstellungen konnten nicht geladen werden. Bitte Seite neu laden.";
  if (!ownsConsole) message = "Das Spiel ist bereits in einem anderen Fenster geöffnet. Bitte dort weiterspielen und dieses Fenster schließen.";
  qs("#gameStatus").textContent = message;
}

function reportActivity() {
  if (ownsConsole && ["counting", "launched"].includes(state.phase)) {
    fetch("/api/activity", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({active: true})}).catch(() => {});
  }
}

function initializeUIState() {
  resetFlightState();
  setDisplay("--:--");
  setLamp(lampReady, true);
  setLamp(lampArmed, false);
  setLamp(lampSafe, false);
  fuelLevel.style.width = "100%";
  fuelValue.textContent = "100%";
  powerLevel.style.width = "0%";
  powerValue.textContent = "0%";
  guidanceLevel.style.width = "0%";
  guidanceValue.textContent = "OFFLINE";
  commsLevel.style.width = "0%";
  commsValue.textContent = "OFFLINE";
  writeLog("Bereit");
  updateWorldMap();
}

(async () => {
  if (navigator.locks) {
    ownsConsole = false;
    navigator.locks.request("airsoft-rocket-console", {ifAvailable: true}, async lock => {
      ownsConsole = !!lock;
      if (lock) await new Promise(() => {});
    });
  }
  await initializeApp();
  setupEventListeners();
  initializeUIState();
  startSystemUpdates();
  refreshControls();
  setInterval(refreshControls, 200);
  setInterval(reportActivity, 10000);
})();
