# ─────────────────────────────────────────
#  Claude Agent — Brain + Voice Output
# ─────────────────────────────────────────

import requests
import pygame
import tempfile
import os
import json
from datetime import datetime
from config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID

from setup_wizard import run_setup, build_system_prompt
_cfg = run_setup()
SYSTEM_PROMPT = build_system_prompt(_cfg)
ASSISTANT_NAME = _cfg.get("name", "Nova")
from mac_control import parse_and_execute, get_weather, search_spotify

# ── LLM backend — switch here ─────────────
USE_OLLAMA   = False         # False = use Claude API
OLLAMA_MODEL = "gemma3:4b"   # change to any model you have: llama3.2, mistral, etc.
OLLAMA_URL   = "http://localhost:11434/api/chat"

if not USE_OLLAMA:
    import anthropic
    from config import ANTHROPIC_API_KEY
    _claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Conversation memory (persists during session)
history = []

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "conversation_history.json")


def _save_history():
    data = {"updated": datetime.now().isoformat(), "messages": history}
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            data = json.load(f)
        history.extend(data.get("messages", []))
        print(f"  [memory] loaded {len(history)} messages from previous session")


_WEATHER_WORDS = ("weather", "temperature", "forecast", "hot", "cold", "raining", "sunny", "humid")
_SPOTIFY_WORDS = ("play", "song", "music", "spotify", "track", "listen")

_TAG_STRIP_RE = __import__('re').compile(r'\[[A-Z_]+[:\]].*?(?=\])\]', re.DOTALL)

def _sanitize_external(text: str) -> str:
    """Strip action-tag patterns from externally fetched data to prevent prompt injection."""
    return _TAG_STRIP_RE.sub('', text)

def think(user_input: str, skip_execute=None) -> str:
    """Send user message to LLM, return response text + execute Mac actions."""
    augmented = user_input
    if any(w in user_input.lower() for w in _WEATHER_WORDS):
        weather = _sanitize_external(get_weather())
        augmented = f"{user_input}\n\n[Live weather data: {weather}]"

    # Spotify search — find top result via API and play directly, no confirmation
    if any(w in user_input.lower() for w in _SPOTIFY_WORDS):
        import re as _re
        query = _re.sub(r'(play|song|music|spotify|track|listen|on|can you|please|the)', '', user_input, flags=_re.I).strip()
        if query:
            results = search_spotify(query, limit=1)
            if results:
                t = results[0]
                safe_name   = _sanitize_external(t['name'])
                safe_artist = _sanitize_external(t['artist'])
                safe_uri    = t['uri'] if t['uri'].startswith('spotify:') else ''
                if safe_uri:
                    augmented += f"\n\n[Spotify search result: '{safe_name}' by {safe_artist} — uri: {safe_uri}]"
                    augmented += f"\nPlay it immediately using [SPOTIFY_URI: {safe_uri}]. Do NOT ask for confirmation."

    history.append({"role": "user", "content": augmented})

    if USE_OLLAMA:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        res = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False
        }, timeout=60)
        data = res.json()
        if "error" in data:
            print(f"  [ollama error] {data['error']}")
            return "Sorry, I ran into an issue with the local model."
        raw_reply = data["message"]["content"]
    else:
        response = _claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=history
        )
        raw_reply = response.content[0].text

    # If caller wants to handle execution (e.g. after confirmation), skip it here
    if skip_execute and skip_execute(raw_reply):
        history.append({"role": "assistant", "content": raw_reply})
        _save_history()
        return raw_reply   # return raw so caller can execute after confirm

    clean_reply = parse_and_execute(raw_reply)
    history.append({"role": "assistant", "content": raw_reply})
    _save_history()
    print(f"\nAgent: {clean_reply}\n")
    return clean_reply


def speak(text: str):
    """Text to speech — ElevenLabs if key set, otherwise Mac built-in."""
    if not text:
        return

    # Use ElevenLabs if configured
    if ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
            res = requests.post(url,
                json={"text": text, "model_id": "eleven_monolingual_v1",
                      "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
                headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
                timeout=10
            )
            if res.status_code == 200:
                print(f"  [elevenlabs] speaking...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                    f.write(res.content)
                    tmp = f.name
                import subprocess as _sp
                _sp.run(["afplay", tmp])
                os.unlink(tmp)
                return
        except Exception as e:
            print(f"  [elevenlabs error] {e} — falling back to local TTS")

    # Fallback: Mac built-in TTS (fully local, no API needed)
    # Change voice with: say -v "Samantha" or "Alex" or "Daniel"
    import subprocess
    subprocess.run(["say", "-v", "Samantha", "-r", "180", text])


def clear_history():
    """Reset conversation memory."""
    history.clear()