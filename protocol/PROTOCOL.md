# AIBody protocol, version 1

This is the message format between the **companion app** (the AI's "brain", running outside VaM)
and the **AIBody VaM plugin** (the AI's "body"). Messages are JSON objects. JSON schemas:
[`schema/command.schema.json`](schema/command.schema.json) (companion to plugin) and
[`schema/event.schema.json`](schema/event.schema.json) (plugin to companion).

## Envelope

Every message has:

| field | type   | notes                                                          |
|-------|--------|----------------------------------------------------------------|
| `v`   | int    | protocol version, `1`                                          |
| `type`| string | message type                                                   |
| `id`  | string | unique id. Replies carry `reply_to`.                           |
| `ts`  | number | Unix time in seconds (informational)                           |

A command may set `"ack": true` to get an `ack` event on success. Failures always produce an
`error` event with `reply_to` set to the command id. A transport payload may contain one message
or a JSON array of messages.

## Transports

The plugin has three modes: **Auto** (default: HTTP primary, files as fallback), **HTTP only** and
**File only**. The companion has the same three (`--transport auto|http|file`).

### HTTP (primary, needs "Allow Plugins Network Access")

The companion runs an HTTP server, by default on `127.0.0.1:8765` (plugin settings
"Companion host" / "Companion port", companion `--host` / `--port`). The plugin only uses
`UnityWebRequest`; raw sockets and WebSockets are not available to VaM plugins
(Unity 2018.1 Mono, sandbox), so this is long-polling over HTTP/1.1.

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

### File transport (fallback, no network permission needed)

All paths are relative to the VaM install folder:

```
Saves/PluginData/AIBody/<channel>/inbox/    companion -> plugin (commands)
Saves/PluginData/AIBody/<channel>/outbox/   plugin -> companion (events)
Saves/PluginData/AIBody/<channel>/audio/    speech audio written by the companion
```

- One message (or array) per `*.json` file. File names must sort (ordinal) in send order,
  e.g. `<20 digit timestamp>_<6 digit sequence>.json`.
- The companion writes `name.tmp` and renames it to `name.json` (atomic).
- The plugin cannot rename through `FileManagerSecure`, so it writes `*.json` in place; the
  companion retries files that fail to parse for 2 s before dropping them.
- The reader deletes each file after processing. The companion clears both folders on start.
- The plugin polls every 0.1 s (0.5 s in Auto mode while HTTP is connected). The companion counts
  the plugin as connected over files while it has received an event in the last 5 s.
- `<channel>` defaults to the uid of the Person atom (e.g. `Person`), so several atoms can each
  have their own AI.

In Auto mode both run at once. The plugin sends events over HTTP while connected, otherwise into
the outbox. The companion sends each command over exactly one link: HTTP while the plugin is
connected there, files while the plugin is only heard over files, HTTP (buffered) otherwise.

## Commands (companion -> plugin)

### Body

| type            | fields                                                                 | effect |
|-----------------|------------------------------------------------------------------------|--------|
| `ping`          | -                                                                      | plugin answers `pong` with its status |
| `speak`         | `url` and/or `audio` (one required), `text`, `expression`, `intensity`, `queue` (`append`/`interrupt`), `duration` | queues speech audio, see [Audio delivery](#audio-delivery) |
| `stop_speaking` | -                                                                      | stops playback and clears the queue |
| `expression`    | `name` (required), `intensity` (1), `blend` s (0.4), `hold` s (keep)   | blends to an expression preset |
| `set_morphs`    | `morphs` {name: value} (required), `blend` s, `release_others` bool    | sets raw morph values |
| `reset_morphs`  | `blend` s                                                               | returns all touched morphs to their original values |
| `gesture`       | `name` (required), `duration` s, `amplitude`                           | gesture from `gestures.json`, or built-in head gestures `nod`, `shake`, `tilt` |
| `pose`          | `path` (required)                                                      | loads a pose preset (`.vap`/`.json`, may be inside a `.var`) |
| `trigger`       | `storable` (required) + `action`, or `param` + `value` (+ `value_type`) | calls an action / sets a parameter on any storable of the atom, e.g. another plugin |
| `idle`          | `enabled`, `intensity` 0..1                                            | procedural idle head motion |
| `breathing`     | `enabled`, `rate` breaths/min, `depth`                                 | procedural breathing |

### Microphone feedback

| type         | fields | when |
|--------------|--------|------|
| `config_ack` | `reply_to`, `applied` (`{"mic": {...}}` settings in effect after clamping), `errors` (list of strings), `mic_state` | answer to every `config` event |
| `devices`    | `devices`: list of `{name, index, default, channels, sample_rate}`, `error`, `reply_to` | answer to `list_devices` |
| `mic_state`  | `enabled`, `capturing`, `device`, `mode`, `ptt_active`, `error` | when the microphone state changes, and after `ready` |
| `mic_level`  | `rms` (peak RMS 0..1 since the last message), `speech`, `gate_open` | 5 per second while capturing, if `level_meter` is on |

## Events (plugin -> companion)

| type             | fields                                              | when |
|------------------|-----------------------------------------------------|------|
| `ready`          | status fields (below)                               | after every (re)connect |
| `heartbeat`      | status fields                                       | every 2 s while connected |
| `pong`           | status fields, `reply_to`                           | answer to `ping` |
| `ack`            | `reply_to`, `command`                               | command succeeded and asked for an ack |
| `error`          | `reply_to`, `code`, `message`                       | `bad_json`, `command_failed`, `audio_failed` |
| `speech_started` | `utterance_id`, `duration` (clip length in s)       | the clip really started playing |
| `speech_ended`   | `utterance_id`, `reason`, `queue_length`            | the clip stopped, or a queued one was dropped |
| `gesture_done`   | `name`                                              | a built-in head gesture finished |
| `config`         | `mic` (see below)                                   | after (re)connect and 0.3 s after the last settings change |
| `ptt`            | `active` (bool)                                     | push-to-talk pressed / released |
| `list_devices`   | -                                                   | after (re)connect and on "Refresh device list" |
| `shutdown`       | -                                                   | plugin is stopping its transport |

`speech_ended.reason`: `completed`, `stopped` (stop_speaking / UI), `interrupted` (a
`queue: interrupt` speak or someone else replaced the clip), `cancelled` (was queued, never
played), `failed` (could not be loaded; an `audio_failed` error comes first).

Status fields: `plugin_version`, `protocol`, `atom`, `channel`, `transport`, `link`
(`http`/`file`), `speaking`, `speech_queue`, `expression`, `audio_dir`, `expressions`,
`gestures`.

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

## Audio delivery

The companion writes each TTS clip to its audio folder and sends a `speak` with:

- `url`: `/v1/audio/<file>` when the plugin is reachable over HTTP. The plugin resolves it
  against the companion base URL and downloads it with `UnityWebRequestMultimedia`. This works
  without a shared folder, so `vam_root` is optional for HTTP.
- `audio`: `Saves/PluginData/AIBody/<channel>/audio/<file>` when the companion knows `vam_root`.
  The plugin loads it through `URLAudioClipManager`. Used when there is no `url` or the download
  fails.

The plugin keeps an ordered queue (`queue: append`, default) and prefetches the next two clips
while one plays. `queue: interrupt` stops the current clip (`speech_ended` reason
`interrupted`), cancels the queue and plays the new clip next. `stop_speaking` stops and cancels
everything. Playback goes to the Person's head audio source, so VaM's lip sync animates the
mouth. The plugin's "Speech volume" setting applies to every clip.

## Echo handling

The companion keeps its microphone closed:

- from sending `speak` until that utterance's `speech_ended`, for every queued utterance,
- for `echo_tail_s` after audio really stopped (not after `cancelled`/`failed`),
- with failsafes: each pending utterance expires at the estimated queue end (refreshed with the
  real `duration` from `speech_started`) plus 5 s, a speaking state longer than 120 s is dropped,
  and `ready`/`shutdown` or a lost connection reset the gate.

In push-to-talk mode with `ptt_interrupts`, pressing the button stops the body's speech and
records regardless of the gate. See `companion/aibody_companion/audio/echo_gate.py`.

## Versioning

Additive changes (new optional fields, new types) keep `v: 1`. Receivers ignore unknown fields in
events and report unknown command types as errors.
