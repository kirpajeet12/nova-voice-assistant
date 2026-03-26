import whisper
import pyaudio
import numpy as np
from config import WHISPER_MODEL

print(f"Loading Whisper model ({WHISPER_MODEL})...")
model = whisper.load_model(WHISPER_MODEL)
print("Whisper ready.")

SAMPLE_RATE = 16000
CHUNK = 1024
CHANNELS = 1
FORMAT = pyaudio.paInt16
SILENCE_THRESH = 800  # higher = less sensitive to background noise

WAKE_WORDS = ["hey claude", "hey claud", "hey cloud", "he claude"]

_pa = pyaudio.PyAudio()
_listening = True

def set_listening(state: bool):
    global _listening
    _listening = state

def _record_chunk(duration: float) -> np.ndarray:
    stream = _pa.open(format=FORMAT, channels=CHANNELS,
                      rate=SAMPLE_RATE, input=True,
                      frames_per_buffer=CHUNK)
    frames = []
    for _ in range(int(SAMPLE_RATE / CHUNK * duration)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(np.frombuffer(data, dtype=np.int16))
    stream.stop_stream()
    stream.close()
    return np.concatenate(frames).astype(np.float32) / 32768.0

def _has_speech(audio: np.ndarray) -> bool:
    return np.sqrt(np.mean(audio ** 2)) * 32768 > SILENCE_THRESH

def _transcribe(audio: np.ndarray) -> str:
    result = model.transcribe(audio, fp16=False, language="en")
    return result["text"].strip().lower()

def listen_for_wake_word() -> str:
    while True:
        if not _listening:
            import time; time.sleep(0.1)
            continue
        audio = _record_chunk(duration=2.0)
        if not _has_speech(audio):
            continue
        text = _transcribe(audio)
        print(f"  [listening] heard: '{text}'")
        for w in WAKE_WORDS:
            if w in text:
                # command in same sentence?
                remainder = text.replace(w, "").strip(" ,?.!")
                if len(remainder) > 3:
                    print(f"  [inline command]: '{remainder}'")
                    return remainder
                return ""

def record_command(duration: float = 4.0) -> str:
    print("  [recording command...]")
    audio = _record_chunk(duration=duration)
    text = _transcribe(audio)
    print(f"  [command] '{text}'")
    return text