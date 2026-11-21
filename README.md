# AIBody

Virt-A-Mate plugin (VaM 1.22) with a Python companion app that gives an AI a body in a VaM scene. Status: version 44, package `d0n.AIBody.44.var`, release `v44`. Version 14 loads in VaM 1.22 without errors (init done, 200 poses); the functions have not yet been fully checked in VaM.

Version scheme since version 12: version = package number of the `.var` (plugin display, companion app, Git tag `v<N>`). Version 12 follows 0.7.4 (= package 11); older tags stay unchanged.

More documents: [SPEC](docs/SPEC.md) (agreed scope) · [REQUIREMENTS](docs/REQUIREMENTS.md) (done / open) · [BACKLOG](docs/BACKLOG.md) (deferred ideas) · [TEST_PROTOCOL](docs/TEST_PROTOCOL.md) · [TECHNICAL](docs/TECHNICAL.md) (architecture, protocol, sandbox) · [REMOTE](docs/REMOTE.md) · [API_AUDIT](docs/API_AUDIT.md) · [Releases](https://github.com/d0n/vam_plugin/releases) (installation and quick start per version in the release notes).

## Getting started

You start VaM as usual. AIBody has two parts:

- **The plugin and the scene** come in one package, `d0n.AIBody.<N>.var`. Since version 44 `AIBody Companion Setup.exe` puts it into `<VaM main folder>/AddonPackages/` for you and removes older `d0n.AIBody.<number>.var` files (option **Remove older AIBody packages**, on by default); without the setup put it there yourself (delete older `d0n.AIBody.*.var` files). In VaM both are found under the add-on packages: the scene via the main menu **Open Scene** > package `d0n.AIBody.<N>` > `AIBody` > **AI-Buddy**, the plugin via Person > tab **Plugins** > **Add Plugin** > `d0n.AIBody.<N>` > `AIBody.cslist`.
- **AIBody Companion** is a small Windows app that runs in the background on the same computer and does the listening and talking: microphone, speech recognition, the AI (xAI) and the voice. VaM plugins run in a sandbox without internet, microphone access or the right to start programs, so this part cannot live inside VaM. The plugin connects to it by itself; you only start it.

**Install AIBody Companion (once):**

1. Download `AIBody Companion Setup.exe` from the [release](https://github.com/d0n/vam_plugin/releases) and double-click it. It installs for your user only, without admin rights, into `%LOCALAPPDATA%\Programs\AIBody Companion`.
2. Windows SmartScreen may say "Windows protected your PC", because the installer is not signed: click **More info**, then **Run anyway**.
3. Choose the options: a desktop shortcut (optional) and **Start with Windows** (off by default).
4. Page **Your VaM folder**: the setup has already looked for your VaM folder and filled it in; check it or click **Browse** and choose the folder that contains `VaM.exe` (a folder without `VaM.exe` is not accepted). AIBody Companion uses this folder from now on; to change it, run the setup again. At the end **Launch AIBody Companion now** starts it. Uninstall it like any app (Settings > Apps, or "Uninstall AIBody Companion" in the Start menu).

**Install over an existing version (version 44):** run the new setup over the old one, no uninstall needed. At start it says what it found: the same version ("AIBody <v> is already installed": **OK** reinstalls / repairs, **Cancel** stops) or an older one ("Update from AIBody <old> to <new>"). A running AIBody Companion is closed by the setup. Nothing else is removed (settings, launcher.json and logs stay); every setup run writes a log `%TEMP%\Setup Log <date> #<n>.txt`.

**Every time:** start **AIBody Companion** from the Start menu (or let Windows start it). A message box says it is now running in the background; click **OK**. Then an icon in the tray has **Quit**. Starting it again only shows a message box that it is already running. It uses the VaM folder chosen during setup; only if that folder is gone (for example VaM was moved) it looks for VaM by itself and, failing that, asks once with a folder picker and remembers the answer. Then start VaM and load the AI-Buddy scene or add the plugin to a Person.

What it uses on your computer: it listens only on `127.0.0.1` (this computer) for the plugin, and goes out only to the AI service (xAI; ElevenLabs only if you set it up). Since version 43 the installed app also asks GitHub once at start whether a newer AIBody release exists (one anonymous request to `api.github.com`, nothing downloaded; it offers to open the release page; off with `"update_check": false` in `%LOCALAPPDATA%\AIBody Companion\launcher.json`). Uninstalling AIBody Companion also deletes the AIBody packages `d0n.AIBody.<n>.var` from `<VaM>\AddonPackages` (only those files). Its settings and log stay under `<VaM main folder>/Saves/PluginData/AIBody/`; the VaM folder chosen during setup is kept in `%LOCALAPPDATA%\AIBody Companion\launcher.json`. The installer never contains an API key.

### For developers: running the companion from source

The companion app can also run from this repository (any OS with Python), **started by hand** in a console, **separately from VaM**:

```
python -m aibody_companion --vam-root "D:\VaM"
```

(Adjust the path to your own VaM folder, i.e. the folder with `VaM.exe`.) Keep the window open as long as VaM runs. On Windows, [`companion/start_companion.bat`](companion/start_companion.bat) does the same by double-click and remembers the VaM folder in `companion/vam_root.txt` (not in git). The installer is built by `.github/workflows/companion-windows.yml` (PyInstaller + Inno Setup, with a `--selftest` of the built app).

- **From which folder:** the command works when you are in the repository's `companion` folder (`cd companion`). Alternatively run `pip install -e .` once in the `companion` folder; then the same command works from any folder. If Python says `No module named aibody_companion`, you are in the wrong folder (and have not installed the package).
- **Microphone:** `python -m pip install sounddevice` (or `python -m pip install -r requirements.txt` in the `companion` folder). Without `sounddevice` there is no listening (the app always records from the system's default input device; there is no microphone menu); typing in the console still works.
- **Python:** version 3.10 or newer.
- **xAI key:** in the plugin, tab **Voice** > *Companion connection*, field **XAI API Token** (below *API Reconnect*); on the very first start a short note at the top of the plugin asks for it. The token is then saved in `config.json` (`ai.xai.api_key`, **plain text**, see the security notice below); alternatively the environment variable `XAI_API_KEY` or `ai.xai.key_file`; more below.
- **Plugin and scene, one download (version 44):** `d0n.AIBody.44.var` holds both, findable on their own: the **plugin** (Person > Plugins > Add Plugin > `d0n.AIBody.44:/Custom/Scripts/d0n/AIBody/AIBody.cslist`) and the **scene** (main menu Open Scene / Load Scene > package `d0n.AIBody.44` > `AIBody` > **AI-Buddy**, path in the package `Saves/scene/AIBody/AI-Buddy.json` with the preview `AI-Buddy.jpg`; it loads the plugin of the same package via `SELF:/`). The package also has the scene and the thumbnail as loose files `AI-Buddy.json` / `AI-Buddy.jpg` (optional): copy both to `<VaM main folder>/Saves/scene/AIBody/`. The scene uses third-party clothing, hair and morph packages listed in `meta.json` dependencies (VaM reports them if they are missing) and a few loose `Custom/` / `Saves/` files that need local content; see [`docs/SCENE_GREENSCREEN.md`](docs/SCENE_GREENSCREEN.md).
- **First start (version 36, from source only; the installed AIBody Companion has no console and skips these questions: switch the background in the plugin, tab Config > Set background color, and load the scene from the package):** the app asks two independent questions once in its console: "Do you want a greenscreen background?" (yes / no / abort; with yes "Set your color for transparency", default #00FF00) and "Choose what to use": **Scene** (the AI-Buddy scene, also in the package: VaM > Open Scene > `d0n.AIBody.<N>` > AI-Buddy) or **Plugin** (AIBody on a Person of your own scene). The background answer only switches the plugin's **Set background color** (tab Config) on with that color; the Scene / Plugin answer only decides whether the scene is written. `--setup` asks again, `--no-setup` never.
- **Get a new version:** install the new `AIBody Companion Setup.exe` over the old one (from source: `git pull` in the repository folder, otherwise the app reports an old version; the app prints `AIBody companion <version>` on start).
- **Remote control (version 31, optional):** a local web page / HTTP API and OSC for this one character, off by default, `127.0.0.1` only: [docs/REMOTE.md](docs/REMOTE.md). **Plugin preset:** the package also holds `Custom/Atom/Person/Plugins/AIBody/Preset_AIBody.vap`, which adds the plugin to a Person (Person > Plugins > Load Preset; not yet tested in VaM).
- **Network:** the plugin and the app talk through files and, by default, through a loopback socket (toggle **Network Active**, see below). The socket needs VaM's global setting *User Preferences > Security > Allow Plugins Network Access*; without it everything still works through the files.

## 1. Purpose and use

- The user talks to a character in VaM. The character answers with voice and lip sync and can show expressions and gestures, plus breathing and head idle, and takes **pose commands** (version 32: an exact phrase such as `Sit Down` applies a linked pose, see below and [docs/SPEC.md](docs/SPEC.md)). Since version 27: expressions even without the AI's help (from the words, fading back, listening face), **personas** (character, language, voice per folder) and an optional **memory** about the user, see [docs/PERSONAS.md](docs/PERSONAS.md). Since version 29: the **local language model Ollama**, **Silero** as voice activity detection, **voice barge-in by a loudness rule** (all in the companion app), see [docs/LOCAL_ENGINES.md](docs/LOCAL_ENGINES.md). Since version 30: the optional **Network Active** loopback link, everything in English, one character per app.
- Two parts, both required:
  - Plugin `AIBody` (C#, one optional loopback socket, no internet code): loaded once in the Plugins tab of the AI character (Person atom); plays speech, controls the body, shows status and settings.
  - Companion app `aibody_companion` (Python, runs next to VaM on the same PC): microphone, speech recognition, language model, speech output, connection to xAI (optionally ElevenLabs). **One app controls exactly one character.**
- Connection: files under `<VaM>/Saves/PluginData/AIBody/default/` and, on top, an optional UDP link on `127.0.0.1`; speech as WAV under `<VaM>/Custom/Sounds/AIBody/default/`.
- Flow: load the plugin on the AI character → start the companion app by hand (`python -m aibody_companion --vam-root "D:\VaM"`, section "Getting started", with an xAI key) → speak (or type in the console) → the character answers.
- Quick install: `d0n.AIBody.44.var` into `<VaM>/AddonPackages/`, delete older `d0n.AIBody.*`, `d0n.AIBodySession.*`, `d0n.AIBodyPerson.*`, `d0n.AIBodyPerson2.*`; select the Person > tab Plugins > Add Plugin > `AddonPackages > d0n.AIBody.44:/Custom/Scripts/d0n/AIBody/AIBody.cslist`; companion app: see "Getting started" (`cd companion`, `pip install sounddevice`, then start). Details and step by step: release notes.

## 2. What it is designed for / specification

- Bundled scene: [`examples/scenes/AI-Buddy.json`](examples/scenes/AI-Buddy.json) with the preview [`examples/scenes/AI-Buddy.jpg`](examples/scenes/AI-Buddy.jpg) (in the package as `Saves/scene/AIBody/AI-Buddy.json` and `AI-Buddy.jpg`), guide [`docs/SCENE_GREENSCREEN.md`](docs/SCENE_GREENSCREEN.md). Content (version 42, Leon's scene): two people, `AI` (female, `Female 1`, no plugin) and `Client` (male, `Male 4`) with AIBody in the Plugins tab and **Set background color** on (#00FF00); AIBody on `Client` drives `AI`; clothing, hair and looks from the original scene; no scene plugin. Third-party packages are declared in `meta.json` dependencies. An optional greenscreen is AIBody's own function (tab Config > Background). The headset / streaming program makes a chosen color transparent by chroma key; VaM itself only shows the color. Not tested in VaM.
- AIBody also works in other scenes, as long as it sits on the AI's Person.
- Short version of the specification (complete: [SPEC.md](docs/SPEC.md)):
  - VaM sandbox: no `UnityWebRequest` / internet, `System.IO`, reflection or microphone code in the plugin; only evidenced APIs; file access only through `FileManagerSecure`; sockets only in the one file `SocketLink.cs` (loopback only).
  - Internet access only in the companion app.
  - One plugin, one `.cslist`, one MVRScript class, one loading step.
  - File transport (protocol v3), an optional loopback socket on top, and one shared `config.json`.
  - xAI needs an API key from console.x.ai; a Grok subscription does not work. You enter it in the plugin: tab **Voice**, section *Companion connection*, field **XAI API Token** (a simple text field, no format check), or in the note shown at the top on the first start. The plugin saves the token in `config.json` (`ai.xai.api_key`, plain text, at Leon's explicit wish), fills the field from it on start and shows it masked: the first 4 and the last 4 characters stay visible with stars between them (`xai-****abcd`), and the full text is shown while the field has focus. **Security notice:** anyone who can read `config.json` can read the token; never share or publish the file. Scenes save only the mask, but a scene saved with versions 21 to 23 still contains the token in plain text and must not be published. The notice is also in the left info field (tab Voice) and in `config.json` (`ai.xai.api_key_warning`).
  - Default mode simple Q&A (speech only); realtime optional.
  - The AI controls expressions and gestures by tool call (not in Q&A mode, not with Body control off). **Poses are not a tool** (since version 32): a pose is applied only when your WHOLE input (typed or spoken) equals a pose command such as `Sit Down` (case, surrounding spaces and trailing `.` `!` `?` are ignored; `please sit down` does nothing). Commands and their poses live in `config.json` > `poses.commands` and are edited in the tab AI Character (**Add Pose**, **Delete Pose**). Poses can also be applied manually there.
  - The menu shows only what can be set (tabs Voice, AI Character, Client Character, Config); all help and status texts are in one large info field on the left.
  - Verbose log and latency measurement (end of speech to first sound) in the status field.

## 3. Two characters: AI Character and Client Character

- AI Character = the AI's body: the Person the plugin is loaded on. Tab *AI Character*: AI mode, voice, poses, expressions, gestures, body.
- Client Character = the human user who talks to the AI. Tab *Client Character*: microphone (recorded by the companion app on the PC), push-to-talk, voice barge-in.
- In the bundled scene (version 42, Leon's scene) each role is its own Person: the AI character `AI` (female, no plugin of its own) and your own figure `Client` (male), which carries AIBody with the background color. AIBody on `Client` finds the Person named `AI` and speaks, poses and moves with it.
- Implementation: AIBody sits only on the AI Person and knows no client atom; the settings of both roles live in this one plugin. The user's input still comes through the microphone / push-to-talk or text input in the companion app's console, not through the client atom.
- **One AI character per app.** A second AI character is not supported (the multi-character feature of version 28 was removed in version 30); for another one run a second VaM instance with its own companion app.
- Not intended and not tested:
  - AIBody without a user side (without a running companion app there is neither listening nor answering; the plugin stays stable and shows "DISCONNECTED").
  - AIBody on a non-Person atom (the plugin window then only explains where it belongs).
  - The scene with only one Person: AIBody itself runs then, but the scene is built for two people (background plugin on the client atom).

## 4. Settings

### 4.1 Locations and precedence

- Plugin menu (right column, tabs): values are saved with the scene.
- `config.json`: `<VaM>/Saves/PluginData/AIBody/config.json`, one file, read by the plugin and the companion app. Schema: `protocol/schema/config.schema.json`, example: `examples/config.json`.
  - If the file is missing: the companion app creates it with default values on start; the plugin writes it about 2 s after loading from its menu values.
  - A scene without saved AIBody values (internal field "Settings initialized" = false): the plugin takes over the file once.
  - A scene with saved values: the menu values win and are written back (within 1 s after a change).
  - Tab *Config* > **Reload Config JSON**: applies the whole file to the menu and sends it to the app.
  - The companion app reads the file on start (microphone, engines, `ai`, `advanced.verbose_log`, network) and completes missing `ai` keys with default values. Changes in the menu arrive live as a `config` event.
  - The plugin writes numbers and true/false as text (`"2.5"`, `"true"`); both forms are valid.
  - Unknown keys are reported and ignored; numbers outside the range are clamped to the range; invalid values fall back to the default (message in the app console).
  - The section `ai` belongs to the companion app; the plugin writes there only the keys for which it has a control (marked with the tab in the table) and leaves the rest unchanged.
- Command line and `--config` file of the companion app (4.4), environment variables (4.5).
- The menu shows only what can be set. All explanation, status and path texts are in the one large info field on the left (since version 15); in addition once in the VaM log: `Settings file: … | Expressions: … | Gestures: … | Audio …`.

### 4.2 config.json

Column "Where": tab in the plugin menu; "file only" = no control. Range in square brackets; the sliders in the plugin have the same limits.

| Key | Type | Default | Values | Effect | Where |
|---|---|---|---|---|---|
| `version` | int | 1 | 1 | schema version; other values: a warning, compatible parts are read | file only |
| `written_by` | string | – | free | who wrote the file last (info only) | is written |
| `connection.active` | bool | true | | link to the companion app on / off | Voice > Companion connection: **Active** |
| `connection.network_active` | bool | true | | version 30: the loopback socket link to the companion app on / off (file channel as an automatic fallback); off = no network code runs in the plugin | Config: **Network Active** |
| `connection.network_port` | int | 38437 | [0–65535] | version 30: UDP port on `127.0.0.1` where the companion app listens; `0` = no listener (files only) | file only |
| `connection.paths.expressions` | string | `Saves/PluginData/AIBody/expressions.json` | relative, under `Saves/` or `Custom/`, without `..` and `:` | file with expression presets (4.6) | file only |
| `connection.paths.gestures` | string | `Saves/PluginData/AIBody/gestures.json` | as above | file with gestures / poses (4.6) | file only |
| `connection.paths.audio` | string | `""` | `""` or relative under `Saves/` / `Custom/` | folder for the speech WAVs. `""` = automatically `Custom/Sounds/AIBody/default`; if VaM cannot load a WAV there, the app switches once to `Saves/PluginData/AIBody/default/audio` and plays again (red line in the status field). A fixed folder = no switch | file only |
| `engines.stt` | string | `null` | `null`, `xai` | speech recognition (`null` = offline, hears nothing) | Voice > Voice and sound: **Speech-to-text** |
| `engines.llm` | string | `echo` | `echo`, `xai`, `ollama` | language model (`echo` = offline, "You said: …"; `ollama` = local, version 29, see [docs/LOCAL_ENGINES.md](docs/LOCAL_ENGINES.md)) | Voice > AI: **Language model** |
| `engines.tts` | string | `tone` | `tone`, `xai`, `elevenlabs` | speech output (`tone` = offline, hum) | Voice > Voice and sound: **Text-to-speech** |
| `mic.enabled` | bool | true | | microphone on | Client Character: **Mic enabled** |
| `mic.mode` | string | `vad` | `vad`, `ptt` (menu: "Voice activation", "Push-to-talk") | voice activation or push-to-talk | Client Character: **Mic mode** |
| `mic.vad_engine` | string | `auto` | `auto`, `energy`, `webrtc`, `silero` | voice detection: `energy` = built-in (learns the basic level, hysteresis, trailing), `webrtc` = webrtcvad (optional, `python -m pip install webrtcvad-wheels`), `silero` = Silero through onnxruntime without torch (version 29, needs the model file `silero_vad.onnx`, see [docs/LOCAL_ENGINES.md](docs/LOCAL_ENGINES.md)), `auto` = silero if the model file is there, else webrtc if installed, else built-in. If the library is missing, the built-in detector keeps running (note in the info field) | Client Character: **VAD engine** (Auto / Built-in / WebRTC / Silero) |
| `mic.vad_strictness` | int | 2 | [0–3] | the higher, the more background noise is ignored (webrtcvad mode 0–3; built-in: speech must be 2 / 2.5 / 3 / 4 times above the basic level) | Client Character: **VAD strictness** |
| `mic.vad_threshold` | number | 0.01 | [0.001–0.5] | quietest level (RMS 0–1) that can count as speech (for all engines) | Client Character: **VAD threshold** |
| `mic.end_silence_ms` | int | 700 | [200–5000] | silence that ends an utterance | Client Character: **Silence timeout (ms)** |
| `mic.min_utterance_ms` | int | 300 | [100–5000], smaller than max | shorter utterances are discarded | Client Character: **Min utterance (ms)** |
| `mic.max_utterance_ms` | int | 20000 | [1000–60000] | longer utterances are cut off | Client Character: **Max utterance (ms)** |
| `mic.echo_tail_s` | number | 0.4 | [0–3] | the microphone stays closed while the character speaks and this long afterwards (echo gate; in realtime mode too until the whole answer is finished) | Client Character: **Echo gate tail (s)** |
| `mic.gain` | number | 1.0 | [0.1–8] | amplification before VAD and speech recognition | Client Character: **Input gain** |
| `mic.ptt_interrupts` | bool | true | | pressing push-to-talk stops the running answer | Client Character: **Push-to-talk interrupts speech** |
| `mic.level_meter` | bool | true | | level meter in the plugin | Client Character: **Show level meter** |
| `body.speech_volume` | number | 1.0 | [0–3] | volume of the head audio source; above 1 (version 44) speech and test tones get louder by that factor (the companion multiplies its WAVs, plain linear gain, no limiter) and **Play test tone** uses a 2x or 3x copy | Voice > Voice and sound: **Speech volume** |
| `body.body_control` | bool | true | | off = speech only: expression, morph, gesture, pose and trigger commands are ignored, the AI gets no body tools; the manual menus keep working | AI Character: **Body control** |
| `body.idle_motion` | bool | true | | idle head motion | AI Character: **Idle head motion** |
| `body.idle_intensity` | number | 0.5 | [0–1] | strength of the idle motion | AI Character: **Idle intensity** |
| `body.breathing` | bool | true | | breathing through a morph | AI Character: **Breathing** |
| `body.breaths_per_minute` | number | 14 | [4–40] | breathing rate | AI Character: **Breaths per minute** |
| `body.breath_depth` | number | 0.35 | [0–1] | breathing depth | AI Character: **Breath depth** |
| `body.breath_morph` | string | `Breath1` | morph name of the figure | chest morph for breathing (no standard morph in VaM, TODO(verify)) | AI Character: **Breath morph** (a morph name from the Morphs tab) |
| `advanced.file_poll_interval_s` | number | 0.1 | [0.02–2] | how often the plugin checks the companion app's inbox (`Saves/PluginData/AIBody/default/inbox/`) for messages (speech, poses, expressions); does not reload config.json (use **Reload Config JSON** for that); a change restarts the connection | Config: **Companion inbox poll interval (s)** (stored name "File poll interval (s)") |
| `advanced.verbose_log` | bool | false | | turn trace in the console and `Saves/PluginData/AIBody/logs/companion.log` (1 MB × 5, keys redacted), `[debug]` lines in the VaM log, *Recent events* in the status field; takes effect at once | Config: **Verbose log**; CLI `-v` |
| `ui.first_run_hint_dismissed` | bool | false | | version 30: set by the plugin once the first-run note was closed or a token exists; the note is never shown again | written by the plugin |
| `ui.background_setup_applied` | number | 0 | | version 36: the `setup.revision` whose background answer the plugin has applied (once per answered setup) | written by the plugin |
| `setup.*` | object | see CONFIG.md | | version 36: the companion's first-start answers (`asked`, `background`, `background_color`, `choice`, `revision`) | written by the companion app |
| `characters.setup_answered` | bool | false | | after version 37: the gate "Do you want to configure your characters?" was answered | AI Character: **Yes**, **No** |
| `characters.setup_wanted` | bool | false | | true = **Yes** (the gender steps are shown); false after answering = skipped until **Configure characters** | AI Character: **Configure characters** |
| `characters.ai_gender` | string | `""` | `""` / `Female` / `Male` | recorded gender/body of the AI character (prompt context only; does not change the Person) | AI Character: **AI gender/body** |
| `characters.user_gender` | string | `""` | `""` / `Female` / `Male` | recorded gender of the user's character (prompt context only) | AI Character: **Your character gender** |
| `poses.commands` | list | the 10 starters | at most 100 entries `{"command", "pose"}` | version 32: the pose commands (AI Character level). Starters: `Sit Down`, `Lay Down`, `Prone`, `Stand Up`, `Spread Your Legs`, `Ankle Your Knees`, `Ankle Your Elbows`, `Turn Around`, `Crawl on all fours`, `Bend Over`, each linked to the pose of the same name. `command` = the text that has to equal the WHOLE input; `pose` = the id of the pose (file name without `Preset_`, or a `gestures.json` pose). A missing key = the starters; `[]` = no pose commands. A command whose pose does not exist is kept but unavailable (never offered or applied) | AI Character: **Add Pose**, **Delete Pose**, **Restore starter poses** |
| `remote.enabled` | bool | false | | version 31: the companion app opens the remote control (web page / HTTP API, optional OSC) at the next start; loopback only, see [docs/REMOTE.md](docs/REMOTE.md) | file only |
| `remote.http_port` | int | 38438 | [1024–65535] | version 31: TCP port of the web page and HTTP API on `127.0.0.1` | file only |
| `remote.osc_port` | int | 0 | [0–65535] | version 31: UDP port of the OSC listener on `127.0.0.1`; `0` = no OSC (OSC has no token) | file only |
| `remote.token` | string | "" | | version 31: secret the HTTP API requires; empty = the app generates one into the file when `remote.enabled` is true; never share the file with it | file only |
| `ai.mode` | string | `qa` | `qa`, `auto`, `realtime`, `chain` | `qa` = simple Q&A: STT → Grok → TTS, with an xAI key `xai` instead of the test engines, speech only, no body tools, no proactive speaking. `auto` = realtime with an xAI key (except with `engines.tts` = `elevenlabs`), else the chain. `realtime` = Grok Voice speech to speech, the chain as fallback (also if no answer comes 12 s after speaking). `chain` = exactly the engines from `engines` | Voice > AI: **AI mode**, **Question and Answer** (sets `qa` and Body control off), **Use realtime voice** (on = `auto`, off = `qa`) |
| `ai.persona` | string | "You are a friendly, curious character …" | free | system prompt (xAI: `instructions` of the first request of a conversation; realtime: part of the instructions) | file only |
| `ai.language` | string | `auto` | `auto` or a language code (`de`, `en`, …) | language hint for STT and TTS | file only |
| `ai.persona_name` | string | `""` | folder name under `Saves/PluginData/AIBody/personas/` or empty | persona (version 27): `persona.json` replaces `ai.persona`, language and voice, see [docs/PERSONAS.md](docs/PERSONAS.md); empty = none | Tab Voice > AI: **Persona** (list from the app) |
| `ai.memory.enabled` | bool | false | | memory (version 27): short notes about the user in `personas/<name>/memory.json`, summarized by xAI after the conversation, used as notes in the instructions | Tab Voice: **Memory**, button **Forget memory** |
| `ai.memory.max_facts` | int | 30 | 1–100 | at most this many notes (at most 160 characters each) | file only |
| `ai.memory.session_idle_minutes` | int | 10 | 1–240 | silence after which a conversation counts as finished and is summarized | file only |
| `ai.memory.min_exchanges` | int | 2 | 1–50 | at least this many questions for a summary to be worthwhile | file only |
| `ai.emotion.fallback` | bool | true | | version 27: expression from the spoken words when the AI chooses none | file only |
| `ai.emotion.fade` | bool | true | | the face blends back to `neutral` after speech | file only |
| `ai.emotion.fade_after_s` | float | 6.0 | 1–120 | wait after the last speech / expression | file only |
| `ai.emotion.fade_seconds` | float | 2.5 | 0.2–10 | blend time when going back | file only |
| `ai.emotion.listening` | bool | true | | small "listening" face while the user speaks (needs the preset in the plugin from version 27) | file only |
| `ai.fallback.stt` / `.llm` / `.tts` | string | `null` / `echo` / `tone` | engines as in `engines` | runs when the chosen engine has no key or a request fails | file only |
| `ai.realtime.url` | string | `wss://api.x.ai/v1/realtime` | | WebSocket address | file only |
| `ai.realtime.model` | string | `grok-voice-latest` | | speech model (query parameter `model`) | file only |
| `ai.realtime.voice` | string | `eve` | a voice of the menu (the 28 built-in xAI voices of docs.x.ai, or the list the companion gets from `GET /v1/tts/voices`) or an own voice id | voice in realtime; a change reconnects | Voice > Voice and sound: **Voice** (also sets `ai.xai.voice`; an own id from the file is taken into the menu) |
| `ai.realtime.sample_rate` | int | 24000 | 8000, 16000, 22050, 24000, 32000, 44100, 48000 | sample rate of the answer (16-bit PCM, as WAV) | file only |
| `ai.realtime.speed` | number | 1.0 | [0.7–1.5] | speaking speed | file only |
| `ai.realtime.reasoning_effort` | string | `none` | `none`, `high` | `none` answers faster; `high` = API default | file only |
| `ai.realtime.send_while_speaking` | bool | false | | the microphone keeps streaming while the character speaks (barge-in by voice); only with headphones | Client Character: **Voice barge-in (headphones)** |
| `ai.realtime.first_segment_s` | number | 1.2 | [0.3–5] | the first audio piece is played as soon as a sentence ends after this much audio | file only |
| `ai.realtime.max_segment_s` | number | 6.0 | [1–20] | longer pieces without a sentence end are cut at the quietest point | file only |
| `ai.realtime.connect_timeout_s` | number | 15 | [3–60] | connection timeout | file only |
| `ai.proactive.enabled` | bool | true | | the AI may speak on its own after silence (realtime or `llm` = `xai`; paused in `qa`) | Voice > AI: **Proactive talking** ("Proactive" until version 22) |
| `ai.proactive.idle_seconds` | number | 90 | [0–3600]; rounded to whole seconds in the plugin; **0 = prompts off** (like Proactive off; anything under 1 s counts as 0) | silence until the AI may speak on its own (not the answer time); doubles with unanswered prompts (up to 8×) | Voice > AI: **Speech delay timer (s)** |
| `ai.proactive.prompt` | string | "The user has been quiet for a while. … answer with exactly [silent] …" | free | note on every prompt; the answer `[silent]` = play nothing | file only |
| `ai.xai.base_url` | string | `https://api.x.ai/v1` | | REST base for STT, LLM, TTS | file only |
| `ai.xai.key_hint` | string | English hint text | any text | note for the reader of the file (JSON has no comments): an xAI API key is needed, in four ways (plugin field **XAI API Token**, `ai.xai.api_key`, `XAI_API_KEY`, `ai.xai.key_file`). Not used by the app; the app adds it to existing `config.json` files | file only |
| `ai.xai.api_key` | string | `""` | any text (no format check) | the xAI token in **plain text**; the plugin writes the field **XAI API Token** here and fills the field from it on start, the app reads it too; applies after the field (live) and before `XAI_API_KEY` and `ai.xai.key_file`; an empty field in the plugin empties it | Voice > Companion connection: **XAI API Token** |
| `ai.xai.api_key_warning` | string | English security notice | any text | note for the reader of the file (JSON has no comments), sits next to `api_key`; the app ignores it, the plugin keeps it when writing back | file only |
| `ai.xai.key_file` | string | `""` | path (absolute or relative to the user folder); not a key | file with the xAI key; applies only after the field **XAI API Token**, `ai.xai.api_key` and `XAI_API_KEY`; a key pasted here is rejected and not stored | file only (no menu field since version 15; the plugin keeps the path it read) |
| `ai.scene_events.enabled` | bool | true | | scene events: if a VaM trigger sets the plugin's text "Scene event", the AI learns of it and may react or stay silent (not in Q&A mode) | file only |
| `ai.scene_events.prompt` | string | "Something just happened in the scene: {event}. … answer with exactly [silent] …" | free, `{event}` is replaced | note to the AI | file only |
| `ai.xai.model` | string | `grok-4.7` | | language model | file only |
| `ai.xai.max_output_tokens` | int | 400 | [16–8000] | keeps answers short | file only |
| `ai.xai.stt_model` | string | `grok-voice-transcribe-2.0` | | speech recognition model | file only |
| `ai.xai.voice` | string | `eve` | as `ai.realtime.voice` | TTS voice | Voice > Voice and sound: **Voice** |
| `ai.xai.speed` | number | 1.0 | [0.7–1.5] | TTS speed | file only |
| `ai.xai.sample_rate` | int | 24000 | 8000, 16000, 22050, 24000, 44100, 48000 | TTS sample rate (PCM, as WAV) | file only |
| `ai.xai.timeout_s` | number | 60 | [5–600] | request timeout | file only |
| `ai.ollama.base_url` | string | `http://127.0.0.1:11434` | | address of Ollama (version 29, local language model without a key) | file only |
| `ai.ollama.model` | string | `llama3.2` | | model name (`ollama pull <model>`) | file only |
| `ai.ollama.max_output_tokens` / `temperature` / `keep_alive` / `max_messages` / `timeout_s` | number / number / string / number / number | 400 / 0.7 / `10m` / 40 / 120 | [16–8000] / [0–2] / – / [2–400] / [5–3600] | length of the answer, randomness, how long the model stays loaded, conversation messages that are sent along, timeout | file only |
| `ai.barge_in.enabled` | bool | false | | voice barge-in without headphones by a loudness rule (version 29, see [docs/LOCAL_ENGINES.md](docs/LOCAL_ENGINES.md)) | file only |
| `ai.barge_in.ratio` / `min_ms` / `floor` | number | 2.0 / 600 / 0.02 | [1.2–10] / [150–3000] / [0.002–0.5] | how much louder than the echo, for how long, from which level | file only |
| `ai.elevenlabs.base_url` | string | `https://api.elevenlabs.io/v1` | | REST base | file only |
| `ai.elevenlabs.key_file` | string | `""` | as `ai.xai.key_file` | file with the ElevenLabs key; `ELEVENLABS_API_KEY` wins | file only (no menu field since version 15; no ElevenLabs field in version 21 either) |
| `ai.elevenlabs.voice_id` | string | `JBFqnCBsd6RMkjVDRZzb` | | voice | file only |
| `ai.elevenlabs.model_id` | string | `eleven_multilingual_v2` | | TTS model | file only |
| `ai.elevenlabs.output_format` | string | `pcm_24000` | `pcm_16000`, `pcm_22050`, `pcm_24000`, `pcm_44100`, `pcm_48000` | output format (44.1 / 48 kHz need an ElevenLabs Pro plan) | file only |
| `ai.elevenlabs.timeout_s` | number | 60 | [5–600] | request timeout | file only |

Removed in version 30 (one character per app): `connection.channel`, `ai.channels` and the plugin's Channel field. Old files and scenes that still hold them are read without an error and the values are ignored.

### 4.3 Menu layout and controls without a config.json key

Layout since version 15 (Leon, 17.11.2026): one large info field on the left, four tabs on the right; the tabs hold only controls, no text fields. Since version 16 the info field shows only the information of the open tab; since version 17 it is 1800 high and stands alone in the left column (no header line any more).

- Info field on the left (always visible), from the top:
  - First line: **AIBody <version>**, atom, startup result ("Startup: ok" or, in red, the number of errors; details in the tab Config).
  - *Info: <tab>*: help and status for the open tab. Voice: AI mode help, key status per provider (configured / missing / rejected, with the hint "You need an xAI API key: create one at console.x.ai …"), engine status (active mode, ready / not configured, fallback; only after the app's first heartbeat). AI Character: the character wizard (gate, skip note, or what the gender and clothing steps record), number of poses and pose files, hints on Body control and the breath morph. Client Character: push-to-talk explanation (the microphone is always the system's default input device), a red hint line if the companion app is not running or the link is off, microphone status, level. Voice additionally *Connection* (link, companion, audio, "Last turn", "Latency to first sound: X s (avg Y s, n turns)"), AI Character additionally *Body* (speaking, audio, expression, breath morph). Config: path of `config.json`, the network status (`Network: off` / `connecting ...` / `connected` / `unavailable, using files`), result of **Reload Config JSON**, then:
  - *Self-test* (Person, head audio, morphs, pose memory, poses, breath morph, expression morphs, Timeline, PluginData, companion; the body checks also appear as "Plugin self-test: …" in the companion app's console and `companion.log`).
  - *Recent events* (with Verbose log), Startup log.
- First-run note (version 30): at the very top of the plugin UI, until an xAI token exists or the note is closed: the header **First start: XAI API Token**, ONE text field and ONE button (**Close** while the field is empty, **OK** once something is typed; OK saves the token exactly like the token field in the tab Voice and closes the note). The field is masked like the token field. Never shown again afterwards (`ui.first_run_hint_dismissed`).
- UI rules (Leon, 20.11.2026, standing): every tab is ordered by topic; the right column holds only bold category headers and controls (plus the label above each input field); all explanations and all status are in the left info field, written as running prose with every control name in **bold** (Unity rich text `<b>`, e.g. "**Breaths per minute** controls how fast the chest breathes"). Stored names and config keys stay unchanged.
- Tab **Voice**:
  - *Companion connection*: **Active**, **API Reconnect** (the app re-reads keys and reopens realtime; the plugin restarts the connection), **XAI API Token** (label above the field; free-text field, plain text, no format check; saved in `config.json`; shown masked once it loses focus: first and last 4 characters with stars between them, full text while focused; sent to the app only in the `config` event, never written to the log; how to change or remove it is explained in the left field).
  - *AI*: **Use realtime voice** (toggle, not stored, a view of AI mode: on = `auto`, off = `qa`), **AI mode**, **Language model**, **Persona**, **Memory**, **Forget memory**, **Proactive talking**, **Speech delay timer (s)** (how long the silence must last before the AI may say something on its own; 0 = off; not the answer time). Version 39: no **Question and Answer** button any more; with **Proactive talking** off the character only answers when asked, and Body control is left as set.
  - *Voice and sound*: **Voice**, **Speech-to-text**, **Text-to-speech**, **Test tone via companion**, **Speech volume** (moved here from the tab AI Character on 20.11.2026), **Play test tone** (a tone from the package, without the app), **Stop speaking**.
- Tab **AI Character**: *Characters* (after version 37, optional): **Yes** / **No** answer "Do you want to configure your characters?"; after No only **Configure characters**; after Yes: **AI gender/body**, **Your character gender** (Female / Male, recorded for the AI, the Person in VaM is not changed), **Clothing** (no list: use VaM's Clothing tab). Then *Body control*: **Body control** (default on); *Idle poses*: **Idle poses**, **Idle default pose**, **Idle pose min wait (s)**, **Idle pose max wait (s)**; *Idle motion and breathing*: **Idle head motion**, **Idle intensity**, **Breathing**, **Breaths per minute**, **Breath depth**, **Breath morph** (a morph name from the Morphs tab) (labeled text field, a morph name from the character's Morphs tab; storable "Breath morph", key `body.breath_morph`); *Expression and gesture*: **Expression** + **Show expression**, **Reset expression**, **Reload expressions (expressions.json)**, **Gesture** + **Play gesture**; *Poses* (version 42): **Pose command** (choosing an entry applies its pose at once), **Add Pose** (VaM's file browser for the pose file, then **New pose command** with **Save pose command** / **Cancel Add Pose**; saved in `config.json`), **Delete Pose** (the chosen command), **Reset poses** (AI, then Client, back to the scene placement), **Restore starter poses**, **Reload poses**. Poses the commands can link to: `gestures.json` entries with `kind` `pose` plus `.vap` / `.json` files in `Custom/Atom/Person/Pose` and `Custom/Atom/Person/Pose/AIBody` (top level, at most 200, prefix `Preset_` removed), or any pose file chosen with Add Pose.
- Tab **Client Character**: *Microphone*: **Mic enabled**, **Mic mode**, **Input gain**, **Show level meter**; *Push-to-talk*: **Push-to-talk active** (not stored; while on, the app listens; only in Mic mode push-to-talk), **Push-to-talk interrupts speech**; *Voice detection*: **VAD engine**, **VAD threshold**, **VAD strictness**, **Silence timeout (ms)**, **Min utterance (ms)**, **Max utterance (ms)**; *Echo and barge-in*: **Echo gate tail (s)**, **Voice barge-in (headphones)**.
- Tab **Config**: *Config file*: **Reload Config JSON**; *Connection*: **Network Active** (on by default: loopback link to the companion app with an automatic file fallback; saved with the scene and mirrored in config.json), **Companion inbox poll interval (s)** (how often the plugin fetches the companion app's messages); *Logging*: **Verbose log**; *Background*: **Set background color**, **Background color** (color picker), the caption "for pass-through transparency".
- Removed in version 15: tabs *AI*, *Post*, *Advanced*; the field **Channel** (`default`), the fields **xAI key file** / **ElevenLabs key file**, the placeholder **Delay (s)**, the title line per tab, all small text / status fields in the tabs. Purpose and whereabouts: [`docs/BACKLOG.md`](docs/BACKLOG.md), section "Removed menu entries (version 15)". Key file paths: in `config.json` (4.2) or through the environment variable. (Version 28's Channel field was removed again in version 30.)
- Actions for triggers (plugin storables): `Reconnect`, `Stop speaking`, `Reset expression`, `Reload config files` (reload expressions and gestures), `Push-to-talk start`, `Push-to-talk stop`, `Push-to-talk toggle`.

### 4.4 Companion app: command line and --config file

- `--vam-root <path>` (required): the VaM main folder.
- `--channel <name>`: no longer used; accepted and ignored with a warning (the app always serves the one character in `Saves/PluginData/AIBody/default/`).
- `--config <file>`: the app's own JSON file (template `companion/config.example.json`), keys: `vam_root`, `poll_interval_s` (0.02, tick of the main loop), `sample_rate` (16000, microphone), `frame_ms` (30, VAD block length), `mic` (start values like `mic.*`), `keep_audio_files` (20, this many WAVs stay around), `stt` / `llm` / `tts`. Microphone, engines, `ai` and `verbose_log` from `config.json` override this file.
- `--setup` / `--no-setup` (version 35, questions of version 36): ask the first-start questions again (background color, then Scene / Plugin) / never ask them. Without either, the app asks once in an interactive console. The character configuration wizard (after version 37) is not asked here; it lives in the plugin, tab AI Character > Characters.
- `--no-mic`: never open the microphone (text input only).
- `--no-stdin`: no text input from the console.
- `--list-devices`: print input devices and exit (diagnosis only; the app always records from the default input device, another microphone is set as the default in Windows).
- Microphone diagnosis without VaM and without the app: `python tools/mic_test.py` in the repo folder (raw devices, per host API, default device; writes `mic_test_output.txt`). Output only, there is no microphone selection.
- `-v` / `--verbose`: DEBUG for all modules, turn trace always on.

### 4.5 Environment variables

- xAI key, order (since version 24): 1. the field **XAI API Token** in the plugin (live, if not empty), 2. `ai.xai.api_key` in `config.json` (plain text; the same as the field after a restart), 3. the environment variable `XAI_API_KEY`, 4. the key file `ai.xai.key_file`. An empty field falls back; if you empty the field in the plugin, `ai.xai.api_key` is emptied too. The token never appears in the log (all keys are redacted).
- `XAI_API_KEY`: optional; an xAI API key from console.x.ai (starts with `xai-`); wins over `ai.xai.key_file`, loses against the field. A Grok subscription (SuperGrok / X Premium) or a grok.com token is not an API key and is rejected. Without a key: a warning on start, the test engines run.
- `ELEVENLABS_API_KEY`: ElevenLabs key; wins over `ai.elevenlabs.key_file`.
- Key files are re-read every 10 s; environment variables only when the app starts. The token from the field travels through one event file under `Saves/PluginData/AIBody/default/outbox/` (never over the loopback socket) which the app deletes right after reading, and it is stored in plain text in `config.json` (`ai.xai.api_key`); in the log it is always redacted.

### 4.6 expressions.json and gestures.json

- `expressions.json` (path `connection.paths.expressions`): object name → {morph display name: value}. Adds to / overrides the built-in presets `neutral`, `happy`, `smile`, `sad`, `angry`, `surprised`, `thinking` (morph names TODO(verify)). Entries that are not an object (e.g. `_comment`) are skipped. Template `examples/expressions.json`.
- `gestures.json` (path `connection.paths.gestures`): object name → definition with `kind`:
  - `head`: `name` (`nod`, `shake`, `tilt`), optional `duration` (default 1.2 s), `amplitude` (1).
  - `pose`: `path` of a pose file (loaded through PosePresets, TODO(verify)); appears in the pose chooser and can be the target of a pose command (name it like a command, e.g. `"Sit Down"`, to make that starter available). It is no gesture and there is no AI tool `pose` (version 32).
  - `timeline`: `storable` (default `VamTimeline.AtomPlugin`), `animation`.
  - `trigger`: `storable` and `action`, or `param` + `value` (+ `value_type` `float` / `bool` / `string` / `chooser`).
  - Template `examples/gestures.json`.

## 5. Notes for users (Hub)

- AIBody is a plugin for Virt-A-Mate 1.22 with a separate Python companion app. It gives a character a voice and body control by an AI.
- The VaM plugin has no internet code. By default it also talks to the companion app through one loopback socket on `127.0.0.1` (toggle **Network Active**); that needs VaM's global setting "Allow Plugins Network Access" (*User Preferences > Security*), which VaM and its per-plugin prompt control, not AIBody. If the setting is off or the app is not running, the plugin falls back to local files automatically; with **Network Active** off it exchanges only local files.
- The companion app connects to external services: xAI (api.x.ai) and optionally ElevenLabs. Microphone recordings or typed text and the answers are transmitted to these services. Their terms of use and privacy policies apply.
- You need your own, paid API key from console.x.ai. A Grok subscription (SuperGrok / X Premium) or a grok.com login does not work. The API costs are carried by the user.
- API keys stay local (field in the plugin, `config.json`, environment variable or key file), never in the `.var` or the repository, and are redacted in the log. The token from the plugin field is stored in plain text in `config.json` and shown masked in the plugin: do not share `config.json`; scenes saved with versions 21 to 23 contain the token in plain text and must not be shared either.
- Without a key only an offline test mode runs (echo and hum).
- AI-generated speech and AI-controlled behavior can be wrong, inappropriate or unexpected. The AI is not a person and has no consciousness.
- Experimental: loads in VaM 1.22 (version 14), functions not yet fully checked there; the companion app has so far only been tested against rebuilt servers, not with a real key.
- Not an official product of, and not affiliated with, xAI, ElevenLabs or Meshed VR.

## 6. Credits and special thanks (sources)

The complete list of every plugin, author, library, service and document the project draws on, with links, is in **[docs/CREDITS.md](docs/CREDITS.md)** (Credits / Special thanks). The short version:

- MacGruber (main source): the model for structure, operation and liveliness of a character – [LogicBricks](https://hub.virtamate.com/resources/logicbricks.1975/), [Life](https://hub.virtamate.com/resources/life.165/), [Benchmark](https://hub.virtamate.com/resources/benchmark.11336/), [Utils](https://hub.virtamate.com/resources/macgruber-utils.40744/). Life can run on the same character and be driven through `gestures.json` (type `trigger`).
- Acid Bubbles: [Timeline](https://github.com/acidbubbles/vam-timeline) (gestures through `Play <animation>`), [Glance](https://github.com/acidbubbles/vam-glance), [Embody](https://github.com/acidbubbles/vam-embody), [Scripter](https://github.com/acidbubbles/vam-scripter), [Keybindings](https://github.com/acidbubbles/vam-keybindings), [Collider Editor](https://github.com/acidbubbles/vam-collider-editor), [Improved PoV](https://github.com/acidbubbles/vam-improved-pov): evidence for storables, file access, menu layout and the scene format.
- VamDeluxe: [DeluxePlugin](https://github.com/vamdeluxe/DeluxePlugin) (Dollmaster, Qualia, HeadIdle, PresetRandomizer): head audio, breathing, head idle, presets, personas as data.
- Sally: *Camera Background Color* (VaM Hub): used in the bundled scene until version 35; its approach (camera clear color, skybox off) guided AIBody's own background color (no code copied).
- lfe999: [VamAutoPupil](https://github.com/lfe999/VamAutoPupil) (camera API evidence); Acid Bubbles: vam-timeline (clip readiness evidence).
- ZengineerVAM: [VAMLaunch](https://github.com/ZengineerVAM/VAMLaunch) and yuyaslabo: [VaM_ML_Skeleton_Engine](https://github.com/yuyaslabo/VaM_ML_Skeleton_Engine): evidence for a UDP socket in a VaM plugin (see `docs/API_AUDIT.md`, "Version 30").
- More evidence for the interfaces used: everlaster (TittyMagic), lfe999 (VamFreeMMD, VamHeightPlugin), Yoooi (ToySerialController), emptyngton (FootstepsExtended); scene format: OnePunchVAM (vam-story-builder), foto2vam; official documentation and patch notes of Meshed VR.
- Every VaM interface used is evidenced with a source and a fixed commit in [`docs/API_AUDIT.md`](docs/API_AUDIT.md).

## License

[LGPL-2.1](LICENSE).
