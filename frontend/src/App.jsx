import React, { useState, useEffect, useRef } from "react";
import { MicrophoneManager } from "./audio/microphone";
import { VADController } from "./audio/vad";
import { SpeechRecognitionManager } from "./audio/speechRecognition";
import { SpeechSynthesisManager } from "./audio/speechSynthesis";
import { playAudioFromBase64 } from "./audio/audioProcessing";
import { fetchWelcomeAudio, sendChatTurn } from "./services/voiceApi";
import "./App.css";

const LANGUAGES = {
  "en-IN": { code: "en-IN", name: "English (India)", key: "1" },
  "hi-IN": { code: "hi-IN", name: "हिंदी (Hindi)", key: "2" },
  "kn-IN": { code: "kn-IN", name: "ಕನ್ನಡ (Kannada)", key: "3" },
};

export default function App() {
  // App states: 'onboarding' | 'hands-free'
  const [stage, setStage] = useState("onboarding");
  const [selectedLanguage, setSelectedLanguage] = useState(
    localStorage.getItem("jbi_language") || "en-IN"
  );

  // Voice assistant states: 'idle' | 'listening' | 'user-speaking' | 'processing' | 'assistant-speaking' | 'paused' | 'error'
  const [voiceStatus, setVoiceStatus] = useState("idle");
  const [conversationId, setConversationId] = useState("");
  const [speechVolume, setSpeechVolume] = useState(0);
  const [spokenAnnouncement, setSpokenAnnouncement] = useState("");
  const [browserNotice, setBrowserNotice] = useState("");

  const micManagerRef = useRef(null);
  const vadControllerRef = useRef(null);
  const recognitionRef = useRef(null);
  const synthRef = useRef(null);
  const isPlayingRef = useRef(false);

  // Initialize Audio & Speech Services
  useEffect(() => {
    micManagerRef.current = new MicrophoneManager();
    synthRef.current = new SpeechSynthesisManager();

    // Check browser speech recognition support
    if (!SpeechRecognitionManager.isSupported()) {
      setBrowserNotice(
        "Browser Speech Recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge."
      );
    }

    // Initialize VAD for reactive aura animation
    vadControllerRef.current = new VADController({
      onSpeechStart: () => {},
      onSpeechEnd: () => {},
      onVADMisfire: () => {},
      onVolumeChange: (vol) => setSpeechVolume(vol),
    });

    // Initialize Speech Recognition
    recognitionRef.current = new SpeechRecognitionManager({
      language: selectedLanguage,
      onSpeechStart: handleSpeechStart,
      onResult: handleSpeechResult,
      onError: handleSpeechError,
      onListeningState: (isListening) => {
        if (!isPlayingRef.current && voiceStatus !== "paused" && voiceStatus !== "processing") {
          setVoiceStatus(isListening ? "listening" : "idle");
        }
      },
    });

    return () => {
      if (recognitionRef.current) recognitionRef.current.stop();
      if (synthRef.current) synthRef.current.stop();
      if (vadControllerRef.current) vadControllerRef.current.destroy();
      if (micManagerRef.current) micManagerRef.current.stop();
    };
  }, []);

  // Keyboard accessibility shortcuts (1, 2, 3 for languages, Space for Pause/Resume)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (stage === "onboarding") {
        if (e.key === "1") handleLanguageSelect("en-IN");
        if (e.key === "2") handleLanguageSelect("hi-IN");
        if (e.key === "3") handleLanguageSelect("kn-IN");
      } else if (stage === "hands-free") {
        if (e.code === "Space") {
          e.preventDefault();
          togglePauseResume();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [stage, voiceStatus, selectedLanguage]);

  // Handle Speech Start from browser recognition
  function handleSpeechStart() {
    if (isPlayingRef.current || voiceStatus === "paused") return;
    setVoiceStatus("user-speaking");
    setSpokenAnnouncement("Hearing you speak...");
  }

  // Handle Final Speech Result from browser recognition
  async function handleSpeechResult(transcript) {
    if (isPlayingRef.current || voiceStatus === "paused") return;
    if (!transcript || !transcript.trim()) return;

    setVoiceStatus("processing");
    setSpokenAnnouncement(`Processing: ${transcript}`);

    // Pause recognition while assistant processes and speaks
    if (recognitionRef.current) {
      recognitionRef.current.pause();
    }

    try {
      // Send recognized text to backend Gemini service
      const result = await sendChatTurn(transcript, conversationId, selectedLanguage);

      if (result.conversation_id) {
        setConversationId(result.conversation_id);
      }

      // Handle spoken language switch
      let targetLang = selectedLanguage;
      if (result.language_code && result.language_code !== selectedLanguage) {
        targetLang = result.language_code;
        setSelectedLanguage(targetLang);
        localStorage.setItem("jbi_language", targetLang);
        if (recognitionRef.current) {
          recognitionRef.current.setLanguage(targetLang);
        }
      }

      // Check if user requested pause
      if (result.action === "pause") {
        await playSpokenResponse(result.response_text, result.audio_base64, result.audio_format, targetLang);
        setVoiceStatus("paused");
        setSpokenAnnouncement("Assistant paused. Say resume or press space to continue.");
        return;
      }

      // Speak assistant response
      await playSpokenResponse(result.response_text, result.audio_base64, result.audio_format, targetLang);

      // Automatically resume continuous listening after playback finishes
      setVoiceStatus("listening");
      setSpokenAnnouncement("Listening for your response...");
      if (recognitionRef.current) {
        recognitionRef.current.resume();
      }
    } catch (err) {
      console.error("[ChatTurn Error]", err);
      setVoiceStatus("error");
      const errorMsg = "Sorry, I had trouble planning that. Please speak again.";
      setSpokenAnnouncement(errorMsg);
      await synthRef.current.speak(errorMsg, selectedLanguage);
      setVoiceStatus("listening");
      if (recognitionRef.current) {
        recognitionRef.current.resume();
      }
    }
  }

  function handleSpeechError(errorMsg) {
    console.warn("[SpeechRecognition Error]", errorMsg);
    setSpokenAnnouncement(errorMsg);
  }

  // Plays spoken response via audio base64 or browser speechSynthesis
  async function playSpokenResponse(text, audioBase64, audioFormat, langCode) {
    isPlayingRef.current = true;
    setVoiceStatus("assistant-speaking");

    if (audioBase64) {
      try {
        await playAudioFromBase64(audioBase64, audioFormat || "audio/mp3");
      } catch (err) {
        await synthRef.current.speak(text, langCode);
      }
    } else if (text) {
      await synthRef.current.speak(text, langCode);
    }

    isPlayingRef.current = false;
  }

  // Toggle Pause/Resume hands-free listening
  function togglePauseResume() {
    if (voiceStatus === "paused") {
      setVoiceStatus("listening");
      setSpokenAnnouncement("Listening resumed.");
      if (recognitionRef.current) {
        recognitionRef.current.resume();
      }
    } else {
      setVoiceStatus("paused");
      setSpokenAnnouncement("Listening paused.");
      if (synthRef.current) {
        synthRef.current.stop();
      }
      if (recognitionRef.current) {
        recognitionRef.current.pause();
      }
    }
  }

  // Stage A: Language Selection & Microphone Onboarding
  async function handleLanguageSelect(langCode) {
    setSelectedLanguage(langCode);
    localStorage.setItem("jbi_language", langCode);

    if (recognitionRef.current) {
      recognitionRef.current.setLanguage(langCode);
    }

    try {
      // 1. Resume AudioContext upon user gesture
      micManagerRef.current.getOrCreateAudioContext();

      // 2. Play welcome audio
      const welcomeData = await fetchWelcomeAudio(langCode);
      const welcomeText = welcomeData?.welcome_text || "Welcome to Just Book It. Speak naturally to plan your trip.";

      if (welcomeData && welcomeData.audio_base64) {
        try {
          await playAudioFromBase64(welcomeData.audio_base64, welcomeData.audio_format || "audio/mp3");
        } catch (e) {
          await synthRef.current.speak(welcomeText, langCode);
        }
      } else {
        await synthRef.current.speak(welcomeText, langCode);
      }

      // 3. Request microphone permission
      const stream = await micManagerRef.current.requestMicrophone();

      // 4. Start VAD for reactive visual aura
      try {
        await vadControllerRef.current.start(stream);
      } catch (e) {
        console.debug("VAD start optional:", e);
      }

      // 5. Start browser Speech Recognition
      if (recognitionRef.current) {
        recognitionRef.current.start();
      }

      // 6. Transition to Hands-Free mode automatically
      setStage("hands-free");
      setVoiceStatus("listening");
      setSpokenAnnouncement("Hands-free assistant active. Speak naturally.");
    } catch (err) {
      console.error("[Onboarding Error]", err);
      const errMsg = `Microphone access required: ${err.message}`;
      setSpokenAnnouncement(errMsg);
      await synthRef.current.speak(errMsg, langCode);
    }
  }

  // Render Onboarding Screen (Accessibility exception)
  if (stage === "onboarding") {
    return (
      <main className="app-container" role="main">
        <div className="sr-only" role="status" aria-live="assertive">
          Welcome to Just Book It. Choose your preferred language: English, Hindi, or Kannada. Press 1 for English, 2 for Hindi, or 3 for Kannada.
        </div>

        <section className="onboarding-card" aria-labelledby="welcome-heading">
          <header>
            <h1 id="welcome-heading" className="onboarding-title">
              Just Book It
            </h1>
            <p className="onboarding-subtitle">
              A completely hands-free AI travel planning assistant. No screens or typing required.
              Choose your language to begin:
            </p>
            {browserNotice && (
              <p className="browser-warning" role="alert" style={{ color: "#f87171", fontSize: "0.9rem", marginTop: "0.5rem" }}>
                {browserNotice}
              </p>
            )}
          </header>

          <nav className="language-grid" aria-label="Language selection">
            {Object.values(LANGUAGES).map((lang) => (
              <button
                key={lang.code}
                className="lang-btn"
                onClick={() => handleLanguageSelect(lang.code)}
                aria-label={`Select ${lang.name}, press ${lang.key}`}
              >
                <span>{lang.name}</span>
                <span className="key-hint" aria-hidden="true">Press [{lang.key}]</span>
              </button>
            ))}
          </nav>
        </section>
      </main>
    );
  }

  // Render Stage B: Continuous Hands-Free Experience (No Screens Theme)
  const statusLabels = {
    listening: "Listening...",
    "user-speaking": "Hearing You...",
    processing: "Planning...",
    "assistant-speaking": "Speaking...",
    paused: "Listening Paused",
    error: "Connection Notice",
    idle: "Ready",
  };

  const statusInstructions = {
    listening: "Speak naturally. Tell me where you'd like to travel.",
    "user-speaking": "Go ahead, I'm listening to your complete thought.",
    processing: "Consulting travel intelligence...",
    "assistant-speaking": "Microphone is muted while assistant speaks.",
    paused: "Tap anywhere or press Space to resume listening.",
    error: "Reconnecting speech services. Speak whenever you are ready.",
    idle: "Waiting for speech...",
  };

  return (
    <main
      className="app-container voice-main"
      onClick={togglePauseResume}
      role="region"
      aria-label="Hands-Free Voice Travel Assistant"
      tabIndex={0}
    >
      {/* Accessible live region for screen-readers */}
      <div className="sr-only" role="status" aria-live="assertive">
        {spokenAnnouncement}
      </div>

      {/* Voice Aura / Reactive Soundwave */}
      <div className="voice-orb-container" aria-hidden="true">
        <div className={`voice-ripple ${voiceStatus}`} />
        <div
          className={`voice-orb ${voiceStatus}`}
          style={{
            transform:
              voiceStatus === "user-speaking"
                ? `scale(${1.2 + Math.min(0.4, speechVolume * 0.5)})`
                : undefined,
          }}
        />
      </div>

      {/* Status Feedback */}
      <div className={`status-badge ${voiceStatus}`} aria-live="polite">
        {statusLabels[voiceStatus] || "Active"}
      </div>

      <p className="status-instruction" aria-hidden="true">
        {statusInstructions[voiceStatus]}
      </p>

      {/* High-Contrast Accessible Indicators */}
      <footer className="hands-free-footer" aria-hidden="true">
        <div className="lang-pill">
          <span className="dot" />
          <span>{LANGUAGES[selectedLanguage]?.name || selectedLanguage}</span>
        </div>
        <p className="accessibility-hint">
          Say "Pause listening" or press Space to pause / resume
        </p>
      </footer>
    </main>
  );
}
