# Remote control (version 31)

A small local control surface for the ONE AI character the companion app serves: a web page and HTTP API, and an
optional OSC listener. It is **off by default**, listens on **127.0.0.1 only** (this computer, nothing else on your
network), and lives entirely in the companion app: the VaM plugin gets no new code, it only receives the same commands
the AI or the plugin menu would produce (`speak`, `expression`, `gesture`, `pose`, `look_at`, `stop_speaking`).

## Switch it on

Edit `<VaM>/Saves/PluginData/AIBody/config.json`, section `remote` (file only, no menu entry; the plugin keeps this
section unchanged when it saves), and restart the companion app:

```json
"remote": { "enabled": true, "http_port": 38438, "osc_port": 0, "token": "" }
```

| Key | Default | Meaning |
|---|---|---|
| `remote.enabled` | `false` | `true` = open the remote at the next start of the app |
| `remote.http_port` | `38438` | TCP port of the web page and the HTTP API (1024-65535) |
| `remote.osc_port` | `0` | UDP port of the OSC listener; `0` = no OSC |
| `remote.token` | empty | secret for the HTTP API; empty = the app generates one into this file on the first start with `enabled: true` |

The console says what is open, e.g. `Remote control: web page and HTTP API on http://127.0.0.1:38438/ (this computer only; ...)`.
If a port is taken or the token is too short (under 16 characters) the app says so (yellow `Remote control:` line) and keeps
that part off; everything else keeps working.

## Web page

Open `http://127.0.0.1:38438/#token=<remote.token>` in a browser on the same computer (the part after `#` is never sent
to a server; the page moves it into the tab's session storage and removes it from the address bar). The page shows the
status and has: text to say exactly / ask the AI / scene event / stop, buttons for the expressions, gestures, pose commands
the plugin reports, eye targets, and push-to-talk start / stop.

## HTTP API

Every `/api/` call needs the token: header `Authorization: Bearer <token>` (or `X-AIBody-Token: <token>`).
POST bodies are JSON objects (`Content-Type: application/json`, at most 16 KB). Answers are `{"ok": true}` or
`{"ok": false, "error": "..."}`.

| Call | Parameters | What happens |
|---|---|---|
| `GET /api/status` | | plugin connected, link, mode, last turn status, microphone, persona, the lists of expressions / gestures / pose commands (`poses` = every command; version 59: no `poses_unavailable`, a missing pose gets a substitute) / gaze atoms, the last remote action |
| `POST /api/say` | `text`, `interrupt` (false) | speaks exactly this text (text to speech, no language model); `interrupt: true` cuts in with the first sentence |
| `POST /api/ask` | `text` | asked like typed text: language model, speech, body tools |
| `POST /api/expression` | `name`, `intensity` (1.0), `blend` (0.4 s), `hold` (seconds, optional) | shows the expression |
| `POST /api/gesture` | `name` | plays the gesture |
| `POST /api/pose` | `name` | runs a **pose command** (version 32): `name` is the command text (e.g. `Sit Down`) and goes through the same exact-match gate as typed input; anything else (`please sit down`, a pose name that is not a command) is refused and logged; version 59: every command runs (a missing or broken pose gets a substitute pose in the plugin) |
| `POST /api/look` | `target` (`client`, `camera`, `forward`, `away`, `off`, `atom`), `atom` (atom name), `seconds` (0 = until changed) | directs the eyes |
| `POST /api/stop` | | stops speaking and drops the answer being prepared |
| `POST /api/event` | `text` | tells the AI about a scene event (like the plugin's *Scene event*) |
| `POST /api/ptt` | `action`: `start`, `stop`, `toggle` | push-to-talk (microphone mode must be `ptt`) |

```
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"text":"Hello there."}' http://127.0.0.1:38438/api/say
```

The same switches as for the AI apply: expressions, gestures, poses and looking need *Body control* on in the plugin
(and, for looking, *Gaze control*); an action that cannot run is logged as a warning and shown as `last_action` in the
status. Names are matched ignoring case and must be ones the plugin lists.

## OSC

With `remote.osc_port` above 0 the app listens for OSC 1.0 messages (types `i f s T F`, bundles are unpacked) on
`udp://127.0.0.1:<osc_port>`:

| Address | Arguments |
|---|---|
| `/aibody/say` | `"text"` [`interrupt` 0/1] |
| `/aibody/ask`, `/aibody/event` | `"text"` |
| `/aibody/expression` | `"name"` [`intensity`] [`blend`] [`hold`] |
| `/aibody/gesture` | `"name"` |
| `/aibody/pose` | `"command text"` (a pose command, e.g. `"Sit Down"`; the exact-match gate applies) |
| `/aibody/look` | `"client"`, `"camera"`, `"forward"`, `"away"`, `"off"` or `"atom:<Name>"`, [`seconds`] |
| `/aibody/stop` | none |
| `/aibody/ptt` | `"start"` / `"stop"` / `"toggle"` (or `1` / `0`) |

OSC has **no token** (most OSC senders cannot send one); it is protected only by the loopback bind and is off unless you set a port.
Any program on this computer can send to it.

## Protection

- Both servers bind `127.0.0.1` only. There is no setting for another address, so nothing on your network can reach them.
- The HTTP API needs the token (constant-time comparison; a wrong token is answered after a short delay). The token is a
  secret in `config.json`: do not share or publish that file with a token in it. It is redacted in the app's logs.
- The `Host` header must be `127.0.0.1:<port>` or `localhost:<port>` and a browser `Origin` must be this server, so other
  web pages (also through DNS rebinding) cannot drive it. There are no CORS headers and no preflight answers.
- JSON only, size limits (16 KB body, 1000 characters of text, OSC datagrams 4 KB), at most 50 queued actions.
- The servers only validate and queue; the main loop of the app runs the actions, so a request never blocks the link to VaM.
- Nothing in the plugin changed: still one `.cslist`, `System.Net` only in `SocketLink.cs`, no HTTP in the plugin.
- Not protected: a program on this computer that can read `config.json` can read the token. That is the same trust
  as for the xAI token in the same file.

## Not included

- One character only (no character selector, no multi-character code).
- No lip-sync or mouth-timeline control, no microphone audio, no file upload.
- No remote access from other computers (put your own tunnel in front if you ever need it; that is your decision, not a setting).
