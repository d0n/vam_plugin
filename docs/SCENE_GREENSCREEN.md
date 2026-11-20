# Scene template "AIBody Green Screen" (the "Scene" choice)

Status 20.11.2026 (version 36) · Leon's wish of 17.11.2026 (two people: 22:30), call of 20.11.2026 22:03 (Scene / Plugin, background color in the plugin) · File: [`examples/scenes/AIBody_GreenScreen.json`](../examples/scenes/AIBody_GreenScreen.json) · in the package: `Saves/scene/AIBody/AIBody_Example.json`

Empty scene without a room, a fixed anchor:

1. Atom `AI Character` (Person, female: `geometry.character` = `Female 3`), position (0, 0, 0), rotation 0°, root controller locked (`control`: `yPositionLock`, `xRotationLock`, `yRotationLock`, `zRotationLock` as in E21; `xPositionLock` / `zPositionLock` TODO(verify)). Plugins tab of the Person: **AIBody** `d0n.AIBody.36:/Custom/Scripts/d0n/AIBody/AIBody.cslist` with its saved values `Set background color` = true and `Background color` = #00FF00 (`{"h":"0.3333333","s":"1","v":"1"}`).
2. Atom `Client Character` (Person, male: `geometry.character` = `Male 1`), position (0, 0, 1.2), rotation 180° about the vertical axis, i.e. facing the AI character, 1.2 m apart. No plugin.
3. `[CameraRig]` (VRController) at the client's place and `useSceneLoadPosition` true: the player starts there (E21; TODO(verify)).
4. Two invisible lights (InvisibleLight). No floor, no walls, no scene plugin, no third-party package (the package's meta dependencies stay `{}`).

Look: only VaM's built-in standard figures (`Female 3`, `Male 1`), no clothes, hair or looks from third-party packages. Plain neutral background; green #00FF00 is the high-contrast chroma color.

Roles:
- `AI Character` is the AI's body (AIBody) and makes the background color (tab Config > Background).
- `Client Character` is the user's visible body. AIBody knows no client atom: microphone, push-to-talk and text input run through the companion app and the tab *Client Character* in the AIBody plugin on the AI character.

**Important:** VaM does **not** make the background transparent. VaM only shows a uniform color. Transparency is made by the headset or the streaming program through a chroma key on exactly the same color (default #00FF00), e.g. Quest 3 with Virtual Desktop. On the desktop this can be done, for example, with an external window chroma key script (see sources).

## Choose what to use

- **Scene:** ONE download is enough: the scene is inside `d0n.AIBody.36.var` at `Saves/scene/AIBody/AIBody_Example.json` (plugin entry `SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist` = the plugin of the same package, so it never points at another version). VaM's scene browser (main menu **Open Scene** / **Load Scene**) lists scenes of packages that lie below `Saves/scene/`: open the package `d0n.AIBody.36` (package filter / shortcut on the left of the browser), folder `AIBody`, file **AIBody_Example**; VaM shows it as `d0n.AIBody.36:/Saves/scene/AIBody/AIBody_Example.json`. TODO(verify) in VaM 1.22: the exact place in the browser (T39).
- Optional loose copy (release asset `AIBody_Example.json`, also what the companion's setup writes when you choose Scene there, with your background answer): put it at `<VaM main folder>/Saves/scene/AIBody/AIBody_Example.json`; it references `d0n.AIBody.36:/Custom/Scripts/d0n/AIBody/AIBody.cslist` (SELF: only works inside a package) and is listed in the scene browser's own folder `Saves/scene/AIBody`.
- **Plugin:** add AIBody to a Person of your own scene (Plugins > Add Plugin, or the plugin preset). Switch **Set background color** on in tab Config if you want the plain color; the companion's setup does it for you when you answered yes there.

## What you need

- `d0n.AIBody.36.var` – [release v36](https://github.com/d0n/vam_plugin/releases/tag/v36), into `<VaM main folder>/AddonPackages/`. Nothing else.

## Checking

1. Open the scene (see above). Select `AI Character` > tab **Plugins**: `d0n.AIBody.36:/Custom/Scripts/d0n/AIBody/AIBody.cslist`; plugin window > tab **Config** > Background: Set background color ON, green.
2. Start the companion app (see README), set the chroma key in the headset to the same color.

Afterwards please send a screenshot (the scene plus the plugin's tab Config) and all red lines with "AIBody:" from the error log. Test steps: `docs/TEST_PROTOCOL.md` T38-T41.

## How AIBody makes the background (version 36)

`src/AIBody/Background.cs`: the view camera `CameraTarget.centerTarget.targetCamera` clears to one color (`CameraClearFlags.SolidColor`, `backgroundColor`) and VaM's skybox is hidden (`SkyshopLightController.singleton`, "showSkybox"); every value is remembered and put back when the toggle goes off or the plugin is disabled / removed. Evidence E30-E32 in `docs/API_AUDIT.md`. Written for AIBody; the approach is the one Sally's plugin (below) takes, no code copied.

## Before version 36: Sally's Camera Background Color (history)

Up to version 35 the scene used Sally's Camera Background Color 7 (Hub package) on the Client Character. Version 36 removed it: the background is AIBody's own function now and the scene needs no other package. The analysis of 17.11.2026 stays for reference.

### Camera Background Color on a Person atom

From the source code of version 7 (CC0, package from the Hub, sha256 `6327040e37a35d7130431b08864dfadf8cac865d208a88387e66d7e4bf8d4662`, downloaded on 17.11.2026):
- `Init()` only fetches global objects: `CameraTarget.centerTarget.targetCamera`, `SuperController.singleton.hiResScreenshotCamera` / `screenshotCamera`, the atom of type `WindowCamera` and `SkyshopLightController.singleton` (skybox). None of this depends on the atom the plugin sits on.
- The only atom-type adjustment is `containingAtom.type == "SessionPluginManager"` in `Start()` (only then `Saves/PluginData/CameraBackgroundColor/default.json` is read). On a Person the color from the scene applies.
- `CheckForMultipleLoadedScripts()` searches for the plugin on all atoms and reports "CameraBackgroundColor on atom: <name>" for atoms other than CoreControl – the author expects the plugin on a normal atom.
- Stored parameters: `Color` (JSONStorableColor), `Show Skybox`, `OriginalSkyboxState`, `Render [Control + R] …`. Storable id on the Person: `plugin#0_CameraBackgroundColor`.
- Consequence: on a Person it should act just like a scene plugin. Not tested in VaM (TODO(verify)).

### What was covered

Taken on 17.11.2026 from the original package `Sally.CameraBackgroundColor.7.var` (downloaded from the Hub, sha256 `6327040e37a35d7130431b08864dfadf8cac865d208a88387e66d7e4bf8d4662`, 6097 bytes; not copied into the repo):
- `meta.json`: `creatorName` "Sally", `packageName` "CameraBackgroundColor", `licenseType` "FC", `programVersion` 1.22.0.3, no dependencies, `scriptReferenceVersionOption` "Exact", content only `Custom/Scripts/Sally/CameraBackgroundColor/CameraBackgroundColor.cs`. Description: "Changes the background color". The setting Skybox in Scene lighting must be disabled to see the color.
- Source code (CC0): class `public class CameraBackgroundColor : MVRScript` without a namespace, hence the storable id `plugin#0_CameraBackgroundColor`.
- Saved parameters: `JSONStorableColor "Color"` (default blue, RGB 0, 0, 1), `JSONStorableBool "Show Skybox"` (default off), `JSONStorableBool "OriginalSkyboxState"` (remembers the skybox state before loading), `JSONStorableBool "Render [Control + R] <color=#FF0000>(experimental)</color>"` (default on). Debug messages are not stored.
- The plugin sets the background color of the main camera, the screenshot cameras and the WindowCamera. As a scene plugin it takes the color from the scene; the file `Saves/PluginData/CameraBackgroundColor/default.json` is read only as a *session plugin*.
- Green in VaM's format `{"h":"0.3333333","s":"1","v":"1"}` gives RGB (0, 255, 0).
- Structure of the scene file: values as text (E21 in `docs/API_AUDIT.md`). A plugin from a package as `PluginManager.plugins["plugin#0"] = "package.version:/path"`, scene plugins in the `PluginManager` of the atom `CoreControl`, settings in `plugin#0_<class name>`, colors as `{"h","s","v"}`. Supporting documents: [ml-clone-test, EMPTY_SCENE_BLUE_HAIR.json @4d20126](https://github.com/RobQuistNL/ml-clone-test/blob/4d2012670deb75338f7d96e1443cdc651920c97d/examples/EMPTY_SCENE_BLUE_HAIR.json) and [vam-improved-pov, Empty.json @dea8570](https://github.com/acidbubbles/vam-improved-pov/blob/dea857067da496e7e19ae5af31088fdc5fa6fb53/scenes/Empty.json) (light color L272–276).
- Gender / figure: storable `geometry` with `character`. Evidence: `"character": "Male 1"` in [OnePunchVAM/vam-story-builder, templates/packages/Guy.json @a4fa8df](https://github.com/OnePunchVAM/vam-story-builder/blob/a4fa8df7f2ff9c7d3a9291d98d4a626ccf4a17a6/templates/packages/Guy.json) (L1868–1869); `"character" : "Female 3"` in [acidbubbles/vam-leap-possess, scenes/Empty.json @9205ecd](https://github.com/acidbubbles/vam-leap-possess/blob/9205ecd97edbcf5eb7ac84e4e72fc7d933aefcbe/scenes/Empty.json) (L808–809); foto2vam sets `Female 1` / `Male 1` ([Utils/Face/vam.py @047e1d3](https://github.com/ChrisTopherTa54321/foto2vam/blob/047e1d3e9eea07a7664b498cdc26a791381f5891/Utils/Face/vam.py) L221–232).

## Open (TODO(verify)), only testable in VaM

- Whether VaM loads a scene without navigation and room atoms without asking and adds missing standard atoms itself.
- Whether the people face the +Z direction, i.e. really look at each other at 0° / 180°; the 1.2 m distance and the light positions.
- The anchor: root controller locks, `[CameraRig]` + `useSceneLoadPosition` start position.
- The headset renders through `CameraTarget.centerTarget.targetCamera` (AIBody's background color).
- Look without fixed clothing / hair (VaM default of the figures `Female 3` / `Male 1`).
- Color fringes on hair and edges (spill) depend on the headset's chroma key.

## Sources

- Hub: <https://hub.virtamate.com/resources/camera-background-color.24185/>
- Patreon mirror (CC0): <https://www.patreon.com/posts/vam-camera-color-73037813>
- The source code mentions, as an idea for the render switch, the Hub thread "VD for passthrough": <https://hub.virtamate.com/threads/vd-for-passthrough.43272/post-135631>
- Passthrough guide on the Hub: "How to use Passthrough in VAM (VR/AR)" by thinoreos, <https://hub.virtamate.com/resources/how-to-use-passthrough-in-vam-vr-mixed-reality.37851/> (not read)
- Desktop variant: <https://vamhub.net/resource/vam-desktop-chroma-passthrough-vamtual-girl-63459>
