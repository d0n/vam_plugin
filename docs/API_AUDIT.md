# VaM API audit (AIBody 0.6.1, extended for 0.6.3 and 0.7.0)

Rule: the plugin uses only VaM 1.22 APIs that the official VaM notes or established, working
plugins show in use inside the plugin sandbox. **Anything without such visible evidence is
removed, never worked around.** Not allowed at all: network code of any kind
(`UnityEngine.Networking`, `UnityWebRequest`, `WWW`, sockets), `System.IO`, `System.Net`,
`Process` / `System.Diagnostics`, reflection, `Assembly.Load`, native libraries (`DllImport`), the
Unity microphone API, `Application.OpenURL`.

Enforcement:

- `tools/check_plugin.py` scans the full text of every file below `src/` and of the assembled
  plugin folder (`tools/sandbox_rules.py`): zero matches required, comments included.
- `tools/build_var.py` scans every file inside the built `.var` with the same rules and deletes
  the package on any match.
- The compile stubs `tools/stubs/VaMStubs.cs` / `UnityStubs.cs` declare only the members listed
  here (each tagged with its evidence key), so a new, unaudited VaM API fails the compile check.

## Evidence (pinned commits)

| key | source | what it shows |
|-----|--------|---------------|
| E1  | [Dollmaster.cs](https://github.com/vamdeluxe/DeluxePlugin/blob/e606e780e79af214b2b4be0a53b1e7b45ecf59b7/Dollmaster/src/Dollmaster.cs) (VAMDeluxe) | `GetStorableByID("HeadAudioSource") as AudioSourceControl` (L60), `PlayNow(clip)` (L246), `QueueClip(SuperController.singleton.NormalizeMediaPath(path))` + `GetClip(clip.uid)` (L296-308), `CreateButton` (L124), `RegisterAction` (L122), `storeId` (L286) |
| E2  | [SFXController.cs](https://github.com/vamdeluxe/DeluxePlugin/blob/e606e780e79af214b2b4be0a53b1e7b45ecf59b7/Dollmaster/src/SFXController.cs) (VAMDeluxe) | `AudioSourceControl.volume` (L116, L121), `PlayNow` (L117, L122), `URLAudioClipManager.singleton.RemoveClip(clip)` (L150), `currentRotationState` / `FreeControllerV3.RotationState` (L36) |
| E3  | [FreeMMD.cs](https://github.com/lfe999/VamFreeMMD/blob/e90be09c06a3ca40962ff6aac3a1a36c7bfbe010/src/FreeMMD.cs) (lfe999); same pattern in [mmd2timeline AudioClipHelper.cs](https://github.com/sFisherE/mmd2timeline/blob/1d22f6de2eb076a56768830eb44f5f9a5ce1d78d/src/Player/Audio/AudioClipHelper.cs) | `headAudioSource.audioSource` (L54), `headAudioSource.Stop()` (L155), `QueueClip(NormalizeMediaPath(path))` (L325), `CreateButton` (L221) |
| E4  | [Qualia Breathing.cs](https://github.com/vamdeluxe/DeluxePlugin/blob/e606e780e79af214b2b4be0a53b1e7b45ecf59b7/Qualia/src/Breathing.cs) (VAMDeluxe) | `GetStorableByID("geometry")` as `DAZCharacterSelector`, `morphsControlUI`, `GetMorphByDisplayName("Breath1")` (L20-23), `morphValue` (L45), `RegisterFloat` (L29) |
| E5  | [TittyMagic Utils.cs](https://github.com/everlasterVR/TittyMagic/blob/eca6d093450994cf589e51e148ceaadf9adfbc79/src/Utils/Utils.cs) (everlaster) | `morphsControlUI.GetMorphByUid(uid)` (L65) |
| E6  | [HeadIdle.cs](https://github.com/vamdeluxe/DeluxePlugin/blob/e606e780e79af214b2b4be0a53b1e7b45ecf59b7/HeadIdle/HeadIdle.cs) (VAMDeluxe) | `GetStorableByID("headControl") as FreeControllerV3` (L31), rotating `headControl.transform` (L35, L45) |
| E7  | [PresetRandomizer.cs](https://github.com/vamdeluxe/DeluxePlugin/blob/e606e780e79af214b2b4be0a53b1e7b45ecf59b7/PresetRandomizer/PresetRandomizer.cs) (VAMDeluxe) | preset loading: `GetStorableByID(presetType)`, `GetUrlJSONParam("presetBrowsePath")`, `.val = SuperController.singleton.NormalizePath(path)`, `CallAction("LoadPreset")` (L58-66) |
| E8  | [vam-timeline ControllerPlugin.cs](https://github.com/acidbubbles/vam-timeline/blob/54e294256d7b73ec7d00d4216fcc7f01bc9d8133/src/ControllerPlugin.cs) (Acid Bubbles) | `atom.GetStorableIDs()` + `EndsWith("VamTimeline.AtomPlugin")` (L196), `storable.CallAction($"Play {animationName}")` (L548) |
| E9  | [vam-timeline AtomPlugin.cs](https://github.com/acidbubbles/vam-timeline/blob/54e294256d7b73ec7d00d4216fcc7f01bc9d8133/src/AtomPlugin.cs) (Acid Bubbles) | registers the `Play <name>` actions (L1024), `RegisterStringChooser` (L310), `RegisterAction` (L321), `RegisterBool` (L400), `RegisterString` (L493), `chooser.choices = ...` (L874), `SuperController.LogError` (L118) |
| E10 | [vam-timeline TimelineDefaults.cs](https://github.com/acidbubbles/vam-timeline/blob/54e294256d7b73ec7d00d4216fcc7f01bc9d8133/src/AtomAnimations/Editing/TimelineDefaults.cs) | `FileManagerSecure.FileExists` (L16), `CreateDirectory` (L21), `DeleteFile` (L67) |
| E11 | [vam-scripter Scripter.cs](https://github.com/acidbubbles/vam-scripter/blob/96674ce01a3ca1e8d5eaebceccf047f14de69394/Scripter.Plugin/src/Scripter.cs) (Acid Bubbles) | `FileManagerSecure.CreateDirectory` (L295), `GetFiles(folder)` without a pattern (L296), `ReadAllText` on the returned paths (L302), `WriteAllText` (L334) |
| E12 | [vam-glance Glance.cs](https://github.com/acidbubbles/vam-glance/blob/dae3c96d06f67a8ca7155ac4d6622a3434d8b013/Glance.cs) (Acid Bubbles) | `containingAtom.type != "Person"` (L149), `JSONStorableAction` (L142), `LogError` (L151), `GetBoolJSONParam` (L182, L843), `GetFloatJSONParam` (L848), `CreateToggle` (L191), `CreateTextField` (L194), `CreateSlider` (L213) |
| E13 | vam-scripter [StringParamReference.cs](https://github.com/acidbubbles/vam-scripter/blob/96674ce01a3ca1e8d5eaebceccf047f14de69394/Scripter.Plugin/src/Module/StorableParams/StringParamReference.cs), [StringChooserParamReference.cs](https://github.com/acidbubbles/vam-scripter/blob/96674ce01a3ca1e8d5eaebceccf047f14de69394/Scripter.Plugin/src/Module/StorableParams/StringChooserParamReference.cs) | `GetStringJSONParam` (L17), `GetStringChooserJSONParam` (L18) on another storable |
| E14 | [ToySerialController UITextInput.cs](https://github.com/Yoooi0/ToySerialController/blob/8aefbbd2dc3e9701bcf7d1010f6fd9b2bb7a5c83/src/UI/Control/UITextInput.cs) (Yoooi) | editable text field: `textField.gameObject.AddComponent<InputField>()`, `input.textComponent = textField.UItext`, `storable.inputField = input` (L44-47) |
| E15 | [Official VaM patch notes](https://cdn.virtamate.com/Release/VaM_PatchNotes.html) (MeshedVR) | `FileManagerSecure` is the file API for plugins (writes below `Saves/PluginData`); plugin network access is a user preference, off by default |
| E16 | [CycleForce.cs](https://github.com/vamdeluxe/DeluxePlugin/blob/e606e780e79af214b2b4be0a53b1e7b45ecf59b7/Templates/CycleForce.cs) (VaM plugin template, in DeluxePlugin) | `RegisterStringChooser` + `CreatePopup` (L85-86), `RegisterBool` + `CreateToggle` (L130-131) |
| E17 | [vam-embody CollapsibleSection.cs](https://github.com/acidbubbles/vam-embody/blob/e09e364f818b0389aa97d84c54ba5c65ad1183d6/src/Screens/CollapsibleSection.cs) (Acid Bubbles) | switching UI pages: `RemoveToggle` (L27), `RemoveSlider` (L30), `RemovePopup` (L36), `RemoveButton` (L40), `RemoveTextField` (L43), `RemoveSpacer` (L46) on controls it created with `CreateToggle/CreateSlider/CreateButton/CreateTextField` (L51-62) |
| E18 | [VamHeightPlugin UI.cs](https://github.com/lfe999/VamHeightPlugin/blob/dfc7781cb4f4038d503bec3d770cfccfcd1e4625/src/UI.cs) (lfe999) | rebuilding a settings page: `RemoveButton` (L1460), `RemoveToggle` (L1465), `RemoveSpacer` (L1470), `RemoveTextField` (L1473) |
| E19 | [vam-keybindings KeybindingsStorage.cs](https://github.com/acidbubbles/vam-keybindings/blob/6495ab5b623358c90a066b2faabfa27213f452dd/src/Keybindings/KeybindingsStorage.cs) (Acid Bubbles) | per-plugin data folder `Saves\PluginData\Keybindings` (L12) created with `FileManagerSecure.CreateDirectory` (L162, L206) |
| E20 | [Official API doc: FileManagerSecure](https://apidoc.virtamate.com/api/MVR.FileManagementSecure.FileManagerSecure.html) (MeshedVR) | `WriteAllText(path, text)`: "file creation is passed to user confirm/deny system for security reasons, so the file may not be immediately created" |
| E21 | [vam-improved-pov scenes/Empty.json](https://github.com/acidbubbles/vam-improved-pov/blob/dea857067da496e7e19ae5af31088fdc5fa6fb53/scenes/Empty.json) (Acid Bubbles, a scene saved by VaM) | VaM's SimpleJSON writes numbers and booleans as strings: `"x" : "355.9811"` (L4), `"useSceneLoadPosition" : "true"` (L8), `"on" : "true"` (L12). The companion app therefore accepts `"0.5"` / `"true"` for numbers / booleans in everything the plugin writes |
| E22 | [FootstepsExtended Footsteps.Audio.cs](https://github.com/emptyngton/FootstepsExtended/blob/cd38ce35546a9fa89d8b7b271a97ff652fff52b7/src/Footsteps.Audio.cs) (emptyngton) | audio below `Custom/Sounds/FootstepsSFX/` (L13); sandboxed `FileManagerSecure.GetFiles(dir, "*.wav")` (L98) and `ReadAllBytes` (L143) on those paths; it decodes with VaM's `NAudioPlayer` / `WAV` helpers instead of `URLAudioClipManager` |
| E23 | [VaM Japan glossary: Scene Audio](https://vamjapan.com/glossary/scene-audio/) (user documentation) | VaM's Scene Audio atom: **Browse** opens `Custom\Sounds` in the file browser; audio files to play are placed below that folder |
| E24 | [vam-collider-editor ColliderEditor.cs](https://github.com/acidbubbles/vam-collider-editor/blob/00d54b06d5aa579d42404684244aad821d35060f/src/ColliderEditor.cs) (Acid Bubbles) | `CreateScrollablePopup(jssc, rightSide)` (L359), `chooser.choices = ...` together with `chooser.displayChoices = ...` on a shown popup (L414-415, L448-449), `popupPanelHeight` (L283) |
| E25 | [vam-embody Embody.cs](https://github.com/acidbubbles/vam-embody/blob/e09e364f818b0389aa97d84c54ba5c65ad1183d6/src/Embody.cs) (L77, L950) and [vam-timeline SequencingScreen.cs](https://github.com/acidbubbles/vam-timeline/blob/54e294256d7b73ec7d00d4216fcc7f01bc9d8133/src/UI/Screens/SequencingScreen.cs) (L257-264, L500) (Acid Bubbles) | `chooser.popupOpenCallback = ...` refills `choices` when the menu opens; `choices = ...` on a popup that is on screen |
| E26 | [TittyMagic WindowBase.cs](https://github.com/everlasterVR/TittyMagic/blob/eca6d093450994cf589e51e148ceaadf9adfbc79/src/UI/WindowBase.cs) (everlaster, L46-48) and [ExpressionRandomizer.cs](https://github.com/everlasterVR/Extraltodeus-ExpressionRND/blob/cd6c9c584ce87c1a52e9e30c2e75310df89ccc71/src/ExpressionRandomizer.cs) (L582-583, L597-598) | `UIDynamicSlider slider = CreateSlider(jsf, rightSide); slider.label = "...";`: a shown slider label that differs from the storable name; also `sliderDynamic.label = name` in [Dollmaster UI.cs](https://github.com/vamdeluxe/DeluxePlugin/blob/e606e780e79af214b2b4be0a53b1e7b45ecf59b7/Dollmaster/src/UI.cs) (L74) |
| E27 | [vam-timeline AnimationsScreen.cs](https://github.com/acidbubbles/vam-timeline/blob/d6f7177c/src/UI/Screens/AnimationsScreen.cs) (`btn.buttonText.alignment = TextAnchor.MiddleLeft;`, `btn.label = ...`) and [vam-embody MainScreen.cs](https://github.com/acidbubbles/vam-embody/blob/e09e364f/src/Screens/MainScreen.cs) (`triggersBtn.buttonText.alignment = TextAnchor.MiddleLeft;`) (Acid Bubbles) | `UIDynamicButton.buttonText` (a `Text`) and its `alignment` (`TextAnchor`) on a button created with `CreateButton`; the shown button text is a plain string, so a `\n` makes a second line |
| E28 | [vam-embody EyeTargetModule.cs](https://github.com/acidbubbles/vam-embody/blob/e09e364f818b0389aa97d84c54ba5c65ad1183d6/src/EyeTarget/EyeTargetModule.cs) (Acid Bubbles); the Glance lines of E12 are re-read at the same pinned commit | `GetStorableByID("Eyes")` as `EyesControl` (L79); `freeControllers.First(fc => fc.name == "eyeTargetControl")` (L83); remember `currentLookMode` and `eyeTarget.control.position` (L108-109); set `currentLookMode = EyesControl.LookMode.Target` (L116); move the target every frame: `_eyeTarget.control.position = eyesCenter + _head.forward * distance` (L209), `= lockTarget.transform.position` (L195); restore position and, if the mode is still `Target`, the old look mode (L166-168); **coexistence precedent:** `GetStorableIDs().Any(id => id.EndsWith("Glance"))` makes Embody's eye module step aside (L88). Glance (E12): `GetStorableByID("Eyes")` (L159), `currentLookMode` get/set (L652, L681, L732), `freeControllers` + `name` (L164, L178), `eyeTarget.control.position` get/set (L678, L704), `SuperController.singleton.centerCameraTarget.transform` (L647), `SuperController.singleton.GetAtoms()` (L180, L759, L797), `atom.mainController.control` (L812, L957), `head.rotation * ... * Vector3.forward` (L1182), `Vector3.zero` (L988) |
| E29 | [MacGruber Eyes 0.1.0](https://github.com/vam-community/vam-packages/blob/17e36f5cccc1f898f6b7a6e7d5e72b91471ed2ea/Custom/Scripts/MacGruber/macgruber-eyes/0.1.0/MacGruber_Eyes.cs), [Gaze 1.1.0](https://github.com/vam-community/vam-packages/blob/17e36f5cccc1f898f6b7a6e7d5e72b91471ed2ea/Custom/Scripts/MacGruber/macgruber-gaze/1.1.0/MacGruber_Gaze.cs) and [Breathe 1.0.0](https://github.com/vam-community/vam-packages/blob/17e36f5cccc1f898f6b7a6e7d5e72b91471ed2ea/Custom/Scripts/MacGruber/macgruber-breathe/1.0.0/Breathe.cs) (MacGruber; the pieces of his Life plugin that are in the vam-community package list) | Eyes: `GetStorableByID("geometry")` as `DAZCharacterSelector`, `morphsControlUI.GetMorphByDisplayName("Eyes Closed")` (L34-38), `GetStorableByID("EyelidControl")` (L40) and `GetBoolJSONParam("blinkEnabled")` (L41), `autoBlink.val = true/false` (L59, L65), `eyesClosed.morphValue = Mathf.SmoothStep(prev, target, t)` (L53, L87). Class names for the coexistence check: `namespace MacGruber { public class Eyes : MVRScript` (Eyes L11-13), `class Gaze` (Gaze L14-16), `class Breathe` (Breathe L14-16); a plugin's storable id is `plugin#N_<namespace>.<class>` (same pattern as E8's Timeline match). Gaze L29-30 uses `headControl` and `eyeTargetControl` like E12 / E28 |
| E30 | [lfe999 VamAutoPupil AutoPupil.cs](https://github.com/lfe999/VamAutoPupil/blob/a223e7527bc754ee07d54d462bfef610065c5480/AutoPupil.cs) (lfe999, an MVRScript) | `CameraTarget.centerTarget.targetCamera` read in the sandbox (L191, L205); `Camera.clearFlags = CameraClearFlags.SolidColor` (L203) and `Camera.backgroundColor = Color.black` (L204) set on a Unity `Camera` from plugin code (there on its own detector camera; on VaM's view camera: TODO(verify)) |
| E31 | `SkyshopLightController.singleton` + `GetBoolJSONParam("showSkybox")`: Sally's Camera Background Color 7 (sandboxed .cs, read 17.11.2026, see docs/SCENE_GREENSCREEN.md) and [VPB GalleryPanel.CreatorMode.cs](https://github.com/gicstin/VPB/blob/77387fcb0580257bb2764e45127fcf82a595eb5c/src/gallery/GalleryPanel.CreatorMode.cs) (L513 `SkyshopLightController.singleton`, L519 `GetBoolJSONParam("showSkybox")`, `show.val = false`; GPL, read only, nothing copied) | hiding VaM's skybox so the camera's solid colour is visible |
| E32 | [DeluxePlugin TemplateWithSamples.cs](https://github.com/vamdeluxe/DeluxePlugin/blob/e606e780e79af214b2b4be0a53b1e7b45ecf59b7/Templates/TemplateWithSamples.cs) (L36-39) and [AmbientLightRig.cs](https://github.com/vamdeluxe/DeluxePlugin/blob/e606e780e79af214b2b4be0a53b1e7b45ecf59b7/AmbientLightRig/AmbientLightRig.cs) (L122-139, L181, L214) (VAMDeluxe) | `HSVColorPicker.RGBToHSV`, `new JSONStorableColor(name, hsv, callback)`, `RegisterColor`, `CreateColorPicker(c, true)`, `HSVColor {H, S, V}`, `Color.HSVToRGB(H, S, V)`, `SetColorParamValue(name, hsv)`; removal: `RemoveColorPicker` (E18 L1506) |
| E33 | [vam-timeline CustomTrigger.cs](https://github.com/acidbubbles/vam-timeline/blob/54e294256d7b73ec7d00d4216fcc7f01bc9d8133/src/AtomAnimations/Animatables/Triggers/CustomTrigger.cs) (Acid Bubbles) | `NamedAudioClip.sourceClip == null` = not loaded yet (L82), `clipToPlay` (L86), `PlayNow(clip)` (L89) |
| E34 | Package layout and `SELF:` (version 36): [vam-orchestrator Plugin/meta.json](https://github.com/collant/vam-orchestrator/blob/2bbec64edff78c7552e50688cb9784e46166b1c9/Plugin/meta.json) (a plugin package whose `contentList` holds `Custom/Scripts/...` and `Saves/scene/<name>.json`: the scene ships in the same .var as the plugin); `SELF:/` = a path inside the same package: [VPB NativeTextureOnDemandCache.cs](https://github.com/gicstin/VPB/blob/77387fcb0580257bb2764e45127fcf82a595eb5c/src/hook/NativeTextureOnDemandCache.cs) L1224, L1267 ("SELF:/Custom, SELF:/Saves" referenced by a package scene), [vam-easymoan EasyMoan.cs](https://github.com/acidbubbles/vam-easymoan/blob/159866c93789bee345cf6ba311cf6b0d57576276/src/EasyMoan.cs) L535 (`SELF:/Custom/Scripts/...`) | the scene `Saves/scene/AIBody/AI-Buddy.json` inside `d0n.AIBody.<N>.var` references the plugin as `SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist`. TODO(verify) in VaM: PluginManager resolves `SELF:` for a plugin entry of a package scene (no plugin-entry example found in a public source; the preset keeps `d0n.AIBody.<N>:/`) |
| E35 | Rich text in text fields (20.11.2026): [vam-timeline ManageAnimationsScreen.cs](https://github.com/acidbubbles/vam-timeline/blob/54e294256d7b73ec7d00d4216fcc7f01bc9d8133/src/UI/Screens/ManageAnimationsScreen.cs) (Acid Bubbles) and [DiagnosticsScreen.cs](https://github.com/acidbubbles/vam-timeline/blob/54e294256d7b73ec7d00d4216fcc7f01bc9d8133/src/UI/Screens/DiagnosticsScreen.cs) | a `JSONStorableString` shown with `CreateTextField` (L60; the factory instantiates VaM's `configurableTextFieldPrefab` and takes its `UIDynamicTextField`, [VamPrefabFactory.cs](https://github.com/acidbubbles/vam-timeline/blob/54e294256d7b73ec7d00d4216fcc7f01bc9d8133/src/UI/Components/VamPrefabFactory.cs) L162-168) gets Unity rich text in its value: `<b>` (L332, L346, L356) and `<color=grey>` (L327), set via `.val` (L369); DiagnosticsScreen: `<b>SCAN RESULT</b>` (L66), `<color=yellow>` (L90). Used for the bold control names in the left info fields (Leon's style rule) | no new API: the value of the existing info `JSONStorableString` |
| E36 | Speech audio, read 21.11.2026 for the playback fix (study only, nothing copied): [Dollmaster BreathController.cs](https://github.com/vamdeluxe/DeluxePlugin/blob/e606e780e79af214b2b4be0a53b1e7b45ecf59b7/Dollmaster/src/BreathController.cs) (VAMDeluxe), [Dollmaster.cs](https://github.com/vamdeluxe/DeluxePlugin/blob/e606e780e79af214b2b4be0a53b1e7b45ecf59b7/Dollmaster/src/Dollmaster.cs), [FreeMMD.cs](https://github.com/lfe999/VamFreeMMD/blob/e90be09c06a3ca40962ff6aac3a1a36c7bfbe010/src/FreeMMD.cs), [mmd2timeline AudioClipHelper.cs](https://github.com/sFisherE/mmd2timeline/blob/1d22f6de2eb076a56768830eb44f5f9a5ce1d78d/src/Player/Audio/AudioClipHelper.cs), [MacGruber Breathe.cs](https://github.com/vam-community/vam-packages/blob/17e36f5cccc1f898f6b7a6e7d5e72b91471ed2ea/Custom/Scripts/MacGruber/macgruber-breathe/1.0.0/Breathe.cs) | one load sequence in all of them: `GetClip(SuperController.singleton.NormalizeLoadPath(path))` for a clip that is already loaded (Dollmaster L295-296, FreeMMD L318-319, mmd2timeline L194-195), else `QueueClip(NormalizeMediaPath(path))` + `GetClip(clip.uid)`; mmd2timeline then calls `sourceClip.LoadAudioData()` (L112) and treats the clip as ready only when `sourceClip.loadState == AudioDataLoadState.Loaded` (`Unloaded` = call `LoadAudioData()` again, `Loading` = wait, `Failed` = give up; L168-185). Playback on the head: `AudioSourceControl.PlayNowClearQueue(clip)` (FreeMMD L176), `PlayNow(clip)` (Dollmaster L246), the storable action `GetStorableByID("HeadAudioSource").CallAction("PlayNow", clip)` (Breathe L139, L209); `AudioSourceControl.playingClip` (null = nothing playing; BreathController L78); `audioSource.time` (FreeMMD L56). |

## Kept

| feature | APIs | evidence |
|---------|------|----------|
| Companion app link (files) | `FileManagerSecure.CreateDirectory`, `FileExists`, `ReadAllText`, `WriteAllText`, `DeleteFile`, `GetFiles(dir)` (filtered to `.json` in code) | E10, E11, E15 |
| Speech audio load | `SuperController.singleton.NormalizeLoadPath` + `GetClip(path)` (already loaded), `NormalizeMediaPath`, `URLAudioClipManager.singleton.QueueClip`, `GetClip(uid)`, `NamedAudioClip.sourceClip` / `clipToPlay`, `AudioClip.loadState` / `LoadAudioData()` (ready only when `Loaded`), `RemoveClip` | E1, E2, E3, E33, E36 |
| Speech playback + lip sync | `GetStorableByID("HeadAudioSource") as AudioSourceControl`, `PlayNowClearQueue` (first try), `PlayNow` and the storable action `CallAction("PlayNow", clip)` (later tries), `Stop`, `volume`, `playingClip`, `audioSource` (read `isPlaying` / `clip` / `time` for start/end detection and the audio debug lines) | E1, E2, E3, E29, E36 |
| Morphs, expressions, breathing | `GetStorableByID("geometry") as DAZCharacterSelector`, `morphsControlUI`, `GetMorphByDisplayName`, `GetMorphByUid`, `morphValue` | E4, E5 |
| Idle head motion, head gestures | `GetStorableByID("headControl") as FreeControllerV3`, `transform.rotation`, `currentRotationState` | E6, E2 |
| Gaze (eyes) | `GetStorableByID("Eyes") as EyesControl`, `currentLookMode` (`LookMode.Target`), `freeControllers` / `name == "eyeTargetControl"`, `eyeTarget.control.position`, `centerCameraTarget.transform`, `GetAtoms()`, `atom.mainController.control`, `rotation * Vector3.forward`, `GetStorableIDs()` + `EndsWith("Glance")` | E12, E28, E6, E8 |
| Blinking (optional) | `GetStorableByID("EyelidControl")` + `GetBoolJSONParam("blinkEnabled")`, `morphValue` of the morph "Eyes Closed", `Mathf.SmoothStep` | E29, E4 |
| Background color (version 36) | `CameraTarget.centerTarget.targetCamera`, `Camera.clearFlags` / `backgroundColor` (old values kept and restored), `SkyshopLightController.singleton.GetBoolJSONParam("showSkybox")`, `JSONStorableColor` / `CreateColorPicker` / `RemoveColorPicker` / `SetColorParamValue`, `UITransform.gameObject.activeInHierarchy` (status text only while the UI is open: E12 L1271, E11 L206) | E30, E31, E32, E18 |
| Scene hooks | `RegisterBool` / `RegisterString` / `RegisterAction` with `isStorable` / `isRestorable` false, `GetBoolJSONParam`, `GetStringJSONParam` (read / set by triggers and other plugins) | E9, E12 (L66), E13 |
| Timeline gestures | `GetStorableIDs()` + suffix match, `CallAction("Play <animation>")` | E8, E9 |
| Pose presets | `GetStorableByID("PosePresets")`, `GetUrlJSONParam("presetBrowsePath")`, `NormalizePath`, `CallAction("LoadPreset")` | E7 (pattern; the `PosePresets` id itself is `TODO(verify)`) |
| Generic trigger | `CallAction`, `GetFloatJSONParam`, `GetBoolJSONParam`, `GetStringJSONParam`, `GetStringChooserJSONParam` | E8, E12, E13 |
| Settings tabs | `RemoveToggle`, `RemoveSlider`, `RemovePopup`, `RemoveButton`, `RemoveTextField` on the controls of the old tab, then `Create*` for the new one (`UiPage` in `UiHelper.cs`) | E17, E18 |
| Shared settings file `Saves/PluginData/AIBody/config.json` | `FileExists`, `ReadAllText`, `CreateDirectory`, `WriteAllText` in the plugin's own folder below `Saves/PluginData` | E10, E11, E19, E20 (see "Config file location") |
| Plugin UI and storables | `CreateToggle`, `CreateSlider`, `CreatePopup`, `CreateButton`, `CreateTextField` (+ `InputField` for editing), `Register*`, `JSONStorableAction`, `chooser.choices` | E1, E9, E12, E14, E16 |
| Logging, Person check | `SuperController.LogMessage` / `LogError`, `containingAtom.type`, `containingAtom.uid` | E9, E12 |

## Removed / dropped (with reason)

| what | reason |
|------|--------|
| Optional HTTP transport (`src/Optional/HttpTransport.cs`, `AutoTransport.cs`, `#if AIBODY_HTTP`), `--http` build path, networking stubs | Owner rule: zero `UnityWebRequest` / `UnityEngine.Networking` in the plugin sources at all, not only in the build |
| Audio download over HTTP (`UnityWebRequestMultimedia`), `speak.url` field | same rule; audio comes only from a local file via `URLAudioClipManager` |
| Transport chooser in the plugin UI | only one transport is left |
| Companion app HTTP server, `auto` mode, `--transport/--host/--port`, `http_host/http_port/audio_cache_dir` | no plugin can talk HTTP any more |
| Clip readiness check via `NamedAudioClip.clipToPlay` | **Correction (19.11.2026): it IS evidenced** (acidbubbles/vam-timeline `CustomTrigger.cs` L86-92, commit 54e2942: `NamedAudioClip.clipToPlay` read after `QueueClip`), the earlier "no public plugin shows it" was wrong. AIBody still does not use it: replaced by `PlayNow` retries (1 s) and watching `AudioSource.isPlaying/clip`, 15 s timeout -> `audio_failed` (a switch to `clipToPlay` is a Backlog item, needs a VaM test). `AudioSourceControl.clipLoudness` is in Dollmaster (E1, `ExpressionController.cs` L84-141) |
| Direct `AudioSource.Play` fallback, `AudioSource.volume` writes | playback only through `AudioSourceControl` as in E1-E3 |
| `AudioSourceControl` "volume" float param lookup | no evidence; the `volume` field (E2) is used instead |
| `JSONStorable.GetActionNames` checks before `CallAction` | no evidence; actions are called directly (E7, E8). A misspelled action is not detected |
| `FileManagerSecure.GetFiles(dir, pattern)` | no evidence for the pattern overload; `GetFiles(dir)` (E11) plus a `.json` filter |
| `UnityEngine.Microphone` / mic capture in VaM | never used; the scan forbids it. Capture lives in the companion app (always the system default input, no device selection); the plugin sends settings and push-to-talk (`ptt` event file) |
| Coroutines in the speech player | not needed after removing the download path |

## Still TODO(verify) in VaM 1.22

These use evidenced APIs but in a combination nobody has shown publicly, or depend on scene content:

1. The plugin loads from `d0n.AIBody.7.var` in the sandbox (flat `.cslist`).
2. `FileManagerSecure.GetFiles(dir)` returns paths that `ReadAllText` / `DeleteFile` accept for
   `Saves/PluginData/AIBody/<channel>/inbox` (`FileTransport.cs`).
3. `NormalizeMediaPath` + `QueueClip` with a `Saves/PluginData/...` relative path (evidence uses
   file-browser paths), and `PlayNow` on a still loading clip being retried safely; start/end
   detection via `AudioSource.isPlaying` / `clip`; lip sync follows (`SpeechPlayer.cs`).
4. ~~`JSONStorableStringChooser.choices` refreshes an open popup~~: now evidenced (E24, E25: set on popups that are on screen, refilled from `popupOpenCallback`). The mic menu that first used it is gone (19.11.2026); E24/E25 stay in use for the pose, expression and gesture choosers (`Body.cs`).
5. The `InputField` text field pattern on `CreateTextField` (`UiHelper.cs`).
6. The `PosePresets` storable id and its `presetBrowsePath` / `LoadPreset` (`PoseController.cs`).
7. Morph names of the built-in expressions and the breath morph (`ExpressionController.cs`,
   `BreathingController.cs`, `Body.cs`).
8. Tabs: `Remove*` + `Create*` switch the right column cleanly, also for editable text fields.
9. `Saves/PluginData/AIBody/config.json` is written without a confirm dialog; the scene's saved
   values are restored within 1.5 s after Init (seeding check in `AIBody.cs`).

## 0.6.2: no new VaM APIs

0.6.2 only reorders and guards the start-up (status box first, one try/catch per phase, lazy
retried lookups of `HeadAudioSource`, `geometry` and `headControl`, a guarded `InputField`, a
PluginData write test with the already audited `FileManagerSecure` calls). Exception details come
from `Exception.ToString()`, not from reflection. The only additions outside the VaM API are plain
`UnityEngine.Time.time` reads for the retry timers.

## 0.6.3: tabs and the shared config file

- **Tabs** use only `Remove*` + `Create*` (E17, E18). `RemoveSpacer` is not needed (no spacers).
  The InputField of an editable text field is unbound (`storable.inputField = null`) before its
  field is removed.
- **Config file location: `Saves/PluginData/AIBody/config.json`, one global file.** Evidence for
  the convention "one folder per plugin below `Saves/PluginData`, settings as JSON in it":
  Timeline keeps its global defaults in `Saves\PluginData\Timeline\settings.json`
  ([TimelineDefaults.cs L9-10](https://github.com/acidbubbles/vam-timeline/blob/54e294256d7b73ec7d00d4216fcc7f01bc9d8133/src/AtomAnimations/Editing/TimelineDefaults.cs)),
  Keybindings uses `Saves\PluginData\Keybindings` (E19), Scripter writes with
  `FileManagerSecure.WriteAllText` into `Saves\PluginData\Scripter\...`
  ([Scripter.cs L87, L334](https://github.com/acidbubbles/vam-scripter/blob/96674ce01a3ca1e8d5eaebceccf047f14de69394/Scripter.Plugin/src/Scripter.cs)).
  The official notes name `FileManagerSecure` as the plugin file API (E15) and say that file
  creation may go through VaM's user confirm/deny system (E20); the per-plugin `Saves/PluginData`
  folder is the place established plugins write to. Global (not per channel) like Timeline's
  `settings.json`, because the settings describe the one AI character; the channel is a value in
  the file. TODO(verify): VaM 1.22 creates the file without asking (as for the channel files).
- New UnityEngine use: none beyond `Time.time` (retry timers, 0.6.2).

## 0.7.0: engine status, preserved "ai" section

- No new VaM API. The plugin keeps the companion-only `ai` section of config.json when it writes
  the file: `JSON.Parse(FileManagerSecure.ReadAllText(...)) as JSONClass`, `existing["ai"] as
  JSONClass`, `root["ai"] = ai` (indexer and `as` cast, as already used for config.json; E10,
  E11). The engine status from `companion_heartbeat` is shown in an unregistered
  `JSONStorableString` text field in the Engines tab (same pattern as the tab headers).
- Finding from the 0.7.0 review (E21): every number / boolean the plugin writes is a string.
  Before 0.7.0 the companion app rejected them, so push-to-talk events (`"active":"true"`), the
  mic settings from the plugin (`config` event) and the plugin-written config.json values were
  dropped. Fixed on the companion side; covered by the end-to-end simulation test.
- Network: still none in the plugin. The cloud engines (xAI, ElevenLabs) run only in the Python
  companion app.

## 0.7.1: AI mode / proactive controls, realtime voice in the companion

- No new VaM API. The Engines tab gets one more `JSONStorableStringChooser` (AI mode), two
  `JSONStorableBool` (Proactive talking, formerly Proactive; Voice barge-in) and one `JSONStorableFloat` (Speech delay timer, formerly Proactive idle),
  registered and shown with `CreatePopup` / `CreateToggle` / `CreateSlider` like the existing
  settings (E11). The plugin merges these four keys into the kept `ai` section with the same
  SimpleJSON indexer / `as JSONClass` pattern as 0.7.0 (no enumeration of `JSONClass` needed).
- The realtime voice (WebSocket to `wss://api.x.ai/v1/realtime`) is companion-only; the plugin
  still has no network code and plays the answer segments through the unchanged `speak` command.

## After 0.7.1 (unreleased): sound path, test tones, menu restructure

- **New: plugin folder lookup for the bundled test WAV**, exactly Dollmaster's `GetPluginPath`
  (E1, L283-290): `storeId.Split('_')[0]`, `containingAtom.GetStorableByID("PluginManager") as
  MVRPluginManager`, `manager.GetJSON(true, true)["plugins"][pluginId].Value`, cut at the last
  `/`. Dollmaster's extra line `currentSaveDir = currentLoadDir` is NOT copied (side effect, not
  needed). The WAV (`AIBodyTest.wav`, next to the `.cslist`) is loaded with the unchanged
  `NormalizeMediaPath` + `QueueClip` + `PlayNow` path; Dollmaster loads its audio from its own
  plugin folder the same way (E1 L293-310, `Personality.cs` L45-72), also from a `.var`.
- **File check before loading:** `FileManagerSecure.FileExists(path)` (E10) for plain paths below
  the VaM folder, so a missing companion file shows as "Audio error: file missing" instead of a
  15 s start timeout. Package paths (`pkg:/...`) are not checked.
- **Tooltip / hover on a toggle: not done.** No public sandboxed plugin shows a tooltip API for
  `CreateToggle` controls, and building one would need Unity `EventTrigger` / pointer handlers
  that no evidence covers. The push-to-talk explanation is a short text field right under the
  checkbox (unregistered `JSONStorableString` + `CreateTextField`, as for the tab headers).
- Placeholder slider "Delay" and the key status text are unregistered storables shown with
  `CreateSlider` / `CreateTextField` (same pattern as the engine status text).
- Toggle labels come from the storable name; the existing storable "Push-to-talk active" keeps its
  name (renaming would lose the value saved in scenes).
- Still TODO(verify): whether VaM's audio loader accepts WAVs below `Saves/PluginData` at all
  (the evidence loads from `Custom/` and package folders). The two test-tone buttons tell the
  cases apart; the fallback is `connection.paths.audio` (e.g. `Custom/Sounds/AIBody`).

## 0.7.2: simple Q&A, audio folder below Custom/Sounds

- **No new plugin API.** The button "Simple Q&A mode" is a `CreateButton` (E1) that sets the
  existing AI mode chooser and the existing "Body control" bool; the explanation texts are
  unregistered `JSONStorableString` + `CreateTextField` (E12), the new status lines are text in the
  existing status box. The `FileExists` check (E10) is now wrapped in try/catch so a throwing check
  never blocks loading.
- **Audio folder default `Custom/Sounds/AIBody/<channel>`** (written by the companion with normal
  file IO, outside the sandbox). Evidence for the folder: VaM's own Scene Audio browser opens
  `Custom\Sounds` (E23); a public plugin keeps its WAVs in `Custom/Sounds/...` and reads them with
  `FileManagerSecure` (E22); Dollmaster loads its clips with `QueueClip(NormalizeMediaPath(path))`
  from its own folder below `Custom/Scripts` or its package (E1). No evidenced plugin loads audio
  from `Saves/PluginData`. So `Custom/Sounds` is the better-supported default, and
  `Saves/PluginData/AIBody/<channel>/audio` (the 0.7.1 folder) is kept as the automatic fallback:
  when the plugin reports `audio_failed` (clip not loadable / never started) the companion switches
  once and sends the same speech again from there.
- Still TODO(verify): `QueueClip` with a loose WAV below `Custom/Sounds` (E22 decodes the bytes
  itself, E23 is documentation of the Scene Audio atom, not of `URLAudioClipManager` from a
  plugin); `QueueClip` below `Saves/PluginData`; `FileExists` on a `Custom/` path in the sandbox.
  T9 (both test tones, then a typed and a spoken question) answers all three.

## 0.7.3: verbose log, realtime toggle

- **No new plugin API.** `[debug]` lines use `SuperController.LogMessage` (already used for every
  `AIBody:` line); the last 8 are kept in a `List<string>` and shown as text in the existing status
  box. "Use realtime voice" is an unregistered `JSONStorableBool` shown with
  `CreateToggle` (same pattern as the other unregistered UI-only storables); it only sets the
  existing AI mode chooser, so nothing new is saved with the scene. No `valNoCallback` (not
  evidenced): a guard flag keeps the two in sync.
- **Tooltip on mouseover (push-to-talk), checked again: not done.** The only sandboxed example
  found is via5/VUI (commit `5d7aea2de5bd51dc6b3f22f27cf3299282d6c450`, `project/src/VUI/Root.cs`):
  its own UI framework with a custom `MonoBehaviour` implementing Unity's `IPointer*Handler` and
  synthesized pointer-enter events. That is not a simple, evidenced pattern for a `UIDynamicToggle`,
  so the explanation text under the checkbox stays.
- Companion (outside the sandbox): checked against the real xAI API with a fake key on 17.11.2026:
  `POST /v1/tts`, `POST /v1/stt` and the realtime WebSocket handshake answer HTTP 400
  `"Incorrect API key provided"` (not 401), `POST /v1/responses` exists (422 for an empty body),
  an unknown path gives 404. The key status now shows "abgelehnt" for that 400 too. Still
  TODO(verify): a full answer with a real key.

## 0.7.4: mic menu, pose menu, body tools, latency

- **Chooser refresh (E24, E25):** `choices` and `displayChoices` set together on a shown popup
  (vam-collider-editor `ColliderEditor.cs` @00d54b06 L414-415, L448-449), `CreateScrollablePopup`
  (L359), `popupOpenCallback` refilling `choices` when the menu opens (vam-embody `Embody.cs`
  @e09e364f L77, L950; vam-timeline `SequencingScreen.cs` @54e29425 L257-264, L500). Used for
  the mic menu and the pose / expression / gesture menus in tab AI Character. Item 4 of the
  TODO(verify) list (chooser updates) is covered by this evidence; still checked in VaM in T11.
- **Pose files:** `FileManagerSecure.GetFiles` on `Custom/Atom/Person/Pose` and
  `Custom/Atom/Person/Pose/AIBody`, at most 200 files. TODO(verify): E11 shows `GetFiles` on
  `Saves/PluginData`, not on `Custom/`. Applying uses the existing `LoadPose` path (PosePresets,
  still TODO(verify) T5).
- **Gaze tool:** was missing until version 24; added in version 25, see "Version 25: gaze control" at the end.
- **Path display removed** from tabs Post and Config (the menu shows only what can be set); the
  paths go once to the log via `SuperController.LogMessage`. No new API.
- **Latency / key hint:** text in the existing status box from the companion heartbeat; no new API.
- Companion (outside the sandbox): xAI function calling in `/v1/responses` (`tools` with
  `type: function`, results as `function_call_output` with `previous_response_id`) and realtime
  (`function_call` -> `conversation.item.create` `function_call_output` + `response.create`).
  Tested against a fake server only; TODO(verify) with a real key.


## Version 13: extended self test

- **No new VaM API.** The body checks reuse what the code already calls: `GetStorableByID("PosePresets")`
  and `GetUrlJSONParam("presetBrowsePath")` (E7, as in `LoadPose`), `MorphHelper.Find` (unchanged
  lookup), `FindStorable` over `GetStorableIDs` (E8) and
  the `GetFiles` result of the pose scan (E11, still TODO(verify) for `Custom/`). The result is
  plain SimpleJSON in the existing `heartbeat`. Checked by `tools/check_plugin.py` (stubs compile).

## Version 14: VaM compiler hotfix (CS584)

- Version 13 did not compile in VaM: `[CS584]: Internal compiler error: Unexpected error when
  loading type 'System.Collections.Generic.Dictionary<TKey,TValue>.ValueCollection.Enumerator' ...
  at [40, 13]` = `ExpressionController.cs`, `MorphNames` getter (line 40), `foreach` over
  `_presets.Values` (added in commit 2be56ff). The Roslyn stub compile in `tools/check_plugin.py`
  accepts this, VaM's Mono `mcs` does not: **the stub compile proves API use, not that VaM's
  compiler accepts the syntax.**
- Fix: no `foreach` / LINQ over `.Keys` / `.Values` anywhere (also removed in `PoseController`:
  `PoseNames` over `_poseFiles.Keys` since 0.7.4, `TimelineGestureCount` / `HasTimeline` over
  `_gestures.Values`). Iteration over the dictionary itself (`KeyValuePair`) is kept: used by
  `MorphHelper` since the first version, and by Timeline (`foreach (var kvp in
  triggersTarget.triggersMap)`, a `SortedDictionary`, [AdvancedKeyframeToolsScreen.cs
  L90](https://github.com/acidbubbles/vam-timeline/blob/54e294256d7b73ec7d00d4216fcc7f01bc9d8133/src/UI/Screens/AdvancedKeyframeToolsScreen.cs)).
  Key lists for callers are copies (`new List<string>(dict.Keys)`, no enumerator in our code).
- Enforcement: `tools/sandbox_rules.py` bans `in <expr>.Keys)` / `in <expr>.Values)`, member access
  on `.Keys` / `.Values` and the `KeyCollection` / `ValueCollection` types (scan of `src/`, the
  assembled plugin and the `.var`).
- TODO(verify): version 14 compiles in VaM 1.22.

## Version 15: menu restructure

- **No new VaM API.** Tabs, sections and the info field use the same `CreateButton` /
  `CreateToggle` / `CreateSlider` / `CreatePopup` / `CreateScrollablePopup` / `CreateTextField`
  and `Remove*` calls as before (E17/E18/E24); the tabs simply create no `CreateTextField` any more
  except section headers and the label above the breath morph field. The big info field is the
  existing status `CreateTextField`, taller (1200). No `foreach` over Dictionary `.Keys`/`.Values`
  (CS584 rule, version 14).

## Version 16: mic menu, info field

- **Less API, not more.** The mic chooser no longer sets `displayChoices` (it was the only chooser of
  the plugin with it and showed "(not selected)" with an empty list in VaM). It now uses only
  `choices` like the pose, expression, voice and engine choosers (E9, E24, E25). TODO(verify): that
  `displayChoices` was the cause; the info field lists the menu entries read back from `choices`.
- `CreateScrollablePopup` (E24) and `popupOpenCallback` (E25) stay as before.
- Info field: same status `CreateTextField`, height 1600 (TODO(verify): visible height in VaM).
- No new VaM API; no `foreach` over Dictionary `.Keys`/`.Values` (CS584 rule).

## Version 17: info field

- No new VaM API. One `CreateTextField` less (the left header line); the info field is 1800 high
  (TODO(verify): visible height in VaM). Button label changes only (`CreateButton` text), no
  storable names changed. No `foreach` over Dictionary `.Keys`/`.Values` (CS584 rule).

## Version 19: shown slider label

- One new member: `UIDynamicSlider.label` set right after `CreateSlider` (E26: TittyMagic,
  ExpressionRND, Dollmaster), in `UiPage.Slider(JSONStorableFloat, string label)`. Used once: the
  storable "File poll interval (s)" is shown as "Companion inbox poll interval (s)". The storable
  name (saved in scenes) and the polling behaviour are unchanged; the compile stub declares the
  member with the E26 tag. No `foreach` over Dictionary `.Keys`/`.Values` (CS584 rule).

## Version 20: mic menu without the companion app (superseded: the whole mic device menu was removed on 19.11.2026)

- No new VaM API. The Mic device chooser gets a new `choices` list when its popup opens (inside
  `popupOpenCallback`, as E25 does), on "Refresh microphones" and when the tab is built (E24, E25).
  TODO(verify): why VaM showed no entry at all; the info field line "Mic device menu: N entries"
  reads the chooser back. No `foreach` over Dictionary `.Keys`/`.Values` (CS584 rule).

## After version 22 (version 24): XAI API Token in config.json, masked display

- **No new VaM API.** The token is read and written through the already audited config.json path
  (`FileManagerSecure.ReadAllText` / `WriteAllText`, E11, with the existing SimpleJSON merge in
  `AIBody.WriteSettings`); the field is still the audited `CreateTextField` + `InputField` bound through
  `storable.inputField` (E14). Masking is plain string work: the storable only shows the mask, the real token
  is a private string, text containing `****` is ignored. No `foreach` over `Dictionary.Keys`/`.Values`.
- **Not used:** `InputField.contentType = Password` (or `asteriskChar`): it is standard Unity UI, but no
  audited VaM plugin uses it on a `CreateTextField` field, so it is not in the stubs and not used.
  Since version 30 the mask is applied when the field loses focus (see "Version 30"), no longer after 4 s.
  TODO(verify) in VaM: pasting a new key over the mask is accepted.
- Version 24 to 30: the scene saved the storable (registered), holding the mask (or, while typing, the raw text). Since
  version 31 the storable is not registered (`RegisterString` is not called; the same pattern as the first-run note's
  field, which also drives `CreateTextField` + `InputField`), so no scene holds the token at all; a token an older
  scene (version 21 to 23) restored is no longer read. `config.json` is the only place.

## Version 21: free-text field "XAI API Token", two-line "Question and Answer" button

- **Text field:** no new API. The field is the already audited editable text field (`CreateTextField`
  + `InputField` bound through `storable.inputField`, E14, as used for "Breath morph" since version 15),
  under a `Header` label and above a `Header` hint, in `UiPage.TextInput`. The storable is a
  `JSONStorableString` registered with `RegisterString` (E9), so VaM saves it with the scene, which
  the hint "(beware: scenes save it)" says. TODO(verify): pasting with Ctrl+V into the field in VaM
  (the same unverified point as for "Breath morph").
- **Button:** one new member, `UIDynamicButton.buttonText` (`Text`), used for
  `buttonText.alignment = TextAnchor.MiddleCenter` (E27: timeline, embody). The two lines are a `\n`
  in the label string passed to `CreateButton` (E1), the height is `UIDynamic.height` (the base
  class of the button; the same member `Glance.cs` sets on a spacer, E12). The compile stubs declare
  `Text.alignment`, `TextAnchor`, `UIDynamicButton.buttonText` with the E27 tag. Both settings sit in
  one `try`/`catch` (`UiPage.Button(label, height, onClick)`): if VaM refuses either, the button still
  works and the reason goes to the log. TODO(verify): the look in VaM (two lines, centered, not cut off at 90 px).
- **Token transport:** unchanged file transport (`FileManagerSecure.WriteAllText` in the channel
  outbox, E10, E11, E15); the token is an extra `keys` object in the `config` event. The plugin never
  writes it to config.json and never logs it. No network API in the plugin, no `foreach` over
  Dictionary `.Keys`/`.Values` (CS584 rule).

## After version 22 (19.11.2026): microphone device selection removed

- No new VaM API; code and API uses only go away. Removed: the "Mic device" chooser (with
  `popupOpenCallback` refill, `choices` refresh and `CreateScrollablePopup` for it), the "Refresh
  microphones" button and the "Refresh mic devices" action. **E24 and E25 stay in use**: the pose,
  expression and gesture choosers (`Body.cs`: `popupOpenCallback = RefreshCharacterChoices`,
  `choices` set on a shown popup) and `UiPage.ScrollablePopup` for the pose menu still rely on
  them, so those entries are not obsolete. The Version 20 section above only describes the removed menu.
- Old scenes that saved "Mic device" simply have a stored value no storable reads any more (VaM
  skips unknown stored parameters of a plugin). TODO(verify): loading such a scene in VaM shows no
  error in the log.

## After version 22 (19.11.2026): speech file hand-over

- No new VaM API. `SpeechPlayer` calls the audited `FileManagerSecure.FileExists` (E10) repeatedly
  (every 0.25 s from `Update`) for a speech file that is not visible when `speak` arrives, instead of
  failing at once (this refines the "File check before loading" note above). A WAV size / RIFF-header
  check was considered and NOT implemented: `ReadAllBytes` and file-size calls have no evidence here,
  and `ReadAllText` would alter binary data. The timeout diagnostics read `AudioSource.isPlaying` and
  `AudioClip.length` (already used). No `foreach` over Dictionary `.Keys`/`.Values`, no network, no
  threads or sleeps.

## After version 23 (19.11.2026): VAD engine and VAD strictness in the Mic menu

No new API. A `JSONStorableStringChooser` ("VAD engine", registered with `RegisterStringChooser`, shown with the
existing `page.Popup`) and a `JSONStorableFloat` ("VAD strictness", `RegisterFloat` via the existing `Reg` helper,
shown with `page.Slider`), the same patterns as "Mic mode" and "VAD threshold". The values travel in the existing
`mic` JSON (`vad_engine`, `vad_strictness`); `mic_state.vad` / `vad_note` are plain strings shown in the info field.
No `foreach` over Dictionary `.Keys`/`.Values`, no file or network access added.

## Version 25 (19.11.2026): gaze control

New in the plugin (`GazeController.cs`), all with evidence E12 / E28 (see the table and the stub comments):

- **Eyes:** `Eyes` storable as `EyesControl`; `currentLookMode` is read, set to `LookMode.Target` and restored;
  the controller `eyeTargetControl` is found in `Atom.freeControllers` by `name`; its `control.position` is set every
  frame (Embody's eye module does the same). Only the look-mode values that the evidence shows are declared in the
  stubs (`Target`, `Custom`); the code uses `Target` only. NOT used (no evidence or not needed): `LookMode.Player` /
  `None`, `lookAt1` / `lookAt2`, `Custom` mode with an own `GameObject`, blink / eyelid control, eye morphs.
- **Targets:** the camera = `SuperController.singleton.centerCameraTarget.transform.position` (the player's view,
  VR or screen; Glance L647); atoms = `SuperController.singleton.GetAtoms()` (a plain loop, no LINQ), a Person's
  face = `headControl` as `FreeControllerV3` (E6) `.control.position`, any other atom = `mainController.control.position`;
  straight ahead / away = own `headControl.control.position` plus `atom.transform.rotation * Vector3.forward`
  (Glance L1182 uses the same `rotation * ... * Vector3.forward`; Embody uses `head.forward`). TODO(verify): that the
  atom's own forward is the way the Person faces (the example scene turns the client by 180 degrees to face the AI).
- **Menu / data:** a `JSONStorableBool` "Gaze control", a `JSONStorableStringChooser` "Default gaze" (registered, refilled
  in `popupOpenCallback`, E25, shown with `CreateScrollablePopup`, E24) and a `JSONStorableBool` "Gaze follows speaker";
  same patterns as the existing controls. The heartbeat gets `gaze_control` and `gaze_atoms` (plain bool / strings).
- **Coexistence:** the plugin steps aside when `GetStorableIDs()` has an id ending in `Glance` (Embody's own check) and
  gives the eyes back when someone else changes `currentLookMode` while it steers. TODO(verify): the id suffix of
  Glance in a real scene, and how the Life plugin behaves (not detected by name; only the look-mode check protects).
- No `foreach` over Dictionary `.Keys`/`.Values`, no LINQ, no file or network access added. A gaze exception only
  stops the gaze (`_gazeBroken`), not the body.

## Version 36 (20.11.2026): background color, speech readiness

- **Background color** (`Background.cs`, toggle "Set background color", default off): the view camera
  `CameraTarget.centerTarget.targetCamera` (E30) gets `clearFlags = CameraClearFlags.SolidColor` and `backgroundColor`
  (E30), VaM's skybox is hidden with `SkyshopLightController.singleton.GetBoolJSONParam("showSkybox")` (E31). Every value
  touched is remembered and put back when the toggle goes off, the plugin is disabled or removed. TODO(verify) in VaM:
  that `targetCamera` is the camera the headset renders (desktop and VR), and that the skybox switch is restored when
  the scene is saved with the background on.
- **Colour picker** (`UiPage.ColorPicker`): `JSONStorableColor`, `RegisterColor`, `CreateColorPicker`, `RemoveColorPicker`,
  `HSVColorPicker.RGBToHSV`, `Color.HSVToRGB` (E32, E18). The companion's setup answer is applied with
  `SetColorParamValue` (E32 L214).
- **Speech start when the clip is ready:** `NamedAudioClip.sourceClip != null` before `PlayNow` (E33). TODO(verify): a
  clip queued with `QueueClip` gets `sourceClip` once loaded (vam-timeline relies on this for scene clips).
- **Status text only while the plugin UI is open:** `UITransform.gameObject.activeInHierarchy` (E12 L1271, E11 L206).
- Not used: `UnityWebRequest`, reflection, indexers. Nothing new in the sandbox rules.

## Version 32 (20.11.2026): pose commands

**No new VaM API.** The plugin side reuses what is already audited:

| Use | API | Evidence |
|---|---|---|
| command chooser | `UiPage.Popup` (`CreatePopup`) | E16 |
| pose chooser (long list) | `UiPage.ScrollablePopup` (`CreateScrollablePopup`), `chooser.choices = ...` | E24 |
| command text field | `UiPage.TextInput` (`CreateTextField` + `InputField`, bound through `storable.inputField`) | E14 |
| Add Pose / Delete Pose / Restore starter poses | `UiPage.Button` (`CreateButton`) | E1, E9 |
| helper storables for the UI | `JSONStorableStringChooser` / `JSONStorableString`, NOT registered (no scene holds them) | as the token field (version 31) |
| applying a pose | unchanged: `PosePresets` storable `presetBrowsePath` + `CallAction("LoadPreset")` | E7 |
| config.json | `JSONClass` / `JSONArray` read and assign, written by the plugin's existing `WriteSettings` | as for the other categories |
| warning line | `SuperController.LogMessage` with the prefix "Warning:" (`Log.Warn`) | same call as `Log.Info` |

The new file `PoseVocabulary.cs` is plain C# (strings, `List<T>`, `StringBuilder`): no VaM or Unity types, no LINQ, no `foreach` over `Dictionary.Keys` / `.Values`, no file or network access; the tests also compile and run it outside VaM. The JSON of a pose command is read by a small strict reader in this file, not by `SimpleJSON`, so the same rules can be tested on both sides. Credits for all evidence sources: `CREDITS.md`.

## Version 31 (19.11.2026): remote control, plugin preset, token fix

**No new VaM API in the plugin.** The remote control is companion-app code (Python standard library: `http.server`,
`socket`); the plugin only keeps one more config.json section when it saves (`JSONClass` read and assign, as for `ai`).

**Token fix:** `_plugin.RegisterString(_xaiTokenJson)` was removed. A storable that is never registered is not saved
with the scene (the pattern of an unregistered `JSONStorableString` is plain Unity/VaM behavior: only registered storables
take part in `GetJSON` / `RestoreFromJSON`; evidenced by every plugin that creates helper storables without registering them,
and by our own `_settingsInitJson`-style handling). The UI still shows and edits the field (`CreateTextField` needs no
registration). TODO(verify) in VaM (T20 step 4): the field still works, the scene file holds no token.

**Plugin preset format (evidence):**

| Evidence | What it shows |
|---|---|
| VaM Hub "PresetLoader" and the vam-backstage classifier (`docs/Implementation.md`, type `pluginPreset`) | Person plugin presets are `.vap` files in `Custom/Atom/Person/Plugins/`; the browser hides them |
| BoominBobbyBo/iHV script (`PluginManager.plugins ... "plugin#100" = "Custom/Scripts/.../x.cs"`) | the Person's storable `PluginManager` has a `plugins` map `plugin#N` -> script path |
| our scene `examples/scenes/AI-Buddy.json` and Timeline / CircleLooks instructions | a package script is referenced as `<creator>.<package>.<version>:/Custom/Scripts/.../X.cslist`; the `.cslist`, not single `.cs` files, is loaded |

The preset therefore holds exactly: `{"storables":[{"id":"PluginManager","plugins":{"plugin#0":"d0n.AIBody.32:/Custom/Scripts/d0n/AIBody/AIBody.cslist"}}]}`.
No parameter values and no `setUnlistedParamsToDefault`, so loading it cannot overwrite other settings. TODO(verify) in VaM (T23):
that a hand-written `.vap` with only this storable loads, that the package-qualified path is accepted in a preset, that the preset is
listed from inside the package, and what a second load does to existing plugins.

## Version 30 (19.11.2026): Network Active, token mask by focus, first-run note

Spec change by Leon (19.11.2026): the plugin may use one loopback socket to the companion app. The file channel stays
the fallback.

**Network: which transport, and the evidence.**

| Evidence | What it shows |
|---|---|
| [VAMLaunchNetwork.cs](https://github.com/ZengineerVAM/VAMLaunch/blob/master/VAMLaunch/src/VAMLaunchNetwork.cs) (ZengineerVAM) | A VaM plugin with plain **UDP**: `UdpClient`, `IPEndPoint`, a background `Thread` (`IsBackground = true`) that blocks in `Receive`, a `Queue<byte[]>` filled under `lock` and drained from the main thread (`GetNextMessage`), `Send` wrapped in try/catch, `Stop` closes the client. Needs "Allow Plugins Network Access". |
| [VaM_ML_Skeleton_Engine / AIVRLab.BoneReceiver](https://github.com/yuyaslabo/VaM_ML_Skeleton_Engine) (yuyaslabo) | A plugin that receives a Python engine's data over **UDP** (default port 9998), "Allow Plugins Network Access" required. |
| [Neptune API](https://www.patreon.com/SPQR_aeternum/posts/neptune-api-v1-145203754) (SPQR) | A plugin that opens a listener on 127.0.0.1:7872 (HTTP-style calls from local tools); says a Windows firewall prompt appears once; needs the same VaM setting. |
| [Voxta plugin docs](https://doc.voxta.ai/docs/integrations/vam/basics/install-plugin) | The Voxta plugin talks SignalR (WebSocket) to the Voxta server on 127.0.0.1:5384; lists "Allow Plugins Network Access" as required. |
| [VaM patch notes 1.22](https://cdn.virtamate.com/Release/VaM_PatchNotes.html) and [MeshedVR security patch](https://www.patreon.com/meshedvr/posts/important-patch-121741619) | "Allow Plugins Network Access" (User Preferences, Security) is off by default; some existing plugins do not work until it is on; it is the riskiest preference. |

**Decision: UDP on 127.0.0.1.** UDP with a receive thread and a locked queue has the most direct source evidence (VAMLaunch, BoneReceiver); no connection state to hang on, a send never waits for the other side, and all messages of this protocol are small (one datagram = one complete JSON message, at most 60000 bytes; bigger ones travel through the file channel). TCP and WebSocket have no source we could read (Voxta's SignalR client is a bundled library); HTTP listeners (Neptune) would mean `HttpListener`, which stays banned.

APIs used, all inside `src/AIBody/SocketLink.cs` (the only file that may mention `System.Net`; `tools/sandbox_rules.py` enforces it):

| API | Use | Evidence |
|---|---|---|
| `UdpClient(IPEndPoint)`, `Send(byte[], int, IPEndPoint)`, `Receive(ref IPEndPoint)`, `Close()` | the socket (plugin side bound to an ephemeral port on `IPAddress.Loopback`) | VAMLaunch (`UdpClient`, `Send`, `Receive`, `Close`) |
| `IPEndPoint`, `IPAddress.Loopback`, `IPAddress.IsLoopback` | address handling; `IPAddress.Any`, `Parse`, `new IPAddress` stay banned, so no other address can be configured | `IPEndPoint` as in VAMLaunch; loopback constants are plain .NET |
| `Thread` (`IsBackground = true`), `Monitor.Wait/Pulse`, `lock`, `Queue<T>` | one receive thread, one send thread, queues drained in `Update` | VAMLaunch (`Thread`, `IsBackground`, `lock`, `Queue`) |
| `Encoding.UTF8` | datagram text | plain .NET |

Rules kept: no `UnityWebRequest`, no `UnityEngine.Networking`, no TCP/HTTP/WebClient types, no `foreach` over `Dictionary.Keys/.Values`, one plugin and one `.cslist`; the threads never call Unity or VaM; `Tick()` only moves finished messages between the queues and the plugin. With the toggle off, `new SocketLink(...)` is never executed (test `test_off_means_no_network_code_runs`). TODO(verify) in VaM 1.22: what the plugin does when "Allow Plugins Network Access" is off (we expect a failing `new UdpClient` that is caught, or VaM's own refusal/prompt; both are outside our code, and the file channel remains the fallback), and whether a firewall prompt appears for loopback UDP.

**Token mask by focus.** `InputField.isFocused` is standard Unity UI (the same `UnityEngine.UI.InputField` class as E14), read each frame while the field exists; added to `tools/stubs/UnityStubs.cs`. There is no audited end-edit event, so the plugin polls. No VaM plugin evidence for `isFocused` itself: TODO(verify) in VaM 1.22 that a VaM text field reports focus. The old 4-second timer is gone.

**First-run note.** Only audited kinds: `UiPage.Header` (CreateTextField), `TextInput` (E14), `Button`. The button label is changed with `UIDynamicButton.buttonText.text` (vam-timeline `MocapScreen.cs` at commit d6f7177c: `_importRecordedUI.buttonText.text = ...`; `button.label` is the other, equally evidenced way). The field's storable is not registered with VaM, so it never reaches a scene.

## Version 29 (19.11.2026): local engines, Silero, voice barge-in

- **No new VaM API.** Everything runs in the companion app. The plugin only gets one more entry in the existing **VAD engine** `JSONStorableStringChooser` ("Silero", mapped to `mic.vad_engine: "silero"`; the same code path as the other three entries).
- **Plain evidence facts (19.11.2026):** `NamedAudioClip.clipToPlay` is used by Timeline (`CustomTrigger.cs` L86-92, commit 54e2942); `AudioSourceControl.clipLoudness` is used in Dollmaster (E1, `ExpressionController.cs` L84-141, commit e606e78). AIBody uses neither.

## Version 28 (19.11.2026): several figures, Channel field (removed again in version 30)

- Version 28 added a Channel field and several figures in one app. **Removed in version 30** (Leon, 19.11.2026: one companion app controls exactly one character). Nothing from it remains in the code; the audit entry stays only as history: it used no VaM API beyond the existing `UiPage.TextInput` pattern (E9, E24).

## Version 27 (19.11.2026): emotions, personas, memory

- **No new VaM API.** Plugin additions are the existing evidenced kinds only: `JSONStorableStringChooser` (like "Voice", refreshed with `choices = ...`: E9, E24, E25), `JSONStorableBool`, `UiPage.Popup` / `Toggle` / `Button`, the existing event path. The new expression preset `listening` uses morph names the other presets already use (`Brow Inner Up`, `Mouth Smile Simple`); the stubs got nothing new.
- **Files:** persona and memory files are written and read only by the companion app (ordinary files below `Saves/PluginData/AIBody/personas/`); the plugin never touches them (FileManagerSecure rule unaffected).
- **xAI Responses API:** the memory summary uses `POST /v1/responses` with `stream: false` and `store: false` (documented parameter, docs.x.ai comparison table "store: control server-side storage (default true)"). TODO(verify): the real model answers a plain JSON array when asked for exactly that (the app takes the first `[...]` in the answer and drops everything that is not a string).

## Version 26 (19.11.2026): natural gaze, blinking, scene hooks

- **Natural gaze** (`GazeController`): no new VaM call, only more of the evidenced Unity math: `Vector3` minus (Glance L1278), `magnitude` (L1279), `normalized` (L1280), `Vector3.Cross` (L1554), `Vector3.up` (L1158), `Random.Range` (L1179). The eyes are driven exactly like the fixed gaze targets (E12 / E28). TODO(verify): that the offsets look natural (about 3 degrees of small movement, glances 35 degrees to the side, "thinking" glance 18 degrees up).
- **Life detection:** `GetStorableIDs()` entries containing `MacGruber` and ending in `Gaze` (the gaze) or `Eyes` (the blinking) make AIBody stay out (E29 for the class names; E8 / E28 for the id match). TODO(verify): the real storable ids in a Life scene (the Hub package could name its classes differently from the vam-community copies).
- **Blinking** (`BlinkController`, off by default): E29 as above. The same sequence MacGruber's Eyes plugin uses: read `blinkEnabled`, set it to false, drive "Eyes Closed". AIBody puts both back on release and gives up if someone sets `blinkEnabled` to true again. TODO(verify): the morph name on the male figure and that VaM's own blink does not write the morph while `blinkEnabled` is false.
- **Scene hooks:** `JSONStorableBool` "AI speaking" / "User speaking", `JSONStorableString` "Scene event" and `JSONStorableAction`s ("Look at client" ... "Blink now", "Expression: <name>", "Gesture: <name>", one per entry known at start, at most 30 each), registered with the plugin so VaM's trigger UI, Timeline and other plugins can see them; `isStorable` / `isRestorable` false as Glance does for its CloseEyes slider (E12 L66). TODO(verify): that a trigger's "Set String" can reach the "Scene event" param of a plugin on the Person (E13 reads and sets such params from outside; the trigger-side listing of plugin storables is VaM behaviour, not read from source).
- **Not built, evidence collected for later (not used, not in the stubs):** VaM's own trigger UI with outgoing triggers. Timeline `CustomTrigger : Trigger` (vam-timeline `src/AtomAnimations/Animatables/Triggers/CustomTrigger.cs` L9, `triggerActionsParent`, `InitTriggerUI()`, `OpenTriggerActionsPanel()` in `TriggersTrackAnimationTargetFrameComponent.cs` L136-141, prefabs from AssetBundle `z_ui2` in `VamPrefabFactory.cs` L24-27) and MacGruber_Utils `EventTrigger` (a Hub plugin that embeds a copy: [vammoan.cs](https://gist.github.com/rutheniumm/c201dd5e6b2bbf56c548ec80ff4546b9) `new EventTrigger(this, name)` L1675, `SimpleTriggerHandler.LoadAssets()` L1724, `GetJSON` / `LateRestoreFromJSON` L2508-2528, `SimpleTriggerHandler` L2601, `EventTrigger : Trigger` L2692). `MacGruber_Utils.cs` is CC BY (credit required). Both need `AssetBundleManager` and coroutines, which this audit does not cover yet.

- **Bold control names in the left info fields (20.11.2026):** Unity rich text `<b>...</b>` in the value of the existing
  info `JSONStorableString` shown by `CreateTextField` (E35; `<color=red>` was already used in the same field). No new API.
