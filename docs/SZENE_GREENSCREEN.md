# Szenen-Vorlage „AIBody Green Screen“

Stand 17.11.2026 · Wunsch von Leon vom 17.11.2026 · Datei: [`examples/scenes/AIBody_GreenScreen.json`](../examples/scenes/AIBody_GreenScreen.json)

Eine leere Szene ohne Raum mit:

1. einer Figur (Person-Atom), auf der **AIBody** im Plugins-Tab der Person geladen ist (`d0n.AIBody.7`),
2. dem Szenen-Plugin **Camera Background Color** von Sally, Farbe **#00FF00 (RGB 0, 255, 0)**,
3. zwei unsichtbaren Lichtern (InvisibleLight). Kein Boden, keine Wände, keine Objekte hinter der Figur.

**Wichtig:** VaM macht den Hintergrund **nicht** durchsichtig. VaM zeigt nur eine gleichmäßig grüne Fläche. Durchsichtig (Passthrough) macht ihn erst die Brille bzw. das Streaming-Programm per Chroma-Key auf genau dieselbe Farbe #00FF00, z. B. Quest 3 mit Virtual Desktop („VR Passthrough“ / Chroma Key). Am Desktop geht das z. B. mit einem externen Fenster-Chroma-Key-Skript (siehe Quellen).

## Was du brauchst

| Paket | Wo | Status |
|---|---|---|
| `d0n.AIBody.7.var` | [Release v0.7.0](https://github.com/d0n/vam_plugin/releases/tag/v0.7.0) | belegt |
| `Sally.CameraBackgroundColor.7.var` (Version 7, 6 KB, Lizenz FC, VaM 1.22.0.3, keine Abhängigkeiten) | Hub: [Camera Background Color](https://hub.virtamate.com/resources/camera-background-color.24185/) von Sally (Sally Whitemane) | belegt über die Hub-Daten |

Beide Dateien nach `<VaM-Hauptordner>/AddonPackages/`.

## Einrichten

1. Szene speichern als:
   `<VaM-Hauptordner>/Saves/scene/AIBody/AIBody_GreenScreen.json`
   (Ordner `AIBody` ggf. anlegen.)
2. VaM starten > **Open Scene** (Szene öffnen) > `Saves/scene/AIBody/AIBody_GreenScreen.json`.
3. **AIBody prüfen:** Figur (Person) auswählen > Tab **Plugins**. Dort muss `d0n.AIBody.7:/Custom/Scripts/d0n/AIBody/AIBody.cslist` stehen. Nicht unter *Session Plugins*.
4. **Camera Background Color prüfen** (offener Punkt, siehe unten): Menü **Scene Plugins**.
   - Steht dort ein roter Fehler oder ist das Plugin nicht geladen: Eintrag entfernen > **Add Plugin** > `AddonPackages > Sally.CameraBackgroundColor.7` > die angebotene `.cs`- bzw. `.cslist`-Datei wählen.
   - Im Plugin-Fenster die Farbe auf **R 0, G 255, B 0** stellen (in VaM-Farbwählern: H 0.333, S 1, V 1). Ohne Einstellung ist laut Nutzern Blau (0, 0, 255) voreingestellt.
5. **Skybox aus:** Tab **Scene Lighting** (CoreControl) > Skybox ausschalten. Sonst verdeckt der Himmel die Farbe (Hinweis vom Plugin-Autor).
6. Szene **speichern** (Save Scene). Dann schreibt VaM selbst den richtigen Plugin-Pfad, den Parameternamen und die Skybox-Einstellung in die Datei.
7. In der Brille den Chroma-Key auf **#00FF00** stellen.

Bitte danach einen Screenshot vom Fenster *Scene Plugins* (mit dem Plugin-Namen) und die gespeicherte Szenen-Datei oder ihren CoreControl-Abschnitt schicken. Damit werden die offenen Punkte in der Vorlage ersetzt.

## Was belegt ist und was offen

Belegt:
- Plugin, Autor, Paketname und Version: Hub-Daten zur Ressource 24185 (Titel „Camera Background Color“, Kurztext „Set any color as camera background.“, Datei `Sally.CameraBackgroundColor.7.var`, Lizenz FC). Der Patreon-Spiegel vom 8.10.2022 nennt CC0. Für das `.var` auf dem Hub gilt FC.
- Zweck und Skybox-Hinweis: [Patreon-Beitrag von Sally](https://www.patreon.com/posts/vam-camera-color-73037813) – „change the black background color in VAM to anything … useful for chroma keying … not affected by light … Make sure the skybox is disabled in the [Scene Lighting]-tab“.
- Szenen-Plugin, Standardfarbe Blau 0, 0, 255, keine Wände/Skybox: [VAM Desktop Chroma Passthrough (VAManon)](https://vamhub.net/resource/vam-desktop-chroma-passthrough-vamtual-girl-63459).
- Aufbau der Szenen-Datei: Werte als Text (`"true"`, `"0.5"`), siehe E21 in `docs/API_AUDIT.md`. Plugin aus einem Paket auf der Person als `PluginManager.plugins["plugin#0"] = "Paket.Version:/Custom/Scripts/…cslist"`, Szenen-Plugins im `PluginManager` des Atoms `CoreControl`, Plugin-Einstellungen in einem Storable `plugin#0_<Klassenname>`, Farben als `{"h","s","v"}` von 0 bis 1. Belege: [ml-clone-test, EMPTY_SCENE_BLUE_HAIR.json @4d20126](https://github.com/RobQuistNL/ml-clone-test/blob/4d2012670deb75338f7d96e1443cdc651920c97d/examples/EMPTY_SCENE_BLUE_HAIR.json) und [vam-improved-pov, Empty.json @dea8570](https://github.com/acidbubbles/vam-improved-pov/blob/dea857067da496e7e19ae5af31088fdc5fa6fb53/scenes/Empty.json) (Lichtfarbe L272–276).

Offen (TODO(verify)), in der Datei als `TODO_VERIFY…` markiert:
- **Pfad im Paket** (`Sally.CameraBackgroundColor.7:/Custom/Scripts/Sally/TODO_VERIFY_CameraBackgroundColor.cs`): geraten. Die Hub-Seite und der Download sind hinter einer Altersabfrage, die nicht stellvertretend bestätigt wurde. Das Paket wurde deshalb nicht geöffnet. Folge, solange nicht ersetzt: VaM meldet beim Laden einen Fehler für dieses Plugin, die übrige Szene lädt trotzdem (TODO(verify)).
- **Klassenname und Name des Farbparameters** (`plugin#0_TODO_VERIFY_ClassName`, `TODO_VERIFY_Background Color`): geraten. Ein falscher Eintrag wird vermutlich ignoriert; dann Farbe von Hand setzen (Schritt 4).
- **Skybox aus** steht nicht in der Datei: der Name der Einstellung in der Szenen-Datei ist nicht belegt. Von Hand ausschalten (Schritt 5) und speichern.
- Ob VaM eine Szene ohne Kamera-, Navigations- und Raum-Atome ohne Rückfrage lädt und fehlende Standard-Atome selbst ergänzt.
- Ob VaM 1.22 ohne Raum-Atome trotzdem einen Boden oder ein Raster zeigt.
- Licht-Positionen und Helligkeit; die Figur hat das Standard-Aussehen (keine Kleidung/Haare festgelegt).
- Grüne Farbsäume an Haaren und Rändern (Spill) hängen vom Chroma-Key der Brille ab.

## Quellen

- Hub: <https://hub.virtamate.com/resources/camera-background-color.24185/> (Altersabfrage; Daten über die Hub-Schnittstelle von VaM gelesen)
- Patreon-Spiegel (CC0): <https://www.patreon.com/posts/vam-camera-color-73037813>
- Passthrough-Anleitung auf dem Hub (nicht gelesen, Altersabfrage): „How to use Passthrough in VAM (VR/AR)“ von thinoreos, <https://hub.virtamate.com/resources/how-to-use-passthrough-in-vam-vr-mixed-reality.37851/>
- Desktop-Variante: <https://vamhub.net/resource/vam-desktop-chroma-passthrough-vamtual-girl-63459>
