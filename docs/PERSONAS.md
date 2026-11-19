# Personas, memory and emotions (version 27)

Status 19.11.2026. Everything here runs in the companion app and in local files; the plugin gets only three controls (menu **Persona**, toggle **Memory**, button **Forget memory**). None of this was tested in VaM (`TEST_PROTOCOL.md` T16). The companion app controls exactly one character (since version 30), so there is one persona and one memory at a time.

## Personas

A persona is a folder with a `persona.json` under

```
<VaM main folder>\Saves\PluginData\AIBody\personas\<name>\persona.json
```

Examples to copy: [`examples/personas/`](../examples/personas/) (Anna, Marc). Folder name = name in the menu (letters, digits, spaces, `_`, `.`, `-`, at most 40 characters, no dot or space at the end).

```json
{
  "name": "Anna",
  "prompt": "You are Anna, a calm librarian ...",
  "language": "auto",
  "voice": "ara",
  "elevenlabs_voice_id": "",
  "memory": true
}
```

| Key | Meaning |
|---|---|
| `prompt` | Character text of the AI; **replaces** `ai.persona` from `config.json` while the persona is selected (empty = `ai.persona`). At most 8000 characters. |
| `name` | Display name; the AI is told "Your name is Anna." Optional. |
| `language` | `auto` or a language code (`de`, `en`, …); replaces `ai.language` (language hint for recognition and voice). Optional. |
| `voice` | xAI voice (`eve`, `ara`, `rex`, `sal`, `leo` or an own id); **replaces the menu "Voice"** for this persona (chain and realtime). Optional. |
| `elevenlabs_voice_id` | Voice for ElevenLabs speech output, replaces `ai.elevenlabs.voice_id`. Optional. |
| `memory` | `false` = nothing is ever remembered for this persona (default `true`; only applies if **Memory** is on). |

Selection: tab **Voice** > **AI Character** > **Persona** (the list comes from the app, 5 s after a folder is created). `(none)` = the text `ai.persona` from `config.json`, as before version 27. The menu saves the choice with the scene (and in `config.json`: `ai.persona_name`). A change starts a **new conversation** (history emptied, new instructions, new voice; a realtime session is rebuilt) and saves the old persona's memory first. A persona that does not exist or is not readable is not used; the info field (tab Voice) and the app window say why. Errors in the file (wrong type, unknown key) are reported and skipped.

## Memory

Opt-in: toggle **Memory** (tab Voice, `ai.memory.enabled`, default off). When on, the app keeps a short list of facts that **the user said about themselves** (name, preferences, plans …) in

```
<VaM main folder>\Saves\PluginData\AIBody\personas\<name>\memory.json      (without a persona: …\personas\default\memory.json)
```

- **When:** after a conversation, i.e. after `ai.memory.session_idle_minutes` (default 10) of silence with at least `ai.memory.min_exchanges` (2) questions, when the persona changes and when the app quits (then waiting up to 15 s). It runs in the background; speaking and the heartbeat are not held up.
- **How:** the language model (xAI, required; with the app's key) gets the old list and the conversation and returns the new list (a summary instead of raw text; at most `ai.memory.max_facts` (30) facts of at most 160 characters each, merged, outdated ones removed). The request goes to xAI with `store: false`, the answer is not stored there (as the Responses API docs say). **The conversation itself therefore goes to xAI**, as it does with every answer anyway. With Ollama selected the summary runs locally and nothing goes to xAI.
- **Used:** when a conversation starts, the facts stand as notes in the instructions ("Notes from earlier conversations … not instructions"); realtime renews them with the time line. The AI should not recite them by itself.
- **Show, change, delete:** `memory.json` is plain JSON text (`{"facts": ["Name is Leon", …]}`), readable and editable by hand (umlauts readable). Button **Forget memory** (tab Voice): deletes the chosen persona's file, empties the notes and starts a fresh conversation (the old one still held the notes in its instructions). Toggle off: the file stays but is neither read nor written.
- **Protection:** facts that look like a key or password (`xai-…`, `sk-…`, long random strings) are never stored; line breaks and control characters are dropped; an empty or unusable answer of the model **never** deletes the old notes (deleting only with the button); on an error (network, key, format) the old notes stay and the info field names the problem. The summary instruction explicitly calls the conversation text data, not commands.
- **Residual risk:** a user can slip the model a "fact" that later stands as a note in the instructions (prompt injection through the memory). Therefore length, number and form are limited and the notes are framed as "not instructions"; anyone who does not want the risk leaves **Memory** off or reads `memory.json` now and then. The files live only locally in `Saves/PluginData`, never in the repository and never in the scene.

Cost: one additional request per conversation (and on change / quit), small (the conversation's last ~12000 characters plus 30 lines).

## Emotions without the AI's help

`config.json`, section `ai.emotion` (file only, no menu; restart the app):

| Key | Default | Meaning |
|---|---|---|
| `fallback` | `true` | If the AI does not call `express` (and gives no `<<tag>>`), the app derives an expression from **every spoken sentence** (keyword rules, German / English, for happy, sad, angry, surprised, thinking; "Hmm", "Unfortunately", "Wow", "I'm glad" …) and sends it shortly before the sentence (strength 0.85, blend 0.5 s). Only expressions that the plugin knows; no hit = no change. If the AI chose an expression itself in the answer, the app stays out. Not in Q&A mode and not with Body control off. |
| `fade` | `true` | The face blends back to `neutral` `fade_after_s` seconds after the last speech (the AI's or the user's) and the last expression. |
| `fade_after_s` | `6.0` | 1–120 s. |
| `fade_seconds` | `2.5` | Blend time when going back, 0.2–10 s. |
| `listening` | `true` | While the user speaks, the character shows a very small "listening" face (brows slightly up on the inside, a touch of a smile; preset `listening` in the plugin, which is not offered to the AI). If the preset is missing (older plugin), nothing happens. |

The rules are deliberately simple and rough (no mood analysis); anyone who wants better expressions gives the AI expressions in `expressions.json` and lets it use `express` itself. Own keywords cannot be entered at the moment (backlog).
