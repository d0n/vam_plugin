# Scene template "AIBody Green Screen"

Status 19.11.2026 (version 30) · Leon's wish of 17.11.2026 (two people: 22:30) · File: [`examples/scenes/AIBody_GreenScreen.json`](../examples/scenes/AIBody_GreenScreen.json)

Empty scene without a room, with:

1. Atom `AI Character` (Person, female: `geometry.character` = `Female 3`), position (0, 0, 0), rotation 0°. Plugins tab of the Person: **AIBody** `d0n.AIBody.30:/Custom/Scripts/d0n/AIBody/AIBody.cslist`.
2. Atom `Client Character` (Person, male: `geometry.character` = `Male 1`), position (0, 0, 1.2), rotation 180° about the vertical axis, i.e. facing the AI character, 1.2 m apart. Plugins tab of the Person: **Camera Background Color** by Sally `Sally.CameraBackgroundColor.7:/Custom/Scripts/Sally/CameraBackgroundColor/CameraBackgroundColor.cs`, color **#00FF00** (HSV h 0.3333333, s 1, v 1), "Show Skybox" off.
3. Two invisible lights (InvisibleLight). No floor, no walls, no scene plugin.

Look: only VaM's built-in standard figures (`Female 3`, `Male 1`), no clothes, hair or looks from third-party packages.

Roles:
- `AI Character` is the AI's body (AIBody).
- `Client Character` is the user's visible body and carries the background plugin. AIBody knows no client atom: microphone, push-to-talk and text input run through the companion app and the tab *Client Character* in the AIBody plugin on the AI character. The client atom has no AIBody plugin.

**Important:** VaM does **not** make the background transparent. VaM only shows a uniform green area. Transparency (passthrough) is made first by the headset or the streaming program through a chroma key on exactly the same color #00FF00, e.g. Quest 3 with Virtual Desktop. On the desktop this can be done, for example, with an external window chroma key script (see sources).

## What you need

- `d0n.AIBody.30.var` – [release v30](https://github.com/d0n/vam_plugin/releases/tag/v30)
- `Sally.CameraBackgroundColor.7.var` (version 7, 6097 bytes, VaM 1.22.0.3, no dependencies) – Hub: [Camera Background Color](https://hub.virtamate.com/resources/camera-background-color.24185/) by Sally (Sally Whitemane). The scene asks for exactly version 7.

Put both files into `<VaM main folder>/AddonPackages/`.

## Setting up

1. Save the scene as `<VaM main folder>/Saves/scene/AIBody/AIBody_GreenScreen.json` (create the `AIBody` folder if necessary).
2. Start VaM > **Open Scene** > `Saves/scene/AIBody/AIBody_GreenScreen.json`.
3. **Check AIBody:** select `AI Character` > tab **Plugins**: `d0n.AIBody.30:/Custom/Scripts/d0n/AIBody/AIBody.cslist`.
4. **Camera Background Color:** select `Client Character` > tab **Plugins**: `Sally.CameraBackgroundColor.7:/…/CameraBackgroundColor.cs`. In the plugin window: "Color" green (R 0, G 255, B 0), "Show Skybox" off.
5. Do not additionally load the plugin as a *Session Plugin* or *Scene Plugin*; two instances interfere (the plugin warns: "multiple CameraBackgroundColor plugins loaded").
6. Start the companion app (see README), set the chroma key in the headset to **#00FF00**.

Afterwards please send a screenshot (the scene plus the Plugins tab of both people) and all red lines with "AIBody:" or "CameraBackgroundColor" from the error log.

## Camera Background Color on a Person atom

From the source code of version 7 (CC0, package from the Hub, sha256 `6327040e37a35d7130431b08864dfadf8cac865d208a88387e66d7e4bf8d4662`, downloaded on 17.11.2026):
- `Init()` only fetches global objects: `CameraTarget.centerTarget.targetCamera`, `SuperController.singleton.hiResScreenshotCamera` / `screenshotCamera`, the atom of type `WindowCamera` and `SkyshopLightController.singleton` (skybox). None of this depends on the atom the plugin sits on.
- The only atom-type adjustment is `containingAtom.type == "SessionPluginManager"` in `Start()` (only then `Saves/PluginData/CameraBackgroundColor/default.json` is read). On a Person the color from the scene applies.
- `CheckForMultipleLoadedScripts()` searches for the plugin on all atoms and reports "CameraBackgroundColor on atom: <name>" for atoms other than CoreControl – the author expects the plugin on a normal atom.
- Stored parameters: `Color` (JSONStorableColor), `Show Skybox`, `OriginalSkyboxState`, `Render [Control + R] …`. Storable id on the Person: `plugin#0_CameraBackgroundColor`.
- Consequence: on a Person it should act just like a scene plugin. Not tested in VaM (TODO(verify)).

## What is covered and what is open

Taken on 17.11.2026 from the original package `Sally.CameraBackgroundColor.7.var` (downloaded from the Hub, sha256 `6327040e37a35d7130431b08864dfadf8cac865d208a88387e66d7e4bf8d4662`, 6097 bytes; not copied into the repo):
- `meta.json`: `creatorName` "Sally", `packageName` "CameraBackgroundColor", `licenseType` "FC", `programVersion` 1.22.0.3, no dependencies, `scriptReferenceVersionOption` "Exact", content only `Custom/Scripts/Sally/CameraBackgroundColor/CameraBackgroundColor.cs`. Description: "Changes the background color". The setting Skybox in Scene lighting must be disabled to see the color.
- Source code (CC0): class `public class CameraBackgroundColor : MVRScript` without a namespace, hence the storable id `plugin#0_CameraBackgroundColor`.
- Saved parameters: `JSONStorableColor "Color"` (default blue, RGB 0, 0, 1), `JSONStorableBool "Show Skybox"` (default off), `JSONStorableBool "OriginalSkyboxState"` (remembers the skybox state before loading), `JSONStorableBool "Render [Control + R] <color=#FF0000>(experimental)</color>"` (default on). Debug messages are not stored.
- The plugin sets the background color of the main camera, the screenshot cameras and the WindowCamera. As a scene plugin it takes the color from the scene; the file `Saves/PluginData/CameraBackgroundColor/default.json` is read only as a *session plugin*.
- Green in VaM's format `{"h":"0.3333333","s":"1","v":"1"}` gives RGB (0, 255, 0).
- Structure of the scene file: values as text (E21 in `docs/API_AUDIT.md`). A plugin from a package as `PluginManager.plugins["plugin#0"] = "package.version:/path"`, scene plugins in the `PluginManager` of the atom `CoreControl`, settings in `plugin#0_<class name>`, colors as `{"h","s","v"}`. Supporting documents: [ml-clone-test, EMPTY_SCENE_BLUE_HAIR.json @4d20126](https://github.com/RobQuistNL/ml-clone-test/blob/4d2012670deb75338f7d96e1443cdc651920c97d/examples/EMPTY_SCENE_BLUE_HAIR.json) and [vam-improved-pov, Empty.json @dea8570](https://github.com/acidbubbles/vam-improved-pov/blob/dea857067da496e7e19ae5af31088fdc5fa6fb53/scenes/Empty.json) (light color L272–276).
- Gender / figure: storable `geometry` with `character`. Evidence: `"character": "Male 1"` in [OnePunchVAM/vam-story-builder, templates/packages/Guy.json @a4fa8df](https://github.com/OnePunchVAM/vam-story-builder/blob/a4fa8df7f2ff9c7d3a9291d98d4a626ccf4a17a6/templates/packages/Guy.json) (L1868–1869); `"character" : "Female 3"` in [acidbubbles/vam-leap-possess, scenes/Empty.json @9205ecd](https://github.com/acidbubbles/vam-leap-possess/blob/9205ecd97edbcf5eb7ac84e4e72fc7d933aefcbe/scenes/Empty.json) (L808–809); foto2vam sets `Female 1` / `Male 1` ([Utils/Face/vam.py @047e1d3](https://github.com/ChrisTopherTa54321/foto2vam/blob/047e1d3e9eea07a7664b498cdc26a791381f5891/Utils/Face/vam.py) L221–232).

Open (TODO(verify)), only testable in VaM:
- Whether VaM loads a scene without camera, navigation and room atoms without asking and adds missing standard atoms itself.
- Whether the people face the +Z direction, i.e. really look at each other at 0° / 180°; the 1.2 m distance and the light positions.
- Look without fixed clothing / hair (VaM default of the figures `Female 3` / `Male 1`).
- Camera Background Color on a Person atom (see above).
- Green color fringes on hair and edges (spill) depend on the headset's chroma key.

## Sources

- Hub: <https://hub.virtamate.com/resources/camera-background-color.24185/>
- Patreon mirror (CC0): <https://www.patreon.com/posts/vam-camera-color-73037813>
- The source code mentions, as an idea for the render switch, the Hub thread "VD for passthrough": <https://hub.virtamate.com/threads/vd-for-passthrough.43272/post-135631>
- Passthrough guide on the Hub: "How to use Passthrough in VAM (VR/AR)" by thinoreos, <https://hub.virtamate.com/resources/how-to-use-passthrough-in-vam-vr-mixed-reality.37851/> (not read)
- Desktop variant: <https://vamhub.net/resource/vam-desktop-chroma-passthrough-vamtual-girl-63459>
