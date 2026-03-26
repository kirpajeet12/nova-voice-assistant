#!/usr/bin/env python3
"""
Nova — Permission Setup
Run this once to grant Nova full Mac control.
"""
import subprocess
import sys

def check_accessibility():
    """Check if Terminal has Accessibility permission."""
    result = subprocess.run(
        ['osascript', '-e',
         'tell application "System Events" to get name of first process whose frontmost is true'],
        capture_output=True, text=True
    )
    return result.returncode == 0

def open_accessibility_settings():
    subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'])

def open_microphone_settings():
    subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone'])

def open_full_disk_settings():
    subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles'])


print("""
╔══════════════════════════════════════════╗
║         Nova — Permission Setup          ║
╚══════════════════════════════════════════╝

Nova needs 3 permissions to work fully.
Each one opens System Settings — just toggle Terminal ON.
""")

# 1. Accessibility
input("[ Step 1 / 3 ] Press Enter to open Accessibility settings...")
open_accessibility_settings()
print("""
   → Find 'Terminal' in the list
   → Toggle it ON
   → This lets Nova control apps (Spotify, WhatsApp, etc.)
""")

input("Done? Press Enter for next step...")

# 2. Microphone
input("[ Step 2 / 3 ] Press Enter to open Microphone settings...")
open_microphone_settings()
print("""
   → Find 'Terminal' in the list
   → Toggle it ON
   → This lets Nova hear your voice
""")

input("Done? Press Enter for next step...")

# 3. Full Disk Access (optional — for reading/writing files anywhere)
answer = input("[ Step 3 / 3 ] Give Nova Full Disk Access? (recommended) y/n: ").strip().lower()
if answer == 'y':
    open_full_disk_settings()
    print("""
   → Find 'Terminal' in the list
   → Toggle it ON
   → This lets Nova read/write files anywhere on your Mac
""")
    input("Done? Press Enter to continue...")

# Final check
print("\nChecking Accessibility permission...")
if check_accessibility():
    print("✅  Accessibility — granted")
else:
    print("❌  Accessibility — not granted yet (go back and toggle Terminal ON)")

print("""
══════════════════════════════════════════
  Setup complete! Run Nova with:
  python3 main.py
══════════════════════════════════════════
""")
