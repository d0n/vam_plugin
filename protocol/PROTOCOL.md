# AIBody protocol, version 1

This is the message format between the **companion app** (the AI's "brain", running outside VaM)
and the two AIBody VaM plugins (the AI's "body"). Messages are JSON objects. JSON schemas:
[`schema/command.schema.json`](schema/command.schema.json) (companion to VaM) and
[`schema/event.schema.json`](schema/event.schema.json) (VaM to companion).

## Parts

```
companion  <-- files in Saves/PluginData/AIBody/<channel>/ -->  AIBody Session plugin     (Session Plugins)
                                                                  |                |   string params,
                                                       "AIBody Inbox/Outbox"  "AIBody2 Inbox/Outbox"  in-process
                                                                  v                v
                                              AIBody Person (slot person1)   AIBody Person 2 (slot person2)
                                              on character 1                 on character 2
```

- **Session plugin** (`d0n.AIBodySession`, `AIBody/AIBodySession.cslist`, loaded in Main UI >
  Session Plugins): the only part that talks to the companion. Owns the transport, channel,
  microphone menu, engine menus and connection status. Survives scene changes; not tied to any atom.
- **Person plugin, character 1** (`d0n.AIBodyPerson`, `AIBody/AIBodyPerson.cslist`, script
  `AIBody.AIBodyPersonPlugin`, slot **`person1`**) and **Person plugin, character 2**
  (`d0n.AIBodyPerson2`, `AIBody2/AIBodyPerson2.cslist`, script `AIBody2.AIBodyPerson2Plugin`, slot
  **`person2`**), each loaded on its character's Plugins tab: speech with lip sync, expressions,
  morphs, gestures, poses, idle and breathing. No I/O of their own. Both are built from the same
  sources (`src/Person`); `tools/make_person2.py` generates the person2 variant with its own
  namespace, class name, slot and param names, so they are two distinct scripts.

## Envelope

Every message has:

| field | type   | notes                                                          |
|-------|--------|----------------------------------------------------------------|
| `v`   | int    | protocol version, `1`                                          |
| `type`| string | message type                                                   |
| `id`  | string | unique id. Replies carry `reply_to`.                           |
| `ts`  | number | Unix time in seconds (informational)                           |
| `slot`| string | optional, `person1` or `person2`. Body commands: target character slot. Events from a Person: its slot. |
| `atom`| string | optional. Body commands: target Person atom uid. Events from a Person: its atom uid. |

A command may set `"ack": true` to get an `ack` event on success. Failures always produce an
`error` event with `reply_to` set to the command id. A transport payload may contain one message
or a JSON array of messages.

## Routing by character slot (Session plugin <-> Person plugins)

**Body commands** are `speak`, `stop_speaking`, `expression`, `set_morphs`, `reset_morphs`,
`gesture`, `pose`, `trigger`, `idle` and `breathing`. The Session plugin forwards each to exactly
one Person plugin, chosen strictly:

1. `slot` given: that slot's plugin. If `atom` is also given, the slot's plugin must be on that
   atom.
2. Only `atom` given: the plugin on that atom (whichever slot it is).
3. Neither: the Session plugin's **Default slot** setting (default `person1`).

A slot is **usable** only if exactly one atom hosts its plugin and that atom hosts no other AIBody
Person plugin. Otherwise the slot is in **conflict** and nothing is delivered to it. **A command is
never redirected to another character**: if the target is not usable, the Session plugin answers
`error` with `reply_to` = command id, `slot`/`atom` as requested and one of these codes:

| code            | meaning |
|-----------------|---------|
| `no_person`     | the slot's plugin (or any plugin on `atom`) is not in the scene |
| `slot_conflict` | the slot's plugin is on several atoms, or the atom hosts both slots |
| `slot_mismatch` | `slot` and `atom` both given, but the slot's plugin is on another atom |
| `unknown_slot`  | `slot` is not `person1` / `person2` |
| `wrong_slot`    | (from the Person plugin) a command for another slot reached it; refused |

Before delivery the Session plugin sets `slot` on the command; each Person plugin refuses commands
whose `slot` is not its own (`wrong_slot`), as a second line of defense.

All other commands (`ping`, `companion_heartbeat`, `config_ack`, `devices`, `mic_state`,
`mic_level`) are handled by the Session plugin itself.

The companion always sets `slot` (per call, else its `default_slot` config / `--slot`, else the
Session's `default_slot`, else `person1`) and never guesses a slot from which characters are
present. It keeps the Persons and conflicts from `ready`, `heartbeat` and `persons`.

**Bridge.** The plugins are compiled separately by VaM, so they cannot call each other's C# types.
They use only VaM's public scene API:

- Each Person plugin registers three string params named after its slot:
  - slot `person1`: `AIBody Inbox`, `AIBody Outbox`, `AIBody Person Version`
  - slot `person2`: `AIBody2 Inbox`, `AIBody2 Outbox`, `AIBody2 Person Version`
- Every second the Session plugin scans `SuperController.singleton.GetAtoms()` and, on each atom,
  the storables whose id starts with `plugin#`, for the Inbox/Outbox pair of each slot. Added or
  removed Persons, conflicts and scene changes are picked up by the next scan; a change is
  reported to the companion as a `persons` event.
- **Command:** the Session sets the slot's Inbox to the command JSON. The Person handles it inside
  the param's change callback (synchronously) and resets the value to `""`.
- **Events:** the Person appends events to a JSON array in its Outbox (at most 100; the oldest
  are dropped). Every frame the Session reads every Outbox (also of conflicting plugins), resets it
  to `""`, sets `slot` (from the param pair it came from) and `atom`, and forwards the events.
- The Person clears a stale outbox on start and shows "Session plugin: NOT FOUND" in its status if
  nobody drains the outbox for 3 s.

No files, sockets or reflection are involved, so the bridge works with every sandbox setting.

## Transports (companion <-> Session plugin)

### File transport (default, the only one in the default build)

All paths are relative to the VaM install folder:

```
Saves/PluginData/AIBody/<channel>/inbox/    companion -> Session plugin (commands)
Saves/PluginData/AIBody/<channel>/outbox/   Session plugin -> companion (events)
Saves/PluginData/AIBody/<channel>/audio/    speech audio written by the companion
```

- The plugin side uses only `FileManagerSecure` (writes are allowed below `Saves/PluginData`).
- One message (or array) per `*.json` file. File names must sort (ordinal) in send order,
  e.g. `<20 digit timestamp>_<6 digit sequence>.json`.
- The companion writes `name.tmp` and renames it to `name.json` (atomic).
- The plugin cannot rename through `FileManagerSecure`, so it writes `*.json` in place; the
  companion retries files that fail to parse for 2 s before dropping them.
- The reader deletes each file after processing. The companion clears both folders on start.
- The plugin polls every 0.1 s ("File poll interval"). It sends `ready`, its `config` and
  `list_devices` on start and a `heartbeat` every 2 s.
- The companion counts the plugin as connected while it received an event in the last 5 s, and
  while connected sends `companion_heartbeat` every 2 s. The plugin counts the companion as
  connected while a `companion_heartbeat` arrived in the last 6 s. A new `session` id in
  `companion_heartbeat` means the companion restarted: the plugin sends `ready` and `config` again.
- `<channel>` defaults to `default` (Session plugin "Channel", companion `channel`). Both sides
  must use the same value. One Session plugin and one channel serve all Persons in the scene.

### HTTP (optional build only)

VaM 1.22 plugins that use `UnityEngine.Networking` / `UnityWebRequest` may be refused by the
sandbox, so the default build contains no network code at all. `src/Optional/HttpTransport.cs`
and `AutoTransport.cs` are compiled only with `#define AIBODY_HTTP` (see the README). With that
build the Session plugin offers "Auto (HTTP, file fallback)" and "HTTP only", and the companion
`--transport http|auto` serves:

```
GET  /v1/health
GET  /v1/hello?channel=<c>&plugin=<version>        -> {"session", "protocol", "server", "channel", "long_poll_max"}
GET  /v1/commands?channel=<c>&after=<seq>&wait=<s> -> {"commands": [...], "last": <seq>, "session": "..."}
POST /v1/events?channel=<c>                        body: JSON array of events (a single object is accepted)
GET  /v1/audio/<file>                              speech audio (wav/ogg/mp3) from the companion's audio folder
```

Connection life cycle (plugin side):

1. **hello**: the plugin sends its version and gets the server `session` id. A different session
   id than last time means the companion restarted: the plugin resets `after` to 0.
2. **connected**: the plugin keeps one long-poll open (`wait=10`, request timeout 15 s). The
   server answers as soon as a command newer than `after` exists, or with an empty list after
   `wait` seconds (max 25). `last` becomes the next `after`. Events are POSTed in batches of up
   to 50 as they occur.
3. **any failure** (network error, HTTP error, invalid JSON): the plugin aborts open requests,
   waits with exponential backoff (0.5 s doubling up to 10 s, ±20 % jitter) and starts again
   with hello. Events queued while offline are dropped on reconnect (they are stale).
4. After every (re)connect, companion restart or switch between HTTP and files, the plugin sends
   `ready`, its full `config` and `list_devices`. While connected it sends a `heartbeat` every 2 s.

Server side: the companion counts the plugin as connected while a long-poll is open or it was
seen in the last 5 s. Commands older than 10 s are not delivered (no replay of old speech after a
late start). Requests for another channel get `409`. If `after` is larger than the server's last
sequence number (plugin talked to an earlier session), the server treats it as 0.

## Commands (companion -> VaM)

### Body (forwarded to one Person plugin by `slot` / `atom`)

| type            | fields                                                                 | effect |
|-----------------|------------------------------------------------------------------------|--------|
| `speak`         | `url` and/or `audio` (one required), `text`, `expression`, `intensity`, `queue` (`append`/`interrupt`), `duration` | queues speech audio, see [Audio delivery](#audio-delivery) |
| `stop_speaking` | -                                                                      | stops playback and clears the queue |
| `expression`    | `name` (required), `intensity` (1), `blend` s (0.4), `hold` s (keep)   | blends to an expression preset |
| `set_morphs`    | `morphs` {name: value} (required), `blend` s, `release_others` bool    | sets raw morph values |
| `reset_morphs`  | `blend` s                                                               | returns all touched morphs to their original values |
| `gesture`       | `name` (required), `duration` s, `amplitude`                           | gesture from `gestures.json`, or built-in head gestures `nod`, `shake`, `tilt` |
| `pose`          | `path` (required)                                                      | loads a pose preset (`.vap`/`.json`, may be inside a `.var`) |
| `trigger`       | `storable` (required) + `action`, or `param` + `value` (+ `value_type`) | calls an action / sets a parameter on any storable of the target atom, e.g. another plugin |
| `idle`          | `enabled`, `intensity` 0..1                                            | procedural idle head motion |
| `breathing`     | `enabled`, `rate` breaths/min, `depth`                                 | procedural breathing |

### Session

| type                  | fields | effect |
|-----------------------|--------|--------|
| `ping`                | -      | Session plugin answers `pong` with its status |
| `companion_heartbeat` | `session` (required), `version`, `engines_available` (`{"stt": [...], "llm": [...], "tts": [...]}`), `mic_capturing` | companion liveness; fills the engine menus |

### Microphone feedback (Session plugin)

| type         | fields | when |
|--------------|--------|------|
| `config_ack` | `reply_to`, `applied` (`{"mic": {...}, "engines": {...}}` settings in effect after clamping), `errors` (list of strings), `mic_state` | answer to every `config` event |
| `devices`    | `devices`: list of `{name, index, default, channels, sample_rate}`, `error`, `reply_to` | answer to `list_devices` |
| `mic_state`  | `enabled`, `capturing`, `device`, `mode`, `ptt_active`, `error` | when the microphone state changes, and after `ready` |
| `mic_level`  | `rms` (peak RMS 0..1 since the last message), `speech`, `gate_open` | 5 per second while capturing, if `level_meter` is on |

## Events (VaM -> companion)

From the Session plugin:

| type             | fields                                              | when |
|------------------|-----------------------------------------------------|------|
| `ready`          | status fields (below)                               | after start, reconnect or companion restart |
| `heartbeat`      | status fields                                       | every 2 s |
| `pong`           | status fields, `reply_to`                           | answer to `ping` |
| `persons`        | `persons`, `conflicts`, `default_slot`, `default_atom` | a Person plugin appeared or disappeared, a conflict changed, or the default slot changed |
| `error`          | `reply_to`, `code`, `message`, (`slot`, `atom`)     | `bad_json`, `command_failed`, routing errors (`no_person`, `slot_conflict`, `slot_mismatch`, `unknown_slot`) |
| `config`         | `mic` (see below), `engines` (`{"stt", "llm", "tts"}`) | after (re)connect and 0.3 s after the last settings change |
| `ptt`            | `active` (bool)                                     | push-to-talk pressed / released |
| `list_devices`   | -                                                   | after (re)connect and on "Refresh mic devices" |
| `shutdown`       | -                                                   | plugin is stopping its transport |

From a Person plugin (forwarded by the Session plugin, always with `slot` and `atom`):

| type             | fields                                              | when |
|------------------|-----------------------------------------------------|------|
| `person_status`  | `plugin_version`, `speaking`, `speech_queue`, `expression`, `expressions`, `gestures` | every 2 s |
| `ack`            | `reply_to`, `command`                               | command succeeded and asked for an ack |
| `error`          | `reply_to`, `code`, `message`                       | `bad_json`, `command_failed`, `audio_failed`, `wrong_slot` |
| `speech_started` | `utterance_id`, `duration` (clip length in s)       | the clip really started playing |
| `speech_ended`   | `utterance_id`, `reason`, `queue_length`            | the clip stopped, or a queued one was dropped |
| `gesture_done`   | `name`                                              | a built-in head gesture finished |

`speech_ended.reason`: `completed`, `stopped` (stop_speaking / UI), `interrupted` (a
`queue: interrupt` speak or someone else replaced the clip), `cancelled` (was queued, never
played), `failed` (could not be loaded; an `audio_failed` error comes first).

Session status fields: `role` (`session`), `plugin_version`, `protocol`, `channel`, `transport`,
`audio_dir`, `default_slot`, `default_atom` (atom of the default slot or `""`), `persons` (usable
slots: list of `{slot, atom, plugin_version}`), `conflicts` (list of `{slot, atoms}`).

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

`stt`, `llm`, `tts`: engine names picked in the Session plugin's menus. The companion accepts only
names it has implemented (listed in `companion_heartbeat.engines_available`) and reports others
in `config_ack.errors`. Implemented so far: `null`, `echo`, `tone` (mock engines).

## Audio delivery

The companion writes each TTS clip to `Saves/PluginData/AIBody/<channel>/audio/` (so it needs
`vam_root`) and sends a `speak` with:

- `audio`: `Saves/PluginData/AIBody/<channel>/audio/<file>`, relative to the VaM folder. The
  Person plugin loads it with VaM's own `URLAudioClipManager.QueueClip` (no `UnityWebRequest` in
  plugin code) and plays the resulting `NamedAudioClip` with the head `AudioSourceControl.PlayNow`,
  so VaM's lip sync animates the mouth.
- `url`: only with the optional HTTP build (`/v1/audio/<file>`, downloaded with
  `UnityWebRequestMultimedia`). The default Person plugin ignores it.

The Person plugin keeps an ordered queue (`queue: append`, default) and prefetches the next two
clips while one plays. `queue: interrupt` stops the current clip (`speech_ended` reason
`interrupted`), cancels the queue and plays the new clip next. `stop_speaking` stops and cancels
everything. The Person plugin's "Speech volume" setting applies to every clip.

## Echo handling

The companion keeps its microphone closed:

- from sending `speak` until that utterance's `speech_ended`, for every queued utterance,
- for `echo_tail_s` after audio really stopped (not after `cancelled`/`failed`),
- not at all for a `speak` that was not delivered (routing `error`: `no_person`, `slot_conflict`,
  `slot_mismatch`, `unknown_slot`, `wrong_slot`),
- with failsafes: each pending utterance expires at the estimated queue end (refreshed with the
  real `duration` from `speech_started`) plus 5 s, a speaking state longer than 120 s is dropped,
  and `ready`/`shutdown` or a lost connection reset the gate.

In push-to-talk mode with `ptt_interrupts`, pressing the button stops the body's speech and
records regardless of the gate. See `companion/aibody_companion/audio/echo_gate.py`.

## Versioning

Additive changes (new optional fields, new types) keep `v: 1`. Receivers ignore unknown fields in
events and report unknown command types as errors.
