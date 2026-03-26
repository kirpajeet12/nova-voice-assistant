# Nova — AI Voice Assistant for Mac

Nova is a voice-controlled AI assistant that runs locally on your Mac. It listens for a wake word, understands natural language, speaks back using ElevenLabs, and controls your Mac — Spotify, WhatsApp, Calendar, Notes, Email, and more.

---

## What Nova Can Do

| Feature | Example Command |
|---|---|
| Play Spotify | "play blinding lights" |
| Pause / Next / Prev | "pause", "next song" |
| Random music | "play random music" |
| Open apps | "open Safari" |
| Open websites | "open youtube" |
| Search YouTube | "search YouTube for cooking videos" |
| Set volume | "volume up", "set volume to 50" |
| Mute / Unmute | "mute", "unmute" |
| Send WhatsApp | "text John I'll be late" |
| Send email | "email Sarah about the meeting" |
| Create a note | "save a note buy groceries" |
| Add calendar event | "add dentist tomorrow at 3pm" |
| Delete calendar event | "delete dentist from calendar" |
| Set reminder | "remind me to call dad at 6pm" |
| Set timer | "set a 10 minute timer" |
| Weather | "what's the weather" |
| Type text | "type hello world" |
| Show notification | "notify me meeting in 5 minutes" |

---

## Requirements

- macOS (uses AppleScript — Mac only)
- Python 3.9 or higher
- Microphone
- Internet connection (for Claude API + ElevenLabs)

---

## Setup

### 1. Clone / Download the project

```bash
cd ~/Documents
git clone <your-repo-url> AI_BOT
cd AI_BOT/files
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API keys

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

Open `.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...         # Required — Nova's brain
ELEVENLABS_API_KEY=...               # Required — Nova's voice
ELEVENLABS_VOICE_ID=...              # Required — which voice to use
SPOTIFY_CLIENT_ID=...                # Optional — for reliable Spotify search
SPOTIFY_CLIENT_SECRET=...            # Optional — for reliable Spotify search
```

### 4. Give Terminal microphone access

Go to **System Settings → Privacy & Security → Microphone** and enable it for Terminal (or your IDE).

### 5. Run Nova

```bash
python3 main.py
```

---

## Getting Your API Keys

### Anthropic (Claude) — Brain
1. Go to console.anthropic.com
2. Create account → API Keys → Create Key
3. Paste into `ANTHROPIC_API_KEY`

### ElevenLabs — Voice
1. Go to elevenlabs.io
2. Create account → Profile → API Key
3. Paste into `ELEVENLABS_API_KEY`
4. Go to Voices → pick a voice → copy Voice ID
5. Paste into `ELEVENLABS_VOICE_ID`

### Spotify (Optional) — More reliable music search
1. Go to developer.spotify.com/dashboard
2. Create App → copy Client ID and Client Secret
3. Paste into `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`
4. Without these, Nova still works but uses keyboard navigation to search

---

## How It Works

```
You speak
    ↓
Whisper (local) transcribes your voice
    ↓
Wake word check ("Hey Claude")
    ↓
Claude Haiku processes your command
    ↓
Nova executes action on Mac (AppleScript / keyboard)
    ↓
ElevenLabs speaks the response back
```

### LLM Options

By default Nova uses **Claude API**. To switch to local Ollama (free, offline):

In `agent.py` line 19:
```python
USE_OLLAMA = True          # uses Ollama locally
USE_OLLAMA = False         # uses Claude API (default)
```

If using Ollama, make sure it's running and you have a model pulled:
```bash
ollama pull gemma3:4b
ollama serve
```

---

## File Structure

```
files/
├── main.py               # Entry point — mic, wake word, input loop
├── agent.py              # LLM brain + ElevenLabs voice
├── mac_control.py        # All Mac actions (Spotify, apps, volume, etc.)
├── communications.py     # WhatsApp, email, calendar, reminders
├── screen_vision.py      # Vision AI (screenshot → action)
├── config.py             # Loads API keys from .env
├── system_prompt.txt     # Nova's personality and action tags
├── voice.py              # Voice utilities
├── contacts.json         # Saved contacts cache
├── conversation_history.json  # Memory across sessions
├── requirements.txt      # Python dependencies
├── .env                  # Your API keys (never share this)
└── .env.example          # Template for .env
```

---

## Contacts (WhatsApp)

Nova looks up contacts automatically from your Mac Contacts app (synced from iPhone).

To manually add a contact, edit `contacts.json`:

```json
{
  "john": "+919876543210",
  "mom": "+919876543211"
}
```

Phone numbers must include country code (e.g. +91 for India, +1 for US).

---

## Troubleshooting

**Nova doesn't hear me**
- Check mic permission: System Settings → Privacy → Microphone → Terminal ✓
- Try speaking louder or closer to mic
- Adjust `SILENCE_THRESH` in `main.py` — lower = more sensitive (default: 1200)

**Stuck after `[elevenlabs] speaking...`**
- Already fixed — uses `afplay` now
- If issue persists, check ElevenLabs API key is valid

**PortAudio error on startup**
- Don't use Ctrl+Z to stop Nova — always use Ctrl+C
- Ctrl+Z suspends but keeps mic locked, causing errors on restart

**Spotify not playing**
- Add Spotify API keys to `.env` for reliable playback
- Without keys, Nova uses keyboard navigation (may vary by Spotify version)

**WhatsApp message not sending**
- Make sure WhatsApp desktop app is installed and logged in
- Contact must exist in Mac Contacts app or `contacts.json`

**Calendar events not saving**
- Open Calendar app at least once and set up an account
- Default calendar must be set in Calendar → Settings

---

## Wake Words

Default: `"Hey Claude"` (also responds to "hey claud", "hey cloud")

To change wake words, edit `main.py` line 20:
```python
WAKE_WORDS = ["hey claude", "hey nova", "hey assistant"]
```

---

## Privacy

- Voice is transcribed **locally** using Whisper (never sent anywhere)
- Commands are sent to Claude API (Anthropic) — see their privacy policy
- ElevenLabs receives text to speak (see their privacy policy)
- Your `.env` file contains sensitive keys — never share it or commit it to Git
