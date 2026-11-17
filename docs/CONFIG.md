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
| `ai` section | sets only its tab controls (`mode`, `proactive.enabled` / `idle_seconds`, `realtime.send_while_speaking` / `voice`, `xai.voice`; `xai.key_file` / `elevenlabs.key_file` are passed through from the file - no menu field since version 15, the file wins on every start), keeps the rest when writing the file | reads it (persona, language, fallback, engine settings); the tab controls also arrive live in the `config` event |
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
the tabs one to one (kept for compatibility with existing files): `connection` = file only
(channel; + *Voice > Voice Mode* **Active**), `engines` = tab *Voice > AI Character*, `mic` = tab *Client Character*, `body` = tab
*AI Character*, `advanced` = tab *Config*, `ai` = companion settings plus the tab controls named
below. Machine-readable:
[protocol/schema/config.schema.json](../protocol/schema/config.schema.json), example:
[examples/config.json](../examples/config.json).

The complete key reference (type, default, allowed values, effect, where to set it) is in the German
[README, section 4](../README.md#4-einstellungen); it is the single list and kept in sync with
`companion/aibody_companion/settings_file.py`.

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
answers (repeat the question). The info field (tab *Voice*) shows the active mode ("Modus: realtime – Realtime
verbunden …").

**Echo:** while the body talks, the companion streams silence instead of the microphone (there is
no echo cancellation), so interrupting by voice needs **Voice barge-in (headphones)**. Push-to-talk
always interrupts.

**Chain** (`ai.mode` `chain`, or `auto` without xAI key / with ElevenLabs TTS): exactly the engines
of *Voice > AI Character*, as before.

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
3. Select **Text-to-speech: elevenlabs** in the plugin's tab *Voice > AI Character*. The engine status in the info field
   changes from "nicht konfiguriert" to "bereit (…)" - a key file within 10 s, an environment
   variable after restarting the app.

Since version 15 the key file path is set only in `config.json` (the menu fields showed as empty,
unlabeled boxes in VaM and were removed); after editing the file press **Reload Config JSON** (tab
*Config*) or reload the scene. The key status in the info field (tab *Voice*) shows per provider **konfiguriert**,
**fehlt** or **abgelehnt** (the server refused the key with HTTP 401/403). Something that looks like
a pasted key (starts with `xai-` / `sk_`, or a long string without `/ \ .`) is refused by the
plugin and the app and never stored. A direct key field is not built: it would be saved readably
in the scene and in `config.json` (open question to the user, TODO hook in `AppLink.cs`).

**Which key:** xAI needs an API key from console.x.ai (starts with `xai-`). A Grok subscription
(SuperGrok / X Premium) or a grok.com login token is not an API key and is refused by `api.x.ai`.
The key status (heartbeat `keys.xai.hint`, info field of tab *Voice*) says so when the key is missing or refused.

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
