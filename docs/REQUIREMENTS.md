# AIBody – requirements catalog (status overview)

Status: 21.11.2026, version 44. Overview of what is done and what is open; updated with every release.
- Agreed specification (what applies): [`docs/SPEC.md`](SPEC.md)
- Deferred ideas / nice to have: [`docs/BACKLOG.md`](BACKLOG.md)
- Test instructions in VaM: [`docs/TEST_PROTOCOL.md`](TEST_PROTOCOL.md) · API evidence: [`docs/API_AUDIT.md`](API_AUDIT.md)
- Repo: https://github.com/d0n/vam_plugin · current package: `d0n.AIBody.47.var` (version = package number since 12)

"Done" means: tested in code and against rebuilt counterparts. What has not yet been checked in VaM or against the real xAI APIs is listed again under 2.

## 1. Done

### Loading, sandbox, package
- One plugin, one `.cslist` (`Custom/Scripts/d0n/AIBody/AIBody.cslist`), one MVRScript class, loaded in one step in the Person's Plugins tab – v0.6.0.
- Strict sandbox (no `UnityWebRequest`, `UnityEngine.Networking`, `WWW`, `System.IO`, `Process`, reflection, `DllImport`, Unity `Microphone`); the build scan fails otherwise – v0.6.1. Until version 29 the plugin had no network code at all; since version 30 `System.Net` / sockets are allowed in exactly one file (`SocketLink.cs`), see "Version 30".
- Only evidenced APIs, evidence in `docs/API_AUDIT.md` (E1–E34) – v0.6.1, extended continuously.
- File access only through `FileManagerSecure` – v0.6.1.
- Diagnosis in the plugin window: status field, self-test, every init phase guarded on its own – v0.6.2.
- One `.var` into `<VaM>/AddonPackages/`; list of old packages to delete in README and release notes – since v0.6.0.
- Hotfix: version 13 did not compile in VaM (CS584, `foreach` over `Dictionary.Values` in `ExpressionController.cs`); no more `foreach` / LINQ over `.Keys` / `.Values`, the build scan forbids the pattern – version 14 (Leon, 17.11.2026 23:16); confirmed in VaM: loads without errors, "Init done, no errors", 200 poses (Leon, 17.11.2026).

### Connection and configuration
- Companion app (Python) `python -m aibody_companion --vam-root "D:\VaM"` – v0.5.0.
- File transport through `Saves/PluginData/AIBody/default/`, protocol v3, heartbeat, status – v0.5.0 / v0.6.3.
- Robust connection: timeout 6 s → "DISCONNECTED", automatic reconnect, old commands discarded, outbox ≤ 20 – v0.6.3, end-to-end simulation v0.7.0.
- Shared `config.json` in `<VaM>/Saves/PluginData/AIBody/` (location decided 15.11.2026), schema, menu values win; VaM values as text (`"2.5"`, `"true"`) are read (E21) – v0.6.3 / v0.7.0.
- Menu in tabs (tab buttons, `Create*` / `Remove*`, E17/E18) – v0.6.3; reordered at Leon's request (Voice Mode, AI, AI Character, Client Character, Post, Config, Advanced) – v0.7.2; redone after the VaM test: Voice (Voice Mode, Voice > AI Character), AI Character, Client Character, Config – version 15 (Leon, 17.11.2026).

### AI and speech
- Test engines `null` / `echo` / `tone` for offline use and as the fallback – v0.5.0.
- Engines xAI (STT `POST /v1/stt`, LLM `POST /v1/responses` streamed, TTS `POST /v1/tts`) and ElevenLabs (TTS); keys through `XAI_API_KEY` / `ELEVENLABS_API_KEY` or the path of a key file; key status configured / missing / rejected – v0.7.0.
- Realtime mode (Grok Voice, `wss://api.x.ai/v1/realtime`), reconnect with backoff, the chain as fallback – v0.7.1.
- Proactive speaking after silence, time and time since the last exchange in the context – v0.7.1.
- Simple Q&A mode `qa` as the default (speech only, Body control off), button in the tab Voice Mode (Voice > Voice Mode since version 15), status line "Last turn", realtime without an answer after 12 s → chain – v0.7.2 (approved by Leon 17.11.2026).
- Toggle "Use realtime voice" (on = `auto`, off = `qa`, the default stays `qa`) – v0.7.3.
- A rejected xAI key (HTTP 400 "Incorrect API key") is recognized as "rejected" – v0.7.3.
- Hint which key works: API key from console.x.ai, not a Grok subscription / grok.com token (key status, startup warning of the app) – v0.7.4.
- Field "XAI API Token" (tab Voice, section Voice Mode, at API Reconnect): a simple free-text field without a format check, no ElevenLabs field; the token goes to the app as `keys.xai` in the `config` event through the file protocol and is used for all xAI calls; order field > `XAI_API_KEY` > `ai.xai.key_file`; the plain text was only in the scene at first, then in config.json (version 24, see below); redacted in the log; `setx XAI_API_KEY` stays optional – version 21 (Leon, 18./19.11.2026).
- Start help – version 22 (Leon, 19.11.2026): README section "Getting started" (manual start, folder, `pip install -e .`, sounddevice, Python ≥ 3.10), `ai.xai.key_hint` in the written `config.json`, VaM path examples as `D:\VaM`, `pip install -e .` repaired (pyproject).
- The button "Simple Q&A mode" is now "Question and Answer", two lines centered "Question" / "& Answer", function unchanged – version 21 (Leon, 18./19.11.2026).
- Tool calls → body commands (chain: `/v1/responses` with tools; realtime: `function_call` + `function_call_output`): `express` (expression / gesture); no `pose` tool since version 32 (poses only through pose commands); every call gets a result; no tools in `qa` and with Body control off – v0.7.4.
- Latency measurement end of speech → first sound with a breakdown (STT, LLM first token, first sentence, TTS, file write, to plugin, plugin start), a log line per turn, last value + average in the status field (*Live*, "Latency to first sound") – v0.7.4.

### Microphone
- Microphone only in the companion app (recording, VAD, echo gate); push-to-talk in the plugin, reported as a file – v0.5.0.
- Push-to-talk interrupts the running answer; voice barge-in (headphones) in realtime mode – v0.7.0 / v0.7.1.
- Microphone settings live (0.3 s after the last change), level meter – v0.6.3.
- Better voice activity detection and a checked echo gate – version 24 (19.11.2026).
- Microphone menu repaired (empty menu): one entry per device (only the host API of the default device, Windows otherwise lists every microphone several times), open by index, the app's error reason is shown, entry "System default microphone", button "Refresh microphones", status line with device count, the list is requested again on opening (E24/E25) – v0.7.4. **Removed since 19.11.2026** (microphone selection removed, see "Next version").
- Microphone menu empty in VaM ("(not selected)", not even "Standard") – version 16: menu without separate display names (`displayChoices`), "Standard (System-Mikrofon)" (since version 18 "System default microphone") always present, info field with count received, host API, time, menu entries; test `tools/mic_test.py`. TODO(verify) in VaM. **Removed since 19.11.2026** (microphone selection removed, see "Next version").

### Voice output
- VaM's audio loader (`NormalizeMediaPath` → `URLAudioClipManager.QueueClip` → `PlayNow` on `HeadAudioSource`) with the built-in lip sync, local files only – v0.6.x.
- Speech independent of expressions, status lines `Audio: Loading/Speaking/Done`, red `Audio error`, test tone directly and through the companion – v0.7.1 / v0.7.2.
- Audio folder `Custom/Sounds/AIBody/default/`, if "not loadable" one switch to `Saves/PluginData/AIBody/default/audio/`; fixed folder through `connection.paths.audio` – v0.7.2.

### Body
- Expressions through morphs, breathing (breath morph configurable in config.json), head idle, gestures through Timeline (`Play <name>`), poses through pose presets – v0.5.0 / v0.6.3.
- Toggle Body control (off = speech only) – v0.7.1.
- Tab AI Character: poses by voice through the AI and a manual menu (chooser + "Apply pose", "Reload poses"; poses from `gestures.json` and preset files in `Custom/Atom/Person/Pose` and `.../Pose/AIBody`), expression / gesture with chooser and button – v0.7.4 (Leon, 17.11.2026 21:41).

### Menu principle
- The menu shows only what can be set (Leon, 17.11.2026 21:43): pure path / info displays in Post, Config and AI Character removed, not moved; paths appear once in the VaM log; explanation / status texts for controls stay – v0.7.4.
- Push-to-talk explanation under the toggle instead of a tooltip (no evidenced way) – v0.7.2, checked again v0.7.3; in the info field on the left since version 15.
- One large info field on the left for all help, status and path texts ("Info: <tab>", Self-test, Live, Startup log); only controls in the tabs; no empty placeholders; input fields labeled; self-explanatory names (AI Character, Client Character) – version 15 (Leon, 17.11.2026).
- Info field height 1800, only the info field on the left (header line with the hint removed), info texts shortened, "Reload expressions" at the expression – version 17 (Leon, 18.11.2026).
- Plugin UI, companion app output and `tools/mic_test.py` in English (international standard, independent of the system language); names supplied by the system (microphones, host APIs) unchanged; old scenes and config.json stay valid – version 18 (Leon, 18.11.2026).
- The slider in the tab Config is called "Companion inbox poll interval (s)" in the UI instead of "File poll interval (s)": it sets how often the plugin checks the companion app's inbox (`Saves/PluginData/AIBody/default/inbox/`) for messages (speech, poses, expressions), not config.json (which is never reloaded automatically). A note in the info field of the tab Config; stored name "File poll interval (s)" and config.json key `advanced.file_poll_interval_s` unchanged, polling behavior unchanged – version 19 (Leon, 18.11.2026).
- Microphone menu without the companion app (Leon, 18.11.2026 19:15: menu empty, "Refresh microphones" changes nothing, info field "no answer from the companion app"): the info field says in red that the app is not running, with the start command `python -m aibody_companion --vam-root "D:\VaM"` ("no answer" only when the app runs); the menu is set anew on opening, on "Refresh microphones" and when the tab is built (at least "System default microphone"); another request every 10 s while the app runs without a list; the app sends the list after every `ready` and logs the raw numbers – version 20. **Removed since 19.11.2026** (microphone selection removed, see "Next version").
- Info field larger (1600) and only with the info of the open tab; self-test, Recent events, Startup log in the tab Config; startup result as one line on every tab; no empty pose chooser; checked: no menu and no section that shows only "default" – version 16 (Leon, 18.11.2026).
- "Poses" instead of "Post": tab Post removed, poses in the tab AI Character; Advanced merged into Config – version 15. Original purpose of the removed entries: `docs/BACKLOG.md`.

### Version and configuration
- Version scheme version = package number (`d0n.AIBody.12.var` = version 12, tag `v12`; a test checks equality) – version 12 (Leon, 17.11.2026 22:31).
- Sliders in the plugin cover the full config.json ranges (VAD threshold up to 0.5, Proactive idle up to 3600 s), so that values from the file are not clipped and written back; a test compares all sliders with the app's ranges – version 12.

### Logging
- Verbose log (tab Config, `advanced.verbose_log`, `-v`): a trace per turn in the console and `<VaM>/Saves/PluginData/AIBody/logs/companion.log` (1 MB × 5), keys redacted; in the plugin `[debug]` lines and *Recent events* – v0.7.3; tool calls and latency in the trace – v0.7.4.
- Extended self-test for the points that can only be checked in VaM (T5): pose memory, poses and pose files, breath morph, expression morphs with missing names, Timeline storable; in the status field and as "Plugin self-test: …" in the console and `companion.log` – version 13.

### Scene, docs
- Attribution in the README, section 6 (MacGruber as the main source, Acid Bubbles, VamDeluxe, Sally, further evidence sources) – version 13.
- Scene template green screen / passthrough (Sally's *Camera Background Color* #00FF00): originally `examples/scenes/AIBody_GreenScreen.json`, `docs/SCENE_GREENSCREEN.md` – v0.7.x (wish 17.11.2026); package reference corrected to the current package – after v0.7.4. Replaced in version 37 by `examples/scenes/AIBody_Example.json` plus the preview `AIBody_Example.jpg`, then on 21.11.2026 (no version bump) by `examples/scenes/AI-Buddy.json` plus `AI-Buddy.jpg` (the original look, clothing kept).
- Scene with two people: `AI Character` (female, `Female 3`, AIBody) and `Client Character` (male, `Male 1`, Camera Background Color directly on the Person), 1.2 m apart, facing each other – version 12 (Leon, 17.11.2026 22:30).
- README rewritten: purpose, bundled scene, two characters, complete settings reference, notes for the Hub; technical details in `docs/TECHNICAL.md` – after v0.7.4 (Leon, 17.11.2026 22:11).
- `docs/BACKLOG.md` (deferred ideas, Leon 17.11.2026 21:45) and `docs/SPEC.md` (spec log, Leon 17.11.2026 21:50) – v0.7.4.

### Version 23 (19.11.2026)
- **Version 23 (19.11.2026):** microphone selection removed (Leon, voice message: under Windows the companion app records from the default device anyway, the selection was superfluous). Gone: menu "Mic device", button "Refresh microphones", action "Refresh mic devices", `MicDeviceList.cs`, microphone list / device count in the info field, setting `mic.device`, messages `list_devices` / `devices`, device parameters of the recording. Recording always uses the default input device (sounddevice). Old scenes, config.json and older plugins with `device` / `list_devices` are tolerated silently. The red line "Companion app not running. Start it: …" stays in the info field. `--list-devices` and `tools/mic_test.py` stay as diagnosis.
- **Version 23 (19.11.2026, commit 45b6993):** the recognized speech text (STT) is always written to the console as an INFO line `Heard (STT …): …` before the answer comes, also without Verbose log.
- **Version 23 (19.11.2026):** the companion app's hint on `audio_failed` ("VaM could load the WAVs neither from … nor from …") no longer points to "TEST_PROTOCOL T9" (Leon took it for a "T9 log") but to `<VaM>/Saves/PluginData/AIBody/logs/companion.log`, the test "Play test tone" (tab Voice) and `--vam-root` = the VaM folder VaM is started from. Background (Leon's log): the plugin reported "did not start playing within 15 s" for a WAV under `Saves/PluginData/AIBody/default/audio`; `sounddevice` was missing at the same time. Behavior otherwise unchanged.
- **Version 23 (19.11.2026):** slider "Proactive idle (s)" minimum 15 → 0 (Leon, voice message): 0 = proactive speaking off. `idle_seconds` ≤ 0 or < 1 s counts like `enabled=false` (realtime and chain, never a prompt on every tick, not even after a long silence); info field "Proactive: off (idle 0 s)"; toggle "Proactive" and default 90 unchanged; config.json range [0–3600], schema regenerated.
- **Version 23 (19.11.2026):** slider "Proactive idle (s)" is now "Speech delay timer (s)" (Leon, voice message; 0 = off). Info field "Proactive: on, speech delay timer 90 s" / "Proactive: off (speech delay timer 0 s)", console lines of the app adjusted; toggle "Proactive", `ai.proactive.idle_seconds` and protocol keys unchanged. **Scenes:** the value stored under the old name is lost (the slider there goes to the default 90), because there is no evidenced API for a migration (no `RestoreFromJSON` in `docs/API_AUDIT.md`). (The question about the toggle's name is decided: "Proactive talking", see the next line.)
- **Version 23 (19.11.2026):** toggle "Proactive" is now "Proactive talking" (Leon, voice message). Info field "Proactive talking: on, speech delay timer 90 s" / "Proactive talking: off (speech delay timer 0 s)" / "Proactive talking: off"; console lines of the app ("Proactive talking: …") adjusted; `ai.proactive.enabled` and protocol keys unchanged. **Scenes:** the value stored under the old name is lost (the toggle there goes to the default on), no evidenced API for a migration.
- **Version 23 (19.11.2026):** info text for the "Speech delay timer (s)" made precise (Leon): the silence before the AI may speak on its own, not the answer time. Info field "Proactive talking: on - after 90 s of silence the AI may speak on its own (speech delay timer, not the answer delay)" / "… off (speech delay timer 0 s)" / "… off"; one sentence in the help text of the tab Voice; start line and trigger line of the app accordingly.
- **Version 23 (19.11.2026):** help and error texts redone in simple, self-explanatory English (Leon): every message says what went wrong, where to look (folder / file / VaM tab) and what to do; especially audio / WAV / TTS, missing xAI key, missing `sounddevice`, discarded files. Details and before / after: SPEC entry of 19.11.2026. Remains of the old microphone selection removed from texts (README info field description). Behavior and key redaction unchanged.
- **Version 23 (19.11.2026):** WAV hand-over without a race: the WAV is written atomically (temp name, fsync, `os.replace`) before the atomically written `speak` command (also `ToneTts` and the copy on a folder change); if the file is not yet visible, the plugin polls with `FileExists` every 0.25 s until the 15-s timeout instead of failing at once; on a start timeout the head audio source's state is also written to the plugin log. **Assessment of Leon's 15-s error:** a race between writing and playing is unlikely (the test tone and the answers were already published by renaming before, the command followed afterwards; for Leon both folders failed one after the other for 15 s each, so systematically; and a missing file would have given "file missing" instead of "did not start playing"). More likely: VaM does not load / play the clip (path form for `NormalizeMediaPath` / `QueueClip` with relative paths unevidenced), or the start detection (`AudioSource.isPlaying` plus a changed `clip`) fires although `PlayNow` plays (unevidenced assumption that `PlayNow` sets `audioSource.clip`), or the head audio source is blocked / muted. The new log names `playing=…, clip=…` on a timeout and narrows it down; TODO(verify) with Leon's next plugin log.
- **Version 23 (19.11.2026), note on `sounddevice`:** README, TECHNICAL and the app's messages now say `python -m pip install sounddevice` (binds `pip` to exactly the Python that starts the app; prerequisite for listening).

### Version 24 (19.11.2026)
- **Version 24 (19.11.2026):** the XAI API Token survives restarts (Leon, explicit wish): stored in plain text in `config.json` (`ai.xai.api_key`, next to it the pointer key `ai.xai.api_key_warning`), the field is filled on start, written back on change (only `FileManagerSecure`, all other keys stay), the companion app reads the key too. Order field > `ai.xai.api_key` > `XAI_API_KEY` > `ai.xai.key_file`. Masked display (`xai-****abcd`) through a separate display value, no new API (`contentType = Password` unevidenced, not used). Security notice "SECURITY NOTICE: …" at the top of the left info field (tab Voice) and in config.json; scenes now save only the mask, older scenes (versions 21 to 23) still contain the token. TODO(verify) in VaM: the mask appears after about 4 s, pasting over the mask, a restart fills the field. (Since version 30 the mask is applied by focus, see below.)
- **Version 24 (19.11.2026) (must-have 3, microphone / PTT / VAD / echo gate):** better voice activity detection (built-in detector with a learning basic level, hysteresis, trailing and continuous-noise rule; optional `webrtcvad` through `python -m pip install webrtcvad-wheels`, automatic fallback to the built-in detector), new keys `mic.vad_engine` (`auto` / `energy` / `webrtc`) and `mic.vad_strictness` (0–3) with menu entries in the tab Client Character, status line "Voice detection". Echo gate checked and two defects fixed (the basic level learned from the character's own voice; realtime: the microphone stays muted for the whole answer). Real echo cancellation (AEC) stays open, see BACKLOG. Test in VaM with a real microphone: `docs/TEST_PROTOCOL.md` T13.
- **Version 24 (19.11.2026):** heading in the tab Client Character: "Client Character: microphone, voice activation and push-to-talk". Checked (test `NoPluginTests`): `mic.mode` is `vad` by default; a `config.json` without `vad_engine` / `vad_strictness` yields `auto` / 2 without an error message; without a plugin in the scene the companion app opens the microphone from `config.json` alone and voice activation works (no handshake).

### Version 25 (19.11.2026)
- **Version 25 (19.11.2026) (must-have 5 remainder, gaze control):** tool `look_at` for the AI (client, camera, forward, away, off, atom by name; `seconds`), command `look_at` in the protocol, menu section "Gaze" in the tab AI Character (**Gaze control**, **Default gaze**, **Gaze follows speaker**), keys `body.gaze_control` / `gaze_default` / `gaze_follows_speaker`. Only evidenced APIs (Glance, Embody; `API_AUDIT.md` E28); with Glance on the Person AIBody stays out, if someone changes the look mode AIBody gives the eyes back. The earlier "no look-at tool because the plugin has no gaze control" no longer applies. TODO(verify) in VaM: gaze direction, "straight ahead", restoring, Glance detection (`docs/TEST_PROTOCOL.md` T14).

### Version 26 (19.11.2026)
- **Version 26 (19.11.2026) (catalog 1, 2: liveliness and scene connection, level 1):** natural gaze ("Natural (looks around)", looking away, looking up while thinking), optional blinking ("Blink control", `body.blink_control`), detection of Life Gaze / Life Eyes (AIBody stays out), scene connection for VaM's trigger UI, Timeline and other plugins: value "Scene event" (event `scene_event` to the app, the AI may react), values "AI speaking" / "User speaking", actions for gaze, blinking, expressions and gestures. The assessment of all backlog entries is in `docs/BACKLOG.md` ("Feasibility (19.11.2026)"). TODO(verify) in VaM: `docs/TEST_PROTOCOL.md` T15.

### Version 27 (19.11.2026)
- **Version 27 (19.11.2026) (catalog 4, 6: emotions, personas, memory):** expression derived from the spoken words when the AI chooses none (`ai.emotion.fallback`), fade back to neutral (`fade`), small listening face (`listening`); personas as folders with `persona.json` (menu **Persona**, `ai.persona_name`; prompt, name, language, voice), optional memory about the user (toggle **Memory**, button **Forget memory**, `memory.json` per persona, local, xAI summary). Description: `docs/PERSONAS.md`. TODO(verify) in VaM: `docs/TEST_PROTOCOL.md` T16.

### Version 28 (19.11.2026)
- Several characters in one app and a Channel field – **removed again in version 30** (see "Version 30" and the BACKLOG entry under "Removed").

### Version 29 (19.11.2026)
- **Version 29 (19.11.2026) (local engines):** language model Ollama without a key (`engines.llm: ollama`, `ai.ollama.*`), Silero voice activity detection through onnxruntime (menu value **Silero**, download the model file yourself), voice barge-in without headphones by a loudness rule (`ai.barge_in`, off by default). Description: `docs/LOCAL_ENGINES.md`. TODO(verify): `docs/TEST_PROTOCOL.md` T18.

### Version 30 (19.11.2026)
- **Network Active (spec change by Leon):** toggle in the tab Config, on by default; loopback UDP on `127.0.0.1` (one socket link, port `connection.network_port`, default 38437); never blocks the main thread; the file channel is the automatic fallback; the companion listens on `127.0.0.1` only; the token never travels over the socket; status in the info field; the plugin description carries a hint about "Allow Plugins Network Access". The only file with sockets is `SocketLink.cs`. TODO(verify) in VaM: `docs/TEST_PROTOCOL.md` T19.
- **English everywhere:** all docs, code comments, test texts and the old GitHub release notes; German file names renamed (`ANFORDERUNGEN` → `REQUIREMENTS`, `TECHNIK` → `TECHNICAL`, `TESTPROTOKOLL` → `TEST_PROTOCOL`, `LOKALE_ENGINES` → `LOCAL_ENGINES`, `SZENE_GREENSCREEN` → `SCENE_GREENSCREEN`); language scan in `tools/check_plugin.py`.
- **One character:** the multi-character feature of version 28 (channel lists, `ai.channels`, Channel field, routing by name, per-channel state, `docs/FIGUREN.md`, test step T17) was removed; the fixed folder is `default`. Old keys and scene values are tolerated and ignored.
- **Token masking by focus:** first and last 4 characters visible with stars between them, no masking while the field has focus (`InputField.isFocused`), config.json keeps the full token; the 4-second timer is gone. TODO(verify): `docs/TEST_PROTOCOL.md` T20.
- **First-run note:** one short text at the top of the plugin UI with ONE field and ONE button (Close / OK), shown only until a token exists or the note was closed (`ui.first_run_hint_dismissed`). TODO(verify): `docs/TEST_PROTOCOL.md` T21.
- **Pose commands (version 32, Leon, voice call 20.11.2026):** fixed vocabulary in `config.json` > `poses.commands` (AI Character level); starter set in Leon's wording: Sit Down, Lay Down, Prone, Stand Up, Spread Your Legs, Ankle Your Knees, Ankle Your Elbows, Turn Around, Crawl on all fours, Bend Over. **Hard gate:** a pose is emitted only when the user's ENTIRE input (trimmed, case-insensitive, trailing `.` `!` `?` ignored, white space collapsed) equals a known command; no substring or fuzzy matching ("please sit down", "sit down and smile" do nothing); enforced deterministically in the companion code, not only in the prompt (typed text, microphone, realtime transcript, remote action). The answer is the JSON `{"pose":"<id>"}`; the plugin parses it and applies the pose; both sides validate against the vocabulary, an unknown or malformed pose is never applied (short English warning in the log). A matched command gets no spoken reply (documented in SPEC.md). Free tool calls cannot apply poses any more (behaviour change, SPEC.md). A starter command without a pose file is kept but marked unavailable: never offered, never applied. Plugin UI in the tab AI Character: **Add Pose**, **Delete Pose** (starters are deletable; **Restore starter poses**); audited UI APIs only. Credits for all sources: `docs/CREDITS.md`. TODO(verify): `docs/TEST_PROTOCOL.md` T24-T29.
- **Remote control (version 31, `docs/REMOTE.md`):** local web page and HTTP API (token) and an optional OSC listener of the companion app, off by default (`remote.enabled`), bound to `127.0.0.1` only, ONE character; actions say / ask / expression / gesture / pose / look / stop / event / ptt. TODO(verify): `docs/TEST_PROTOCOL.md` T22.
- **Plugin preset (version 31):** `Custom/Atom/Person/Plugins/AIBody/Preset_AIBody.vap` in the package adds the one `.cslist` to a Person. TODO(verify): `docs/TEST_PROTOCOL.md` T23.
- **Token never in a scene (version 31):** the token field's storable is not registered with VaM any more (closes the T20 caveat).

### Version 35 (20.11.2026)
- **Starter poses from the start:** a missing, empty or unusable `poses.commands` = the 10 starters (plugin and companion).
- **Idle poses:** toggle, default pose (`Stand Up`), min / max wait (45 / 120 s); random available vocabulary poses alternating with the default pose; not while speaking or listening, 120 s cooldown after a user pose command, not with Body control off; persisted in `config.json` `body.idle_*`. TODO(verify): T31.
- **Own idle motion / breathing:** chest weight shift and breath rise in AIBody's own `IdleController`, breath cycle without the morph; no third-party idle / breathing plugin needed, no code copied. TODO(verify): `chestControl`, T32.
- **Voice pose commands:** trailing `,` `;` `:` ignored as well (C# and Python); no translations. T33.
- **Persona dropdown** always present with at least `(none)`, refilled on open. T34.
- **No start note in the menu**, only "Companion app: not connected"; **Test tone via companion** waits for the app and reports the result at the top of the Voice info. T35.
- **Body control** also gates `idle` / `breathing` commands and idle poses; documented in the info field and SPEC. T36.
- **First-start questions** in the companion console (green background first, then the standard scene). T37.

### Version 36 (20.11.2026)
- **Background color in the plugin** (tab Config: Set background color, default OFF; color picker, default #00FF00; hint "for pass-through transparency"); VaM's camera clear color + skybox off, restored on off / disable; replaces Sally's plugin. TODO(verify): T38.
- **Choose what to use: Scene / Plugin**, either / or; the scene as a fixed anchor (AI Character locked, player start), shipped in the package (`Saves/scene/AIBody/AI-Buddy.json`); third-party content of that scene is declared in `meta.json` dependencies. TODO(verify): T39, T40, T46.
- **Companion setup, two independent points:** background yes / no / abort + "Set your color for transparency", then Scene / Plugin; the background answer switches the plugin's toggle ON with that color once per setup, in any scene; the scene choice only writes the scene. Tests for all four combinations. TODO(verify): T41.
- **Latency, code only (no feature):** keep-alive HTTPS pool for STT / LLM / TTS with pre-connect on speech start, immediate main-loop wake-up, early first clause, speech files without fsync; plugin: speech starts when the clip is loaded, status texts only while the UI is open, fewer per-frame allocations. T42.

### Version 37 (20.11.2026)
- **New example scene with preview thumbnail:** Leon's two-character scene (female `Person`, built-in `Female 1`, AIBody; male `BryanGosling`, built-in `Male 4`, no plugin) replaced the old greenscreen template in version 37 as `AIBody_Example`. On 21.11.2026 (no version bump) it was replaced by **AI-Buddy**: the original scene with clothing, hair, morphs and textures kept, Dollmaster and Improved PoV removed, explicit genital morphs removed, AIBody on the female, Set background color on. In the package as `Saves/scene/AIBody/AI-Buddy.json` plus `AI-Buddy.jpg`. Plugin entry `SELF:/` inside the package. Remaining third-party packages are declared in `meta.json` dependencies; loose `Custom/` / `Saves/` files need local content and are not redistributed. TODO(verify): T44 (historical name), T46.
- **Menu rebuild from after version 36 included:** menus ordered by topic, Body control on by default, the gaze and blinking block removed, status in the left info fields with bold control labels (commit d431901). T43.

### Version 38 (21.11.2026)
- **Character configuration wizard** (tab AI Character, section Characters): gate "Do you want to configure your characters?", skip path, AI gender/body and your character gender recorded for the AI, clothing via VaM's Clothing tab. T45.
- **AI-Buddy** example scene (Leon's original scene with clothing) replaces `AIBody_Example`. T46.

### Version 39 (21.11.2026)
- **Question and Answer button removed** (Leon, call 21.11.2026 15:59): with **Proactive talking** off the character only answers when asked; Body control is no longer switched off by any button. T47.

### Version 40 (21.11.2026)
- **Character wizard shows its question again:** the gate answer is per scene (it was seeded from the global config.json into every new scene, so the question never came); the question stands above **Yes** / **No**; stored answers refresh the section. T48.
- **Persona menu:** AIBody Companion writes the starter personas Anna and Marc once into an empty personas folder; an empty persona means "(none)". T49.
- **Plugin log:** the "not connected" hint and the test-tone wait line once per VaM session, at most one waiting test tone; hints point to the Start menu entry **AIBody Companion**. T50.
- **AIBody Companion Setup.exe:** per-user Windows installer (no admin), Start menu and optional desktop shortcut, optional Start with Windows, background note, tray Quit, single instance, VaM folder detection or a one-time folder picker, uninstaller; built and self-tested by GitHub Actions. T51.

### Version 41 (21.11.2026, Leon 17:01-17:27)
- **Installer asks for the VaM folder** (Leon, 17:01): wizard page **Your VaM folder**, prefilled by auto-detection, only a folder with `VaM.exe` is accepted, changeable by running the setup again; written to `%LOCALAPPDATA%\AIBody Companion\launcher.json`, which the app reads first. Silent setup: `/VAMDIR="..."`. The in-app folder picker is only the fallback. T52.
- **Reset to Default** (Leon, 17:01): tab Config > Reset, with **Confirm Reset to Default** / **Cancel**; all saved plugin settings of the scene back to their defaults, including the character wizard's answers; the XAI API Token, the key file paths, pose commands, personas and the companion's own config sections are kept. T53.
- **AI-Buddy scene: AIBody on the male `BryanGosling`** (Leon, 17:02), with its saved values (Set background color on, #00FF00); the female `Person` has no plugin; the rest of the scene is unchanged. T54.
- **Speech audio** (Leon, 17:19/17:21: it never worked): plays only after the WAV's audio data is loaded (`loadState` Loaded, `LoadAudioData()`), with the load and play calls of audited working plugins (API_AUDIT E36); `[audio]` debug lines behind **Verbose log**. TODO(verify): T55.
- **Installer messages** are message boxes with **OK** that wait. T51/T52.
- **Voice menu with all xAI voices:** the 28 built-in voices of docs.x.ai, replaced by the companion's answer of `GET /v1/tts/voices`. T56.
- **Persona menu:** every persona folder and loose `<name>.json`; the starters Anna and Marc also next to own personas (only these two are shipped). T49.
- **Pose commands:** **Apply pose command** for the chosen entry, results and errors in the left field and the log; **Add Pose** without text takes the pose name. T57.
- **Right column:** headers and controls only; no new info field without Leon's approval.
- **No spoken tool calls:** `<tool_call>...</tool_call>` text from the model is run, not spoken. T58.

### Version 42 (21.11.2026, Leon 18:27 and 18:33)
- **Pose command applies on choosing**; the **Pose** dropdown, **Apply pose** and **Apply pose command** are gone. T59.
- **Add Pose** asks for the pose file (VaM's file browser) and the spoken command; **Delete Pose** removes the chosen command; both are kept in `config.json` at once. T59/T60.
- **Reset poses:** AI back to the scene placement first, Client 0.5 s later. T61.
- **AI-Buddy is Leon's scene** (`AI`, `Client`, greenscreen kept): AIBody on `Client`, driving the Person named `AI` (speech, poses, expressions, idle motion). T62.
- **Version check:** the companion warns when the scene loads an older plugin package (Leon's v41 test ran plugin 40: his scene pinned `d0n.AIBody.40`). T62.
- **Audio:** v41's evidenced play sequence, still unverified in VaM (it never ran there); `[audio]` lines from VaM's log requested. T63.
- **Voice menu scrolls**: all 28 xAI voices reachable (companion list from `GET /v1/tts/voices`, static fallback from docs.x.ai). T64.
- **Realtime:** a response that was only a tool call is followed by one request for the spoken answer.

### Version 43 (21.11.2026, Leon 20:04-20:05)
- **Test tone louder:** peak 0.70 of full scale (was 0.35, +6 dB), both the bundled WAV and the companion's tone. T65.
- **Update notice:** the installed companion asks GitHub at start for a newer release and offers to open its page; silent offline. T66.
- **Uninstall removes our packages:** `d0n.AIBody.<n>.var` at the top of `<VaM>\AddonPackages`, nothing else. T67.
- **speech_ended reason:** `completed` when a clip played to its end; `interrupted` only for a real barge-in or stop. T68.
- **v42 installer "no longer works":** no regression found in the installer script, workflow or CI run (same toolchain, install / self-test / uninstall passed); details from Leon needed. T69.

### Version 44 (21.11.2026, Leon 20:39-21:09)
- **The setup installs the package:** `AIBody Companion Setup.exe` carries `d0n.AIBody.<v>.var` (built in CI before Inno Setup; the build fails without it) and copies it to `<VaM>\AddonPackages`. No earlier setup (v40-v43) ever did. T70.
- **Every install removes the other `d0n.AIBody.<n>.var`** (also a first install over hand-placed packages), option **Remove older AIBody packages** on by default; nothing else is cleaned up (Leon 21:08). T70.
- **Existing install reported:** same version: "already installed", OK = reinstall / repair, Cancel = stop; older: "Update from <old> to <new>". Silent setups never ask. T71.
- **Running companion closed:** the setup ends it (taskkill) before replacing files; the companion now accepts Windows' close request (pystray's tray windows refused it, the v43 setup looped on "files in use"). Setup log always written. T72, T69.
- **Speech volume up to 3:** one slider for speech and test tones; above 1 the companion multiplies its WAVs by the volume (plain linear gain, no limiter, Leon 21:15/21:16); **Play test tone** uses 2x / 3x copies. Default 1 unchanged. T73. Since 22.11.2026 (Leon 04:15) the slider shows percent: **Speech volume (%)** 0–1000 (Leon 04:16; 0–300 at 04:15), default 100, plain linear gain, no limiter; config.json and the event keep the factor 0–10; test tone copies stay 2x / 3x; old saved factors load as percent (1 → 100). T75.
- Not in v44 (v45): config-menu commands for the AI, post-command / Add Pose follow-ups.

### Version 45 (21.11.2026, Leon 21:25 / 22:25)
- **The package survives a failed setup run:** older `d0n.AIBody.<n>.var` are removed only after the install succeeded and the new package is in AddonPackages with the bundled SHA-256 (v44 removed them before copying; a failed / cancelled install then left no package, Leon's v44 test). If the new package is not there, the older ones stay and the setup says so. T74.
- **No option "Remove older AIBody packages" any more:** the other `d0n.AIBody.<n>.var` are always removed (Leon 22:25). T74.
- **A companion that cannot be ended stops the setup before anything changes** (Preparing to Install), instead of failing halfway; taskkill without `/T`. T74.

## 2. Still open / to do

### Next version
_Version 21 implemented the field "XAI API Token" and the button "Question and Answer" (see above, AI and speech)._
- ~~All pose entries (Apply pose, Reload poses and everything else about poses) belong in a sub-section "Poses" in the tab AI Character, not in Config. Reason: poses belong to one character and make sense only for the AI Character, not for the Client Character (Leon, 18.11.2026). State in the code since version 15: Apply pose and Reload poses are already in the section Poses in the tab AI Character; Config contains only Reload Config JSON, Companion inbox poll interval (s) (until version 18 "File poll interval (s)"), Network Active (since version 30), Verbose log. Check in VaM whether pose entries still appear under Config (perhaps an older package version was loaded).~~ Closed in version 31 with a source test (`Version31LayoutTests`); if Leon still sees pose entries under Config, an old package is loaded.
- ~~Everything that hangs under Config in Leon's view ("basically everything that comes under Config"), in particular Expression and gesture and what follows below it (e.g. Body), move under the AI Character or group it there, so that character-bound controls are clearly assigned to the AI Character. The exact layout does not matter (Leon, 18.11.2026). State in the code since version 15: Expression and gesture and Body are already in the tab AI Character; the tab Config contains only Reload Config JSON, Companion inbox poll interval (s), Network Active and Verbose log (not character-bound). Clarify which version Leon sees in VaM.~~ Closed in version 31 (same source test).
- ~~Move the two info text fields at the bottom of the tab AI Character into the large info field on the left (only controls on the right; rule: configurable things in the menu and mirrored in config.json, info on the left) (Leon, 18.11.2026). Which two fields exactly: determine when implementing, from Leon's view in version 20.~~ Closed in version 31: no `Text(` field is left in any right-hand tab (source test); all help and status texts are in the left info field.
- ~~Companion web / OSC remote~~ and ~~plugin presets~~: done in version 31 (`docs/REMOTE.md`; preset `Custom/Atom/Person/Plugins/AIBody/Preset_AIBody.vap`); VaM tests T22 / T23 are open. Still open, all Backlog: trigger UI stage 2, Hub publishing and the demo scene (parked).

### Test in VaM (instructions `docs/TEST_PROTOCOL.md`)
- T1: loading from the `.var`, prompt about plugins from the package, old packages removed.
- T2: `ReadAllText` / `DeleteFile` accept the paths from `GetFiles`.
- T3: head audio with lip sync, `PlayNow` retry, start / end detection.
- T4: menu refresh, text field, tabs.
- T5: pose memory name, morph names, breath morph (readable directly in the self-test and in the companion app's log since version 13).
- T6: add / remove / save / reload without exceptions and FPS drop; "DISCONNECTED" and reconnect; config.json without a prompt.
- T7: engine status.
- T8: realtime with a real xAI key, interrupting, proactive speaking.
- T9: question → audible answer in the game.
- T10: Verbose log, realtime toggle.
- T11: microphone settings (without device selection), pose / expression menu, tool calls, latency display.
- T12: field "XAI API Token" (pasting, status, saving / loading the scene), button "Question and Answer" two lines centered (since version 21).
- T13–T16, T18: voice detection and echo gate, gaze, natural gaze / blinking / scene hooks, emotions / personas / memory, local engines.
- T19: Network Active (toggle on / off, VaM's network switch off → file fallback, companion not running).
- T20: token masking by focus. T21: first-run note. T22: remote control (web page, HTTP, OSC). T23: plugin preset (Load Preset).
- T38–T42: background color, scene from the package, setup Scene / Plugin, speech start (version 36). T43: eyes belong to VaM, Body control ON, menus by topic. T44: example scene thumbnail in Load Scene and AIBody on the female (version 37). T45: character wizard. T46: AI-Buddy scene (version 38). T47: no Question and Answer button (version 39). T48-T51: character wizard question, persona menu, companion log hints, AIBody Companion installer (version 40). T52-T54: installer VaM folder page, Reset to Default, AIBody on BryanGosling (on main after version 40).
- The engines have never run against the real xAI / ElevenLabs APIs (only a rebuilt server).

### TODO(verify) in the code
- `GetFiles` paths are accepted by `ReadAllText` / `DeleteFile` (1.22).
- A 1.5 s wait after a scene change is enough.
- Relative `Saves/PluginData` path with `NormalizeMediaPath` + audio loader.
- Breath morph: no standard morph in VaM, choose a chest morph on the character.
- Editable text field through `CreateTextField` (1.22); pasting with Ctrl+V into the field "XAI API Token".
- Network: behavior of VaM with "Allow Plugins Network Access" off (exception caught, plugin refused, or a prompt); `InputField.isFocused` on VaM's text fields.
- ~~Button "Question and Answer": two lines, centered (version 22)~~: obsolete, the button is removed in version 39.
- `GetFiles` on a `Custom/` folder in the sandbox (pose files).
- Storable "PosePresets" follows the evidenced pattern (1.22).
- Morph names for expressions on standard figures (female / male).
- Scene: people facing +Z (0° / 180° = facing each other), look without fixed clothing, Camera Background Color on a Person atom.
- ~~Cause of Leon's empty microphone menu (version 16)~~: obsolete, the microphone selection is removed since 19.11.2026.
- Visible height of the info field (1800) in VaM.

### Open questions for Leon
- Version 42: the exact order of headers and buttons you want (no exact instruction was found; now by topic, Poses in your order of 18:27). Should **Reset poses** replace **Restore starter poses**? Which of your saved plugin values should the shipped AI-Buddy scene carry (now only greenscreen and the two genders)?
- ~~A direct API key field in the plugin?~~ Decided 18.11.2026: yes, field "XAI API Token" (implemented in version 21, see AI and speech).
- Key file path back in the menu (labeled)? Since version 15 only in config.json, because the fields appeared as empty boxes; see Backlog.
- "Delay": what should be delayed? Placeholder removed from the menu since version 15, see Backlog.
- Session config vs. Person config: deferred until after the tests, see Backlog.

### Not yet implemented (agreed)
- ~~Demo / tutorial scene.~~ Shipped in the package since version 36; version 37 is Leon's two-character example with a Load Scene preview thumbnail (T44).
- Documentation and publication on the VaM Hub ("Plugins + Scripts", with tags).
- Deferred (formerly "we want", details in BACKLOG): session / person split with session connection and bootstrap plugin, client on its own atom.

## 3. Ideas and spec
- Nice to have, deferred ideas and approaches (path display, in-game test plugin, key field, delay, session / person config, tooltip, client on its own atom, bootstrap, gaze control, personas, Life / LogicBricks functions, local engines, better VAD, echo cancellation and more; also what was dropped for good): [`docs/BACKLOG.md`](BACKLOG.md).
- Agreed specification including the tab layout: [`docs/SPEC.md`](SPEC.md).

## Fixed constraints
- Sandbox rule and only evidenced APIs (see SPEC).
- Internet access only in the companion app; the plugin may use one loopback socket to the companion app (Network Active, `SocketLink.cs`). The remote control (version 31) lives in the companion app and binds `127.0.0.1` only.
- Do not touch LICENSE and `licenseType` "FC" in `meta.json`; the license question is out of scope.
- No secrets in the repository.
- Push directly to `main` in meaningful, individually green commits.
- Everything in English: code, README, docs, release notes (since 19.11.2026); release notes give the full path from the VaM main folder, the loading location (Plugins tab of the Person), a request for a screenshot, red `AIBody:` log lines and the companion app's console output.

## Sources to learn from
- MacGruber: [LogicBricks](https://hub.virtamate.com/resources/logicbricks.1975/), [Life](https://hub.virtamate.com/resources/life.165/), [Benchmark](https://hub.virtamate.com/resources/benchmark.11336/), [Utils](https://hub.virtamate.com/resources/macgruber-utils.40744/)
- AcidBubbles: Timeline, Glance, Keybindings (bootstrap through `CreatePlugin`)
- VamDeluxe: [DeluxePlugin / DollMaster](https://github.com/vamdeluxe/DeluxePlugin) (audio loader, personas as data)
- hazmhox: [VAMStory](https://hub.virtamate.com/resources/vamstory.28256/) (story control on its own atom)
