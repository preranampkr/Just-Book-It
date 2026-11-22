# Just Book It — Milestone 1: Hands-Free Voice Assistant

> **Hackathon Theme:** No Screens  
> **Vision:** A completely hands-free AI travel planning assistant designed for blind users, elderly people, and anyone who cannot or prefers not to interact with a screen.

---

## 1. Product Overview

**Just Book It** is a screenless, hands-free conversational voice assistant. During normal operation, there is no typing field, no microphone button to click, no chat bubbles, and no requirement to interact with the screen.

The user simply speaks naturally. The assistant:
1. Greets the user with a spoken welcome.
2. Lets the user choose **English (India)**, **Hindi**, or **Kannada** (via voice or accessible onboarding).
3. Requests microphone permission explicitly.
4. Automatically starts listening without requiring button taps.
5. Employs browser-native Speech Recognition (`SpeechRecognition` / `webkitSpeechRecognition`) to detect speech onset and utterance completion without requiring Google Cloud billing.
6. Employs Web Audio API and on-device Voice Activity Detection (VAD) to provide real-time audio energy visualization (reactive glowing voice aura).
7. Transmits the utterance to the **FastAPI** backend where **Gemini** (via the official `google-genai` SDK and free Google AI Studio API key) understands travel context, duration, and budget.
8. Speaks the response through browser **Speech Synthesis** (`speechSynthesis`).
9. Automatically pauses microphone capture while the assistant is speaking (preventing echo loops) and resumes listening immediately when speech finishes.

---

## 2. Architecture & Free Service Stack

```
just-book-it/
├── backend/
│   ├── main.py              # FastAPI server (/health, /api/chat-turn, /api/voice-turn, /api/welcome-audio)
│   ├── voice_service.py     # Conversation session manager & turn orchestrator
│   ├── gemini_service.py    # Official google-genai SDK integration & travel prompt engine
│   ├── speech_service.py    # Google Cloud STT client (optional; bypassed for browser Web Speech)
│   ├── tts_service.py       # Google Cloud TTS client (optional; bypassed for browser Web Speech)
│   ├── test_suite.py        # Automated test suite (11 comprehensive tests)
│   ├── requirements.txt     # Python dependencies
│   ├── .env.example         # Template environment variables
│   └── venv/                # Python virtual environment
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Hands-free voice interface & accessible onboarding
│   │   ├── App.css          # High-contrast reactive voice aura & accessibility styles
│   │   ├── audio/
│   │   │   ├── speechRecognition.js # Browser SpeechRecognition (webkitSpeechRecognition)
│   │   │   ├── speechSynthesis.js   # Browser speechSynthesis with voice fallbacks
│   │   │   ├── microphone.js        # Web Audio API getUserMedia & hardware noise/echo control
│   │   │   ├── vad.js               # Silero VAD + Energy VAD for reactive aura animation
│   │   │   └── audioProcessing.js   # 16kHz LINEAR16 WAV encoder & base64 audio player
│   │   └── services/
│   │       └── voiceApi.js          # Backend API client (/api/chat-turn, /api/voice-turn)
│   ├── public/vad/          # Local ONNX runtime and Silero VAD models
│   ├── package.json
│   └── vite.config.js       # Vite configuration with proxy to backend
├── .gitignore
└── README.md
```

### Components Summary:
- **Speech Recognition (STT):** Free browser Web Speech API (`webkitSpeechRecognition` in Chrome / Edge). Does **not** require Google Cloud billing or service account credentials.
- **Speech Synthesis (TTS):** Free browser Web Speech API (`window.speechSynthesis`).
- **Intelligence:** **Gemini 2.5 Flash** via the official `google-genai` Python SDK (uses a free Google AI Studio API key).
- **Audio & Visualizer:** Web Audio API (`getUserMedia` with noise suppression, echo cancellation, auto gain control) + Silero VAD / Energy VAD driving the reactive voice ring.

---

## 3. Browser Compatibility & Language Support

### Recommended Browsers
- **Google Chrome** (Version 100+ recommended)
- **Microsoft Edge** (Chromium-based)

> **Important Internet Notice:** Browser-native speech recognition (`webkitSpeechRecognition`) uses the browser's built-in cloud speech service, which requires an active internet connection and is not guaranteed to function offline.

### Language & Voice Availability (Evaluated in Chrome on Windows)
1. **English (India - `en-IN`):** Fully supported for Speech Recognition and Speech Synthesis.
2. **Hindi (India - `hi-IN`):** Fully supported for Speech Recognition and Speech Synthesis (Chrome includes native `Google हिन्दी` voice).
3. **Kannada (India - `kn-IN`):**
   - **Speech Recognition:** Supported in Chrome for speech-to-text.
   - **Speech Synthesis:** If a Windows machine does not have a dedicated Kannada TTS voice pack installed, the application gracefully falls back to the system's default voice, ensuring speech playback never crashes or hangs.

---

## 4. Travel Interaction Stages & Safety

The assistant strictly distinguishes three stages of travel interaction:
1. **Exploration:** Discovers destinations, sights, culture, and activities (e.g., *"I want to visit Goa"*).
2. **Planning:** Organizes itineraries based on duration, budget, and preferences (e.g., *"Five days with a budget of ₹25,000"*). Retains context across conversational turns.
3. **Execution:** Booking, payment, or cancellation.
   - **Safety Rule:** Live booking transactions and supplier pricing are **not** connected.
   - The assistant **never claims a booking has been made** and **never fabricates flight/hotel prices**.

---

## 5. Spoken Commands & Hands-Free Operation

- **No screen interaction required:** After initial onboarding, the assistant continuously listens and speaks.
- **Microphone Auto-Mute:** Microphone input is automatically muted while the assistant speaks and re-activates immediately after speech ends.
- **Spoken Commands:**
  - Say *"Pause listening"* or *"Stop listening"* to pause listening.
  - Say *"Resume listening"* or *"Continue"* to resume.
  - Say *"Switch to Hindi"*, *"Switch to Kannada"*, or *"Switch to English"* to change language on the fly.
- **Accessibility Fallback:**
  - Press the `Spacebar` or tap anywhere on the screen to toggle Pause/Resume.
  - Hotkeys on onboarding: `1` for English, `2` for Hindi, `3` for Kannada.

---

## 6. How to Run on Windows

### Step 1: Backend Setup

1. **Open PowerShell in the backend directory:**
   ```powershell
   cd "C:\Users\ASUS\Desktop\SEMESTER 1\JBI\backend"
   ```

2. **Verify `.env` configuration:**
   Ensure `backend/.env` contains your Gemini API key from Google AI Studio:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key
   GEMINI_MODEL=gemini-2.5-flash
   HOST=127.0.0.1
   PORT=8000
   ```
   *(Notice: `GOOGLE_APPLICATION_CREDENTIALS` is omitted / commented out, removing all Google Cloud billing requirements).*

3. **Start the FastAPI backend:**
   ```powershell
   .\venv\Scripts\python.exe main.py
   ```
   The backend will start at `http://127.0.0.1:8000`.

---

### Step 2: Frontend Setup

1. **Open a new PowerShell window in the frontend directory:**
   ```powershell
   cd "C:\Users\ASUS\Desktop\SEMESTER 1\JBI\frontend"
   ```

2. **Start the Vite development server:**
   ```powershell
   npm.cmd run dev
   ```

3. **Launch in Google Chrome:**
   Open Chrome and navigate to:
   ```text
   http://127.0.0.1:5173
   ```

4. **Start Speaking:**
   - Click your language (or press `1`, `2`, or `3`).
   - Grant microphone permission when prompted.
   - The assistant will speak the welcome message, and automatically transition into continuous hands-free listening mode!

---

## 7. Automated Test Suite

Run the backend test suite:
```powershell
cd "C:\Users\ASUS\Desktop\SEMESTER 1\JBI\backend"
.\venv\Scripts\pytest.exe test_suite.py -v
```

**Results:**
```text
test_suite.py::test_health_endpoint PASSED                               [  9%]
test_suite.py::test_welcome_audio_endpoint PASSED                        [ 18%]
test_suite.py::test_voice_turn_invalid_language PASSED                   [ 27%]
test_suite.py::test_chat_turn_invalid_language PASSED                    [ 36%]
test_suite.py::test_voice_turn_empty_audio PASSED                        [ 45%]
test_suite.py::test_audio_validation PASSED                              [ 54%]
test_suite.py::test_conversation_continuity_5_turns PASSED               [ 63%]
test_suite.py::test_hindi_conversation_turn PASSED                       [ 72%]
test_suite.py::test_kannada_conversation_turn PASSED                     [ 81%]
test_suite.py::test_spoken_pause_command PASSED                          [ 90%]
test_suite.py::test_spoken_language_switch PASSED                        [100%]

============================= 11 passed in 0.60s ==============================
```
