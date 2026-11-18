# AIBody protocol, version 3

This is the message format between the **companion app** (the AI's "brain", a Python program
running outside VaM) and the **AIBody plugin** (the AI's "body", inside VaM). Messages are JSON
objects. JSON schemas: [`schema/command.schema.json`](schema/command.schema.json) (companion app
to VaM) and [`schema/event.schema.json`](schema/event.schema.json) (VaM to companion app).

## Parts

```
companion app  <-- files in Saves/PluginData/AIBody/<channel>/ -->  AIBody plugin (AI's Person atom)
                                                                      AppLink --in-process--> Body
```

The VaM side is **one plugin**: `Custom/Scripts/d0n/AIBody/AIBody.cslist` in `d0n.AIBody.7.var`,
one MVRScript (`AIBody.AIBodyPlugin`), loaded once on the AI character's Person atom (Plugins
tab). Inside it, two plain C# components call each other directly:

- **AppLink**: the transport to the companion app, channel, heartbeat/status, microphone menu and
  engine menus. Handles `ping`, `companion_heartbeat` and the microphone feedback itself and hands
  every body command to the Body.
- **Body**: speech with lip sync on the head audio, expressions, morphs, gestures, poses, idle and
  breathing. Its events go back through the AppLink.

There is no routing, no target atom and no bridge between plugins: one plugin = one character.

## Envelope

Every message has:

| field | type   | notes                                                          |
|-------|--------|----------------------------------------------------------------|
| `v`   | int    | protocol version, `3`                                          |
| `type`| string | message type                                                   |
| `id`  | string | unique id. Replies carry `reply_to`.                           |
| `ts`  | number | Unix time in seconds (informational)                           |

**Value types from the plugin:** VaM's SimpleJSON writes every number and boolean as a string
(`"v":"3"`, `"active":"true"`, `"duration":"1.25"`). The companion accepts both forms in all
plugin events and in config.json (`aibody_companion/vamjson.py`); the plugin reads the
companion's real JSON numbers and booleans with `AsFloat` / `AsBool`.

A command may set `"ack": true` to get an `ack` event on success. Failures always produce an
`error` event with `reply_to` set to the command id. A transport payload may contain one message
or a JSON array of messages.

## Transports (companion app <-> AIBody plugin)

### File transport (the only transport)

The plugin contains no network code at all (no `UnityEngine.Networking`, no `UnityWebRequest`,
no sockets), so it needs no "Allow Plugins Network Access". The file folder is the only link.

All paths are relative to the VaM install folder:

```
Saves/PluginData/AIBody/<channel>/inbox/    companion app -> AIBody plugin (commands)
Saves/PluginData/AIBody/<channel>/outbox/   AIBody plugin -> companion app (events)
Custom/Sounds/AIBody/<channel>/             speech audio written by the companion (default)
Saves/PluginData/AIBody/<channel>/audio/    its fallback if VaM cannot load the default folder
```

- The plugin side uses only `FileManagerSecure` (writes are allowed below `Saves/PluginData`).
- One message (or array) per `*.json` file. File names must sort (ordinal) in send order,
  e.g. `<20 digit timestamp>_<6 digit sequence>.json`.
- The companion writes `name.tmp` and renames it to `name.json` (atomic).
- The plugin cannot rename through `FileManagerSecure`, so it writes `*.json` in place; the
  companion retries files that fail to parse for 2 s before dropping them.
- The reader deletes each file after processing. The companion clears both folders on start.
- The plugin polls its inbox every 0.1 s (slider "Companion inbox poll interval (s)" in the Config tab;
  stored name "File poll interval (s)", config.json `advanced.file_poll_interval_s`). This is only
  the companion message inbox; config.json is never reloaded automatically. It sends `ready`, its `config` and
  `list_devices` on start and a `heartbeat` every 2 s.
- The companion counts the plugin as connected while it received an event in the last 5 s, and
  while connected sends `companion_heartbeat` every 2 s. The plugin counts the companion as
  connected while a `companion_heartbeat` arrived in the last 6 s. A new `session` id in
  `companion_heartbeat` means the companion restarted: the plugin sends `ready` and `config` again.
- `<channel>` defaults to `default` (AIBody plugin "Channel", companion app `channel`). Both sides
  must use the same value.

### Shared config file

Besides the message files, both sides use `Saves/PluginData/AIBody/config.json` (one global file,
one object per plugin tab: `connection`, `engines`, `mic`, `body`, `advanced`, plus `ai` for the
companion app only, which the plugin keeps unchanged). The plugin UI wins and writes it back;
the companion app reads it on start. See `docs/CONFIG.md` and
`schema/config.schema.json`. Live changes still travel as `config` events.

### Robustness

- The plugin deletes stale `inbox/*.json` when its link starts (no replay of old commands) and,
  while no `companion_heartbeat` arrives, keeps at most 20 files in `outbox/`.
- The companion app deletes its own `inbox/*.json` that the plugin did not pick up within 10 s.
- A `companion_heartbeat` with a new `session` after an earlier one means the app restarted: the
  plugin cancels its speech queue and sends `ready` + `config` again.

## Commands (companion -> VaM)

### Body (handled by the plugin's Body)

| type            | fields                                                                 | effect |
|-----------------|------------------------------------------------------------------------|--------|
| `speak`         | `audio` (required), `text`, `expression`, `intensity`, `queue` (`append`/`interrupt`), `duration` | queues speech audio, see [Audio delivery](#audio-delivery) |
| `stop_speaking` | -                                                                      | stops playback and clears the queue |
| `expression`    | `name` (required), `intensity` (1), `blend` s (0.4), `hold` s (keep)   | blends to an expression preset |
| `set_morphs`    | `morphs` {name: value} (required), `blend` s, `release_others` bool    | sets raw morph values |
| `reset_morphs`  | `blend` s                                                               | returns all touched morphs to their original values |
| `gesture`       | `name` (required), `duration` s, `amplitude`                           | gesture from `gestures.json`, or built-in head gestures `nod`, `shake`, `tilt` |
| `pose`          | `path` or `name` (one required)                                        | `path`: loads a pose preset (`.vap`/`.json`, may be inside a `.var`); `name`: a pose from the plugin's pose list (`gestures.json` kind `pose` or a preset file in `Custom/Atom/Person/Pose[/AIBody]`) |
| `trigger`       | `storable` (required) + `action`, or `param` + `value` (+ `value_type`) | calls an action / sets a parameter on any storable of the target atom, e.g. another plugin |
| `idle`          | `enabled`, `intensity` 0..1                                            | procedural idle head motion |
| `breathing`     | `enabled`, `rate` breaths/min, `depth`                                 | procedural breathing |

`pose`, `gesture` (Timeline) and `trigger` use `JSONStorable.CallAction(name)` directly. The plugin
cannot list a storable's actions (no evidenced API for that), so a misspelled action name is
not detected by the plugin; a missing storable or parameter is reported as `command_failed`.

### App link

| type                  | fields | effect |
|-----------------------|--------|--------|
| `ping`                | -      | answers `pong` with its status |
| `companion_heartbeat` | `session` (required), `version`, `engines_available` (`{"stt": [...], "llm": [...], "tts": [...]}`), `engines_status` (`{"tts": {"elevenlabs": "nicht konfiguriert: ..."}, ...}`: "bereit (...)" or "nicht konfiguriert: <why>" per engine), `engines_active` (`{"stt": "null", ...}`: what really runs, the fallback if the selected engine is not configured), `mic_capturing`, `mode` (`{"requested": "qa" \| "auto" \| "realtime" \| "chain", "active": "realtime", "status": "Realtime verbunden …"}`), `proactive` (`{"enabled": true, "idle_seconds": 90, "status": …}`), `keys` (`{"xai": {"state": "configured" \| "missing" \| "rejected", "detail": "Key-Datei …", "hint"?: "nötig: API-Key von console.x.ai …"}, "elevenlabs": {…}}`, never the key; `hint` when missing / rejected), `audio_out` (`{"folder": "Custom/Sounds/AIBody/default", "auto": true, "note"?: "VaM konnte … nicht laden - Audio-Ordner gewechselt auf …"}`), `turn` (last question / answer step or problem as text: `Gehört: …`, `Antwort (…): …`, `Nichts verstanden …`, `Sprachmodell-Fehler: …`), `latency` (`{"last_s": 2.41, "avg_s": 2.6, "n": 5, "kind": "chain" \| "realtime", "parts": {"STT": 0.8, "LLM erstes Token": 0.5, …}}`: end of the user's speech to the plugin's `speech_started`, average of the last 10 turns) | companion liveness; fills the engine menus and the engine status in the tab AI |

### Microphone feedback (app link)

The microphone is opened only by the companion app. The plugin never touches a VaM/Unity
microphone API: it shows the device names from `devices`, and sends settings (`config`) and
push-to-talk (`ptt`) as event files.

| type         | fields | when |
|--------------|--------|------|
| `config_ack` | `reply_to`, `applied` (`{"mic": {...}, "engines": {...}, "ai": {...}, "advanced": {"verbose_log": true}}` settings in effect after clamping), `errors` (list of strings), `mic_state` | answer to every `config` event |
| `devices`    | `devices`: list of `{name, index, default, channels, sample_rate}`, `error`, `reply_to` | answer to `list_devices` |
| `mic_state`  | `enabled`, `capturing`, `device`, `mode`, `ptt_active`, `error` | when the microphone state changes, and after `ready` |
| `mic_level`  | `rms` (peak RMS 0..1 since the last message), `speech`, `gate_open` | 5 per second while capturing, if `level_meter` is on |

## Events (VaM -> companion)

All events come from the one plugin:

| type             | fields                                              | when |
|------------------|-----------------------------------------------------|------|
| `ready`          | status fields (below)                               | after start, reconnect or companion restart |
| `heartbeat`      | status fields                                       | every 2 s |
| `pong`           | status fields, `reply_to`                           | answer to `ping` |
| `error`          | `reply_to`, `code`, `message`                       | `bad_json`, `command_failed`, `audio_failed` |
| `config`         | `mic` (see below), `engines` (`{"stt", "llm", "tts"}`), `ai` (`{"mode", "proactive": {"enabled", "idle_seconds"}, "realtime": {"send_while_speaking", "voice"}, "xai": {"voice", "key_file"?}, "elevenlabs": {"key_file"}?}`, key file paths only when set), `advanced` (`{"verbose_log"}`: Erweitert > Verbose log, turns the companion's turn trace on/off live) | after (re)connect and 0.3 s after the last settings change |
| `ptt`            | `active` (bool)                                     | push-to-talk pressed / released |
| `list_devices`   | -                                                   | after (re)connect, on "Refresh mic devices", when the Mic device menu opens, and every 10 s while the companion runs but no list arrived (version 20); the companion also sends `devices` after every `ready` |
| `test_tone`      | -                                                   | button "Test-Ton über Companion": the app answers with a `speak` (queue `interrupt`, text "Test-Ton") of a 1.5 s chime WAV in its audio folder |
| `reconnect`      | -                                                   | button "API Reconnect": the app re-reads its API keys and reopens the realtime connection |
| `shutdown`       | -                                                   | plugin is stopping its transport |
| `ack`            | `reply_to`, `command`                               | command succeeded and asked for an ack |
| `speech_started` | `utterance_id`, `duration` (clip length in s)       | the clip really started playing |
| `speech_ended`   | `utterance_id`, `reason`, `queue_length`            | the clip stopped, or a queued one was dropped |
| `gesture_done`   | `name`                                              | a built-in head gesture finished |

`speech_ended.reason`: `completed`, `stopped` (stop_speaking / UI), `interrupted` (a
`queue: interrupt` speak or someone else replaced the clip), `cancelled` (was queued, never
played), `failed` (could not be loaded; an `audio_failed` error comes first).

Status fields (`ready`, `heartbeat`, `pong`): `plugin_version`, `protocol`, `channel`,
`transport`, `audio_dir`, `atom` (uid of the Person atom the plugin is on, informational),
`speaking`, `speech_queue`, `expression`, `expressions` (preset names), `gestures` (names),
`poses`, `body_control`, `selftest` (since version 13: the in-game self test of the body, object
with `pose_storage` ("ok" or why not), `pose_files`, `poses`, `breath_morph`, `breath_morph_found`,
`expression_morphs_found`, `expression_morphs_total`, `expression_morphs_missing`,
`timeline_gestures`, `timeline`, or `error`; recomputed at most every 5 s; the companion logs it as
"Plugin-Selbsttest: …" once per change, as a warning when something is missing).

### Microphone settings (`config.mic`)

All fields are optional; unknown fields and wrong types are reported in `config_ack.errors` and
leave the previous value in place. Numbers are clamped to the range.

| field              | type   | default | range        | meaning |
|--------------------|--------|---------|--------------|---------|
| `enabled`          | bool   | true    |              | open the microphone |
| `mode`             | string | `vad`   | `vad`, `ptt` | voice activation or push-to-talk |
| `device`           | string | `""`    |              | input device name from `devices`, `""` = system default |
| `vad_threshold`    | number | 0.01    | 0.001..0.5   | RMS level (after gain) that counts as speech |
| `end_silence_ms`   | int    | 700     | 200..5000    | silence that ends an utterance |
| `min_utterance_ms` | int    | 300     | 100..5000    | shorter utterances are dropped (must be < max) |
| `max_utterance_ms` | int    | 20000   | 1000..60000  | longer utterances are cut |
| `echo_tail_s`      | number | 0.4     | 0..3         | mic stays closed this long after speech ended |
| `gain`             | number | 1.0     | 0.1..8       | input gain before VAD and STT |
| `ptt_interrupts`   | bool   | true    |              | pressing push-to-talk sends `stop_speaking` and ignores the echo gate |
| `level_meter`      | bool   | true    |              | stream `mic_level` |

### Engines (`config.engines`)

`stt`, `llm`, `tts`: engine names picked in the AIBody plugin's menus. The companion accepts only
names it has implemented (listed in `companion_heartbeat.engines_available`) and reports others
in `config_ack.errors`. Implemented: stt `null` | `xai`, llm `echo` | `xai`, tts `tone` | `xai` |
`elevenlabs`. A cloud engine without API key is accepted (the choice is kept) but the fallback
runs; `config_ack.errors` and `companion_heartbeat.engines_status` / `engines_active` say so.
A streaming model is spoken sentence by sentence: one `speak` (queue `append`) per sentence, the
first one sent while the model still writes. An answer may start with `expression` / `gesture`
commands taken from a `<<expression gesture>>` tag at the start of the model's text.

### AI controls (`config.ai`)

`mode` (`qa` | `auto` | `realtime` | `chain`), `proactive.enabled`, `proactive.idle_seconds` (15..3600),
`realtime.send_while_speaking`, `realtime.voice` / `xai.voice` (a changed realtime voice reconnects),
`xai.key_file` / `elevenlabs.key_file` (paths; a value that looks like a key is refused with an error in
`config_ack.errors` and the old path stays): applied live, echoed in `config_ack.applied.ai`; all other `ai`
settings live in `config.json` only (docs/CONFIG.md). In realtime mode the answer audio arrives as
one `speak` (queue `append`) per segment, exactly like the sentence-by-sentence chain answers; a
barge-in sends `stop_speaking`. The protocol itself is unchanged (still version 3).

### Verbose log (`config.advanced`)

`advanced.verbose_log` (true/false; VaM sends it as a string) is the plugin's Config > "Verbose log"
toggle. The companion applies it live (turn trace in its console and log file, see docs/CONFIG.md) and
echoes it in `config_ack.applied.advanced`. The plugin writes its own side ([debug] lines) to the VaM log.
The Voice > Voice Mode toggle "Echtzeit (Realtime) verwenden" is not a protocol field: it only sets `ai.mode`
(on = `auto`, off = `qa`).

## Audio delivery

The companion writes each TTS clip to `Custom/Sounds/AIBody/<channel>/` (so it needs
`vam_root`; `connection.paths.audio` overrides the folder) and sends a `speak` with:

- `audio`: `Custom/Sounds/AIBody/<channel>/<file>`, relative to the VaM folder. The
  AIBody plugin loads it with VaM's own `URLAudioClipManager.QueueClip` (after
  `SuperController.NormalizeMediaPath`) and plays the resulting `NamedAudioClip` with the head `AudioSourceControl.PlayNow`,
  so VaM's lip sync animates the mouth.
- If the plugin reports `error` with `code` `audio_failed` for one of these clips (VaM could not
  load or start it) and the folder is automatic, the companion switches once to
  `Saves/PluginData/AIBody/<channel>/audio/`, copies the WAV there and sends a new `speak` for it;
  later clips go to the new folder (heartbeat `audio_out`). `command_failed` (file missing, no head
  audio) does not switch.

The plugin keeps an ordered queue (`queue: append`, default) and prefetches the next two
clips while one plays. `queue: interrupt` stops the current clip (`speech_ended` reason
`interrupted`), cancels the queue and plays the new clip next. `stop_speaking` stops and cancels
everything. The plugin's "Speech volume" setting applies to every clip.

## Echo handling

The companion keeps its microphone closed:

- from sending `speak` until that utterance's `speech_ended`, for every queued utterance,
- for `echo_tail_s` after audio really stopped (not after `cancelled`/`failed`),
- not at all for a `speak` that failed (`error` with `reply_to` = the speak id and code
  `audio_failed` or `command_failed`),
- with failsafes: each pending utterance expires at the estimated queue end (refreshed with the
  real `duration` from `speech_started`) plus 5 s, a speaking state longer than 120 s is dropped,
  and `ready`/`shutdown` or a lost connection reset the gate.

In push-to-talk mode with `ptt_interrupts`, pressing the button stops the body's speech and
records regardless of the gate. See `companion/aibody_companion/audio/echo_gate.py`.

## Versioning

- v3, AIBody 0.6.1 revision: the optional HTTP transport is gone, so `speak.url` was removed and
  `speak.audio` is required; `transport` / `link` in events are `file` or `none`. A 0.6.0 plugin
  and a 0.6.1 companion app still work together (0.6.0 used only `audio` over files).
- v3 (AIBody 0.6.0): one plugin on the AI character. The envelope field `atom` on commands, the
  events `companions` / `companion_status` and the routing errors are gone; the body's state comes
  with `ready` / `heartbeat` / `pong`.
- v2 (0.5.0): Client + Companion plugins with an in-VaM bridge.
- v1 (0.2-0.4): Session + Person plugins with character slots.

Additive changes (new optional fields, new types) keep the version. Receivers ignore unknown
fields in events and report unknown command types as errors.

## Body tools (companion <-> xAI, v0.7.4)

The plugin's status fields (`ready` / `heartbeat`) list `expressions`, `gestures`, `poses` and `body_control`. From these
the companion offers the language model the tools `express` (`expression`, `gesture`, enums of the
loaded names) and `pose` (`name`, only when poses exist). A call becomes `expression` / `gesture` /
`pose` commands on this channel; every call is answered (`{"ok": true}` / `{"ok": false, "error"}`).
No tools in `ai.mode` `qa` or with `body_control` false.

