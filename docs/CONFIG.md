# Shared config file: `Saves/PluginData/AIBody/config.json`

One JSON file, relative to the VaM folder, read by the AIBody plugin **and** the companion app:

```
<VaM>/Saves/PluginData/AIBody/config.json
```

Why there: established plugins keep their settings in their own folder below `Saves/PluginData`
(Timeline: `Saves/PluginData/Timeline/settings.json`, Keybindings: `Saves/PluginData/Keybindings`),
and it is where AIBody's folder already is. It is global: one file for the one character. Evidence links: [API_AUDIT.md](API_AUDIT.md) ("Config file location").

## Who reads and writes it

| when | plugin | companion app |
|------|--------|---------------|
| file missing | writes it about 2 s after loading (from its UI values) | creates it with the defaults on start |
| plugin added to a scene **without** saved AIBody settings | takes the values from the file once (new scene / re-added plugin) | - |
| scene **with** saved AIBody settings | the scene's values win and are written back | - |
| a value changes in the plugin UI | written back within 1 s (only if something changed) | gets it live as a `config` event (protocol) |
| app start | - | reads mic, engines and `ai` from the file; adds a missing `ai` section with its defaults |
| `ai` section | sets only its tab controls (`mode`, `language`, `proactive.enabled` / `idle_seconds`, `barge_in.enabled`, `realtime.voice`, `xai.voice`; `xai.key_file` / `elevenlabs.key_file` are passed through from the file - no menu field since version 15, the file wins on every start), keeps the rest when writing the file | reads it (persona, language, fallback, engine settings); the tab controls also arrive live in the `config` event |
| paths (`connection.paths`) | read from the file (no UI), on start and on **Reload Config JSON** (tab *Config*); `paths.audio` is kept unchanged | `paths.audio`: where it writes the speech WAVs |
| `poses` section (version 32) | owns it: **Add Pose** / **Delete Pose** / **Restore starter poses** write `poses.commands`; read at start and on **Reload Config JSON** (a missing key, `[]` or a list without a usable entry = the 10 starters, version 35) | reads it as the pose vocabulary (the gate); also learns the live list from the plugin's status field `pose_commands` |
| `characters` section (after version 37) | owns it: the character wizard answers (`setup_answered`, `setup_wanted`, `ai_gender`, `user_gender`), written with the scene and this file, also sent in the `config` event | reads it on start and live from the `config` event; adds the genders to the AI instructions |
| `setup` section (version 35) | never touches it; keeps it when it writes the file | owns it: the answers of the first-start questions (`asked`, `green_background`, `example_scene`) |
| tab *Config* > **Reload Config JSON** | applies the whole file to the UI (also for a saved scene) and sends it to the app | gets the new values live |

The plugin writes compact JSON in place (FileManagerSecure cannot rename); the app writes the
default file atomically and ignores a file it cannot parse (then defaults, with a warning).

**Numbers and true/false as strings:** the plugin writes with VaM's SimpleJSON, which stores every
number and boolean as a string (`"gain":"2.5"`, `"active":"true"`), like VaM scene files do. The
app accepts both forms everywhere (config.json and the plugin's events); so does the schema.
Edit the file while VaM is closed, or remove the plugin's saved settings, if you want the file
to win.

## Schema (version 1)

One object per settings category. Since the menu restructure the categories no longer match
the tabs one to one (kept for compatibility with existing files): `connection` = file only
(network switch and port, paths; + *Voice > Companion connection* **Active**), `engines` = tab *Voice* (sections *AI* and *Voice and sound*), `mic` = tab *Client Character*, `body` = tab
*AI Character*, `characters` = tab *AI Character* > Characters (after version 37), `advanced` = tab *Config*, `ai` = companion settings plus the tab controls named
below. Machine-readable:
[protocol/schema/config.schema.json](../protocol/schema/config.schema.json), example:
[examples/config.json](../examples/config.json).

The complete key reference (type, default, allowed values, effect, where to set it) is in the
[README, section 4](../README.md#4-settings); it is the single list and kept in sync with
`companion/aibody_companion/settings_file.py`.

The push-to-talk *state* is never saved (only the setting `ptt_interrupts` and `mode`). Unknown
keys are reported and ignored; out-of-range numbers are clamped.

## Modes: simple Q&A, realtime voice and chain

**Simple Q&A** (`ai.mode` `qa`, the default): the chain below, made as hard to get wrong as
possible. With an xAI key (the plugin field `XAI API Token`, environment `XAI_API_KEY` or a key file) the offline test engines
(`null` / `echo` / `tone`) are replaced by `xai`, so STT `xai` -> Grok (streamed, split into
sentences, the first sentence is spoken while the rest is still written) -> TTS `xai` -> WAV ->
`speak` -> head audio; engines picked explicitly (e.g. TTS `elevenlabs`) stay. Expression /
gesture tags in the answer are dropped (speech only); proactive remarks are paused. Typed text in
the companion console takes the same path without speech to text. Every step reports to the
status box (heartbeat `turn`): `Heard: …`, `Answer (n sentence(s), xai -> xai): …`,
`Nothing understood: …`, `Speech recognition error: … - using the test engine instead; check your xAI key …`,
`Language model error: … - fallback answer` (a short spoken notice instead of the answer),
`Text-to-speech error: … - you hear a fallback tone (tone) instead; check your xAI / ElevenLabs key …` (the
sentence is played as a tone). Every message says what went wrong, where to look and what to do next. Without a key the test engines run and the mode status says so.

In every mode but `chain`, an xAI key also replaces the test engines on the chain path for typed
text and for the realtime fallback.

**Realtime** (`ai.mode` `realtime`, or `auto` with an xAI key): one persistent WebSocket to
`wss://api.x.ai/v1/realtime?model=grok-voice-latest` (header `Authorization: Bearer <key>`, same
key as the xAI engines). The companion sends `session.update` (persona + rules as `instructions`,
`voice`, `turn_detection: server_vad`, PCM formats, a function tool `express`) and streams the
microphone as `input_audio_buffer.append` (16-bit PCM at the mic rate, 16 kHz by default). The
server detects the end of speech and answers; the answer audio (`response.output_audio.delta`) is
cut into WAV segments at sentence ends and played through the usual `speak` commands, so the body
starts talking with the first segment. Expressions and gestures come from the `express` function
call and become the existing `expression` / `gesture` commands. When the server reports
`input_audio_buffer.speech_started` while the body talks, the companion sends `stop_speaking`
and drops the rest of that answer (push-to-talk also sends `response.cancel`). The connection is
re-opened with backoff (1, 2, 4, 8, 15, 30 s); meanwhile chain runs. If the server is connected but
sends no answer within 12 s after `input_audio_buffer.speech_stopped`, the companion gives realtime
up ("Realtime off: no answer …") until **API Reconnect** or a new AI mode, and the chain
answers (repeat the question). The info field (tab *Voice*) shows the active mode ("Mode: realtime – Realtime
connected …").

**Voice detection (`mic.vad_engine`, `mic.vad_strictness`):** `energy` is the built-in detector (noise floor that
follows the room, a higher bar to start than to continue speech, a short hangover, and a constant hum is learned as
noise after about 6 s); `webrtc` needs `python -m pip install webrtcvad-wheels`; `auto` (default) uses it when it is
installed. Without the library the built-in detector runs (if you chose WebRTC yourself, the status line in the menu
says how to install it). `vad_threshold` is
the quietest level that can count as speech for every engine; `vad_strictness` 0-3 ignores more noise when higher.

**Echo:** while the body talks, the companion streams silence instead of the microphone (there is
no echo cancellation), so interrupting by voice needs **Voice barge-in (headphones)**. Push-to-talk
always interrupts. The mic stays closed while a clip is queued or playing and for `echo_tail_s` after it ends; in
realtime mode it also stays muted from the start of an answer until the answer is done (at most 90 s).

**Chain** (`ai.mode` `chain`, or `auto` without xAI key / with ElevenLabs TTS): exactly the engines
of *Voice > AI*, as before.

## Proactive speech and time context

- **Proactive talking** (toggle `ai.proactive.enabled`; until version 22 called "Proactive"): after `ai.proactive.idle_seconds` without speech (user or AI), the companion
  nudges the AI: realtime via `conversation.item.create` + `response.create`, chain via one
  language-model turn (needs `llm` = `xai`). The nudge carries the time context and
  `ai.proactive.prompt`; the default prompt allows the AI to stay silent by answering `[silent]`,
  which is then not played. After an unanswered nudge the wait doubles (up to 8x); any user speech
  resets it. Never while the body talks, the user speaks or push-to-talk is held.
  **`idle_seconds` 0 = proactive speech off** (same as `enabled: false`, in realtime and chain; any
  value below 1 s counts as 0; range 0..3600, default 90). The plugin slider is called **Speech delay timer (s)** (until version 22: "Proactive idle (s)"); it shows `Proactive talking: off (speech delay timer 0 s)` for 0, else `Proactive talking: on - after 90 s of silence the AI may speak on its own (speech delay timer, not the answer delay)`. The timer is the silence before the AI may speak on its own, not how long it takes to answer.
- **Time context:** the AI has no clock of its own. The companion adds the local date and time
  (with UTC offset) and the time since the last exchange to every user turn (chain, `xai` LLM:
  prefix of the user message, not stored in the history) and to every nudge; in realtime mode it
  is part of the `instructions`, refreshed when the user starts speaking and every 60 s.

## API keys and engines

| engine | kind | needs | endpoint |
|--------|------|-------|----------|
| `null` | STT | nothing (offline, hears nothing) | - |
| `echo` | LLM | nothing (offline, "You said: …") | - |
| `tone` | TTS | nothing (offline humming tone) | - |
| `xai` | STT | `XAI_API_KEY` or `ai.xai.key_file` | `POST https://api.x.ai/v1/stt` (multipart, WAV upload) |
| `xai` | LLM | `XAI_API_KEY` or `ai.xai.key_file` | `POST https://api.x.ai/v1/responses`, `stream: true` (SSE) |
| `xai` | TTS | `XAI_API_KEY` or `ai.xai.key_file` | `POST https://api.x.ai/v1/tts`, `output_format: {codec: pcm}` |
| `elevenlabs` | TTS | `ELEVENLABS_API_KEY` or `ai.elevenlabs.key_file` | `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=pcm_24000` |

`config.json` also carries `ai.xai.key_hint` (version 22): a plain-text note (JSON has no comments) saying that an xAI
API key is required and the three ways to give it. The app ignores it; any text is accepted.

**Plugging in the xAI key (version 21, stored in config.json since version 24):** paste it into
the field **XAI API Token** (tab *Voice*, section *Companion connection*, below **API Reconnect**). Plain text, no
format check. The plugin saves it in `config.json` as `ai.xai.api_key` (PLAIN TEXT, at Don's explicit
request; `ai.xai.api_key_warning` next to it carries the security notice), fills the field from it on
every start, and then shows it masked once the field is not focused (first and last 4 characters visible, stars between: `xai-****abcd`; the mask never replaces the stored token). The
companion app reads `ai.xai.api_key` too, also before the plugin connects. Masked in every log.
Precedence: 1. the field (live, when not empty), 2. `ai.xai.api_key`, 3. `XAI_API_KEY`, 4. `ai.xai.key_file`;
emptying the field in the plugin also empties `ai.xai.api_key` and falls back to 3 / 4. A changed key also
reconnects realtime. There is no ElevenLabs field.

**Security notice:** anyone who can read `config.json` can read the token: do not share or publish the file.
Since version 31 no scene holds the token any more (the field is not saved with the scene), but a scene saved with
version 21 to 23 still contains the full token (plain text): do not publish such a scene. The notice is also shown at the top of the info field on the left
(tab *Voice*) and in `config.json` (`ai.xai.api_key_warning`).

**Plugging in a key from the environment or a file** (example ElevenLabs, the same for xAI):

1. Either set the environment variable before starting the app, e.g. in PowerShell
   `$env:ELEVENLABS_API_KEY = "<key>"` (or permanently via *System > Environment Variables*),
2. or save the key alone in a text file outside the repository and the VaM folder, e.g.
   `C:\Users\<you>\keys\elevenlabs.txt`, and enter its path in `config.json`:
   `"ai": { "elevenlabs": { "key_file": "C:/Users/<you>/keys/elevenlabs.txt" } }`
   (a relative path counts from your home folder, e.g. `keys/elevenlabs.txt`).
3. Select **Text-to-speech: elevenlabs** in the plugin's tab *Voice > Voice and sound*. The engine status in the info field
   changes from "not configured" to "ready (…)" - a key file within 10 s, an environment
   variable after restarting the app.

Since version 15 the key file path is set only in `config.json` (the menu fields showed as empty,
unlabeled boxes in VaM and were removed); after editing the file press **Reload Config JSON** (tab
*Config*) or reload the scene. The key status in the info field (tab *Voice*) shows per provider **configured**,
**missing** or **rejected** (the server refused the key with HTTP 401/403). Something that looks like
a pasted key (starts with `xai-` / `sk_`, or a long string without `/ \ .`) is refused by the
plugin and the app and never stored - this rule applies to the `key_file` values only, not to the
field **XAI API Token** or `ai.xai.api_key`, which take anything (plain text, see the security notice above).

**Which key:** xAI needs an API key from console.x.ai (starts with `xai-`). A Grok subscription
(SuperGrok / X Premium) or a grok.com login token is not an API key and is refused by `api.x.ai`.
The key status (heartbeat `keys.xai.hint`, info field of tab *Voice*) says so when the key is missing or refused.

The token goes into `config.json` only as `ai.xai.api_key` (a `key_file` value that looks like a key is
refused) and never into the log. Without a key nothing is blocked: the engine is "not configured"
and the fallback runs.

**Real API check** (once keys exist; everything is only tested against a fake server so far):
type a line into the companion app with `llm: xai`, `tts: xai` or `elevenlabs`, and watch its log
for `Engine ... ready`, the spoken sentences and any `failed (...)` warnings.

## What xAI offers for speech (checked on docs.x.ai, 17.11.2026)

- **Speech to text: yes** - `POST /v1/stt` (batch, file upload) and `wss://api.x.ai/v1/stt`
  (streaming), model `grok-voice-transcribe-2.0`.
  <https://docs.x.ai/developers/model-capabilities/audio/speech-to-text>
- **Text to speech: yes** - `POST /v1/tts` (and `wss://api.x.ai/v1/tts` streaming), voices such
  as `eve` / `ara` / `rex`, codecs mp3/wav/pcm/mulaw/alaw.
  <https://docs.x.ai/developers/model-capabilities/audio/text-to-speech>
- **Speech to speech:** `wss://api.x.ai/v1/realtime` (Grok Voice, `grok-voice-latest`). Used by
  `ai.mode` `realtime` since v0.7.1 (standard-library WebSocket client in the companion).
  <https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech>,
  <https://docs.x.ai/developers/rest-api-reference/inference/voice>
- Language model: `POST /v1/responses` with `stream: true`; `instructions` cannot be combined with
  `previous_response_id` (the stored system prompt is reused), so the persona goes out with the
  first request of a conversation only.
  <https://docs.x.ai/developers/rest-api-reference/inference/responses>

## Gaze and blinking (removed after version 36)

Don, 20.11.2026: the eyes belong entirely to VaM. The plugin has no gaze or blink control any more, and the keys
`body.gaze_control`, `body.gaze_default`, `body.gaze_follows_speaker` and `body.blink_control` are gone (versions 25 to 36
had them). An old file that still holds them loads without a warning and the plugin drops them on its next write.

## Scene events and more (version 26 and later)

- `ai.ollama.*` (version 29, file only): the local language model Ollama, `engines.llm: "ollama"`. `base_url` (`http://127.0.0.1:11434`), `model` (`llama3.2`), `max_output_tokens`, `temperature`, `keep_alive`, `max_messages`, `timeout_s`. See [LOCAL_ENGINES.md](LOCAL_ENGINES.md).
- `ai.barge_in.{enabled,ratio,min_ms,floor}` (version 29, file only, off by default): talk over the body without headphones by a loudness rule. `mic.vad_engine: "silero"` needs onnxruntime and the model file `Saves/PluginData/AIBody/models/silero_vad.onnx` (or `AIBODY_SILERO_MODEL`). Same document.
- `connection.network_active` (default `true`, version 30): the plugin toggle **Network Active** (tab *Config*), mirrored here. On = the loopback link described in TECHNICAL.md ("Network Active") is used, with the file channel as automatic fallback; off = files only and no network code runs in the plugin.
- `connection.network_port` (default `38437`, version 30, file only): the UDP port on `127.0.0.1` where the companion app listens; `0` = no listener (files only). Only the loopback address can be used.
- `ui.first_run_hint_dismissed` (default `false`, version 30): set by the plugin when the first-run note was closed or a token exists; the note is never shown again.
- `poses.commands` (version 32, written by the plugin): the pose commands, a list of `{"command": "<text>", "pose": "<pose id>"}` (at most 100; `command` at most 60 characters, no two commands equal after normalizing). Version 58: a pose is applied when the user's input contains a `command` as whole words (case and punctuation ignored, also inside a sentence, not after a negation such as "don't" / "never" / "nicht", the longest command wins); up to v57 the WHOLE input had to equal it. `pose` is matched to the character's poses (file name without `Preset_` or a `gestures.json` pose; case, spaces, `_` and `-` ignored). Default (version 59, the built-in commands): `Sit Down`, `Lay Down` (also "lie down"), `Turn Around`, `Stand Up`, `Prone`, `Crawl`, `Get On Your Knees` (also "kneel down"), `Handstand`, `Headstand`, `Stand On Your Right Leg`, `Stand On Your Left Leg` (each linked to the pose of the same name); a saved list with the v32-v58 starters (`Spread Your Legs`, `Ankle Your Knees`, `Ankle Your Elbows`, `Crawl on all fours`, `Bend Over` still linked to their own pose) is migrated: those are dropped and the new built-ins added, other entries stay. Version 59: every command runs; when its pose is missing or its file is broken, the plugin loads a random pose of the idle pool (failed files and the current pose skipped), else the Idle default pose. No "unavailable" commands. Invalid entries (empty, too long, duplicate, wrong type) are reported and dropped. Edit it in the plugin (tab AI Character > Poses) or in the file; see SPEC.md "Pose commands".
- `remote.enabled` (default `false`, version 31, file only): `true` = the companion app opens the remote control (web page and HTTP API, optional OSC) at the next start. Loopback only (`127.0.0.1`). See [REMOTE.md](REMOTE.md).
- `remote.http_port` (default `38438`, 1024-65535): TCP port of the web page and HTTP API.
- `remote.osc_port` (default `0`, 0-65535): UDP port of the OSC listener; `0` = no OSC (OSC has no token).
- `remote.token` (default empty): secret for the HTTP API; empty = the app writes a random one here when `remote.enabled` is `true`. Never share a `config.json` that holds it. The plugin keeps the whole `remote` section unchanged when it saves.
- Removed in version 30 (one character per app): `ai.channels`, the plugin's `Channel` value and `--channel` lists. Old files and scenes that still hold them are read without error and the values are ignored.
- `ai.persona_name` (default `""`), `ai.memory.{enabled,max_facts,session_idle_minutes,min_exchanges}` and `ai.emotion.{fallback,fade,fade_after_s,fade_seconds,listening}`: version 27, see [PERSONAS.md](PERSONAS.md). The plugin owns `ai.persona_name` (menu **Persona**) and `ai.memory.enabled` (switch **Memory**) and writes them back; the rest is file only.
- `ai.scene_events.enabled` (default true) and `ai.scene_events.prompt` (default text with `{event}`): what the AI is told when a scene trigger sets the plugin's string **Scene event** (see PROTOCOL.md, "Scene events"). File only, no menu field.

## Idle poses and first-start questions (version 35)

- `body.idle_poses` (true): idle poses on / off (tab AI Character > Idle poses). After a random quiet time the character takes a random pose of all its poses (pose files, gestures.json poses, the poses of `poses.commands` and the default idle pose), never the same one twice in a row (version 51; up to v50: only pose-command poses, alternating with the default idle pose). Never while someone speaks, not for 120 s after a user pose command, never with `body.body_control` false.
- `body.idle_pose_interval_s` (165, range 30-18000 = 300 min, version 59; slider **Idle pose interval (s)**): how often the idle pose changes, the quiet time in seconds; each wait is the interval +/- 25 % at random. Replaces `body.idle_pose_min_s` / `body.idle_pose_max_s` (v51-v58): a file or scene with only those gets their mean (30 / 300 -> 165). Paused while Dollmaster is active.
- Mute (version 55): **not** a config.json key. The toggle **Mute AI (stop talking and listening)** (tab Config) and the voice commands switch the companion's in-memory state; it is off on every start.
- `body.idle_pose_pool` (`"aibody"`, version 66; `"aibody"` or `"all"`): tab AI Character > Idle poses > **Idle pose pool**, a dropdown that replaces the version 54 toggle. `"aibody"` = **AIBody poses only**: the idle pool is the pose files in `Custom/Atom/Person/Pose/AIBody` plus the poses linked in gestures.json (pose commands, default idle pose); `"all"` = **All pose files**: every pose file of the library, including other packages (the v51-v53 pool), plus the same linked poses. A pose file that is missing or fails to load is left out of the pool until the next reload. An unknown, empty or `"0"` value is `"aibody"`.
- `body.idle_poses_all_files` (version 54-65, removed in version 66): only read to migrate an old `config.json` - `true` becomes `body.idle_pose_pool = "all"`, `false` or missing becomes `"aibody"`; `body.idle_pose_pool` wins when both exist. The companion drops the old key when it rewrites the file and the plugin no longer writes it. A scene saved with v54-v65 that stored the toggle *Idle poses from all pose files* still loads: `true` selects **All pose files** (the old storable stays registered, hidden, and is never saved again).
- `ai.driver` (`"direct"`, version 61; `"direct"` or `"grok_bot"`, file only): who answers. `direct` = this app's own AI (all modes above, unchanged). `grok_bot` = Grok Bot answers through the localhost bridge of the remote control (needs `remote.enabled` and a token; without them the direct method runs and the console warns). See [GROK_BOT_BRIDGE.md](GROK_BOT_BRIDGE.md). Back to the direct method: `"direct"` and restart the app.
- `ai.emotion.gestures` (false, version 61) and `ai.emotion.keywords` (version 61; `happy`, `sad`, `angry`, `surprised`, `thinking`, each a comma-separated list, default empty): gestures = a nod / head shake before the first sentence of an answer that starts with a clear yes / no (only when the AI chose no gesture; only gestures the plugin lists); keywords = own words or phrases added to the built-in rules of the expression fallback (a trailing `*` matches every word that starts like this, e.g. `"yay*, awesome"`). File only.
- `body.idle_movement`, `body.idle_movement_opt_in`, `body.idle_movement_liveliness` (versions 60-63): removed in version 64 together with the idle movement (MacGruber's IdlePoser). An older `config.json` that still has them loads normally; the keys are ignored (the plugin drops them the next time it writes the file).
- `body.pose_root_reset` (true, version 63): tab AI Character > Body position > **Center body on control point**. When a pose is applied (pose commands, Apply Pose, idle poses, the AI's pose tool; not Dollmaster montages) the pose is kept, but the hips are put back over the AI character's control point (her root controller, placed by the scene and Body position): only the flat distance, the height stays.
- Version 65: a saved `"0"` or empty value in a dropdown (`idle_pose_default`, engines, voice, persona, language, pose command) is ignored and the default stays; it is not added as a choice. A menu with fewer than two entries is shown as a read-only line, not as a dropdown.
- `body.idle_pose_default` (`"Stand Up"`): the pose **Apply idle default pose** goes to; one of the idle poses (a pose name of the character).
- `setup.asked` (false), `setup.background` (false), `setup.background_color` ("#00FF00"), `setup.choice` ("", "scene" or "plugin"), `setup.revision` (0): written by the companion app after the first-start questions (version 36: background yes / no / abort with "Set your color for transparency", then "Choose what to use"; Abort writes nothing). The plugin only reads `background`, `background_color` and `revision`: a new revision with `background` true switches "Set background color" ON with that color, once. The version 35 keys `setup.green_background` / `setup.example_scene` are ignored without a warning. `python -m aibody_companion --setup` asks again, `--no-setup` never asks. See SPEC.md "Scene".
- `ui.background_setup_applied` (0, version 36): written by the plugin, the `setup.revision` it has applied.
- `ai.proactive.idle_seconds` is the menu's *Speech delay timer (s)*: 0-3600, default 90, 0 = off.

## Character configuration wizard (after version 37)

Written by the plugin (tab AI Character > Characters). Recorded settings only, also sent in the live `config` event so the companion can add them to the AI instructions.

- `characters.setup_answered` (false): true after the user answers the gate "Do you want to configure your characters?" with **Yes** or **No**. false = the question is shown (first visit, or after **Configure characters**).
- `characters.setup_wanted` (false): true = the user chose **Yes** and the gender steps are shown. false after answering = skipped, until **Configure characters** is pressed.
- `characters.ai_gender` (`""`, `Female` or `Male`): menu **AI gender/body**. Empty = not chosen yet. Used as prompt context ("The AI character's body is female."); the plugin does not change the Person's gender or body in VaM (no evidenced API).
- `characters.user_gender` (`""`, `Female` or `Male`): menu **Your character gender**. Same recording rule for the user's own character (a separate atom AIBody does not drive).
- Clothing is not a key: it is a free choice in VaM's own Clothing tab, with nothing predefined and no invented clothing ids.

## Reset to Default (plugin tab Config, since version 41)

**Reset to Default** (with **Confirm Reset to Default**) sets the plugin's saved settings of the scene back to their defaults: connection, AI mode, voice, persona selection, memory, proactive talking, engines, microphone and voice detection, body, idle and breathing values, idle poses, the character wizard's answers and genders, verbose log and the background toggle and color. The plugin then writes these values to `config.json` as it always does (UI wins), so the keys it owns there show the defaults too. Kept unchanged, never deleted: `ai.xai.api_key` (the XAI API Token) and every other part of `ai` the companion owns (persona text, engine details, key file paths `key_file`), `remote`, `setup`, `poses` (pose commands), `ui.first_run_hint_dismissed` and `ui.background_setup_applied` (so the companion's first-start background answer is not applied again), the plugin's `xAI key file` / `ElevenLabs key file` fields and the personas folder. The companion itself has no reset; to reset its own sections, edit or delete those sections in `config.json` while it is not running.

