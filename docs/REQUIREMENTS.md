# AIBody – requirements catalog (status overview)

Status: 19.11.2026, version 30. Overview of what is done and what is open; updated with every release.
- Agreed specification (what applies): [`docs/SPEC.md`](SPEC.md)
- Deferred ideas / nice to have: [`docs/BACKLOG.md`](BACKLOG.md)
- Test instructions in VaM: [`docs/TEST_PROTOCOL.md`](TEST_PROTOCOL.md) · API evidence: [`docs/API_AUDIT.md`](API_AUDIT.md)
- Repo: https://github.com/d0n/vam_plugin · current package: `d0n.AIBody.30.var` (version = package number since 12)

"Done" means: tested in code and against rebuilt counterparts. What has not yet been checked in VaM or against the real xAI APIs is listed again under 2.

## 1. Done

### Loading, sandbox, package
- One plugin, one `.cslist` (`Custom/Scripts/d0n/AIBody/AIBody.cslist`), one MVRScript class, loaded in one step in the Person's Plugins tab – v0.6.0.
- Strict sandbox (no `UnityWebRequest`, `UnityEngine.Networking`, `WWW`, `System.IO`, `Process`, reflection, `DllImport`, Unity `Microphone`); the build scan fails otherwise – v0.6.1. Until version 29 the plugin had no network code at all; since version 30 `System.Net` / sockets are allowed in exactly one file (`SocketLink.cs`), see "Version 30".
- Only evidenced APIs, evidence in `docs/API_AUDIT.md` (E1–E27) – v0.6.1, extended continuously.
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
- Tool calls → body commands (chain: `/v1/responses` with tools; realtime: `function_call` + `function_call_output`): `express` (expression / gesture), `pose` (if poses exist); every call gets a result; no tools in `qa` and with Body control off – v0.7.4.
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
- Scene template green screen / passthrough (Sally's *Camera Background Color* #00FF00): `examples/scenes/AIBody_GreenScreen.json`, `docs/SCENE_GREENSCREEN.md` – v0.7.x (wish 17.11.2026); package reference corrected to the current package – after v0.7.4.
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

## 2. Still open / to do

### Next version
_Version 21 implemented the field "XAI API Token" and the button "Question and Answer" (see above, AI and speech)._
- All pose entries (Apply pose, Reload poses and everything else about poses) belong in a sub-section "Poses" in the tab AI Character, not in Config. Reason: poses belong to one character and make sense only for the AI Character, not for the Client Character (Leon, 18.11.2026). State in the code since version 15: Apply pose and Reload poses are already in the section Poses in the tab AI Character; Config contains only Reload Config JSON, Companion inbox poll interval (s) (until version 18 "File poll interval (s)"), Network Active (since version 30), Verbose log. Check in VaM whether pose entries still appear under Config (perhaps an older package version was loaded).
- Everything that hangs under Config in Leon's view ("basically everything that comes under Config"), in particular Expression and gesture and what follows below it (e.g. Body), move under the AI Character or group it there, so that character-bound controls are clearly assigned to the AI Character. The exact layout does not matter (Leon, 18.11.2026). State in the code since version 15: Expression and gesture and Body are already in the tab AI Character; the tab Config contains only Reload Config JSON, Companion inbox poll interval (s), Network Active and Verbose log (not character-bound). Clarify which version Leon sees in VaM.
- Move the two info text fields at the bottom of the tab AI Character into the large info field on the left (only controls on the right; rule: configurable things in the menu and mirrored in config.json, info on the left) (Leon, 18.11.2026). Which two fields exactly: determine when implementing, from Leon's view in version 20.
- Open again after the v30 release build (unfinished, so not part of it): **companion web / OSC remote** (localhost only, off by default) and **plugin presets** (chunk 3 of the 19.11.2026 plan). Also still open: trigger UI stage 2, Hub publishing and the demo scene (parked).

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
- T20: token masking by focus. T21: first-run note.
- The engines have never run against the real xAI / ElevenLabs APIs (only a rebuilt server).

### TODO(verify) in the code
- `GetFiles` paths are accepted by `ReadAllText` / `DeleteFile` (1.22).
- A 1.5 s wait after a scene change is enough.
- Relative `Saves/PluginData` path with `NormalizeMediaPath` + audio loader.
- Breath morph: no standard morph in VaM, choose a chest morph on the character.
- Editable text field through `CreateTextField` (1.22); pasting with Ctrl+V into the field "XAI API Token".
- Network: behavior of VaM with "Allow Plugins Network Access" off (exception caught, plugin refused, or a prompt); `InputField.isFocused` on VaM's text fields.
- Button "Question and Answer": `buttonText.alignment` and `height` (90) visibly two lines, centered, not cut off in VaM (version 22).
- `GetFiles` on a `Custom/` folder in the sandbox (pose files).
- Storable "PosePresets" follows the evidenced pattern (1.22).
- Morph names for expressions on standard figures (female / male).
- Scene: people facing +Z (0° / 180° = facing each other), look without fixed clothing, Camera Background Color on a Person atom.
- ~~Cause of Leon's empty microphone menu (version 16)~~: obsolete, the microphone selection is removed since 19.11.2026.
- Visible height of the info field (1800) in VaM.

### Open questions for Leon
- ~~A direct API key field in the plugin?~~ Decided 18.11.2026: yes, field "XAI API Token" (implemented in version 21, see AI and speech).
- Key file path back in the menu (labeled)? Since version 15 only in config.json, because the fields appeared as empty boxes; see Backlog.
- "Delay": what should be delayed? Placeholder removed from the menu since version 15, see Backlog.
- Session config vs. Person config: deferred until after the tests, see Backlog.

### Not yet implemented (agreed)
- Demo / tutorial scene.
- Documentation and publication on the VaM Hub ("Plugins + Scripts", with tags).
- Companion web / OSC remote and plugin presets (see "Next version").
- Deferred (formerly "we want", details in BACKLOG): session / person split with session connection and bootstrap plugin, client on its own atom.

## 3. Ideas and spec
- Nice to have, deferred ideas and approaches (path display, in-game test plugin, key field, delay, session / person config, tooltip, client on its own atom, bootstrap, gaze control, personas, Life / LogicBricks functions, local engines, better VAD, echo cancellation and more; also what was dropped for good): [`docs/BACKLOG.md`](BACKLOG.md).
- Agreed specification including the tab layout: [`docs/SPEC.md`](SPEC.md).

## Fixed constraints
- Sandbox rule and only evidenced APIs (see SPEC).
- Internet access only in the companion app; the plugin may use one loopback socket to the companion app (Network Active, `SocketLink.cs`).
- Do not touch LICENSE and `licenseType` "FC" in `meta.json`; the license question is out of scope.
- No secrets in the repository.
- Push directly to `main` in meaningful, individually green commits.
- Everything in English: code, README, docs, release notes (since 19.11.2026); release notes give the full path from the VaM main folder, the loading location (Plugins tab of the Person), a request for a screenshot, red `AIBody:` log lines and the companion app's console output.

## Sources to learn from
- MacGruber: [LogicBricks](https://hub.virtamate.com/resources/logicbricks.1975/), [Life](https://hub.virtamate.com/resources/life.165/), [Benchmark](https://hub.virtamate.com/resources/benchmark.11336/), [Utils](https://hub.virtamate.com/resources/macgruber-utils.40744/)
- AcidBubbles: Timeline, Glance, Keybindings (bootstrap through `CreatePlugin`)
- VamDeluxe: [DeluxePlugin / DollMaster](https://github.com/vamdeluxe/DeluxePlugin) (audio loader, personas as data)
- hazmhox: [VAMStory](https://hub.virtamate.com/resources/vamstory.28256/) (story control on its own atom)
