# Szenen-Vorlage „AIBody Green Screen“

Stand 19.11.2026 (Version 24) · Wunsch von Leon vom 17.11.2026 (zwei Figuren: 22:30) · Datei: [`examples/scenes/AIBody_GreenScreen.json`](../examples/scenes/AIBody_GreenScreen.json)

Leere Szene ohne Raum mit:

1. Atom `AI Character` (Person, weiblich: `geometry.character` = `Female 3`), Position (0, 0, 0), Drehung 0°. Plugins-Tab der Person: **AIBody** `d0n.AIBody.24:/Custom/Scripts/d0n/AIBody/AIBody.cslist`.
2. Atom `Client Character` (Person, männlich: `geometry.character` = `Male 1`), Position (0, 0, 1,2), Drehung 180° um die Hochachse, also der KI-Figur zugewandt, 1,2 m Abstand. Plugins-Tab der Person: **Camera Background Color** von Sally `Sally.CameraBackgroundColor.7:/Custom/Scripts/Sally/CameraBackgroundColor/CameraBackgroundColor.cs`, Farbe **#00FF00** (HSV h 0,3333333, s 1, v 1), „Show Skybox“ aus.
3. Zwei unsichtbare Lichter (InvisibleLight). Kein Boden, keine Wände, kein Szenen-Plugin.

Aussehen: nur VaMs eingebaute Standard-Figuren (`Female 3`, `Male 1`), keine Kleidung, Haare oder Looks aus Fremdpaketen festgelegt.

Rollen:
- `AI Character` ist der Körper der KI (AIBody).
- `Client Character` ist der sichtbare Körper des Nutzers und trägt das Hintergrund-Plugin. AIBody kennt kein Client-Atom: Mikrofon, Push-to-Talk und Texteingabe laufen weiter über die Begleit-App und den Tab *Client Character* im AIBody-Plugin auf der KI-Figur. Das Client-Atom hat kein AIBody-Plugin.

**Wichtig:** VaM macht den Hintergrund **nicht** durchsichtig. VaM zeigt nur eine gleichmäßig grüne Fläche. Durchsichtig (Passthrough) macht ihn erst die Brille bzw. das Streaming-Programm per Chroma-Key auf genau dieselbe Farbe #00FF00, z. B. Quest 3 mit Virtual Desktop. Am Desktop geht das z. B. mit einem externen Fenster-Chroma-Key-Skript (siehe Quellen).

## Was du brauchst

- `d0n.AIBody.24.var` – [Release v24](https://github.com/d0n/vam_plugin/releases/tag/v24)
- `Sally.CameraBackgroundColor.7.var` (Version 7, 6097 Bytes, VaM 1.22.0.3, keine Abhängigkeiten) – Hub: [Camera Background Color](https://hub.virtamate.com/resources/camera-background-color.24185/) von Sally (Sally Whitemane). Die Szene verlangt genau Version 7.

Beide Dateien nach `<VaM-Hauptordner>/AddonPackages/`.

## Einrichten

1. Szene speichern als `<VaM-Hauptordner>/Saves/scene/AIBody/AIBody_GreenScreen.json` (Ordner `AIBody` ggf. anlegen).
2. VaM starten > **Open Scene** > `Saves/scene/AIBody/AIBody_GreenScreen.json`.
3. **AIBody prüfen:** `AI Character` auswählen > Tab **Plugins**: `d0n.AIBody.24:/Custom/Scripts/d0n/AIBody/AIBody.cslist`.
4. **Camera Background Color prüfen:** `Client Character` auswählen > Tab **Plugins**: `Sally.CameraBackgroundColor.7:/…/CameraBackgroundColor.cs`. Im Plugin-Fenster: „Color“ Grün (R 0, G 255, B 0), „Show Skybox“ aus.
5. Das Plugin nicht zusätzlich als *Session Plugin* oder *Scene Plugin* laden; zwei Instanzen stören sich (das Plugin warnt: „multiple CameraBackgroundColor-Plugins loaded“).
6. Begleit-App starten (siehe README), in der Brille den Chroma-Key auf **#00FF00** stellen.

Bitte danach einen Screenshot (Szene plus Plugins-Tab beider Personen) und alle roten Zeilen mit „AIBody:“ oder „CameraBackgroundColor“ aus dem Error-Log schicken.

## Camera Background Color auf einem Person-Atom

Aus dem Quelltext von Version 7 (CC0, Paket vom Hub, sha256 `6327040e37a35d7130431b08864dfadf8cac865d208a88387e66d7e4bf8d4662`, am 17.11.2026 erneut geladen):
- `Init()` holt nur globale Objekte: `CameraTarget.centerTarget.targetCamera`, `SuperController.singleton.hiResScreenshotCamera` / `screenshotCamera`, das Atom vom Typ `WindowCamera` und `SkyshopLightController.singleton` (Skybox). Nichts davon hängt am Atom, auf dem das Plugin liegt.
- Der einzige Atom-Typ-Abgleich ist `containingAtom.type == "SessionPluginManager"` in `Start()` (nur dann wird `Saves/PluginData/CameraBackgroundColor/default.json` gelesen). Auf einer Person gilt die Farbe aus der Szene.
- `CheckForMultipleLoadedScripts()` sucht das Plugin auf allen Atomen und meldet „CameraBackgroundColor on atom: <Name>“ für andere Atome als CoreControl – der Autor rechnet also mit dem Plugin auf einem normalen Atom.
- Gespeicherte Parameter: `Color` (JSONStorableColor), `Show Skybox`, `OriginalSkyboxState`, `Render [Control + R] …`. Storable-ID auf der Person: `plugin#0_CameraBackgroundColor`.
- Folge: Auf einer Person sollte es genauso wirken wie als Szenen-Plugin. In VaM nicht getestet (TODO(verify)).

## Was belegt ist und was offen

Belegt am 17.11.2026 aus dem Original-Paket `Sally.CameraBackgroundColor.7.var` (vom Hub geladen, sha256 `6327040e37a35d7130431b08864dfadf8cac865d208a88387e66d7e4bf8d4662`, 6097 Bytes; nicht ins Repo übernommen):
- `meta.json`: `creatorName` „Sally“, `packageName` „CameraBackgroundColor“, `licenseType` „FC“, `programVersion` 1.22.0.3, keine Abhängigkeiten, `scriptReferenceVersionOption` „Exact“, Inhalt nur `Custom/Scripts/Sally/CameraBackgroundColor/CameraBackgroundColor.cs`. Beschreibung: „Changes the background color. The Skybox in Scene lighting setting must be disabled to see the color.“
- Quelltext (CC0): Klasse `public class CameraBackgroundColor : MVRScript` ohne Namespace, daher Storable-ID `plugin#0_CameraBackgroundColor`.
- Gespeicherte Parameter: `JSONStorableColor "Color"` (Standard Blau, RGB 0, 0, 1), `JSONStorableBool "Show Skybox"` (Standard aus), `JSONStorableBool "OriginalSkyboxState"` (merkt den Skybox-Zustand vor dem Laden), `JSONStorableBool "Render [Control + R] <color=#FF0000>(experimental)</color>"` (Standard an). „Debug messages“ wird nicht gespeichert.
- Das Plugin setzt die Hintergrundfarbe der Hauptkamera, der Screenshot-Kameras und der WindowCamera. Als Szenen-Plugin nimmt es die Farbe aus der Szene; die Datei `Saves/PluginData/CameraBackgroundColor/default.json` liest es nur als *Session Plugin*.
- Grün im VaM-Format `{"h":"0.3333333","s":"1","v":"1"}` ergibt RGB (0, 255, 0).
- Aufbau der Szenen-Datei: Werte als Text (E21 in `docs/API_AUDIT.md`). Plugin aus einem Paket als `PluginManager.plugins["plugin#0"] = "Paket.Version:/Pfad"`, Szenen-Plugins im `PluginManager` des Atoms `CoreControl`, Einstellungen in `plugin#0_<Klassenname>`, Farben als `{"h","s","v"}`. Belege: [ml-clone-test, EMPTY_SCENE_BLUE_HAIR.json @4d20126](https://github.com/RobQuistNL/ml-clone-test/blob/4d2012670deb75338f7d96e1443cdc651920c97d/examples/EMPTY_SCENE_BLUE_HAIR.json) und [vam-improved-pov, Empty.json @dea8570](https://github.com/acidbubbles/vam-improved-pov/blob/dea857067da496e7e19ae5af31088fdc5fa6fb53/scenes/Empty.json) (Lichtfarbe L272–276).

- Geschlecht/Figur: Storable `geometry` mit `character`. Belege: `"character": "Male 1"` in [OnePunchVAM/vam-story-builder, templates/packages/Guy.json @a4fa8df](https://github.com/OnePunchVAM/vam-story-builder/blob/a4fa8df7f2ff9c7d3a9291d98d4a626ccf4a17a6/templates/packages/Guy.json) (L1868–1869); `"character" : "Female 3"` in [acidbubbles/vam-leap-possess, scenes/Empty.json @9205ecd](https://github.com/acidbubbles/vam-leap-possess/blob/9205ecd97edbcf5eb7ac84e4e72fc7d933aefcbe/scenes/Empty.json) (L808–809); foto2vam setzt `Female 1` / `Male 1` ([Utils/Face/vam.py @047e1d3](https://github.com/ChrisTopherTa54321/foto2vam/blob/047e1d3e9eea07a7664b498cdc26a791381f5891/Utils/Face/vam.py) L221–232).

Offen (TODO(verify)), nur in VaM prüfbar:
- Ob VaM eine Szene ohne Kamera-, Navigations- und Raum-Atome ohne Rückfrage lädt und fehlende Standard-Atome selbst ergänzt.
- Ob die Personen in Blickrichtung +Z stehen, sich also mit 0° / 180° wirklich ansehen; Abstand 1,2 m und Licht-Positionen.
- Aussehen ohne festgelegte Kleidung/Haare (VaM-Standard der Figuren `Female 3` / `Male 1`).
- Camera Background Color auf einem Person-Atom (siehe oben).
- Grüne Farbsäume an Haaren und Rändern (Spill) hängen vom Chroma-Key der Brille ab.

## Quellen

- Hub: <https://hub.virtamate.com/resources/camera-background-color.24185/>
- Patreon-Spiegel (CC0): <https://www.patreon.com/posts/vam-camera-color-73037813>
- Der Quelltext nennt als Idee für den Render-Schalter den Hub-Thread „VD for passthrough“: <https://hub.virtamate.com/threads/vd-for-passthrough.43272/post-135631>
- Passthrough-Anleitung auf dem Hub: „How to use Passthrough in VAM (VR/AR)“ von thinoreos, <https://hub.virtamate.com/resources/how-to-use-passthrough-in-vam-vr-mixed-reality.37851/> (nicht gelesen)
- Desktop-Variante: <https://vamhub.net/resource/vam-desktop-chroma-passthrough-vamtual-girl-63459>
