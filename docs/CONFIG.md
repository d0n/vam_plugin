# Shared config file: `Saves/PluginData/AIBody/config.json`

One JSON file, relative to the VaM folder, read by the AIBody plugin **and** the companion app:

```
<VaM>/Saves/PluginData/AIBody/config.json
```

Why there: established plugins keep their settings in their own folder below `Saves/PluginData`
(Timeline: `Saves/PluginData/Timeline/settings.json`, Keybindings: `Saves/PluginData/Keybindings`),
and it is where AIBody's channel folders already are. It is global, not per channel: the channel
is one of the values. Evidence links: [API_AUDIT.md](API_AUDIT.md) ("Config file location").

## Who reads and writes it

| when | plugin | companion app |
|------|--------|---------------|
| file missing | writes it about 2 s after loading (from its UI values) | creates it with the defaults on start |
| plugin added to a scene **without** saved AIBody settings | takes the values from the file once (new scene / re-added plugin) | - |
| scene **with** saved AIBody settings | the scene's values win and are written back | - |
| a value changes in the plugin UI | written back within 1 s (only if something changed) | gets it live as a `config` event (protocol) |
| app start | - | reads channel, mic and engines from the file (`--channel` on the command line wins) |
| paths (`connection.paths`) | read from the file (no UI), on start, channel change and "Reload config.json" | - |

The plugin writes compact JSON in place (FileManagerSecure cannot rename); the app writes the
default file atomically and ignores a file it cannot parse (then defaults, with a warning).
Edit the file while VaM is closed, or remove the plugin's saved settings, if you want the file
to win.

## Schema (version 1)

One object per tab of the plugin window ("Status" has no settings). Machine-readable:
[protocol/schema/config.schema.json](../protocol/schema/config.schema.json), example:
[examples/config.json](../examples/config.json).

| key | type | default | meaning |
|-----|------|---------|---------|
| `version` | int | 1 | schema version |
| `written_by` | string | | who wrote the file last (informational) |
| **`connection`** (tab "Verbindung") | | | |
| `channel` | string | `default` | folder `Saves/PluginData/AIBody/<channel>/` for the message files; letters, digits, `-`, `_` |
| `active` | bool | true | link to the companion app on/off |
| `paths.expressions` | string | `Saves/PluginData/AIBody/expressions.json` | expression presets, relative, below `Saves/` or `Custom/` |
| `paths.gestures` | string | `Saves/PluginData/AIBody/gestures.json` | gestures (Timeline actions), same rules |
| **`engines`** (tab "Engines") | | | |
| `stt`, `llm`, `tts` | string | `null`, `echo`, `tone` | engine names; the app only accepts engines it has |
| **`mic`** (tab "Mikrofon & PTT") | | | captured by the companion app |
| `enabled` | bool | true | microphone on |
| `mode` | `vad` / `ptt` | `vad` | voice activation or push-to-talk |
| `device` | string | `""` | input device name, empty = system default |
| `vad_threshold` | number 0.001-0.5 | 0.01 | speech level (RMS) |
| `end_silence_ms` | number 200-5000 | 700 | silence that ends an utterance |
| `min_utterance_ms` / `max_utterance_ms` | number | 300 / 20000 | shorter ones are dropped / longer ones cut |
| `echo_tail_s` | number 0-3 | 0.4 | mic stays closed after the body stopped speaking |
| `gain` | number 0.1-8 | 1.0 | input gain |
| `ptt_interrupts` | bool | true | push-to-talk stops the body's speech |
| `level_meter` | bool | true | level meter in the plugin |
| **`body`** (tab "Körper") | | | |
| `speech_volume` | number 0-1 | 1.0 | volume of the head audio |
| `idle_motion` / `idle_intensity` | bool / number 0-1 | true / 0.5 | idle head motion |
| `breathing` / `breaths_per_minute` / `breath_depth` | bool / 4-40 / 0-1 | true / 14 / 0.35 | procedural breathing |
| `breath_morph` | string | `Breath1` | chest morph for breathing |
| **`advanced`** (tab "Erweitert") | | | |
| `file_poll_interval_s` | number 0.02-2 | 0.1 | how often the plugin checks its inbox |
| `verbose_log` | bool | false | debug lines in the VaM log |

The push-to-talk *state* is never saved (only the setting `ptt_interrupts` and `mode`). Unknown
keys are reported and ignored; out-of-range numbers are clamped.
