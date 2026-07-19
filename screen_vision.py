#!/usr/bin/env python3
# ─────────────────────────────────────────
#  Nova — Screen Vision
#  Takes screenshot → Claude Vision reads it → executes action
# ─────────────────────────────────────────

import os
import base64
import subprocess
import tempfile
import requests
import pyautogui
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────
USE_LOCAL_VISION = True        # True = Ollama (free, local), False = Claude API
VISION_MODEL     = "gemma3:4b" # already installed — supports vision
OLLAMA_URL       = "http://localhost:11434/api/chat"

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3


def take_screenshot() -> str:
    """Take screenshot and return path to PNG file."""
    # mktemp() is deprecated and has a TOCTOU race; use mkstemp instead.
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    subprocess.run(["screencapture", "-x", path])
    return path


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def see_and_act(instruction: str) -> str:
    """
    Take a screenshot, send to Claude Vision with an instruction,
    get back an action (click, type, scroll) and execute it.
    """
    print(f"  [vision] taking screenshot...")
    screenshot_path = take_screenshot()
    image_data = _encode_image(screenshot_path)
    os.unlink(screenshot_path)

    prompt = f"""You are controlling a Mac computer. Look at this screenshot and help with:
"{instruction}"

Respond with ONLY a JSON object — no explanation, no markdown:
{{
  "description": "what you see relevant to the task",
  "action": "click" | "double_click" | "type" | "scroll" | "none",
  "x": <screen x coordinate if clicking>,
  "y": <screen y coordinate if clicking>,
  "text": "<text to type if action is type>",
  "scroll_direction": "up" | "down" if action is scroll,
  "result": "what this action will accomplish"
}}

If you cannot find what's needed, set action to "none" and explain in description."""

    print(f"  [vision] analyzing screen with {VISION_MODEL}...")

    if USE_LOCAL_VISION:
        # Ollama local vision (gemma3:4b supports images)
        res = requests.post(OLLAMA_URL, json={
            "model": VISION_MODEL,
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": [image_data]
            }],
            "stream": False
        }, timeout=60)
        raw = res.json()["message"]["content"].strip()
    else:
        # Claude Vision API fallback
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_data}},
                {"type": "text", "text": prompt}
            ]}]
        )
        raw = response.content[0].text.strip()

    import json, re
    # Extract JSON even if wrapped in markdown
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        print(f"  [vision] no action found")
        return "I couldn't find that on screen."

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        print(f"  [vision] malformed JSON from model: {e}")
        return "I couldn't parse the vision response."

    action      = data.get("action", "none")
    description = data.get("description", "")
    result      = data.get("result", "")

    print(f"  [vision] {description}")
    print(f"  [vision] action: {action} → {result}")

    screen_w, screen_h = pyautogui.size()

    if action == "click":
        x, y = int(data.get("x", 0)), int(data.get("y", 0))
        if not (0 <= x <= screen_w and 0 <= y <= screen_h):
            print(f"  [vision] coordinates out of bounds ({x},{y}), skipping")
            return "Vision returned out-of-bounds coordinates."
        pyautogui.click(x, y)
    elif action == "double_click":
        x, y = int(data.get("x", 0)), int(data.get("y", 0))
        if not (0 <= x <= screen_w and 0 <= y <= screen_h):
            print(f"  [vision] coordinates out of bounds ({x},{y}), skipping")
            return "Vision returned out-of-bounds coordinates."
        pyautogui.doubleClick(x, y)
    elif action == "type":
        pyautogui.typewrite(data.get("text", ""), interval=0.05)
    elif action == "scroll":
        direction = 1 if data.get("scroll_direction") == "up" else -1
        pyautogui.scroll(direction * 3)
    elif action == "none":
        return description

    return result


def spotify_play_from_search() -> str:
    """After Spotify search results are shown, find and click the first song's play button."""
    return see_and_act(
        "In Spotify search results, find the first song in the 'Songs' section and click the Play button next to it"
    )


def whatsapp_find_and_open(contact: str) -> str:
    """Find a contact in WhatsApp search results and open their chat."""
    return see_and_act(
        f"In WhatsApp, find '{contact}' in the search results list and click on their name to open the chat"
    )
