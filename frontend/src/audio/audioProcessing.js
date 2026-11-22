/**
 * Audio processing utilities for Just Book It.
 * Converts Web Audio API Float32 PCM to 16kHz mono LINEAR16 WAV.
 */

/**
 * Encodes Float32Array PCM samples ([-1.0, 1.0]) to a standard 16-bit mono PCM WAV Blob.
 *
 * @param {Float32Array} samples - Audio samples
 * @param {number} sampleRate - Sample rate (default 16000 Hz)
 * @returns {Blob} - audio/wav Blob with standard 44-byte RIFF header
 */
export function encodeWAV(samples, sampleRate = 16000) {
  const numChannels = 1;
  const bytesPerSample = 2; // 16-bit PCM
  const blockAlign = numChannels * bytesPerSample;
  const byteRate = sampleRate * blockAlign;
  const dataSize = samples.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  // Helper to write ASCII strings
  const writeString = (offset, string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  };

  // RIFF Chunk Descriptor
  writeString(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true); // ChunkSize
  writeString(8, "WAVE");

  // "fmt " Subchunk
  writeString(12, "fmt ");
  view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
  view.setUint16(20, 1, true); // AudioFormat (1 = PCM)
  view.setUint16(22, numChannels, true); // NumChannels (1 = Mono)
  view.setUint32(24, sampleRate, true); // SampleRate
  view.setUint32(28, byteRate, true); // ByteRate
  view.setUint16(32, blockAlign, true); // BlockAlign
  view.setUint16(34, 16, true); // BitsPerSample (16 bits)

  // "data" Subchunk
  writeString(36, "data");
  view.setUint32(40, dataSize, true); // Subchunk2Size

  // Write 16-bit PCM samples with clipping
  let offset = 44;
  for (let i = 0; i < samples.length; i++) {
    let s = Math.max(-1, Math.min(1, samples[i]));
    // Convert float [-1.0, 1.0] to int16 [-32768, 32767]
    const sample = s < 0 ? s * 0x8000 : s * 0x7fff;
    view.setInt16(offset, sample, true);
    offset += 2;
  }

  return new Blob([view], { type: "audio/wav" });
}

/**
 * Resamples an audio buffer to 16000 Hz if needed.
 *
 * @param {Float32Array} audioData
 * @param {number} inputSampleRate
 * @param {number} targetSampleRate
 * @returns {Float32Array}
 */
export function resampleAudio(audioData, inputSampleRate, targetSampleRate = 16000) {
  if (inputSampleRate === targetSampleRate) {
    return audioData;
  }

  const ratio = inputSampleRate / targetSampleRate;
  const newLength = Math.round(audioData.length / ratio);
  const result = new Float32Array(newLength);

  for (let i = 0; i < newLength; i++) {
    const originalPos = i * ratio;
    const index = Math.floor(originalPos);
    const fraction = originalPos - index;

    const sample1 = audioData[index] || 0;
    const sample2 = audioData[index + 1] || sample1;

    // Linear interpolation
    result[i] = sample1 + fraction * (sample2 - sample1);
  }

  return result;
}

/**
 * Plays base64-encoded audio using HTML Audio element.
 *
 * @param {string} base64Data
 * @param {string} mimeType
 * @returns {Promise<void>} Resolves when playback finishes
 */
export function playAudioFromBase64(base64Data, mimeType = "audio/mp3") {
  return new Promise((resolve, reject) => {
    try {
      const audioUrl = `data:${mimeType};base64,${base64Data}`;
      const audio = new Audio(audioUrl);

      audio.onended = () => {
        resolve();
      };

      audio.onerror = (e) => {
        reject(new Error(`Audio playback error: ${e.message || "Failed to decode/play audio"}`));
      };

      audio.play().catch((err) => {
        reject(err);
      });
    } catch (err) {
      reject(err);
    }
  });
}
