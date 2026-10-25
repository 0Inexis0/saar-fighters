import {state} from './missile.js';

export function ensureAudioContext() {
  if (state.audioCtx) {
    if (state.audioCtx.state === "suspended") {
      state.audioCtx.resume().catch(() => {});
    }
    return state.audioCtx;
  }
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return null;
  try {
    state.audioCtx = new Ctx();
  } catch {
    state.audioCtx = null;
  }
  return state.audioCtx;
}

export function playTone(frequency = 440, duration = 150, type = "sine", volume = 0.18) {
  const ctx = ensureAudioContext();
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(frequency, ctx.currentTime);
  const stopTime = ctx.currentTime + Math.max(duration, 0) / 1000;
  gain.gain.setValueAtTime(volume, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.0001, stopTime);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(stopTime);
  osc.onended = () => {
    osc.disconnect();
    gain.disconnect();
  };
}

export function beep(frequency = 800, duration = 150) {
  playTone(frequency, duration, "triangle", 0.22);
}

export function buzz(frequency = 220, duration = 220) {
  playTone(frequency, duration, "sawtooth", 0.25);
}

let countdownAudio = null;
let hasPlayedThisCountdown = false;

function initCountdownAudio() {
  if (!countdownAudio) {
    countdownAudio = new Audio('assets/Tactical Nuke Test Countdown and Explosion Sound Effect.mp3');
    countdownAudio.volume = 0.7;
    countdownAudio.preload = 'auto';
  }
  return countdownAudio;
}

export function speakCountdown(value) {
  if (value === 11 && !hasPlayedThisCountdown) {
    const audio = initCountdownAudio();
    audio.currentTime = 0;
    audio.play().catch((error) => {
      console.log("Audio play failed:", error);
    });
    hasPlayedThisCountdown = true;
  }
}

export function stopCountdownAudio() {
  hasPlayedThisCountdown = false;
  if (countdownAudio) {
    countdownAudio.pause();
    countdownAudio.currentTime = 0;
  }
}

let explosionAudio = null;

function initExplosionAudio() {
  if (!explosionAudio) {
    explosionAudio = new Audio('assets/Explosion - Sound Effect.mp3');
    explosionAudio.volume = 0.8;
    explosionAudio.preload = 'auto';
  }
  return explosionAudio;
}

export function playExplosion() {
  const audio = initExplosionAudio();
  audio.currentTime = 0;
  audio.play().catch((error) => {
    console.log("Explosion audio play failed:", error);
  });
}

export function stopAllAudio() {
  stopCountdownAudio();
  if (explosionAudio) {
    explosionAudio.pause();
    explosionAudio.currentTime = 0;
  }
}

// export function speakCountdown(value) {
//   if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
//   if (state.lastCountdownSpoken === value) return;
//   try {
//     const synth = window.speechSynthesis;
//     if (!synth) return;
//     state.lastCountdownSpoken = value;
//     if (synth.speaking || synth.pending) {
//       synth.cancel();
//     }
//     const phrase = value === 0 ? "Launch" : value.toString();
//     const utterance = new SpeechSynthesisUtterance(phrase);
//     utterance.rate = 1;
//     utterance.pitch = 1;
//     utterance.volume = 1;
//     synth.speak(utterance);
//   } catch (error) {
//     state.lastCountdownSpoken = null;
//   }
// }
