# AIBody – Anforderungskatalog (Stand-Übersicht)

Stand: 17.11.2026, v0.7.4. Übersicht, was umgesetzt ist und was offen ist; wird bei jedem Release aktualisiert.
- Vereinbarte Spezifikation (was gilt): [`docs/SPEC.md`](SPEC.md)
- Zurückgestellte Ideen / Nice to have: [`docs/BACKLOG.md`](BACKLOG.md)
- Testanleitung in VaM: [`docs/TESTPROTOKOLL.md`](TESTPROTOKOLL.md) · API-Belege: [`docs/API_AUDIT.md`](API_AUDIT.md)
- Repo: https://github.com/d0n/vam_plugin · aktuelles Paket: `d0n.AIBody.11.var`

„Umgesetzt“ heißt: im Code und gegen nachgebaute Gegenstellen getestet. Was in VaM bzw. gegen die echten xAI-APIs noch nicht geprüft ist, steht zusätzlich unter 2.

## 1. Bereits umgesetzt

### Laden, Sandbox, Paket
- Ein Plugin, eine `.cslist` (`Custom/Scripts/d0n/AIBody/AIBody.cslist`), eine MVRScript-Klasse, Laden in einem Schritt im Plugins-Tab der Person – v0.6.0.
- Strenge Sandbox ohne Netzwerkcode (kein `UnityWebRequest`, `UnityEngine.Networking`, `WWW`, `System.IO`, `System.Net`, `Process`, Reflection, `DllImport`, Unity-`Microphone`); Build-Scan bricht ab – v0.6.1.
- Nur belegte APIs, Belege in `docs/API_AUDIT.md` (E1–E25) – v0.6.1, laufend ergänzt.
- Dateizugriff nur über `FileManagerSecure`; „Allow Plugins Network Access“ bleibt aus – v0.6.1.
- Diagnose im Plugin-Fenster: Statusfeld, Selbsttest, jede Init-Phase einzeln abgesichert – v0.6.2.
- Eine `.var` nach `<VaM>/AddonPackages/`; Liste alter Pakete zum Löschen in README und Release-Notes – seit v0.6.0.

### Verbindung und Konfiguration
- Begleit-App (Python) `python -m aibody_companion --vam-root "<VaM>"` – v0.5.0.
- Datei-Transport über `Saves/PluginData/AIBody/<Kanal>/`, Protokoll v3, Heartbeat, Status – v0.5.0/v0.6.3.
- Robuste Verbindung: Timeout 6 s → „GETRENNT“, automatischer Neuaufbau, alte Befehle verworfen, Outbox ≤ 20 – v0.6.3, End-to-End-Simulation v0.7.0.
- Gemeinsame `config.json` unter `<VaM>/Saves/PluginData/AIBody/` (Ort entschieden 15.11.2026), Schema, Menüwerte gewinnen; VaM-Werte als Text (`"2.5"`, `"true"`) werden gelesen (E21) – v0.6.3/v0.7.0.
- Menü in Tabs (Tab-Buttons, `Create*`/`Remove*`, E17/E18) – v0.6.3; neu geordnet nach Leons Wunsch (Voice Mode, AI, AI Character, Client Character, Post, Config, Erweitert) – v0.7.2.

### KI und Sprache
- Test-Engines `null`/`echo`/`tone` als Offline-Betrieb und Fallback – v0.5.0.
- Engines xAI (STT `POST /v1/stt`, LLM `POST /v1/responses` gestreamt, TTS `POST /v1/tts`) und ElevenLabs (TTS); Keys über `XAI_API_KEY`/`ELEVENLABS_API_KEY` oder Pfad einer Key-Datei; Key-Status konfiguriert/fehlt/abgelehnt – v0.7.0.
- Realtime-Modus (Grok Voice, `wss://api.x.ai/v1/realtime`), Neuverbindung mit Backoff, Kette als Fallback – v0.7.1.
- Proaktives Sprechen nach Stille, Uhrzeit und Zeit seit letztem Austausch im Kontext – v0.7.1.
- Einfacher Q&A-Modus `qa` als Standard (nur Sprache, Body control aus), Knopf im Tab Voice Mode, Statuszeile „Letzte Runde“, Realtime ohne Antwort nach 12 s → Kette – v0.7.2 (von Leon freigegeben 17.11.2026).
- Schalter „Echtzeit (Realtime) verwenden“ (an = `auto`, aus = `qa`, Standard bleibt `qa`) – v0.7.3.
- Abgelehnter xAI-Key (HTTP 400 „Incorrect API key“) wird als „abgelehnt“ erkannt – v0.7.3.
- Hinweis, welcher Key funktioniert: API-Key von console.x.ai, kein Grok-Abo/grok.com-Token (Key-Status, Startwarnung der App) – v0.7.4.
- Tool-Aufrufe → Körperbefehle (Kette: `/v1/responses` mit tools; Realtime: function_call + function_call_output): `express` (Ausdruck/Geste), `pose` (wenn Posen vorhanden); jeder Aufruf bekommt ein Ergebnis; keine Tools in `qa` und bei Body control aus – v0.7.4.
- Latenzmessung Sprechende → erster Ton mit Aufschlüsselung (STT, LLM erstes Token, erster Satz, TTS, Datei, an Plugin, Plugin-Start), Logzeile pro Runde, letzter Wert + Mittel im Statusfeld (*Live*, „Latenz bis zum ersten Ton“) – v0.7.4.

### Mikrofon
- Mikrofon nur in der Begleit-App (Aufnahme, Geräteliste, VAD, Echo-Sperre); Push-to-Talk im Plugin, Meldung als Datei – v0.5.0.
- Push-to-Talk unterbricht die laufende Antwort; Voice barge-in (Kopfhörer) im Realtime-Modus – v0.7.0/v0.7.1.
- Mikrofon-Einstellungen live (0,3 s nach letzter Änderung), Pegelanzeige – v0.6.3.
- Mikrofon-Menü repariert (leeres Menü): ein Eintrag je Gerät (nur Host-API des Standardgeräts, Windows listet sonst jedes Mikro mehrfach), Öffnen per Index, Fehlergrund der App wird angezeigt, Eintrag „Standard (System-Mikrofon)“, Knopf „Mikrofone neu laden“, Statuszeile mit Geräteanzahl, Liste wird beim Öffnen neu angefragt (E24/E25) – v0.7.4.

### Sprachausgabe
- VaMs Audio-Lader (`NormalizeMediaPath` → `URLAudioClipManager.QueueClip` → `PlayNow` auf `HeadAudioSource`) mit eingebautem Lippensync, nur lokale Dateien – v0.6.x.
- Sprache unabhängig von Ausdrücken, Statuszeilen `Audio: Lade/Spreche/Fertig`, rote `Audio-Fehler`, Test-Ton direkt und über Companion – v0.7.1/v0.7.2.
- Audio-Ordner `Custom/Sounds/AIBody/<Kanal>/`, bei „nicht ladbar“ einmal Wechsel nach `Saves/PluginData/AIBody/<Kanal>/audio/`; fester Ordner über `connection.paths.audio` – v0.7.2.

### Körper
- Ausdrücke über Morphs, Atmung (Atem-Morph in config.json einstellbar), Kopf-Leerlauf, Gesten über Timeline (`Play <Name>`), Posen über Pose-Presets – v0.5.0/v0.6.3.
- Schalter Body control (aus = nur Sprache) – v0.7.1.
- Tab AI Character: Posen per Sprache über die KI und manuelles Menü (Auswahl + „Pose anwenden“, „Posen neu laden“; Posen aus `gestures.json` und Preset-Dateien in `Custom/Atom/Person/Pose` und `.../Pose/AIBody`), Ausdruck/Geste mit Auswahl und Knopf – v0.7.4 (Leon, 17.11.2026 21:41).

### Menü-Grundsatz
- Das Menü zeigt nur Einstellbares (Leon, 17.11.2026 21:43): reine Pfad-/Info-Anzeigen in Post, Config und AI Character entfernt, nicht verschoben; Pfade stehen einmal im VaM-Log; Erklär-/Statustexte zu Bedienelementen bleiben – v0.7.4.
- Push-to-Talk-Erklärtext unter dem Schalter statt Tooltip (kein belegter Weg) – v0.7.2, erneut geprüft v0.7.3.

### Protokollierung
- Verbose log (Tab Erweitert, `advanced.verbose_log`, `-v`): Trace pro Runde in Konsole und `<VaM>/Saves/PluginData/AIBody/logs/companion.log` (1 MB × 5), Keys geschwärzt; im Plugin `[debug]`-Zeilen und *Letzte Ereignisse* – v0.7.3; Tool-Aufrufe und Latenz im Trace – v0.7.4.

### Szene, Doku
- Szenen-Vorlage Green Screen / Passthrough (Sallys *Camera Background Color* #00FF00): `examples/scenes/AIBody_GreenScreen.json`, `docs/SZENE_GREENSCREEN.md` – v0.7.x (Wunsch 17.11.2026).
- `docs/BACKLOG.md` (zurückgestellte Ideen, Leon 17.11.2026 21:45) und `docs/SPEC.md` (Spec-Log, Leon 17.11.2026 21:50) – v0.7.4.

## 2. Noch offen / zu tun

### Test in VaM (Anleitung `docs/TESTPROTOKOLL.md`)
- T1: Laden aus der `.var`, Nachfrage zu Plugins aus dem Paket, alte Pakete entfernt.
- T2: `ReadAllText`/`DeleteFile` akzeptieren die Pfade aus `GetFiles`.
- T3: Kopf-Audio mit Lippensync, `PlayNow`-Retry, Start/Ende-Erkennung.
- T4: Menü-Aktualisierung, Textfeld, Tabs.
- T5: Pose-Speicher-Name, Morph-Namen, Atem-Morph.
- T6: Hinzufügen/Entfernen/Speichern/Neuladen ohne Exceptions und FPS-Einbruch; „GETRENNT“ und Neuaufbau; config.json ohne Rückfrage.
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
- Ursache des leeren Mikrofon-Menüs bei Leon: aus dem Code abgeleitet, Bestätigung über Statuszeile/Konsole steht aus.

### Offene Fragen an Leon
- Tab „Post“ oder „Port“ gemeint? (Bezeichnung ist eine Konstante.)
- Direktes API-Key-Feld im Plugin (Klartext in Szene/config.json)? Nicht gebaut, siehe Backlog.
- „Delay“: was soll verzögert werden? Platzhalter ohne Funktion, siehe Backlog.
- Session-Config vs. Person-Config: zurückgestellt bis nach den Tests, siehe Backlog.

### Noch nicht umgesetzt (vereinbart)
- Bessere Sprachaktivitätserkennung (aktuell Energie-VAD).
- Quellennennung bei Veröffentlichung (MacGruber als Hauptquelle, ebenso AcidBubbles, VamDeluxe).
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
- Code und README Englisch; Release-Notes Deutsch mit vollem Pfad ab VaM-Hauptordner, Ladeort (Plugins-Tab der Person), Bitte um Screenshot, rote `AIBody:`-Logzeilen und Konsolenausgabe der Begleit-App.

## Lernquellen
- MacGruber: [LogicBricks](https://hub.virtamate.com/resources/logicbricks.1975/), [Life](https://hub.virtamate.com/resources/life.165/), [Benchmark](https://hub.virtamate.com/resources/benchmark.11336/), [Utils](https://hub.virtamate.com/resources/macgruber-utils.40744/)
- AcidBubbles: Timeline, Glance, Keybindings (Bootstrap per `CreatePlugin`)
- VamDeluxe: [DeluxePlugin / DollMaster](https://github.com/vamdeluxe/DeluxePlugin) (Audio-Lader, Personas als Daten)
- hazmhox: [VAMStory](https://hub.virtamate.com/resources/vamstory.28256/) (Story-Steuerung auf eigenem Atom)
