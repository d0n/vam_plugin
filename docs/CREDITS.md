# Credits and special thanks

AIBody stands on the work of many people. This list names every plugin, author, library, service and
documentation that the project documents (`API_AUDIT.md`, `TECHNICAL.md`, `BACKLOG.md`, `LOCAL_ENGINES.md`,
`REMOTE.md`, `CONFIG.md`, `SCENE_GREENSCREEN.md`, `README.md`) as a source, with the links those documents give.
Nothing is listed that the documents do not mention. "Evidence" means: we read this code or page to learn how a
VaM interface works; we did not copy their code, and the evidence for each interface is in
[API_AUDIT.md](API_AUDIT.md) with the pinned commit. Not affiliated with any of them.

Thank you!

## VaM plugin authors (the main sources)

- **MacGruber**: the model for structure, operation and liveliness of a character. [Life](https://hub.virtamate.com/resources/life.165/), [LogicBricks](https://hub.virtamate.com/resources/logicbricks.1975/), [Benchmark](https://hub.virtamate.com/resources/benchmark.11336/), [Utils](https://hub.virtamate.com/resources/macgruber-utils.40744/). Evidence for eyes, gaze and breathing (the pieces of Life in the vam-community package list): [Eyes 0.1.0](https://github.com/vam-community/vam-packages/blob/17e36f5cccc1f898f6b7a6e7d5e72b91471ed2ea/Custom/Scripts/MacGruber/macgruber-eyes/0.1.0/MacGruber_Eyes.cs), [Gaze 1.1.0](https://github.com/vam-community/vam-packages/blob/17e36f5cccc1f898f6b7a6e7d5e72b91471ed2ea/Custom/Scripts/MacGruber/macgruber-gaze/1.1.0/MacGruber_Gaze.cs), [Breathe 1.0.0](https://github.com/vam-community/vam-packages/blob/17e36f5cccc1f898f6b7a6e7d5e72b91471ed2ea/Custom/Scripts/MacGruber/macgruber-breathe/1.0.0/Breathe.cs). Life can run on the same character (the *Life* detection in the gaze and blinking code).
- **Acid Bubbles**: [Timeline](https://github.com/acidbubbles/vam-timeline) ([Hub](https://hub.virtamate.com/resources/timeline.94/), [wiki](https://hub.virtamate.com/resources/timeline-3-wiki.860/); gestures through `Play <animation>`, storables, file access, UI patterns), [Glance](https://github.com/acidbubbles/vam-glance) ([Hub](https://hub.virtamate.com/resources/glance-realistic-head-driven-eye-motion.5461/); eye control), [Embody](https://github.com/acidbubbles/vam-embody) (eye targets, menu patterns), [Scripter](https://github.com/acidbubbles/vam-scripter) (`FileManagerSecure` usage, storable references), [Keybindings](https://github.com/acidbubbles/vam-keybindings) (per-plugin data folder), [Collider Editor](https://github.com/acidbubbles/vam-collider-editor) (scrollable popups, chooser refresh), [Improved PoV](https://github.com/acidbubbles/vam-improved-pov) and [Leap Possess](https://github.com/acidbubbles/vam-leap-possess) (scene files saved by VaM), and [Dev Tools](https://github.com/acidbubbles/vam-devtools) (code to study).
- **VAMDeluxe**: [DeluxePlugin](https://github.com/vamdeluxe/DeluxePlugin): Dollmaster (head audio source, queueing and playing clips, plugin folder lookup, UI), Qualia Breathing, HeadIdle, PresetRandomizer (loading presets through the preset storable: `presetBrowsePath` + `LoadPreset`, the base of our pose loading) and the CycleForce plugin template.
- **everlaster**: [TittyMagic](https://github.com/everlasterVR/TittyMagic) (morph lookup, slider labels) and [Extraltodeus ExpressionRND / ExpressionRandomizer](https://github.com/everlasterVR/Extraltodeus-ExpressionRND).
- **Yoooi**: [ToySerialController](https://github.com/Yoooi0/ToySerialController): the editable text field (`UITextInput`) used for the XAI API Token, Breath morph and the new pose command field.
- **lfe999**: [VamFreeMMD](https://github.com/lfe999/VamFreeMMD) (head audio playback) and [VamHeightPlugin](https://github.com/lfe999/VamHeightPlugin) (rebuilding a settings page).
- **sFisherE**: [mmd2timeline](https://github.com/sFisherE/mmd2timeline) (the same head-audio pattern as FreeMMD).
- **emptyngton**: [FootstepsExtended](https://github.com/emptyngton/FootstepsExtended) (sandboxed reading of WAV files below `Custom/Sounds`).
- **ZengineerVAM**: [VAMLaunch](https://github.com/ZengineerVAM/VAMLaunch): evidence for a UDP socket with a receive thread in a VaM plugin (the loopback link, version 30).
- **yuyaslabo**: [VaM_ML_Skeleton_Engine](https://github.com/yuyaslabo/VaM_ML_Skeleton_Engine) (AIVRLab.BoneReceiver): a Python engine talking to a VaM plugin over UDP.
- **SPQR_aeternum**: [Neptune API](https://www.patreon.com/SPQR_aeternum/posts/neptune-api-v1-145203754): a plugin with a local listener (network evidence).
- **Voxta**: [Voxta VaM integration](https://doc.voxta.ai/docs/integrations/vam) ([plugin install guide](https://doc.voxta.ai/docs/integrations/vam/basics/install-plugin)): the thin-client-in-VaM design, state triggers, echo handling, and the "Allow Plugins Network Access" requirement.
- **StyleMavin**: [VoiceControl2](https://github.com/StyleMavin/VoiceControl2) and [VoskCompanion](https://github.com/StyleMavin/VoskCompanion): a plugin talking to an external speech app.
- **OnePunchVAM**: [vam-story-builder](https://github.com/OnePunchVAM/vam-story-builder), **RobQuistNL**: [ml-clone-test](https://github.com/RobQuistNL/ml-clone-test), **ChrisTopherTa54321**: [foto2vam](https://github.com/ChrisTopherTa54321/foto2vam): scene file format (`geometry.character`, `PluginManager`, colors).
- **rutheniumm**: a [gist embedding MacGruber_Utils' `EventTrigger`](https://gist.github.com/rutheniumm/c201dd5e6b2bbf56c548ec80ff4546b9) (evidence for trigger objects, not used).
- **Sally**: *Camera Background Color* ([Hub](https://hub.virtamate.com/resources/camera-background-color.24185/), [Patreon mirror, CC0](https://www.patreon.com/posts/vam-camera-color-73037813)), used in the bundled green screen scene.
- Mentioned in `TECHNICAL.md` / `BACKLOG.md` as plugins to use next to AIBody or as references (no code taken): **VRAdultFun** E-Motion, **everlaster** Naturalis, SpeechRecognition (VaM Hub), [VAMStory](https://hub.virtamate.com/resources/vamstory.28256/).
- Preset format evidence (version 31, `API_AUDIT.md`): the VaM Hub plugin *PresetLoader* and the *vam-backstage* classifier, the script of **BoominBobbyBo** (iHV), and the instructions of *Timeline* and *CircleLooks*. The documents give no links for these.

## Virt-A-Mate and its documentation

- **Meshed VR** (VaM): [official patch notes](https://cdn.virtamate.com/Release/VaM_PatchNotes.html), the [`FileManagerSecure` API documentation](https://apidoc.virtamate.com/api/MVR.FileManagementSecure.FileManagerSecure.html) and the [security patch notice](https://www.patreon.com/meshedvr/posts/important-patch-121741619) (Allow Plugins Network Access).
- [VaM Japan glossary: Scene Audio](https://vamjapan.com/glossary/scene-audio/) (user documentation for audio).
- Unity: the standard `UnityEngine.UI.InputField`, `UnityEngine` math and VaM's `SimpleJSON` as used by the plugins above (API_AUDIT names them without a link).
- Green screen and passthrough notes in `SCENE_GREENSCREEN.md`: the Hub thread [VD for passthrough](https://hub.virtamate.com/threads/vd-for-passthrough.43272/post-135631), the Hub guide [How to use Passthrough in VAM](https://hub.virtamate.com/resources/how-to-use-passthrough-in-vam-vr-mixed-reality.37851/) (thinoreos; listed, not read), and [VaM desktop chroma passthrough](https://vamhub.net/resource/vam-desktop-chroma-passthrough-vamtual-girl-63459).

## Services, models and libraries (companion app)

- **xAI**: the speech-to-text, text-to-speech, Responses and realtime voice APIs ([speech to text](https://docs.x.ai/developers/model-capabilities/audio/speech-to-text), [text to speech](https://docs.x.ai/developers/model-capabilities/audio/text-to-speech), [speech to speech](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech), [voice reference](https://docs.x.ai/developers/rest-api-reference/inference/voice), [Responses reference](https://docs.x.ai/developers/rest-api-reference/inference/responses); API keys at [console.x.ai](https://console.x.ai)).
- **ElevenLabs**: the optional text-to-speech service ([API](https://api.elevenlabs.io/v1)).
- **Ollama**: [local language models](https://ollama.com) (`ai.ollama`, version 29).
- **Silero VAD** ([snakers4/silero-vad](https://github.com/snakers4/silero-vad/tree/master/src/silero_vad/data), MIT license, model `silero_vad.onnx`) with **onnxruntime**: optional voice activity detection.
- **webrtcvad** (installed as `webrtcvad-wheels`): optional WebRTC voice activity detection.
- **sounddevice**: microphone recording.
- **faster-whisper**, **Piper**, **Vosk**, **XTTS**: named in `BACKLOG.md` / `LOCAL_ENGINES.md` as candidates for local engines; not implemented, not used.
- Python and its standard library (HTTP server, sockets, `unittest`): the companion app has no other required dependency.
