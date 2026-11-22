/**
 * Browser Speech Recognition Manager for Just Book It.
 * Uses the free browser Web Speech API (SpeechRecognition / webkitSpeechRecognition)
 * to provide continuous hands-free voice input in English (India), Hindi, and Kannada.
 */

export class SpeechRecognitionManager {
  constructor(options = {}) {
    this.language = options.language || "en-IN";
    this.onSpeechStart = options.onSpeechStart || (() => {});
    this.onResult = options.onResult || (() => {}); // receives (finalTranscript)
    this.onError = options.onError || (() => {});
    this.onListeningState = options.onListeningState || (() => {});

    this.recognition = null;
    this.isActive = false; // Intended listening state
    this.isPaused = false; // Paused (e.g. during assistant speech or user command)
    this.restartTimer = null;

    this._initRecognition();
  }

  /**
   * Checks if the browser supports SpeechRecognition.
   * Supported out of the box in Google Chrome, Microsoft Edge, and Chromium browsers.
   */
  static isSupported() {
    return (
      typeof window !== "undefined" &&
      !!(window.SpeechRecognition || window.webkitSpeechRecognition)
    );
  }

  _initRecognition() {
    if (!SpeechRecognitionManager.isSupported()) {
      console.warn(
        "[SpeechRecognition] Web Speech API is not supported in this browser. " +
        "Please use Google Chrome or Microsoft Edge."
      );
      return;
    }

    const SpeechRecognitionClass =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    this.recognition = new SpeechRecognitionClass();
    this.recognition.lang = this.language;
    this.recognition.continuous = false; // Single utterance mode + auto restart ensures clean sentence boundaries
    this.recognition.interimResults = true;
    this.recognition.maxAlternatives = 1;

    let hasReportedSpeech = false;
    let finalTranscriptAccumulator = "";

    this.recognition.onstart = () => {
      hasReportedSpeech = false;
      finalTranscriptAccumulator = "";
      if (this.isActive && !this.isPaused) {
        this.onListeningState(true);
      }
    };

    this.recognition.onspeechstart = () => {
      if (this.isActive && !this.isPaused) {
        hasReportedSpeech = true;
        this.onSpeechStart();
      }
    };

    this.recognition.onresult = (event) => {
      if (!this.isActive || this.isPaused) return;

      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const item = event.results[i];
        if (item.isFinal) {
          finalTranscriptAccumulator += item[0].transcript;
        } else {
          interim += item[0].transcript;
        }
      }

      if (!hasReportedSpeech && (interim || finalTranscriptAccumulator)) {
        hasReportedSpeech = true;
        this.onSpeechStart();
      }
    };

    this.recognition.onerror = (event) => {
      // 'no-speech' is completely normal during pauses; don't disrupt the user
      if (event.error === "no-speech") {
        return;
      }

      console.warn(`[SpeechRecognition] Event error: ${event.error}`);

      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        this.onError("Microphone permission was not allowed for speech recognition.");
        this.isActive = false;
      } else if (event.error === "network") {
        this.onError(
          "Speech recognition network error. Browser speech recognition requires an active internet connection."
        );
      } else if (event.error === "language-not-supported") {
        this.onError(`Selected language (${this.language}) is not supported by your browser's speech recognition.`);
      }
    };

    this.recognition.onend = () => {
      // If we collected a final utterance, emit it
      if (finalTranscriptAccumulator.trim()) {
        const transcript = finalTranscriptAccumulator.trim();
        finalTranscriptAccumulator = "";
        this.onResult(transcript);
        return;
      }

      // If still active and not paused by assistant speech, automatically restart listening
      if (this.isActive && !this.isPaused) {
        this._scheduleRestart(150);
      }
    };
  }

  _scheduleRestart(delayMs = 150) {
    if (this.restartTimer) {
      clearTimeout(this.restartTimer);
    }
    this.restartTimer = setTimeout(() => {
      if (this.isActive && !this.isPaused && this.recognition) {
        try {
          this.recognition.start();
        } catch (e) {
          // In case start is called while already starting
          console.debug("[SpeechRecognition] Restart attempt:", e.message);
        }
      }
    }, delayMs);
  }

  /**
   * Starts hands-free continuous listening.
   */
  start() {
    if (!this.recognition) {
      this._initRecognition();
    }
    this.isActive = true;
    this.isPaused = false;
    if (this.recognition) {
      try {
        this.recognition.lang = this.language;
        this.recognition.start();
      } catch (e) {
        console.debug("[SpeechRecognition] Start error (already started):", e.message);
      }
    }
  }

  /**
   * Pauses speech recognition (e.g. while the assistant is speaking out loud).
   */
  pause() {
    this.isPaused = true;
    if (this.restartTimer) {
      clearTimeout(this.restartTimer);
      this.restartTimer = null;
    }
    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch (e) {}
    }
    this.onListeningState(false);
  }

  /**
   * Resumes speech recognition after assistant speech completes.
   */
  resume() {
    this.isPaused = false;
    if (this.isActive) {
      this._scheduleRestart(100);
    }
  }

  /**
   * Updates target recognition language.
   * @param {string} langCode - 'en-IN', 'hi-IN', or 'kn-IN'
   */
  setLanguage(langCode) {
    this.language = langCode;
    if (this.recognition) {
      this.recognition.lang = langCode;
      // If currently active, restart recognition with new language
      if (this.isActive && !this.isPaused) {
        this.pause();
        this.resume();
      }
    }
  }

  /**
   * Completely stops listening and cleans up.
   */
  stop() {
    this.isActive = false;
    this.isPaused = true;
    if (this.restartTimer) {
      clearTimeout(this.restartTimer);
      this.restartTimer = null;
    }
    if (this.recognition) {
      try {
        this.recognition.abort();
      } catch (e) {}
    }
    this.onListeningState(false);
  }
}
