# AIBody – test protocol for the first test in VaM 1.22 (from v0.6.3, now version 30; T9 from v0.7.2, T10 from v0.7.3, menu layout from version 15, T19–T21 from version 30)

Goal: the open "must do now" points that can only be checked in VaM. Please go through every point
in order and enter the result (✅ / ❌ / unclear). Duration: about 20 minutes.

**What I need for every point**

- a **screenshot of the plugin window** (on the left the status field with *Self-test*, *Live* and
  *Startup log*),
- all **red lines with "AIBody:"** from the error log (VaM: main menu, bottom left *Show Errors*,
  or the error message that opens by itself). Please copy as text or photograph.

**Preparation**

- Close VaM. In `<VaM main folder>/AddonPackages/` delete all old AIBody packages:
  `d0n.AIBody.1.var` to `d0n.AIBody.29.var`, `d0n.AIBodySession.*`, `d0n.AIBodyPerson.*`,
  `d0n.AIBodyPerson2.*`. Also remove loose files under `Custom/Scripts/d0n/AIBody/`.
- Copy `d0n.AIBody.31.var` to `<VaM main folder>/AddonPackages/`.
- Have the companion app ready (do **not** start it yet):
  `python -m aibody_companion --vam-root "D:\VaM"` (adjust the path to your own VaM folder).
  For T9 enter the xAI key in the plugin (tab **Voice** > field **XAI API Token**, from version 21) or set it before starting: `set XAI_API_KEY=xai-...` (cmd) or `$env:XAI_API_KEY="xai-..."` (PowerShell); the field wins.

---

## T1 – Old packages removed, loading from the `.var`

1. Start VaM, open a scene with a female standard figure (or a new scene + Person).
2. Select the figure (Person atom) > tab **Plugins** > **Add Plugin** >
   `AddonPackages > d0n.AIBody.31:/Custom/Scripts/d0n/AIBody/AIBody.cslist`.
   **Not** under *Session Plugins* or *Scene Plugins*.
3. If VaM asks whether to allow plugins from the package: allow it and note that it asked.
4. Open **Open Custom UI** (plugin window).

Report: Does only `d0n.AIBody.31` still show up in the package list? Did VaM ask for permission?
Screenshot of the window; red "AIBody:" lines. Expected: *Self-test* "Person atom: yes",
the Startup log ends with "Init complete, no errors."

## T2 – File paths: `GetFiles` → `ReadAllText` / `DeleteFile`

1. Start the companion app (see above).
2. Wait about 5 seconds.

Report: Does the *Self-test* say "PluginData writable: yes" and "Companion app heartbeat: yes"?
Does *Live* say "Companion app: connected …"? Do files stay lying around in
`<VaM>/Saves/PluginData/AIBody/default/inbox/` (it should stay empty)? Are there lines like
"Could not delete processed inbox file"? Is there
`<VaM>/Saves/PluginData/AIBody/config.json`?

## T3 – Head audio, lip sync, `PlayNow` retry, start / end

1. In the companion app's window (console) type a sentence and press Enter, e.g. `Hello, how are you?`.
2. Listen and look at the mouth. Type three sentences quickly one after another (queue).

Report: Can you hear the sound from the figure's head (the test engine `tone` plays a hum instead of a voice)? Does the mouth move (lip sync)? Does the sound come
immediately or only after 1–2 seconds? Are the three sentences played one after another? In the
companion app: do `speech_started` / `speech_ended` or errors like `audio_failed` appear
(please copy the console lines)? Does the *Self-test* say "Head audio (HeadAudioSource): yes"?

## T4 – Menu refresh and text field

Tabs from version 15: Voice, AI Character, Client Character, Config (before: Voice Mode, AI, AI Character, Client Character, Post, Config, Advanced). One large info field on the left, only controls in the tabs.

1. Open the tab **Client Character**. At the top of the info field on the left it says "Info: Client Character" with the push-to-talk explanation and the microphone status.
2. Open the tab **Voice**: at the top the section *Voice Mode*, below it *Voice > AI Character*; open the choosers. In the info field: Q&A help, AI mode help, key status, engine status.
3. Tab **Config**: press **Reload Config JSON**; the info field shows the path of config.json, the network status and the result.
4. Tab **AI Character**: the section **Poses** is there; click into the labeled field under "Breath morph" and change a letter, then go back.
5. Click through all four tabs once. No empty field, no empty chooser and no field with only a tab name may appear. From version 16: the info field shows only the information of the open tab (from version 17 without a header line above it, height 1800: do you still have to scroll?); self-test and Startup log are in the tab Config; at the top it says `Startup: ok` (or the errors in red).

Report: Does the device list show the real microphones? Can you type into the breath morph field? Does the
info field show matching help for every tab? Do the tabs switch
cleanly (old elements gone, no duplicates)? Is there a *WARNING "is read-only"* in the Startup log?

## T5 – Pose memory, morph names, breath morph

1. Tab **AI Character** (v0.7.1: *Body*): switch **Body control** and **Breathing** on; look at the chest. Read the line "Breath morph" under *Live*.
2. In the companion app type one after another: `Hello` (happy + nod), `No` (sad +
   head shake), `What are you doing?` (thoughtful + head tilt). The test engine sends expression
   and gesture along automatically. Watch the face and head.
3. **Pose memory:** quit the companion app. Save an own pose of the figure (figure > tab
   *Pose* > save preset, e.g. as `Custom/Atom/Person/Pose/test.json`). Then create a
   text file `<VaM>/Saves/PluginData/AIBody/default/inbox/pose_test.json` with the content
   `{ "v": 3, "type": "pose", "id": "p-1", "path": "Custom/Atom/Person/Pose/test.json" }`
   (adjust the path to your own pose). Put the figure in a somewhat different position first.

Report (since version 13): the lines in the *Self-test* "Pose storage (PosePresets)", "Poses",
"Breath morph", "Expression morphs: x of y found – missing: …" and possibly "Timeline"; the same values
appear in the companion app's console and in `companion.log` as "Plugin self-test: …".
Does the chest rise and fall? Does *Live* say "Breath morph: Breath1" or "not found"?
Does the face change while speaking (smile, eyebrows)? Please copy red lines with "Morph not found"
in full. Do the nod / head shake / head tilt arrive? Does the figure jump into the saved pose? What
does *Live* say for the last command, and what is in the newest file in
`Saves/PluginData/AIBody/default/outbox/` (e.g. "Atom has no PosePresets storable")?

## T6 – Add, remove, save, reload (exceptions, FPS)

1. Switch on the FPS display (VaM: *User Preferences* > *Show FPS*), note the FPS without the plugin.
2. Add the plugin as in T1, note the FPS. Quit the companion app (Ctrl+C), wait 20 s,
   look at *Live* / self-test, start the app again, wait 10 s.
3. Save the scene (*File* > *Save Scene*), reload the scene, open the plugin window.
4. Remove the plugin (Plugins tab > **X** at the entry), add it again.

Report: FPS without / with the plugin. After quitting the app, does it say "DISCONNECTED" and after the restart
"connected" again without you clicking anything? Are your own settings still there after reloading?
Red lines on removing, saving or reloading? How many files are in
`Saves/PluginData/AIBody/default/outbox/` after a minute without the app (should be at most ~20)?

## T7 – Engine status (from v0.7.0)

1. The companion app is running (without API keys).
2. Open the tab **Voice**, under *Voice > AI Character* choose `elevenlabs` for **Text-to-speech**, wait 3 seconds.
3. Type a sentence in the companion app.

Report: Does the info field on the left say "Text-to-speech: elevenlabs – not configured: …" and
"running instead: tone (fallback)"? Does the figure still speak (hum)? (From version 17 the
engine line appears only once, in the engine status.) Afterwards choose `tone` again.

---

## T8 – Realtime speech and proactive speaking (from v0.7.1)

Needs an xAI key (field **XAI API Token**, environment variable `XAI_API_KEY` or `ai.xai.key_file` in `config.json`)
and preferably a headset.

1. Start the companion app with the key. The app's log should say: `Mode: auto -> realtime` and
   `Realtime: connected to wss://api.x.ai/v1/realtime?model=grok-voice-latest`.
2. In the plugin tab **Voice**: **AI mode** is `auto`; the info field says
   "Mode: realtime – Realtime connected …" and "Proactive talking: on - after 90 s of silence the AI may speak on its own (speech delay timer, not the answer delay)".
3. Say something (e.g. "Hello, what time is it?"). The figure should answer after a short pause,
   the mouth moves, the time is roughly right.
4. While she speaks, press **Push-to-talk** (or, with a headset and **Voice barge-in (headphones)**
   switched on, just talk over her): she should fall silent at once.
5. Set **Speech delay timer (s)** (until version 22 "Proactive idle (s)") to 20, stay quiet for 30 seconds: the figure says something on its own
   (or deliberately stays silent – then the app log says `Proactive talking: the AI chose to stay silent`).
6. Set **AI mode** to `chain`: the status shows "Mode: chain"; afterwards back to `auto`.

Report: lines 1–2 from the app log, how long it takes until the answer (estimated), whether the
answer sounds choppy (pauses between the pieces), whether interrupting works, and all lines
with `Realtime` or `failed` from the app log.

---

## T9 – Sound in the game: question → audible answer (from v0.7.2)

Goal: an audible answer should simply come from the figure's head. Body control is not needed for it.


1. Tab **Voice** > **Question and Answer** (two lines, centered; "Simple Q&A mode" until version 20; sets AI mode `qa` and Body control off; check in the
   tab **AI Character**). Set **Speech volume** to 1.
2. Tab **Voice** > **Play test tone** (plays the file from the package, without the companion app).
   In the status field under *Live* it says `Audio: Loading: AIBodyTest.wav`, then `Speaking: AIBodyTest.wav (1.5 s)`, then `Done: …`.
3. Start the companion app with an xAI key, then **Test tone via companion** (file from
   `Custom/Sounds/AIBody/default/`). Under *Live* it says `Audio folder: …`.
4. In the companion console type `Hello` + Enter (the same way as spoken, only without the microphone).
   Under *Live* it says `Last turn: Question (typed): Hello`, then `Last turn: Answer (…, xai -> xai): …`,
   and the figure speaks the answer (a few seconds of delay are normal).
5. Speak a question into the microphone. Expected: `Last turn: Heard: …`, then the spoken answer.

Report: Do you hear something in 2, 3, 4 and 5? What does *Live* say under `Audio:`, `Audio folder:`
and `Last turn:` each time? Please copy red lines (`Audio error: …`, `Language model error: …`, `Nothing understood …`)
exactly, together with the output of the companion console.

- If 2 sounds but 3 does not: after about 15 s the app switches by itself to
  `Saves/PluginData/AIBody/default/audio/` and plays the sound again (red line "audio folder
  switched to …"). Please report whether it sounds then.
- If it says "without an xAI API key": key not set (field **XAI API Token** in the tab **Voice** empty? Or the environment variable not set in the same console window as the app?) or enter a key file in `config.json` under
  `ai.xai.key_file` and press **Reload Config JSON** in the tab **Config**.

## T10 – Verbose log and realtime toggle (from v0.7.3)

1. Tab **Config** > switch **Verbose log** on. In the companion console it says
   `Verbose log on (turn trace) - log file <VaM>/Saves/PluginData/AIBody/logs/companion.log`.
2. Type or speak a question. The console shows lines like `[t0001 +0.00s] start: …`,
   `path: …`, `stt: …`, `llm request: …`, `tts: … wav='Custom/Sounds/AIBody/default/…'`, `speak sent: …`,
   `plugin: speech_started …` – all with the same turn number. In the status field
   *Recent events* appears with `Command speak …`, `PlayNow …`, `Speaking …`, `End …`.
3. Tab **Voice** > switch **Use realtime voice** on: below it, under *Voice > AI Character*, AI mode
   is `auto`, the console reports the mode change. Off again: AI mode `qa`.
4. Switch **Verbose log** off again: the turn lines stop.

Report: the file `companion.log` from `<VaM>/Saves/PluginData/AIBody/logs/` (contains no keys,
but please have a quick look anyway) and a screenshot of the status field with *Recent events*.

## T11 – Microphone settings, pose menu, AI body control, latency (from v0.7.4)

1. Tab **Client Character** (without a microphone selection since 19.11.2026): no **Mic device** menu, no
   **Refresh microphones** button. The info field on the left says `Mic: capturing | microphone: system default input | mode: …`.
   Without a running companion app: red line
   `Companion app not running, so nothing is heard or spoken. Start it in a console, in the 'companion' folder: python -m aibody_companion --vam-root "D:\VaM"`; after the app is
   started it disappears. Speak (the level moves): the app records from the Windows default input device.
   Another microphone: set it as the default device in Windows and restart the app. An old scene with a
   stored "Mic device" loads without an error (the value is ignored).
2. Tab **AI Character** > section **Poses**: open the menu (poses from `gestures.json` and from
   `<VaM>/Custom/Atom/Person/Pose/` or `.../Pose/AIBody/`), choose one, **Apply pose**.
   Status field: result of the action. **Reload poses** after putting a new pose file there.
3. Choose an expression > **Show expression**; choose a gesture > **Play gesture**.
4. Tab **Voice** > **Use realtime voice** on, tab **AI Character** > **Body control** on.
   Say: "Smile for me" or "Strike another pose". Console: `realtime tool call` or
   `llm tool call` (with Verbose log), the figure reacts. With **Question and Answer** it does not react
   (speech only, as intended).
5. After every answer in the status field (*Live*): `Latency to first sound: X s (avg Y s, n turns)` and
   below it the breakdown. In the console: `Latency t000N to first sound: …`.
6. Tab **Voice** without a key: the info field shows the key status `missing` with `needed: API key from console.x.ai … a Grok subscription /
   grok.com token does not work`.

Report: screenshot of the info field (tab Client Character), screenshot of the status field with the
latency, console output.

## T12 – Field "XAI API Token" and button "Question and Answer" (from version 21)

1. Tab **Voice**, section *Voice Mode*: the button at the top has two lines **Question** / **& Answer**,
   text centered, text not cut off. Below it **Active**, **Use realtime voice**, **API Reconnect**,
   then the label **XAI API Token**, the text field and below it the masking note (since version 24; the scene warning "(beware: scenes save it)" no longer exists).
2. Start the companion app **without** `XAI_API_KEY` (the warning "No xAI API key yet" is correct). Info field on the left:
   `xAI key: missing` and the pointer to the field.
3. Click into the field, paste the xAI key (console.x.ai) (Ctrl+V). Expected: after about a second
   the info field says `xAI key: configured – plugin field 'XAI API Token'`; app console:
   `XAI API Token from the plugin field set` (the token itself appears nowhere, not even with Verbose log).
4. Press **Question and Answer**, speak or type a question: audible answer. Function as before.
5. Empty the field: `xAI key: missing`. Fill the field with nonsense (e.g. `abc`): it is accepted
   without a format check, the first request reports `rejected` (HTTP 401/403).
6. (Version 24) Save the scene, restart VaM, load the scene: the field is filled again, now **masked** (`xai-****abcd`);
   `config.json` contains `ai.xai.api_key` (plain text) and next to it `ai.xai.api_key_warning`. In the left info field (tab Voice) it says
   "SECURITY NOTICE: …" at the top, not below the field. Info field `xAI key: configured`.
7. (Version 24, mask by focus since version 30) Select the field and paste another key: once the field loses focus it shows the new mask, `ai.xai.api_key`
   has the new value (check the file, other keys unchanged). Type into the mask: the token stays unchanged, the
   mask comes back. Empty the field: `xAI key: missing` (without an environment variable), `ai.xai.api_key` is `""`.
8. (Version 24) Open the companion log (`companion.log`) and the plugin log: the token appears nowhere.

Report: screenshot of the tab **Voice** (button, field, note), info field on the left, red `AIBody:` lines, output of the
companion app console. Important: whether pasting with Ctrl+V into the field works, whether the button is centered on two lines.

### T11a – Microphone diagnosis without VaM (`tools/mic_test.py`, from version 16)

1. Quit the companion app. In the repo folder (after `git pull`): `python tools/mic_test.py`.
   Output: versions, host APIs, all devices raw, input devices per host API, input devices of the default host API
   (`*` = default device, the one the app records from). File `mic_test_output.txt` in the current folder.
   Since 19.11.2026 diagnosis only: no microphone selection, no message to the plugin, no `--vam-root`.

Report: `mic_test_output.txt`.

**Send back the result:** per point T1–T12 ✅/❌, the screenshots, the red "AIBody:" lines and,
for problems with an answer, the file `companion.log` (with Verbose log switched on).

## T13 – Voice detection and echo lock (version 24)

Needs a real microphone and speakers. Companion started with a real xAI key (or offline engines).

1. Tab **Client Character**: **VAD engine** (Auto / Built-in / WebRTC), **VAD strictness** (0-3). Info field shows
   `Voice detection: energy (built-in, ...)`. Without `webrtcvad-wheels`, choose WebRTC: a `Note:` line explains how
   to install it and the built-in detector keeps working. After `python -m pip install webrtcvad-wheels` and a
   companion restart, Auto shows `Voice detection: webrtc ...`.
2. Speak a sentence with a pause between two words (about 0.3 s): one utterance, not two. Switch on a fan or play
   music quietly: nothing is heard as speech with strictness 2-3 (raise it or **VAD threshold** if not).
3. Echo: speakers (no headphones), let the character talk a long answer. The AI must not answer itself, in voice mode
   and in realtime mode. Watch for self-triggers right after the voice ends; if there are any, raise **Echo gate tail
   (s)**.
4. Speak just after the character has finished: you are heard (tail only 0.4 s by default).

## T14 – Gaze control (version 25)

Needs VaM with the AI Character (AIBody) and the Client Character in the example scene. No Glance on the AI Character.

1. Tab **AI Character** > **Gaze**: **Gaze control** on, **Default gaze** = *Client Character*: the AI's eyes turn to the
   client's face. *Camera / player*: they look at you (VR or screen camera). *Straight ahead*: level, 2 m in front of the
   face. Pick an *Atom: …* entry (open the list; it refills): the eyes look at that atom. *VaM default*: the eyes go back to
   what they did before (VaM look mode and eye target position are restored).
2. Info field (left): *Gaze now: looking at … (default gaze)* and the help text. Turn **Gaze control** off: *Gaze now: off*.
3. Ask the AI (not Question and Answer mode) to look at you, at the client, away; the AI uses `look_at` (console line / log
   `look_at`). *Away* looks to the side for about 3 s and returns to the default.
4. **Gaze follows speaker** on, Default gaze = *VaM default*: while the AI or you talk, the eyes go to the client; silent: back.
5. Coexistence: add the Glance plugin to the AI Character: the info field says *paused: Glance is on this Person*, the AI
   gets no `look_at` tool. Remove it again (or switch the Eyes look mode by hand in VaM while AIBody steers): AIBody stops
   and says so; picking a Default gaze takes the eyes again.
6. Report: where the eyes look in each step (correct / mirrored / too high / too low), whether *Straight ahead* really is
   the way the face points, the VaM error log.

## T18 – Local engines, Silero, voice barge-in (version 29)

Needs VaM with the AI Character (AIBody 29 or later) and the companion app from this version. Steps 1-2 need [Ollama](https://ollama.com) with a model, step 3 needs `python -m pip install onnxruntime` and the file `silero_vad.onnx` (see `docs/LOCAL_ENGINES.md`), step 4 needs speakers (no headphones).

1. **Ollama:** `ollama pull llama3.2`, tab Voice > AI Character > **Language model** = `ollama`, AI mode *chain*. Type into the app console or speak (Speech-to-text xai or typed): the character answers with the local model; the status line (info field) names the engine `ollama`. Report: answer quality and delay, do expressions follow (the `<<tag>>` or the fallback from the words), anything spoken that should not be (tags read aloud, markdown)?
2. **Ollama problems:** stop Ollama: the next question gives the red message *no connection to Ollama … ollama serve* and the test model answers. Choose a model that is not installed (`ai.ollama.model`): *model … is not installed - run: ollama pull …*. Memory switch on with Ollama selected: the summary at the end must not contact xAI (check the app log).
3. **Silero:** copy the model file, tab Client Character > **VAD engine** = *Silero*: the info field says `silero (onnxruntime), strictness 2`. Speak, pause, speak: utterances are cut at your pauses; in a noisy room compare with *Built-in* and *WebRTC*. Report: false triggers by noise, missed quiet speech, strictness 0 to 3 effect. Without the file the info field says why it is not used (no crash).
4. **Voice barge-in:** set `ai.barge_in.enabled` true in `config.json`, restart the app, voice activation mode, speakers on. Let the character speak a long answer, then talk clearly louder over it: after about 0.6 s the character stops and your sentence is answered (console: `Voice barge-in: …`). Report: how loud do you need to be, does the character's own voice ever trigger it (then raise `ratio` or `min_ms`), is the start of your sentence kept? Do the same in realtime mode.
5. Report the VaM error log lines with `AIBody:` and `companion.log`.

## T16 – Emotions, personas, memory (version 27)

Needs VaM with the AI Character (AIBody 27 or later) and the companion app from this version with an xAI key; AI mode not Question and Answer (chain or auto) for steps 1-3.

1. **Expression from the words:** say or type something clearly happy ("That is wonderful, haha"), sad, surprised. The face should follow the AI's answer even though it calls no `express` (console line `Expression from the words (the AI chose none): happy`). Report which morphs move and whether the strength (0.85) looks right.
2. **Fade:** about 6 s after the AI has finished talking the face blends back to neutral over about 2.5 s. Change `ai.emotion.fade_after_s` / `fade_seconds` in `config.json` (restart the app) if it is too slow or too fast.
3. **Listening face:** while you talk, a very small brow raise appears (preset `listening`); when the AI starts to answer it is replaced. Report whether it is visible at all or too much (preset values in `ExpressionController.cs`; you can override `listening` in `expressions.json`).
4. **Persona:** copy `examples/personas/Anna` to `Saves/PluginData/AIBody/personas/Anna` (so `…/personas/Anna/persona.json`). Tab Voice > **Persona**: after a few seconds *Anna* is in the list; pick it: the voice changes to *ara*, the AI calls itself Anna, the console says `Persona: Anna`. *(none)* = back to `ai.persona`. Info field (left, tab Voice): persona and memory lines. Pick a name that does not exist (edit `ai.persona_name` in `config.json`): the info field says *not in use … not found*.
5. **Memory:** switch **Memory** on, say "My name is Leon and I like cats" and one more sentence, then be silent for 10 minutes (or lower `ai.memory.session_idle_minutes`, or stop the app with Ctrl+C: it summarizes first). `personas/default/memory.json` (or `personas/Anna/memory.json`) holds the notes; restart the app, ask "What is my name?". **Forget memory** deletes the file and the AI no longer knows. Report: did the summary request work (console lines `Memory: …`), are the notes correct, any invented facts?
6. One character per app (since version 30): for a second persona run a second VaM instance and app.
7. Report the VaM error log lines with `AIBody:` and `companion.log`.

## T15 – Natural gaze, blinking, scene hooks (version 26)

Needs VaM with the AI Character (AIBody) and the companion app (AI mode not Question and Answer for step 6). No Glance, no Life on the AI Character for steps 1-5.

1. Tab **AI Character** > **Gaze and blinking** > **Default gaze** = *Natural (looks around)*: the eyes stay on the client (or on you) with tiny moves and look away briefly every few seconds; the info field says *looking at the client (natural gaze)*. Report: too busy, too calm, too wide?
2. Speak a sentence and stop: while the AI "thinks" it glances up and aside once. Needs *Level meter* on (tab Client Character). While the AI talks it glances away more often.
3. **Blink control** on: VaM's blinking stops, AIBody blinks (irregular). Info field *Blinking now: blinking by AIBody*. Off again: VaM's blinking is back and the eyes are open. Report: morph "Eyes Closed" found on the female and the male figure? Do the eyelids move normally, no stuck-closed eyes?
4. With Blink control on, open the character's Eyelid Control (Atom > Person > Eyes/Eyelids) and switch **Blink enabled** on by hand: AIBody must stop (*stopped: someone switched VaM's auto blink on again*). Toggle **Blink control** off and on to take over again.
5. Add Life (Gaze / Eyes) to the Person: the info field says *paused: Life (MacGruber Gaze)* / *Life (MacGruber Eyes)*. Report the real plugin id if the pause does not appear (Plugins tab of the atom shows `plugin#N_<name>`).
6. Scene hooks: add a trigger on any atom (for example a UIButton): receiver = the Person, receiver target = the AIBody plugin, **Scene event** (string) = `A bell rings`, or an action such as `Look at camera` / `Expression: happy` / `Blink now`. Check that the targets appear in the trigger list at all. With the companion running (chain or realtime, not Q&A) the AI reacts briefly to the bell or stays silent; the log of the companion shows `Scene event: A bell rings`. Also check the values `AI speaking` / `User speaking` are listed as readable values for other plugins.
7. Report what is missing in the trigger list (which entries appear), and the VaM error log.

## T19 – Network Active (version 30)

Needs VaM with the AI Character (AIBody 31) and the companion app from this version. The companion listens on `127.0.0.1:38437` (`connection.network_port`). VaM's *User Preferences > Security > Allow Plugins Network Access* has to be on for steps 1-4 and off for step 5.

1. **Default:** add the plugin, start the companion app. Tab **Config**: **Network Active** is on. The info field shows `Network: connected` within a few seconds (it may say `connecting ...` first). The console of the app says that the plugin linked up over the network. Type a sentence into the app console: the answer is spoken as usual. Report the `Network:` line and whether the delay is the same as or shorter than before.
2. **Off:** switch **Network Active** off: the info field says `Network: off`, the companion console reports that the link dropped, everything keeps working through the files (type a sentence: it is spoken). Switch it on again: `connected` returns without restarting anything.
3. **Companion not running:** quit the app: the info field says `Network: unavailable, using files` (and the red "Companion app not running" line); VaM does not stutter (note FPS). Start the app again: `connected` returns by itself.
4. **Scene and file:** save the scene with **Network Active** off, reload it: it is still off, and `config.json` says `"network_active": false`. **Reload Config JSON** applies the file's value.
5. **VaM's network switch off:** switch *Allow Plugins Network Access* off (restart VaM if it asks), add the plugin. Report exactly what happens: a prompt from VaM, an error in the log (copy the red `AIBody:` lines), or the plugin loads and says `Network: unavailable, using files`. The file channel must keep working (type a sentence).
6. **Token never over the socket:** with Verbose log on, paste a token into the field: the app log shows the token only as masked, and the token arrives (info field `xAI key: configured`). (The token travels through the file channel on purpose.)
7. Report the VaM error log lines with `AIBody:` and the app console.

## T20 – Token masking by focus (version 30)

Needs VaM with the AI Character (AIBody 31). Use a harmless fake token such as `xai-0123456789abcdefghij` for steps 1-3.

1. Tab **Voice** > field **XAI API Token**: click into it and paste the fake token. While the field has focus you see the whole text (no mask, no timer).
2. Click outside the field (another control or another tab and back): the field shows the first 4 and the last 4 characters with stars between them (`xai-****ghij`). Click into the field again: the real text is shown again while it has focus.
3. Type into the masked field without first selecting everything: the real token must not be overwritten by the mask text (`****` is ignored); after leaving the field the mask returns.
4. Save the scene while the field is focused and the full text is typed (and once more after clicking away), open the scene file in a text editor and search for the fake token and for `XAI API Token`: since version 31 neither the token nor the mask is in the scene (the field is not registered with VaM); report if either shows up. `config.json` holds the full token in `ai.xai.api_key`.
5. Report: does `InputField.isFocused` work on VaM's field (does the mask appear when you click away)? Is the text cursor visible (known problem, see BACKLOG: cursor fix, low priority)?

## T21 – First-run note (version 30)

Needs VaM with the AI Character (AIBody 31). Start without a token: no `ai.xai.api_key` in `config.json` (or move the file away), no `XAI_API_KEY`, and `ui.first_run_hint_dismissed` not set.

1. Add the plugin and open the tab **Voice**: at the very top there is one short note "An xAI API token is required. Paste it here, or later in Voice > XAI API Token.", ONE text field and ONE button. The button says **Close** while the field is empty.
2. Paste a fake token into the note's field: the button changes to **OK**, and the field follows the masking rules of T20 (full text while focused, mask when not).
3. Press **OK**: the note disappears, the token is set exactly as if you had typed it into the tab Voice field (info field `xAI key: configured`, `config.json` holds it). Reload the scene or restart VaM: the note does not come back.
4. Remove the token (empty the field in the tab Voice and delete `ai.xai.api_key`), reset `ui.first_run_hint_dismissed` to `false`: the note shows again. This time press **Close** with the field empty: it disappears, points at the token field in the tab Voice and does not come back.
5. With a token already present from the start, the note never appears.
6. Report: look and size of the note, whether the button label changes while typing, VaM error log lines with `AIBody:`.

## T22 – Remote control (version 31)

Needs VaM with the AI Character (AIBody 31) and the companion app from this version. Edit `Saves/PluginData/AIBody/config.json` section `remote`: `"enabled": true` (leave `token` empty), restart the app. The remote is off until you do this.

1. The console shows `Remote control: web page and HTTP API on http://127.0.0.1:38438/ (this computer only; ...)`, and `config.json` now has a `remote.token` (copy it). Without `enabled` nothing is opened.
2. Open `http://127.0.0.1:38438/#token=<token>` in a browser on this computer: the status shows `Plugin: connected`, the expressions / gestures / poses of the character appear as buttons. Type a sentence and press **Say exactly this**: the character speaks it. **Ask the AI** answers like a typed question. **Stop** stops speech.
3. Click an expression, a gesture and a pose button: they show on the character (with *Body control* on in the tab AI Character). With *Body control* off the page shows `FAILED - body control is off in the plugin` under Remote.
4. From a console on the same computer: `curl -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d "{\"text\":\"Hello\"}" http://127.0.0.1:38438/api/say` speaks; the same call without the header or with a wrong token answers HTTP 401.
5. Save and reload the scene, change something in the plugin menu, wait 2 s: `config.json` still holds the `remote` section with your token (the plugin keeps it).
6. Optional OSC: set `"osc_port": 9000`, restart, send `/aibody/say "Hello"` from any OSC tool on this computer (for example `python -m pip install python-osc` and `SimpleUDPClient("127.0.0.1", 9000).send_message("/aibody/say", "Hello")`): the character speaks. Report that OSC works without a token.
7. Not reachable from elsewhere: from another computer in the network, `http://<this computer's IP>:38438/` must not connect.
8. Report the red `AIBody:` lines in VaM and the companion console output.

## T23 – Plugin preset (version 31)

Needs VaM with `d0n.AIBody.31.var` in `AddonPackages`, a Person atom WITHOUT the AIBody plugin.

1. Select the Person > tab **Plugins** > **Load Preset** (Plugins tab, preset browser). Look for `Preset_AIBody` under the package `d0n.AIBody.31` (the browser hides some plugin presets; also try *Packages* and the folder `Custom/Atom/Person/Plugins/AIBody`). Take a screenshot of what you see.
2. Load it: the plugin `AIBody` (from `d0n.AIBody.31:/Custom/Scripts/d0n/AIBody/AIBody.cslist`) appears in the Plugins tab, exactly once, and its UI opens as usual. Report the `AIBody:` startup lines.
3. Load the preset a second time on the same Person: report whether a second copy of the plugin appears (and, if you had other plugins on the Person, whether the preset removed them).
4. Report anything VaM complains about in the red log lines.
