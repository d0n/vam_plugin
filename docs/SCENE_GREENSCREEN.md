# AI-Buddy example scene (and greenscreen background)

Status 21.11.2026 (version 42) · Leon's scene of 21.11.2026 18:27 (his two-character AI-Buddy scene with the people renamed `AI` and `Client`), clothing and looks kept · File: [`examples/scenes/AI-Buddy.json`](../examples/scenes/AI-Buddy.json) with preview [`examples/scenes/AI-Buddy.jpg`](../examples/scenes/AI-Buddy.jpg) · in the package: `Saves/scene/AIBody/AI-Buddy.json` and `Saves/scene/AIBody/AI-Buddy.jpg`

Two people. AIBody is only on the male `Client` (the user's own character; version 42, Leon 18:27) and drives the female `AI`: it finds the Person atom named `AI` and speaks, poses and moves with it (before: on `BryanGosling`, version 41, and on the female `Person`). Dollmaster, Improved PoV and the Dollmaster animation/audio atoms are not in the scene (they conflict with AIBody and were the likely cause of a complete load hang). Explicit genital morphs are removed (version 42: `OpenXXL` on `Client` again). **Set background color** is on (#00FF00).

1. Atom `AI` (Person, female: `geometry.character` = `Female 1`), right of the origin. No plugin: AIBody on `Client` controls it. Clothing: Pro Court Short F (`EuLinRabei.ProCourt_Outfit.3`) and Nico Tanktop (`paledriver.Nico.2`). Hair: Long Backswept Pony (`NoStage3.Hair_Long_Backswept_Pony.1`) plus a loose scamp THEV hair (see local content below). Face and body morphs from the original look, including package morphs from `Ark1F1.Olivia_McAllister.1`, `Wolverine333.LAUREN_4.1`, `mopedlampe.Morwyn.1`, `particle pinnacle.missing_morphs.1` and the breath morph `Breath1` from `KdollMASTA.KDoll_Mk10.1` (AIBody's default **Breath morph**).
2. Atom `Client` (Person, male: `geometry.character` = `Male 4`), left of the origin. Plugins tab of `Client`: **AIBody** `d0n.AIBody.52:/Custom/Scripts/d0n/AIBody/AIBody.cslist` (inside the package: `SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist`) with saved values `Set background color` = true, `Background color` = #00FF00, `AI gender/body` = Female and `Your character gender` = Male. Leon's other saved plugin values of that session (Verbose log, Settings initialized, Memory, Speech delay timer 5 s, xai engines, AI mode auto, Persona Anna, Idle default pose `fight pose20`) are not in the shipped scene: with `Settings initialized` saved, a new user's config.json would never be applied. Clothing: police pants (`Molmark.Police_uniform.2`) and a loose PositiveResult hoodie. Built-in hair entry `No Hair`. Face texture and the Bryan Gosling morph are loose local files.
3. `[CameraRig]`, `WindowCamera`, `PlayerNavigationPanel`, `CoreControl`. No scene plugin.

Roles:
- `AI` is the AI's body: AIBody on `Client` speaks with its head audio, poses it and moves it (the info field says "AIBody 52 on 'Client', AI person 'AI'"). One character only: do not add AIBody to `AI` as well.
- `Client` (male) is your own figure and carries the plugin. Microphone, push-to-talk and text input run through the companion app and the tab *Client Character*. **Reset poses** (tab AI Character > Poses) puts `AI` back where the scene placed it, then `Client` half a second later, so they do not collide.

**Background / greenscreen:** the packaged scene ships with **Set background color** on (default color #00FF00). Switch it off in tab Config > Background if you want the room sky instead. VaM does **not** make the background transparent. VaM only shows a uniform color. Transparency is made by the headset or the streaming program through a chroma key on exactly the same color, e.g. Quest 3 with Virtual Desktop. The companion's first-start setup can still write a loose copy of the scene with the toggle on or off from your answer.

## Choose what to use

- **Scene:** ONE download of `d0n.AIBody.52.var` plus the third-party packages listed below: the scene is inside the package at `Saves/scene/AIBody/AI-Buddy.json` (plugin entry `SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist` = the plugin of the same package, so it never points at another version) with the preview `Saves/scene/AIBody/AI-Buddy.jpg` (same base name: VaM's Load Scene menu can show the thumbnail). VaM's scene browser (main menu **Open Scene** / **Load Scene**) lists scenes of packages that lie below `Saves/scene/`: open the package `d0n.AIBody.52` (package filter / shortcut on the left of the browser), folder `AIBody`, file **AI-Buddy**. TODO(verify) in VaM 1.22: the thumbnail in the list and a clean load (T46).
- Optional loose copy (what the companion's setup writes when you choose Scene there, with your background answer): put `AI-Buddy.json` and `AI-Buddy.jpg` at `<VaM main folder>/Saves/scene/AIBody/`; the JSON references `d0n.AIBody.52:/Custom/Scripts/d0n/AIBody/AIBody.cslist` (SELF: only works inside a package).
- **Plugin:** add AIBody to a Person of your own scene (Plugins > Add Plugin, or the plugin preset). Switch **Set background color** on in tab Config if you want the plain color; the companion's setup does it for you when you answered yes there.

## Third-party packages (`meta.json` dependencies)

These packages stay referenced in the scene, so they are declared in `packaging/meta.json` `dependencies` in VaM's format (package id, `licenseType` when a Hub lookup found one, nested `dependencies`). VaM can then show a missing-package notice. License types were read from the Hub `getResourceDetail` API on 21.11.2026; the packages themselves were not downloaded. Three packages were not on the Hub, so `licenseType` is omitted rather than invented. Our own package `licenseType` stays `FC` and is not changed.

- `Ark1F1.Olivia_McAllister.1` — not found on the Hub (a later, different package `Ark1F1.Olivia_Look_+_Futa_Final_Update.1` exists; the scene still points at this older name)
- `EuLinRabei.ProCourt_Outfit.3` — CC BY-SA
- `KdollMASTA.KDoll_Mk10.1` — not found on the Hub (looked up 21.11.2026, version 42; the creator's packages are no longer listed there). Only the `Breath1` morph of `AI` uses it; without it AIBody's breathing reports the missing morph and you can pick another in **Breath morph**.
- `Molmark.Police_uniform.2` — CC BY
- `NoStage3.Hair_Long_Backswept_Pony.1` — CC BY
- `Wolverine333.LAUREN_4.1` — CC BY
- `mopedlampe.Morwyn.1` — CC BY
- `paledriver.Nico.2` — CC BY-NC-ND
- `particle pinnacle.missing_morphs.1` — not found on the Hub

`WeebU.Amy_Demon_futa_scenes.2` (Improved PoV) and `JoyBoy.Andi_Collection.2` (the AG2_M_OpenXXL genital morph) are no longer referenced and are not dependencies.

## Needs local content

The following items need local content (loose files that this package does not ship):

These paths are loose files under `Custom/` or `Saves/`, not inside a `.var`. They cannot be redistributed with this package. They resolve on the author's PC; elsewhere VaM skips the missing morph, texture, hair or clothing and still loads the scene. This list needs local content:

- `Custom/Atom/Person/Morphs/female/AUTO/FHMGiselle.vmi`
- `Custom/Atom/Person/Morphs/female/AUTO/FHMShaneka.vmi`
- `Custom/Atom/Person/Morphs/female/AUTO/PHMGiselleEyelashes.vmi`
- `Custom/Atom/Person/Morphs/female/CTRLFitness.vmi`
- `Custom/Atom/Person/Morphs/female/Claire 0401 Alt-cc2d3570.vmi`
- `Custom/Atom/Person/Morphs/male/AUTO/RG InOut.vmi`
- `Custom/Atom/Person/Morphs/male/AUTO/RG Side2Side.vmi`
- `Custom/Atom/Person/Morphs/male/Bryan Gosling.vmi`
- `Custom/Atom/Person/Textures/N3DX/0329/0329_face v5.jpg`
- `Custom/Atom/Person/Textures/N3DX/0329/0329_limbs.jpg`
- `Custom/Atom/Person/Textures/N3DX/0329/0329_torso.jpg`
- `Custom/Atom/Person/Textures/Tan Lines (Decals)/Base Female/6%/String Bikini (select)/genitalsDecal.png`
- `Custom/Atom/Person/Textures/Tan Lines (Decals)/Base Female/6%/String Bikini (select)/torsoDecal.png`
- `Custom/Clothing/Male/PositiveResult/HoodieMale/HoodieMale_Down.vam`
- `Custom/Hair/Female/scamp/Samples/THEV.vam`
- `Saves/scene/Tiseb29/RetroGlide/RetroSlinger_RyanG/BryanGoslingFace.jpg`

## What you need

- `d0n.AIBody.52.var` — into `<VaM main folder>/AddonPackages/`. The third-party packages above, if you want the full look. The loose local files above, if you have them.

## Checking

1. Open the scene (see above) and confirm the thumbnail in the Load Scene list. If a listed dependency is missing, VaM should mention it rather than hang. Select `Client` > tab **Plugins**: `SELF:/Custom/Scripts/d0n/AIBody/AIBody.cslist` (or the package path); the plugin's info field starts with "AIBody 52 on 'Client', AI person 'AI'"; tab **Config** > Background: Set background color ON, color #00FF00 unless you changed it. `AI` (the female) has no AIBody plugin.
2. Start the companion app (see README). For a greenscreen, keep Set background color on and set the chroma key in the headset to the same color.

Afterwards please send a screenshot (the Load Scene list with the thumbnail, the scene, and the plugin's tab Config) and all red lines with "AIBody:" from the error log. Test steps: `docs/TEST_PROTOCOL.md` T38 (background) and T46 (AI-Buddy thumbnail, plugin, clothing, background on).

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
