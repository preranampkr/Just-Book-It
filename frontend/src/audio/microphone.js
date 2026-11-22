/**
 * Microphone manager using Web Audio API.
 * Configures hardware/browser noise suppression, echo cancellation, and auto gain control.
 */

export class MicrophoneManager {
  constructor() {
    this.stream = null;
    this.audioContext = null;
    this.mediaStreamSource = null;
    this.isMuted = false;
  }

  /**
   * Checks current permission status for microphone.
   * @returns {Promise<'granted'|'denied'|'prompt'>}
   */
  async checkPermissionStatus() {
    if (navigator.permissions && navigator.permissions.query) {
      try {
        const status = await navigator.permissions.query({ name: "microphone" });
        return status.state;
      } catch (e) {
        // Some browsers do not support microphone in permissions.query
        return "prompt";
      }
    }
    return "prompt";
  }

  /**
   * Requests user microphone with echo cancellation, noise suppression, and AGC enabled.
   * @returns {Promise<MediaStream>}
   */
  async requestMicrophone() {
    const audioConstraints = {
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
      video: false,
    };

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Web Audio API / getUserMedia is not supported in this browser.");
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia(audioConstraints);
      return this.stream;
    } catch (err) {
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        throw new Error("Microphone permission was denied. Please allow microphone access to talk to Just Book It.");
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        throw new Error("No microphone device was detected on your system.");
      }
      throw err;
    }
  }

  /**
   * Initializes or resumes the AudioContext (handling user-gesture requirements).
   */
  getOrCreateAudioContext() {
    if (!this.audioContext) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      this.audioContext = new AudioContextClass();
    }
    if (this.audioContext.state === "suspended") {
      this.audioContext.resume();
    }
    return this.audioContext;
  }

  /**
   * Temporarily mutes or un-mutes the microphone track (e.g. during assistant speech playback).
   * @param {boolean} muted
   */
  setMute(muted) {
    this.isMuted = muted;
    if (this.stream) {
      this.stream.getAudioTracks().forEach((track) => {
        track.enabled = !muted;
      });
    }
  }

  /**
   * Releases all audio tracks and closes AudioContext.
   */
  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
    if (this.audioContext && this.audioContext.state !== "closed") {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
}
