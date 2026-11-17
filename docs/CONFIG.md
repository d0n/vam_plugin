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
| app start | - | reads channel, mic, engines and `ai` from the file (`--channel` on the command line wins); adds a missing `ai` section with its defaults |
| `ai` section | never edits it, keeps it when writing the file | reads it (persona, language, fallback, engine settings) |
| paths (`connection.paths`) | read from the file (no UI), on start, channel change and "Reload config.json" | - |

The plugin writes compact JSON in place (FileManagerSecure cannot rename); the app writes the
default file atomically and ignores a file it cannot parse (then defaults, with a warning).

**Numbers and true/false as strings:** the plugin writes with VaM's SimpleJSON, which stores every
number and boolean as a string (`"gain":"2.5"`, `"active":"true"`), like VaM scene files do. The
app accepts both forms everywhere (config.json and the plugin's events); so does the schema.
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
| **`ai`** (companion app only, no tab) | | | the plugin keeps this section unchanged |
| `persona` | string | friendly character … | persona / system prompt of the language model (xAI: `instructions`, sent with the first request of a conversation) |
| `language` | string | `auto` | `auto` or a language code (`de`, `en`, …): STT bias (`language`), TTS language |
| `fallback.stt` / `.llm` / `.tts` | string | `null` / `echo` / `tone` | runs when the selected engine has no key or a request fails |
| `xai.base_url` | string | `https://api.x.ai/v1` | |
| `xai.key_file` | string | `""` | **path** of a file holding the xAI key (absolute, or relative to your home folder). `XAI_API_KEY` wins |
| `xai.model` | string | `grok-4.7` | language model (docs.x.ai recommends Grok 4.7 for chat; `grok-4.20-0309-non-reasoning` may answer faster) |
| `xai.max_output_tokens` | int 16-8000 | 400 | keeps spoken answers short |
| `xai.stt_model` | string | `grok-voice-transcribe-2.0` | speech-to-text model |
| `xai.voice` | string | `eve` | TTS voice (`GET /v1/tts/voices` lists them; custom voice ids work too) |
| `xai.speed` | number 0.7-1.5 | 1.0 | TTS speed |
| `xai.sample_rate` | 8000 … 48000 | 24000 | TTS sample rate (raw PCM, wrapped into WAV) |
| `xai.timeout_s` | number 5-600 | 60 | request timeout |
| `elevenlabs.base_url` | string | `https://api.elevenlabs.io/v1` | |
| `elevenlabs.key_file` | string | `""` | **path** of a file holding the ElevenLabs key. `ELEVENLABS_API_KEY` wins |
| `elevenlabs.voice_id` | string | `JBFqnCBsd6RMkjVDRZzb` | voice (the example voice of the ElevenLabs docs; pick your own in their voice library) |
| `elevenlabs.model_id` | string | `eleven_multilingual_v2` | TTS model (the API default) |
| `elevenlabs.output_format` | `pcm_16000` … `pcm_48000` | `pcm_24000` | raw PCM, wrapped into WAV; 44.1/48 kHz need an ElevenLabs Pro plan |
| `elevenlabs.timeout_s` | number 5-600 | 60 | request timeout |

The push-to-talk *state* is never saved (only the setting `ptt_interrupts` and `mode`). Unknown
keys are reported and ignored; out-of-range numbers are clamped.

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

**Plugging in a key** (example ElevenLabs, the same for xAI):

1. Either set the environment variable before starting the app, e.g. in PowerShell
   `$env:ELEVENLABS_API_KEY = "<key>"` (or permanently via *System > Environment Variables*),
2. or save the key alone in a text file outside the repository and the VaM folder, e.g.
   `C:\Users\<you>\keys\elevenlabs.txt`, and enter its path in `config.json`:
   `"ai": { "elevenlabs": { "key_file": "C:/Users/<you>/keys/elevenlabs.txt" } }`
   (a relative path counts from your home folder, e.g. `keys/elevenlabs.txt`).
3. Select **Text-to-speech: elevenlabs** in the plugin's Engines tab. The status line there
   changes from "nicht konfiguriert" to "bereit (…)" - a key file within 10 s, an environment
   variable after restarting the app.

The key itself never goes into `config.json` (a `key_file` value that looks like a key is
refused) or into the log. Without a key nothing is blocked: the engine is "nicht konfiguriert"
and the fallback runs.

**Real API check** (once keys exist; everything is only tested against a fake server so far):
type a line into the companion app with `llm: xai`, `tts: xai` or `elevenlabs`, and watch its log
for `Engine ... bereit`, the spoken sentences and any `failed (...)` warnings.

## What xAI offers for speech (checked on docs.x.ai, 17.11.2026)

- **Speech to text: yes** - `POST /v1/stt` (batch, file upload) and `wss://api.x.ai/v1/stt`
  (streaming), model `grok-voice-transcribe-2.0`.
  <https://docs.x.ai/developers/model-capabilities/audio/speech-to-text>
- **Text to speech: yes** - `POST /v1/tts` (and `wss://api.x.ai/v1/tts` streaming), voices such
  as `eve` / `ara` / `rex`, codecs mp3/wav/pcm/mulaw/alaw.
  <https://docs.x.ai/developers/model-capabilities/audio/text-to-speech>
- **Speech to speech:** `wss://api.x.ai/v1/realtime` (Grok voice). Not used: it would replace the
  STT -> LLM -> TTS pipeline and needs a WebSocket client.
  <https://docs.x.ai/developers/model-capabilities/audio/voice>
- Language model: `POST /v1/responses` with `stream: true`; `instructions` cannot be combined with
  `previous_response_id` (the stored system prompt is reused), so the persona goes out with the
  first request of a conversation only.
  <https://docs.x.ai/developers/rest-api-reference/inference/responses>
