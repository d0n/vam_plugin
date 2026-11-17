# Szenen-Vorlage „AIBody Green Screen“

Stand 17.11.2026 · Wunsch von Leon vom 17.11.2026 · Datei: [`examples/scenes/AIBody_GreenScreen.json`](../examples/scenes/AIBody_GreenScreen.json)

Eine leere Szene ohne Raum mit:

1. einer Figur (Person-Atom), auf der **AIBody** im Plugins-Tab der Person geladen ist (`d0n.AIBody.11`),
2. dem Szenen-Plugin **Camera Background Color** von Sally, Farbe **#00FF00 (RGB 0, 255, 0)**,
3. zwei unsichtbaren Lichtern (InvisibleLight). Kein Boden, keine Wände, keine Objekte hinter der Figur.

**Wichtig:** VaM macht den Hintergrund **nicht** durchsichtig. VaM zeigt nur eine gleichmäßig grüne Fläche. Durchsichtig (Passthrough) macht ihn erst die Brille bzw. das Streaming-Programm per Chroma-Key auf genau dieselbe Farbe #00FF00, z. B. Quest 3 mit Virtual Desktop („VR Passthrough“ / Chroma Key). Am Desktop geht das z. B. mit einem externen Fenster-Chroma-Key-Skript (siehe Quellen).

## Was du brauchst

| Paket | Wo |
|---|---|
| `d0n.AIBody.11.var` | [Release v0.7.4](https://github.com/d0n/vam_plugin/releases/tag/v0.7.4) |
| `Sally.CameraBackgroundColor.7.var` (Version 7, 6 KB, Lizenz FC, VaM 1.22.0.3, keine Abhängigkeiten) | Hub: [Camera Background Color](https://hub.virtamate.com/resources/camera-background-color.24185/) von Sally (Sally Whitemane) |

Beide Dateien nach `<VaM-Hauptordner>/AddonPackages/`. Die Szene verlangt genau Version 7 von Sallys Paket (das Paket ist auf „Exact“ gestellt).

## Einrichten

1. Szene speichern als:
   `<VaM-Hauptordner>/Saves/scene/AIBody/AIBody_GreenScreen.json`
   (Ordner `AIBody` ggf. anlegen.)
2. VaM starten > **Open Scene** (Szene öffnen) > `Saves/scene/AIBody/AIBody_GreenScreen.json`.
3. **AIBody prüfen:** Figur (Person) auswählen > Tab **Plugins**. Dort muss `d0n.AIBody.11:/Custom/Scripts/d0n/AIBody/AIBody.cslist` stehen. Nicht unter *Session Plugins*.
4. **Camera Background Color prüfen:** Menü **Scene Plugins**. Dort steht `Sally.CameraBackgroundColor.7:/Custom/Scripts/Sally/CameraBackgroundColor/CameraBackgroundColor.cs`. Im Plugin-Fenster: Farbwähler „Color“ auf Grün (R 0, G 255, B 0), Schalter „Show Skybox“ aus. Beides ist in der Szene schon so eingestellt.
5. **Skybox:** schaltet das Plugin beim Laden selbst aus (Schalter „Show Skybox“, aus = Skybox aus). Wird das Plugin deaktiviert oder entfernt, stellt es die Skybox auf den vorherigen Zustand zurück und den Hintergrund auf Schwarz.
6. Nicht zusätzlich als *Session Plugin* laden. Zwei Instanzen stören sich; das Plugin warnt dann selbst („multiple CameraBackgroundColor-Plugins loaded“).
7. In der Brille den Chroma-Key auf **#00FF00** stellen.

Bitte danach einen Screenshot (Szene plus Fenster *Scene Plugins*) und alle roten Zeilen mit „AIBody:“ oder „CameraBackgroundColor“ aus dem Error-Log schicken.

## Was belegt ist und was offen

Belegt am 17.11.2026 aus dem Original-Paket `Sally.CameraBackgroundColor.7.var` (vom Hub geladen, sha256 `6327040e37a35d7130431b08864dfadf8cac865d208a88387e66d7e4bf8d4662`, 6097 Bytes; nicht ins Repo übernommen):
- `meta.json`: `creatorName` „Sally“, `packageName` „CameraBackgroundColor“, `licenseType` „FC“, `programVersion` 1.22.0.3, keine Abhängigkeiten, `scriptReferenceVersionOption` „Exact“, Inhalt nur `Custom/Scripts/Sally/CameraBackgroundColor/CameraBackgroundColor.cs`. Beschreibung: „Changes the background color. The Skybox in Scene lighting setting must be disabled to see the color.“
- Quelltext (CC0): Klasse `public class CameraBackgroundColor : MVRScript` ohne Namespace, daher Storable-ID `plugin#0_CameraBackgroundColor`.
- Gespeicherte Parameter: `JSONStorableColor "Color"` (Standard Blau, RGB 0, 0, 1), `JSONStorableBool "Show Skybox"` (Standard aus), `JSONStorableBool "OriginalSkyboxState"` (merkt den Skybox-Zustand vor dem Laden), `JSONStorableBool "Render [Control + R] <color=#FF0000>(experimental)</color>"` (Standard an). „Debug messages“ wird nicht gespeichert.
- Das Plugin setzt die Hintergrundfarbe der Hauptkamera, der Screenshot-Kameras und der WindowCamera. Als Szenen-Plugin nimmt es die Farbe aus der Szene; die Datei `Saves/PluginData/CameraBackgroundColor/default.json` liest es nur als *Session Plugin*.
- Grün im VaM-Format `{"h":"0.3333333","s":"1","v":"1"}` ergibt RGB (0, 255, 0).
- Aufbau der Szenen-Datei: Werte als Text (E21 in `docs/API_AUDIT.md`). Plugin aus einem Paket als `PluginManager.plugins["plugin#0"] = "Paket.Version:/Pfad"`, Szenen-Plugins im `PluginManager` des Atoms `CoreControl`, Einstellungen in `plugin#0_<Klassenname>`, Farben als `{"h","s","v"}`. Belege: [ml-clone-test, EMPTY_SCENE_BLUE_HAIR.json @4d20126](https://github.com/RobQuistNL/ml-clone-test/blob/4d2012670deb75338f7d96e1443cdc651920c97d/examples/EMPTY_SCENE_BLUE_HAIR.json) und [vam-improved-pov, Empty.json @dea8570](https://github.com/acidbubbles/vam-improved-pov/blob/dea857067da496e7e19ae5af31088fdc5fa6fb53/scenes/Empty.json) (Lichtfarbe L272–276).

Offen (TODO(verify)), nur in VaM prüfbar:
- Ob VaM eine Szene ohne Kamera-, Navigations- und Raum-Atome ohne Rückfrage lädt und fehlende Standard-Atome selbst ergänzt.
- Ob VaM 1.22 ohne Raum-Atome trotzdem einen Boden oder ein Raster zeigt.
- Licht-Positionen und Helligkeit; die Figur hat das Standard-Aussehen (keine Kleidung/Haare festgelegt).
- Grüne Farbsäume an Haaren und Rändern (Spill) hängen vom Chroma-Key der Brille ab.

## Quellen

- Hub: <https://hub.virtamate.com/resources/camera-background-color.24185/>
- Patreon-Spiegel (CC0): <https://www.patreon.com/posts/vam-camera-color-73037813>
- Der Quelltext nennt als Idee für den Render-Schalter den Hub-Thread „VD for passthrough“: <https://hub.virtamate.com/threads/vd-for-passthrough.43272/post-135631>
- Passthrough-Anleitung auf dem Hub: „How to use Passthrough in VAM (VR/AR)“ von thinoreos, <https://hub.virtamate.com/resources/how-to-use-passthrough-in-vam-vr-mixed-reality.37851/> (nicht gelesen)
- Desktop-Variante: <https://vamhub.net/resource/vam-desktop-chroma-passthrough-vamtual-girl-63459>
