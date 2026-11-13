# AIBody protocol, version 1

This is the message format between the **companion app** (the AI's "brain", running outside VaM)
and the **AIBody VaM plugin** (the AI's "body"). Messages are JSON objects. JSON schemas:
[`schema/command.schema.json`](schema/command.schema.json) and
[`schema/event.schema.json`](schema/event.schema.json).

## Envelope

Every message has:

| field | type   | notes                                                          |
|-------|--------|----------------------------------------------------------------|
| `v`   | int    | protocol version, `1`                                          |
| `type`| string | command or event type                                          |
| `id`  | string | unique id. Events that answer a command carry `reply_to`.      |
| `ts`  | number | Unix time in seconds (informational)                           |

A command may set `"ack": true` to get an `ack` event on success. Failures always produce an
`error` event with `reply_to` set to the command id.

A transport payload may contain one message or a JSON array of messages.

## Transports

### File transport (default, no network permission needed)

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
- The reader deletes each file after processing.
- `<channel>` defaults to the uid of the Person atom (e.g. `Person`), so several atoms can each
  have their own AI.

### HTTP transport (needs "Allow Plugins Network Access")

The companion runs a server on `127.0.0.1:8765`; the plugin polls it (~10x per second).

```
GET  /v1/health
GET  /v1/commands?channel=<channel>&after=<seq>   -> {"commands": [...], "last": <seq>}
POST /v1/events?channel=<channel>                 body: one event object (or an array)
```

Commands older than 10 s are not delivered, so a plugin that starts late does not replay
old speech. Audio files still go through the shared `audio/` folder.

## Commands (companion -> plugin)

| type            | fields                                                                 | effect |
|-----------------|------------------------------------------------------------------------|--------|
| `ping`          | -                                                                      | plugin answers `pong` with its status |
| `speak`         | `audio` (required), `text`, `expression`, `intensity`                  | loads the audio file and plays it through the head audio source (built-in lip sync). The command `id` becomes the `utterance_id`. Interrupts current speech. |
| `stop_speaking` | -                                                                      | stops playback, `speech_ended` with `reason: "stopped"` |
| `expression`    | `name` (required), `intensity` (1), `blend` s (0.4), `hold` s (keep)   | blends to an expression preset |
| `set_morphs`    | `morphs` {name: value} (required), `blend` s, `release_others` bool    | sets raw morph values |
| `reset_morphs`  | `blend` s                                                               | returns all touched morphs to their original values |
| `gesture`       | `name` (required), `duration` s, `amplitude`                           | gesture from `gestures.json`, or built-in head gestures `nod`, `shake`, `tilt` |
| `pose`          | `path` (required)                                                      | loads a pose preset (`.vap`/`.json`, may be inside a `.var`) |
| `trigger`       | `storable` (required) + `action`, or `param` + `value` (+ `value_type`) | calls an action / sets a parameter on any storable of the atom, e.g. another plugin |
| `idle`          | `enabled`, `intensity` 0..1                                            | procedural idle head motion |
| `breathing`     | `enabled`, `rate` breaths/min, `depth`                                 | procedural breathing |

Audio paths are relative to the VaM folder with forward slashes, e.g.
`Saves/PluginData/AIBody/Person/audio/utt-123.wav`. WAV is the safe choice.

## Events (plugin -> companion)

| type             | fields                                              | when |
|------------------|-----------------------------------------------------|------|
| `ready`          | status fields (below)                               | plugin started / reconnected |
| `heartbeat`      | status fields                                       | every 2 s |
| `pong`           | status fields, `reply_to`                           | answer to `ping` |
| `ack`            | `reply_to`, `command`                               | command succeeded and asked for an ack |
| `error`          | `reply_to`, `code`, `message`                       | `bad_json`, `command_failed`, `audio_failed` |
| `speech_started` | `utterance_id`                                      | audio actually started playing |
| `speech_ended`   | `utterance_id`, `reason` (`completed`/`stopped`/`interrupted`) | audio stopped |
| `gesture_done`   | `name`                                              | a built-in head gesture finished |
| `shutdown`       | -                                                   | plugin is stopping its transport |

Status fields: `plugin_version`, `protocol`, `atom`, `channel`, `transport`, `speaking`,
`expression`, `audio_dir`, `expressions` (preset names), `gestures` (gesture names).

## Echo handling

The companion keeps its microphone closed from the moment it sends `speak` until
`speech_ended` plus a short tail (0.4 s). It reopens early on `error` with
`code: "audio_failed"`, and after a failsafe timeout if events are lost. See
`companion/aibody_companion/audio/echo_gate.py`.

## Versioning

Additive changes (new optional fields, new types) keep `v: 1`. Receivers ignore unknown
fields in events and report unknown command types as errors.
