#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ClientTools, ConversationInitiationData
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from mac_control import (
    open_app, quit_app, open_url,
    set_volume, mute, unmute,
    play_spotify, spotify_pause, spotify_next, spotify_prev,
    send_email, draft_email,
    show_notification, type_text,
    take_screenshot, lock_screen, sleep_mac,
    parse_and_execute
)

load_dotenv()
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
AGENT_ID           = os.getenv("ELEVENLABS_AGENT_ID", "")

with open(os.path.join(os.path.dirname(__file__), "system_prompt.txt")) as f:
    SYSTEM_PROMPT = f.read()

client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
client_tools = ClientTools()
 
# ── Register all tools ───────────────────
 
client_tools.register("open_app",
    lambda p: (open_app(p["name"]), "Opened")[1])
 
client_tools.register("quit_app",
    lambda p: (quit_app(p["name"]), "Closed")[1])
 
client_tools.register("open_url",
    lambda p: (open_url(p["url"]), "Opened in browser")[1])
 
client_tools.register("set_volume",
    lambda p: (set_volume(int(p["level"])), "Volume set")[1])
 
client_tools.register("mute",
    lambda p: (mute(), "Muted")[1])
 
client_tools.register("unmute",
    lambda p: (unmute(), "Unmuted")[1])
 
client_tools.register("play_spotify",
    lambda p: (play_spotify(p.get("song", "")), "Playing on Spotify")[1])
 
client_tools.register("spotify_pause",
    lambda p: (spotify_pause(), "Paused")[1])
 
client_tools.register("spotify_next",
    lambda p: (spotify_next(), "Next track")[1])
 
client_tools.register("spotify_prev",
    lambda p: (spotify_prev(), "Previous track")[1])
 
client_tools.register("send_email",
    lambda p: (send_email(p["to"], p["subject"], p["body"]), "Email sent")[1])
 
client_tools.register("draft_email",
    lambda p: (draft_email(p["to"], p["subject"], p["body"]), "Email drafted, please review")[1])
 
client_tools.register("notify",
    lambda p: (show_notification("Claude", p["message"]), "Notification sent")[1])
 
client_tools.register("type_text",
    lambda p: (type_text(p["text"]), "Typed")[1])
 
client_tools.register("screenshot",
    lambda p: (take_screenshot(), "Screenshot saved to Desktop")[1])
 
client_tools.register("lock_screen",
    lambda p: (lock_screen(), "Screen locked")[1])
 
client_tools.register("sleep_mac",
    lambda p: (sleep_mac(), "Mac going to sleep")[1])
 
# ── Start conversation ────────────────────
 
conversation = Conversation(
    client=client,
    agent_id=AGENT_ID,
    requires_auth=True,
    audio_interface=DefaultAudioInterface(),
    client_tools=client_tools,
    callback_agent_response=lambda r: (parse_and_execute(r), print(f"  [claude]: {r}")),
    callback_user_transcript=lambda t: print(f"  [you]: {t}"),
)
 
print("=" * 40)
print("  Claude Agent — Ready")
print("  Speak to start...")
print("=" * 40)
 
conversation.start_session()
 