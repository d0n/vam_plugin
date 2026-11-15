# AIBody backlog

Deferred on purpose. Since v0.6.0 the rule is **workability first**: one `.cslist`, one MVRScript,
one "Add Plugin" step on the AI character, plus the companion app. Anything that adds a second
load step, a second plugin or a plugin-to-plugin bridge waits here until the single plugin is
verified inside VaM 1.22.

## Setup and loading

- **Separate Client on another atom.** Let the companion app link (mic, engines, status) live on
  the user's own atom or an Empty, apart from the body. Was v0.5.0 (`legacy/v0.5`); needs the
  cross-plugin bridge (`GetStorableIDs`, `plugin#` storable ids, string-param callbacks), which is
  unverified.
- **A second character** (or more): a second body driven by the same companion app, with a
  target per command and one LLM persona per character. Was v0.4 slots / v0.5 atom routing.
- **Session bootstrap**: a Session plugin that adds AIBody to the right atom by itself via
  `MVRPluginManager.CreatePlugin()` and `pluginURLJSON` (the Keybindings pattern), so scenes
  without the plugin still get a body. Unverified API, extra plugin.
- **Shipped plugin presets** (`Custom/Atom/Person/Plugins/...`) so a preset load adds and
  configures the plugin.
- **Sub-plugin nesting**: one entry plugin loading further `.cslist` files.
- **Demo / how-to scene** in the package (needs a character look and a tested scene).
- **Hub publishing** on VaMHub (needs a verified build, screenshots, description).

## Character

- **Gaze and attention**: look at the user's camera while listening (for now use Glance).
- **Data-only personas**: a folder `Saves/PluginData/AIBody/personas/<name>/` with a JSON (name,
  voice, prompt, expressions, gestures) and sound files, read via `FileManagerSecure`
  (DollMaster style). Never loads plugins. Not trivial yet: needs persona selection in the plugin
  and the companion app, and real engines to matter.
- **States** (idle, listening, thinking, speaking) as plugin triggers, like Voxta, so scene
  builders can attach Timeline animations without code.
- Viseme-based lip sync from TTS timing data, as an alternative to VaM's audio lip sync.

## Companion app

- **Real engines**: STT (faster-whisper or Vosk), LLM (local server such as Ollama, or a cloud
  API), TTS (Piper or XTTS), on a worker thread, streamed sentence by sentence.
- Better VAD (webrtcvad or Silero) and barge-in in voice-activation mode with echo cancellation.

## Nice-to-haves from the requirements catalog

- **Life-style features** (MacGruber's Life): breathing with chest movement and breath sounds,
  heartbeat, blinking, subtle body sway, arousal/exertion states. For now use Life itself on the
  same atom.
- **LogicBricks-style features**: reactions to scene events (touch, proximity, gaze, triggers)
  wired to body commands or companion app events, and simple state machines for scene builders.
- Reactions to collisions/touch zones fed back to the companion app as events.

## Removed for good (not backlog)

- **HTTP transport / any network code in the plugin** (removed in 0.6.1): no
  `UnityEngine.Networking`, `UnityWebRequest`, `WWW` or sockets, not even behind a compile flag.
  The shared folder is the only link. The companion app's HTTP server went with it.
- **Microphone capture inside VaM**: stays in the companion app; the plugin has no microphone API.
- **Anything without a public, working plugin as evidence** for VaM 1.22's sandbox: see
  `docs/API_AUDIT.md`. New VaM API use needs such evidence before it goes in.
