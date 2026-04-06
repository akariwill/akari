/**
 * AKARI — Main entry point.
 */

import { createOrb, type OrbState } from "./orb";
import { createVoiceInput, createAudioPlayer } from "./voice";
import { createSocket } from "./ws";
import { openSettings, checkFirstTimeSetup } from "./settings";
import "./style.css";

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

type State = "idle" | "listening" | "thinking" | "speaking";
let currentState: State = "idle";
let isMuted = false;
let isWaitingForWelcome = true;

const statusEl = document.getElementById("status-text")!;
const errorEl = document.getElementById("error-text")!;
const startOverlay = document.getElementById("start-overlay")!;
const btnStart = document.getElementById("btn-start") as HTMLButtonElement;
const akariGifContainer = document.getElementById("akari-gif-container")!;

function showError(msg: string) {
  errorEl.textContent = msg;
  errorEl.style.opacity = "1";
  setTimeout(() => {
    errorEl.style.opacity = "0";
  }, 5000);
}

function updateStatus(state: State) {
  const labels: Record<State, string> = {
    idle: "",
    listening: "listening...",
    thinking: "thinking...",
    speaking: "",
  };
  statusEl.textContent = labels[state];
}

// ---------------------------------------------------------------------------
// Init components
// ---------------------------------------------------------------------------

const canvas = document.getElementById("orb-canvas") as HTMLCanvasElement;
const orb = createOrb(canvas);

// Use current window location to derive WS URL, ensuring it works through Vite proxy
const isDev = window.location.port === "5173";
const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
const wsHost = window.location.host;
const WS_URL = `${wsProto}//${wsHost}/ws/voice`;
const socket = createSocket(WS_URL);

const audioPlayer = createAudioPlayer();
orb.setAnalyser(audioPlayer.getAnalyser());

function transition(newState: State) {
  if (newState === currentState) return;
  currentState = newState;
  orb.setState(newState as OrbState);
  updateStatus(newState);

  switch (newState) {
    case "idle":
      if (!isMuted && !isWaitingForWelcome) voiceInput.resume();
      break;
    case "listening":
      if (!isMuted && !isWaitingForWelcome) voiceInput.resume();
      break;
    case "thinking":
      voiceInput.pause();
      break;
    case "speaking":
      voiceInput.pause();
      break;
  }
}

// ---------------------------------------------------------------------------
// Voice input
// ---------------------------------------------------------------------------

const voiceInput = createVoiceInput(
  (text: string) => {
    if (isWaitingForWelcome) return;
    audioPlayer.stop();
    socket.send({ type: "transcript", text, isFinal: true });
    transition("thinking");
  },
  (msg: string) => {
    showError(msg);
  }
);

// ---------------------------------------------------------------------------
// Audio playback finished
// ---------------------------------------------------------------------------

audioPlayer.onFinished(() => {
  if (isWaitingForWelcome) {
    console.log("[welcome] finished, starting listening");
    isWaitingForWelcome = false;
    transition("listening");
    voiceInput.start();
  } else {
    transition("idle");
  }
});

// ---------------------------------------------------------------------------
// WebSocket messages
// ---------------------------------------------------------------------------

socket.onMessage((msg) => {
  const type = msg.type as string;

  if (type === "audio") {
    const audioData = msg.data as string;
    if (audioData) {
      if (currentState !== "speaking") {
        transition("speaking");
      }
      audioPlayer.enqueue(audioData);
    } else {
      transition("idle");
    }
    if (msg.text) console.log("[AKARI]", msg.text);
  } else if (type === "status") {
    const state = msg.state as string;
    if (state === "thinking" && currentState !== "thinking") {
      transition("thinking");
    } else if (state === "working") {
      transition("thinking");
      statusEl.textContent = "working...";
    } else if (state === "idle") {
      if (!isWaitingForWelcome) transition("idle");
    }
  } else if (type === "text") {
    console.log("[AKARI]", msg.text);
  }
});

// ---------------------------------------------------------------------------
// Welcome Message Fetch & Play
// ---------------------------------------------------------------------------

async function playWelcomeSequence() {
  try {
    const resp = await fetch("/api/welcome-audio");
    const data = await resp.json();
    if (data.audio) {
      console.log("[welcome] playing audio");
      transition("speaking");
      await audioPlayer.enqueue(data.audio);
    } else {
      console.warn("[welcome] no audio returned from API, skipping to listening");
      isWaitingForWelcome = false;
      transition("listening");
      voiceInput.start();
    }
  } catch (err) {
    console.error("[welcome] fetch error:", err);
    isWaitingForWelcome = false;
    transition("listening");
    voiceInput.start();
  }
}

// ---------------------------------------------------------------------------
// Kick off
// ---------------------------------------------------------------------------

btnStart.addEventListener("click", () => {
  console.log("[start] user clicked start");
  
  // 1. Resume AudioContext
  const ctx = audioPlayer.getAnalyser().context as AudioContext;
  ctx.resume().then(() => {
    // 2. Hide overlay
    startOverlay.style.opacity = "0";
    setTimeout(() => {
      startOverlay.style.display = "none";
    }, 500);

    // 3. Show GIF if hidden
    akariGifContainer.style.display = "block";

    // 4. Play Welcome Sequence
    playWelcomeSequence();
  });
});

async function playRestartSequence() {
  try {
    const resp = await fetch("/api/restart-audio");
    const data = await resp.json();
    if (data.audio) {
      console.log("[restart] playing audio");
      transition("speaking");
      await audioPlayer.enqueue(data.audio);
    }
  } catch (err) {
    console.error("[restart] fetch error:", err);
  }
}

// ---------------------------------------------------------------------------
// UI Controls
// ---------------------------------------------------------------------------

const btnMute = document.getElementById("btn-mute")!;
const btnMenu = document.getElementById("btn-menu")!;
const menuDropdown = document.getElementById("menu-dropdown")!;
const btnRestart = document.getElementById("btn-restart")!;
const btnFixSelf = document.getElementById("btn-fix-self")!;

btnMute.addEventListener("click", (e) => {
  e.stopPropagation();
  isMuted = !isMuted;
  btnMute.classList.toggle("muted", isMuted);
  if (isMuted) {
    voiceInput.pause();
    transition("idle");
  } else {
    if (!isWaitingForWelcome) {
      voiceInput.resume();
      transition("listening");
    }
  }
});

btnMenu.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = menuDropdown.style.display === "none" ? "block" : "none";
});

document.addEventListener("click", () => {
  menuDropdown.style.display = "none";
});

btnRestart.addEventListener("click", async (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  statusEl.textContent = "restarting...";
  
  // Play restart voice first
  playRestartSequence();

  try {
    await fetch("/api/restart", { method: "POST" });
    // Wait for the audio to play and server to bounce
    setTimeout(() => window.location.reload(), 5000);
  } catch {
    statusEl.textContent = "restart failed";
  }
});

btnFixSelf.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  socket.send({ type: "fix_self" });
  statusEl.textContent = "entering work mode...";
});

const btnSettings = document.getElementById("btn-settings")!;
btnSettings.addEventListener("click", (e) => {
  e.stopPropagation();
  menuDropdown.style.display = "none";
  openSettings();
});

setTimeout(() => {
  checkFirstTimeSetup();
}, 2000);
