# AIBody – Anforderungskatalog (Stand-Übersicht)

Stand: 17.11.2026, Version 12. Übersicht, was umgesetzt ist und was offen ist; wird bei jedem Release aktualisiert.
- Vereinbarte Spezifikation (was gilt): [`docs/SPEC.md`](SPEC.md)
- Zurückgestellte Ideen / Nice to have: [`docs/BACKLOG.md`](BACKLOG.md)
- Testanleitung in VaM: [`docs/TESTPROTOKOLL.md`](TESTPROTOKOLL.md) · API-Belege: [`docs/API_AUDIT.md`](API_AUDIT.md)
- Repo: https://github.com/d0n/vam_plugin · aktuelles Paket: `d0n.AIBody.19.var` (Version = Paketnummer seit 12)

„Umgesetzt“ heißt: im Code und gegen nachgebaute Gegenstellen getestet. Was in VaM bzw. gegen die echten xAI-APIs noch nicht geprüft ist, steht zusätzlich unter 2.

## 1. Bereits umgesetzt

### Laden, Sandbox, Paket
- Ein Plugin, eine `.cslist` (`Custom/Scripts/d0n/AIBody/AIBody.cslist`), eine MVRScript-Klasse, Laden in einem Schritt im Plugins-Tab der Person – v0.6.0.
- Strenge Sandbox ohne Netzwerkcode (kein `UnityWebRequest`, `UnityEngine.Networking`, `WWW`, `System.IO`, `System.Net`, `Process`, Reflection, `DllImport`, Unity-`Microphone`); Build-Scan bricht ab – v0.6.1.
- Nur belegte APIs, Belege in `docs/API_AUDIT.md` (E1–E25) – v0.6.1, laufend ergänzt.
- Dateizugriff nur über `FileManagerSecure`; „Allow Plugins Network Access“ bleibt aus – v0.6.1.
- Diagnose im Plugin-Fenster: Statusfeld, Selbsttest, jede Init-Phase einzeln abgesichert – v0.6.2.
- Eine `.var` nach `<VaM>/AddonPackages/`; Liste alter Pakete zum Löschen in README und Release-Notes – seit v0.6.0.
- Hotfix: Version 13 kompilierte in VaM nicht (CS584, `foreach` über `Dictionary.Values` in `ExpressionController.cs`); kein `foreach`/LINQ über `.Keys`/`.Values` mehr, der Build-Scan verbietet das Muster – Version 14 (Leon, 17.11.2026 23:16); in VaM bestätigt: lädt ohne Fehler, „Init fertig, keine Fehler“, 200 Posen (Leon, 17.11.2026).

### Verbindung und Konfiguration
- Begleit-App (Python) `python -m aibody_companion --vam-root "<VaM>"` – v0.5.0.
- Datei-Transport über `Saves/PluginData/AIBody/<Kanal>/`, Protokoll v3, Heartbeat, Status – v0.5.0/v0.6.3.
- Robuste Verbindung: Timeout 6 s → „DISCONNECTED“, automatischer Neuaufbau, alte Befehle verworfen, Outbox ≤ 20 – v0.6.3, End-to-End-Simulation v0.7.0.
- Gemeinsame `config.json` unter `<VaM>/Saves/PluginData/AIBody/` (Ort entschieden 15.11.2026), Schema, Menüwerte gewinnen; VaM-Werte als Text (`"2.5"`, `"true"`) werden gelesen (E21) – v0.6.3/v0.7.0.
- Menü in Tabs (Tab-Buttons, `Create*`/`Remove*`, E17/E18) – v0.6.3; neu geordnet nach Leons Wunsch (Voice Mode, AI, AI Character, Client Character, Post, Config, Erweitert) – v0.7.2; neu nach dem VaM-Test: Voice (Voice Mode, Voice > AI Character), AI Character, Client Character, Config – Version 15 (Leon, 17.11.2026).

### KI und Sprache
- Test-Engines `null`/`echo`/`tone` als Offline-Betrieb und Fallback – v0.5.0.
- Engines xAI (STT `POST /v1/stt`, LLM `POST /v1/responses` gestreamt, TTS `POST /v1/tts`) und ElevenLabs (TTS); Keys über `XAI_API_KEY`/`ELEVENLABS_API_KEY` oder Pfad einer Key-Datei; Key-Status konfiguriert/fehlt/abgelehnt – v0.7.0.
- Realtime-Modus (Grok Voice, `wss://api.x.ai/v1/realtime`), Neuverbindung mit Backoff, Kette als Fallback – v0.7.1.
- Proaktives Sprechen nach Stille, Uhrzeit und Zeit seit letztem Austausch im Kontext – v0.7.1.
- Simple Q&A mode `qa` als Standard (nur Sprache, Body control aus), Knopf im Tab Voice Mode (seit Version 15: Voice > Voice Mode), Statuszeile „Last turn“, Realtime ohne Antwort nach 12 s → Kette – v0.7.2 (von Leon freigegeben 17.11.2026).
- Schalter „Use realtime voice“ (an = `auto`, aus = `qa`, Standard bleibt `qa`) – v0.7.3.
- Abgelehnter xAI-Key (HTTP 400 „Incorrect API key“) wird als „abgelehnt“ erkannt – v0.7.3.
- Hinweis, welcher Key funktioniert: API-Key von console.x.ai, kein Grok-Abo/grok.com-Token (Key-Status, Startwarnung der App) – v0.7.4.
- Tool-Aufrufe → Körperbefehle (Kette: `/v1/responses` mit tools; Realtime: function_call + function_call_output): `express` (Ausdruck/Geste), `pose` (wenn Posen vorhanden); jeder Aufruf bekommt ein Ergebnis; keine Tools in `qa` und bei Body control aus – v0.7.4.
- Latenzmessung Sprechende → erster Ton mit Aufschlüsselung (STT, LLM first token, first sentence, TTS, file write, to plugin, plugin start), Logzeile pro Runde, letzter Wert + Mittel im Statusfeld (*Live*, „Latency to first sound“) – v0.7.4.

### Mikrofon
- Mikrofon nur in der Begleit-App (Aufnahme, Geräteliste, VAD, Echo-Sperre); Push-to-Talk im Plugin, Meldung als Datei – v0.5.0.
- Push-to-Talk unterbricht die laufende Antwort; Voice barge-in (Kopfhörer) im Realtime-Modus – v0.7.0/v0.7.1.
- Mikrofon-Einstellungen live (0,3 s nach letzter Änderung), Pegelanzeige – v0.6.3.
- Mikrofon-Menü repariert (leeres Menü): ein Eintrag je Gerät (nur Host-API des Standardgeräts, Windows listet sonst jedes Mikro mehrfach), Öffnen per Index, Fehlergrund der App wird angezeigt, Eintrag „System default microphone“, Knopf „Refresh microphones“, Statuszeile mit Geräteanzahl, Liste wird beim Öffnen neu angefragt (E24/E25) – v0.7.4.
- Mikrofon-Menü leer in VaM („(not selected)“, nicht einmal „Standard“) – Version 16: Menü ohne getrennte Anzeigenamen (`displayChoices`), „Standard (System-Mikrofon)“ (seit Version 18 „System default microphone“) immer drin, Infofeld mit Anzahl empfangen, Host-API, Uhrzeit, Menüeinträgen; Test `tools/mic_test.py`. TODO(verify) in VaM.

### Sprachausgabe
- VaMs Audio-Lader (`NormalizeMediaPath` → `URLAudioClipManager.QueueClip` → `PlayNow` auf `HeadAudioSource`) mit eingebautem Lippensync, nur lokale Dateien – v0.6.x.
- Sprache unabhängig von Ausdrücken, Statuszeilen `Audio: Loading/Speaking/Done`, rote `Audio error`, Test-Ton direkt und über Companion – v0.7.1/v0.7.2.
- Audio-Ordner `Custom/Sounds/AIBody/<Kanal>/`, bei „nicht ladbar“ einmal Wechsel nach `Saves/PluginData/AIBody/<Kanal>/audio/`; fester Ordner über `connection.paths.audio` – v0.7.2.

### Körper
- Ausdrücke über Morphs, Atmung (Atem-Morph in config.json einstellbar), Kopf-Leerlauf, Gesten über Timeline (`Play <Name>`), Posen über Pose-Presets – v0.5.0/v0.6.3.
- Schalter Body control (aus = nur Sprache) – v0.7.1.
- Tab AI Character: Posen per Sprache über die KI und manuelles Menü (Auswahl + „Apply pose“, „Reload poses“; Posen aus `gestures.json` und Preset-Dateien in `Custom/Atom/Person/Pose` und `.../Pose/AIBody`), Ausdruck/Geste mit Auswahl und Knopf – v0.7.4 (Leon, 17.11.2026 21:41).

### Menü-Grundsatz
- Das Menü zeigt nur Einstellbares (Leon, 17.11.2026 21:43): reine Pfad-/Info-Anzeigen in Post, Config und AI Character entfernt, nicht verschoben; Pfade stehen einmal im VaM-Log; Erklär-/Statustexte zu Bedienelementen bleiben – v0.7.4.
- Push-to-Talk-Erklärtext unter dem Schalter statt Tooltip (kein belegter Weg) – v0.7.2, erneut geprüft v0.7.3; seit Version 15 im Infofeld links.
- Ein großes Infofeld links für alle Hilfe-, Status- und Pfadtexte („Info: <Tab>“, Self-test, Live, Startup log); in den Tabs nur Bedienelemente; keine leeren Platzhalter; Eingabefelder beschriftet; Namen selbsterklärend (AI Character, Client Character) – Version 15 (Leon, 17.11.2026).
- Infofeld 1800 hoch, links nur das Infofeld (Kopfzeile mit Hinweis entfernt), Infotexte gekürzt, „Reload expressions“ beim Ausdruck – Version 17 (Leon, 18.11.2026).
- Plugin-Oberfläche, Begleit-App-Ausgaben und `tools/mic_test.py` auf Englisch (internationaler Standard, unabhängig von der Systemsprache); vom System gelieferte Namen (Mikrofone, Host-APIs) unverändert; alte Szenen und config.json bleiben gültig – Version 18 (Leon, 18.11.2026).
- Regler im Tab Config heißt in der Oberfläche „Companion inbox poll interval (s)“ statt „File poll interval (s)“: er bestimmt, wie oft das Plugin den Eingang der Companion-App (`Saves/PluginData/AIBody/<Kanal>/inbox/`) auf Nachrichten prüft (Sprache, Posen, Ausdrücke), nicht config.json (wird nie automatisch neu geladen). Hinweis dazu im Infofeld des Tabs Config; gespeicherter Name „File poll interval (s)“ und config.json-Schlüssel `advanced.file_poll_interval_s` unverändert, Abfrageverhalten unverändert – Version 19 (Leon, 18.11.2026).
- Infofeld größer (1600) und nur mit den Infos des offenen Tabs; Selbsttest, Recent events, Startup log im Tab Config; Startergebnis als eine Zeile auf jedem Tab; keine leere Posen-Auswahl; geprüft: kein Menü und kein Abschnitt, der nur „default“ zeigt – Version 16 (Leon, 18.11.2026).
- „Posen“ statt „Post“: Tab Post entfernt, Posen im Tab AI Character; Erweitert in Config aufgegangen – Version 15. Ursprüngliche Absicht der entfernten Einträge: `docs/BACKLOG.md`.

### Version und Konfiguration
- Versionsschema Version = Paketnummer (`d0n.AIBody.12.var` = Version 12, Tag `v12`; Test prüft Gleichheit) – Version 12 (Leon, 17.11.2026 22:31).
- Regler im Plugin decken die vollen config.json-Bereiche ab (VAD threshold bis 0,5, Proactive idle bis 3600 s), damit Werte aus der Datei nicht abgeschnitten und zurückgeschrieben werden; Test vergleicht alle Regler mit den Bereichen der App – Version 12.

### Protokollierung
- Verbose log (Tab Config, `advanced.verbose_log`, `-v`): Trace pro Runde in Konsole und `<VaM>/Saves/PluginData/AIBody/logs/companion.log` (1 MB × 5), Keys geschwärzt; im Plugin `[debug]`-Zeilen und *Recent events* – v0.7.3; Tool-Aufrufe und Latenz im Trace – v0.7.4.

- Erweiterter Selbsttest für die nur in VaM prüfbaren Punkte (T5): Pose-Speicher, Posen und Pose-Dateien, Atem-Morph, Ausdrucks-Morphs mit fehlenden Namen, Timeline-Storable; im Statusfeld und als „Plugin self-test: …“ in Konsole und `companion.log` – Version 13.

### Szene, Doku
- Quellennennung im README, Abschnitt 6 (MacGruber als Hauptquelle, Acid Bubbles, VamDeluxe, Sally, weitere Belegquellen) – Version 13.
- Szenen-Vorlage Green Screen / Passthrough (Sallys *Camera Background Color* #00FF00): `examples/scenes/AIBody_GreenScreen.json`, `docs/SZENE_GREENSCREEN.md` – v0.7.x (Wunsch 17.11.2026); Paketverweis auf das aktuelle Paket korrigiert – nach v0.7.4.
- Szene mit zwei Personen: `AI Character` (weiblich, `Female 3`, AIBody) und `Client Character` (männlich, `Male 1`, Camera Background Color direkt auf der Person), 1,2 m, einander zugewandt – Version 12 (Leon, 17.11.2026 22:30).
- README auf Deutsch neu: Zweck, mitgelieferte Szene, zwei Figuren, vollständige Einstellungsreferenz, Hinweise für den Hub; Technik nach `docs/TECHNIK.md` – nach v0.7.4 (Leon, 17.11.2026 22:11).
- `docs/BACKLOG.md` (zurückgestellte Ideen, Leon 17.11.2026 21:45) und `docs/SPEC.md` (Spec-Log, Leon 17.11.2026 21:50) – v0.7.4.

## 2. Noch offen / zu tun

### Nächste Version (noch nicht umgesetzt)
- Alle Posen-Einträge (Apply pose, Reload poses und alles weitere zu Posen) gehören in einen Unterpunkt „Poses“ im Tab AI Character, nicht in Config. Grund: Posen gehören zu einer Figur und sind nur für den AI Character sinnvoll, nicht für den Client Character (Leon, 18.11.2026). Stand im Code seit Version 15: Apply pose und Reload poses liegen schon im Abschnitt Poses im Tab AI Character; Config enthält nur Reload Config JSON, Companion inbox poll interval (s) (bis Version 18 „File poll interval (s)“), Verbose log. In VaM prüfen, ob dort noch Posen-Einträge unter Config erscheinen (ggf. ältere Paketversion geladen).
- Alles, was in Leons Ansicht unter Config hängt („eigentlich quasi alles, was unter Config kommt“), insbesondere Expression and gesture und was darunter folgt (z. B. Body), unter den AI Character verschieben bzw. dort gruppieren, damit figurgebundene Steuerung eindeutig dem AI Character zugeordnet ist. Genaues Layout egal (Leon, 18.11.2026). Stand im Code seit Version 15: Expression and gesture und Body liegen schon im Tab AI Character; der Tab Config enthält nur Reload Config JSON, Companion inbox poll interval (s) und Verbose log (nicht figurgebunden). Klären, welche Version Leon in VaM sieht.
- xAI-API-Token ingame setzen: Freitextfeld im Menü mit der Beschriftung „XAI API Token“ ist der Hauptweg; `setx XAI_API_KEY` (Windows-Konsole) darf keine Voraussetzung sein, bleibt nur als optionale Alternative dokumentiert. Kein Freitextfeld für ElevenLabs (Leon, 18.11.2026). Am Feld ein kurzer Hinweis in Klammern auf Englisch, dass der Token im Klartext in Szene bzw. config.json gespeichert wird, z. B. „(beware: scenes save it)“ – knapp, für normale Englischsprecher verständlich (Leon, 18.11.2026). Damit ist die offene Frage „Direktes API-Key-Feld“ entschieden.

### Test in VaM (Anleitung `docs/TESTPROTOKOLL.md`)
- T1: Laden aus der `.var`, Nachfrage zu Plugins aus dem Paket, alte Pakete entfernt.
- T2: `ReadAllText`/`DeleteFile` akzeptieren die Pfade aus `GetFiles`.
- T3: Kopf-Audio mit Lippensync, `PlayNow`-Retry, Start/Ende-Erkennung.
- T4: Menü-Aktualisierung, Textfeld, Tabs.
- T5: Pose-Speicher-Name, Morph-Namen, Atem-Morph (seit Version 13 direkt im Selbsttest und im Log der Begleit-App ablesbar).
- T6: Hinzufügen/Entfernen/Speichern/Neuladen ohne Exceptions und FPS-Einbruch; „DISCONNECTED“ und Neuaufbau; config.json ohne Rückfrage.
- T7: Engine-Status.
- T8: Realtime mit echtem xAI-Key, Unterbrechen, proaktives Sprechen.
- T9: Frage → hörbare Antwort im Spiel.
- T10: Verbose log, Echtzeit-Schalter.
- T11: Mikrofon-Menü, Posen-/Ausdrucks-Menü, Tool-Aufrufe, Latenzanzeige.
- Engines noch nie gegen die echten xAI-/ElevenLabs-APIs gelaufen (nur nachgebauter Server).

### TODO(verify) im Code
- `GetFiles`-Pfade werden von `ReadAllText`/`DeleteFile` akzeptiert (1.22).
- 1,5 s Wartezeit nach Szenenwechsel reicht.
- Relativer `Saves/PluginData`-Pfad mit `NormalizeMediaPath` + Audio-Lader.
- Atem-Morph: kein Standard-Morph in VaM, Brust-Morph auf der Figur wählen.
- Editierbares Textfeld über `CreateTextField` (1.22).
- `GetFiles` auf einem `Custom/`-Ordner in der Sandbox (Posen-Dateien).
- Storable „PosePresets“ folgt dem belegten Muster (1.22).
- Morph-Namen für Ausdrücke an Standard-Figuren (weiblich/männlich).
- Szene: Personen in Blickrichtung +Z (0°/180° = einander zugewandt), Aussehen ohne festgelegte Kleidung, Camera Background Color auf einem Person-Atom.
- Ursache des leeren Mikrofon-Menüs bei Leon (Version 16): Vermutung `displayChoices` (einzige Auswahl des Plugins damit); Bestätigung über Screenshot des Infofelds (Zeile „Mic device menu: N entries …“) und Ausgabe von `tools/mic_test.py` steht aus.
- Sichtbare Höhe des Infofelds (1800) in VaM.

### Offene Fragen an Leon
- ~~Direktes API-Key-Feld im Plugin?~~ Entschieden 18.11.2026: ja, Feld „XAI API Token“ (siehe Nächste Version).
- Key-Datei-Pfad wieder im Menü (beschriftet)? Seit Version 15 nur in config.json, weil die Felder als leere Kästen erschienen; siehe Backlog.
- „Delay“: was soll verzögert werden? Platzhalter seit Version 15 aus dem Menü entfernt, siehe Backlog.
- Session-Config vs. Person-Config: zurückgestellt bis nach den Tests, siehe Backlog.

### Noch nicht umgesetzt (vereinbart)
- Bessere Sprachaktivitätserkennung (aktuell Energie-VAD).
- Blicksteuerung (bis dahin Glance; kein Look-at-Tool für die KI, weil das Plugin keine Blicksteuerung hat).
- Demo- bzw. Anleitungsszene.
- Doku und Veröffentlichung auf dem VaM Hub („Plugins + Scripts“, mit Tags).
- Zurückgestellt (früher „wollen wir“, Details in BACKLOG): Session/Person-Aufteilung mit Session-Anbindung und Bootstrap-Plugin, zweite Figur als eigene Instanz, Client auf eigenem Atom.

## 3. Ideen und Spec
- Nice to have, zurückgestellte Ideen und Ansätze (Pfadanzeige, In-Game-Testplugin, Key-Feld, Delay, Session/Person-Config, Tooltip, Client auf eigenem Atom, zweite Figur, Bootstrap, Blicksteuerung, Personas, Life/LogicBricks-Funktionen, lokale Engines, bessere VAD, Echo-Unterdrückung u. a.; dazu endgültig Gestrichenes): [`docs/BACKLOG.md`](BACKLOG.md).
- Vereinbarte Spezifikation inkl. Tab-Aufbau: [`docs/SPEC.md`](SPEC.md).

## Feste Rahmenbedingungen
- Sandbox-Regel und nur belegte APIs (siehe SPEC).
- Netzwerk nur in der Begleit-App.
- LICENSE und `licenseType` „FC“ in `meta.json` nicht anfassen; Lizenzfrage außen vor.
- Keine Secrets im Repo.
- Push direkt auf `main` in sinnvollen, einzeln grünen Commits.
- Code Englisch, README Deutsch (seit 17.11.2026 22:11); Release-Notes Deutsch mit vollem Pfad ab VaM-Hauptordner, Ladeort (Plugins-Tab der Person), Bitte um Screenshot, rote `AIBody:`-Logzeilen und Konsolenausgabe der Begleit-App.

## Lernquellen
- MacGruber: [LogicBricks](https://hub.virtamate.com/resources/logicbricks.1975/), [Life](https://hub.virtamate.com/resources/life.165/), [Benchmark](https://hub.virtamate.com/resources/benchmark.11336/), [Utils](https://hub.virtamate.com/resources/macgruber-utils.40744/)
- AcidBubbles: Timeline, Glance, Keybindings (Bootstrap per `CreatePlugin`)
- VamDeluxe: [DeluxePlugin / DollMaster](https://github.com/vamdeluxe/DeluxePlugin) (Audio-Lader, Personas als Daten)
- hazmhox: [VAMStory](https://hub.virtamate.com/resources/vamstory.28256/) (Story-Steuerung auf eigenem Atom)
