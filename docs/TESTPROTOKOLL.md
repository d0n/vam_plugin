# AIBody – Testprotokoll für den ersten Test in VaM 1.22 (ab v0.6.3, aktuell v0.7.2; T9 und die neuen Tab-Namen ab v0.7.2)

Ziel: die offenen „Muss jetzt“-Punkte, die nur in VaM prüfbar sind. Bitte jeden Punkt der Reihe
nach durchgehen und das Ergebnis eintragen (✅ / ❌ / unklar). Dauer: etwa 20 Minuten.

**Was ich bei jedem Punkt brauche**

- einen **Screenshot des Plugin-Fensters** (links das Statusfeld mit *Selbsttest*, *Live* und
  *Start-Protokoll*),
- alle **roten Zeilen mit „AIBody:“** aus dem Error-Log (VaM: Hauptmenü unten links *Show Errors*,
  oder die Fehlermeldung, die sich von selbst öffnet). Bitte als Text kopieren oder fotografieren.

**Vorbereitung**

- VaM schließen. In `<VaM-Hauptordner>/AddonPackages/` alle alten AIBody-Pakete löschen:
  `d0n.AIBody.1.var` bis `d0n.AIBody.8.var`, `d0n.AIBodySession.*`, `d0n.AIBodyPerson.*`,
  `d0n.AIBodyPerson2.*`. Lose Dateien unter `Custom/Scripts/d0n/AIBody/` ebenfalls entfernen.
- `d0n.AIBody.9.var` nach `<VaM-Hauptordner>/AddonPackages/` kopieren.
- Companion-App bereithalten (noch **nicht** starten):
  `python -m aibody_companion --vam-root "C:/VaM"` (Pfad zum eigenen VaM-Ordner anpassen).
  Für T9 vorher den xAI-Key setzen: `set XAI_API_KEY=xai-...` (cmd) bzw. `$env:XAI_API_KEY="xai-..."` (PowerShell).

---

## T1 – Alte Pakete entfernt, Laden aus der `.var`

1. VaM starten, eine Szene mit einer weiblichen Standard-Figur öffnen (oder neue Szene + Person).
2. Die Figur (Person-Atom) auswählen > Tab **Plugins** > **Add Plugin** >
   `AddonPackages > d0n.AIBody.7:/Custom/Scripts/d0n/AIBody/AIBody.cslist`.
   **Nicht** unter *Session Plugins* oder *Scene Plugins*.
3. Falls VaM fragt, ob Plugins aus dem Paket erlaubt werden sollen: erlauben und notieren, dass gefragt wurde.
4. **Open Custom UI** (Plugin-Fenster) öffnen.

Melden: Taucht in der Paketliste nur noch `d0n.AIBody.7` auf? Hat VaM nach Erlaubnis gefragt?
Screenshot des Fensters; rote „AIBody:“-Zeilen. Erwartet: *Selbsttest* „Person-Atom: ja“,
Start-Protokoll endet mit „Init fertig, keine Fehler.“

## T2 – Dateipfade: `GetFiles` → `ReadAllText` / `DeleteFile`

1. Companion-App starten (siehe oben).
2. Etwa 5 Sekunden warten.

Melden: Steht im *Selbsttest* „PluginData beschreibbar: ja“ und „Companion-App-Heartbeat: ja“?
Steht unter *Live* „Companion app: verbunden …“? Liegen in
`<VaM>/Saves/PluginData/AIBody/default/inbox/` dauerhaft Dateien herum (sollte leer bleiben)?
Gibt es Zeilen wie „Could not delete processed inbox file“? Gibt es
`<VaM>/Saves/PluginData/AIBody/config.json`?

## T3 – Kopf-Audio, Lippensync, `PlayNow`-Retry, Start/Ende

1. Im Fenster der Companion-App (Konsole) einen Satz tippen und Enter drücken, z. B. `Hallo, wie geht es dir?`.
2. Zuhören und auf den Mund schauen. Drei Sätze schnell hintereinander tippen (Warteschlange).

Melden: Hört man den Ton aus dem Kopf der Figur (die Test-Engine `tone` spielt einen Summton statt einer Stimme)? Bewegt sich der Mund (Lippensync)? Kommt der Ton
sofort oder erst nach 1–2 Sekunden? Werden die drei Sätze nacheinander gespielt? In der
Companion-App: erscheinen `speech_started`/`speech_ended` bzw. Fehler wie `audio_failed`
(bitte die Konsolenzeilen kopieren)? Steht im *Selbsttest* „Kopf-Audio (HeadAudioSource): ja“?

## T4 – Menü-Aktualisierung und Textfeld

Tab-Namen ab v0.7.2 (in v0.7.1 noch: Status, Verbindung, Engines, Mikrofon & PTT, Körper, Erweitert):

1. Tab **Client Character** (früher *Mikrofon & PTT*) öffnen > **Refresh device list** > Auswahl **Mic device** öffnen.
2. Tab **AI** (früher *Engines*) öffnen und die drei Auswahllisten öffnen; ins Feld **xAI key file** klicken und tippen.
3. Tab **Post** (früher *Verbindung*): ins Feld **Channel** klicken, `test` eintippen, Enter. Danach wieder `default`.
4. Tab **AI Character** (früher *Körper*): ins Feld **Breath morph** klicken und einen Buchstaben ändern, dann zurück.
5. Alle sieben Tabs einmal durchklicken (Voice Mode, AI, AI Character, Client Character, Post, Config, Erweitert).

Melden: Zeigt die Geräteliste die echten Mikrofone? Lässt sich in die Textfelder tippen? Ändert
sich nach `test` der Ordner unter *Live* auf `Saves/PluginData/AIBody/test`? Wechseln die Tabs
sauber (alte Elemente weg, keine doppelten)? Steht eine *WARNUNG „nur lesbar“* im Start-Protokoll?

## T5 – Pose-Speicher, Morph-Namen, Atem-Morph

1. Tab **AI Character** (v0.7.1: *Körper*): **Body control** und **Breathing** an; auf die Brust schauen. Unter *Live* die Zeile „Breath morph“ lesen.
2. In der Companion-App nacheinander tippen: `Hallo` (fröhlich + Nicken), `Nein` (traurig +
   Kopfschütteln), `Was machst du?` (nachdenklich + Kopfneigen). Die Test-Engine schickt Ausdruck
   und Geste automatisch mit. Auf Gesicht und Kopf achten.
3. **Pose-Speicher:** Companion-App beenden. Eine eigene Pose der Figur speichern (Figur > Tab
   *Pose* > Preset speichern, z. B. unter `Custom/Atom/Person/Pose/test.json`). Dann eine
   Textdatei `<VaM>/Saves/PluginData/AIBody/default/inbox/pose_test.json` anlegen mit dem Inhalt
   `{ "v": 3, "type": "pose", "id": "p-1", "path": "Custom/Atom/Person/Pose/test.json" }`
   (Pfad an die eigene Pose anpassen). Die Figur vorher etwas anders hinstellen.

Melden: Hebt und senkt sich die Brust? Steht unter *Live* „Breath morph: Breath1“ oder „not found“?
Ändert sich das Gesicht beim Sprechen (Lächeln, Augenbrauen)? Rote Zeilen mit „Morph not found“
bitte vollständig kopieren. Kommen Nicken/Kopfschütteln/Kopfneigen an? Springt die Figur in die gespeicherte Pose? Was
steht unter *Live* beim letzten Befehl, und was steht in der neuesten Datei in
`Saves/PluginData/AIBody/default/outbox/` (z. B. „Atom has no PosePresets storable“)?

## T6 – Hinzufügen, Entfernen, Speichern, Neu laden (Exceptions, FPS)

1. FPS-Anzeige einschalten (VaM: *User Preferences* > *Show FPS*), FPS ohne Plugin notieren.
2. Plugin wie in T1 hinzufügen, FPS notieren. Companion-App beenden (Strg+C), 20 s warten,
   *Live*/Selbsttest ansehen, App wieder starten, 10 s warten.
3. Szene speichern (*File* > *Save Scene*), Szene neu laden, Plugin-Fenster öffnen.
4. Plugin entfernen (Plugins-Tab > **X** am Eintrag), wieder hinzufügen.

Melden: FPS ohne / mit Plugin. Steht nach dem Beenden der App „GETRENNT“ und nach dem Neustart
wieder „verbunden“, ohne dass man etwas klickt? Sind die eigenen Einstellungen nach dem Neuladen
noch da? Rote Zeilen beim Entfernen, Speichern oder Neuladen? Wie viele Dateien liegen nach
einer Minute ohne App in `Saves/PluginData/AIBody/default/outbox/` (sollten höchstens ~20 sein)?

## T7 – Engine-Status (ab v0.7.0)

1. Companion-App läuft (ohne API-Keys).
2. Tab **AI** (v0.7.1: *Engines*) öffnen, bei **Text-to-speech** `elevenlabs` auswählen, 3 Sekunden warten.
3. Einen Satz in der Companion-App tippen.

Melden: Steht unter den Auswahllisten „Text-to-speech: elevenlabs – nicht konfiguriert: …“ und
„läuft stattdessen: tone (Fallback)“? Spricht die Figur trotzdem (Summton)? Steht unter *Live*
„Engines aktiv: STT null, LLM echo, TTS tone (Fallback …)“? Danach wieder `tone` auswählen.

---

## T8 – Realtime-Sprache und proaktives Sprechen (ab v0.7.1)

Braucht einen xAI-Key (Umgebungsvariable `XAI_API_KEY` oder `ai.xai.key_file` in `config.json`)
und am besten ein Headset.

1. Companion-App mit Key starten. Im Log der App sollte stehen: `Modus: auto -> realtime` und
   `Realtime: verbunden mit wss://api.x.ai/v1/realtime?model=grok-voice-latest`.
2. Im Plugin Tab **AI Character** (v0.7.1: *Engines*): **AI mode** steht auf `auto`; im Tab **AI** im Status
   „Modus: realtime – Realtime verbunden …“ und „Proaktiv: an, nach 90 s Stille“.
3. Etwas sagen (z. B. „Hallo, wie spät ist es?“). Die Figur soll nach kurzer Pause antworten,
   der Mund bewegt sich, die Uhrzeit stimmt ungefähr.
4. Während sie spricht, **Push-to-talk** drücken (oder mit Headset und eingeschaltetem
   **Voice barge-in (headphones)** einfach reinsprechen): Sie soll sofort verstummen.
5. **Proactive idle (s)** auf 20 stellen, 30 Sekunden still sein: Die Figur sagt von sich aus etwas
   (oder schweigt bewusst – dann steht im App-Log `Proactive: the AI chose to stay silent`).
6. **AI mode** auf `chain` stellen: Status zeigt „Modus: chain“; danach wieder `auto`.

Melden: die Zeilen 1–2 aus dem App-Log, wie lange es bis zur Antwort dauert (geschätzt), ob die
Antwort abgehackt klingt (Pausen zwischen den Stücken), ob Unterbrechen klappt, und alle Zeilen
mit `Realtime` oder `failed` aus dem App-Log.

---

## T9 – Ton im Spiel: Frage → Antwort hörbar (ab v0.7.2)

Ziel: Es soll einfach eine hörbare Antwort aus dem Kopf der Figur kommen. Körpersteuerung ist dafür
nicht nötig.

1. Tab **Voice Mode** > **Einfacher Q&A-Modus** (setzt AI mode `qa` und Body control aus; prüfen im
   Tab **AI Character**). **Speech volume** auf 1.
2. Tab **Voice Mode** > **Test-Ton abspielen** (spielt die Datei aus dem Paket, ohne Companion-App).
   Im Statusfeld unter *Live* steht `Audio: Lade: AIBodyTest.wav`, dann `Spreche: AIBodyTest.wav (1.5 s)`, dann `Fertig: …`.
3. Companion-App mit xAI-Key starten, dann **Test-Ton über Companion** (Datei aus
   `Custom/Sounds/AIBody/default/`). Unter *Live* steht `Audio-Ordner: …`.
4. In der Companion-Konsole `Hallo` tippen + Enter (gleicher Weg wie gesprochen, nur ohne Mikrofon).
   Unter *Live* erscheint `Letzte Runde: Frage (getippt): Hallo`, dann `Letzte Runde: Antwort (…, xai -> xai): …`,
   und die Figur spricht die Antwort (ein paar Sekunden Verzögerung sind normal).
5. Eine Frage ins Mikrofon sprechen. Erwartet: `Letzte Runde: Gehört: …`, dann die gesprochene Antwort.

Melden: Hört man bei 2, 3, 4 und 5 etwas? Was steht jeweils unter *Live* bei `Audio:`, `Audio-Ordner:`
und `Letzte Runde:`? Rote Zeilen (`Audio-Fehler: …`, `Sprachmodell-Fehler: …`, `Nichts verstanden …`)
bitte genau abschreiben, dazu die Ausgabe der Companion-Konsole.

- Wenn 2 klingt, 3 aber nicht: Die App wechselt nach etwa 15 s von selbst nach
  `Saves/PluginData/AIBody/default/audio/` und spielt den Ton noch einmal (rote Zeile „Audio-Ordner
  gewechselt“). Bitte melden, ob er dann klingt.
- Steht dort „ohne xAI-Key“: Key nicht gesetzt (gleiches Konsolenfenster wie die App?) oder im Tab
  **AI** eine Key-Datei eintragen.

**Ergebnis zurückschicken:** pro Punkt T1–T9 ✅/❌, die Screenshots und die roten „AIBody:“-Zeilen.
