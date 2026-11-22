/**
 * API service client for Just Book It backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

/**
 * Checks backend health and integration readiness.
 */
export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (!res.ok) {
      throw new Error(`Health check returned status ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.error("Health check error:", err);
    throw err;
  }
}

/**
 * Fetches spoken welcome audio and text for the initial onboarding screen.
 */
export async function fetchWelcomeAudio(languageCode = "en-IN") {
  try {
    const res = await fetch(`${API_BASE_URL}/api/welcome-audio?language_code=${encodeURIComponent(languageCode)}`);
    if (!res.ok) {
      throw new Error(`Failed to fetch welcome audio: HTTP ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    console.warn("Failed to fetch welcome audio from backend:", err);
    return null;
  }
}

/**
 * Sends a completed audio utterance to the backend for speech recognition,
 * Gemini reasoning, and text-to-speech synthesis.
 *
 * @param {Blob} wavBlob - The 16kHz LINEAR16 WAV audio blob
 * @param {string} conversationId - The active conversation ID
 * @param {string} languageCode - Target language ('en-IN', 'hi-IN', 'kn-IN')
 * @returns {Promise<{
 *   conversation_id: string,
 *   transcript: string,
 *   response_text: string,
 *   audio_base64: string,
 *   audio_format: string,
 *   action: string,
 *   language_code: string
 * }>}
 */
export async function sendVoiceTurn(wavBlob, conversationId, languageCode = "en-IN") {
  const formData = new FormData();
  formData.append("audio", wavBlob, "utterance.wav");
  if (conversationId) {
    formData.append("conversation_id", conversationId);
  }
  formData.append("language_code", languageCode);

  const res = await fetch(`${API_BASE_URL}/api/voice-turn`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}`;
    try {
      const errorJson = await res.json();
      errorDetail = errorJson.detail || errorDetail;
    } catch (e) {
      errorDetail = await res.text();
    }
    throw new Error(errorDetail);
  }

  return await res.json();
}

/**
 * Sends recognized text from browser speech recognition to the backend for
 * Gemini reasoning and conversational context management.
 *
 * @param {string} transcript - The recognized text from Web Speech API
 * @param {string} conversationId - The active conversation ID
 * @param {string} languageCode - Target language ('en-IN', 'hi-IN', 'kn-IN')
 * @returns {Promise<{
 *   conversation_id: string,
 *   transcript: string,
 *   response_text: string,
 *   audio_base64: string|null,
 *   audio_format: string|null,
 *   action: string,
 *   language_code: string
 * }>}
 */
export async function sendChatTurn(transcript, conversationId, languageCode = "en-IN") {
  const res = await fetch(`${API_BASE_URL}/api/chat-turn`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      transcript,
      conversation_id: conversationId || null,
      language_code: languageCode,
    }),
  });

  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}`;
    try {
      const errorJson = await res.json();
      errorDetail = errorJson.detail || errorDetail;
    } catch (e) {
      errorDetail = await res.text();
    }
    throw new Error(errorDetail);
  }

  return await res.json();
}
