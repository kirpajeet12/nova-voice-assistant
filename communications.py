#!/usr/bin/env python3
# ─────────────────────────────────────────
#  Communications — WhatsApp, Email, Calendar, Reminders
# ─────────────────────────────────────────

import subprocess
import time
import re
import os
import json
from datetime import datetime, timedelta
from urllib.parse import quote


def _s(text: str) -> str:
    return text.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")


def _run(script: str) -> dict:
    try:
        r = subprocess.run(['osascript', '-e', script],
                           capture_output=True, text=True, timeout=20)
        return {'ok': r.returncode == 0, 'output': r.stdout.strip(), 'error': r.stderr.strip()}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def _run_file(script: str) -> dict:
    """Write script to temp file and run — more reliable for multi-step automation."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.scpt', delete=False) as f:
        f.write(script)
        path = f.name
    try:
        r = subprocess.run(['osascript', path],
                           capture_output=True, text=True, timeout=30)
        return {'ok': r.returncode == 0, 'output': r.stdout.strip(), 'error': r.stderr.strip()}
    except Exception as e:
        return {'ok': False, 'error': str(e)}
    finally:
        os.unlink(path)


# ── WHATSAPP ──────────────────────────────

CONTACTS_FILE = os.path.join(os.path.dirname(__file__), "contacts.json")

def _load_contacts() -> dict:
    if os.path.exists(CONTACTS_FILE):
        with open(CONTACTS_FILE) as f:
            return json.load(f)
    return {}

def _save_contact(name: str, phone: str):
    contacts = _load_contacts()
    contacts[name.lower()] = phone
    with open(CONTACTS_FILE, "w") as f:
        json.dump(contacts, f, indent=2)
    print(f"  [contacts] saved {name} → {phone}")

def _lookup_mac_contacts(name: str) -> str:
    """Search Mac Contacts app for a phone number by name."""
    script = f'''
tell application "Contacts"
    set results to every person whose name contains "{_s(name)}"
    if length of results is 0 then
        -- try first name only
        set nameParts to words of "{_s(name)}"
        if length of nameParts > 0 then
            set results to every person whose first name contains item 1 of nameParts
        end if
    end if
    if length of results > 0 then
        set p to item 1 of results
        if (count of phones of p) > 0 then
            return value of item 1 of phones of p
        end if
    end if
    return ""
end tell
'''
    result = _run(script)
    phone = result.get("output", "").strip()
    if phone:
        # Normalize: remove spaces, dashes, brackets
        import re as _re
        phone = _re.sub(r'[\s\-\(\)]', '', phone)
        if not phone.startswith('+'):
            phone = '+91' + phone.lstrip('0')  # default country code — change if needed
        print(f"  [contacts] found {name} → {phone}")
    return phone

def _find_contact(name: str) -> str:
    """Find phone: check local contacts.json first, then Mac Contacts app."""
    # 1. Check local saved contacts
    contacts = _load_contacts()
    name_lower = name.lower().strip()
    if name_lower in contacts:
        return contacts[name_lower]
    for saved_name, phone in contacts.items():
        if name_lower in saved_name or saved_name in name_lower:
            return phone

    # 2. Search Mac Contacts app (synced with iPhone)
    phone = _lookup_mac_contacts(name)
    if phone:
        _save_contact(name, phone)  # cache it for next time
        return phone

    return ""

def send_whatsapp(contact: str, message: str):
    print(f"  [whatsapp] → {contact}: {message[:40]}...")
    phone = _find_contact(contact)

    if not phone:
        print(f"  [whatsapp] contact '{contact}' not found in contacts.json")
        return f"NEED_PHONE:{contact}"   # signal to main that we need the phone number

    # URL scheme — opens WhatsApp directly to the chat with message pre-filled
    encoded_phone = quote(phone, safe="+")
    encoded_msg   = quote(message, safe="")
    url = f"whatsapp://send?phone={encoded_phone}&text={encoded_msg}"

    script = f'''
tell application "WhatsApp" to activate
delay 0.5
open location "{url}"
delay 3
tell application "System Events"
    key code 36
end tell
'''
    result = _run_file(script)
    if result['ok']:
        print(f"  [whatsapp] sent to {contact} ({phone})")
        return f"Sent to {contact}!"
    else:
        print(f"  [whatsapp error] {result.get('error','')}")
        return "Couldn't send the message."


def read_whatsapp_messages(contact: str) -> str:
    """Try to read the last message from a contact via WhatsApp accessibility API."""
    print(f"  [whatsapp] reading messages from: {contact}")
    contact_safe = _s(contact)

    script = f'''
tell application "WhatsApp" to activate
delay 2

-- Open search to find the contact's chat
tell application "System Events"
    tell process "WhatsApp"
        -- Cmd+F to open search / new chat
        keystroke "f" using command down
        delay 1.2
        keystroke "{contact_safe}"
        delay 1.5
        -- Select first result
        key code 125
        delay 0.5
        key code 36
        delay 2.5

        -- Try to grab static text from the chat window
        set msgList to {{}}
        try
            set allItems to every static text of window 1
            repeat with itm in allItems
                set val to value of itm
                if val is not missing value and length of val > 5 then
                    set end of msgList to val
                end if
            end repeat
        end try

        set output to ""
        repeat with t in msgList
            set output to output & t & "|||"
        end repeat
        return output
    end tell
end tell
'''
    result = _run_file(script)
    raw = result.get("output", "").strip()

    if not raw:
        # Second attempt: try AXValue of scroll areas / text areas
        script2 = f'''
tell application "WhatsApp" to activate
delay 1
tell application "System Events"
    tell process "WhatsApp"
        try
            set sa to every text area of window 1
            set output to ""
            repeat with itm in sa
                set val to value of itm
                if val is not missing value then
                    set output to output & val & "|||"
                end if
            end repeat
            return output
        end try
        return ""
    end tell
end tell
'''
        result2 = _run_file(script2)
        raw = result2.get("output", "").strip()

    if not raw:
        return f"Opened WhatsApp chat with {contact}, but couldn't read messages automatically — WhatsApp blocks direct text access."

    # Filter: skip obvious UI labels (short strings, button names)
    skip = {"reply", "forward", "emoji", "sticker", "attach", "send", "search",
            "new chat", "settings", "calls", "chats", "status", "archived",
            "type a message", "mute", "block", "delete", "close", "back"}
    parts = [p.strip() for p in raw.split("|||") if p.strip()]
    msgs = [p for p in parts if len(p) > 8 and p.lower() not in skip and not p.lower().startswith("whatsapp")]

    if not msgs:
        return f"Couldn't extract message text from {contact}'s chat — WhatsApp may not expose it via accessibility."

    # Return last few meaningful lines
    last = msgs[-3:] if len(msgs) >= 3 else msgs
    return f"Last messages from {contact}: " + " | ".join(last)


# ── EMAIL ─────────────────────────────────

def send_email(to: str, subject: str, body: str):
    print(f"  [email] → {to} | {subject}")
    script = f'''tell application "Mail"
        activate
        set msg to make new outgoing message with properties {{subject:"{_s(subject)}", content:"{_s(body)}", visible:true}}
        tell msg
            make new to recipient with properties {{address:"{_s(to)}"}}
        end tell
        send msg
    end tell'''
    _run(script)
    return f"Email sent to {to}!"


def draft_email(to: str, subject: str, body: str):
    print(f"  [email draft] → {to} | {subject}")
    to_s      = _s(to)
    subject_s = _s(subject)
    body_s    = _s(body)
    script = f'''tell application "Mail"
        activate
        set msg to make new outgoing message with properties {{subject:"{subject_s}", content:"{body_s}", visible:true}}
        tell msg
            make new to recipient with properties {{address:"{to_s}"}}
        end tell
    end tell'''
    _run(script)
    return f"Email draft opened for {to} — please review before sending."


# ── CALENDAR ─────────────────────────────

def _parse_when(when: str) -> datetime:
    """Convert natural language like 'tomorrow', 'monday', 'next friday' to datetime."""
    when = when.lower().strip()
    now  = datetime.now().replace(second=0, microsecond=0)
    today = now.replace(hour=0, minute=0)

    if when in ("today", "tonight", ""):
        return today
    if when == "tomorrow":
        return today + timedelta(days=1)

    days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    if when in days:
        target = days.index(when)
        current = today.weekday()
        diff = (target - current) % 7 or 7
        return today + timedelta(days=diff)

    if when.startswith("next "):
        day = when[5:]
        if day in days:
            target = days.index(day)
            current = today.weekday()
            diff = (target - current) % 7 or 7
            return today + timedelta(days=diff)

    return today  # fallback to today


def _parse_time(time_str: str) -> tuple:
    """Parse '3pm', '14:00', '9:30am' → (hour, minute)"""
    time_str = time_str.lower().strip()
    try:
        if ":" in time_str:
            t = datetime.strptime(time_str.replace("am","").replace("pm","").strip(), "%H:%M")
            hour = t.hour
            if "pm" in time_str and hour < 12: hour += 12
            if "am" in time_str and hour == 12: hour = 0
            return hour, t.minute
        elif "am" in time_str or "pm" in time_str:
            num = int(re.sub(r'[^0-9]', '', time_str))
            hour = num % 12
            if "pm" in time_str: hour += 12
            return hour, 0
        else:
            return int(time_str) % 24, 0
    except:
        return 9, 0  # default 9am


def add_calendar_event(title: str, when: str = "today", time_str: str = "9am", duration_hours: float = 1.0):
    print(f"  [calendar] '{title}' on {when} at {time_str}")
    date     = _parse_when(when)
    hour, mn = _parse_time(time_str)
    start    = date.replace(hour=hour, minute=mn)
    end_secs = int(duration_hours * 3600)

    script = f'''
    tell application "Calendar"
        set startDate to current date
        set year of startDate to {start.year}
        set month of startDate to {start.month}
        set day of startDate to {start.day}
        set hours of startDate to {start.hour}
        set minutes of startDate to {start.minute}
        set seconds of startDate to 0
        set endDate to startDate + {end_secs}
        tell first calendar whose name is "Home"
            make new event with properties {{summary:"{_s(title)}", start date:startDate, end date:endDate}}
        end tell
        reload calendars
    end tell
    '''
    result = _run(script)
    if result['ok']:
        return f"Added '{title}' to Calendar on {when} at {time_str}!"
    else:
        return f"Couldn't add event: {result.get('error','unknown error')}"


# ── REMINDERS ────────────────────────────

def add_reminder(text: str, when: str = "today", time_str: str = "9am"):
    print(f"  [reminder] '{text}' — {when} {time_str}")
    date     = _parse_when(when)
    hour, mn = _parse_time(time_str)
    due      = date.replace(hour=hour, minute=mn)

    script = f'''
    tell application "Reminders"
        set dueDate to current date
        set year of dueDate to {due.year}
        set month of dueDate to {due.month}
        set day of dueDate to {due.day}
        set hours of dueDate to {due.hour}
        set minutes of dueDate to {due.minute}
        tell list "Reminders"
            make new reminder with properties {{name:"{_s(text)}", due date:dueDate}}
        end tell
    end tell
    '''
    result = _run(script)
    if result['ok']:
        return f"Reminder set: '{text}' for {when} at {time_str}!"
    else:
        return f"Couldn't set reminder: {result.get('error','unknown error')}"


# ── TIMER ────────────────────────────────

def set_timer(minutes: int):
    print(f"  [timer] {minutes} min")
    import threading
    def _fire():
        time.sleep(minutes * 60)
        _run(f'display notification "Time\'s up! {minutes} minute timer done." with title "Nova Timer" sound name "Glass"')
    threading.Thread(target=_fire, daemon=True).start()
    return f"Timer set for {minutes} minutes!"
