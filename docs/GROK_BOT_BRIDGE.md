# Grok Bot bridge (version 61, optional)

AIBody has two ways to drive the AI character. Both stay in the app; you choose one in `config.json`:

| `ai.driver` | Who answers | Default |
|---|---|---|
| `direct` | the companion app's own AI (speech recognition -> Grok -> voice, or Grok Voice realtime), as up to version 60 | yes |
| `grok_bot` | Grok Bot (the desktop app on this computer, with local execution allowed) through a local bridge | no, opt-in |

Nothing of the direct method was removed. Switching back is one key (`"ai": {"driver": "direct"}`) and a restart of
the app, so the bridge can be rolled back at any time.

## What changes with `grok_bot`

- The app still listens (microphone, voice activity, speech recognition), still mutes on the mute words, still runs the
  pose commands and still speaks (text to speech, lip sync in VaM).
- It asks **no** language model and opens **no** realtime session; it sends no proactive nudges. What the user says
  and the scene events go into the bridge's event queue instead.
- Grok Bot reads that queue and answers with the remote control's actions (`/api/say`, `/api/expression`,
  `/api/gesture`, `/api/pose`, `/api/look`, `/api/stop`), see [REMOTE.md](REMOTE.md).
- The bridge is the remote control's HTTP API: 127.0.0.1 only, token required. Without `remote.enabled` (or without a
  valid token) `grok_bot` falls back to `direct`, and the console says so.

## Switch it on

By hand: in `<VaM>/Saves/PluginData/AIBody/config.json` set

```json
"ai": { "driver": "grok_bot" },
"remote": { "enabled": true }
```

(keep the other keys) and restart AIBody Companion; it writes a token into `remote.token` on that start. Or tick
**Grok Bot (optional)** > **Install Grok Bot on this computer** in `AIBody Companion Setup.exe`, which installs Grok Bot
and sets both keys (see "Setup" below).

## The calls Grok Bot uses

Every call needs the header `Authorization: Bearer <remote.token>`.

```
# wait up to 20 s for what the user says next (after = the last id already handled)
curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:38438/api/bridge/events?after=0&wait=20"

# answer: speak, show a face, run a pose command
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"text":"Hi, nice to see you."}' http://127.0.0.1:38438/api/say
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name":"happy"}' http://127.0.0.1:38438/api/expression
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name":"Sit Down"}' http://127.0.0.1:38438/api/pose

# what the character has (expressions, gestures, pose commands) and the driver state
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:38438/api/status
```

`GET /api/bridge/events` answers `{"ok": true, "events": [...], "last_id": N, "driver": {...}}`. Each event has `id`,
`type` (`user_said` with `text` and `source` `voice` / `typed`, or `scene_event` with `text`) and `time` (Unix seconds).
The app keeps the last 200 events; a gap in the ids means older ones were dropped. `wait` is at most 25 s.

## Setup (opt-in)

The setup's task **Grok Bot (optional)** is unchecked; the default install is the direct method only. When ticked:

- **Install Grok Bot on this computer**: the setup reads the official release feed
  (`https://api2.cursor.sh/updates/api/download/stable/win32-x64-user/sand`, Arm64: `win32-arm64-user`), downloads the
  Setup `.exe` it names (only `https://downloads.cursor.com/...`), installs it silently per user (`/S`, no admin
  rights) and sets `ai.driver` `grok_bot` and `remote.enabled` `true`. The result is written to
  `<VaM>/Saves/PluginData/AIBody/logs/grok_bot_setup.log`. A failed download or install never fails the AIBody setup;
  the direct method then stays.
- **Grok's cloud only**: nothing more is installed and the direct method stays (it already uses Grok through the xAI API).

What no setup can do for you (Grok Bot has no scripted configuration for single users): sign in with your Cursor
account, allow local execution on this computer (Settings > Computer, or "always allow" on the first command) and any
own auto-review rules. The setup's last page says so.

## Not decided yet (open in the backlog)

- Auto-configuration of Grok Bot beyond the two `config.json` keys (which settings, how the API connection is entered):
  variants to be discussed.
- Installing Cursor (the editor) as well: not needed for Grok Bot; open until it is decided.
- A menu chooser for the driver in the plugin (today: `config.json` only).
