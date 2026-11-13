# AIBody: a virtual body for an AI in Virt-A-Mate

AIBody gives an AI a body in [Virt-A-Mate](https://www.virtamate.com/) (VaM). The body hears the
user through the microphone, speaks with lip sync, shows facial expressions, makes gestures and
poses, and keeps moving (idle motion and breathing) while it waits.

The project has four parts. **All of them are needed together** (Person2 only if a second
character should be voiced):

- **AIBody Session plugin** (`src/Session/`, package `d0n.AIBodySession`): the *connection*.
  Loaded once in VaM's **Session Plugins**, so it survives scene changes. It talks to the
  companion through a shared folder, holds the microphone and engine menus and shows the
  connection status. It forwards body commands strictly by character slot.
- **AIBody Person plugin** (`src/Person/`, package `d0n.AIBodyPerson`, slot **person1**): the
  *body of character 1*. Loaded on character 1's Person atom (**Plugins** tab). It plays speech
  audio with lip sync, drives morphs, expressions, gestures and poses, and reports when it starts
  and stops speaking. Its settings (volume, idle, breathing, ...) are saved with the Person.
- **AIBody Person 2 plugin** (package `d0n.AIBodyPerson2`, slot **person2**): the *body of
  character 2*. Same features, but a distinct script (own class, own params `AIBody2 ...`, own
  folder `Custom/Scripts/d0n/AIBody2/`), generated from the Person sources by
  `tools/make_person2.py`. The two characters can never be confused: every command names its
  slot and only that slot's plugin may act on it.
- **Companion app** (`companion/`, Python): the *brain*. It runs next to VaM and does everything
  the VaM plugin sandbox does not allow: microphone capture, voice activity detection, speech to
  text, the language model and text to speech.

Status: **early (v0.4.0)**. All three plugins compile as C# 6 against API stubs but have not been
run inside VaM yet; every unverified VaM/Unity call is marked `TODO(verify)` in the code. The
companion runs end to end with mock engines (no real STT, LLM or TTS yet). See
[Roadmap](#roadmap).

## Architecture

```mermaid
flowchart LR
    user((User))
    subgraph companion["Companion app (Python)"]
        mic[Mic capture and gain] --> gate{Echo gate}
        gate -->|open| vad[VAD or push-to-talk]
        vad --> stt[Speech to text]
        stt --> llm[Language model]
        llm --> tts[Text to speech]
        filet[File transport]
    end
    folder[("Saves/PluginData/AIBody/channel: inbox, outbox, audio")]
    subgraph vam["Virt-A-Mate 1.22"]
        subgraph session["AIBody Session plugin (Session Plugins)"]
            sfile[File transport] --> route[Router]
            micmenu[Mic and engine menus]
            registry[Person registry: scans atoms]
        end
        subgraph person["AIBody Person: slot person1, character 1"]
            inbox[AIBody Inbox / Outbox params] --> router[Command router]
            router --> speech[Speech queue]
            router --> expr[Expressions and morphs]
            router --> pose[Gestures, poses, triggers]
            idle[Idle and breathing]
        end
        subgraph person2["AIBody Person 2: slot person2, character 2"]
            inbox2[AIBody2 Inbox / Outbox params] --> router2[Same features as Person]
        end
        other["Other plugins: Timeline, Life, Glance, ..."]
    end
    user -- voice --> mic
    llm -- commands --> filet
    tts -- WAV --> folder
    filet <-->|JSON files| folder
    folder <-->|FileManagerSecure| sfile
    route <-->|"slot person1"| inbox
    route <-->|"slot person2"| inbox2
    registry -.-> inbox
    registry -.-> inbox2
    micmenu -- "config, ptt" --> sfile
    folder -- "URLAudioClipManager" --> speech
    speech -- "HeadAudioSource and lip sync" --> user
    filet -- "speech_started / speech_ended" --> gate
    pose -. trigger .-> other
```

Flow of one turn:

1. The companion records the user (voice activation or push-to-talk), detects the end of the
   utterance (silence timeout) and transcribes it.
2. The language model answers with text plus an optional expression and gesture.
3. The companion writes a WAV into `Saves/PluginData/AIBody/<channel>/audio/` and drops
   `expression`, `gesture` and `speak` commands into the channel's `inbox/`, each addressed to a
   character slot (`slot`: `person1` or `person2`).
4. The Session plugin picks them up and hands them to that slot's Person plugin only.
5. The Person plugin loads the clip with VaM's `URLAudioClipManager`, queues it and plays it
   through the Person's head audio source. VaM's built-in lip sync moves the mouth.
6. The Person plugin reports `speech_started` and `speech_ended` from actual playback; the
   Session plugin forwards them. The companion keeps the microphone closed in between (plus a
   short tail) so the AI does not hear and answer itself.

This is the same split that [Voxta](https://doc.voxta.ai/docs/integrations/vam) and
[VoiceControl2](https://github.com/StyleMavin/VoiceControl2) +
[VoskCompanion](https://github.com/StyleMavin/VoskCompanion) use: a thin client inside VaM and the
heavy work in a separate program.

### How the plugins talk, and how the characters stay apart

VaM compiles each plugin separately, so the plugins cannot call each other's C# code. They use
only VaM's public scene API (no files, no network):

- Each Person plugin registers string params named after its **slot**: `AIBody Inbox`,
  `AIBody Outbox`, `AIBody Person Version` (Person, slot `person1`) or `AIBody2 Inbox`,
  `AIBody2 Outbox`, `AIBody2 Person Version` (Person 2, slot `person2`).
- Once per second the Session plugin scans the scene's atoms for these params. New or removed
  characters and scene changes are picked up automatically.
- Commands: the Session plugin writes one command JSON (with `slot`) into the slot's Inbox; the
  Person plugin checks the slot, handles it right away and clears the value.
- Events: the Person plugin appends to a JSON array in its Outbox; the Session plugin drains it
  every frame and forwards the events with `slot` and atom name.
- Routing is strict: `slot` if given, else the plugin on `atom`, else the Session plugin's
  **Default slot**. If that slot is missing or ambiguous (its plugin on two atoms, or one atom with
  both plugins) the companion gets an `error` (`no_person`, `slot_conflict`, `slot_mismatch`,
  `unknown_slot`) and **nothing is redirected to the other character**. Each Person plugin also
  refuses commands for another slot (`wrong_slot`).

Details: [protocol/PROTOCOL.md](protocol/PROTOCOL.md#routing-by-character-slot-session-plugin---person-plugins).

## Repository layout

```
src/                       VaM plugins (C# 6)
  AIBodySession.cslist       Session plugin entry (Session Plugins)
  AIBodyPerson.cslist        Person plugin entry (character 1 > Plugins, slot person1)
  Shared/                    Log.cs, Protocol.cs (message types, bridge param names); in both packages
  Session/
    AIBodySession.cs           MVRScript: transport, channel, engine menus, status, routing
    PersonRegistry.cs          finds Person plugins by slot, conflicts, inbox/outbox bridge
    FileTransport.cs           JSON files in Saves/PluginData via FileManagerSecure
    ITransport.cs              transport interface
    MicConfig.cs               microphone menu, device list, push-to-talk, level meter
  Person/                    (also the source of Person 2, see tools/make_person2.py)
    PersonIdentity.cs          slot / title of this build (person1; rewritten to person2 for Person 2)
    AIBodyPerson.cs            MVRScript: per-character settings, inbox/outbox, slot check, status
    CommandRouter.cs           dispatches body commands, ack / error events
    SpeechPlayer.cs            speech queue: file path via URLAudioClipManager, playback, events
    MorphHelper.cs             morph lookup and smooth blending layer
    ExpressionController.cs    expression presets (built-in + expressions.json)
    PoseController.cs          poses, gestures.json, Timeline and generic triggers
    IdleController.cs          idle head sway and head gestures (nod, shake, tilt)
    BreathingController.cs     procedural breathing on a chest morph
  Optional/                  HTTP transport (UnityWebRequest), NOT in any .cslist or package
protocol/                  PROTOCOL.md and JSON schemas
companion/                 Python companion app (stdlib only for the core)
  aibody_companion/
    transport/               file transport (default), optional HTTP server, auto
    audio/                   capture + device control, mic settings, input processor, VAD, echo gate
    pipeline/                STT, LLM, TTS interfaces and mock engines
    orchestrator.py          ties it all together (tick loop, slot routing, heartbeat)
  tests/                     unit and end-to-end tests (python -m unittest)
examples/                  example commands and events, expressions.json, gestures.json
packaging/                 meta.json (shared) + AIBodySession/AIBodyPerson/AIBodyPerson2.json overrides
tools/                     build_var.py (packages), make_person2.py (Person 2 variant),
                           check_plugin.sh/.py + stubs (sandbox, identity and compile check)
```

## Setup

### Requirements

- Virt-A-Mate **1.22** (VaM 1.x). VaM 2 does not support plugins yet.
- Windows PC that runs VaM, Python 3.10+ for the companion, a microphone.
- No "Allow Plugins Network Access" needed: the default build uses no network code.

### Install the packages

Download from the [releases](https://github.com/d0n/vam_plugin/releases), or build them:

```
python tools/build_var.py    # dist/d0n.AIBodySession.2.var, d0n.AIBodyPerson.2.var, d0n.AIBodyPerson2.1.var
```

Copy them into VaM's `AddonPackages` folder:

```
<VaM>/AddonPackages/d0n.AIBodySession.2.var     always
<VaM>/AddonPackages/d0n.AIBodyPerson.2.var      character 1
<VaM>/AddonPackages/d0n.AIBodyPerson2.1.var     character 2 (only if a second character speaks)
```

Remove older versions of the same packages (e.g. `d0n.AIBodySession.1.var`, `d0n.AIBodyPerson.1.var`).

Contents of the packages:

```
d0n.AIBodySession.2.var
├── meta.json
└── Custom/Scripts/d0n/AIBody/
    ├── AIBodySession.cslist
    ├── Shared/Log.cs, Shared/Protocol.cs
    └── Session/ITransport.cs, FileTransport.cs, PersonRegistry.cs, MicConfig.cs, AIBodySession.cs

d0n.AIBodyPerson.2.var                      (slot person1, character 1)
├── meta.json
└── Custom/Scripts/d0n/AIBody/
    ├── AIBodyPerson.cslist
    ├── Shared/Log.cs, Shared/Protocol.cs
    └── Person/PersonIdentity.cs, MorphHelper.cs, SpeechPlayer.cs, ExpressionController.cs,
               BreathingController.cs, IdleController.cs, PoseController.cs, CommandRouter.cs,
               AIBodyPerson.cs

d0n.AIBodyPerson2.1.var                     (slot person2, character 2)
├── meta.json
└── Custom/Scripts/d0n/AIBody2/
    ├── AIBodyPerson2.cslist
    ├── Shared/Log.cs, Shared/Protocol.cs
    └── Person/PersonIdentity.cs, MorphHelper.cs, SpeechPlayer.cs, ExpressionController.cs,
               BreathingController.cs, IdleController.cs, PoseController.cs, CommandRouter.cs,
               AIBodyPerson2.cs
```

Then in VaM (if VaM asks whether to enable plugins from these packages, allow it):

1. **Session plugin, once:** Main UI > **Session Plugins** > **Add Plugin** > choose
   `AddonPackages > d0n.AIBodySession.2:/Custom/Scripts/d0n/AIBody/AIBodySession.cslist`.
   Optional: **Set Current As User Defaults** in the session plugin presets, so it loads with
   every VaM start. It stays loaded across scene changes.
2. **Character 1:** select character 1's Person atom > **Plugins** tab > **Add Plugin** > choose
   `AddonPackages > d0n.AIBodyPerson.2:/Custom/Scripts/d0n/AIBody/AIBodyPerson.cslist` (slot
   person1).
3. **Character 2:** select character 2's Person atom > **Plugins** tab > **Add Plugin** > choose
   `AddonPackages > d0n.AIBodyPerson2.1:/Custom/Scripts/d0n/AIBody2/AIBodyPerson2.cslist` (slot
   person2). Never put both Person plugins on the same atom, and each only once per scene; the
   Session plugin refuses an ambiguous slot (status "CONFLICT").
4. Save the scene to keep the plugins and their settings with the characters.
5. Keep each Person's **Auto Behaviors > Lip Sync** enabled. It animates the mouth from the audio.
6. Pick the character the AI speaks through: the Session plugin's **Default slot**, or the
   companion's `default_slot` / `--slot`, or `@person2 ...` for a single typed line.
7. Optional: copy `examples/expressions.json` and `examples/gestures.json` to
   `<VaM>/Saves/PluginData/AIBody/` and adjust them (shared by both characters), then press
   **Reload expressions / gestures** in the Person plugins.

Loose files instead of packages (handy while developing): copy `src/AIBodySession.cslist`,
`src/AIBodyPerson.cslist`, `src/Shared/`, `src/Session/` and `src/Person/` to
`<VaM>/Custom/Scripts/d0n/AIBody/` (do not copy `src/Optional/`), and generate Person 2 into its
own folder with `python tools/make_person2.py --out "<VaM>/Custom/Scripts/d0n/AIBody2"` (or unzip
`Custom/Scripts/d0n/AIBody2/` from the Person2 .var). Then pick
`Custom/Scripts/d0n/AIBody/AIBodySession.cslist` (Session Plugins),
`Custom/Scripts/d0n/AIBody/AIBodyPerson.cslist` (character 1) and
`Custom/Scripts/d0n/AIBody2/AIBodyPerson2.cslist` (character 2). Use either the packages or the
loose files, not both.

### Session plugin settings

- **Active**, **Transport** (only "File (shared folder)" in the default build), **Channel**
  (default `default`; must match the companion's `channel`), **File poll interval**.
- **Default slot** (`person1` / `person2`): character for commands that name neither `slot` nor
  `atom`. **Rescan characters** forces a scan.
- **Speech-to-text**, **Language model**, **Text-to-speech**: engine menus, filled from the
  companion's list of available engines and sent with the settings.
- Status box: companion connection, and per slot the atom, "missing" or "CONFLICT". **Reconnect**,
  **Stop all speech** (both characters).

### Microphone menu (Session plugin)

The microphone is captured by the companion, but configured in the Session plugin. Settings are
applied by the companion live (0.3 s after the last change) and are kept in the session plugin
preset:

- **Mic enabled**, **Mic mode** (Voice activation / Push-to-talk), **Mic device** (list reported
  by the companion; **Refresh mic devices** asks again)
- **VAD threshold** (RMS level that counts as speech), **Input gain**, **Silence timeout**,
  **Min / Max utterance**, **Echo gate tail**
- **Push-to-talk active** toggle, plus the actions *Push-to-talk start / stop / toggle* for
  scene triggers or key bindings, and **Push-to-talk interrupts speech**
- **Show level meter**: a text meter (`[|||||....!.....] -32 dB`, `!` marks the threshold), the
  current mic state and whether the companion accepted the settings

### Person plugin settings (Person and Person 2)

The header and status show the slot (`person1` / character 1 or `person2` / character 2).
**Speech volume**, **Idle head motion** and **Idle intensity**, **Breathing**, **Breaths per
minute**, **Breath depth**, **Breath morph**, **Verbose log**. Actions: **Stop speaking**,
**Reset expression**, **Reload config files** (button: *Reload expressions / gestures*). The status box shows whether the Session plugin
is draining its events, the speech queue and missing morphs or audio source. Gaze is not part of
AIBody yet; use [Glance](https://hub.virtamate.com/resources/glance-realistic-head-driven-eye-motion.5461/)
on the same atom.

### Run the companion

```
cd companion
pip install sounddevice                                   # microphone support
python -m aibody_companion --list-devices                 # check the microphone
python -m aibody_companion --vam-root "C:/VaM"            # file transport, channel "default"
```

Options: `--channel` (default `default`), `--slot person1|person2` (character the AI speaks
through; default: the Session plugin's Default slot), `--no-mic`
(text only), `--no-stdin`, `--config config.json` (see `config.example.json`, including initial
`mic` settings). `--transport http|auto` only works with the optional HTTP build (below).
Typed lines on stdin make the body speak (`@person2 Hallo` addresses character 2), which is handy
for testing without a microphone. With
the mock engines the character answers "You said: ..." with a humming tone, enough to test lip
sync, expressions, gestures, queueing and echo gating. Put API keys for real engines in
environment variables, never in the repository.

Tests and checks:

```
cd companion && python -m unittest discover -s tests -t .
tools/check_plugin.sh      # needs the .NET SDK: sandbox scan, identity check, compiles all three .cslist (C# 6)
```

## Plugin sandbox limits

VaM compiles plugins itself (C# 6, Mono, .NET 3.5 profile) and runs them in a sandbox. A plugin
that uses a blocked API does not load at all, so the default build avoids all of them and
`tools/check_plugin.sh` enforces it (it scans both `.cslist` file sets and compiles them without
any networking stubs):

- **No `System.IO`.** File access goes through `MVR.FileManagementSecure.FileManagerSecure`.
  Writing is limited to `Saves/PluginData`. There is no reliable rename, so the Session plugin
  writes event files in place and the companion tolerates partial files.
- **No native DLLs, no `System.Diagnostics.Process`, no reflection.** The plugins cannot start
  the companion or load speech engines. That is why the brain is a separate app.
- **No `UnityEngine.Networking` / `UnityWebRequest`** in the default build. The companion link is
  the shared folder; speech audio is loaded from a local file path with VaM's own
  `URLAudioClipManager` (`TODO(verify)` on 1.22).
- **C# 6 only.** No tuples, `out var`, pattern matching or other C# 7+ features.
- **Microphone inside VaM is unverified**, so capture and device listing live in the companion.

### Optional HTTP build (not in the packages)

`src/Optional/HttpTransport.cs` and `AutoTransport.cs` (HTTP long-poll with file fallback, needs
"Allow Plugins Network Access") are wrapped in `#if AIBODY_HTTP` and listed in no `.cslist`. To
try them with loose files: add `#define AIBODY_HTTP` as the first line of
`Session/AIBodySession.cs` and `Person/SpeechPlayer.cs`, add `Optional/HttpTransport.cs` and
`Optional/AutoTransport.cs` to `AIBodySession.cslist`, copy `Optional/` too, and run the
companion with `--transport auto`. This may not load on sandboxed VaM 1.22 installs.

## Protocol summary

Full spec: [protocol/PROTOCOL.md](protocol/PROTOCOL.md). Every message is a JSON object with
`v`, `type`, `id` and `ts`; body commands carry `slot` (and optionally `atom`).

Companion to VaM: body commands `speak`, `stop_speaking`, `expression`, `set_morphs`,
`reset_morphs`, `gesture`, `pose`, `trigger`, `idle`, `breathing` (forwarded to a Person
plugin by slot); `ping`, `companion_heartbeat`, and for the microphone menu `config_ack`, `devices`,
`mic_state`, `mic_level` (Session plugin).

VaM to companion: from the Session plugin `ready`, `heartbeat`, `pong`, `persons`, `config`,
`ptt`, `list_devices`, `shutdown`, `error`; from Person plugins (with `slot`, `atom`) `person_status`,
`speech_started`, `speech_ended`, `gesture_done`, `ack`, `error`.

Example:

```json
{ "v": 1, "type": "speak", "id": "utt-0001", "slot": "person2",
  "audio": "Saves/PluginData/AIBody/default/audio/utt-0001.wav",
  "text": "Hello, nice to meet you!", "expression": "happy", "queue": "append" }
```

## Reusing other plugins

AIBody keeps its own motion simple and is meant to work alongside established plugins on the same
atom. The `trigger` command and `gestures.json` (`kind: timeline` or `trigger`) can call actions and
set parameters on any of them.

| Plugin | Use for | Link |
|--------|---------|------|
| Timeline (Acid Bubbles) | keyframe animations for gestures and idle loops; "Play &lt;name&gt;" actions | [Hub](https://hub.virtamate.com/resources/timeline.94/), [wiki](https://hub.virtamate.com/resources/timeline-3-wiki.860/), [GitHub](https://github.com/acidbubbles/vam-timeline) |
| Life (MacGruber) | realistic breathing with chest movement and sounds, Gaze head motion | [Hub](https://hub.virtamate.com/resources/life.165/) |
| Glance (Acid Bubbles) | natural eye movement driven by head motion | [Hub](https://hub.virtamate.com/resources/glance-realistic-head-driven-eye-motion.5461/), [GitHub](https://github.com/acidbubbles/vam-glance) |
| E-Motion (VRAdultFun) | expressions and idle reactions from personality presets | VaMHub, search "E-Motion" |
| Naturalis (everlaster) | breast and glute physics | VaMHub, search "Naturalis" |
| Voxta (Acid Bubbles) | reference for the thin-client design, state triggers, echo handling | [docs](https://doc.voxta.ai/docs/integrations/vam) |
| VoiceControl2 + VoskCompanion | reference for a plugin talking to an external speech app | [plugin](https://github.com/StyleMavin/VoiceControl2), [companion](https://github.com/StyleMavin/VoskCompanion) |
| SpeechRecognition | in-VaM Windows speech recognition (legacy, breaks with Windows updates) | VaMHub |
| Embody, Dev Tools (Acid Bubbles) | code to study for VaM plugin patterns | [Embody](https://github.com/acidbubbles/vam-embody), [Dev Tools](https://github.com/acidbubbles/vam-devtools) |

Poses from VaMHub can be loaded with the `pose` command using the usual package path, for example
`Author.Package.1:/Custom/Atom/Person/Pose/name.vap`.

## Roadmap

1. **Test inside VaM 1.22** and fix every `TODO(verify)` in `src/`: that both packages load in
   the sandbox, the Session/Person bridge (atom scan, `plugin#` storable ids, param callbacks),
   Person and Person 2 loaded at the same time,
   `URLAudioClipManager` path loading and `PlayNow` playback (lip sync), pose preset loading,
   Timeline action names, editable text fields, chooser updates, morph names.
2. **Real engines** in the companion: STT (faster-whisper or Vosk), LLM (local server such as
   Ollama, or a cloud API), TTS (Piper or XTTS). Run them on a worker thread and stream
   sentence by sentence into the speech queue.
3. **Better VAD** (webrtcvad or Silero) and **barge-in** in voice-activation mode with acoustic
   echo cancellation.
4. **States** (idle, listening, thinking, speaking) as plugin triggers, like Voxta, so scene
   builders can attach Timeline animations without code.
5. **Gaze and attention** in the Person plugin: look at the user's camera while listening (for
   now use Glance).
6. Two AIs at once (one LLM persona per slot) and more than two slots if needed.
7. Viseme-based lip sync from TTS timing data, as an alternative to VaM's audio lip sync.
8. Publish the packages on VaMHub.

## License

[LGPL-2.1](LICENSE).
