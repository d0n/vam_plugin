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
| `ai` section | sets only its tab controls (`mode`, `proactive.enabled` / `idle_seconds`, `realtime.send_while_speaking` / `voice`, `xai.voice`, `xai.key_file` / `elevenlabs.key_file` when set), keeps the rest when writing the file; an empty key file field takes the path from the file on every start | reads it (persona, language, fallback, engine settings); the tab controls also arrive live in the `config` event |
| paths (`connection.paths`) | read from the file (no UI), on start, channel change and **Reload Config JSON** (tab *Config*); `paths.audio` is kept unchanged | `paths.audio`: where it writes the speech WAVs |
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
the tabs one to one (kept for compatibility with existing files): `connection` = tab *Post*
(+ *Voice Mode* **Active**), `engines` = tab *AI*, `mic` = tab *Client Character*, `body` = tab
*AI Character*, `advanced` = tab *Erweitert*, `ai` = companion settings plus the tab controls named
below. Machine-readable:
[protocol/schema/config.schema.json](../protocol/schema/config.schema.json), example:
[examples/config.json](../examples/config.json).

| key | type | default | meaning |
|-----|------|---------|---------|
| `version` | int | 1 | schema version |
| `written_by` | string | | who wrote the file last (informational) |
| **`connection`** (tab "Post", **Active** on "Voice Mode") | | | |
| `channel` | string | `default` | folder `Saves/PluginData/AIBody/<channel>/` for the message files; letters, digits, `-`, `_` |
| `active` | bool | true | link to the companion app on/off |
| `paths.expressions` | string | `Saves/PluginData/AIBody/expressions.json` | expression presets, relative, below `Saves/` or `Custom/` |
| `paths.gestures` | string | `Saves/PluginData/AIBody/gestures.json` | gestures (Timeline actions), same rules |
| `paths.audio` | string | `""` | folder for the companion's speech WAVs, relative, below `Saves/` or `Custom/`. `""` = automatic: `Custom/Sounds/AIBody/<channel>`; if VaM cannot load a WAV there (plugin error `audio_failed`), the app switches once to `Saves/PluginData/AIBody/<channel>/audio` and sends the speech again (status box: red note). A fixed folder turns the switch off |
| **`engines`** (tab "AI") | | | |
| `stt`, `llm`, `tts` | string | `null`, `echo`, `tone` | engine names; the app only accepts engines it has |
| **`mic`** (tab "Client Character", section Microphone) | | | captured by the companion app |
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
| **`body`** (tab "AI Character") | | | |
| `speech_volume` | number 0-1 | 1.0 | volume of the head audio |
| `body_control` | bool | true | **Body control**: false = speech only; expression / morph / gesture / pose / trigger commands are ignored |
| `idle_motion` / `idle_intensity` | bool / number 0-1 | true / 0.5 | idle head motion |
| `breathing` / `breaths_per_minute` / `breath_depth` | bool / 4-40 / 0-1 | true / 14 / 0.35 | procedural breathing |
| `breath_morph` | string | `Breath1` | chest morph for breathing |
| **`advanced`** (tab "Erweitert") | | | |
| `file_poll_interval_s` | number 0.02-2 | 0.1 | how often the plugin checks its inbox |
| `verbose_log` | bool | false | debug lines in the VaM log |
| **`ai`** (companion app) | | | the plugin sets only `mode`, `proactive.enabled`, `proactive.idle_seconds`, `realtime.send_while_speaking`, `realtime.voice`, `xai.voice` and (when its field is not empty) `xai.key_file` / `elevenlabs.key_file`; it keeps the rest of the section |
| `mode` | `qa` / `auto` / `realtime` / `chain` | `qa` | tab *AI Character* **AI mode** (*Voice Mode* > **Einfacher Q&A-Modus** sets `qa`). `qa` = simple Q&A: STT -> LLM -> TTS with `xai` instead of the offline test engines when an xAI key exists, speech only, no proactive remarks. `auto` = realtime when an xAI key exists, else chain; with `engines.tts` = `elevenlabs` auto picks chain. `realtime` = Grok Voice speech-to-speech; `chain` = STT -> LLM -> TTS (exactly the engines above). If realtime cannot connect, or gives no answer 12 s after the user spoke, chain runs (reported). Files from 0.7.1 keep their value (`auto`) |
| `realtime.url` | string | `wss://api.x.ai/v1/realtime` | |
| `realtime.model` | string | `grok-voice-latest` | voice model (query parameter `model`) |
| `realtime.voice` | string | `eve` | tab *AI Character* **Voice** (`eve`, `ara`, `rex`, `sal`, `leo` or a custom voice id from this file); also sets `xai.voice`. Changing it reconnects realtime |
| `realtime.sample_rate` | 8000 … 48000 | 24000 | answer audio rate (16-bit PCM, written as WAV segments) |
| `realtime.speed` | number 0.7-1.5 | 1.0 | speaking speed |
| `realtime.reasoning_effort` | `none` / `high` | `none` | `none` answers faster; `high` is the API default |
| `realtime.send_while_speaking` | bool | false | tab *Client Character* **Voice barge-in (headphones)**: the mic keeps streaming while the body talks, so you can interrupt by voice. Only with headphones - with speakers the AI hears itself |
| `realtime.first_segment_s` | number 0.3-5 | 1.2 | the first audio segment is played as soon as a sentence ended after this much audio |
| `realtime.max_segment_s` | number 1-20 | 6.0 | longer stretches without a sentence end are cut at the quietest spot |
| `realtime.connect_timeout_s` | number 3-60 | 15 | |
| `proactive.enabled` | bool | true | tab *AI* **Proactive**: the AI may speak up by itself after a silence |
| `proactive.idle_seconds` | number 15-3600 | 90 | tab *AI* **Proactive idle (s)** (slider 15-900): silence (nobody spoke) before a nudge; doubles (up to 8x) while the user stays quiet |
| `proactive.prompt` | string | "The user has been quiet … answer with exactly [silent] …" | note sent with each nudge; the AI may answer `[silent]`, then nothing is played |
| `persona` | string | friendly character … | persona / system prompt of the language model (xAI: `instructions`, sent with the first request of a conversation) |
| `language` | string | `auto` | `auto` or a language code (`de`, `en`, …): STT bias (`language`), TTS language |
| `fallback.stt` / `.llm` / `.tts` | string | `null` / `echo` / `tone` | runs when the selected engine has no key or a request fails |
| `xai.base_url` | string | `https://api.x.ai/v1` | |
| `xai.key_file` | string | `""` | tab *AI* **xAI key file**: **path** of a file holding the xAI key (absolute, or relative to your home folder). `XAI_API_KEY` wins |
| `xai.model` | string | `grok-4.7` | language model (docs.x.ai recommends Grok 4.7 for chat; `grok-4.20-0309-non-reasoning` may answer faster) |
| `xai.max_output_tokens` | int 16-8000 | 400 | keeps spoken answers short |
| `xai.stt_model` | string | `grok-voice-transcribe-2.0` | speech-to-text model |
| `xai.voice` | string | `eve` | TTS voice (`GET /v1/tts/voices` lists them; custom voice ids work too) |
| `xai.speed` | number 0.7-1.5 | 1.0 | TTS speed |
| `xai.sample_rate` | 8000 … 48000 | 24000 | TTS sample rate (raw PCM, wrapped into WAV) |
| `xai.timeout_s` | number 5-600 | 60 | request timeout |
| `elevenlabs.base_url` | string | `https://api.elevenlabs.io/v1` | |
| `elevenlabs.key_file` | string | `""` | tab *AI* **ElevenLabs key file**: **path** of a file holding the ElevenLabs key. `ELEVENLABS_API_KEY` wins |
| `elevenlabs.voice_id` | string | `JBFqnCBsd6RMkjVDRZzb` | voice (the example voice of the ElevenLabs docs; pick your own in their voice library) |
| `elevenlabs.model_id` | string | `eleven_multilingual_v2` | TTS model (the API default) |
| `elevenlabs.output_format` | `pcm_16000` … `pcm_48000` | `pcm_24000` | raw PCM, wrapped into WAV; 44.1/48 kHz need an ElevenLabs Pro plan |
| `elevenlabs.timeout_s` | number 5-600 | 60 | request timeout |

The push-to-talk *state* is never saved (only the setting `ptt_interrupts` and `mode`). Unknown
keys are reported and ignored; out-of-range numbers are clamped.

## Modes: simple Q&A, realtime voice and chain

**Simple Q&A** (`ai.mode` `qa`, the default): the chain below, made as hard to get wrong as
possible. With an xAI key (environment `XAI_API_KEY` or a key file) the offline test engines
(`null` / `echo` / `tone`) are replaced by `xai`, so STT `xai` -> Grok (streamed, split into
sentences, the first sentence is spoken while the rest is still written) -> TTS `xai` -> WAV ->
`speak` -> head audio; engines picked explicitly (e.g. TTS `elevenlabs`) stay. Expression /
gesture tags in the answer are dropped (speech only); proactive remarks are paused. Typed text in
the companion console takes the same path without speech to text. Every step reports to the
status box (heartbeat `turn`): `Gehört: …`, `Antwort (n Satz/Sätze, xai -> xai): …`,
`Nichts verstanden …`, `Spracherkennung-Fehler: …`, `Sprachmodell-Fehler: … - Ersatzantwort` (a
short spoken notice instead of the answer), `Sprachausgabe-Fehler: … - Ersatzton (tone)` (the
sentence is played as a tone). Without a key the test engines run and the mode status says so.

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
up ("Realtime aus: keine Antwort …") until **API Reconnect** or a new AI mode, and the chain
answers (repeat the question). The tab *AI* shows the active mode ("Modus: realtime – Realtime
verbunden …").

**Echo:** while the body talks, the companion streams silence instead of the microphone (there is
no echo cancellation), so interrupting by voice needs **Voice barge-in (headphones)**. Push-to-talk
always interrupts.

**Chain** (`ai.mode` `chain`, or `auto` without xAI key / with ElevenLabs TTS): exactly the engines
of the tab *AI*, as before.

## Proactive speech and time context

- **Proactive:** after `ai.proactive.idle_seconds` without speech (user or AI), the companion
  nudges the AI: realtime via `conversation.item.create` + `response.create`, chain via one
  language-model turn (needs `llm` = `xai`). The nudge carries the time context and
  `ai.proactive.prompt`; the default prompt allows the AI to stay silent by answering `[silent]`,
  which is then not played. After an unanswered nudge the wait doubles (up to 8x); any user speech
  resets it. Never while the body talks, the user speaks or push-to-talk is held.
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

**Plugging in a key** (example ElevenLabs, the same for xAI):

1. Either set the environment variable before starting the app, e.g. in PowerShell
   `$env:ELEVENLABS_API_KEY = "<key>"` (or permanently via *System > Environment Variables*),
2. or save the key alone in a text file outside the repository and the VaM folder, e.g.
   `C:\Users\<you>\keys\elevenlabs.txt`, and enter its path in `config.json`:
   `"ai": { "elevenlabs": { "key_file": "C:/Users/<you>/keys/elevenlabs.txt" } }`
   (a relative path counts from your home folder, e.g. `keys/elevenlabs.txt`).
3. Select **Text-to-speech: elevenlabs** in the plugin's tab *AI*. The status line there
   changes from "nicht konfiguriert" to "bereit (…)" - a key file within 10 s, an environment
   variable after restarting the app.

Instead of editing `config.json` you can enter the key file path in the tab *AI*
(**xAI key file**, **ElevenLabs key file**); the status below shows per provider **konfiguriert**,
**fehlt** or **abgelehnt** (the server refused the key with HTTP 401/403). Something that looks like
a pasted key (starts with `xai-` / `sk_`, or a long string without `/ \ .`) is refused by the
plugin and the app and never stored. A direct key field is not built: it would be saved readably
in the scene and in `config.json` (open question to the user, TODO hook in `AppLink.cs`).

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
- **Speech to speech:** `wss://api.x.ai/v1/realtime` (Grok Voice, `grok-voice-latest`). Used by
  `ai.mode` `realtime` since v0.7.1 (standard-library WebSocket client in the companion).
  <https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech>,
  <https://docs.x.ai/developers/rest-api-reference/inference/voice>
- Language model: `POST /v1/responses` with `stream: true`; `instructions` cannot be combined with
  `previous_response_id` (the stored system prompt is reused), so the persona goes out with the
  first request of a conversation only.
  <https://docs.x.ai/developers/rest-api-reference/inference/responses>
