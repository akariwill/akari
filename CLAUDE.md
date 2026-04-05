# 🌸 AKARI (渡辺 星) — Guide for AI Assistants

This document contains essential context, instructions, and conventions for AI assistants (like Claude Code) working on the AKARI project.

---

## Quick Start Checklist

If you are helping a user set up AKARI for the first time, follow these steps:

1.  **Environment**: `cp .env.example .env` and prompt for `ANTHROPIC_API_KEY` & `FISH_API_KEY`.
2.  **Certificates**: Run `openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj '/CN=localhost'` for secure WebSockets.
3.  **Dependencies**:
    -   Backend: `pip install -r requirements.txt`
    -   Frontend: `cd frontend && npm install`
4.  **Execution**:
    -   Terminal 1: `python server.py`
    -   Terminal 2: `cd frontend && npm run dev`
5.  **Browser**: Open `http://localhost:5173` in Google Chrome.

---

## Architecture Summary

-   **Backend**: Python + FastAPI (`server.py`). Main orchestrator for LLMs, TTS, and macOS integrations.
-   **Frontend**: Vite + TypeScript + Three.js. Handles the voice loop and particle visualization.
-   **AI Stack**: Claude Haiku (Fast Chat), Claude Opus (Deep Research), Fish Audio (Voice).
-   **Integrations**: AppleScript for native macOS app access (Calendar, Mail, Notes).

---

## Akari Persona & Conventions

When generating voice responses or acting as Akari:

-   **Personality**: Energetic, cheerful, supportive, and slightly playful.
-   **Language**: Uses English but can understand/speak Japanese. Use honorifics like **"-kun"** or **"-san"** for the user.
-   **Brevity**: Keep spoken responses to **1-2 sentences max**. Be concise but lively.
-   **Action Tags**: Use tags like `[ACTION:BUILD]`, `[ACTION:BROWSE]`, `[ACTION:RESEARCH]` to trigger system capabilities.
-   **Safety**: Mail integration is **READ-ONLY**. Never send emails.

---

## Key Files to Know

-   `server.py`: The heart of the project. WebSocket and LLM routing.
-   `actions.py`: Definitions for system actions and Claude Code orchestration.
-   `memory.py`: SQLite-based long-term memory system.
-   `frontend/src/orb.ts`: The Three.js implementation of the Lilac Orb.
-   `frontend/src/voice.ts`: Handles the Web Speech API and audio buffering.

---

## Development Rules

1.  **Style**: Follow existing patterns in `server.py` (FastAPI) and `main.ts` (State Machine).
2.  **Errors**: Always log errors via the `log` object. Notify the user via voice if a critical action fails.
3.  **Dependencies**: Avoid adding new heavy dependencies. Prefer native macOS tools or standard libraries.
4.  **Testing**: After any change, verify the voice loop still works.

---

<p align="center">
  <i>"Let's make today amazing together! ✨"</i>
</p>
