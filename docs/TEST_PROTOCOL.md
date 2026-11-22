# AIBody – test protocol for the first test in VaM 1.22 (from v0.6.3, now version 44; T9 from v0.7.2, T10 from v0.7.3, menu layout from version 15, T19–T21 from version 30, T22–T23 from version 31, T24–T29 from version 32, T38–T42 from version 36, T43 after version 36, T44 from version 37, T45 after version 37, T46 from version 38, T47 from version 39, T48–T51 from version 40, T52–T58 from version 41)

Goal: the open "must do now" points that can only be checked in VaM. Please go through every point
in order and enter the result (✅ / ❌ / unclear). Duration: about 20 minutes.

**What I need for every point**

- a **screenshot of the plugin window** (on the left the status field with *Self-test*, *Live* and
  *Startup log*),
- all **red lines with "AIBody:"** from the error log (VaM: main menu, bottom left *Show Errors*,
  or the error message that opens by itself). Please copy as text or photograph.

**Preparation**

- Close VaM. In `<VaM main folder>/AddonPackages/` delete all old AIBody packages:
  `d0n.AIBody.1.var` to `d0n.AIBody.39.var`, `d0n.AIBodySession.*`, `d0n.AIBodyPerson.*`,
  `d0n.AIBodyPerson2.*`. Also remove loose files under `Custom/Scripts/d0n/AIBody/`.
- Copy `d0n.AIBody.44.var` to `<VaM main folder>/AddonPackages/`.
- Have the companion app ready (do **not** start it yet):
  `python -m aibody_companion --vam-root "D:\VaM"` (adjust the path to your own VaM folder).
  For T9 enter the xAI key in the plugin (tab **Voice** > field **XAI API Token**, from version 21) or set it before starting: `set XAI_API_KEY=xai-...` (cmd) or `$env:XAI_API_KEY="xai-..."` (PowerShell); the field wins.

---

## T1 – Old packages removed, loading from the `.var`

1. Start VaM, open a scene with a female standard figure (or a new scene + Person).
2. Select the figure (Person atom) > tab **Plugins** > **Add Plugin** >
   `AddonPackages > d0n.AIBody.44:/Custom/Scripts/d0n/AIBody/AIBody.cslist`.
   **Not** under *Session Plugins* or *Scene Plugins*.
3. If VaM asks whether to allow plugins from the package: allow it and note that it asked.
4. Open **Open Custom UI** (plugin window).

Report: Does only `d0n.AIBody.32` still show up in the package list? Did VaM ask for permission?
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
4. Tab **AI Character**: the section **Poses** is there; (until version 46: the labeled field under "Breath morph"; gone in version 47) click into the field under "New pose command" (Add Pose) and change a letter, then go back.
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
   *Pose* > save preset under the name `Sit Down`, i.e. the file `Custom/Atom/Person/Pose/Preset_Sit Down.vap`).
   Then create a text file `<VaM>/Saves/PluginData/AIBody/default/inbox/pose_test.json` with the content
   `{ "v": 3, "type": "pose", "id": "p-1", "command": "Sit Down", "json": "{\"pose\":\"Sit Down\"}" }`
   (since version 32 a pose command carries only this JSON; `path` and `name` are refused). Put the figure in a
   somewhat different position first. The full pose command test is T24-T29.

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
   Say: "Smile for me" (poses are no AI tool any more since version 32: "Strike another pose" must NOT move the
   body, see T24-T29). Console: `realtime tool call` or
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
4. (Removed after version 36: *Gaze follows speaker* is gone, see T43.) Default gaze = *VaM default*: while the AI or you talk, the eyes stay with VaM.
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

Needs VaM with the AI Character (AIBody 32) and the companion app from this version. The companion listens on `127.0.0.1:38437` (`connection.network_port`). VaM's *User Preferences > Security > Allow Plugins Network Access* has to be on for steps 1-4 and off for step 5.

1. **Default:** add the plugin, start the companion app. Tab **Config**: **Network Active** is on. The info field shows `Network: connected` within a few seconds (it may say `connecting ...` first). The console of the app says that the plugin linked up over the network. Type a sentence into the app console: the answer is spoken as usual. Report the `Network:` line and whether the delay is the same as or shorter than before.
2. **Off:** switch **Network Active** off: the info field says `Network: off`, the companion console reports that the link dropped, everything keeps working through the files (type a sentence: it is spoken). Switch it on again: `connected` returns without restarting anything.
3. **Companion not running:** quit the app: the info field says `Network: unavailable, using files` (and the red "Companion app not running" line); VaM does not stutter (note FPS). Start the app again: `connected` returns by itself.
4. **Scene and file:** save the scene with **Network Active** off, reload it: it is still off, and `config.json` says `"network_active": false`. **Reload Config JSON** applies the file's value.
5. **VaM's network switch off:** switch *Allow Plugins Network Access* off (restart VaM if it asks), add the plugin. Report exactly what happens: a prompt from VaM, an error in the log (copy the red `AIBody:` lines), or the plugin loads and says `Network: unavailable, using files`. The file channel must keep working (type a sentence).
6. **Token never over the socket:** with Verbose log on, paste a token into the field: the app log shows the token only as masked, and the token arrives (info field `xAI key: configured`). (The token travels through the file channel on purpose.)
7. Report the VaM error log lines with `AIBody:` and the app console.

## T20 – Token masking by focus (version 30)

Needs VaM with the AI Character (AIBody 32). Use a harmless fake token such as `xai-0123456789abcdefghij` for steps 1-3.

1. Tab **Voice** > field **XAI API Token**: click into it and paste the fake token. While the field has focus you see the whole text (no mask, no timer).
2. Click outside the field (another control or another tab and back): the field shows the first 4 and the last 4 characters with stars between them (`xai-****ghij`). Click into the field again: the real text is shown again while it has focus.
3. Type into the masked field without first selecting everything: the real token must not be overwritten by the mask text (`****` is ignored); after leaving the field the mask returns.
4. Save the scene while the field is focused and the full text is typed (and once more after clicking away), open the scene file in a text editor and search for the fake token and for `XAI API Token`: since version 31 neither the token nor the mask is in the scene (the field is not registered with VaM); report if either shows up. `config.json` holds the full token in `ai.xai.api_key`.
5. Report: does `InputField.isFocused` work on VaM's field (does the mask appear when you click away)? Is the text cursor visible (known problem, see BACKLOG: cursor fix, low priority)?

## T21 – First-run note (version 30)

Needs VaM with the AI Character (AIBody 32). Start without a token: no `ai.xai.api_key` in `config.json` (or move the file away), no `XAI_API_KEY`, and `ui.first_run_hint_dismissed` not set.

1. Add the plugin and open the tab **Voice**: at the very top there is one short note "An xAI API token is required. Paste it here, or later in Voice > XAI API Token.", ONE text field and ONE button. The button says **Close** while the field is empty.
2. Paste a fake token into the note's field: the button changes to **OK**, and the field follows the masking rules of T20 (full text while focused, mask when not).
3. Press **OK**: the note disappears, the token is set exactly as if you had typed it into the tab Voice field (info field `xAI key: configured`, `config.json` holds it). Reload the scene or restart VaM: the note does not come back.
4. Remove the token (empty the field in the tab Voice and delete `ai.xai.api_key`), reset `ui.first_run_hint_dismissed` to `false`: the note shows again. This time press **Close** with the field empty: it disappears, points at the token field in the tab Voice and does not come back.
5. With a token already present from the start, the note never appears.
6. Report: look and size of the note, whether the button label changes while typing, VaM error log lines with `AIBody:`.

## T22 – Remote control (version 31)

Needs VaM with the AI Character (AIBody 32) and the companion app from this version. Edit `Saves/PluginData/AIBody/config.json` section `remote`: `"enabled": true` (leave `token` empty), restart the app. The remote is off until you do this.

1. The console shows `Remote control: web page and HTTP API on http://127.0.0.1:38438/ (this computer only; ...)`, and `config.json` now has a `remote.token` (copy it). Without `enabled` nothing is opened.
2. Open `http://127.0.0.1:38438/#token=<token>` in a browser on this computer: the status shows `Plugin: connected`, the expressions / gestures / poses of the character appear as buttons. Type a sentence and press **Say exactly this**: the character speaks it. **Ask the AI** answers like a typed question. **Stop** stops speech.
3. Click an expression, a gesture and a pose command button (only commands whose pose exists are offered): they show on the character (with *Body control* on in the tab AI Character). With *Body control* off the page shows `FAILED - body control is off in the plugin` under Remote.
4. From a console on the same computer: `curl -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d "{\"text\":\"Hello\"}" http://127.0.0.1:38438/api/say` speaks; the same call without the header or with a wrong token answers HTTP 401.
5. Save and reload the scene, change something in the plugin menu, wait 2 s: `config.json` still holds the `remote` section with your token (the plugin keeps it).
6. Optional OSC: set `"osc_port": 9000`, restart, send `/aibody/say "Hello"` from any OSC tool on this computer (for example `python -m pip install python-osc` and `SimpleUDPClient("127.0.0.1", 9000).send_message("/aibody/say", "Hello")`): the character speaks. Report that OSC works without a token.
7. Not reachable from elsewhere: from another computer in the network, `http://<this computer's IP>:38438/` must not connect.
8. Report the red `AIBody:` lines in VaM and the companion console output.

## T23 – Plugin preset (version 31)

Needs VaM with `d0n.AIBody.32.var` in `AddonPackages`, a Person atom WITHOUT the AIBody plugin.

1. Select the Person > tab **Plugins** > **Load Preset** (Plugins tab, preset browser). Look for `Preset_AIBody` under the package `d0n.AIBody.32` (the browser hides some plugin presets; also try *Packages* and the folder `Custom/Atom/Person/Plugins/AIBody`). Take a screenshot of what you see.
2. Load it: the plugin `AIBody` (from `d0n.AIBody.32:/Custom/Scripts/d0n/AIBody/AIBody.cslist`) appears in the Plugins tab, exactly once, and its UI opens as usual. Report the `AIBody:` startup lines.
3. Load the preset a second time on the same Person: report whether a second copy of the plugin appears (and, if you had other plugins on the Person, whether the preset removed them).
4. Report anything VaM complains about in the red log lines.

## T24 – Pose commands: exact match (version 32)

Needs VaM with the AI Character (AIBody 32) and the companion app from this version, AI mode *chain* or *auto* with a key (the gate itself needs no key: the words are typed into the app). *Body control* on (tab AI Character).

Preparation: pose files. None ships with the package, so at first **all 10 starter commands are unavailable**. Pose the Person in a few different ways and save each pose preset (Person > tab *Pose* > save preset) with the command's name, e.g. `Sit Down` (file `Custom/Atom/Person/Pose/Preset_Sit Down.vap`), then tab AI Character > Poses > **Reload poses**. Matching ignores case, spaces, `_` and `-`, so `Preset_sit_down` works too. Make as many as you can: `Sit Down`, `Lay Down`, `Prone`, `Stand Up`, `Spread Your Legs`, `Ankle Your Knees`, `Ankle Your Elbows`, `Turn Around`, `Crawl on all fours`, `Bend Over`.

1. Tab AI Character > **Poses**: the info field lists the pose commands and which of them are available. Report which starters are unavailable.
2. For each command that has a pose file, type EXACTLY its text into the app (console or the app's input) or say it: the Person takes the pose, there is NO spoken answer, the status line says `Pose command: <command>`, and the console shows no language-model call for it. Report which commands worked.
3. Case and punctuation: `sit down`, `SIT DOWN`, `Sit Down.`, `Sit Down!`, `Sit Down?`, `  Sit   Down  ` each apply the pose again (put the figure in another position in between).
4. A command WITHOUT a pose file (for example one you did not make): type it. Nothing moves, no pose is applied, the console warns `Pose command '<x>' is unavailable: ...`. It is not offered to the AI.
5. Report the red `AIBody:` lines in VaM and the companion console output.

## T25 – Pose commands: near-misses must NOT trigger (version 32)

Same setup as T24, with `Sit Down` and `Prone` available.

1. Type each of these: `please sit down`, `sit down and smile`, `Sit Down please`, `sit`, `down`, `Sit-Down`, `sitdown`, `Can you sit down?`, `sit down, then stand up`, `Prone position`. The Person does NOT change pose; each is an ordinary conversation (the AI answers normally; the answer must not move the body into a pose).
2. Say the same sentences into the microphone (a sentence that only CONTAINS a command, such as "please sit down", must not move the body).
3. Ask the AI "Strike a pose" / "Sit down for me, please" (realtime and chain): it answers in words, the body does not take a pose (there is no pose tool).
4. Switch **Body control** off: type `Sit Down`: nothing happens (the words go to the conversation like any text). Switch it on again.
5. Report which sentence, if any, moved the body, plus the red `AIBody:` lines.

## T26 – Pose commands: realtime voice (version 32)

Needs VaM with the AI Character and the companion app, **Use realtime voice** on, `Sit Down` available (T24).

1. Say "Sit down." (only that): the Person takes the pose and the character does NOT answer by voice. Report if you hear the start of an answer anyway (the app cancels the realtime answer when the transcript arrives; TODO(verify): the real server may already have started it; report how much was heard).
2. Say "Please sit down.": an ordinary spoken answer, no pose.
3. Say "Sit down" and right after a normal question: the question is answered (the cancelled answer of the command must not swallow the next answer).
4. Report the console lines `Heard: ...` and `Pose command: ...` and the red `AIBody:` lines.

## T27 – Add Pose (version 32)

Needs VaM with the AI Character (AIBody 32) and at least one pose file (T24).

1. Tab AI Character > **Poses**: choose a pose in the pose chooser, type `Take a seat` into **New pose command**, press **Add Pose**. The info field shows the command linked to the pose, the command chooser contains `Take a seat`, and within about 2 seconds `config.json` > `poses.commands` has the new entry `{"command": "Take a seat", "pose": "<pose>"}` (the file also still holds the other commands).
2. Type `take a seat!` into the app: the pose is applied. Type `please take a seat`: nothing.
3. Press **Add Pose** with an empty text field, with only `...` as text, and with a text longer than 60 characters: a red note, nothing added.
4. Type `Take a seat` again with another pose chosen and press **Add Pose**: the command is not duplicated, it is linked to the new pose.
5. Report the entry in `config.json` and the red `AIBody:` lines.

## T28 – Delete Pose and Restore starter poses (version 32)

1. Tab AI Character > **Poses**: choose `Prone` in the command chooser (the first chooser), press **Delete Pose**: it disappears from the chooser; `config.json` > `poses.commands` no longer has it; typing `Prone` now does nothing special (it is an ordinary sentence).
2. Delete `Take a seat` (T27) too. Delete all remaining commands: the chooser and **Delete Pose** disappear (no empty menu) and no typed command applies a pose. Since version 35 an empty list means the starters: after **Reload Config JSON** (or the next start) the 10 starters are back.
3. Press **Restore starter poses**: the 10 starters are back (the info note says how many were restored), your own commands and links are untouched; a second press says all are already there.
4. Report the info field text and the red `AIBody:` lines.

## T29 – Pose commands: persistence and a missing pose file (version 32)

1. Add a command (T27), save the scene, quit VaM, start it, load the scene: the command chooser still holds it and it works. Check `config.json` > `poses.commands`.
2. Edit `config.json` while VaM is closed (add `{"command": "Wave Hello", "pose": "wave"}`), start VaM: the command is in the chooser; **Reload Config JSON** applies later edits. Remove the whole `poses` key and press **Reload Config JSON**: the starters are back.
3. Missing pose file: move the file of an available command (for example `Preset_Sit Down.vap`) out of the Pose folder, press **Reload poses**: the command is unavailable (no offer, typing it applies nothing and the console warns), but it is still in the chooser and in `config.json`. Put the file back and **Reload poses**: it works again.
4. Malformed JSON test: put `{ "v": 3, "type": "pose", "id": "p-9", "command": "x", "json": "{\"pose\":\"Sit Down\",\"x\":1}" }` as `inbox/pose_bad.json` (and once with `"json": "nope"`, and once with a pose id that is not linked to any command): nothing moves; the red log shows one short line `AIBody: Warning: Pose ignored: ...` each.
5. Report all red `AIBody:` lines and the companion console output.

## T30 – Starter poses from the start (version 35)

1. Close VaM and the app. Rename `Saves/PluginData/AIBody/config.json` (keep it as a backup). Start VaM, load the AI Character with AIBody 35.
2. Tab AI Character > **Poses**: the command chooser holds the 10 starters, **Delete Pose** is there. Within about 2 seconds the new `config.json` has the 10 starters in `poses.commands`.
3. Set `"poses": {"commands": []}` in `config.json`, press **Reload Config JSON** (tab Config): the starters are back.
4. Report the info field text and the red `AIBody:` lines; then restore your backup.

## T31 – Idle poses (version 35)

Needs the starter pose files (T24), at least `Stand Up` and one more.

1. Tab AI Character > **Idle poses**: *Idle poses* on, *Idle default pose* `Stand Up`, set *Idle pose min wait (s)* 10 and *max* 15. Do not talk to the character.
2. After 10-15 s it takes a random pose of the command list (never one whose pose file is missing), after the next 10-15 s it goes back to `Stand Up`, and so on. The info field line "Idle poses: on ..." shows the next step.
3. Talk to it (or let it speak): no pose change while either of you speaks; the timer starts again afterwards.
4. Say or type `Sit Down`: it sits and stays seated for at least 2 minutes (cooldown), then idle poses go on.
5. Switch **Body control** off: no idle pose changes any more. Switch *Idle poses* off: none either.
6. Close and reopen VaM: the four settings are kept (`config.json` > `body.idle_poses`, `idle_pose_min_s`, `idle_pose_max_s`, `idle_pose_default`).
7. Report the info field text and the red `AIBody:` lines.

## T32 – Own idle motion and breathing (version 35)

1. Remove any third-party idle / breathing plugin from the AI Character. *Idle head motion* and *Breathing* on (tab AI Character > Body).
2. Watch the character for a minute in a standing pose: the head sways a little, the upper body shifts slowly from side to side and rises and falls with the breath. Nothing jumps.
3. Apply another pose (Apply pose or a pose command): the motion continues in the new pose without a jump back.
4. Choose a breath morph that does not exist (or none): the chest still breathes through the motion.
5. Switch *Idle head motion* off: head and chest go back to the pose. Report whether the chest shift is visible (chest controller id `chestControl`, TODO(verify)) and the red `AIBody:` lines.

## T33 – Pose commands by voice (version 35)

1. With the app running and the microphone on, say `Sit down`, `Lay down`, `Turn around` clearly, each alone: the pose is applied every time, with no spoken answer. The console shows "Pose command: ..." (the speech-to-text result may end with `.`, `,` or `?`: it still matches).
2. Say `please sit down` and `sit down and smile`: no pose, a normal answer.
3. Say a German sentence such as `Setz dich hin`: no pose (there are no German commands). Optional: add `Setz dich hin` with **Add Pose** linked to the Sit Down pose and say it again: it sits.
4. Report the console lines for each sentence.

## T34 – Persona dropdown (version 35)

1. Tab Voice > section **Voice > AI Character** > **Persona**: the dropdown is there and shows at least `(none)`, also without the app running.
2. Copy `examples/personas/Anna` to `Saves/PluginData/AIBody/personas/Anna`, start the app: within a few seconds (or when the dropdown is opened) `Anna` is in the list; the info field says "Persona menu: 1 persona(s) ...". Choose `Anna`: the app console reports the persona change.
3. Report the list and the info field line.

## T35 – Companion app not connected / Test tone via companion (version 35)

1. Close the app. The menu shows only "Companion app: not connected" (tab Client Character and Voice); no "Start it in a console" text in the menu. The VaM log contains the start command once.
2. Press **Test tone via companion** with the app closed: the top of the Voice info field says it waits for the app. Start the app within 60 s: the test tone is heard, the info field says it arrived, the console says "Test tone sent: ...".
3. Press it again with the app running: the tone is heard at once. Report the info field lines.

## T36 – Body control off (version 35)

1. Switch **Body control** off (tab AI Character > Body). Ask the AI to smile and to wave, type `Sit Down`: it answers by voice, but no expression, gesture or pose; `Sit Down` is answered as ordinary text. No idle poses (T31).
2. Your own buttons still work: Apply pose, Show expression, Play gesture. Idle head motion, breathing, gaze and blink keep their own toggles.
3. The info field (AI Character) explains this. Switch it on again: everything works. Report the info field text.

## T37 – First-start questions in the companion app (version 35; replaced by T41 in version 36)

1. Start the app once with `python -m aibody_companion --vam-root "D:\VaM" --setup` in a console.
2. It asks first "Do you want a green background to use pass-through?", then "Do you want to use the standard scene as an example?". Answer `yes`, `yes`: `Saves/scene/AIBody/AIBody_Example.json` is written; load it in VaM: two people, green background, AIBody 35 on the AI Character.
3. Run with `--setup` again, answer `no`, `yes`: the scene is written again (the old one as `.bak`) without the green background. Answer `yes`, `no`: no scene is written; the console explains where the green background is set.
4. Start the app normally: no questions any more (`config.json` > `setup.asked` true). Report the console output.

## T38 – Background color in the plugin (version 36)

1. Plugin window > tab **Config**: below the other controls the section **Background**: toggle **Set background color** (OFF), below it the color picker (sliders and swatch, green #00FF00), below that the text "for pass-through transparency".
2. Switch it on: the sky / room background turns plain green in the desktop view and in the headset. Move the hue slider to purple: the background follows at once.
3. Switch it off: the old background (sky) comes back exactly as before. Switch on again, then disable the plugin (checkbox in the Plugins tab) and remove it: the old background comes back each time.
4. Switch on, save the scene, load it again: the background is on with the same color.

Report: screenshots in VR / desktop with green and after switching off, red "AIBody:" lines. TODO(verify): the headset view uses the same camera (`CameraTarget.centerTarget.targetCamera`).

## T39 – Scene from the package (version 36)

1. VaM > **Open Scene** (scene browser) > package `d0n.AIBody.36` > folder `AIBody` > **AIBody_Example** (`d0n.AIBody.36:/Saves/scene/AIBody/AIBody_Example.json`). Report exactly where the browser lists it (package shortcut on the left, or in the main list), and whether the AIBody plugin loads (the scene references it as `SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist`).
   Optional: copy the release asset `AIBody_Example.json` to `Saves/scene/AIBody/` and open it from the browser's folder `Saves/scene/AIBody`: the same scene.
2. Expected: AI Character (female) with AIBody 36, Client Character (male) 1.2 m opposite, no room, plain green background (tab Config of AIBody: Set background color ON); no question about a missing package.
3. Try to drag the AI Character's root controller: it does not turn and does not move up / down (anchored). In VR you start at the Client Character's place.

Report: screenshot, whether the anchor holds, where you start in VR.

## T40 – Choose what to use: Plugin (version 36)

1. In your own scene add AIBody to a Person (Plugins > Add Plugin or the preset). Nothing else is added; Set background color is OFF.

## T41 – Companion setup: background and Scene / Plugin are independent (version 36)

1. Start `python -m aibody_companion --vam-root "D:\VaM" --setup` in a console. First question: "Do you want a greenscreen background? [yes/no/abort]". Answer `abort`: the app says nothing was changed; start again with `--setup`.
2. Answer `yes`, then "Set your color for transparency [#00FF00]": type `#800080` (purple), then "Choose what to use": `plugin`. No scene is written. In VaM (your own scene with AIBody, T40): within a few seconds after the app connects (or with Reload Config JSON) Set background color switches ON and the color picker shows purple.
3. Switch it OFF in VaM, restart the app normally: it stays OFF (applied once).
4. `--setup` again: `no`, `scene`: `Saves/scene/AIBody/AI-Buddy.json` is written; load it: the scene without background color, Set background color OFF.
5. `--setup` again: `yes`, Enter (green), `scene`: the scene loads with the green background ON.

Report: the console output of each run and the tab Config after each step.

## T42 – Speech starts without a delay (version 36)

1. Ask three short questions in a row. Each answer starts without a noticeable gap after the companion log line "Say"; no answer is cut at the start, none plays twice.
2. Report the "Latency to first sound" line of the status field before (version 35) and now, if you still have it.

## T43 – Eyes belong to VaM, Body control ON, menus by topic (after version 36)

1. Tab AI Character: no gaze or blink entry anywhere (no "Gaze and Blinking" block, no Gaze control, Default gaze, Blink control), and the left info field does not mention gaze or blinking. Scene trigger actions of AIBody: no Look at ... / Gaze back to default / Blink now. Asking the AI to look at you does nothing special; VaM's own eye movement and blinking are unchanged.
2. Expressions (Show expression, Reset expression, Reload expressions) and gestures (nod, shake, tilt via Play gesture) work as before.
3. An old `config.json` with `body.gaze_control`, `body.gaze_default`, `body.gaze_follows_speaker` or `body.blink_control` loads without a warning; after a few seconds the plugin rewrites the file without these keys.
4. Fresh scene, add the plugin, and with a `config.json` without `body.body_control`: **Body control** is on. Only Question and Answer switches it off.
5. Right column of every tab: only bold category headers, controls and the labels above the two input fields, no help or status text (the one caption "for pass-through transparency" under the color picker stays). Order as in `docs/SPEC.md` > Menu (e.g. AI Character: Body control, Idle poses, Idle motion and breathing with Breath morph right under Breath depth, Expression and gesture, Poses; Speech volume is in Voice > Voice and sound).
6. Left info field of every tab: the explanations read as running prose and every control name is **bold** (e.g. "**Breaths per minute** controls how fast the chest breathes"); the status lines (companion connection, test tone result, idle pose status, breath morph found / NOT found, errors in red) are there and short.

## T44 – Example scene thumbnail and AIBody on the female (version 37)

Historical for the v37 release name `AIBody_Example`. After 21.11.2026 the shipped scene is **AI-Buddy**; use T46 for a current build.

1. VaM > **Open Scene** / **Load Scene** > package `d0n.AIBody.37` > folder `AIBody` > **AIBody_Example**. The preview thumbnail of the two characters is visible in the scene list next to the name (the package has `Saves/scene/AIBody/AIBody_Example.jpg` beside the `.json`).
2. Load the scene: two people, no question about a missing package. Select the female atom `Person` > tab **Plugins**: AIBody of this package (`SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist` or the equivalent package path). The male atom `BryanGosling` has no AIBody plugin. Tab Config: **Set background color** is OFF unless you turned it on yourself.
3. Optional: copy the release assets `AIBody_Example.json` and `AIBody_Example.jpg` together to `Saves/scene/AIBody/` and open that copy from the browser; the same thumbnail and the same plugin load (the loose scene references `d0n.AIBody.37:/…`).

Report: screenshot of the Load Scene list with the thumbnail, and of the loaded scene with the plugin on `Person`.

## T45 – Character configuration wizard (after version 37)

1. Fresh scene, add AIBody to one Person. Tab **AI Character**: the first section is **Characters**, before **Body control**. The left info field asks **Do you want to configure your characters?** and names the buttons **Yes** and **No**. The companion console setup (first start or `--setup`) still only asks about the background and Scene / Plugin, not about characters.
2. Press **No**: the Yes / No buttons and the gender menus disappear; only **Configure characters** stays in that section. Reload the scene: it does not ask the question again. Press **Configure characters**: the question returns.
3. Press **Yes**: **AI gender/body** and **Your character gender** appear (Female / Male, nothing applied to the Person's figure) and a **Clothing** header with no clothing list. The left field says the choices are recorded for the AI and that clothing is set in VaM's own Clothing tab. Pick Female for the AI and Male for your character, save the scene, reload: the same choices are still selected. The Person's body and clothing in VaM are unchanged.
4. Optional: with the companion app connected, ask the AI how it sees the two characters; the answer should match the recorded genders.

Report: short note that the gate, the skip path and both gender menus behaved as above, and that clothing stayed a VaM Clothing-tab choice.

## T46 – AI-Buddy scene: original look, plugin, background, dependencies (version 38)

1. VaM > **Open Scene** / **Load Scene** > package `d0n.AIBody.44` > folder `AIBody` > **AI-Buddy**. The preview thumbnail of the two characters is visible in the scene list next to the name (the package has `Saves/scene/AIBody/AI-Buddy.jpg` beside the `.json`).
2. Load the scene. It should not hang. If a declared third-party package is missing, VaM should show a missing-package notice and still load. Two people with clothing: female `Person` in the Pro Court shorts and Nico tanktop, male `BryanGosling` in the police pants and hoodie (the hoodie is loose local content and may be missing). Select `Person` > tab **Plugins**: AIBody of this package (`SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist` or the equivalent package path). The male atom `BryanGosling` has no AIBody plugin and no Improved PoV. There are no Dollmaster atoms (`Doll SFX Person`, `Thrust AP Person`). Tab Config: **Set background color** is ON, color #00FF00, unless you changed it.
3. Optional: copy `AI-Buddy.json` and `AI-Buddy.jpg` together to `Saves/scene/AIBody/` and open that copy from the browser; the same thumbnail and the same plugin load (the loose scene references `d0n.AIBody.40:/…`).
4. Missing loose files listed in `docs/SCENE_GREENSCREEN.md` as needs local content (morphs, N3DX textures, tan-line decals, scamp THEV hair, PositiveResult hoodie, Bryan Gosling morph/face texture) should be skipped, not crash the load.

Report: screenshot of the Load Scene list with the thumbnail, of the loaded scene with clothing, and of the plugin on `Person` with Set background color on. Note any missing-package or missing-file messages.

## T47 – No Question and Answer button; Proactive talking only (version 39)

1. Load an older scene that has AIBody on a Person (for example one saved with version 38, or `AI-Buddy` from `d0n.AIBody.38`), then switch the plugin to version 39 (or load `AI-Buddy` from `d0n.AIBody.39`). The scene loads without a red `AIBody:` error line.
2. Tab **Voice** > section **AI**: there is no **Question and Answer** button. The section starts with **Use realtime voice**, then **AI mode** and the other controls; **Proactive talking** (on/off) and **Speech delay timer (s)** are still there.
3. The left info field explains in prose that there is no separate Question and Answer button and that with **Proactive talking** off the character only speaks when asked.
4. Switch **Proactive talking** off, ask a question (spoken or typed in the companion console): the character answers. Stay silent longer than **Speech delay timer (s)**: it does not start talking by itself.
5. Tab **AI Character**: **Body control** keeps the value you set; nothing in step 2-4 switched it off.

Report: screenshot of the Voice tab (AI section and left info field) and a short note on steps 1, 4 and 5.

## T48 – Character wizard asks its question (version 40)

1. Load **AI-Buddy** from `d0n.AIBody.44` (or a fresh scene with AIBody on a Person), even if you answered the wizard in an earlier scene. Tab **AI Character**: under **Characters** the line **Do you want to configure your characters?** stands right above **Yes** and **No**.
2. Press **Yes**: **AI gender/body** and **Your character gender** appear. Save the scene, reload it: the steps are shown again (the answer is saved with the scene). Load a different new scene with AIBody: the question is asked there again.
3. Press **No** in a scene: only **Configure characters** stays; it brings the question back.

Report: screenshot of the Characters section before and after Yes.

## T49 – Persona menu (version 40)

1. Install and start **AIBody Companion** (T51). Its first start writes `Saves/PluginData/AIBody/personas/Anna/persona.json` and `.../Marc/persona.json` (only if that folder had no persona yet).
2. VaM, plugin tab **Voice** > **Persona**: the menu lists **(none)**, **Anna**, **Marc**. Pick **Anna**: the left info field says the persona is in use after a moment, and the AI answers as Anna.
3. Quit AIBody Companion: the left field says the list comes from the running companion; the menu keeps the last list.

Report: screenshot of the open Persona menu and of the left info field.

## T50 – Quiet log while the companion is not running (version 40)

1. Quit AIBody Companion, load a scene with AIBody. The VaM log shows `AIBody: Companion app not connected: start 'AIBody Companion' from the Windows Start menu ...` once, no Python command, no error popup.
2. Tab **Voice** > **Test tone via companion** six times: the log has the "waits" line once; the left info field says one request is waiting. Start AIBody Companion: one test tone plays (not six).

Report: the AIBody lines of the VaM log.

## T51 – AIBody Companion installer (version 40, Windows)

1. Download `AIBody Companion Setup.exe` from the v41 release (v40 has the first installer), double-click. If SmartScreen shows "Windows protected your PC": **More info** > **Run anyway**. No admin prompt appears.
2. Leave **Create a desktop shortcut** and **Start with Windows** as you like, finish with **Launch AIBody Companion now** checked. A message box says AIBody Companion is now running in the background and stays until you click **OK** (since version 41; in v40 it closed by itself); the tray has its icon with **Quit**. No console window.
3. If your VaM folder is not found (the app looks at the remembered folder, a VaM folder around the app, and `X:\VaM`, `X:\Virt-A-Mate`, `X:\Games\VaM` ... on every drive), a folder picker asks once; choose the folder with `VaM.exe`. Start it again from the Start menu: only the "already running" message box appears; click **OK**.
4. Start VaM, load AI-Buddy: the plugin connects (tab Voice, left field: companion connected), the companion log is `<VaM>/Saves/PluginData/AIBody/logs/companion.log`.
5. Tray > **Quit**: the plugin reports the companion as not connected. Settings > Apps > AIBody Companion > Uninstall: the folder `%LOCALAPPDATA%\Programs\AIBody Companion` and the shortcuts are gone.

Report: screenshots of the note, the tray menu and the Voice tab; anything SmartScreen or an antivirus said.

## T52 – Installer asks for the VaM folder (version 41, Windows)

Use `AIBody Companion Setup.exe` of the v41 release.

1. Run the setup. After the options page comes **Your VaM folder**: the field already shows your VaM folder (the folder of the last setup, the remembered folder, or a VaM folder found on any drive, e.g. `D:\VaM`). If it is empty or wrong, click **Browse** and choose the folder with `VaM.exe`.
2. Choose a folder without `VaM.exe` (e.g. your Desktop) and click **Next**: a message says there is no VaM.exe in this folder and the page stays. Choose the right folder again: **Next** works.
3. Finish with **Launch AIBody Companion now**: no folder picker appears; the message box says the app runs in the background and waits for **OK**. `%LOCALAPPDATA%\AIBody Companion\launcher.json` contains your folder as `vam_root` and `"vam_root_set_by": "setup"`.
4. Run the setup again: the page shows the folder from step 1. Choose another VaM folder if you have one, finish, quit and start AIBody Companion from the Start menu: it uses the new folder (its log is under that folder's `Saves/PluginData/AIBody/logs/`).
5. Fallback: quit the app, rename the chosen VaM folder for a moment, start AIBody Companion: it looks for VaM itself and, if it finds nothing, asks once with its folder picker. Rename the folder back.

Report: screenshot of the **Your VaM folder** page and of the error message from step 2; the content of `launcher.json`.

## T53 – Reset to Default (version 41)

1. Load AI-Buddy. Change a few settings in different tabs: tab Voice **Voice** = rex, **Proactive talking** off; tab Client Character **Mic mode** = Push-to-talk; tab AI Character: answer the wizard with **Yes** and choose **AI gender/body**; tab Config **Verbose log** on, **Set background color** off.
2. Tab Config: below **Background** is the header **Reset** with the button **Reset to Default**. The left info field explains what it resets and what it keeps. Press it: instead of it there are **Confirm Reset to Default** and **Cancel**, and the left field says the reset waits for your confirmation. Press **Cancel**: nothing changed, the left field says so.
3. Press **Reset to Default**, switch to another tab and back: the plain **Reset to Default** button is shown again (switching tabs cancels). Press it and then **Confirm Reset to Default**: the left field says how many settings went back to their defaults. Check: Voice = eve, Proactive talking on, Mic mode = Voice activation, Verbose log off, Set background color off (the color is back to #00FF00); tab AI Character asks **Do you want to configure your characters?** again with **Yes** / **No**.
4. The **XAI API Token** still works (the AI answers; tab Voice shows the masked token), the **xAI key file** path and the pose commands are unchanged. `Saves/PluginData/AIBody/config.json` still has `ai.xai.api_key` and the reset values (e.g. `"voice": "eve"`).
5. Save the scene under a new name and reload it: the reset values are kept.

Report: screenshots of the Config tab before and after pressing **Reset to Default**, and of the AI Character tab after the reset; any red `AIBody:` log line.

## T54 – AI-Buddy: AIBody on the male BryanGosling (version 41)

Use `d0n.AIBody.41.var`.

1. Load **AI-Buddy**. Select the male atom `BryanGosling` > tab **Plugins**: AIBody (`SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist`) is there; its tab Config shows **Set background color** on with #00FF00, and the background is green.
2. Select the female atom `Person` > tab **Plugins**: no AIBody plugin.
3. Talk to the character: the male's voice comes from his head audio (T55), his expressions and idle motion move. Clothing, hair and looks of both people are as before.

Report: screenshots of both Plugins tabs; anything that looks different from the v40 scene apart from the plugin.

## T55 – Speech audio: loaded before play, [audio] debug lines (version 41)

Audio never played in any version (companion.log: "did not start playing within 15 s" for every sentence and the test tone). Version 41 waits until the WAV's audio data is loaded (`loadState` Loaded, `LoadAudioData()` when needed) and only then plays it on the head audio with the calls of known working plugins.

1. Load AI-Buddy with the companion running. Tab Config > **Logging**: **Verbose log** on.
2. Tab Voice > **Voice and sound**: **Play test tone** (the plugin's own WAV), then **Test tone via companion** (a WAV the companion writes). Each time you should hear the short tone from the male's head within about a second.
3. Open VaM's log (the message log / `output_log.txt`) and copy every line with `AIBody: [audio]`: "head audio of 'BryanGosling': HeadAudioSource found", per sound a `QueueClip(...)` line (or "clip already loaded, reused"), lines with the clip's `loadState` (Unloaded / Loading / Loaded), one "PlayNowClearQueue (try 1)" line and a "playing" line (clip length, number of play calls, time to start).
4. Ask the AI something: each sentence is spoken; each one has its own `[audio]` lines.
5. If nothing is heard: copy the `[audio]` lines and the red `AIBody:` lines (they now say whether the clip never loaded, failed to decode, or loaded but the head audio did not start, and what it showed: enabled, active, volume, the clip it was playing). Also check that **Freeze Motion/Sound** in VaM's top menu is off.

Report: the `[audio]` lines of the test tone and of one answer, heard yes/no.

## T56 – Voice: all xAI voices (version 41)

1. Tab Voice > **Voice and sound** > **Voice**: the list has the 28 built-in xAI voices (carina, zagan, helix, orion, luna, iris, altair, zenith, perseus, helios, lux, kepler, rigel, cosmo, celeste, ursa, sirius, lumen, castor, naksh, atlas, aurora, liora, ara, eve, leo, rex, sal), before the companion is connected too.
2. With the companion connected and a working XAI API Token, wait a few seconds: the companion asks xAI for its current list (`GET /v1/tts/voices`) and the menu shows that list (companion.log: "Voices: N from xAI /tts/voices"). Without network it says the static list stays.
3. Choose e.g. **luna** and ask something: the answer is spoken with that voice (after T55 works). A persona with its own voice still overrides the menu.

Report: screenshot of the open Voice menu; the "Voices:" line of companion.log.

## T57 – Pose commands: Apply pose command, Add Pose (version 41)

1. Tab AI Character > **Poses**: under **Pose command** is the new button **Apply pose command**. Choose a command (e.g. "sit") and press it: the character takes that pose; the left field says "Pose command applied: 'sit' -> <pose>" and VaM's log has the same line. Choosing in the menu alone only selects (with **Verbose log** a debug line says so).
2. Choose a command whose pose this character does not have (the left field marks it UNAVAILABLE): **Apply pose command** shows a red reason in the left field and a warning in VaM's log.
3. Choose a pose in **Pose**, leave **New pose command** empty and press **Add Pose**: the pose name becomes a new pose command and is chosen in **Pose command**. With text typed in, that text becomes the command. Close and reopen the plugin UI: the entries are still there (config.json `poses.commands`).
4. **Pose** + **Apply pose** still work as before.

Report: the left-field lines and VaM log lines of steps 1-3.

## T58 – No spoken "tool_call" text (version 41)

companion.log of 21.11.2026 showed the model sometimes writes its expression call as text (`<tool_call>{"name": "express", ...}</tool_call>`), which was sent to the voice. Version 41 runs such a block as the expression / gesture and never speaks it.

1. Talk for a few minutes (English and German). companion.log: no `Say (...)` line contains `tool_call`; when the model does it, the log says "The model wrote a tool call into its text (express); it is run, not spoken".

Report: any `Say` line with `<`, `{` or `tool_call`.

## T59 – Pose command applies on choosing, Add Pose with the file browser (version 42)

Use `d0n.AIBody.42.var` and load **AI-Buddy from the package `d0n.AIBody.42`** (not a scene saved with an older version: a scene names its plugin package, and an old one keeps loading the old plugin).

1. Tab AI Character > **Poses**: the order is **Pose command**, **Add Pose**, **Delete Pose**, **Reset poses**, **Restore starter poses**, **Reload poses**. There is no **Pose** dropdown, no **Apply pose** and no **Apply pose command**.
2. Choose a command in **Pose command** (e.g. "Sit Down"): `AI` takes the pose at once; the left field starts with "Last action: Pose command ..." and VaM's log has the same line. A command marked UNAVAILABLE gives a red reason instead.
3. **Add Pose**: VaM's file browser opens in `Custom/Atom/Person/Pose`. Choose a pose file: the label **New pose command** and a field appear, prefilled with the file name, with **Save pose command** and **Cancel Add Pose**. Type e.g. "wave hello" and press **Save pose command**: the command is in **Pose command**; choosing it applies that file.
4. Reload the scene: "wave hello" is still there (`config.json` > `poses.commands`).

Report: screenshot of the Poses section; the left-field and log lines of steps 2-3; whether the file browser opened.

## T60 – Delete Pose (version 42)

1. Choose "wave hello" in **Pose command**, press **Delete Pose**: it is gone from the menu.
2. Reload the scene: still gone. **Restore starter poses** brings back deleted starters only.

## T61 – Reset poses: AI first, then Client (version 42)

1. Load AI-Buddy, wait 2 s. Pose `AI` (a pose command) and drag `Client` a bit.
2. **Reset poses**: `AI` jumps back to where the scene placed it; about half a second later `Client` does too. They do not collide. The left field says "Reset poses: 'AI' back to the scene placement (N controllers), then 'Client' in 0.5 s."

Report: did both go back, in that order?

## T62 – AI-Buddy: AIBody on Client drives AI; version check (version 42)

1. Load **AI-Buddy** from `d0n.AIBody.42`. Select `Client` > tab **Plugins**: AIBody (`SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist`); the info field starts with "AIBody 42 on 'Client', AI person 'AI'"; tab Config: **Set background color** on, #00FF00, green background. `AI` > tab **Plugins**: no AIBody.
2. Talk: the voice comes from `AI`'s head, `AI`'s expressions, idle motion, breathing and poses move; `Client` stays still.
3. companion.log: "AIBody plugin ready on 'Client': plugin=42". Then load one of your own scenes saved with version 40 or 41: the companion log and the plugin's status line say "The AIBody plugin in VaM is version 40, the companion app is version 42 ...".

Report: screenshots; the "plugin ready" lines.

## T63 – Speech audio in VaM, first real run of the v41 fix (version 42)

Leon's v41 test ran the v40 plugin (every log line said plugin=40), so the v41 audio code has never run in VaM. Repeat T55 with the v42 scene of step T62.1 and **Verbose log** on, then copy every `AIBody: [audio]` line from VaM's own log (`output_log.txt` / message log; they are not in companion.log).

Report: heard yes/no for **Play test tone**, **Test tone via companion** and one answer; the `[audio]` lines.

## T64 – Voice menu shows all voices (version 42)

1. Tab Voice > **Voice and sound** > **Voice**: the open menu scrolls; all 28 voices can be reached (e.g. the last ones alphabetically).
2. companion.log: "Voices: 28 from xAI /tts/voices". With the companion stopped the menu still offers the 28 docs.x.ai voices.

Report: screenshot of the scrolled menu.

## T65 – Louder test tone (version 43)

1. Tab Voice > **Voice and sound**: **Play test tone** and **Test tone via companion**, Speech volume as before. Both tones are clearly louder than in v42 (about twice the level) and not distorted.

Report: louder yes/no, distorted yes/no.

## T66 – Update notice of AIBody Companion (version 43, Windows)

1. With v43 installed and online, start AIBody Companion: after **OK** on "running in the background" no further box appears (v43 is the newest). `%LOCALAPPDATA%\AIBody Companion\launcher.log` has a line "update check: nothing newer (or offline)".
2. When a newer release exists (v44 or later), a box "A newer AIBody is available: version 44 ..." asks to open the release page; **Yes** opens it in the browser, **No** closes it.
3. Offline (network off): no box, no error; the app runs as usual.
4. Optional: `"update_check": false` in `launcher.json` switches the check off (log line "update check: off").

Report: the launcher.log lines of steps 1 and 3.

## T67 – Uninstall also removes the AIBody packages (version 43, Windows)

1. Settings > Apps > **AIBody Companion** > Uninstall (or Start menu > Uninstall AIBody Companion). Close VaM first.
2. `<VaM>\AddonPackages`: every `d0n.AIBody.<number>.var` directly in that folder is gone; other packages (also `d0n.AIBodySession.*` or VARs in subfolders) are still there. Install v43 again afterwards (VAR + Setup.exe) to continue testing.

Report: the list of `d0n.*` files in AddonPackages before and after.

## T68 – speech_ended "completed" (version 43)

1. **Test tone via companion**, then ask the AI something. companion.log: each `speech_ended` line says `reason='completed'` (v42 said `interrupted` for every clip).
2. Talk while the AI speaks (barge-in, headphones) or press **Stop speaking**: that clip ends with `interrupted` or `stopped`.

Report: the speech_ended lines.

## T69 – Installer of v43 (version 43, Windows)

Leon reported "the v42 installer no longer works" without details. Run `AIBody Companion Setup.exe` of v43 and note exactly what happens: SmartScreen (**More info** > **Run anyway**), each wizard page, any message text, whether AIBody Companion starts afterwards. If it fails, send the setup log and `%LOCALAPPDATA%\AIBody Companion\launcher.log`.

Correction (version 44): the v43 setup writes no log by itself. Start it from a command prompt with `"AIBody Companion Setup.exe" /LOG="%USERPROFILE%\Desktop\aibody-setup.log"` and send that file. Since v44 every setup run writes `%TEMP%\Setup Log <date> #<n>.txt` (`SetupLogging=yes`); send the newest one. Found cause of the v42/v43 failures: see T72.

## T70 – The setup installs the package and removes older ones (version 44, Windows)

1. In `<VaM>\AddonPackages` put an old `d0n.AIBody.42.var` (or keep your hand-copied one) and note the other packages there.
2. Run `AIBody Companion Setup.exe` of v44. Page **Select Additional Tasks**: **Remove older AIBody packages (d0n.AIBody.<number>.var) from AddonPackages** is checked (since v45 there is no such option, see T74). Page **Your VaM folder**: your VaM folder (e.g. `D:\VaM`). Finish.
3. `<VaM>\AddonPackages` now has `d0n.AIBody.44.var` (about 180 kB) and no other `d0n.AIBody.<number>.var`; every other package (also `d0n.AIBodySession.*`, VARs in subfolders) is still there.
4. Repeat with the option unchecked: the older packages stay, `d0n.AIBody.44.var` is copied anyway. (v44 only; v45 has no option.)
5. VaM (restart or **Rescan Add-on Packages**): **AI-Buddy** in package `d0n.AIBody.44` loads.
Report: the file list of AddonPackages before / after, and the lines `Existing install`, `Remove older AIBody packages`, `Deleted`, `Package:` of `%TEMP%\Setup Log <date> #<n>.txt`.

## T71 – Messages about an existing install (version 44, Windows)

1. With v43 installed, run the v44 setup: first a box **Update from AIBody 43 to 44.** with what it will do (and the AIBody packages it found), **OK** continues, **Cancel** stops without changes.
2. Run the v44 setup again (v44 installed): box **AIBody 44 is already installed (AIBody Companion 44 and the package d0n.AIBody.44.var in AddonPackages).** with **OK: reinstall / repair** and **Cancel**. Cancel: the setup ends, nothing changed. OK: the setup runs through and replaces the files and the package.
3. Without a companion install but with `d0n.AIBody.44.var` copied by hand: the same "already installed" box names only the package.
Report: the exact box texts (screenshots) and which button you pressed.

## T72 – Setup over a running AIBody Companion (version 44, Windows)

Cause of "the installer no longer works" (v41-v43): the setup asked Windows' Restart Manager to close the running companion; its tray windows refused, so the "files in use" dialog came back after every **Continue** / **Retry** and nothing was installed.
1. Start AIBody Companion (tray icon visible), leave it running, run the v44 setup and click through.
2. The tray icon disappears during the install, no "close applications" loop, the setup finishes; with **Launch AIBody Companion now** the new version starts.
3. In the setup log: `Stop AIBody Companion: taskkill /F /T /IM "AIBody Companion.exe" exit code 0` (since v45 without `/T`: `taskkill /F /IM "AIBody Companion.exe" exit code 0`).
4. Optional: with the companion running, sign out of Windows: Windows no longer says AIBody Companion prevents it.
Report: whether any dialog came up, and the `Stop AIBody Companion` lines of the log.

## T73 – Speech volume above 1 (version 44)

1. Tab **Voice** > *Voice and sound*: **Speech volume** goes from 0 to 3; default 1 (an existing scene keeps its value).
2. At 1, **Play test tone** and **Test tone via companion** sound as in v43. At 2, then 3, both are clearly louder (plain gain, no limiter: at 3 the test tone may start to sound harsh, that is expected). Speakers and headset.
3. At 1.5, 2 and 3 let the AI talk (a long answer): the voice is clearly louder than at 1, at normal speaker volume; note from which value it distorts. companion.log: `Speech volume 2.00: speech WAVs x2.00 (linear gain)`.
4. Back to 0.5: quieter than 1 (VaM's head audio), companion.log `unchanged`.
Report: the loudest setting that still sounds clean on speakers and on the headset.

## T74 – The package is placed even after a failed setup run (version 45, Windows)

Leon's v44 test (21:25): the v44 setup removed the old VAR, but `d0n.AIBody.44.var` never arrived. Cause: v44 deleted the older packages before copying; when the install then failed or was cancelled, Inno Setup's rollback removed the new package as well. Since v45 the older ones are removed only after the install succeeded and the new package is in place (SHA-256 checked), always (there is no option any more).
1. In `<VaM>\AddonPackages` put an old `d0n.AIBody.42.var` (and keep any other packages). Run the v45 setup. Page **Select Additional Tasks** shows only **Create a desktop shortcut** and **Start with Windows**.
2. Finish: `<VaM>\AddonPackages` has `d0n.AIBody.45.var` and no other `d0n.AIBody.<number>.var`; other packages untouched. Setup log: `Dest filename: D:\VaM\AddonPackages\d0n.AIBody.45.var`, then `Package: ... in place (SHA-256 checked)`, then `Remove older AIBody packages: found ...` and `Deleted ...`.
3. Put `d0n.AIBody.42.var` back, run the setup again and press **Cancel** on the page **Installing** while files are copied (or on the progress page as early as you can): `d0n.AIBody.42.var` is still there (with v44 it was gone and no package was left).
4. Start AIBody Companion **as administrator** (right-click > **Run as administrator**), then run the setup: on **Preparing to Install** it says **AIBody Companion is still running and could not be closed ... Nothing was changed.** and stops; AddonPackages unchanged. Quit the companion from the tray and run the setup again: it goes through.
Report: the AddonPackages file list after each step and the lines `Package:`, `Remove older`, `Deleted`, `Stop AIBody Companion`, `Rolling back` of `%TEMP%\Setup Log <date> #<n>.txt`.

## T75 – Speech loudness: Full volume distance and Speech volume (%) (version 46 only; the distance part is gone in version 47, see T76)

Cause of "too quiet / much quieter away from the head": VaM's head audio is a 3D sound that is turned down beyond its minimum distance (Unity's logarithmic rolloff), and a sound file cannot go above full scale, so Speech volume above about 150 % mostly adds distortion.
1. Load AI-Buddy, open tab **Voice** > *Voice and sound*: **Speech volume (%)** goes from 0 to 1000, default 100 (an older scene saved with Speech volume 1 shows 100, not 1). Below it there is **Full volume distance (m)**, default 2. The left field shows a line `Head audio: volume 1.00, full volume within 2.0 m`.
2. Desktop, normal camera distance (about 1.5-2.5 m from the face), Speech volume (%) 100: let the AI talk. The voice is clearly audible, much louder than with the previous version at the same distance.
3. Move the camera to about 4 m: quieter, but still audible. Raise **Full volume distance (m)** to 5: the voice is at full volume again there. Lower it to 0.3: the old behaviour (loud only right at the head).
4. Headset: stand about 0.5 m in front of the character: full volume. Compare with a Steam game at the same Windows volume and note the difference.
5. Speech volume (%) 100, 200, 300, 600, 1000 at the same place: companion.log shows `Speech volume 200 % (factor 2.00): ...` and `Speech level: peak ... dBFS before the gain, gain x2.00 -> ..., ...% of the samples cut at full scale` once per change. If it says the file is at its limit, higher values only make the voice harsher (no limiter: at 1000 % expect clear distortion). **Play test tone** above 300 % still plays the 3x copy.
6. Remove the plugin (or disable it): the head audio's distance goes back to what the scene had (VaM log: `Head audio of 'AI' before AIBody: volume ..., minDistance ... m, maxDistance ... m` shows the values it restores).
Report: from which distance the voice gets too quiet with the default 2 m, the `Head audio of ...` and `Speech level:` lines, and whether anything sounds distorted at 100 %. **Play test tone** at 200 % and 300 % plays the 2x / 3x copy (switch points 150 % and 250 %).

## T76 – v46 regression fixed: speech, sound like v45, body, Breath boxes, thumbnail (version 47, Leon 22.11.2026 12:17)

v46 wrote the head audio's "volume" / "minDistance" / "maxDistance" params before every clip and shipped the scene with minDistance 2; version 47 goes back to v45 there (only the head volume is set, scene minDistance 0.04, no "Full volume distance (m)" slider).
1. Install v47 with the setup, start AIBody Companion, then VaM; load **AI-Buddy** from `d0n.AIBody.47` (not a scene saved with v46: its head audio still has minDistance 2 – load the package scene or set it back by hand).
2. Tab **Voice** > *Voice and sound*: **Speech volume (%)** 100, no **Full volume distance (m)** below it. Say something: the AI answers with its voice (not the test tone). companion.log: `speak sent` followed by `plugin: speech_started` for every sentence, no `did not start playing within 15 s`.
3. Loudness: at 100 % the voice is as loud as in v45 at Speech volume 1 at the same camera distance; 200 % / 300 % louder like v45 at 2 / 3. Note if it is not like v45.
4. **Play test tone** still plays the tone (2x copy from 150 %, 3x from 250 %) and the next AI answer is speech again.
5. Idle head motion, Breathing (chest), an expression (tab AI Character > **Show expression**) and a pose (**Pose command** menu) work; let the AI talk for a minute: expressions/gestures come with its answers.
6. Tab **AI Character** > *Idle motion and breathing*: **Idle head motion**, **Idle intensity**, **Breathing**, **Breaths per minute**, **Breath depth**, then directly *Expression and gesture*: no "Breath morph" box and no "Breath1" box. Breathing still uses Breath1 (left field: "Breath morph: Breath1").
7. Main menu > Open Scene: AI-Buddy of `d0n.AIBody.47` shows its thumbnail (two characters in T-pose on black).
Report: companion.log and, if speech still fails, VaM's output_log.txt lines starting with `AIBody` (Verbose log on in tab Config for the `[audio]` lines).

## T77 – Full volume distance (m) back, EasyMoan way (version 48, Leon 22.11.2026 12:58)

Sound output: VaM plays on the Windows default output device that is active when VaM starts. With SteamVR / Oculus start the headset app first (or set the Windows sound output to the headset), then start VaM. companion.log shows `Windows default output device: ...` at start.
1. Install v48 with the setup, start AIBody Companion, then VaM; load **AI-Buddy** from `d0n.AIBody.48`. Tab **Voice** > *Voice and sound*: **Speech volume (%)** 100, **Full volume distance (m)** 3 (default; range 0.3–10).
2. Talk to the AI for a few turns: every answer is spoken (not only the test tone), like in v47. The left info field shows "Head audio: full volume within 3.0 m".
3. Stand 1–2 m from the AI's head (VR or the desktop camera): clearly louder than v47 at the same distance (v47 kept the scene's 0.04 m).
4. While the AI is speaking, move **Full volume distance (m)** to 1: the info field says "... applied as soon as the AI is not speaking"; the current sentence plays to the end and the next answers still start. After the speech it shows "full volume within 1.0 m" and the voice is quieter at 2 m. Set it back to 3 during a pause: applied at once.
5. Save the scene, reload it: the slider keeps its value; config.json has `body.full_volume_distance`.
6. Remove the AIBody plugin: the head audio's minDistance is the scene's value again (Client > Head audio, or save and look at `minDistance` 0.04).
Report: companion.log and VaM's output_log.txt lines starting with `AIBody` (the line "Head audio of ... before AIBody: minDistance ...").

## T78 – Voice barge-in on by default, chain and realtime, echo protection (main after v48, Leon 22.11.2026 call)

1. Fresh config (or tab Client Character): **Voice barge-in (headphones)** is ON; Mic mode voice activation. companion.log at start: "Voice barge-in: on, echo protection on ...".
2. Speakers, AI mode Chain (or Q&A): ask for a long story and stay silent: she tells it to the end (her own voice never interrupts her).
3. Talk over her clearly louder than her voice for about half a second: she stops at once (log "Voice barge-in: the user talks over the body - stopping it"), and your words get an answer (not the rest of the old story).
4. Same in AI mode Realtime; with Verbose log the log shows response.cancel and conversation.item.truncate.
5. With headphones: a normal voice is enough. Toggle off: talking over her does nothing; push-to-talk with "Push-to-talk interrupts speech" still stops her.
Report: companion.log, and whether a cough, laugh or loud sentence of hers interrupted her.

## T79 – Menu Language, German by default (main after v48, Leon 22.11.2026 call)

1. Tab **Voice**, AI section: **Language** under Persona shows **German (de)** in a new scene (a scene or config.json saved earlier with `auto` shows Auto: pick German once). The list scrolls: Auto, German, English, French, Spanish, Italian, Portuguese, ... (21 entries).
2. AI mode Chain or Q&A, persona Anna: talk German for a few minutes, also mix in a few English words: every answer is German, "die" is pronounced German, no English accent words (companion.log "Language: de" after a change).
3. Pick English (en): the next answers are English with an English voice; pick German again.
4. AI mode Realtime: same check; the session reconnects after a change (log "Realtime: connected").
5. Auto: the persona's language is used (Anna: de); a persona without a language falls back to detection per sentence.
Report: companion.log and the sentences that still sounded English.

## T80 – Setup notice without English button text (main after v48, Leon 22.11.2026 call)

1. Run the next setup over an installed AIBody: the box says **Update from AIBody <old> to <new>.** and what it will do, with no "OK: ... Cancel: ..." line; the buttons are Windows' own (OK / Abbrechen on German Windows). OK continues, Abbrechen stops without changes.
2. Run the same setup again: **AIBody <n> is already installed (...). Reinstall / repair it? ...** with the same two Windows buttons.
Report: screenshots of both boxes.

## T81 – Apply Pose button (main after v48, Leon 22.11.2026 call)

1. Tab **AI Character** > *Poses*: under **Pose command** there is a button **Apply Pose**.
2. Choose a command: the pose is applied at once (as before). Move the character a bit (or let an idle pose run), press **Apply Pose**: the same pose is applied again right away; the left field says "Last action: Pose command applied: ...".
3. **Apply Pose** with nothing chosen: red note "choose the command in Pose command first".

## T82 – Idle pose control: Apply idle default pose (main after v48, Leon 22.11.2026 call)

1. Tab **AI Character** > *Idle poses*: **Idle poses**, **Idle default pose**, then the new button **Apply idle default pose**, then the two wait sliders.
2. Choose a pose in **Idle default pose** and press **Apply idle default pose**: the character takes it at once ("Last action: Idle default pose applied: ..."), and the next idle pose comes only after the min wait.
3. A default pose the character does not have: red note, nothing moves.

## T83 – Body position (main after v48, Leon 22.11.2026 call)

1. Tab **AI Character**: under *Body control* the new section *Body position*: **Move forward / back (m)**, **Move right / left (m)**, **Turn (degrees)**, **Reset body position**.
2. Drag **Move forward / back (m)** to 0.5: the AI character moves half a metre the way she faces (whole body, no stretching); **Move right / left (m)** sideways; **Turn (degrees)** 90: she turns on the spot.
3. **Reset body position**: she is back where she was, the sliders show 0.
4. Move her, save the scene, reload: she stands at the new place and the sliders show 0 (they are not saved, so she is not moved twice).
5. After a move: idle head motion, breathing, a pose command and an idle pose still work.
Report: anything that stretched, fell or jumped back.

## T84 – Tab Dollmaster (main after v48, Leon 22.11.2026)

1. Load AI-Buddy. New tab **Dollmaster** between *Client Character* and *Config*. At the top **Activate** (off); below it the old Dollmaster menu (Test Emotion Trigger, Test Climax Trigger, Zero Pose Morphs, Enable Arousal, ... Enable Sound Effects). The other tabs show none of these controls.
2. With **Activate** off: no Dollmaster panel, no new atoms in the scene (no "Thrust AP", no "Doll SFX"), the AI speaks, breathes and moves as before.
3. Turn **Activate** on: after about a second the atoms "Thrust AP AI" and "Doll SFX AI" appear and the floating Dollmaster panel shows with VaM's main HUD, as in the old plugin (heart slider, Thrust Speed, Personality, Select Person, Undress, VAMasutra, Next Thruster, Minimize UI). The info field says Dollmaster owns the body; AIBody's idle motion / breathing / expressions / idle poses stop.
4. Move **Thrust Speed** up: moans of the chosen personality, arousal rises, face expressions and head follow, skin / insertion sounds play. **Test Climax Trigger**: climax voice and pose change. **VAMasutra** opens the pose browser on the shipped poses; a pose loads. **Undress** toggles the clothes. **Personality** switches the voice.
5. Talk to the AI while active: she answers with AIBody's voice; no Dollmaster moan starts while she speaks.
6. Turn **Activate** off: panel gone, "Doll SFX AI" and "Thrust AP AI" removed, blinking and eyes as before, AIBody's body control resumes. On again: everything comes back.
7. Change some Dollmaster sliders, save the scene, reload: the values and Activate are kept.
Report: any red line in the info field or the VaM log ("Dollmaster ..."), anything missing compared to the old Dollmaster.


## T85 – Reset to Default and a fresh config (version 50, Leon 22.11.2026 20:35)
1. Install v50, start AIBody Companion, then VaM; load AI-Buddy. Paste your xAI key into **XAI API Token** and check that the AI answers.
2. Tab Config > **Reset to Default** > **Confirm Reset to Default**. The status line says "The XAI API Token is cleared"; the token field is empty; in config.json `ai.xai.api_key` is `""`; companion.log only says "XAI API Token from the plugin field cleared" (never the token).
3. Tab Voice: **Language model** offers xai, ollama, echo; **Speech-to-text** offers xai, null; **Text-to-speech** offers xai, elevenlabs, tone; all three show **xai**. The lists are full even before the companion connects (start VaM without the companion).
4. **Persona** offers Anna and Marc (no "(none)"), Anna is chosen. **Memory** is checked.
5. Tab Client Character: **Mic enabled** and **Push-to-talk interrupts speech** are checked.
6. Paste the token again and speak: you are heard and answered with the xAI voice. Without a token the info field says the test engines run (no xAI API key).
7. Optional: close VaM and the companion, rename config.json, start again: the new config.json has the same defaults (engines xai, persona Anna, memory on, mic on).
Report: any menu with only one entry, any '(none)', a token left anywhere after the reset.

## T86 – Idle poses random of all poses, idle timer, dropdowns after Reset (version 51, Leon 22.11.2026 20:38-20:58)
1. Install v51, start AIBody Companion, then VaM; load AI-Buddy. Put three or more pose files into `Custom/Atom/Person/Pose/AIBody` (or have them in `Custom/Atom/Person/Pose`), press **Reload poses**.
2. Tab AI Character > Idle poses: the info field says "random pose of all N poses" with N = your pose files + gestures.json poses + the Idle default pose; **Idle pose min wait (s)** shows 30, **Idle pose max wait (s)** 300 (after a reset or in a new scene).
3. Set both sliders to 30 (type 30 into the value field). Stay silent for 5 minutes: the pose changes about every 30 s, to different poses (not only two), never the same pose twice in a row, and not back to the default pose every second time. Logging Verbose: the log shows `Idle pose: X (random of a pool of N poses)`.
4. Type 600 into min: max moves to 600 too; type 120 into max: min moves to 120. Type 18000 into max: the info field says "18000 s (300 min)". Values below 30 or above 18000 are not possible.
5. Speak during the wait: no change while you or the AI speak. Turn on Dollmaster: no idle pose change while it is active; turn it off: the idle poses go on.
6. Tab Config > **Reset to Default** > **Confirm Reset to Default**. Then open every dropdown of every tab (AI mode, Voice, Persona, Language, Speech-to-text, Language model, Text-to-speech, Mic mode, VAD engine, Idle default pose, Pose command, Expression, Gesture, AI gender/body, Your character gender): every one has its entries and a chosen value (the gender menus are empty until you answer, by design). The AI model field may be empty (expected).
Report: a dropdown without entries after the reset, the same pose twice in a row, only two poses alternating, a change while someone speaks or while Dollmaster is active.

## T87 – Pose commands, Apply Pose, no twitching (version 52, Leon 22.11.2026 20:47-20:48)
1. Install v52, start AIBody Companion, then VaM; load AI-Buddy. Have at least two pose presets (.vap) in `Custom/Atom/Person/Pose` or `.../AIBody`; tab AI Character > **Reload poses**. Link two commands with **Add Pose** (e.g. "Sit Down" and "Stand Up") if no file has the command's name.
2. Choose "Sit Down" in **Pose command**: nothing moves, the left field says "Pose command chosen ... press Apply Pose". Press **Apply Pose**: the AI person takes the pose fully, without twitching. Press it again: it is applied again. Choose "Stand Up", press **Apply Pose**.
3. The left field shows "Last pose load: pose '...': N controllers moved". Logging Verbose: the log says "Pose preset loaded once ... (Load On Select was on)". If it ever says "no controller moved" for a different pose, report the file name.
4. **Idle default pose**: choose an entry - nothing moves; **Apply idle default pose** applies it.
5. Say "Sit down." / "Stand up." (whole sentence): the pose changes; the companion status says "Pose command: ...".
6. Tab Dollmaster: Activate on, then press **Apply Pose**: a red note says Dollmaster is active. Activate off, then close VaM and start again (or Reload Config JSON): **Body control** is still on, and step 5 still works.
7. Idle head motion on: watch the head and chest for 2 s after each pose load: no jerk; the idle sway starts again after about 1 s.
Report: a pose that does not apply, any twitching, a pose applied by just choosing an entry, Body control off after using Dollmaster.

