import {beep, speakCountdown, stopCountdownAudio, playExplosion} from './audio.js';
import {writeLog, setDisplay, setLamp, setImpactEstimate, fmt, fuelLevel, fuelValue, guidanceLevel, guidanceValue, commsLevel, commsValue, powerLevel, powerValue} from './ui.js';
import {setRandomTarget, updateWorldMap, strategicTargets} from './map.js';

const qs = (sel) => document.querySelector(sel);
export const timerBadge = qs("#timerBadge");
export const codeInput = qs("#codeInput");
export const display = qs("#display");
export const loadingBar = qs("#loadingBar");
export const targetDestruction = qs("#targetDestruction");
export const lampReady = qs("#lampReady");
export const lampArmed = qs("#lampArmed");
export const lampSafe = qs("#lampSafe");
export const targetMarker = qs("#targetMarker");
export const targetCoords = qs("#targetCoords");
export const targetRange = qs("#targetRange");
export const targetETA = qs("#targetETA");

export const SETTINGS = {
  launchCode: "8421",
  disarmCode: "0000",
  timerSeconds: 120,
  flightDurationSeconds: 45,
  lockAfterWrongAttempts: true,
  lockThreshold: 3,
  lockDurationSec: 30,
  allowDisarmDuringCountdown: true,
  allowDisarmDuringFlight: true,
};

export const baseSite = {
  lat: 39.7392,
  lon: -104.9903,
};

export const MAP_DIMENSIONS = {width: 1000, height: 520};

export const state = {
  phase: "idle",
  secondsLeft: SETTINGS.timerSeconds,
  countdownStartSeconds: SETTINGS.timerSeconds,
  wrongAttempts: 0,
  lockUntil: 0,
  tickHandle: null,
  countdownDeadline: 0,
  disarmDeadline: 0,
  disarmHandle: null,
  ready: false,
  audioCtx: null,
  adminAuthenticated: false,
  lastCountdownSpoken: null,
  systemStatus: {
    fuel: 100,
    guidance: "OFFLINE",
    comms: "OFFLINE",
    power: 0,
    target: "STANDBY",
    weather: "CLEAR",
    satellite: "CONNECTED",
    radar: "ACTIVE",
  },
  systemUpdateInterval: null,
  mapData: {
    targetId: null,
    destroyedTargetId: null,
    targetLabel: "",
    targetCoords: {lat: 0, lon: 0},
    range: 0,
    eta: 0,
    hasTarget: false,
  },
  targetDestroyed: false,
  multiTargetStrike: false,
  flightDurationSec: SETTINGS.flightDurationSeconds,
  flightTimeout: null,
  flightTicker: null,
  flightStartMs: 0,
  flightRemaining: 0,
};

export function clearFlightTimers() {
  if (state.flightTimeout) {
    clearTimeout(state.flightTimeout);
    state.flightTimeout = null;
  }
  if (state.flightTicker) {
    clearInterval(state.flightTicker);
    state.flightTicker = null;
  }
}

export function resetFlightState() {
  clearFlightTimers();
  state.flightRemaining = 0;
  state.flightStartMs = 0;
  setImpactEstimate("");
}

export function startLaunchSequence() {
  writeLog("Start-Sequenz");
}

export function stopLaunchSequence() {
  writeLog("Sequenz abgebrochen");
}

export function startMissileFlight() {
  writeLog("Gestartet");
  clearFlightTimers();
  state.flightStartMs = performance.now();
  state.flightRemaining = state.flightDurationSec;
  const initialFuel = state.systemStatus.fuel;

  setImpactEstimate(`IMPACT EST ${fmt(Math.ceil(state.flightDurationSec))}`);
  updateWorldMap();

  state.flightTicker = setInterval(() => {
    const elapsed = (performance.now() - state.flightStartMs) / 1000;
    const remaining = Math.max(0, state.flightDurationSec - elapsed);
    state.flightRemaining = remaining;
    const displaySeconds = Math.max(0, Math.ceil(remaining));

    const fuelPercentage = remaining / state.flightDurationSec;
    state.systemStatus.fuel = Math.max(0, initialFuel * fuelPercentage);
    fuelLevel.style.width = state.systemStatus.fuel + "%";
    fuelValue.textContent = Math.round(state.systemStatus.fuel) + "%";

    if (remaining > 0) {
      setImpactEstimate(`IMPACT T-${fmt(displaySeconds)}`);
    } else {
      setImpactEstimate("IMPACT");
      if (state.flightTicker) {
        clearInterval(state.flightTicker);
        state.flightTicker = null;
      }
    }
  }, 200);

  state.flightTimeout = setTimeout(() => {
    state.flightTimeout = null;
    triggerTargetDestruction();
  }, state.flightDurationSec * 1000);
}

export function triggerTargetDestruction() {
  if (state.targetDestroyed) return;
  clearFlightTimers();
  state.phase = "complete";
  stopCountdownAudio();
  setImpactEstimate("IMPACT CONFIRMED");
  state.targetDestroyed = true;
  state.mapData.destroyedTargetId = state.multiTargetStrike ? "all" : state.mapData.targetId;
  targetDestruction.style.display = "none";
  targetMarker.style.display = "none";
  updateWorldMap();
  state.systemStatus.target = state.multiTargetStrike ? "ALL IMPACTED" : "DESTROYED";
  state.systemStatus.guidance = "MISSION COMPLETE";
  state.systemStatus.radar = state.multiTargetStrike ? "MULTI IMPACT CONFIRMED" : "TARGET ELIMINATED";
  if (state.multiTargetStrike) {
    targetCoords.textContent = "GLOBAL STRIKE";
    targetRange.textContent = `${strategicTargets.length} Ziele`;
    targetETA.textContent = "00:00";
  } else {
    targetCoords.textContent = "DESTROYED";
    targetRange.textContent = "0 km";
    targetETA.textContent = "00:00";
  }
  writeLog(state.multiTargetStrike ? "Global Strike" : "Zerstört");
  playExplosion();
  beep(800, 200);
  setTimeout(() => beep(600, 200), 250);
}

export function abortMissileFlight() {
  if (state.phase !== "launched") return false;
  clearFlightTimers();
  stopCountdownAudio();
  writeLog("Rakete in Luft abgefangen");
  setImpactEstimate("FLUG ABGEBROCHEN");
  state.systemStatus.target = "LUFTABFANG";
  state.systemStatus.guidance = "SELBSTZERSTÖRUNG";
  state.systemStatus.radar = "SIGNAL VERLOREN";
  targetMarker.style.display = "none";
  targetDestruction.style.display = "none";
  beep(600, 150);
  setTimeout(() => beep(500, 150), 200);
  setTimeout(() => beep(400, 300), 400);
  updateWorldMap();
  return true;
}

export function resetMissileSystem() {
  state.targetDestroyed = false;
  state.mapData.destroyedTargetId = null;
  state.multiTargetStrike = false;
  resetFlightState();
  targetDestruction.style.display = "none";
  updateWorldMap();
}

export function maybeUnlock() {
  if (state.lockUntil && Date.now() >= state.lockUntil) {
    state.lockUntil = 0;
    state.wrongAttempts = 0;
    writeLog("Sperre aufgehoben");
  }
}

export function lockTemporarily() {
  if (!SETTINGS.lockAfterWrongAttempts) return;
  if (state.wrongAttempts < SETTINGS.lockThreshold) return;
  state.lockUntil = Date.now() + SETTINGS.lockDurationSec * 1000;
  writeLog("Codeeingabe für 30 Sekunden gesperrt. Die Runde läuft weiter.");
}

export function startCountdown() {
  if (state.tickHandle || state.phase === "launched") return;
  cancelDisarm();
  state.phase = "counting";
  state.flightDurationSec = SETTINGS.flightDurationSeconds;
  state.countdownStartSeconds = state.secondsLeft;
  state.countdownDeadline = performance.now() + state.secondsLeft * 1000;
  resetFlightState();
  timerBadge.style.display = "inline-flex";
  setDisplay(fmt(state.secondsLeft));
  writeLog("Countdown start");
  beep(900, 150);
  setTimeout(() => beep(1100, 150), 170);
  state.lastCountdownSpoken = null;
  stopCountdownAudio();
  // if (typeof window !== "undefined" && "speechSynthesis" in window) {
  //   window.speechSynthesis.cancel();
  // }
  state.systemStatus.target = "ACQUIRED";
  state.systemStatus.guidance = "OFFLINE";
  state.systemStatus.comms = "OFFLINE";
  state.systemStatus.power = 0;
  state.systemStatus.fuel = 100;
  state.systemStatus.radar = "TRACKING";
  guidanceValue.textContent = state.systemStatus.guidance;
  commsValue.textContent = state.systemStatus.comms;
  powerLevel.style.width = "0%";
  powerValue.textContent = "0%";
  guidanceLevel.style.width = "0%";
  commsLevel.style.width = "0%";
  fuelLevel.style.width = "100%";
  fuelValue.textContent = "100%";
  const needsNewTarget = state.targetDestroyed || !state.mapData.hasTarget;
  targetDestruction.style.display = "none";
  state.targetDestroyed = false;
  state.mapData.destroyedTargetId = null;
  if (needsNewTarget) {
    setRandomTarget();
  } else {
    updateWorldMap();
  }
  state.tickHandle = setInterval(tick, 100);
}

export function stopCountdown(reason) {
  if (state.tickHandle) {
    clearInterval(state.tickHandle);
    state.tickHandle = null;
  }
  timerBadge.style.display = "none";
  resetFlightState();
  writeLog("Countdown stopp (" + reason + ")");
  state.lastCountdownSpoken = null;
  stopCountdownAudio();
  // if (typeof window !== "undefined" && "speechSynthesis" in window) {
  //   window.speechSynthesis.cancel();
  // }
}

function tick() {
  maybeUnlock();
  if (state.phase !== "counting") return;
  const now = performance.now();
  if (state.disarmDeadline && now >= state.disarmDeadline && state.disarmDeadline < state.countdownDeadline) {
    completeDisarm();
    return;
  }
  const remaining = Math.max(0, Math.ceil((state.countdownDeadline - now) / 1000));
  if (remaining === state.secondsLeft) return;
  state.secondsLeft = remaining;
  beep(620, 60);
  setDisplay(fmt(Math.max(0, state.secondsLeft)));

  const elapsed = state.countdownStartSeconds - state.secondsLeft;
  const timeUntilReady = Math.max(1, state.countdownStartSeconds - 10);
  const loadProgress = Math.min(1, elapsed / timeUntilReady);

  if (state.secondsLeft > 10) {
    state.systemStatus.power = Math.round(loadProgress * 100);
    powerLevel.style.width = state.systemStatus.power + "%";
    powerValue.textContent = Math.round(state.systemStatus.power) + "%";
    guidanceLevel.style.width = state.systemStatus.power + "%";
    commsLevel.style.width = state.systemStatus.power + "%";

    if (loadProgress < 0.25) {
      state.systemStatus.guidance = "BOOTING";
      state.systemStatus.comms = "INITIALIZING";
    } else if (loadProgress < 0.5) {
      state.systemStatus.guidance = "LOADING";
      state.systemStatus.comms = "CONNECTING";
    } else if (loadProgress < 0.75) {
      state.systemStatus.guidance = "CALIBRATING";
      state.systemStatus.comms = "SYNCING";
    } else if (loadProgress < 1) {
      state.systemStatus.guidance = "READY";
      state.systemStatus.comms = "STANDBY";
    } else {
      state.systemStatus.guidance = "ONLINE";
      state.systemStatus.comms = "ONLINE";
      state.systemStatus.power = 100;
      powerLevel.style.width = "100%";
      powerValue.textContent = "100%";
      guidanceLevel.style.width = "100%";
      commsLevel.style.width = "100%";
    }
    guidanceValue.textContent = state.systemStatus.guidance;
    commsValue.textContent = state.systemStatus.comms;
  }

  if (state.secondsLeft <= 11) {
    if (state.secondsLeft >= 0) {
      speakCountdown(state.secondsLeft);
    }
  }

  if (state.secondsLeft <= 10) {
    state.systemStatus.target = "LOCKED";
    state.systemStatus.guidance = "ARMED";
    state.systemStatus.comms = "ARMED";
    state.systemStatus.power = 100;
    state.systemStatus.radar = "CONFIRMED";
    guidanceValue.textContent = state.systemStatus.guidance;
    commsValue.textContent = state.systemStatus.comms;
    powerLevel.style.width = "100%";
    powerValue.textContent = "100%";
    guidanceLevel.style.width = "100%";
    commsLevel.style.width = "100%";

    if (state.secondsLeft === 10) {
      startLaunchSequence();
    }
  } else if (state.secondsLeft <= 30) {
    state.systemStatus.target = "TRACKING";
  }

  if (state.secondsLeft <= 0) {
    cancelDisarm();
    clearInterval(state.tickHandle);
    state.tickHandle = null;
    state.phase = "launched";
    setDisplay("LAUNCH");
    writeLog("Start");
    beep(1040, 250);
    setTimeout(() => beep(1240, 250), 280);
    setLamp(lampReady, false);
    setLamp(lampArmed, true);
    setLamp(lampSafe, false);
    state.systemStatus.target = "LAUNCHED";
    state.systemStatus.guidance = "IN FLIGHT";
    state.systemStatus.radar = "TRACKING";
    updateWorldMap();
    startMissileFlight();
  }
}

export function completeDisarm() {
  if (state.phase !== "counting") return;
  cancelDisarm();
  stopCountdownAudio();
  if (state.tickHandle) {
    clearInterval(state.tickHandle);
    state.tickHandle = null;
  }
  if (state.phase === "counting") {
    stopCountdown("ENTSCHÄRFT");
  }
  stopLaunchSequence();
  state.phase = "disarmed";
  state.secondsLeft = SETTINGS.timerSeconds;
  state.wrongAttempts = 0;
  setDisplay("SAFE");
  timerBadge.style.display = "none";
  setLamp(lampReady, false);
  setLamp(lampArmed, false);
  setLamp(lampSafe, true);
  codeInput.value = "";
  state.systemStatus.target = "DISARMED";
  state.systemStatus.guidance = "OFFLINE";
  state.systemStatus.comms = "OFFLINE";
  state.systemStatus.power = 0;
  state.systemStatus.fuel = 100;
  state.systemStatus.radar = "IDLE";
  fuelLevel.style.width = "100%";
  fuelValue.textContent = "100%";
  powerLevel.style.width = "0%";
  powerValue.textContent = "0%";
  guidanceLevel.style.width = "0%";
  guidanceValue.textContent = "OFFLINE";
  commsLevel.style.width = "0%";
  commsValue.textContent = "OFFLINE";
  state.targetDestroyed = false;
  state.mapData.destroyedTargetId = null;
  resetFlightState();
  targetDestruction.style.display = "none";
  updateWorldMap();
  writeLog("Entschärft");
  beep(720, 160);
}

export function showHackerLoading() {
  if (state.disarmHandle || state.phase !== "counting") return;
  state.disarmDeadline = performance.now() + 10000;
  loadingBar.style.display = "block";
  const messages = [
    "PROTOKOLL INITIIERT",
    "VERBINDE SERVER",
    "AUTHENTIFIZIERUNG OK",
    "ZUGRIFF GEWÄHRT",
    "SICHERHEIT ÜBERBRÜCKT",
    "FIREWALL UMGANGEN",
    "ROOT ZUGRIFF",
    "SENSOREN NEUTRALISIERT",
    "DETONATION UNTERBROCHEN",
    "COUNTDOWN ABGEFANGEN",
    "SPRENGKOPF DEAKTIVIERT",
    "ZÜNDSYSTEM OFFLINE",
    "CODES ÜBERSCHRIEBEN",
    "SICHERHEIT ZURÜCKGESETZT",
    "SYSTEME DEAKTIVIERT",
    "95% ABGESCHLOSSEN",
    "FINALE PRÜFUNG",
    "ENTSCHÄRFT"
  ];
  let index = 0;
  const totalDuration = 10000;
  const messageInterval = totalDuration / messages.length;
  state.disarmHandle = setInterval(() => {
    if (index < messages.length) {
      writeLog(messages[index]);
      index++;
    }
  }, messageInterval);
}

export function cancelDisarm() {
  clearInterval(state.disarmHandle);
  state.disarmHandle = null;
  state.disarmDeadline = 0;
  loadingBar.style.display = "none";
}
