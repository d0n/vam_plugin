# Translation version 18: plugin UI and outputs in English

Status: 18.11.2026, version 18 (package `d0n.AIBody.18.var`). Leon's order: translate all German, user-visible texts of the plugin into natural English for an IT / developer audience, as well as identifiers and comments in the code; function and layout unchanged. The console, log and status texts of the companion app and the output of `tools/mic_test.py` belong to the same interface and are translated too. At that time the documentation (README, SPEC, REQUIREMENTS, BACKLOG, TEST_PROTOCOL) stayed German; since 19.11.2026 it is English as well. **The "Old (German)" columns below deliberately quote the old German texts: they are data of this record, not documentation language.**

## Rule: what is translated and what is not

- Only **own** texts are translated: field names, labels, headings, info and status texts, log and self-test lines, button texts and own fixed menu entries (e.g. "Standard (System-Mikrofon)" → "System default microphone"). Goal: wording in international standard English, understandable regardless of the system language.
- **Not** translated is content that the operating system or VaM supplies in its language: microphone device names (e.g. "Mikrofon (Realtek(R) Audio)"), names of the Windows default devices (e.g. "Primärer Soundaufnahmetreiber"), host API names, system error messages. They appear in the menu, the info field and the `mic_test.py` output exactly as the system names them (Leon, 18.11.2026).
- Stored names stay unchanged (see below): JSONStorable names, config.json keys, message types and fields of the file protocol.

## Numbers

| Category | Count |
|---|---|
| Plugin: translated texts (unique string literals, `src/AIBody/*.cs`) | 182 |
| Companion app and tools: translated texts (unique literals / lines) | 93 |
| Comment / docstring places with German text (plugin / companion app + tools) | 25 / 6 |
| Identifiers renamed (German → English) | 1 (a test name) |
| New identifiers for compatibility | 5 |
| Test expectations adjusted (German → English texts) | 65 |
| New tests | 3 Python (Version18MenuTests) + 3 C# checks (MicDeviceListTests) |
| Stored names renamed | 0 |

## Main labels

| Old (German) | New (English) |
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

## Plugin: all translated texts (`src/AIBody`)

### `src/AIBody/AIBody.cs`

| Old (German) | New (English) |
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

| Old (German) | New (English) |
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
| `bool bad = _turn.Contains("Fehler") \|\| _turn.StartsWith("Nichts") \|\| _turn.StartsWith("Realtime") \|\| turn.StartsWith("None"); ` | `bool bad = IsProblemTurn(_turn);` |
| `Letzte Runde: ` | `Last turn: ` |
| `Companion app: GETRENNT – verbindet automatisch neu, sobald die App wieder läuft\n` | `Companion app: DISCONNECTED – reconnects automatically as soon as the app runs again\n` |
| `API-Keys: warte auf die Companion-App ...\n` | `API keys: waiting for the companion app ...\n` |

### `src/AIBody/Body.cs`

| Old (German) | New (English) |
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

| Old (German) | New (English) |
|---|---|
| `Befehl ` | `Command ` |
| `Posen/Gesten nicht verfügbar (PoseController fehlt)` | `Poses/gestures not available (PoseController missing)` |
| `Ausdrücke nicht verfügbar (keine Morphs auf dieser Figur)` | `Expressions not available (no morphs on this character)` |
| `Sprachausgabe nicht verfügbar (SpeechPlayer fehlt)` | `Speech output not available (SpeechPlayer missing)` |
| `Kopfbewegung nicht verfügbar` | `Head motion not available` |
| `Atmung nicht verfügbar (keine Morphs)` | `Breathing not available (no morphs)` |

### `src/AIBody/MicConfig.cs`

| Old (German) | New (English) |
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

| Old (German) | New (English) |
|---|---|
| `kein DAZCharacterSelector 'geometry'` | `no DAZCharacterSelector 'geometry'` |
| `morphsControlUI ist leer` | `morphsControlUI is empty` |

### `src/AIBody/PoseController.cs`

| Old (German) | New (English) |
|---|---|
| ` Pose-Dateien in ` | ` pose files in ` |
| ` (Ordner nicht lesbar oder leer)` | ` (folders not readable or empty)` |
| `kein Storable 'PosePresets'` | `no storable 'PosePresets'` |
| `Keine Pose gewählt` | `No pose selected` |
| `Unbekannte Pose '` | `Unknown pose '` |

### `src/AIBody/SpeechPlayer.cs`

| Old (German) | New (English) |
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

Note: texts composed of several string literals are listed here as individual parts. Line breaks are shown as `⏎`.

## Companion app and tools: all translated texts

### `companion/aibody_companion/cli.py`

| Old (German) | New (English) |
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

| Old (German) | New (English) |
|---|---|
| `an Plugin` | `to plugin` |
| `Plugin-Start` | `plugin start` |
| `Datei` | `file write` |

### `companion/aibody_companion/logsetup.py`

| Old (German) | New (English) |
|---|---|
| `an (Turn-Trace)` | `on (turn trace)` |
| ` - Logdatei {_state['file']}` | ` - log file {_state['file']}` |

### `companion/aibody_companion/orchestrator.py`

| Old (German) | New (English) |
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

| Old (German) | New (English) |
|---|---|
| `bereit` | `ready` |
| `nicht konfiguriert` | `not configured` |
| `nötig: API-Key von console.x.ai (beginnt mit xai-) - ein Grok-Abo / grok.com-Token funktioniert nicht` | `needed: an API key from console.x.ai (starts with xai-) - a Grok subscription / grok.com token does not work` |
| `nötig: API-Key von elevenlabs.io (Profil -> API Keys)` | `needed: an API key from elevenlabs.io (Profile -> API Keys)` |
| `vom Server abgelehnt (HTTP {status})` | `rejected by the server (HTTP {status})` |
| `{kind}: {name!r} gibt es nicht (verfügbar: {', '.join(ENGINES_AVAILABLE[kind])})` | `{kind}: {name!r} does not exist (available: {', '.join(ENGINES_AVAILABLE[kind])})` |

### `companion/aibody_companion/pipeline/keys.py`

| Old (German) | New (English) |
|---|---|
| `{env_name} nicht gesetzt, Key-Datei {path} nicht lesbar` | `{env_name} not set, key file {path} not readable` |
| `Key-Datei {path}` | `key file {path}` |
| `{env_name} nicht gesetzt, Key-Datei {path} ist leer` | `{env_name} not set, key file {path} is empty` |
| `{env_name} nicht gesetzt und kein key_file in config.json` | `{env_name} not set and no key_file in config.json` |

### `companion/aibody_companion/pipeline/realtime.py`

| Old (German) | New (English) |
|---|---|
| `Fehler: {e}` | `Error: {e}` |
| `API-Key abgelehnt (HTTP {e.status})` | `{KEY_REJECTED} (HTTP {e.status})` |
| `nicht konfiguriert (kein xAI-Key)` | `not configured (no xAI API key)` |
| `Realtime: verbunden mit %s` | `Realtime: connected to %s` |

### `companion/aibody_companion/pipeline/xai.py`

| Old (German) | New (English) |
|---|---|
| `nicht konfiguriert (kein API-Key)` | `not configured (no API key)` |

### `companion/aibody_companion/realtime_voice.py`

| Old (German) | New (English) |
|---|---|
| `keine Antwort {ANSWER_TIMEOUT_S:.0f} s nach dem Sprechen` | `no answer {ANSWER_TIMEOUT_S:.0f} s after speaking` |

### `tools/build_var.py`

| Old (German) | New (English) |
|---|---|
| `Test-Ton abspielen` | `Play test tone` |

### `tools/gen_config_schema.py`

| Old (German) | New (English) |
|---|---|
| `Tab 'Verbindung': channel (folder below Saves/PluginData/AIBody), link on/off, data file paths ` | `Connection (link on/off in tab 'Voice'): channel (folder below Saves/PluginData/AIBody), data file paths ` |
| `Tab 'Mikrofon & PTT': captured by the companion app; push-to-talk state itself is never saved` | `Tab 'Client Character': captured by the companion app; push-to-talk state itself is never saved` |
| `Tab 'Körper'` | `Tab 'AI Character', section 'Body (this Person only)'` |
| `Tab 'Erweitert'` | `Tab 'Config' (file poll interval, verbose log)` |

### `tools/mic_test.py`

| Old (German) | New (English) |
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

## Identifiers

The identifiers in the code (classes, methods, fields, variables, files) were already English, with one exception in the test code. New for version 18:

| Old | New | Kind |
|---|---|---|
| `test_pose_section_is_called_posen` (`companion/tests/test_plugin_menu.py`) | `test_pose_section_is_called_poses` | test renamed |
| – | `AppLink.IsProblemTurn(string)` (`src/AIBody/AppLink.cs`) | new: decides whether the line "Last turn" is shown in red (English and old German texts) |
| `MicDeviceList.DefaultChoice = "Standard (System-Mikrofon)"` | `MicDeviceList.DefaultChoice = "System default microphone"` | value changed |
| – | `MicDeviceList.LegacyDefaultV16 = "Standard (System-Mikrofon)"` | new: old value from scenes of version 16/17 |
| – | `MicDeviceList.IsLegacyDefault(string)` | new: recognizes `(system default)` (until version 15) and `Standard (System-Mikrofon)` |
| `startswith("API-Key abgelehnt")` (orchestrator) | `KEY_REJECTED = "API key rejected"` in `pipeline/realtime.py`, in the orchestrator as `REALTIME_KEY_REJECTED` | new: one constant instead of two coupled texts |
| – | `Version18MenuTests` (`companion/tests/test_plugin_menu.py`) | new test class |

(Version 22 removed `MicDeviceList`; the entries stay here as the record of version 18.)

## Comments per file (summary)

| File | What changed |
|---|---|
| `src/AIBody/AIBody.cs` | Header comment (tab overview with English labels), comments on tabs, diagnosis and info field; note on removed tabs without a German tab name. |
| `src/AIBody/AppLink.cs` | XML docs of the buttons (Simple Q&A mode, Test tone via companion), heartbeat / status comments, latency and mode docs with the English example lines, IsProblemTurn. |
| `src/AIBody/Body.cs` | Comments on the pose menu and the self-test. |
| `src/AIBody/MicConfig.cs` | Comments on the microphone list, migration of the old default entry, info field lines. |
| `src/AIBody/MicDeviceList.cs` | File header and XML docs of the default / legacy entries. |
| `src/AIBody/SpeechPlayer.cs` | File header (status values Loading / Speaking / Done / Cancelled) and docs of LastError. |
| `src/AIBody/CommandRouter.cs, Diag.cs, MorphHelper.cs, PoseController.cs` | Single comments with quoted German texts. |
| `companion/aibody_companion/latency.py` | Module docstring with the breakdown (LLM first token, first sentence, file write, to plugin, plugin start, server first audio). |
| `companion/aibody_companion/logsetup.py` | Docstring example of a trace line ("What time is it?"). |
| `companion/aibody_companion/pipeline/engines.py, keys.py, elevenlabs.py, tts.py, protocol.py` | Docstrings / comments that quote the status values ("not configured", "ready", "file write"). |
| `companion/aibody_companion/pipeline/realtime.py` | New comment on KEY_REJECTED. |
| `tools/build_var.py` | Comment on the test tone ("Play test tone"). |
| `tools/gen_config_schema.py` | Descriptions of the config.json sections show the current tabs (Voice, AI Character, Client Character, Config) instead of the old German tab names; `protocol/schema/config.schema.json` regenerated. |
| `tools/cs_tests/MicDeviceListTests.cs` | Check texts "Standard" → "default"; new checks for the old German entry. |
| `companion/tests/*.py` | Expectations switched to the new English texts; inputs that simulate German user speech ("Hallo", "Wie spät ist es?") and German device names in the test data stay. |

## Stored names, protocol and compatibility

- **JSONStorable names:** all registered names were already English (checked over all `Register*` calls); none was renamed (Leon's decision on renaming stays postponed). The toggle "Use realtime voice" is not registered and not stored. Existing scenes load unchanged.
- **Stored value "Mic device":** scenes of version 16/17 contain `Standard (System-Mikrofon)`, older ones `(system default)`. Both are recognized as the system default on loading (`MicDeviceList.IsLegacyDefault`) and shown in the menu as `System default microphone`; `MicConfig.Update` converts the value once. In config.json the default is still `""` (`mic.device`), nothing changes there.
- **config.json keys:** unchanged (all English). Only the descriptions in the schema (`protocol/schema/config.schema.json`) are updated.
- **File protocol plugin ↔ companion app:** message types and fields (`list_devices`, `devices`, `heartbeat`, `turn`, `engines_status`, `selftest`, …) were already English and stay the same. Only display texts that are transmitted as values changed (e.g. `turn`, `mode.status`, engine status, latency breakdown). The plugin evaluates only one point of them: whether the line "Last turn" is shown in red. `AppLink.IsProblemTurn` recognizes the new English texts (`Nothing…`, `No …`, `Realtime…`, `error` / `Error`) **and** the German texts of older companion apps (`Nichts…`, `Keine…`, `Fehler`). So an older companion app with the new plugin (or the other way round) keeps working; the texts then appear in the language of the respective side.
- **Coupling inside the companion app:** the orchestrator recognized a key rejected by the realtime server by the text `API-Key abgelehnt`. Both sides now use the constant `KEY_REJECTED = "API key rejected"` (`pipeline/realtime.py`), so that text and check do not drift apart.
- **Engine status:** `bereit` → `ready`, `nicht konfiguriert` → `not configured` (constants `READY` / `NOT_CONFIGURED` in `pipeline/engines.py`); the plugin only displays these values.

## Deliberately still German

| Place | Reason |
|---|---|
| `MicDeviceList.LegacyDefaultV16 = "Standard (System-Mikrofon)"` | compatibility: old stored value from scenes of version 16/17 |
| `AppLink.IsProblemTurn`: prefixes `Nichts`, `Keine`, part `Fehler` | compatibility: mark status lines of older companion apps in red |
| `orchestrator.py` `LLM_ERROR_SAY["de"]` | spoken error message when the persona language is German (content, not UI text; `"en"` exists next to it) |
| `pipeline/context.py` `_SILENT_WORDS` (`schweigen`, `schweigt`, `stille`) | recognizing "stay silent" answers of the model in German |
| `pipeline/llm.py` echo test engine (`hallo`, `danke`, `nein`, `traurig`) | recognizes words in the user input, also German ones |
| `pipeline/sentences.py` abbreviations (`z.b`, `bzw`, `usw`, …) | sentence splitting for German texts |
| Device names, host API names, system messages | come from the system in its language (rule above) |
