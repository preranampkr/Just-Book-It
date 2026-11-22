/**
 * Browser Speech Synthesis Manager for Just Book It.
 * Uses the free browser Web Speech API (speechSynthesis) to speak responses in
 * English (India), Hindi, and Kannada.
 */

export class SpeechSynthesisManager {
  constructor() {
    this.synth = typeof window !== "undefined" ? window.speechSynthesis : null;
    this.voices = [];
    this.isSpeaking = false;
    this._loadVoices();
  }

  _loadVoices() {
    if (!this.synth) return;
    this.voices = this.synth.getVoices();
    if (this.synth.onvoiceschanged !== undefined) {
      this.synth.onvoiceschanged = () => {
        this.voices = this.synth.getVoices();
      };
    }
  }

  /**
   * Checks if browser speech synthesis is supported.
   * @returns {boolean}
   */
  isSupported() {
    return !!this.synth;
  }

  /**
   * Finds the best matching voice for the target language.
   * Priority:
   * 1. Exact BCP-47 match (e.g. 'en-IN', 'hi-IN', 'kn-IN')
   * 2. Language prefix match (e.g. 'hi', 'kn', 'en')
   * 3. Fallback to default voice
   *
   * @param {string} langCode
   * @returns {{ voice: SpeechSynthesisVoice|null, isExact: boolean }}
   */
  getBestVoice(langCode = "en-IN") {
    if (!this.voices || this.voices.length === 0) {
      this._loadVoices();
    }

    const normalizedLang = langCode.toLowerCase();
    const langPrefix = normalizedLang.split("-")[0];

    // 1. Exact match
    const exactMatch = this.voices.find(
      (v) => v.lang.toLowerCase() === normalizedLang || v.lang.toLowerCase().replace("_", "-") === normalizedLang
    );
    if (exactMatch) {
      return { voice: exactMatch, isExact: true };
    }

    // 2. Prefix match
    const prefixMatch = this.voices.find(
      (v) => v.lang.toLowerCase().startsWith(langPrefix)
    );
    if (prefixMatch) {
      return { voice: prefixMatch, isExact: true };
    }

    // 3. Fallback
    const defaultVoice = this.voices.find((v) => v.default) || (this.voices[0] || null);
    return { voice: defaultVoice, isExact: false };
  }

  /**
   * Speaks the provided text in the target language.
   *
   * @param {string} text
   * @param {string} langCode
   * @returns {Promise<void>} Resolves when speech playback finishes
   */
  speak(text, langCode = "en-IN") {
    return new Promise((resolve) => {
      if (!this.synth || !text || !text.trim()) {
        resolve();
        return;
      }

      // Cancel any ongoing speech before starting a new one
      this.synth.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = langCode;
      utterance.rate = 1.0;
      utterance.pitch = 1.0;

      const { voice, isExact } = this.getBestVoice(langCode);
      if (voice) {
        utterance.voice = voice;
      }

      if (!isExact && langCode === "kn-IN") {
        console.warn(
          "[SpeechSynthesis] System does not have a dedicated Kannada voice installed. Using available system voice fallback."
        );
      }

      this.isSpeaking = true;

      utterance.onend = () => {
        this.isSpeaking = false;
        resolve();
      };

      utterance.onerror = (e) => {
        console.warn("[SpeechSynthesis] Utterance playback issue:", e);
        this.isSpeaking = false;
        resolve();
      };

      this.synth.speak(utterance);
    });
  }

  /**
   * Immediately stops any active speech.
   */
  stop() {
    if (this.synth) {
      this.isSpeaking = false;
      this.synth.cancel();
    }
  }
}
