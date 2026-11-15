# Security Findings — Nova Voice Assistant

Generated: automated security review

---

## Critical

### 1. Arbitrary AppleScript Execution via LLM Output (`mac_control.py:400-401`)
The `[RUN: ...]` tag passes LLM-generated text **directly** into `run_applescript()` with no content filtering.
If the Claude API is compromised, or a user crafts an adversarial prompt that causes the LLM to emit a
`[RUN: ...]` tag with a destructive payload (e.g. `do shell script "rm -rf ~"`), the host Mac executes it
immediately — with no confirmation gate.

**Fix:** Restrict `[RUN: ...]` to a known allowlist of safe AppleScript templates, or remove the tag
entirely and replace with explicit named actions.

---

### 2. Incomplete URL Encoding in WhatsApp URL Scheme (`communications.py:120-121`)
The outgoing message is only partially encoded:
```python
encoded_msg = message.replace(" ", "%20").replace("\n", "%0A")
url = f"whatsapp://send?phone={phone}&text={encoded_msg}"
```
Characters like `&`, `?`, `#`, `+` are **not** encoded. A message containing `&phone=...` would inject
extra URL parameters and could redirect the message to an attacker-controlled number.

**Fix:** Use `urllib.parse.quote(message, safe='')`.

---

## High

### 3. TOCTOU Race Condition with `tempfile.mktemp()` (`screen_vision.py:28`)
`tempfile.mktemp()` returns a name without creating the file, leaving a window between name generation and
`screencapture` writing to it. A local attacker can place a symlink at that path to redirect the screenshot
to an arbitrary file (symlink attack).

**Fix:** Replace with `tempfile.mkstemp()`:
```python
fd, path = tempfile.mkstemp(suffix=".png")
os.close(fd)
subprocess.run(["screencapture", "-x", path])
```

---

### 4. No URL Scheme Validation in `open_url()` (`mac_control.py:62-64`)
Only presence of `"http"` is checked:
```python
if not url.startswith("http"):
    url = "https://" + url
```
URLs like `javascript:...`, `file:///etc/passwd`, or `data:...` pass through once they start with `http`.
These are served to AppleScript's `open location` and may execute in browsers.

**Fix:** Validate that the URL starts with `https://` or `http://` and reject other schemes.

---

### 5. Inconsistent AppleScript Sanitization (`mac_control.py:25-26` vs `communications.py:14-15`)
`communications.py._s()` escapes `\`, `"`, and `'`. `mac_control.py._s()` escapes only `\` and `"`.
Single quotes in app names or user-supplied text passed through the `mac_control._s()` function can break
out of AppleScript string literals and inject arbitrary commands.

**Fix:** Align both `_s()` functions to escape `\`, `"`, and `'`.

---

## Medium

### 6. No Phone Number Validation (`communications.py:111-117`, `main.py:103-104`)
Phone numbers provided by voice/text are accepted raw, stored in `contacts.json`, and embedded in a
`whatsapp://` URL with no format validation. Malformed or adversarial input (e.g. a number containing
`&text=INJECTED_MSG`) is silently stored and used.

**Fix:** Validate that the phone string matches `^\+?[0-9]{7,15}$` before saving/using.

---

### 7. Race Condition on `_listening` Flag (`main.py:31,87,107,...`)
`_listening` is a plain Python `bool` read and written from the main thread and potentially the voice input
thread without a lock. Under CPython's GIL this is usually safe in practice, but it's formally a data race
and can misbehave if the threading model changes.

**Fix:** Use `threading.Event` instead of a bare boolean flag.

---

### 8. Unbounded Conversation History Growth (`agent.py:35-45`)
`_save_history()` appends every exchange to `conversation_history.json` and `history` list indefinitely.
On long-running sessions this will exhaust memory and disk space, and also sends an ever-growing context
to the LLM, increasing latency and cost.

**Fix:** Cap the in-memory list (e.g. last 50 turns) and truncate the JSON file accordingly.

---

## Low

### 9. Bare `except:` Silently Swallowing Errors (`mac_control.py:99`, others)
Several `except:` blocks (without a specific exception type) silently discard failures, including
potential `KeyboardInterrupt` and `SystemExit`, making debugging impossible.

**Fix:** Catch `Exception as e` and log the error at minimum.

---

### 10. Hardcoded Country Code Assumption (`communications.py:88`)
Phone numbers without a leading `+` are prefixed with `+91` (India). This silently corrupts phone numbers
for users outside India.

**Fix:** Make the default country code a configurable setting in `assistant_config.json`.

---

### 11. API Keys May Appear in Error Logs (`agent.py:106-131`)
When ElevenLabs or the Anthropic client raises an exception, the printed traceback may include headers or
request metadata that expose API keys depending on the HTTP library's error formatting.

**Fix:** Catch specific request exceptions and log only sanitized error messages, never raw exception
objects from HTTP calls.
