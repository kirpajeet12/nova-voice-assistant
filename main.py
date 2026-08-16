#!/usr/bin/env python3
import time
import threading
import queue
import pyaudio
import numpy as np
import whisper
from config import WHISPER_MODEL
from setup_wizard import run_setup
_cfg = run_setup()
from agent import think, speak, load_history, ASSISTANT_NAME

# Shared queue — both voice and text input feed into this
_input_queue = queue.Queue()

# ── Audio setup ───────────────────────────
SAMPLE_RATE    = 16000
CHUNK          = 1024
SILENCE_THRESH = 1200  # balanced — filters background noise but picks up normal speech
CHUNK_SECS     = 3

_wake_base  = _cfg.get("wake_word", "hey nova")
WAKE_WORDS  = [_wake_base, _wake_base.replace(" ", "")]
SLEEP_AFTER = 20   # seconds of silence before going back to sleep

print(f"Loading Whisper ({WHISPER_MODEL})...")
_model = whisper.load_model(WHISPER_MODEL)
_pa    = pyaudio.PyAudio()
print("Ready.")

_listening = True   # pause mic while speaking

def _record(duration: float) -> np.ndarray:
    if not _listening:
        return np.zeros(1)
    stream = _pa.open(format=pyaudio.paInt16, channels=1,
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
    return _model.transcribe(audio, fp16=False, language="en")["text"].strip().lower()

def _wake_word(text: str):
    for w in WAKE_WORDS:
        if w in text:
            return text.replace(w, "").strip(" ,?.!")
    return None

CONFIRM_WORDS = ["yes", "yeah", "yep", "sure", "go ahead", "do it", "send it", "confirm", "ok", "okay"]
CANCEL_WORDS  = ["no", "nope", "cancel", "stop", "don't", "abort", "nevermind", "never mind"]

_pending_action = None   # stores (reply_with_tags, spoken_preview) when waiting for confirm

def _needs_confirmation(text: str) -> bool:
    """Check if agent reply contains a sensitive tag that needs confirmation."""
    if "[READ_WHATSAPP:" in text:
        return False   # reading never needs confirmation
    # [RUN:] executes arbitrary AppleScript so it must always be confirmed.
    sensitive = ["[WHATSAPP:", "[EMAIL:", "[DRAFT_EMAIL:", "[RUN:"]
    return any(tag in text for tag in sensitive)

def _preview(raw_reply: str) -> str:
    """Extract a human-readable preview of what's about to happen."""
    import re
    parts = []
    m = re.search(r'\[WHATSAPP:\s*([^|]+)\|([^\]]+)\]', raw_reply)
    if m:
        parts.append(f"send WhatsApp to {m.group(1).strip()}: \"{m.group(2).strip()}\"")
    m = re.search(r'\[EMAIL:\s*([^|]+)\|([^|]+)', raw_reply)
    if m:
        parts.append(f"send email to {m.group(1).strip()} about \"{m.group(2).strip()}\"")
    m = re.search(r'\[DRAFT_EMAIL:\s*([^|]+)\|([^|]+)', raw_reply)
    if m:
        parts.append(f"draft email to {m.group(1).strip()} about \"{m.group(2).strip()}\"")
    return " and ".join(parts) if parts else "do that"

def handle(command: str, source: str = "voice"):
    global _listening, _pending_action, awake, last_spoke

    if not command or len(command) < 3:
        return

    cmd_lower = command.lower().strip()

    # ── Handle pending confirmation ────────
    if _pending_action:
        raw_reply, preview = _pending_action

        # Handle phone number collection for unknown contacts
        if isinstance(raw_reply, dict) and raw_reply.get("type") == "need_phone":
            contact_name = raw_reply["contact"]
            pending_msg  = raw_reply["message"]
            from communications import _save_contact, send_whatsapp
            phone = command.strip().replace(" ", "")
            _save_contact(contact_name, phone)
            _pending_action = None
            result = send_whatsapp(contact_name, pending_msg)
            _listening = False
            speak(result if "NEED_PHONE" not in result else "Something went wrong.")
            time.sleep(1.5)
            _listening = True
            return

        if any(w in cmd_lower for w in CONFIRM_WORDS):
            _pending_action = None
            print(f"  [confirmed] executing action")
            from mac_control import parse_and_execute
            clean = parse_and_execute(raw_reply)

            # Handle unknown contact flow
            if isinstance(clean, str) and clean.startswith("NEED_PHONE:"):
                contact_name = clean.replace("NEED_PHONE:", "").strip()
                import re as _re
                m = _re.search(r'\[WHATSAPP:\s*[^|]+\|([^\]]+)\]', raw_reply)
                pending_msg = m.group(1).strip() if m else ""
                _pending_action = {"type": "need_phone", "contact": contact_name, "message": pending_msg}
                _listening = False
                speak(f"I don't have {contact_name}'s number. What is it?")
                time.sleep(1.5)
                _listening = True
                return

            spoken = clean if clean else "done!"
            _listening = False
            speak(spoken)
            time.sleep(1.5)
            _listening = True
        elif any(w in cmd_lower for w in CANCEL_WORDS):
            _pending_action = None
            print(f"  [cancelled]")
            _listening = False
            speak("got it, cancelled.")
            time.sleep(1.0)
            _listening = True
        else:
            # Not a yes/no — treat as new command, clear pending
            _pending_action = None
            handle(command, source)
        return

    # ── Normal command ─────────────────────
    print(f"  [{source}] '{command}'")
    raw_reply = think(command, skip_execute=_needs_confirmation)

    if raw_reply and _needs_confirmation(raw_reply):
        preview = _preview(raw_reply)
        _pending_action = (raw_reply, preview)
        confirm_msg = f"should I {preview}?"
        print(f"  [confirm?] {confirm_msg}")
        _listening = False
        speak(confirm_msg)
        time.sleep(1.5)
        _listening = True
    elif raw_reply:
        _listening = False
        speak(raw_reply)
        time.sleep(1.5)
        _listening = True

# ── Text input thread ─────────────────────
def _text_input_loop():
    while True:
        try:
            line = input()
            if line.strip():
                _input_queue.put(("text", line.strip()))
        except EOFError:
            break

threading.Thread(target=_text_input_loop, daemon=True).start()

# ── Voice input loop ──────────────────────
def _voice_loop():
    global awake, last_spoke
    while True:
        audio = _record(CHUNK_SECS)

        if not _has_speech(audio):
            if awake and (time.time() - last_spoke) > SLEEP_AFTER:
                print("  [sleeping]")
                awake = False
            continue

        text = _transcribe(audio)
        if not text:
            continue

        print(f"  [heard] '{text}'")

        if not awake:
            inline = _wake_word(text)
            if inline is not None:
                awake      = True
                last_spoke = time.time()
                if len(inline) > 3:
                    _input_queue.put(("voice", inline))
                else:
                    _input_queue.put(("voice", "__wake__"))
        else:
            inline  = _wake_word(text)
            command = inline if (inline and len(inline) > 3) else text
            last_spoke = time.time()
            _input_queue.put(("voice", command))

# ── Main loop ─────────────────────────────
load_history()
print("=" * 40)
print(f"  {ASSISTANT_NAME} — Ready")
print(f"  Say '{_cfg.get('wake_word', 'Hey Nova')}' or type below")
print("=" * 40)

awake      = False
last_spoke = 0.0

threading.Thread(target=_voice_loop, daemon=True).start()

while True:
    try:
        source, command = _input_queue.get(timeout=1)
    except queue.Empty:
        continue

    if command == "__wake__":
        _listening = False
        speak("Yeah?")
        time.sleep(0.8)
        _listening = True
        awake = True
        last_spoke = time.time()
    else:
        awake      = True
        last_spoke = time.time()
        handle(command, source)
