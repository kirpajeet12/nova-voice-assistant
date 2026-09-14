# ─────────────────────────────────────────
#  Claude Agent — Mac Control
#  Full control: apps, volume, email, music, files, browser
# ─────────────────────────────────────────

import re
import subprocess
import os
import requests as _requests
from communications import send_whatsapp, send_email, draft_email, add_calendar_event, add_reminder, set_timer


def get_weather(location: str = "") -> str:
    """Fetch current weather as plain text using wttr.in"""
    loc = location.strip().replace(" ", "+") or ""
    try:
        url = f"https://wttr.in/{loc}?format=3"
        r = _requests.get(url, timeout=8)
        return r.text.strip() if r.ok else "Couldn't fetch weather right now."
    except Exception as e:
        return f"Weather fetch failed: {e}"


def _s(text: str) -> str:
    """Sanitize a string for safe embedding inside an AppleScript string literal."""
    # Escape backslashes first, then double-quotes and single-quotes
    return text.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")


_BLOCKED_APPLESCRIPT_PATTERNS = [
    "do shell script",
    "load script",
    "run script",
    "path to",
]

def run_applescript(script: str) -> dict:
    # Block AppleScript constructs that allow arbitrary shell/file execution
    script_lower = script.lower()
    for pattern in _BLOCKED_APPLESCRIPT_PATTERNS:
        if pattern in script_lower:
            print(f"  [mac] blocked dangerous AppleScript pattern: {pattern!r}")
            return {'ok': False, 'error': f'Blocked AppleScript pattern: {pattern}'}
    try:
        r = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True, text=True, timeout=15
        )
        return {'ok': r.returncode == 0, 'output': r.stdout.strip(), 'error': r.stderr.strip()}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


# ── APPS ─────────────────────────────────

def open_app(name: str):
    import time
    print(f"  [mac] opening: {name}")
    run_applescript(f'tell application "{_s(name)}" to activate')
    # For document-based apps, create a new document automatically
    if name.lower() in ("pages", "keynote", "numbers", "textedit"):
        time.sleep(1.5)
        run_applescript('tell application "System Events" to keystroke "n" using command down')
        time.sleep(1.0)
    return {"ok": True}

def quit_app(name: str):
    print(f"  [mac] quitting: {name}")
    return run_applescript(f'tell application "{_s(name)}" to quit')


# ── BROWSER ──────────────────────────────

def open_url(url: str):
    print(f"  [mac] opening url: {url}")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    # Block non-http(s) schemes that could execute code or read local files
    from urllib.parse import urlparse
    scheme = urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        print(f"  [mac] blocked unsafe URL scheme: {scheme}")
        return {"ok": False, "error": f"Blocked unsafe URL scheme: {scheme}"}
    return run_applescript(f'open location "{_s(url)}"')


# ── VOLUME ───────────────────────────────

def set_volume(level: int):
    level = max(0, min(100, level))
    print(f"  [mac] volume: {level}")
    return run_applescript(f'set volume output volume {level}')

def mute():
    return run_applescript('set volume with output muted')

def unmute():
    return run_applescript('set volume without output muted')


# ── MUSIC / SPOTIFY ──────────────────────

def _spotify_token() -> str:
    import base64, os
    from dotenv import load_dotenv
    load_dotenv()
    client_id     = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    if not client_id or client_id == "your_client_id_here":
        return ""
    try:
        creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        res = _requests.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {creds}"},
            data={"grant_type": "client_credentials"}, timeout=8
        )
        return res.json().get("access_token", "")
    except:
        return ""

def search_spotify(query: str, limit: int = 3) -> list:
    """Search Spotify — returns list of {name, artist, uri}"""
    token = _spotify_token()
    if not token:
        return []
    try:
        res = _requests.get(
            "https://api.spotify.com/v1/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": query, "type": "track", "limit": limit},
            timeout=8
        )
        items = res.json().get("tracks", {}).get("items", [])
        return [{"name": t["name"], "artist": t["artists"][0]["name"], "uri": t["uri"]} for t in items]
    except Exception as e:
        print(f"  [spotify error] {e}")
        return []

def _get_spotify_uri(query: str) -> str:
    results = search_spotify(query, limit=1)
    if results:
        t = results[0]
        print(f"  [spotify] found: {t['name']} by {t['artist']}")
        return t["uri"]
    return ""


def play_spotify(song: str = ""):
    import time, tempfile, os as _os
    print(f"  [mac] spotify play: {song or 'resume'}")

    if not song:
        run_applescript('tell application "Spotify" to play')
        return

    # "random" → shuffle-play liked songs instead of searching the word "random"
    _random_words = {"random", "anything", "something", "shuffle", "surprise me", "whatever"}
    if song.lower().strip() in _random_words:
        import tempfile, os as _os2
        script = '''
tell application "Spotify" to activate
delay 1.5
-- Enable shuffle
tell application "Spotify"
    set shuffling to true
end tell
-- Navigate to Liked Songs
open location "spotify:collection"
delay 2.5
-- Tab to the Shuffle Play button and press it
tell application "System Events"
    key code 48
end tell
delay 0.3
tell application "System Events"
    key code 36
end tell
delay 0.5
-- Fallback: press Space in case focus missed the button
tell application "System Events"
    keystroke space
end tell
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.scpt', delete=False) as f:
            f.write(script)
            path = f.name
        try:
            subprocess.run(['osascript', path], capture_output=True, timeout=20)
        finally:
            _os2.unlink(path)
        return

    # Try Spotify API first (if keys are configured)
    uri = _get_spotify_uri(song)
    if uri:
        # Use open location to navigate directly to the track — more reliable than play track AppleScript
        script = f'''
tell application "Spotify" to activate
delay 1
open location "{uri}"
'''
        run_applescript(script)
        return

    # Keyboard-only fallback: search → full results → Tab to Best Result → Enter
    song_safe = _s(song)
    script = f'''
tell application "Spotify" to activate
delay 2

-- Focus search bar
tell application "System Events"
    keystroke "l" using command down
end tell
delay 1

-- Clear and type song name
tell application "System Events"
    keystroke "a" using command down
    delay 0.2
    keystroke "{song_safe}"
end tell
delay 2

-- Enter → go to full results page (avoids unpredictable dropdown)
tell application "System Events"
    key code 36
end tell
delay 3

-- Tab past all filter pills (All, Music, Audiobook, Album, Podcasts = 5)
-- Tab 6 lands on Best Result card
tell application "System Events"
    key code 48
end tell
delay 0.2
tell application "System Events"
    key code 48
end tell
delay 0.2
tell application "System Events"
    key code 48
end tell
delay 0.2
tell application "System Events"
    key code 48
end tell
delay 0.2
tell application "System Events"
    key code 48
end tell
delay 0.2
tell application "System Events"
    key code 48
end tell
delay 0.4

-- Enter to play Best Result
tell application "System Events"
    key code 36
end tell
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.scpt', delete=False) as f:
        f.write(script)
        path = f.name
    try:
        subprocess.run(['osascript', path], capture_output=True, timeout=20)
    finally:
        _os.unlink(path)

def spotify_pause():
    return run_applescript('tell application "Spotify" to pause')

def spotify_next():
    return run_applescript('tell application "Spotify" to next track')

def spotify_prev():
    return run_applescript('tell application "Spotify" to previous track')


# ── EMAIL (Apple Mail) ────────────────────

def send_email(to: str, subject: str, body: str):
    print(f"  [mac] sending email to: {to}")
    script = f'''tell application "Mail"
        activate
        set newMsg to make new outgoing message with properties {{subject:"{_s(subject)}", content:"{_s(body)}", visible:true}}
        tell newMsg
            make new to recipient with properties {{address:"{_s(to)}"}}
        end tell
        send newMsg
    end tell'''
    return run_applescript(script)

def draft_email(to: str, subject: str, body: str):
    print(f"  [mac] drafting email to: {to}")
    script = f'''tell application "Mail"
        activate
        set newMsg to make new outgoing message with properties {{subject:"{_s(subject)}", content:"{_s(body)}", visible:true}}
        tell newMsg
            make new to recipient with properties {{address:"{_s(to)}"}}
        end tell
    end tell'''
    return run_applescript(script)


# ── NOTIFICATIONS ─────────────────────────

def show_notification(title: str, message: str):
    print(f"  [mac] notify: {title} — {message}")
    return run_applescript(f'display notification "{_s(message)}" with title "{_s(title)}"')


# ── SYSTEM ───────────────────────────────

def get_frontmost_app() -> str:
    r = run_applescript('tell application "System Events" to get name of first application process whose frontmost is true')
    return r.get('output', 'unknown')

def type_text(text: str):
    print(f"  [mac] typing: {text[:40]}...")
    return run_applescript(f'tell application "System Events" to keystroke "{_s(text)}"')

def take_screenshot():
    path = os.path.expanduser("~/Desktop/screenshot.png")
    subprocess.run(['screencapture', '-x', path])
    print(f"  [mac] screenshot saved: {path}")
    return path

def create_note(text: str) -> str:
    print(f"  [mac] creating note: {text[:40]}...")
    safe = _s(text)
    script = f'''
tell application "Notes"
    activate
    set newNote to make new note with properties {{body:"{safe}"}}
    return name of newNote
end tell
'''
    result = run_applescript(script)
    return "Note saved!" if result['ok'] else "Couldn't save the note."


def delete_calendar_event(title: str) -> str:
    print(f"  [mac] deleting calendar event: {title}")
    safe = _s(title)
    script = f'''
tell application "Calendar"
    set found to false
    repeat with cal in calendars
        set matchEvents to (every event of cal whose summary contains "{safe}")
        if (count of matchEvents) > 0 then
            delete first item of matchEvents
            set found to true
            exit repeat
        end if
    end repeat
    if found then
        return "deleted"
    else
        return "not found"
    end if
end tell
'''
    result = run_applescript(script)
    if result.get('output') == 'deleted':
        return f"Deleted '{title}' from Calendar!"
    elif result.get('output') == 'not found':
        return f"Couldn't find '{title}' in Calendar."
    else:
        return "Something went wrong deleting the event."


def lock_screen():
    return run_applescript('tell application "System Events" to keystroke "q" using {command down, control down}')

def sleep_mac():
    return run_applescript('tell application "System Events" to sleep')


# ── TAG PARSER ───────────────────────────

def parse_and_execute(text: str) -> str:
    """
    Scan Claude's raw reply for control tags, execute each action,
    and return the reply with all tags stripped (clean text for TTS).

    Supported tags:
        [OPEN: AppName]
        [URL: https://...]
        [VOLUME: 50]
        [NOTIFY: Title|message]
        [RUN: applescript code]
        [TYPE: text to type]
    """

    def _open(m):
        open_app(m.group(1).strip())
        return ""

    def _url(m):
        open_url(m.group(1).strip())
        return ""

    def _volume(m):
        try:
            set_volume(int(m.group(1).strip()))
        except ValueError:
            pass
        return ""

    def _notify(m):
        parts = m.group(1).split("|", 1)
        title = parts[0].strip()
        msg   = parts[1].strip() if len(parts) > 1 else ""
        show_notification(title, msg)
        return ""

    def _type(m):
        type_text(m.group(1).strip())
        return ""

    def _note(m):
        result = create_note(m.group(1).strip())
        return result

    def _delete_calendar(m):
        result = delete_calendar_event(m.group(1).strip())
        return result

    def _spotify(m):
        play_spotify(m.group(1).strip())
        return ""

    def _spotify_pause(m):
        spotify_pause()
        return ""

    def _spotify_next(m):
        spotify_next()
        return ""

    def _spotify_prev(m):
        spotify_prev()
        return ""

    def _mute(m):
        mute()
        return ""

    def _unmute(m):
        unmute()
        return ""

    def _read_whatsapp(m):
        from communications import read_whatsapp_messages
        contact = m.group(1).strip()
        result = read_whatsapp_messages(contact)
        print(f"  [whatsapp read] {result}")
        return result

    def _whatsapp(m):
        parts = m.group(1).split("|", 1)
        contact = parts[0].strip()
        message = parts[1].strip() if len(parts) > 1 else ""
        send_whatsapp(contact, message)
        return ""

    def _email(m):
        parts = m.group(1).split("|")
        to      = parts[0].strip() if len(parts) > 0 else ""
        subject = parts[1].strip() if len(parts) > 1 else "Message"
        body    = parts[2].strip() if len(parts) > 2 else ""
        send_email(to, subject, body)
        return ""

    def _draft_email(m):
        parts = m.group(1).split("|")
        to      = parts[0].strip() if len(parts) > 0 else ""
        subject = parts[1].strip() if len(parts) > 1 else "Message"
        body    = parts[2].strip() if len(parts) > 2 else ""
        draft_email(to, subject, body)
        return ""

    def _calendar(m):
        parts = m.group(1).split("|")
        title    = parts[0].strip() if len(parts) > 0 else "Event"
        when     = parts[1].strip() if len(parts) > 1 else "today"
        time_str = parts[2].strip() if len(parts) > 2 else "9am"
        duration = float(parts[3].strip()) if len(parts) > 3 else 1.0
        add_calendar_event(title, when, time_str, duration)
        return ""

    def _reminder(m):
        parts    = m.group(1).split("|")
        text     = parts[0].strip() if len(parts) > 0 else "Reminder"
        when     = parts[1].strip() if len(parts) > 1 else "today"
        time_str = parts[2].strip() if len(parts) > 2 else "9am"
        add_reminder(text, when, time_str)
        return ""

    def _timer(m):
        try:
            set_timer(int(m.group(1).strip()))
        except:
            pass
        return ""

    text = re.sub(r'\[NOTE:\s*([^\]]+)\]',          _note,          text)
    text = re.sub(r'\[DELETE_CALENDAR:\s*([^\]]+)\]', _delete_calendar, text)
    text = re.sub(r'\[OPEN:\s*([^\]]+)\]',        _open,          text)
    text = re.sub(r'\[URL:\s*([^\]]+)\]',          _url,           text)
    text = re.sub(r'\[VOLUME:\s*([^\]]+)\]',       _volume,        text)
    text = re.sub(r'\[NOTIFY:\s*([^\]]+)\]',       _notify,        text)
    # [RUN:] tag removed — arbitrary AppleScript execution is a shell-injection risk
    text = re.sub(r'\[RUN:\s*([^\]]+)\]',          lambda m: "",   text)
    text = re.sub(r'\[TYPE:\s*([^\]]+)\]',         _type,          text)
    def _spotify_uri(m):
        uri = m.group(1).strip()
        run_applescript(f'''
tell application "Spotify" to activate
delay 1
open location "{uri}"
''')
        return ""

    text = re.sub(r'\[SPOTIFY_URI:\s*([^\]]+)\]',  _spotify_uri,   text)
    text = re.sub(r'\[SPOTIFY:\s*([^\]]+)\]',      _spotify,       text)
    text = re.sub(r'\[SPOTIFY_PAUSE\]',            _spotify_pause, text)
    text = re.sub(r'\[SPOTIFY_NEXT\]',             _spotify_next,  text)
    text = re.sub(r'\[SPOTIFY_PREV\]',             _spotify_prev,  text)
    text = re.sub(r'\[MUTE\]',                     _mute,          text)
    text = re.sub(r'\[UNMUTE\]',                   _unmute,        text)
    text = re.sub(r'\[READ_WHATSAPP:\s*([^\]]+)\]',  _read_whatsapp, text)
    text = re.sub(r'\[WHATSAPP:\s*([^\]]+)\]',     _whatsapp,      text)
    text = re.sub(r'\[EMAIL:\s*([^\]]+)\]',        _email,         text)
    text = re.sub(r'\[DRAFT_EMAIL:\s*([^\]]+)\]',  _draft_email,   text)
    text = re.sub(r'\[CALENDAR:\s*([^\]]+)\]',     _calendar,      text)
    text = re.sub(r'\[REMINDER:\s*([^\]]+)\]',     _reminder,      text)
    text = re.sub(r'\[TIMER:\s*([^\]]+)\]',        _timer,         text)

    return text.strip()
