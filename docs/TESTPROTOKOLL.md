# AIBody – Testprotokoll für den ersten Test in VaM 1.22 (ab v0.6.3, aktuell v0.7.3; T9 ab v0.7.2, T10 ab v0.7.3, Menü-Aufbau ab Version 15)

Ziel: die offenen „Muss jetzt“-Punkte, die nur in VaM prüfbar sind. Bitte jeden Punkt der Reihe
nach durchgehen und das Ergebnis eintragen (✅ / ❌ / unklar). Dauer: etwa 20 Minuten.

**Was ich bei jedem Punkt brauche**

- einen **Screenshot des Plugin-Fensters** (links das Statusfeld mit *Self-test*, *Live* und
  *Startup log*),
- alle **roten Zeilen mit „AIBody:“** aus dem Error-Log (VaM: Hauptmenü unten links *Show Errors*,
  oder die Fehlermeldung, die sich von selbst öffnet). Bitte als Text kopieren oder fotografieren.

**Vorbereitung**

- VaM schließen. In `<VaM-Hauptordner>/AddonPackages/` alle alten AIBody-Pakete löschen:
  `d0n.AIBody.1.var` bis `d0n.AIBody.23.var`, `d0n.AIBodySession.*`, `d0n.AIBodyPerson.*`,
  `d0n.AIBodyPerson2.*`. Lose Dateien unter `Custom/Scripts/d0n/AIBody/` ebenfalls entfernen.
- `d0n.AIBody.24.var` nach `<VaM-Hauptordner>/AddonPackages/` kopieren.
- Companion-App bereithalten (noch **nicht** starten):
  `python -m aibody_companion --vam-root "D:\VaM"` (Pfad zum eigenen VaM-Ordner anpassen).
  Für T9 den xAI-Key im Plugin eintragen (Tab **Voice** > Feld **XAI API Token**, ab Version 21) oder vor dem Start setzen: `set XAI_API_KEY=xai-...` (cmd) bzw. `$env:XAI_API_KEY="xai-..."` (PowerShell); das Feld gewinnt.

---

## T1 – Alte Pakete entfernt, Laden aus der `.var`

1. VaM starten, eine Szene mit einer weiblichen Standard-Figur öffnen (oder neue Szene + Person).
2. Die Figur (Person-Atom) auswählen > Tab **Plugins** > **Add Plugin** >
   `AddonPackages > d0n.AIBody.7:/Custom/Scripts/d0n/AIBody/AIBody.cslist`.
   **Nicht** unter *Session Plugins* oder *Scene Plugins*.
3. Falls VaM fragt, ob Plugins aus dem Paket erlaubt werden sollen: erlauben und notieren, dass gefragt wurde.
4. **Open Custom UI** (Plugin-Fenster) öffnen.

Melden: Taucht in der Paketliste nur noch `d0n.AIBody.7` auf? Hat VaM nach Erlaubnis gefragt?
Screenshot des Fensters; rote „AIBody:“-Zeilen. Erwartet: *Self-test* „Person atom: yes“,
Startup log endet mit „Init complete, no errors.“

## T2 – Dateipfade: `GetFiles` → `ReadAllText` / `DeleteFile`

1. Companion-App starten (siehe oben).
2. Etwa 5 Sekunden warten.

Melden: Steht im *Self-test* „PluginData writable: yes“ und „Companion app heartbeat: yes“?
Steht unter *Live* „Companion app: connected …“? Liegen in
`<VaM>/Saves/PluginData/AIBody/default/inbox/` dauerhaft Dateien herum (sollte leer bleiben)?
Gibt es Zeilen wie „Could not delete processed inbox file“? Gibt es
`<VaM>/Saves/PluginData/AIBody/config.json`?

## T3 – Kopf-Audio, Lippensync, `PlayNow`-Retry, Start/Ende

1. Im Fenster der Companion-App (Konsole) einen Satz tippen und Enter drücken, z. B. `Hallo, wie geht es dir?`.
2. Zuhören und auf den Mund schauen. Drei Sätze schnell hintereinander tippen (Warteschlange).

Melden: Hört man den Ton aus dem Kopf der Figur (die Test-Engine `tone` spielt einen Summton statt einer Stimme)? Bewegt sich der Mund (Lippensync)? Kommt der Ton
sofort oder erst nach 1–2 Sekunden? Werden die drei Sätze nacheinander gespielt? In der
Companion-App: erscheinen `speech_started`/`speech_ended` bzw. Fehler wie `audio_failed`
(bitte die Konsolenzeilen kopieren)? Steht im *Self-test* „Head audio (HeadAudioSource): yes“?

## T4 – Menü-Aktualisierung und Textfeld

Tabs ab Version 15: Voice, AI Character, Client Character, Config (davor: Voice Mode, AI, AI Character, Client Character, Post, Config, Erweitert). Links ein großes Infofeld, in den Tabs nur Bedienelemente.

1. Tab **Client Character** öffnen. Im Infofeld links oben steht „Info: Client Character“ mit Push-to-Talk-Erklärung und Mikrofon-Status.
2. Tab **Voice** öffnen: oben Abschnitt *Voice Mode*, darunter *Voice > AI Character*; die Auswahllisten öffnen. Im Infofeld: Q&A-Hilfe, AI-mode-Hilfe, Key-Status, Engine-Status.
3. Tab **Config**: **Reload Config JSON** drücken; im Infofeld stehen Pfad der config.json, Kanal und das Ergebnis.
4. Tab **AI Character**: Abschnitt **Poses** vorhanden; ins beschriftete Feld unter „Breath morph“ klicken und einen Buchstaben ändern, dann zurück.
5. Alle vier Tabs einmal durchklicken. Es darf kein leeres Feld, keine leere Auswahl und kein Feld nur mit einem Tab-Namen erscheinen. Ab Version 16: das Infofeld zeigt nur die Infos des offenen Tabs (ab Version 17 ohne Kopfzeile darüber, 1800 hoch: muss man noch scrollen?); Selbsttest und Startup log stehen im Tab Config; oben steht `Startup: ok` (oder rot die Fehler).

Melden: Zeigt die Geräteliste die echten Mikrofone? Lässt sich in das Atem-Morph-Feld tippen? Steht
im Infofeld zu jedem Tab passende Hilfe? Wechseln die Tabs
sauber (alte Elemente weg, keine doppelten)? Steht eine *WARNING „is read-only“* im Startup log?

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

Melden (seit Version 13): die Zeilen im *Self-test* „Pose storage (PosePresets)“, „Poses“,
„Breath morph“, „Expression morphs: x of y found – missing: …“ und ggf. „Timeline“; dieselben Werte
stehen in der Konsole der Companion-App und in `companion.log` als „Plugin self-test: …“.
Hebt und senkt sich die Brust? Steht unter *Live* „Breath morph: Breath1“ oder „not found“?
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

Melden: FPS ohne / mit Plugin. Steht nach dem Beenden der App „DISCONNECTED“ und nach dem Neustart
wieder „connected“, ohne dass man etwas klickt? Sind die eigenen Einstellungen nach dem Neuladen
noch da? Rote Zeilen beim Entfernen, Speichern oder Neuladen? Wie viele Dateien liegen nach
einer Minute ohne App in `Saves/PluginData/AIBody/default/outbox/` (sollten höchstens ~20 sein)?

## T7 – Engine-Status (ab v0.7.0)

1. Companion-App läuft (ohne API-Keys).
2. Tab **Voice** öffnen, unter *Voice > AI Character* bei **Text-to-speech** `elevenlabs` auswählen, 3 Sekunden warten.
3. Einen Satz in der Companion-App tippen.

Melden: Steht im Infofeld links „Text-to-speech: elevenlabs – not configured: …“ und
„running instead: tone (fallback)“? Spricht die Figur trotzdem (Summton)? (Ab Version 17 steht die
Engine-Zeile nur noch einmal, im Engine-Status.) Danach wieder `tone` auswählen.

---

## T8 – Realtime-Sprache und proaktives Sprechen (ab v0.7.1)

Braucht einen xAI-Key (Feld **XAI API Token**, Umgebungsvariable `XAI_API_KEY` oder `ai.xai.key_file` in `config.json`)
und am besten ein Headset.

1. Companion-App mit Key starten. Im Log der App sollte stehen: `Mode: auto -> realtime` und
   `Realtime: connected to wss://api.x.ai/v1/realtime?model=grok-voice-latest`.
2. Im Plugin Tab **Voice**: **AI mode** steht auf `auto`; im Infofeld
   „Mode: realtime – Realtime connected …“ und „Proactive talking: on - after 90 s of silence the AI may speak on its own (speech delay timer, not the answer delay)“.
3. Etwas sagen (z. B. „Hallo, wie spät ist es?“). Die Figur soll nach kurzer Pause antworten,
   der Mund bewegt sich, die Uhrzeit stimmt ungefähr.
4. Während sie spricht, **Push-to-talk** drücken (oder mit Headset und eingeschaltetem
   **Voice barge-in (headphones)** einfach reinsprechen): Sie soll sofort verstummen.
5. **Speech delay timer (s)** (bis Version 22 „Proactive idle (s)“) auf 20 stellen, 30 Sekunden still sein: Die Figur sagt von sich aus etwas
   (oder schweigt bewusst – dann steht im App-Log `Proactive talking: the AI chose to stay silent`).
6. **AI mode** auf `chain` stellen: Status zeigt „Mode: chain“; danach wieder `auto`.

Melden: die Zeilen 1–2 aus dem App-Log, wie lange es bis zur Antwort dauert (geschätzt), ob die
Antwort abgehackt klingt (Pausen zwischen den Stücken), ob Unterbrechen klappt, und alle Zeilen
mit `Realtime` oder `failed` aus dem App-Log.

---

## T9 – Ton im Spiel: Frage → Antwort hörbar (ab v0.7.2)

Ziel: Es soll einfach eine hörbare Antwort aus dem Kopf der Figur kommen. Körpersteuerung ist dafür
nicht nötig.

1. Tab **Voice** > **Question and Answer** (zweizeilig und mittig; bis Version 20 „Simple Q&A mode“; setzt AI mode `qa` und Body control aus; prüfen im
   Tab **AI Character**). **Speech volume** auf 1.
2. Tab **Voice** > **Play test tone** (spielt die Datei aus dem Paket, ohne Companion-App).
   Im Statusfeld unter *Live* steht `Audio: Loading: AIBodyTest.wav`, dann `Speaking: AIBodyTest.wav (1.5 s)`, dann `Done: …`.
3. Companion-App mit xAI-Key starten, dann **Test tone via companion** (Datei aus
   `Custom/Sounds/AIBody/default/`). Unter *Live* steht `Audio folder: …`.
4. In der Companion-Konsole `Hallo` tippen + Enter (gleicher Weg wie gesprochen, nur ohne Mikrofon).
   Unter *Live* erscheint `Last turn: Question (typed): Hallo`, dann `Last turn: Answer (…, xai -> xai): …`,
   und die Figur spricht die Antwort (ein paar Sekunden Verzögerung sind normal).
5. Eine Frage ins Mikrofon sprechen. Erwartet: `Last turn: Heard: …`, dann die gesprochene Antwort.

Melden: Hört man bei 2, 3, 4 und 5 etwas? Was steht jeweils unter *Live* bei `Audio:`, `Audio folder:`
und `Last turn:`? Rote Zeilen (`Audio error: …`, `Language model error: …`, `Nothing understood …`)
bitte genau abschreiben, dazu die Ausgabe der Companion-Konsole.

- Wenn 2 klingt, 3 aber nicht: Die App wechselt nach etwa 15 s von selbst nach
  `Saves/PluginData/AIBody/default/audio/` und spielt den Ton noch einmal (rote Zeile „audio folder
  switched to …“). Bitte melden, ob er dann klingt.
- Steht dort „without an xAI API key“: Key nicht gesetzt (Feld **XAI API Token** im Tab **Voice** leer? Oder Umgebungsvariable nicht im selben Konsolenfenster wie die App?) oder in `config.json` unter
  `ai.xai.key_file` eine Key-Datei eintragen und im Tab **Config** **Reload Config JSON** drücken.

## T10 – Verbose log und Echtzeit-Schalter (ab v0.7.3)

1. Tab **Config** > **Verbose log** einschalten. In der Companion-Konsole erscheint
   `Verbose log on (turn trace) - log file <VaM>/Saves/PluginData/AIBody/logs/companion.log`.
2. Eine Frage tippen oder sprechen. In der Konsole stehen Zeilen wie `[t0001 +0.00s] start: …`,
   `path: …`, `stt: …`, `llm request: …`, `tts: … wav='Custom/Sounds/AIBody/default/…'`, `speak sent: …`,
   `plugin: speech_started …` – alle mit derselben Turn-Nummer. Im Statusfeld erscheint
   *Recent events* mit `Command speak …`, `PlayNow …`, `Speaking …`, `End …`.
3. Tab **Voice** > **Use realtime voice** einschalten: darunter unter *Voice > AI Character* steht
   AI mode `auto`, die Konsole meldet den Moduswechsel. Wieder aus: AI mode `qa`.
4. **Verbose log** wieder aus: die Turn-Zeilen hören auf.

Melden: die Datei `companion.log` aus `<VaM>/Saves/PluginData/AIBody/logs/` (enthält keine Keys,
bitte trotzdem kurz reinschauen) und einen Screenshot des Statusfelds mit *Recent events*.

## T11 – Mikrofon-Menü, Posen-Menü, KI-Körpersteuerung, Latenz (ab v0.7.4)

1. Tab **Client Character** (seit 19.11.2026 ohne Mikrofon-Auswahl): kein Menü **Mic device**, kein Knopf
   **Refresh microphones**. Im Infofeld links steht `Mic: capturing | microphone: system default input | mode: …`.
   Ohne laufende Begleit-App: rote Zeile
   `Companion app not running, so nothing is heard or spoken. Start it in a console, in the 'companion' folder: python -m aibody_companion --vam-root "D:\VaM"`; nach dem Start
   der App verschwindet sie. Sprechen (Pegel bewegt sich): die App nimmt vom Windows-Standard-Eingabegerät auf.
   Anderes Mikrofon: in Windows als Standardgerät einstellen und die App neu starten. Eine alte Szene mit
   gespeichertem „Mic device“ lädt ohne Fehler (Wert wird ignoriert).
2. Tab **AI Character** > Abschnitt **Poses**: Menü öffnen (Posen aus `gestures.json` und aus
   `<VaM>/Custom/Atom/Person/Pose/` bzw. `.../Pose/AIBody/`), eine wählen, **Apply pose**.
   Statusfeld: Ergebnis der Aktion. **Reload poses** nach dem Ablegen einer neuen Pose-Datei.
3. Ausdruck wählen > **Show expression**; Geste wählen > **Play gesture**.
4. Tab **Voice** > **Use realtime voice** an, Tab **AI Character** > **Body control** an.
   Sagen: „Lächle mal“ bzw. „Nimm eine andere Pose ein“. Konsole: `realtime tool call` bzw.
   `llm tool call` (mit Verbose log), die Figur reagiert. Mit **Question and Answer** reagiert sie nicht
   (nur Sprache, so gewollt).
5. Nach jeder Antwort im Statusfeld (*Live*): `Latency to first sound: X s (avg Y s, n turns)` und
   darunter die Aufschlüsselung. In der Konsole: `Latenz t000N bis zum ersten Ton: …`.
6. Tab **Voice** ohne Key: im Infofeld Key-Status `fehlt` mit `nötig: API-Key von console.x.ai … ein Grok-Abo /
   grok.com-Token funktioniert nicht`.

Melden: Screenshot des Infofelds (Tab Client Character), Screenshot des Statusfelds mit der
Latenz, Konsolenausgabe.

## T12 – Feld „XAI API Token“ und Knopf „Question and Answer“ (ab Version 21)

1. Tab **Voice**, Abschnitt *Voice Mode*: Der Knopf oben heißt zweizeilig **Question** / **& Answer**,
   Text mittig, Text nicht abgeschnitten. Darunter **Active**, **Use realtime voice**, **API Reconnect**,
   dann die Beschriftung **XAI API Token**, das Textfeld und darunter der Hinweis zum Maskieren (seit Version 24; die Szenen-Warnung „(beware: scenes save it)“ gibt es nicht mehr).
2. Begleit-App **ohne** `XAI_API_KEY` starten (Warnung „No xAI API key yet“ ist richtig). Infofeld links:
   `xAI key: missing` und der Hinweis auf das Feld.
3. In das Feld klicken, den xAI-Key (console.x.ai) einfügen (Strg+V). Erwartet: nach etwa einer Sekunde
   Infofeld `xAI key: configured – plugin field 'XAI API Token'`; Konsole der App:
   `XAI API Token from the plugin field set` (der Token selbst steht nirgends, auch nicht bei Verbose log).
4. **Question and Answer** drücken, eine Frage sprechen oder tippen: hörbare Antwort. Funktion wie vorher.
5. Feld leeren: `xAI key: missing`. Feld mit Unsinn füllen (z. B. `abc`): wird ohne Formatprüfung
   angenommen, die erste Anfrage meldet `rejected` (HTTP 401/403).
6. (Version 24) Szene speichern, VaM neu starten, Szene laden: das Feld ist wieder gefüllt, jetzt **maskiert** (`xai-****abcd`);
   `config.json` enthält `ai.xai.api_key` (Klartext) und daneben `ai.xai.api_key_warning`. Im linken Infofeld (Tab Voice) steht
   oben „SECURITY NOTICE: …“, nicht unter dem Feld. Infofeld `xAI key: configured`.
7. (Version 24) Feld markieren und einen anderen Key einfügen: nach etwa 4 s zeigt das Feld die neue Maske, `ai.xai.api_key`
   hat den neuen Wert (Datei prüfen, andere Schlüssel unverändert). In die Maske tippen: der Token bleibt unverändert, die
   Maske kommt zurück. Feld leeren: `xAI key: missing` (ohne Umgebungsvariable), `ai.xai.api_key` ist `""`.
8. (Version 24) Companion-Log (`companion.log`) und Plugin-Log öffnen: der Token steht nirgends.

Melden: Screenshot des Tabs **Voice** (Knopf, Feld, Hinweis), Infofeld links, rote `AIBody:`-Zeilen, Ausgabe der
Begleit-App-Konsole. Wichtig: ob Einfügen per Strg+V im Feld klappt, ob der Knopf zweizeilig mittig steht.

### T11a – Mikrofon-Diagnose ohne VaM (`tools/mic_test.py`, ab Version 16)

1. Companion-App beenden. Im Repo-Ordner (nach `git pull`): `python tools/mic_test.py`.
   Ausgabe: Versionen, Host-APIs, alle Geräte roh, Eingabegeräte je Host-API, Eingabegeräte der Standard-Host-API
   (`*` = Standardgerät, von dem die App aufnimmt). Datei `mic_test_output.txt` im aktuellen Ordner.
   Seit 19.11.2026 nur Diagnose: keine Mikrofon-Auswahl, keine Nachricht an das Plugin, kein `--vam-root`.

Melden: `mic_test_output.txt`.

**Ergebnis zurückschicken:** pro Punkt T1–T12 ✅/❌, die Screenshots, die roten „AIBody:“-Zeilen und
bei Problemen mit einer Antwort die Datei `companion.log` (mit eingeschaltetem Verbose log).

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

## T14 – Gaze control (after version 24, next version 25)

Needs VaM with the AI Character (AIBody) and the Client Character in the example scene. No Glance on the AI Character.

1. Tab **AI Character** > **Gaze**: **Gaze control** on, **Default gaze** = *Client Character*: the AI's eyes turn to the
   client's face. *Camera / player*: they look at you (VR or screen camera). *Straight ahead*: level, 2 m in front of the
   face. Pick an *Atom: …* entry (open the list; it refills): the eyes look at that atom. *VaM default*: the eyes go back to
   what they did before (VaM look mode and eye target position are restored).
2. Info field (left): *Gaze now: looking at … (default gaze)* and the help text. Turn **Gaze control** off: *Gaze now: off*.
3. Ask the AI (not Question and Answer mode) to look at you, at the client, away; the AI uses `look_at` (console line / log
   `look_at`). *Away* looks to the side for about 3 s and returns to the default.
4. **Gaze follows speaker** on, Default gaze = *VaM default*: while the AI or you talk, the eyes go to the client; silent: back.
5. Coexistence: add the Glance plugin to the AI Character: the info field says *paused: Glance is on this Person*, the AI
   gets no `look_at` tool. Remove it again (or switch the Eyes look mode by hand in VaM while AIBody steers): AIBody stops
   and says so; picking a Default gaze takes the eyes again.
6. Report: where the eyes look in each step (correct / mirrored / too high / too low), whether *Straight ahead* really is
   the way the face points, the VaM error log.
