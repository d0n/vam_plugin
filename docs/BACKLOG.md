# AIBody – Backlog

Deferred ideas and wishes. No priority, no time order (except where an entry says "low priority"). Whatever is called "cool" / "nice to have" but is not due now comes here instead of into the code.
Agreed scope: [`SPEC.md`](SPEC.md) · status done / open: [`REQUIREMENTS.md`](REQUIREMENTS.md).
Format: **Idea** – origin, date – note / why deferred.
Basic rule since v0.6.0: first make it run (one `.cslist`, one MVRScript, one loading step + companion app); anything with a second loading step, a second plugin or a plugin-to-plugin bridge waits until the one plugin has been checked in VaM 1.22.

## Feasibility (19.11.2026)

Assessment of all entries in this file and of the nice-to-haves of the catalog of 13.11.2026 (written in the chat, never checked in; the "catalog 1–8" below are its numbers: 1 liveliness like Life, 2 trigger UI / LogicBricks / Timeline, 3 HTTP transport, 4 emotions / gestures, 5 convenience UI like MacGruber Utils, 6 VR, several characters, personality and memory, 7 demo scene / docs / Hub, 8 VaM2). Assessment only, until an entry appears under "Done". Yardstick: only the sandbox rules as in `API_AUDIT.md` (evidenced APIs, `FileManagerSecure`, one plugin / one `.cslist`, no network in the plugin except the one loopback socket since version 30, no secrets in the repository). Verdicts: **feasible** (approach, effort S/M/L, risk, what a VaM test has to clarify), **partly feasible**, **not possible** (reason). The order at the end is a proposal from the analysis; the basic rule "no priority" of this file stays, Leon decides.

The three lists are separate: **Done** (in the code, with version), **Won't work** (reason, when to reassess) and **Backlog** (feasible, not yet built). Effort: S = hours, M = one to two days, L = several days.

### Done

**Version 26 (19.11.2026)** – in detail in `SPEC.md`, tested only with unit tests and source checks, **not in VaM** (`TEST_PROTOCOL.md` T15):

- **Natural gaze** ("Natural (looks around)": client / camera with small movements, looking away, looking up while thinking) – catalog 1.
- **Blinking** ("Blink control", off by default, restores VaM's automatic blinking on release) – catalog 1.
- **Life detection** (Life Gaze pauses the gaze, Life Eyes the blinking; real storable ids open) – catalog 1.
- **Scene connection level 1** (value "Scene event" → event `scene_event`, the AI may react; values "AI speaking" / "User speaking"; actions for gaze, blinking, expressions, gestures) – catalog 2, "states as triggers" (part), "LogicBricks-like reactions" (part), Timeline connection (inputs).

**Version 27 (19.11.2026)** – in detail in `SPEC.md` and `PERSONAS.md`, tested only with unit tests and source checks, **not in VaM** (`TEST_PROTOCOL.md` T16):

- **Emotion fallback** (the app derives an expression from every spoken sentence when the AI chooses none; the AI always wins) – catalog 4 (a).
- **Fade to neutral** (`ai.emotion.fade_after_s` after the last speech, blend time `fade_seconds`) – catalog 4 (b).
- **Listening face** (a very small preset `listening` while the user speaks) – catalog 4 (c), part: the "micro-expressions" in the cheap form; following the emphasis stays in the backlog.
- **Personas** (folder with `persona.json`: prompt, name, language, voice, ElevenLabs voice, memory permission; menu **Persona** with the list from the app; changing it = a new conversation) – catalog 6, "personas as a data folder" (without sounds).
- **Memory** (toggle **Memory**, button **Forget memory**, `memory.json` per persona, summary through xAI after the conversation, notes in the instructions, protection against secrets and against overwriting with an empty list) – catalog 6, "personality profiles and memory".

**Version 29 (19.11.2026)** – in detail in `SPEC.md` and `LOCAL_ENGINES.md`, tested only with unit tests (Silero additionally once with the real model on noise), **not in VaM** and not against a real Ollama (`TEST_PROTOCOL.md` T18):

- **Ollama as a local language model** (`engines.llm: ollama`, `ai.ollama.*`, no key, history in the app, without body tools; with Ollama the memory is summarized locally) – catalog "local engines".
- **Silero VAD through onnxruntime without torch** (menu value "Silero" in **VAD engine**, `Auto` takes it as soon as the model file is there) – catalog "Silero VAD".
- **Voice barge-in without headphones by a loudness rule** (`ai.barge_in`, off by default) – catalog "interrupt by voice".

**Version 30 (19.11.2026)** – in detail in `SPEC.md` and `TECHNICAL.md`, tested with unit tests, real sockets and a .NET harness for `SocketLink.cs`, **not in VaM** (`TEST_PROTOCOL.md` T19–T21):

- **Network Active** (loopback UDP on `127.0.0.1`, default on, never blocks the main thread, automatic file fallback, companion listener on `127.0.0.1`, token never over the socket) – catalog 3, "transport", with the spec change by Leon of 19.11.2026. Plain HTTP / `UnityWebRequest` in the plugin stays under Won't work.
- **Everything in English** (docs, code comments, release notes, file names) – Leon, 19.11.2026.
- **Token masking by focus** (first / last 4 characters visible, none while the field has focus) – Leon, 19.11.2026.
- **First-run note** (one short text, one field, one button at the top of the plugin UI; shown until a token exists or the note was closed) – Leon, 19.11.2026.

### Removed

| Entry | Reason | Reassess if … |
|---|---|---|
| **Several characters in one companion app** (version 28: `--channel` lists, `ai.channels`, Channel field, routing by name, per-channel state; also "one microphone per character", "director tool", "address by gaze", "switch channels in a running app", "example scene with two characters", "per-persona settings") | Deliberate single-character focus (Leon, 19.11.2026). One app controls exactly one character; for a second one run a second VaM instance and app. The feature was removed from the code in version 30; the published v28 release stays as it was. | Leon changes the decision |

### Won't work (reassess later)

| Entry | Reason | Reassess if … |
|---|---|---|
| **HTTP / `UnityWebRequest` in the plugin** (catalog 3) | Fixed rule (no `UnityWebRequest`, no `UnityEngine.Networking`). Additionally, in VaM it depends on the setting "Allow Plugins Network Access" (off by default, the riskiest setting according to MeshedVR). Since version 30 the plugin has one exception: the loopback UDP socket to the companion app in `SocketLink.cs` (toggle **Network Active**; see "Done" and "Transport" below). | Leon changes the rule |
| **Client logic on its own atom** (microphone, engines, status on the user's figure) | Needs a second plugin and a plugin-to-plugin bridge (violates "one plugin / one `.cslist`"). Little benefit: microphone and engines run in the companion app anyway. | a second plugin is allowed |
| **Splitting session / person plugins**, **session bootstrap** through `CreatePlugin()`, **sub-plugins / nesting** | All three need another plugin or an API call without evidence (`MVRPluginManager.CreatePlugin`, `pluginURLJSON`). Against the one-plugin rule and against "only evidenced APIs". | an evidenced call and permission for a second plugin exist |
| **Rebuilding heartbeat and breathing sounds** from Life | Life's recordings are licensed and live in an AssetBundle (not usable in our package); own sounds would share the `HeadAudioSource` with speech and interrupt it. Breathing as a chest morph already exists (E4). Anyone who wants Life's breathing sounds uses Life next to AIBody (see "Liveliness"). | an own, license-free breathing sound collection and a second `AudioSource` are evidenced |
| **Push-to-talk explanation as a tooltip / mouseover** | No evidenced sandbox way for a VaM toggle (the only find: via5/VUI with its own UI system). The explanation in the info field stays. | an evidenced pattern turns up |
| **Real echo cancellation (AEC), e.g. WebRTC** | The reference signal (what the character is playing) is in VaM, not in the companion app; the latency between the WAV file and the loudspeaker is unknown and varies. An AEC without an exact reference signal cancels badly. Replacement in the backlog: interrupt by voice with a level / length rule. | VaM can report the playback time or the companion app plays by itself |
| **Looking at mirrors** | No evidenced access to mirror images; little use. | – |
| **VaM2 compatibility** | According to MeshedVR (development report October 2026) VaM2 has no plugins yet; they are the main goal of beta 1.3 without a date, the security work (restricted file system, replacement for system classes) is still going on. There is no API to check against. Preparation is already there: protocol v3 and the companion app know nothing about VaM except the file channel. | beta 1.3 with a plugin kit and documentation has been released |
| **Lip sync** (own mouth movement, viseme timing data, a mouth timeline for the WAV) | Only conceivable via in-game sound; not planned at present; delay risk too high. Mouth-timeline idea rejected. (VaM already derives the lip sync itself from the audio of the `HeadAudioSource` that AIBody plays through, E1.) | Leon changes the decision |

### Backlog: feasible, still open

**Cursor fix for the token field (low priority, 19.11.2026, Leon):** *diagnosis only, NOT implemented.* The text cursor (caret) is not visible in VaM's input fields. Probable cause: the caret is drawn behind VaM's field background, or it is only 1 px wide in the text color. Fix idea: set `customCaretColor` and a clearly visible `caretColor`, `caretWidth = 3`, move the caret object to the front (`SetAsLastSibling`) when the field gets focus, plus one log line that prints the field's hierarchy (to see where the caret sits). Needs a VaM test; none of the calls is audited yet (`docs/API_AUDIT.md`).

**Transport (catalog 3, replacement for HTTP):** *the plugin-side part is done since version 30 (toggle Network Active, loopback UDP, file fallback; see "Done").* The file channel stays as the fallback and the always-available way (polling every 0.1 s). What can still be solved differently lies in the companion app: (a) **remote control / web interface in the app** (local HTTP or WebSocket server, only 127.0.0.1, token; also OSC / MIDI): phone control panel, scene scripts, streaming overlays; they write the same commands into the file channel. Effort M, no VaM test needed. **Open again: it was not finished for the v30 release.** (b) **VaM and app on two computers** through a shared folder (SMB, Syncthing) with `--vam-root` pointing at the shared path: works today, only needs documenting and testing (S; risk: latency and locking on write; the loopback socket does not cross computers). (c) VaM's own loading of audio through an `http://` URL (as the Voxta plugin does) would only be an audio channel, needs the user settings "Enable Web Images and Audio" and `whitelist_domains.json` and brings nothing for commands: not recommended. Incidentally: Voxta (AcidBubbles) uses SignalR with "Allow Plugins Network Access"; AIBody works without that setting through the file channel, with the socket as an optional extra.

**Liveliness like Life (catalog 1):** *blinking, natural gaze and Life detection implemented since version 26 (see "Done"); only VaM tests, fine tuning and how the chest breathing works together with Life remain open.* Original assessment: partly implemented, the rest feasible. State: breathing (chest morph with a sine, E4), idle head movement (E6), gaze control (version 25). Missing: (a) **Blinking**: VaM has its own automatic blinking (`EyelidControl`, param `blinkEnabled`, evidence E29: MacGruber Eyes 0.1.0 L40-41 switches it off and drives the "Eyes Closed" morph itself); an own blink slider with an interval, a blink on gaze change and at the start of speech: S–M, VaM test (morph name, collision with VaM's automatic blinking). (b) **Gaze behavior** (micro-jumps, looking away while thinking, wandering gaze): as the default gaze "Natural" in `GazeController`, M, VaM test. (c) **Working together instead of rebuilding:** Life (Gaze, Eyes, Breathing) runs as its own plugin; AIBody recognizes it by the storable id (pattern E8/E28, `EndsWith`, namespaces `MacGruber.Gaze` / `MacGruber.Eyes` from the sources E29) and stays out of the eyes and the blinking; the idle head movement subtracts its own offset again and works with Life (TODO(verify)). Not possible: heartbeat and breathing sounds (see Won't work).

**Own actions in the trigger UI, LogicBricks style, Timeline (catalog 2) and "states as triggers", "LogicBricks-like reactions", "story scenes":** *feasible, two stages.* Stage 1 (**implemented in version 26**, S–M, only evidenced APIs, without a trigger class): **inputs** as `JSONStorableAction` (E9, E12) that VaM's trigger UI, Timeline and LogicBricks offer as targets (gaze, blinking, expressions, gestures), a string property "Scene event" that scenes set by trigger and that goes to the app as the event `scene_event` (the AI may react or stay silent), and **state values** (`AI speaking`, `User speaking` as bool storables) that other plugins can read (E13). Stage 2 (L): **real outgoing triggers** ("on speech start", "on speech end", "on listening") with VaM's own trigger UI. Evidence: Timeline `CustomTrigger : Trigger` (L9, `InitTriggerUI`, `OpenTriggerActionsPanel`) and MacGruber_Utils `EventTrigger` (Hub plugin VamMoan, contains a copy: `new EventTrigger(this, name)`, `SimpleTriggerHandler.LoadAssets()` loads the panels from VaM's AssetBundle `z_ui2`, `OpenPanelActionStart()`, `Trigger()`, saving through `GetJSON` / `LateRestoreFromJSON`). `MacGruber_Utils.cs` is under CC BY (attribution needed, the file could go into the same `.cslist` as one more source file); the way uses AssetBundle loading and coroutines that are not in the audit yet (add as E30). Risk: high (the trigger panel depends on the VaM version), a VaM test is mandatory. Timeline connection in both directions runs through these actions and triggers; AIBody already starts Timeline animations today (E8, E9). An own story engine (VAMStory) is **not possible** (not AIBody's job); the AI as a director through scene events, on the other hand, is.

**Emotions on morphs, gestures matching what is said (catalog 4):** *fallback, fade and listening face implemented since version 27 (see "Done"); the rest feasible.* Open: **micro-expressions with emphasis** (brows while listening on loudness jumps, M, risk: looks twitchy, needs an impression in VaM), **own keywords** per language or persona in `config.json` (S) and **expressions and gestures per persona** (one `expressions.json` per persona folder, S–M; the plugin reads one file per path today, it would need a switch by command). Gestures matching what is said (nodding on "yes") would be the same rule machine for the `gesture` command (S, companion app only). VaM test: strength and morph names (T16).

**Convenient UI à la MacGruber Utils, operation in VR (catalog 5, 6):** *partly feasible.* We use VaM's own `UIDynamic` building blocks (E16–E18, E24–E27); beyond that `MacGruber_Utils.cs` mainly offers `EventTrigger` (see above), slider / button helpers already exist in an equivalent form. Convenience can be raised without the library (S): section headings, short help in the info field, "Gaze now" lines, preset groups. In VR the plugin menus work like any VaM interface; the menu size is limited. **Push-to-talk** already exists as actions (`Push-to-talk start/stop/toggle`) that any VR controller trigger, Keybindings or Logic Brick can fire (TODO(verify) in VR). Microphone: always the system default input device, so in VR set the headset microphone as the Windows default. Gaze at "Camera / player" uses `centerCameraTarget` and thus the VR head position (E12). Open: text input in VR (the input fields need VaM's keyboard, TODO(verify)). A VaM test in VR is needed.

**Several characters, session / person config (catalog 6):** *removed, see "Removed" above (single-character focus, Leon, 19.11.2026).* What stays from this item: the **split into session and person config** (mode, voice and gaze per persona instead of per plugin) is not planned either, because there is only one character per app.

**Personas and memory (catalog 6):** *implemented since version 27 (see "Done", `PERSONAS.md`).* Open and feasible: **sounds in persona folders** (greeting or mood sounds in the DollMaster style; played as `speak` through the head audio source, S–M), **memory through a local model** (now that local engines exist), **memory view in the menu** (the notes as text in the info field, S; today only the count).

**Local engines (companion app):** *LLM through Ollama implemented since version 29 (see "Done", `LOCAL_ENGINES.md`); the rest feasible, M per engine, no sandbox question.* Open: **STT with faster-whisper**, **TTS with Piper**, **tool calls for Ollama** (function calls vary by model; conceivable with a model whitelist), **model list from Ollama** (`/api/tags`) as a chooser in the menu (S). Optional dependencies as for `webrtcvad`; tests with fakes. Risk: model size, latency, GPU.

**Silero VAD:** *implemented since version 29* (onnxruntime without torch, download the model file `silero_vad.onnx` yourself, menu value "Silero"; see `LOCAL_ENGINES.md`). Open: a model download helper in the app (S, needs the app's network access to GitHub; deliberately not automatic), Silero model v4 (S, if someone needs it).

**Interrupting by voice without headphones:** *implemented since version 29 by a loudness rule* (`ai.barge_in`, off by default, only with voice activation; see `LOCAL_ENGINES.md`). Open: a **menu toggle** in the plugin (S–M: JSONStorableBool, `BuildAiJson` / `MergeAi` / `ApplySettings`), a **rule with a speaker feature** (pitch / spectrum instead of level only, M, a test with loudspeakers is needed), fine tuning after the VaM tests (T18).

**Bundled plugin presets:** *feasible, S; open again, not finished for the v30 release.* A plugin preset (`.vap`) for Persons in the package under `Custom/Atom/Person/Plugins/` that registers the `.cslist`. Risk: VaM's format (VaM test: load the preset, the plugin appears), `licenseType` stays untouched.

**Demo scene, docs, Hub publication (catalog 7):** *partly feasible.* The demo scene exists as JSON (`examples/scenes/AIBody_GreenScreen.json`); missing: a scene **in the package** (scene `.var` depending on `d0n.AIBody`, without a token), a preview image, a Hub description. Hub: Voxta shows that a plugin with external companion software can go on the Hub (reference the plugin as a Hub resource, do not copy it; category, tag, instructions, credits). Open and for Leon alone to decide: account, license (`FC`, unchanged), price, whether the app is distributed in the repository or separately, age rating / content rules of the Hub. Before a publication: a token scan of the scene, a section about the app's network behavior (the app uses xAI / ElevenLabs on the internet; the plugin only talks to the app on the loopback address). Hub publishing stays parked.

**Small menu items:** *feasible, S, waiting for Leon's decision:* "key file path in the menu, labeled" (with `UiPage.TextInput` and a label), "delay setting" (specification missing), "info / path display" (in the info field of the tab Config since version 15), "in-game test plugin" (partly: the self-test in the info field covers it; an own plugin would only be another tab, S, not a second plugin).

### Recommended order (proposal, no priority)

1. ~~**Scene connection level 1** (actions, "Scene event", state values)~~ – implemented in version 26.
2. ~~**Natural gaze and blinking** including Life detection~~ – implemented in version 26.
3. ~~**Emotion fallback and fade**~~ – implemented in version 27.
4. ~~**Personas and memory**~~ – implemented in version 27.
5. ~~**Several characters** (one app, several channels) and the channel in the menu~~ – implemented in version 28, **removed in version 30** (single-character focus).
6. **Demo scene in the package and Hub description** (Leon's decision needed).
7. ~~**Local engines** (Ollama first), **Silero through ONNX**, **voice barge-in by rule**~~ – implemented in version 29 (faster-whisper, Piper open).
8. ~~**Network Active** (loopback socket with file fallback)~~ – implemented in version 30.
9. **Trigger UI stage 2** (real outgoing triggers) – the biggest risk, only after VaM tests of stage 1.
10. **Remote control / web interface in the app** (also OSC), **bundled plugin presets** – open again after the v30 release build.
11. **Cursor fix for the token field** – low priority, see above.

## Menu and operation
- **Info / path display in the menu** (channel, audio, config.json folders) – Leon, 17.11.2026 – Removed from the tabs in v0.7.4 (the menu shows only what can be set). Since version 15 the config.json path and the folder are in the info field on the left (tab Config); other paths once in the VaM log.
- **In-game test plugin à la Timeline** – Leon, 17.11.2026 – No specification yet. Partly covered: the extended self-test in the status field with output in the companion app's log (version 13); an own test plugin stays without a specification.
- **Key file path in the menu, labeled** – version 15 – The fields "xAI key file" / "ElevenLabs key file" appeared in VaM as empty, unlabeled boxes and were removed; the path is now only in config.json (`ai.xai.key_file`, `ai.elevenlabs.key_file`) or as an environment variable. It can come back as a labeled field if Leon wants it.
- **Channel in the menu** – version 15 – The field "Channel" (which showed only `default`) was removed; it came back in version 28 for several characters and was **removed again in version 30** (one character per app, fixed folder `default`).
- ~~**Direct API key text field in the plugin**~~ – Leon, 17.11.2026 – decided on 18.11.2026 and built in version 21: field "XAI API Token" in the tab Voice (plain text in the scene; since version 24 in plain text in config.json `ai.xai.api_key` and only masked in the scene). Only an ElevenLabs field remains open (explicitly not wanted by Leon).
- **Delay setting** – Leon, 17.11.2026 – Placeholder "Delay (s)" in the tab AI without a function, removed from the menu since version 15; no specification of what should be delayed (candidates: a pause before the answer, a wait until the end of speech is detected – both for Leon to decide).
- **Menus that show only "default"** – Leon, 18.11.2026 – think about it later. Checked in version 16: none left (the field Channel and the tab Post were already removed in version 15). The engine choosers (Speech-to-text, Language model, Text-to-speech) show only the configured value (`null` / `echo` / `tone`) before the first connection to the app, then the app's list; they stay because they can be set. Without poses the pose chooser is omitted.
- **Split of session config vs. person config** – Leon, 17.11.2026 – which setting applies per session, which per person; deferred until after the tests in VaM.
- **Push-to-talk explanation as a mouseover / tooltip** – Leon, 17.11.2026 – No evidenced sandbox way for a VaM toggle (the only example, via5/VUI, builds its own UI system), see `API_AUDIT.md`; until then an explanation text, in the info field on the left since version 15 (tab Client Character).
- **Convenient UI à la MacGruber Utils**, **operation in VR** – requirements catalog – Not started.

## Loading and structure
- **Client logic on its own atom** (microphone, engines, status on the user's figure or an Empty) – v0.5.0 (`legacy/v0.5`) – Since version 12 the scene has a male client Person, but only as a visible body with a background plugin; AIBody is not on it. Needs a plugin-to-plugin bridge (`GetStorableIDs`, `plugin#` ids, string param callbacks), unevidenced.
- **Second character or several characters** (own instance, target per command, persona per character) – v0.4 `AIBodyPerson2` / v0.5 atom routing – **Removed** (single-character focus, Leon, 19.11.2026; version 28's multi-character feature was taken out again in version 30).
- **Splitting session / person plugins**, session connection through "Set Current As User Defaults" – v0.3 / v0.4 (code under `legacy/`) – Deferred in favor of loading in one step.
- **Session bootstrap**: the plugin puts AIBody on the right character through `MVRPluginManager.CreatePlugin()` + `pluginURLJSON` (Keybindings pattern) – requirements catalog – API unevidenced, an additional plugin.
- **Bundled plugin presets** (`Custom/Atom/Person/Plugins/...`) – backlog v0.6.0 – Not started (open again after the v30 release build).
- **Sub-plugins / nesting** (one entry plugin loads further `.cslist`) – requirements catalog – No evidenced way except bootstrap.
- **Interactive story scenes à la VAMStory** (control on its own atom) – requirements catalog – Not started.
- **VaM2 compatibility** – requirements catalog – Later.

## Character
- **Gaze control, remainder:** the basic function (tool `look_at`, menu "Gaze") since version 25, natural gaze (random glances, looking away while thinking), blinking and Life detection since version 26 (see SPEC). Open: finer micro-saccades as in Glance, check the effect of the values in VaM (T14, T15).
- **Personas as a data folder** `Saves/PluginData/AIBody/personas/<name>/` – requirements catalog – Implemented in version 27 (JSON; sounds in the folder and male personas as templates open: see "Feasibility").
- **States as triggers** (idle, listening, thinking, speaking) for scene logic – requirements catalog – Partly (version 26: readable values "AI speaking" / "User speaking"); real outgoing triggers see "Feasibility", stage 2.
- **Viseme lip sync** from TTS timing data instead of VaM's audio lip sync – requirements catalog – Rejected (see "Won't work", last entry).
- **Emotions on morphs**, gestures matching what is said – requirements catalog – Tool calls since v0.7.4, fallback from the words, fade and listening face since version 27; emphasis and gestures from words open (see "Feasibility").
- **Liveliness like MacGruber Life** (breathing with chest movement and breathing sound, heartbeat, blinking, swaying) – requirements catalog – Blinking and gaze behavior since version 26 (see "Feasibility"); breathing sounds and heartbeat: Won't work (see there), use Life on the same character instead.
- **LogicBricks-like reactions** to scene events (touch, proximity, triggers) and feedback to the app, closer Timeline connection – requirements catalog – Inputs since version 26 (Scene event, actions); outgoing triggers (stage 2) open, see "Feasibility".
- **Personality profiles and memory** of the AI – requirements catalog – Implemented in version 27 (personas, memory), see `PERSONAS.md`.

## Companion app
- **Local engines** (STT faster-whisper / Vosk, LLM through Ollama or similar, TTS Piper / XTTS) – backlog v0.6.0 – Cloud engines xAI / ElevenLabs since v0.7.0, Ollama since version 29; local STT and TTS open.
- **Silero VAD (neural)** – formerly deliberately not implemented (torch); implemented since version 29 through onnxruntime without torch, see SPEC and `LOCAL_ENGINES.md`.
- **Interrupting by voice without headphones** – real echo cancellation (AEC) stays "Won't work"; since version 29 there is the level rule `ai.barge_in` (off by default); otherwise the echo gate, by voice with headphones, push-to-talk always.
- **Remote control / web interface, OSC** (localhost only, off by default) – open again after the v30 release build, see "Transport".

## Removed menu entries (version 15) and their original purpose

Leon's feedback after the VaM test of version 14 (17.11.2026): placeholders and empty fields out, information in one large field. Recorded before removal (sources: code comments, commits, SPEC, REQUIREMENTS, BACKLOG):

- **Tab "Post"** – commit c601b87 (17.11.2026 19:59, menu at Leon's request), before that the tab "Verbindung" (v0.6.3). Purpose: connection settings; the name as Leon said it, in the code as the constant `PostTabLabel` with the note "perhaps Port was meant". Content at the end only the field Channel (path displays already removed in v0.7.4). Decision by Leon 17.11.2026: "Post" means "poses"; poses are in the tab AI Character, the tab is gone.
- **Field "Channel" (showed only `default`)** – since v0.6.3. Purpose: the channel = the subfolder `Saves/PluginData/AIBody/<channel>/` and `Custom/Sounds/AIBody/<channel>/`, so that several plugin / app pairs run separately. Version 28 brought it back; version 30 removed it again for good (fixed folder `default`).
- **Fields "xAI key file" / "ElevenLabs key file"** (empty unlabeled boxes in VaM, Leon's "empty Questions") – commit c601b87. Purpose: the path of a text file with the key instead of the key itself (no plain-text key in the scene / config.json); a pasted key was rejected. Stays valid through config.json (`ai.xai.key_file`, `ai.elevenlabs.key_file`) and environment variables; the file wins on every start. Future: BACKLOG "Key file path in the menu, labeled".
- **Slider "Delay (s) – placeholder, no function"** – commit c601b87, requested by Leon, purpose never specified ("what should be delayed?"), not stored. Future: BACKLOG "Delay setting".
- **Title line per tab** (a text field with only the tab name, e.g. just "AI") – since v0.6.3. Purpose: show which tab is open. Replacement: "Info: <tab>" in the info field on the left.
- **Tab "AI"** – commit c601b87, before that the tab "Engines" (v0.7.0). Purpose: engines, key files, key / engine status, Proactive. Content now under Voice > AI Character; status in the info field.
- **Text field "Engines: waiting for the companion app …"** (engine status) – v0.7.0 (commit 4ea1d45). Purpose: show per engine chosen / active / fallback with the reason. Useful, hence in the info field (tab Voice) as soon as the app sends the first heartbeat; before that *Live* says "Companion app: not seen yet".
- **Text field key status** ("API keys: waiting for the companion app …") – v0.7.0 / c601b87. Purpose: configured / missing / rejected per provider with a hint to console.x.ai. In the info field (tab Voice).
- **Help texts Simple Q&A and AI mode, push-to-talk explanation, microphone status, result of Reload Config JSON** – v0.7.2–v0.7.4. Purpose: explanation or feedback right at the control (a tooltip without an evidenced API). In the info field for the respective tab.
- **Tab "Advanced"** – v0.6.3. Purpose: rarely used settings (File poll interval, Verbose log). Merged into Config.

## Dropped for good (not backlog)
- **HTTP transport / network code in the plugin** (removed v0.6.1) – only if VaM officially allows it. (Since version 30 the one loopback socket to the companion app exists, see "Done"; HTTP, `UnityWebRequest` and any internet access from the plugin stay dropped.)
- **Microphone in VaM** – stays in the companion app.
- **APIs without a public, working plugin evidence** for VaM 1.22's sandbox – see `API_AUDIT.md`.
