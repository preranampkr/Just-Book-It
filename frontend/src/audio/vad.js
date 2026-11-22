/**
 * Voice Activity Detection (VAD) module for Just Book It.
 * Implements Silero VAD via @ricky0123/vad-web with an Energy-based Web Audio API fallback.
 */

import { encodeWAV, resampleAudio } from "./audioProcessing";

export class VADController {
  constructor(options = {}) {
    this.onSpeechStart = options.onSpeechStart || (() => {});
    this.onSpeechEnd = options.onSpeechEnd || (() => {}); // receives (wavBlob, durationSec)
    this.onVADMisfire = options.onVADMisfire || (() => {});
    this.onError = options.onError || (() => {});
    this.onVolumeChange = options.onVolumeChange || (() => {}); // For audio visualizer/feedback

    this.sileroVAD = null;
    this.fallbackVAD = null;
    this.isListening = false;
    this.isPaused = false;
    this.activeBackend = null; // 'silero' | 'energy-fallback'
  }

  /**
   * Initializes and starts Voice Activity Detection.
   * Attempts Silero VAD first; falls back to Web Audio API Energy VAD on failure.
   */
  async start(stream) {
    if (this.isListening) return;

    try {
      await this._initSileroVAD(stream);
      this.activeBackend = "silero";
      console.log("[VAD] Silero VAD initialized and active.");
    } catch (err) {
      console.warn("[VAD] Silero VAD initialization failed, using Web Audio Energy VAD fallback:", err);
      await this._initEnergyFallbackVAD(stream);
      this.activeBackend = "energy-fallback";
      console.log("[VAD] Fallback Web Audio Energy VAD active.");
    }

    this.isListening = true;
    this.isPaused = false;
  }

  /**
   * Initializes Silero VAD using @ricky0123/vad-web.
   */
  async _initSileroVAD(stream) {
    const { MicVAD } = await import("@ricky0123/vad-web");

    this.sileroVAD = await MicVAD.new({
      stream: stream,
      baseAssetPath: "/vad/",
      onnxWASMBasePath: "/vad/",
      positiveSpeechThreshold: 0.6,
      negativeSpeechThreshold: 0.4,
      redemptionFrames: 8, // ~256ms silence hang-over
      preSpeechPadFrames: 5,
      minSpeechFrames: 5,
      onSpeechStart: () => {
        if (this.isPaused) return;
        this.onSpeechStart();
      },
      onSpeechEnd: (audio) => {
        if (this.isPaused) return;
        // audio is Float32Array at 16000 Hz
        const durationSec = audio.length / 16000;
        if (durationSec < 0.25) {
          this.onVADMisfire();
          return;
        }
        const wavBlob = encodeWAV(audio, 16000);
        this.onSpeechEnd(wavBlob, durationSec);
      },
      onVADMisfire: () => {
        if (this.isPaused) return;
        this.onVADMisfire();
      },
      onFrameProcessed: (probs) => {
        if (this.isPaused) return;
        if (this.onVolumeChange) {
          this.onVolumeChange(probs.isSpeech);
        }
      },
    });

    this.sileroVAD.start();
  }

  /**
   * Fallback Web Audio API Energy/RMS Voice Activity Detector.
   * Analyzes audio frames in real-time, detecting speech onset and silence hangover.
   */
  async _initEnergyFallbackVAD(stream) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    const audioCtx = new AudioContextClass();
    const source = audioCtx.createMediaStreamSource(stream);

    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 1024;
    source.connect(analyser);

    const bufferLength = analyser.fftSize;
    const timeData = new Float32Array(bufferLength);

    // Audio collection state
    let isSpeaking = false;
    let speechBuffer = [];
    let silenceStart = null;
    const SILENCE_TIMEOUT_MS = 900; // 900ms natural pause before utterance completion
    const SPEECH_ENERGY_THRESHOLD = 0.02; // RMS threshold

    const intervalId = setInterval(() => {
      if (this.isPaused || !this.isListening) return;

      analyser.getFloatTimeDomainData(timeData);

      // Calculate Root Mean Square (RMS) energy
      let sumSquares = 0;
      for (let i = 0; i < bufferLength; i++) {
        sumSquares += timeData[i] * timeData[i];
      }
      const rms = Math.sqrt(sumSquares / bufferLength);

      if (this.onVolumeChange) {
        this.onVolumeChange(Math.min(1, rms * 10));
      }

      const now = performance.now();

      if (rms > SPEECH_ENERGY_THRESHOLD) {
        // Speech detected
        if (!isSpeaking) {
          isSpeaking = true;
          this.onSpeechStart();
        }
        silenceStart = null;
        // Keep frame samples
        speechBuffer.push(new Float32Array(timeData));
      } else if (isSpeaking) {
        // Potential silence during active speech
        speechBuffer.push(new Float32Array(timeData));
        if (silenceStart === null) {
          silenceStart = now;
        } else if (now - silenceStart > SILENCE_TIMEOUT_MS) {
          // Finished speaking
          isSpeaking = false;
          silenceStart = null;

          // Merge collected frames
          const totalSamples = speechBuffer.reduce((acc, f) => acc + f.length, 0);
          const fullAudio = new Float32Array(totalSamples);
          let offset = 0;
          for (const frame of speechBuffer) {
            fullAudio.set(frame, offset);
            offset += frame.length;
          }
          speechBuffer = [];

          // Resample to 16kHz
          const resampled = resampleAudio(fullAudio, audioCtx.sampleRate, 16000);
          const durationSec = resampled.length / 16000;

          if (durationSec >= 0.3) {
            const wavBlob = encodeWAV(resampled, 16000);
            this.onSpeechEnd(wavBlob, durationSec);
          } else {
            this.onVADMisfire();
          }
        }
      }
    }, 40);

    this.fallbackVAD = {
      audioCtx,
      intervalId,
      stop: () => {
        clearInterval(intervalId);
        source.disconnect();
        if (audioCtx.state !== "closed") {
          audioCtx.close();
        }
      },
    };
  }

  /**
   * Pauses VAD (e.g. while the assistant is speaking out loud).
   */
  pause() {
    this.isPaused = true;
    if (this.sileroVAD && this.activeBackend === "silero") {
      this.sileroVAD.pause();
    }
  }

  /**
   * Resumes VAD listening after assistant speech finishes.
   */
  resume() {
    this.isPaused = false;
    if (this.sileroVAD && this.activeBackend === "silero") {
      this.sileroVAD.start();
    }
  }

  /**
   * Destroys and cleans up VAD resources.
   */
  destroy() {
    this.isListening = false;
    if (this.sileroVAD) {
      try {
        this.sileroVAD.destroy();
      } catch (e) {}
      this.sileroVAD = null;
    }
    if (this.fallbackVAD) {
      try {
        this.fallbackVAD.stop();
      } catch (e) {}
      this.fallbackVAD = null;
    }
  }
}
