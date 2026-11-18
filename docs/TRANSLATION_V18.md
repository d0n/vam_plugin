# Übersetzung Version 18: Plugin-Oberfläche und Ausgaben auf Englisch

Stand: 18.11.2026, Version 18 (Paket `d0n.AIBody.18.var`). Auftrag von Leon: alle deutschen, für Nutzer sichtbaren Texte des Plugins in natürliches Englisch für ein IT-/Entwickler-Publikum übersetzen, ebenso Bezeichner und Kommentare im Code; Funktion und Layout unverändert. Die Konsolen-, Log- und Statustexte der Begleit-App und die Ausgabe von `tools/mic_test.py` gehören zur selben Oberfläche und sind mit übersetzt. Die Dokumentation (README, SPEC, ANFORDERUNGEN, BACKLOG, TESTPROTOKOLL) bleibt Deutsch; zitierte Oberflächentexte darin zeigen jetzt die englischen Beschriftungen.

## Regel: was übersetzt wird und was nicht

- Übersetzt werden nur **eigene** Texte: Feldnamen, Beschriftungen, Überschriften, Info- und Statustexte, Log- und Selbsttest-Zeilen, Knopftexte und eigene feste Menüeinträge (z. B. „Standard (System-Mikrofon)“ → „System default microphone“). Ziel: Benennung nach internationalem englischem Standard, verständlich unabhängig von der Systemsprache.
- **Nicht** übersetzt werden Inhalte, die Betriebssystem oder VaM in ihrer Sprache liefern: Mikrofon-Gerätenamen (z. B. „Mikrofon (Realtek(R) Audio)“), Namen der Windows-Standardgeräte (z. B. „Primärer Soundaufnahmetreiber“), Host-API-Namen, Fehlermeldungen des Systems. Sie erscheinen in Menü, Infofeld und `mic_test.py`-Ausgabe genau so, wie das System sie benennt (Leon, 18.11.2026).
- Gespeicherte Namen bleiben unverändert (siehe unten): JSONStorable-Namen, config.json-Schlüssel, Nachrichtentypen und Felder des Datei-Protokolls.

## Zahlen

| Kategorie | Anzahl |
|---|---|
| Plugin: übersetzte Texte (eindeutige String-Literale, `src/AIBody/*.cs`) | 182 |
| Begleit-App und Tools: übersetzte Texte (eindeutige Literale/Zeilen) | 93 |
| Kommentar-/Docstring-Stellen mit deutschem Text (Plugin / Begleit-App+Tools) | 25 / 6 |
| Bezeichner umbenannt (deutsch → englisch) | 1 (Testname) |
| neue Bezeichner für die Kompatibilität | 5 |
| Test-Erwartungen angepasst (deutsche → englische Texte) | 65 |
| neue Tests | 3 Python (Version18MenuTests) + 3 C#-Prüfungen (MicDeviceListTests) |
| gespeicherte Namen umbenannt | 0 |

## Wichtigste Beschriftungen

| Alt | Neu |
|---|---|
| `Einfacher Q&A-Modus` | `Simple Q&A mode` |
| `Echtzeit (Realtime) verwenden` | `Use realtime voice` |
| `Test-Ton abspielen` | `Play test tone` |
| `Test-Ton über Companion` | `Test tone via companion` |
| `Voice Mode (Verbindung, Modus, Ton-Test)` | `Voice Mode (connection, mode, sound test)` |
| `Voice > AI Character (Stimme und Sprach-KI der Figur)` | `Voice > AI Character (the character's voice and speech AI)` |
| `Posen (per Sprache über die KI, oder hier)` | `Poses (by voice through the AI, or here)` |
| `Pose anwenden` | `Apply pose` |
| `Posen neu laden` | `Reload poses` |
| `Ausdruck und Geste` | `Expression and gesture` |
| `Ausdruck zeigen` | `Show expression` |
| `Ausdrücke neu laden (expressions.json)` | `Reload expressions (expressions.json)` |
| `Geste abspielen` | `Play gesture` |
| `Körper (nur diese Person)` | `Body (this Person only)` |
| `Atem-Morph: Name des Brust-Morphs (Feld darunter)` | `Breath morph: name of the chest morph (field below)` |
| `Client Character: Mikrofon und Push-to-Talk` | `Client Character: microphone and push-to-talk` |
| `Mikrofone neu laden` | `Refresh microphones` |
| `Standard (System-Mikrofon)` | `System default microphone` |
| `Config (config.json, Verbindung, Protokoll)` | `Config (config.json, connection, logging)` |
| `Selbsttest / Start-Protokoll / Letzte Ereignisse` | `Self-test / Startup log / Recent events` |
| `Verbindung / Körper (Infofeld-Abschnitte)` | `Connection / Body` |
| `Start: ok / Fehler` | `Startup: ok / error(s)` |
| `Companion app: verbunden / GETRENNT / noch nicht gesehen` | `Companion app: connected / DISCONNECTED / not seen yet` |
| `Letzte Runde` | `Last turn` |
| `Latenz bis zum ersten Ton: X s (Ø Y s, n Runden)` | `Latency to first sound: X s (avg Y s, n turns)` |
| `Mikrofon-Liste: N empfangen von der Companion-App …` | `Microphone list: N received from the companion app …` |
| `Menü Mic device: N Einträge` | `Mic device menu: N entries` |
| `Auswahl / Windows-Standard` | `Selected / Windows default` |
| `konfiguriert / abgelehnt / fehlt` | `configured / rejected / missing` |
| `Lade / Spreche / Fertig / Abgebrochen / Audio-Fehler` | `Loading / Speaking / Done / Cancelled / Audio error` |
| `WARNUNG: / FEHLER in` | `WARNING: / ERROR in` |
| `Gehört: / Frage (getippt): / Antwort (…)` | `Heard: / Question (typed): / Answer (…)` |
| `Nichts verstanden …` | `Nothing understood …` |
| `Sprachmodell-Fehler / Sprachausgabe-Fehler / Spracherkennung-Fehler` | `Language model error / Text-to-speech error / Speech recognition error` |
| `bereit / nicht konfiguriert (Engine-Status)` | `ready / not configured` |
| `API-Key abgelehnt` | `API key rejected` |
| `Plugin-Selbsttest: …` | `Plugin self-test: …` |

## Plugin: alle übersetzten Texte (`src/AIBody`)

### `src/AIBody/AIBody.cs`

| Alt | Neu |
|---|---|
| `noch nicht geprüft` | `not checked yet` |
| `(kein Atom)` | `(no atom)` |
| `Dieses Plugin gehört in den Plugins-Tab einer Person-Figur, nicht in Session/Scene ` | `This plugin belongs in the Plugins tab of a Person atom, not in Session/Scene ` |
| `Plugins oder auf ein Empty – aktuell: ` | `plugins or on an Empty. Current atom type: ` |
| `Init beendet: AIBody bleibt hier inaktiv. Plugin hier entfernen und auf der ` | `Init stopped: AIBody stays inactive here. Remove it and add it to the AI ` |
| `KI-Figur (Person) unter Plugins > Add Plugin hinzufügen.` | `character (Person) via Plugins > Add Plugin.` |
| `Companion-App neu gestartet: alte Sprachausgabe abgebrochen.` | `Companion app restarted: pending speech cancelled.` |
| `Restart (Verbindung starten)` | `Restart (start connection)` |
| `Selbsttest PluginData` | `Self-test PluginData` |
| `ja (` | `yes (` |
| `NEIN: ` | `NO: ` |
| `Init fertig, keine Fehler.` | `Init complete, no errors.` |
| `Init fertig mit ` | `Init complete with ` |
| ` Fehler(n): ` | ` error(s): ` |
| `<b>Voice Mode</b> (Verbindung, Modus, Ton-Test)` | `<b>Voice Mode</b> (connection, mode, sound test)` |
| `Einfacher Q&A-Modus` | `Simple Q&A mode` |
| `<b>Voice > AI Character</b> (Stimme und Sprach-KI der Figur)` | `<b>Voice > AI Character</b> (the character's voice and speech AI)` |
| `<b>Config</b> (config.json, Verbindung, Protokoll)` | `<b>Config</b> (config.json, connection, logging)` |
| `Einfacher Q&A-Modus: Frage sprechen oder in der Companion-Konsole tippen -> Grok antwortet -> ` | `Simple Q&A mode: speak a question or type it in the companion console -> Grok answers -> ` |
| `die Person spricht. Setzt AI mode = qa und Body control = aus (Tab AI Character). Braucht einen xAI-Key.` | `the character speaks. Sets AI mode = qa and Body control = off (tab AI Character). Needs an xAI API key.` |
| `Einfacher Q&A-Modus an (` | `Simple Q&A mode on (` |
| `): AI mode = qa, Body control = aus. ` | `): AI mode = qa, Body control = off. ` |
| `Jetzt 'Test-Ton abspielen', dann eine Frage stellen.` | `Now press 'Play test tone', then ask a question.` |
| `Keine gültige config.json unter ` | `No valid config.json at ` |
| ` – nichts geändert.` | `; nothing changed.` |
| `config.json neu geladen (` | `config.json reloaded (` |
| `config.json laden fehlgeschlagen: ` | `Loading config.json failed: ` |
| `Key-Datei-Pfade aus config.json` | `Key file paths from config.json` |
| `Einstellungen aus config.json übernehmen (neue Szene)` | `Apply settings from config.json (new scene)` |
| `<b>Selbsttest</b>\n` | `<b>Self-test</b>\n` |
| `ja` | `yes` |
| `NEIN (` | `NO (` |
| `  Kopf-Audio (HeadAudioSource): ` | `  Head audio (HeadAudioSource): ` |
| `NEIN` | `NO` |
| `Body fehlt` | `Body missing` |
| `GETRENNT (verbindet automatisch neu)` | `DISCONNECTED (reconnects automatically)` |
| `noch nicht` | `not yet` |
| `Verbindung` | `Connection` |
| `Körper` | `Body` |
| `<b>Letzte Ereignisse</b> (Verbose log)\n` | `<b>Recent events</b> (Verbose log)\n` |
| `<b>Start-Protokoll</b>\n` | `<b>Startup log</b>\n` |
| `Start: ok\n` | `Startup: ok\n` |
| `Start läuft ...\n` | `Starting ...\n` |
| `<color=red>Start: ` | `<color=red>Startup: ` |
| ` Fehler (` | ` error(s) (` |
| `</b> auf '` | `</b> on '` |
| `AppLink.Update (Verbindung angehalten)` | `AppLink.Update (connection stopped)` |
| `Body.Update (Körper angehalten)` | `Body.Update (body stopped)` |

### `src/AIBody/AppLink.cs`

| Alt | Neu |
|---|---|
| `Engines: warte auf die Companion-App ...` | `Engines: waiting for the companion app ...` |
| `API-Keys: warte auf die Companion-App ...` | `API keys: waiting for the companion app ...` |
| `Echtzeit (Realtime) verwenden` | `Use realtime voice` |
| `Mikrofon-Einstellungen (Storables)` | `Microphone settings (storables)` |
| `Das sah wie ein API-Key aus und wurde NICHT gespeichert. Hier gehört der PFAD einer ` | `That looked like an API key and was NOT saved. Enter the PATH of a text file ` |
| `Textdatei hin, in der der Key steht (z. B. C:/Users/<du>/keys/xai.txt).` | `that contains the key (e.g. C:/Users/<you>/keys/xai.txt).` |
| `Latenz bis zum ersten Ton: ` | `Latency to first sound: ` |
| ` Runden)` | ` turns)` |
| `Test-Ton über Companion` | `Test tone via companion` |
| `Test-Ton über Companion: App nicht verbunden` | `Test tone via companion: app not connected` |
| `Test-Ton über Companion angefordert (kommt als normales speak)` | `Test tone via companion requested (arrives as a normal speak command)` |
| `; ändern: config.json connection.channel oder --channel)` | `; change via config.json connection.channel or --channel)` |
| `AI mode: qa = Spracherkennung -> Grok -> Stimme (nur Sprache). auto / realtime = Grok Voice direkt ` | `AI mode: qa = speech recognition -> Grok -> voice (speech only). auto / realtime = Grok Voice directly ` |
| `(Fallback: Kette). chain = die Engines unter Voice > AI Character.` | `(falls back to the chain). chain = the engines under Voice > AI Character.` |
| `Key auch per Umgebungsvariable XAI_API_KEY / ELEVENLABS_API_KEY vor dem App-Start (gewinnt).` | `Keys can also come from XAI_API_KEY / ELEVENLABS_API_KEY set before starting the app (takes precedence).` |
| `konfiguriert` | `configured` |
| `<color=red>abgelehnt</color>` | `<color=red>rejected</color>` |
| `fehlt` | `missing` |
| `<b>Engine-Status</b> (von der Companion-App)\n` | `<b>Engine status</b> (from the companion app)\n` |
| `Modus: ` | `Mode: ` |
| `Modus: Einfacher Q&A` | `Mode: Simple Q&A` |
| ` (gewählt: ` | ` (selected: ` |
| `Proaktiv: ` | `Proactive: ` |
| `an, nach ` | `on, after ` |
| `aus` | `off` |
| `\n    läuft stattdessen: ` | `\n    running instead: ` |
| `<b>Client Character: Mikrofon und Push-to-Talk</b>` | `<b>Client Character: microphone and push-to-talk</b>` |
| `\nAudio (von der Companion-App geschrieben): ` | `\nAudio (written by the companion app): ` |
| ` (automatisch; falls VaM dort nicht laden kann: ` | ` (automatic; if VaM cannot load from there: ` |
| `Testdatei nicht gefunden: ` | `Test file not found: ` |
| `Stimmen-Liste erweitern` | `Extend voice list` |
| `Engine-Auswahl aktualisieren` | `Update engine choices` |
| `Companion app: verbunden, ` | `Companion app: connected, ` |
| `Audio-Ordner: ` | `Audio folder: ` |
| `bool bad = _turn.Contains("Fehler") \|\| _turn.StartsWith("Nichts") \|\| _turn.StartsWith("Realtime") \|\| _turn.StartsWith("Keine");` | `bool bad = IsProblemTurn(_turn);` |
| `Letzte Runde: ` | `Last turn: ` |
| `Companion app: GETRENNT – verbindet automatisch neu, sobald die App wieder läuft\n` | `Companion app: DISCONNECTED – reconnects automatically as soon as the app runs again\n` |
| `API-Keys: warte auf die Companion-App ...\n` | `API keys: waiting for the companion app ...\n` |

### `src/AIBody/Body.cs`

| Alt | Neu |
|---|---|
| `SpeechPlayer fehlt` | `SpeechPlayer missing` |
| `MorphHelper fehlt` | `MorphHelper missing` |
| `PoseController fehlt` | `PoseController missing` |
| `  Körper-Prüfung: FEHLER ` | `  Body check: ERROR ` |
| `  Pose-Speicher (PosePresets): ` | `  Pose storage (PosePresets): ` |
| `  Posen: ` | `  Poses: ` |
| ` (davon Dateien in Custom/Atom/Person/Pose: ` | ` (files in Custom/Atom/Person/Pose: ` |
| `  Atem-Morph '` | `  Breath morph '` |
| `gefunden` | `found` |
| `NICHT gefunden (Tab AI Character > Breath morph)` | `NOT found (tab AI Character > Breath morph)` |
| `  Ausdrucks-Morphs: ` | `  Expression morphs: ` |
| ` gefunden` | ` found` |
| `  Timeline für ` | `  Timeline for ` |
| ` Geste(n): ` | ` gesture(s): ` |
| `NEIN (Timeline-Plugin fehlt auf dieser Person)` | `NO (Timeline plugin missing on this Person)` |
| `Sprachausgabe (SpeechPlayer)` | `Speech output (SpeechPlayer)` |
| `Ausdrücke (ExpressionController)` | `Expressions (ExpressionController)` |
| `Kopfbewegung (IdleController)` | `Head motion (IdleController)` |
| `Posen/Gesten (PoseController)` | `Poses/gestures (PoseController)` |
| `Befehle (CommandRouter)` | `Commands (CommandRouter)` |
| `Config-Dateien laden` | `Load config files` |
| `Test-Ton abspielen` | `Play test tone` |
| `<b>Posen</b> (per Sprache über die KI, oder hier)` | `<b>Poses</b> (by voice through the AI, or here)` |
| `Pose anwenden` | `Apply pose` |
| `Posen neu laden` | `Reload poses` |
| `<b>Ausdruck und Geste</b>` | `<b>Expression and gesture</b>` |
| `Ausdruck zeigen` | `Show expression` |
| `Ausdrücke neu laden (expressions.json)` | `Reload expressions (expressions.json)` |
| `Geste abspielen` | `Play gesture` |
| `<b>Körper</b> (nur diese Person)` | `<b>Body</b> (this Person only)` |
| `Atem-Morph: Name des Brust-Morphs (Feld darunter)` | `Breath morph: name of the chest morph (field below)` |
| `Feld 'Breath morph' ist nur lesbar (InputField ging nicht).` | `Field 'Breath morph' is read-only (InputField failed).` |
| `Posen: ` | `Poses: ` |
| ` im Menü und für die KI (` | ` in the menu and available to the AI (` |
| `Body control aus = nur Sprache, die KI steuert den Körper nicht. Atem-Morph: Name aus dem Morphs-Tab der Figur.\n` | `Body control off = speech only, the AI does not move the body. Breath morph: a name from the character's Morphs tab.\n` |
| `Pose angewendet: ` | `Pose applied: ` |
| `Pose: PoseController fehlt` | `Pose: PoseController missing` |
| `Ausdruck: keine Morphs auf dieser Figur` | `Expression: no morphs on this character` |
| `Ausdruck: ` | `Expression: ` |
| `<color=red>Ausdruck '` | `<color=red>Unknown expression '` |
| `Geste: PoseController fehlt` | `Gesture: PoseController missing` |
| `<color=red>Geste '` | `<color=red>Gesture '` |
| ` Posen im Menü / für die KI` | ` poses in the menu / available to the AI` |
| `Test-Ton: Sprachausgabe fehlt` | `Test tone: speech output missing` |
| `Test-Ton: Plugin-Ordner nicht gefunden (` | `Test tone: plugin folder not found (` |
| `Test-Ton: Plugin-Ordner nicht gefunden` | `Test tone: plugin folder not found` |
| ` – Speech volume ist 0!` | ` – Speech volume is 0!` |
| `Body control: aus (nur Sprache)\n` | `Body control: off (speech only)\n` |
| `Geste: ` | `Gesture: ` |

### `src/AIBody/CommandRouter.cs`

| Alt | Neu |
|---|---|
| `Befehl ` | `Command ` |
| `Posen/Gesten nicht verfügbar (PoseController fehlt)` | `Poses/gestures not available (PoseController missing)` |
| `Ausdrücke nicht verfügbar (keine Morphs auf dieser Figur)` | `Expressions not available (no morphs on this character)` |
| `Sprachausgabe nicht verfügbar (SpeechPlayer fehlt)` | `Speech output not available (SpeechPlayer missing)` |
| `Kopfbewegung nicht verfügbar` | `Head motion not available` |
| `Atmung nicht verfügbar (keine Morphs)` | `Breathing not available (no morphs)` |

### `src/AIBody/MicConfig.cs`

| Alt | Neu |
|---|---|
| `Mikrofon-Liste: noch keine Antwort (Companion-App starten)` | `Microphone list: no answer yet (start the companion app)` |
| `Push-to-talk active: solange angehakt, hört die Companion-App zu (wie eine gedrückte Funk-Taste). ` | `Push-to-talk active: while checked, the companion app listens (like holding a radio talk button). ` |
| `Mikrofone neu laden` | `Refresh microphones` |
| `<color=red>Mikrofon-Liste: keine Antwort der Companion-App</color> (Konsole prüfen)` | `<color=red>Microphone list: no answer from the companion app</color> (check its console)` |
| `Mikrofon-Liste: Companion-App nicht verbunden - Liste kommt, sobald sie läuft` | `Microphone list: companion app not connected - the list arrives once it runs` |
| `Mikrofon-Liste: angefordert um ` | `Microphone list: requested at ` |
| `Mikrofon-Liste: ` | `Microphone list: ` |
| ` empfangen von der Companion-App` | ` received from the companion app` |
| `</color> (Standard bleibt wählbar)` | `</color> (system default stays selectable)` |
| `\n<color=red>Gespeichertes Mikrofon nicht in der Liste: ` | `\n<color=red>Saved microphone not in the list: ` |
| `, Menü hat ` | `, menu has ` |
| ` Einträge` | ` entries` |
| `, Fehler: ` | `, error: ` |
| `Menü Mic device: ` | `Mic device menu: ` |
| ` \| Windows-Standard: ` | ` \| Windows default: ` |

### `src/AIBody/MorphHelper.cs`

| Alt | Neu |
|---|---|
| `kein DAZCharacterSelector 'geometry'` | `no DAZCharacterSelector 'geometry'` |
| `morphsControlUI ist leer` | `morphsControlUI is empty` |

### `src/AIBody/PoseController.cs`

| Alt | Neu |
|---|---|
| ` Pose-Dateien in ` | ` pose files in ` |
| ` (Ordner nicht lesbar oder leer)` | ` (folders not readable or empty)` |
| `kein Storable 'PosePresets'` | `no storable 'PosePresets'` |
| `Keine Pose gewählt` | `No pose selected` |
| `Unbekannte Pose '` | `Unknown pose '` |

### `src/AIBody/SpeechPlayer.cs`

| Alt | Neu |
|---|---|
| `Audio-Fehler: ` | `Audio error: ` |
| `(kein Pfad)` | `(no path)` |
| `kein Storable 'HeadAudioSource'` | `no storable 'HeadAudioSource'` |
| `kein Kopf-Audio (HeadAudioSource) auf dieser Figur: ` | `no head audio (HeadAudioSource) on this character: ` |
| `Datei fehlt: ` | `File missing: ` |
| ` (schreibt die Companion-App in denselben VaM-Ordner? --vam-root prüfen)` | ` (does the companion app write to the same VaM folder? Check --vam-root)` |
| `QueueClip ging nicht` | `QueueClip failed` |
| `' nicht ladbar?)` | `' not loadable?)` |
| `GetClip fand den geladenen Clip nicht (uid ` | `GetClip did not find the loaded clip (uid ` |
| `Lade: ` | `Loading: ` |
| ` (Achtung: Speech volume ist 0)` | ` (note: Speech volume is 0)` |
| `Spreche: ` | `Speaking: ` |
| `, Speech volume ist 0 – nichts zu hören` | `, Speech volume is 0 – nothing audible` |
| `Spricht ` | `Speaking ` |
| `Clip startete nicht in ` | `Clip did not start within ` |
| `x PlayNow) – Datei nicht ladbar (Format/Pfad) oder Kopf-Audio blockiert: ` | `x PlayNow) – file not loadable (format/path) or head audio blocked: ` |
| `Fertig: ` | `Done: ` |
| `Abgebrochen (` | `Cancelled (` |
| `Ende ` | `End ` |

Hinweis: Texte, die aus mehreren Literalen zusammengesetzt werden, stehen hier als einzelne Teile. Zeilenumbrüche sind als `⏎` dargestellt.

## Begleit-App und Tools: alle übersetzten Texte

### `companion/aibody_companion/cli.py`

| Alt | Neu |
|---|---|
| `Modus: %s -> %s (%s)` | `Mode: %s -> %s (%s)` |
| `Audio-Ordner: %s%s` | `Audio folder: %s%s` |
| ` (automatisch; wechselt einmal nach Saves/PluginData, falls VaM dort nicht laden kann)` | ` (automatic; switches once to Saves/PluginData if VaM cannot load from there)` |
| `Proaktiv: pausiert im Einfachen Q&A-Modus (die KI spricht nur, wenn sie gefragt wird)` | `Proactive: paused in Simple Q&A mode (the AI only speaks when asked)` |
| `Proaktiv: %s, nach %.0f s Stille` | `Proactive: %s, after %.0f s of silence` |
| `an` | `on` |
| `aus` | `off` |
| `AIBody companion %s, Logdatei: %s` | `AIBody companion %s, log file: %s` |
| `keine (Ordner nicht beschreibbar)` | `none (folder not writable)` |
| `Kein xAI-Key: nur Test-Engines (Echo + Ton). %s; XAI_API_KEY setzen oder Key-Datei ` | `No xAI API key: test engines only (echo + tone). %s; set XAI_API_KEY or a key file ` |

### `companion/aibody_companion/latency.py`

| Alt | Neu |
|---|---|
| `an Plugin` | `to plugin` |
| `Plugin-Start` | `plugin start` |
| `Datei` | `file write` |

### `companion/aibody_companion/logsetup.py`

| Alt | Neu |
|---|---|
| `an (Turn-Trace)` | `on (turn trace)` |
| ` - Logdatei {_state['file']}` | ` - log file {_state['file']}` |

### `companion/aibody_companion/orchestrator.py`

| Alt | Neu |
|---|---|
| `Pose-Speicher ja` | `pose storage yes` |
| `Pose-Speicher NEIN ({storage})` | `pose storage NO ({storage})` |
| `Posen {as_number(t.get('poses')) or 0:.0f} (Dateien {as_number(t.get('pose_files')) or 0:.0f})` | `poses {as_number(t.get('poses')) or 0:.0f} (files {as_number(t.get('pose_files')) or 0:.0f})` |
| `Atem-Morph '{t.get('breath_morph', '')}' {'gefunden' if breath else 'NICHT gefunden'}` | `breath morph '{t.get('breath_morph', '')}' {'found' if breath else 'NOT found'}` |
| `Ausdrucks-Morphs {found:.0f}/{total:.0f}{gone}` | `expression morphs {found:.0f}/{total:.0f}{gone}` |
| `Timeline {'ja' if has else 'NEIN'} für {timeline_gestures:.0f} Geste(n)` | `Timeline {'yes' if has else 'NO'} for {timeline_gestures:.0f} gesture(s)` |
| `Einfacher Q&A: Spracherkennung xAI -> Grok -> Stimme xAI, nur Sprache` | `Simple Q&A: xAI speech recognition -> Grok -> xAI voice, speech only` |
| `Einfacher Q&A ohne xAI-Key: nur Test-Engines (Echo + Ton) - ` | `Simple Q&A without an xAI API key: test engines only (echo + tone) - ` |
| `API-Key von console.x.ai (kein Grok-Abo-Token) als XAI_API_KEY oder Key-Datei ` | `set an API key from console.x.ai (not a Grok subscription token) as XAI_API_KEY or a key file ` |
| `Chain gewählt (Spracherkennung -> Sprachmodell -> Sprachausgabe)` | `Chain selected (speech recognition -> language model -> text-to-speech)` |
| `Realtime aus: {self.realtime_off} - Fallback Chain` | `Realtime off: {self.realtime_off} - falling back to the chain` |
| `{' mit xAI' if has_key else ''}; 'API Reconnect' versucht es neu` | `{' with xAI' if has_key else ''}; 'API Reconnect' tries again` |
| `Realtime nicht konfiguriert (kein xAI-Key) - Chain läuft` | `Realtime not configured (no xAI API key) - chain running` |
| `Auto: Chain, weil Text-to-speech = elevenlabs gewählt ist` | `Auto: chain, because Text-to-speech = elevenlabs is selected` |
| `Auto: Chain (kein xAI-Key für Realtime)` | `Auto: chain (no xAI API key for realtime)` |
| `Realtime antwortet nicht (%s) - ab jetzt Chain; 'API Reconnect' versucht es neu` | `Realtime is not responding (%s) - using the chain from now on; 'API Reconnect' tries again` |
| `Realtime antwortete nicht ({reason}) - ab jetzt Chain, bitte Frage wiederholen` | `Realtime did not respond ({reason}) - using the chain from now on, please repeat the question` |
| `Key geändert` | `key changed` |
| `if client.last_error and client.last_error.startswith("API-Key abgelehnt"):` | `if client.last_error and client.last_error.startswith(REALTIME_KEY_REJECTED):` |
| `vom Realtime-Server abgelehnt ({client.last_error})` | `rejected by the realtime server ({client.last_error})` |
| `Realtime verbunden ({client.model}, Stimme {settings['voice']})` | `Realtime connected ({client.model}, voice {settings['voice']})` |
| `Realtime verbindet ... (solange läuft Chain)` | `Realtime connecting ... (chain runs meanwhile)` |
| `Realtime nicht verbunden: {client.last_error or 'getrennt'} - Fallback Chain, ` | `Realtime not connected: {client.last_error or 'disconnected'} - falling back to the chain, ` |
| `pausiert im Einfachen Q&A-Modus` | `paused in Simple Q&A mode` |
| `wartet: braucht Realtime oder Sprachmodell xai` | `waiting: needs realtime or language model xai` |
| `Plugin-Selbsttest: %s` | `Plugin self-test: %s` |
| `Proactive: %.0f s Stille - die KI darf etwas sagen` | `Proactive: %.0f s of silence - the AI may say something` |
| `Latenz %s bis zum ersten Ton: %s` | `Latency %s to first sound: %s` |
| `Mikrofone: keine Liste für das Plugin - %s` | `Microphones: no list for the plugin - %s` |
| `Mikrofone: %d gefunden%s: %s` | `Microphones: %d found%s: %s` |
| `Frage (getippt): {_short(text)}` | `Question (typed): {_short(text)}` |
| `Antwort ({len(said)} Satz/Sätze, {self.engine_set.active_names['llm']} -> ` | `Answer ({len(said)} sentence(s), {self.engine_set.active_names['llm']} -> ` |
| `Keine Antwort: das Sprachmodell lieferte keinen Text` | `No answer: the language model returned no text` |
| `Spracherkennung-Fehler: {_short(str(e), 120)}` | `Speech recognition error: {_short(str(e), 120)}` |
| `Sprachmodell-Fehler: {_short(str(e), 120)}` | `Language model error: {_short(str(e), 120)}` |
| ` - Ersatzantwort` | ` - fallback answer` |
| `Sprachausgabe-Fehler: {_short(str(e), 120)} - Ersatzton ({name})` | `Text-to-speech error: {_short(str(e), 120)} - fallback tone ({name})` |
| `Gehört: {_short(step[1])}` | `Heard: {_short(step[1])}` |
| `{stt_error} - keine Antwort` | `{stt_error} - no answer` |
| `Nichts verstanden: Spracherkennung 'null' (Test) erkennt nichts - xAI-Key nötig` | `Nothing understood: speech recognition 'null' (test) recognizes nothing - xAI API key needed` |
| `Nichts verstanden ({step[2]:.1f} s Ton, Spracherkennung lieferte keinen Text)` | `Nothing understood ({step[2]:.1f} s of audio, speech recognition returned no text)` |
| `VaM konnte {path.name} nicht laden ({_short(message, 100)}); ` | `VaM could not load {path.name} ({_short(message, 100)}); ` |
| `Audio-Ordner fest eingestellt: {current} (connection.paths.audio)` | `audio folder is fixed: {current} (connection.paths.audio)` |
| `VaM konnte {failed_dir} nicht laden - Audio-Ordner gewechselt auf {new}` | `VaM could not load from {failed_dir} - audio folder switched to {new}` |
| `VaM konnte die WAVs weder aus {self.cfg.audio_default_dirs[0]} noch aus ` | `VaM could load the WAVs neither from {self.cfg.audio_default_dirs[0]} nor from ` |
| `{current} laden ({_short(message, 100)}) - siehe TESTPROTOKOLL T9` | `{current} ({_short(message, 100)}) - see TESTPROTOKOLL T9` |

### `companion/aibody_companion/pipeline/engines.py`

| Alt | Neu |
|---|---|
| `bereit` | `ready` |
| `nicht konfiguriert` | `not configured` |
| `nötig: API-Key von console.x.ai (beginnt mit xai-) - ein Grok-Abo / grok.com-Token funktioniert nicht` | `needed: an API key from console.x.ai (starts with xai-) - a Grok subscription / grok.com token does not work` |
| `nötig: API-Key von elevenlabs.io (Profil -> API Keys)` | `needed: an API key from elevenlabs.io (Profile -> API Keys)` |
| `vom Server abgelehnt (HTTP {status})` | `rejected by the server (HTTP {status})` |
| `{kind}: {name!r} gibt es nicht (verfügbar: {', '.join(ENGINES_AVAILABLE[kind])})` | `{kind}: {name!r} does not exist (available: {', '.join(ENGINES_AVAILABLE[kind])})` |

### `companion/aibody_companion/pipeline/keys.py`

| Alt | Neu |
|---|---|
| `{env_name} nicht gesetzt, Key-Datei {path} nicht lesbar` | `{env_name} not set, key file {path} not readable` |
| `Key-Datei {path}` | `key file {path}` |
| `{env_name} nicht gesetzt, Key-Datei {path} ist leer` | `{env_name} not set, key file {path} is empty` |
| `{env_name} nicht gesetzt und kein key_file in config.json` | `{env_name} not set and no key_file in config.json` |

### `companion/aibody_companion/pipeline/realtime.py`

| Alt | Neu |
|---|---|
| `Fehler: {e}` | `Error: {e}` |
| `API-Key abgelehnt (HTTP {e.status})` | `{KEY_REJECTED} (HTTP {e.status})` |
| `nicht konfiguriert (kein xAI-Key)` | `not configured (no xAI API key)` |
| `Realtime: verbunden mit %s` | `Realtime: connected to %s` |

### `companion/aibody_companion/pipeline/xai.py`

| Alt | Neu |
|---|---|
| `nicht konfiguriert (kein API-Key)` | `not configured (no API key)` |

### `companion/aibody_companion/realtime_voice.py`

| Alt | Neu |
|---|---|
| `keine Antwort {ANSWER_TIMEOUT_S:.0f} s nach dem Sprechen` | `no answer {ANSWER_TIMEOUT_S:.0f} s after speaking` |

### `tools/build_var.py`

| Alt | Neu |
|---|---|
| `Test-Ton abspielen` | `Play test tone` |

### `tools/gen_config_schema.py`

| Alt | Neu |
|---|---|
| `Tab 'Verbindung': channel (folder below Saves/PluginData/AIBody), link on/off, data file paths ` | `Connection (link on/off in tab 'Voice'): channel (folder below Saves/PluginData/AIBody), data file paths ` |
| `Tab 'Mikrofon & PTT': captured by the companion app; push-to-talk state itself is never saved` | `Tab 'Client Character': captured by the companion app; push-to-talk state itself is never saved` |
| `Tab 'Körper'` | `Tab 'AI Character', section 'Body (this Person only)'` |
| `Tab 'Erweitert'` | `Tab 'Config' (file poll interval, verbose log)` |

### `tools/mic_test.py`

| Alt | Neu |
|---|---|
| `== Alle Geräte, roh ({len(devices)}) ==` | `== All devices, raw ({len(devices)}) ==` |
| `== Eingabegeräte pro Host-API ==` | `== Input devices per host API ==` |
| `sounddevice ist NICHT installiert: pip install sounddevice` | `sounddevice is NOT installed: pip install sounddevice` |
| `== Liste, die die Companion-App an das Plugin schickt ({len(found)}) ==` | `== List the companion app sends to the plugin ({len(found)}) ==` |
| `  Fehler: {error}` | `  Error: {error}` |
| `  (* = Windows-Standard; im Plugin-Menü steht davor immer 'Standard (System-Mikrofon)')` | `  (* = Windows default; the plugin menu always lists 'System default microphone' first)` |
| `AIBody Mikrofon-Test (ohne VaM und Companion-App)` | `AIBody microphone test (without VaM and the companion app)` |
| `VaM-Hauptordner: legt die Liste zusätzlich in den Plugin-Eingang` | `VaM root folder: also drops the list into the plugin inbox` |
| `Kanal des Plugins (Standard: default)` | `plugin channel (default: default)` |
| `  -> in VaM Tab 'Client Character' öffnen: Menü 'Mic device' und Infofeld zeigen jetzt diese Liste.` | `  -> in VaM open tab 'Client Character': the 'Mic device' menu and the info panel now show this list.` |
| `Ausgabe gespeichert: {folder / 'mic_test_output.txt'} (bitte zurückschicken)` | `output saved: {folder / 'mic_test_output.txt'} (please send it back)` |

## Bezeichner

Die Bezeichner im Code (Klassen, Methoden, Felder, Variablen, Dateien) waren bereits englisch, mit einer Ausnahme im Test-Code. Neu für Version 18:

| Alt | Neu | Art |
|---|---|---|
| `test_pose_section_is_called_posen` (`companion/tests/test_plugin_menu.py`) | `test_pose_section_is_called_poses` | Testname umbenannt |
| – | `AppLink.IsProblemTurn(string)` (`src/AIBody/AppLink.cs`) | neu: entscheidet, ob die Zeile „Last turn“ rot erscheint (englische und alte deutsche Texte) |
| `MicDeviceList.DefaultChoice = "Standard (System-Mikrofon)"` | `MicDeviceList.DefaultChoice = "System default microphone"` | Wert geändert |
| – | `MicDeviceList.LegacyDefaultV16 = "Standard (System-Mikrofon)"` | neu: alter Wert aus Szenen von Version 16/17 |
| – | `MicDeviceList.IsLegacyDefault(string)` | neu: erkennt `(system default)` (bis Version 15) und `Standard (System-Mikrofon)` |
| `startswith("API-Key abgelehnt")` (Orchestrator) | `KEY_REJECTED = "API key rejected"` in `pipeline/realtime.py`, im Orchestrator als `REALTIME_KEY_REJECTED` | neu: eine Konstante statt zweier gekoppelter Texte |
| – | `Version18MenuTests` (`companion/tests/test_plugin_menu.py`) | neue Testklasse |

## Kommentare je Datei (zusammengefasst)

| Datei | Was geändert wurde |
|---|---|
| `src/AIBody/AIBody.cs` | Kopfkommentar (Tab-Übersicht mit englischen Beschriftungen), Kommentare zu Tabs, Diagnose und Infofeld; Hinweis auf entfallene Tabs ohne deutschen Tab-Namen. |
| `src/AIBody/AppLink.cs` | XML-Doku der Knöpfe (Simple Q&A mode, Test tone via companion), Heartbeat-/Status-Kommentare, Latenz- und Modus-Doku mit den englischen Beispielzeilen, IsProblemTurn. |
| `src/AIBody/Body.cs` | Kommentare zum Posen-Menü und zum Selbsttest. |
| `src/AIBody/MicConfig.cs` | Kommentare zur Mikrofonliste, Migration des alten Standard-Eintrags, Infofeld-Zeilen. |
| `src/AIBody/MicDeviceList.cs` | Dateikopf und XML-Doku der Standard-/Legacy-Einträge. |
| `src/AIBody/SpeechPlayer.cs` | Dateikopf (Statuswerte Loading/Speaking/Done/Cancelled) und Doku von LastError. |
| `src/AIBody/CommandRouter.cs, Diag.cs, MorphHelper.cs, PoseController.cs` | einzelne Kommentare mit zitierten deutschen Texten. |
| `companion/aibody_companion/latency.py` | Modul-Docstring mit der Aufschlüsselung (LLM first token, first sentence, file write, to plugin, plugin start, server first audio). |
| `companion/aibody_companion/logsetup.py` | Docstring-Beispiel einer Trace-Zeile („What time is it?“). |
| `companion/aibody_companion/pipeline/engines.py, keys.py, elevenlabs.py, tts.py, protocol.py` | Docstrings/Kommentare, die die Statuswerte zitieren („not configured“, „ready“, „file write“). |
| `companion/aibody_companion/pipeline/realtime.py` | neuer Kommentar zu KEY_REJECTED. |
| `tools/build_var.py` | Kommentar zum Testton („Play test tone“). |
| `tools/gen_config_schema.py` | Beschreibungen der config.json-Abschnitte zeigen die aktuellen Tabs (Voice, AI Character, Client Character, Config) statt der alten deutschen Tab-Namen; `protocol/schema/config.schema.json` neu erzeugt. |
| `tools/cs_tests/MicDeviceListTests.cs` | Prüftexte „Standard“ → „default“; neue Prüfungen für den alten deutschen Eintrag. |
| `companion/tests/*.py` | Erwartungen auf die neuen englischen Texte umgestellt; Eingaben, die deutsche Nutzersprache simulieren („Hallo“, „Wie spät ist es?“), und deutsche Gerätenamen in den Testdaten bleiben. |

## Gespeicherte Namen, Protokoll und Kompatibilität

- **JSONStorable-Namen:** alle registrierten Namen waren bereits englisch (geprüft über alle `Register*`-Aufrufe); keiner wurde umbenannt (Leons Entscheidung zur Umbenennung bleibt zurückgestellt). Der Schalter „Use realtime voice“ ist nicht registriert und wird nicht gespeichert. Bestehende Szenen laden unverändert.
- **Gespeicherter Wert „Mic device“:** Szenen aus Version 16/17 enthalten `Standard (System-Mikrofon)`, ältere `(system default)`. Beide werden beim Laden als Systemstandard erkannt (`MicDeviceList.IsLegacyDefault`) und im Menü als `System default microphone` angezeigt; `MicConfig.Update` setzt den Wert einmal um. In config.json steht für den Standard weiter `""` (`mic.device`), daran ändert sich nichts.
- **config.json-Schlüssel:** unverändert (alle englisch). Nur die Beschreibungen im Schema (`protocol/schema/config.schema.json`) sind aktualisiert.
- **Datei-Protokoll Plugin ↔ Begleit-App:** Nachrichtentypen und Felder (`list_devices`, `devices`, `heartbeat`, `turn`, `engines_status`, `selftest`, …) waren bereits englisch und bleiben gleich. Geändert haben sich nur Anzeigetexte, die als Werte übertragen werden (z. B. `turn`, `mode.status`, Engine-Status, Latenz-Aufschlüsselung). Das Plugin wertet davon nur einen Punkt aus: ob die Zeile „Last turn“ rot erscheint. `AppLink.IsProblemTurn` erkennt dafür die neuen englischen Texte (`Nothing…`, `No …`, `Realtime…`, `error`/`Error`) **und** die deutschen Texte älterer Begleit-Apps (`Nichts…`, `Keine…`, `Fehler`). Eine ältere Begleit-App mit dem neuen Plugin (oder umgekehrt) funktioniert also weiter; die Texte erscheinen dann in der Sprache der jeweiligen Seite.
- **Kopplung innerhalb der Begleit-App:** Der Orchestrator erkannte einen vom Realtime-Server abgelehnten Key am Text `API-Key abgelehnt`. Beide Seiten nutzen jetzt die Konstante `KEY_REJECTED = "API key rejected"` (`pipeline/realtime.py`), damit Text und Prüfung nicht auseinanderlaufen.
- **Engine-Status:** `bereit` → `ready`, `nicht konfiguriert` → `not configured` (Konstanten `READY`/`NOT_CONFIGURED` in `pipeline/engines.py`); das Plugin zeigt diese Werte nur an.

## Bewusst Deutsch geblieben

| Stelle | Grund |
|---|---|
| `MicDeviceList.LegacyDefaultV16 = "Standard (System-Mikrofon)"` | Kompatibilität: alter gespeicherter Wert aus Szenen von Version 16/17 |
| `AppLink.IsProblemTurn`: Präfixe `Nichts`, `Keine`, Teiltext `Fehler` | Kompatibilität: Statuszeilen älterer Begleit-Apps rot markieren |
| `orchestrator.py` `LLM_ERROR_SAY["de"]` | gesprochene Fehlermeldung, wenn die Persona-Sprache Deutsch ist (Inhalt, kein Oberflächentext; `"en"` gibt es daneben) |
| `pipeline/context.py` `_SILENT_WORDS` (`schweigen`, `schweigt`, `stille`) | Erkennung von „schweigen“-Antworten des Modells in deutscher Sprache |
| `pipeline/llm.py` Echo-Test-Engine (`hallo`, `danke`, `nein`, `traurig`) | erkennt Wörter in der Nutzereingabe, auch auf Deutsch |
| `pipeline/sentences.py` Abkürzungen (`z.b`, `bzw`, `usw`, …) | Satztrennung für deutsche Texte |
| Gerätenamen, Host-API-Namen, Systemmeldungen | kommen vom System in dessen Sprache (Regel oben) |
| Testdaten mit deutscher Nutzersprache und deutschen Gerätenamen | simulieren echte Eingaben und Windows-Geräte |
| Dokumentation (README, SPEC, ANFORDERUNGEN, BACKLOG, TESTPROTOKOLL, Release Notes) | bleibt Deutsch nach Vorgabe; nur zitierte Oberflächentexte sind englisch. Ältere Einträge der Änderungsliste nennen die damaligen deutschen Bezeichnungen, wo es um die Geschichte geht. |
