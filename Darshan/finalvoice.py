import os
import sys
import tempfile
import time

import sounddevice as sd
from scipy.io.wavfile import write
import numpy as np
import whisper


# ====== CONFIGURATION ======
SAMPLE_RATE = 16000    # Whisper default
CHANNELS = 1           # mono
RECORD_SECONDS = 5     # how long to record per run
MODEL_NAME = "small"   # "tiny", "base", "small", "medium", "large"
# ===========================


def record_audio(duration=RECORD_SECONDS, fs=SAMPLE_RATE, channels=CHANNELS):
    """
    Record audio from the default microphone for `duration` seconds.
    Returns a NumPy array (float32) with shape (N, channels).
    """
    print(f"\n[INFO] Recording for {duration} seconds... Speak now.")
    sd.default.samplerate = fs
    sd.default.channels = channels

    audio = sd.rec(int(duration * fs), samplerate=fs, channels=channels, dtype="float32")
    sd.wait()  # wait until recording is finished
    print("[INFO] Recording finished.\n")
    return audio


def save_to_wav(audio, fs=SAMPLE_RATE):
    """
    Save the audio to a temporary WAV file and return the file path.
    Whisper can read directly from file paths.
    """
    # Convert float32 -1..1 to int16
    audio_int16 = np.int16(audio * 32767)

    tmp_dir = tempfile.gettempdir()
    wav_path = os.path.join(tmp_dir, f"whisper_recording_{int(time.time())}.wav")
    write(wav_path, fs, audio_int16)
    print(f"[INFO] Saved recording to: {wav_path}")
    return wav_path


def transcribe_file(model, wav_path):
    """
    Run Whisper on the given WAV file and return the recognized text.
    """
    print("[INFO] Transcribing with Whisper...")
    result = model.transcribe(wav_path)
    text = result.get("text", "").strip()
    print("[INFO] Transcription complete.\n")
    return text


def main():
    print("======================================")
    print("   Whisper Microphone Speech-to-Text  ")
    print("======================================\n")

    # Load Whisper model once
    print(f"[INFO] Loading Whisper model: {MODEL_NAME} (this may take a moment the first time)...")
    model = whisper.load_model(MODEL_NAME)
    print("[INFO] Model loaded.\n")

    # You can wrap this in a loop if you want repeated commands
    while True:
        try:
            # 1) Record
            audio = record_audio()

            # 2) Save to WAV
            wav_path = save_to_wav(audio)

            # 3) Transcribe
            text = transcribe_file(model, wav_path)

            if text:
                print(f"Recognized text: \"{text}\"\n")
            else:
                print("No speech recognized.\n")

            # TODO: Here is where you can connect to your coupled-tank logic
            # Example:
            # if "start pump" in text.lower():
            #     start_pump()
            # elif "stop pump" in text.lower():
            #     stop_pump()

            # Ask user if they want to record again
            ans = input("Record another command? (y/n): ").strip().lower()
            if ans != "y":
                print("Exiting.")
                break

        except KeyboardInterrupt:
            print("\n[INFO] Interrupted by user. Exiting.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            # Don’t crash the whole script on one failure
            ans = input("Error occurred. Try again? (y/n): ").strip().lower()
            if ans != "y":
                break


if __name__ == "__main__":
    main()
