# AIBody

Virt-A-Mate-Plugin (VaM 1.22) mit Python-Begleit-App, das einer KI einen Körper in einer VaM-Szene gibt. Stand: v0.7.4, Paket `d0n.AIBody.11.var`. Noch nicht in VaM getestet.

Weitere Dokumente: [SPEC](docs/SPEC.md) (vereinbarter Umfang) · [ANFORDERUNGEN](docs/ANFORDERUNGEN.md) (umgesetzt / offen) · [BACKLOG](docs/BACKLOG.md) (zurückgestellte Ideen) · [TESTPROTOKOLL](docs/TESTPROTOKOLL.md) · [TECHNIK](docs/TECHNIK.md) (Architektur, Protokoll, Sandbox, englisch) · [API_AUDIT](docs/API_AUDIT.md) · [Releases](https://github.com/d0n/vam_plugin/releases) (Installation und Schnellstart je Version in den Release-Notes).

## 1. Wozu und wie benutzt

- Der Nutzer spricht mit einer Figur in VaM. Die Figur antwortet mit Stimme und Lippensync und kann Ausdrücke, Gesten und Posen zeigen; dazu Atmung und Kopf-Leerlauf.
- Zwei Teile, beide nötig:
  - Plugin `AIBody` (C#, ohne Netzwerkcode): wird einmal im Plugins-Tab der KI-Figur (Person-Atom) geladen; spielt Sprache ab, steuert den Körper, zeigt Status und Einstellungen.
  - Begleit-App `aibody_companion` (Python, läuft neben VaM auf demselben PC): Mikrofon, Spracherkennung, Sprachmodell, Sprachausgabe, Verbindung zu xAI (optional ElevenLabs).
- Verbindung: Dateien unter `<VaM>/Saves/PluginData/AIBody/<Kanal>/`; Sprache als WAV unter `<VaM>/Custom/Sounds/AIBody/<Kanal>/`.
- Ablauf: Plugin auf die KI-Figur laden → Begleit-App starten (`python -m aibody_companion --vam-root "<VaM>"`, mit xAI-Key) → sprechen (oder in der Konsole tippen) → die Figur antwortet.
- Kurzinstallation: `d0n.AIBody.11.var` nach `<VaM>/AddonPackages/`, ältere `d0n.AIBody.*`, `d0n.AIBodySession.*`, `d0n.AIBodyPerson.*`, `d0n.AIBodyPerson2.*` löschen; Person auswählen > Tab Plugins > Add Plugin > `AddonPackages > d0n.AIBody.11:/Custom/Scripts/d0n/AIBody/AIBody.cslist`; Begleit-App: `cd companion`, `pip install sounddevice`, dann starten wie oben. Details und Schritt-für-Schritt: Release-Notes.

## 2. Wofür ausgelegt / Spezifikation

- Mitgelieferte Szene: [`examples/scenes/AIBody_GreenScreen.json`](examples/scenes/AIBody_GreenScreen.json), Anleitung [`docs/SZENE_GREENSCREEN.md`](docs/SZENE_GREENSCREEN.md). Inhalt: eine Person mit AIBody (`d0n.AIBody.11`) im Plugins-Tab, Sallys Szenen-Plugin *Camera Background Color* (`Sally.CameraBackgroundColor.7`, Farbe #00FF00, Skybox aus), zwei unsichtbare Lichter, kein Raum. Gedacht für Passthrough per Chroma-Key in Brille/Streaming-Programm; VaM selbst zeigt nur Grün. Nicht in VaM getestet.
- Das Plugin funktioniert auch in anderen Szenen, solange es auf einer Person liegt.
- Kurzfassung der Spezifikation (vollständig: [SPEC.md](docs/SPEC.md)):
  - VaM-Sandbox: kein Netzwerk-, `System.IO`-, Reflection-, Mikrofon-Code im Plugin; nur belegte APIs; Dateizugriff nur über `FileManagerSecure`; „Allow Plugins Network Access“ bleibt aus.
  - Netzwerk nur in der Begleit-App.
  - Ein Plugin, eine `.cslist`, eine MVRScript-Klasse, ein Ladeschritt.
  - Datei-Transport (Protokoll v3) und eine gemeinsame `config.json`.
  - xAI braucht einen API-Key von console.x.ai; ein Grok-Abo funktioniert nicht.
  - Standardmodus Einfacher Q&A (nur Sprache); Realtime optional.
  - Die KI steuert den Körper per Tool-Aufruf (nicht im Q&A-Modus, nicht bei Body control aus); Posen zusätzlich manuell im Tab AI Character.
  - Das Menü zeigt nur Einstellbares.
  - Verbose log und Latenzmessung (Sprechende bis erster Ton) im Statusfeld.

## 3. Zwei Figuren: AI Character und Client Character

- AI Character = der Körper der KI: die Person, auf der das Plugin geladen ist. Tab *AI Character*: KI-Modus, Stimme, Posen, Ausdrücke, Gesten, Körper.
- Client Character = der menschliche Nutzer, der mit der KI spricht. Tab *Client Character*: Mikrofon (aufgenommen von der Begleit-App am PC), Push-to-Talk, Unterbrechen per Stimme.
- Umsetzung im Code: beide Rollen stecken in dem einen Plugin auf der KI-Person. Für den Nutzer gibt es kein eigenes Atom und kein eigenes Plugin; seine Eingabe kommt über Mikrofon/Push-to-Talk bzw. Texteingabe in der Konsole der Begleit-App.
- Nicht vorgesehen und nicht getestet:
  - AIBody ohne Nutzerseite (ohne laufende Begleit-App gibt es weder Zuhören noch Antworten; das Plugin bleibt stabil und zeigt „GETRENNT“).
  - AIBody auf einem Nicht-Person-Atom (das Plugin-Fenster erklärt dann nur, wohin es gehört).
  - AIBody auf einer zweiten Person bzw. zwei Instanzen auf demselben Kanal (beide würden dieselben Dateien lesen).
  - Client Character als eigene Figur/eigenes Atom und eine zweite KI-Figur: zurückgestellt, siehe [BACKLOG](docs/BACKLOG.md).

## 4. Einstellungen

### 4.1 Orte und Vorrang

- Plugin-Menü (rechte Spalte, Tabs): Werte werden mit der Szene gespeichert.
- `config.json`: `<VaM>/Saves/PluginData/AIBody/config.json`, eine Datei für alle Kanäle, gelesen von Plugin und Begleit-App. Schema: `protocol/schema/config.schema.json`, Beispiel: `examples/config.json`.
  - Fehlt die Datei: die Begleit-App legt sie beim Start mit Standardwerten an; das Plugin schreibt sie ca. 2 s nach dem Laden aus seinen Menüwerten.
  - Szene ohne gespeicherte AIBody-Werte (internes Feld „Settings initialized“ = false): das Plugin übernimmt die Datei einmal.
  - Szene mit gespeicherten Werten: die Menüwerte gewinnen und werden zurückgeschrieben (innerhalb 1 s nach einer Änderung).
  - Tab *Config* > **Reload Config JSON**: übernimmt die ganze Datei ins Menü und schickt sie an die App.
  - Die Begleit-App liest die Datei beim Start (Kanal, Mikrofon, Engines, `ai`, `advanced.verbose_log`) und ergänzt fehlende `ai`-Schlüssel mit Standardwerten. Änderungen im Menü kommen live als `config`-Ereignis an.
  - Das Plugin schreibt Zahlen und true/false als Text (`"2.5"`, `"true"`); beide Formen sind gültig.
  - Unbekannte Schlüssel werden gemeldet und ignoriert; Zahlen außerhalb des Bereichs werden auf den Bereich begrenzt; ungültige Werte fallen auf den Standard zurück (Meldung in der App-Konsole).
  - Abschnitt `ai` gehört der Begleit-App; das Plugin schreibt dort nur die Schlüssel, für die es ein Bedienelement hat (in der Tabelle mit Tab angegeben), und lässt den Rest unverändert.
- Kommandozeile und `--config`-Datei der Begleit-App (4.4), Umgebungsvariablen (4.5).
- Erklär- und Statustexte im Menü bleiben dort; reine Pfad-/Info-Anzeigen gibt es nicht (Pfade stehen einmal im VaM-Log: `Settings file: … | Expressions: … | Gestures: … | Audio …`).

### 4.2 config.json

Spalte „Wo“: Tab im Plugin-Menü; „nur Datei“ = kein Bedienelement. Bereich in eckigen Klammern; „Plugin-Regler“ nennt abweichende Reglergrenzen im Menü.

| Schlüssel | Typ | Standard | Werte | Wirkung | Wo |
|---|---|---|---|---|---|
| `version` | int | 1 | 1 | Schema-Version; andere Werte: Warnung, Kompatibles wird gelesen | nur Datei |
| `written_by` | string | – | frei | wer die Datei zuletzt schrieb (nur Info) | wird geschrieben |
| `connection.channel` | string | `default` | Buchstaben, Ziffern, `-`, `_` (anderes wird zu `_`) | Unterordner `Saves/PluginData/AIBody/<Kanal>/` für die Nachrichtendateien und `Custom/Sounds/AIBody/<Kanal>/` für Audio; Plugin und App müssen gleich sein; `--channel` gewinnt in der App; Änderung startet die Verbindung neu | Post: **Channel** |
| `connection.active` | bool | true | | Verbindung zur Begleit-App an/aus | Voice Mode: **Active** |
| `connection.paths.expressions` | string | `Saves/PluginData/AIBody/expressions.json` | relativ, unter `Saves/` oder `Custom/`, ohne `..` und `:` | Datei mit Ausdrucks-Presets (4.6) | nur Datei |
| `connection.paths.gestures` | string | `Saves/PluginData/AIBody/gestures.json` | wie oben | Datei mit Gesten/Posen (4.6) | nur Datei |
| `connection.paths.audio` | string | `""` | `""` oder relativ unter `Saves/`/`Custom/` | Ordner für die Sprach-WAVs. `""` = automatisch `Custom/Sounds/AIBody/<Kanal>`; kann VaM eine WAV dort nicht laden, wechselt die App einmal nach `Saves/PluginData/AIBody/<Kanal>/audio` und spielt neu ab (rote Zeile im Statusfeld). Fester Ordner = kein Wechsel | nur Datei |
| `engines.stt` | string | `null` | `null`, `xai` | Spracherkennung (`null` = offline, hört nichts) | AI: **Speech-to-text** |
| `engines.llm` | string | `echo` | `echo`, `xai` | Sprachmodell (`echo` = offline, „You said: …“) | AI: **Language model** |
| `engines.tts` | string | `tone` | `tone`, `xai`, `elevenlabs` | Sprachausgabe (`tone` = offline, Summton) | AI: **Text-to-speech** |
| `mic.enabled` | bool | true | | Mikrofon an | Client Character: **Mic enabled** |
| `mic.mode` | string | `vad` | `vad`, `ptt` (Menü: „Voice activation“, „Push-to-talk“) | Sprachaktivierung oder Push-to-Talk | Client Character: **Mic mode** |
| `mic.device` | string | `""` | Gerätename aus der Liste der App; `""` = System-Standard | Eingabegerät; Menüeintrag „Standard (System-Mikrofon)“ = `""` | Client Character: **Mic device** |
| `mic.vad_threshold` | number | 0.01 | [0.001–0.5]; Plugin-Regler 0.001–0.2 | Pegel (RMS 0–1), ab dem ein Block als Sprache zählt | Client Character: **VAD threshold** |
| `mic.end_silence_ms` | int | 700 | [200–5000] | Stille, die eine Äußerung beendet | Client Character: **Silence timeout (ms)** |
| `mic.min_utterance_ms` | int | 300 | [100–5000], kleiner als max | kürzere Äußerungen werden verworfen | Client Character: **Min utterance (ms)** |
| `mic.max_utterance_ms` | int | 20000 | [1000–60000] | längere Äußerungen werden abgeschnitten | Client Character: **Max utterance (ms)** |
| `mic.echo_tail_s` | number | 0.4 | [0–3] | Mikrofon bleibt so lange nach dem Sprechende der Figur zu (Echo-Sperre) | Client Character: **Echo gate tail (s)** |
| `mic.gain` | number | 1.0 | [0.1–8] | Verstärkung vor VAD und Spracherkennung | Client Character: **Input gain** |
| `mic.ptt_interrupts` | bool | true | | Push-to-Talk drücken stoppt die laufende Antwort | Client Character: **Push-to-talk interrupts speech** |
| `mic.level_meter` | bool | true | | Pegelanzeige im Plugin | Client Character: **Show level meter** |
| `body.speech_volume` | number | 1.0 | [0–1] | Lautstärke der Kopf-Audioquelle | AI Character: **Speech volume** |
| `body.body_control` | bool | true | | aus = nur Sprache: Ausdrucks-, Morph-, Gesten-, Posen- und Trigger-Befehle werden ignoriert, die KI bekommt keine Körper-Tools; die manuellen Menüs funktionieren weiter | AI Character: **Body control** |
| `body.idle_motion` | bool | true | | Kopf-Leerlaufbewegung | AI Character: **Idle head motion** |
| `body.idle_intensity` | number | 0.5 | [0–1] | Stärke der Leerlaufbewegung | AI Character: **Idle intensity** |
| `body.breathing` | bool | true | | Atmung über Morph | AI Character: **Breathing** |
| `body.breaths_per_minute` | number | 14 | [4–40] | Atemfrequenz | AI Character: **Breaths per minute** |
| `body.breath_depth` | number | 0.35 | [0–1] | Atemtiefe | AI Character: **Breath depth** |
| `body.breath_morph` | string | `Breath1` | Morph-Name der Figur | Brust-Morph für die Atmung (kein Standard-Morph in VaM, TODO(verify)) | AI Character: **Breath morph** |
| `advanced.file_poll_interval_s` | number | 0.1 | [0.02–2] | wie oft das Plugin seinen Eingang prüft; Änderung startet die Verbindung neu | Erweitert: **File poll interval (s)** |
| `advanced.verbose_log` | bool | false | | Turn-Trace in Konsole und `Saves/PluginData/AIBody/logs/companion.log` (1 MB × 5, Keys geschwärzt), `[debug]`-Zeilen im VaM-Log, *Letzte Ereignisse* im Statusfeld; wirkt sofort | Erweitert: **Verbose log**; CLI `-v` |
| `ai.mode` | string | `qa` | `qa`, `auto`, `realtime`, `chain` | `qa` = Einfacher Q&A: STT → Grok → TTS, mit xAI-Key `xai` statt der Test-Engines, nur Sprache, keine Körper-Tools, kein proaktives Sprechen. `auto` = Realtime mit xAI-Key (außer bei `engines.tts` = `elevenlabs`), sonst Kette. `realtime` = Grok Voice Sprache-zu-Sprache, Kette als Fallback (auch wenn 12 s nach dem Sprechen keine Antwort kommt). `chain` = genau die Engines aus `engines` | AI Character: **AI mode**; Voice Mode: **Einfacher Q&A-Modus** (setzt `qa` und Body control aus), **Echtzeit (Realtime) verwenden** (an = `auto`, aus = `qa`) |
| `ai.persona` | string | „You are a friendly, curious character …“ | frei | System-Prompt (xAI: `instructions` der ersten Anfrage einer Unterhaltung; Realtime: Teil der Instructions) | nur Datei |
| `ai.language` | string | `auto` | `auto` oder Sprachcode (`de`, `en`, …) | Sprachhinweis für STT und TTS | nur Datei |
| `ai.fallback.stt` / `.llm` / `.tts` | string | `null` / `echo` / `tone` | Engines wie bei `engines` | läuft, wenn die gewählte Engine keinen Key hat oder eine Anfrage scheitert | nur Datei |
| `ai.realtime.url` | string | `wss://api.x.ai/v1/realtime` | | WebSocket-Adresse | nur Datei |
| `ai.realtime.model` | string | `grok-voice-latest` | | Sprachmodell (Query-Parameter `model`) | nur Datei |
| `ai.realtime.voice` | string | `eve` | `eve`, `ara`, `rex`, `sal`, `leo` oder eigene Voice-ID | Stimme in Realtime; Änderung verbindet neu | AI Character: **Voice** (setzt auch `ai.xai.voice`; eine eigene ID aus der Datei wird ins Menü übernommen) |
| `ai.realtime.sample_rate` | int | 24000 | 8000, 16000, 22050, 24000, 32000, 44100, 48000 | Abtastrate der Antwort (16-Bit-PCM, als WAV) | nur Datei |
| `ai.realtime.speed` | number | 1.0 | [0.7–1.5] | Sprechtempo | nur Datei |
| `ai.realtime.reasoning_effort` | string | `none` | `none`, `high` | `none` antwortet schneller; `high` = API-Standard | nur Datei |
| `ai.realtime.send_while_speaking` | bool | false | | Mikrofon streamt weiter, während die Figur spricht (Unterbrechen per Stimme); nur mit Kopfhörer | Client Character: **Voice barge-in (headphones)** |
| `ai.realtime.first_segment_s` | number | 1.2 | [0.3–5] | erstes Audiostück wird gespielt, sobald nach so viel Audio ein Satz endet | nur Datei |
| `ai.realtime.max_segment_s` | number | 6.0 | [1–20] | längere Stücke ohne Satzende werden an der leisesten Stelle geschnitten | nur Datei |
| `ai.realtime.connect_timeout_s` | number | 15 | [3–60] | Verbindungs-Timeout | nur Datei |
| `ai.proactive.enabled` | bool | true | | KI darf nach Stille von sich aus sprechen (Realtime oder `llm` = `xai`; pausiert in `qa`) | AI: **Proactive** |
| `ai.proactive.idle_seconds` | number | 90 | [15–3600]; Plugin-Regler 15–900 | Stille bis zum Anstoß; verdoppelt sich bei unbeantworteten Anstößen (bis 8×) | AI: **Proactive idle (s)** |
| `ai.proactive.prompt` | string | „The user has been quiet for a while. … answer with exactly [silent] …“ | frei | Hinweis bei jedem Anstoß; Antwort `[silent]` = nichts abspielen | nur Datei |
| `ai.xai.base_url` | string | `https://api.x.ai/v1` | | REST-Basis für STT, LLM, TTS | nur Datei |
| `ai.xai.key_file` | string | `""` | Pfad (absolut oder relativ zum Benutzerordner); kein Key | Datei mit dem xAI-Key; `XAI_API_KEY` gewinnt; ein eingefügter Key wird abgelehnt und nicht gespeichert | AI: **xAI key file** (leeres Feld überschreibt die Datei nicht) |
| `ai.xai.model` | string | `grok-4.7` | | Sprachmodell | nur Datei |
| `ai.xai.max_output_tokens` | int | 400 | [16–8000] | hält Antworten kurz | nur Datei |
| `ai.xai.stt_model` | string | `grok-voice-transcribe-2.0` | | Spracherkennungsmodell | nur Datei |
| `ai.xai.voice` | string | `eve` | wie `ai.realtime.voice` | TTS-Stimme | AI Character: **Voice** |
| `ai.xai.speed` | number | 1.0 | [0.7–1.5] | TTS-Tempo | nur Datei |
| `ai.xai.sample_rate` | int | 24000 | 8000, 16000, 22050, 24000, 44100, 48000 | TTS-Abtastrate (PCM, als WAV) | nur Datei |
| `ai.xai.timeout_s` | number | 60 | [5–600] | Anfrage-Timeout | nur Datei |
| `ai.elevenlabs.base_url` | string | `https://api.elevenlabs.io/v1` | | REST-Basis | nur Datei |
| `ai.elevenlabs.key_file` | string | `""` | wie `ai.xai.key_file` | Datei mit dem ElevenLabs-Key; `ELEVENLABS_API_KEY` gewinnt | AI: **ElevenLabs key file** |
| `ai.elevenlabs.voice_id` | string | `JBFqnCBsd6RMkjVDRZzb` | | Stimme | nur Datei |
| `ai.elevenlabs.model_id` | string | `eleven_multilingual_v2` | | TTS-Modell | nur Datei |
| `ai.elevenlabs.output_format` | string | `pcm_24000` | `pcm_16000`, `pcm_22050`, `pcm_24000`, `pcm_44100`, `pcm_48000` | Ausgabeformat (44,1/48 kHz brauchen einen ElevenLabs-Pro-Plan) | nur Datei |
| `ai.elevenlabs.timeout_s` | number | 60 | [5–600] | Anfrage-Timeout | nur Datei |

### 4.3 Nur im Plugin-Menü (nicht in config.json)

- Voice Mode: **Einfacher Q&A-Modus** (Knopf, setzt `ai.mode` = `qa` und Body control aus; Hilfetext darunter), **Echtzeit (Realtime) verwenden** (Schalter, nicht gespeichert, Ansicht von AI mode: an = `auto`, aus = `qa`; zeigt an bei `auto`/`realtime`), **API Reconnect** (App liest Keys neu und öffnet Realtime neu; Plugin startet die Verbindung neu), **Test-Ton über Companion**, **Test-Ton abspielen** (Ton aus dem Paket, ohne App), **Stop speaking**.
- AI: **Delay (s)** (0–5, Platzhalter ohne Funktion, nicht gespeichert); Key-Status je Anbieter (konfiguriert / fehlt / abgelehnt, mit Hinweis „nötig: API-Key von console.x.ai …“); Engine-Status (aktiver Modus, bereit / nicht konfiguriert, Fallback).
- AI Character: Modus-Hilfetext; **Pose** (Auswahl, nicht gespeichert; Liste = `gestures.json`-Einträge mit `kind` `pose` plus Dateien `.vap`/`.json` in `Custom/Atom/Person/Pose` und `Custom/Atom/Person/Pose/AIBody`, je Ordner oberste Ebene, max. 200, Präfix `Preset_` entfernt), **Pose anwenden**, **Posen neu laden**; **Ausdruck** (Auswahl) + **Ausdruck zeigen**, **Reset expression**; **Geste** (Auswahl) + **Geste abspielen**; **Reload Expressions**.
- Client Character: **Mikrofone neu laden** (Liste wird zusätzlich beim Öffnen des Menüs angefragt), Statuszeile „Mikrofone: N gefunden (…)“ bzw. roter Grund, Mikrofon-Status/Pegel, **Push-to-talk active** (nicht gespeichert; solange an, hört die App zu; nur im Mic mode Push-to-talk) mit Erklärtext.
- Config: **Reload Config JSON** und Ergebnis.
- Statusfeld links (immer sichtbar): Selbsttest, *Live* (Verbindung, Companion, Audio, „Letzte Runde“, „Latenz bis zum ersten Ton: X s (Ø Y s, n Runden)“ mit Aufschlüsselung), *Letzte Ereignisse* (bei Verbose log), Start-Protokoll.
- Aktionen für Trigger (Plugin-Storable): `Reconnect`, `Stop speaking`, `Reset expression`, `Reload config files` (Ausdrücke und Gesten neu laden), `Push-to-talk start`, `Push-to-talk stop`, `Push-to-talk toggle`, `Refresh mic devices`.

### 4.4 Begleit-App: Kommandozeile und --config-Datei

- `--vam-root <Pfad>` (Pflicht): VaM-Hauptordner.
- `--channel <name>`: Kanal; Standard `connection.channel` aus config.json; gewinnt über die Datei.
- `--config <datei>`: eigene JSON-Datei der App (Vorlage `companion/config.example.json`), Schlüssel: `vam_root`, `channel`, `poll_interval_s` (0.02, Takt der Hauptschleife), `sample_rate` (16000, Mikrofon), `frame_ms` (30, VAD-Blocklänge), `mic` (Startwerte wie `mic.*`), `keep_audio_files` (20, so viele WAVs bleiben liegen), `stt`/`llm`/`tts`. Kanal, Mikrofon, Engines, `ai` und `verbose_log` aus `config.json` überschreiben diese Datei.
- `--no-mic`: Mikrofon nie öffnen (nur Texteingabe).
- `--no-stdin`: keine Texteingabe aus der Konsole.
- `--list-devices`: Eingabegeräte ausgeben und beenden.
- `-v` / `--verbose`: DEBUG für alle Module, Turn-Trace immer an.

### 4.5 Umgebungsvariablen

- `XAI_API_KEY`: xAI-API-Key von console.x.ai (beginnt mit `xai-`); gewinnt über `ai.xai.key_file`. Ein Grok-Abo (SuperGrok / X Premium) bzw. grok.com-Token ist kein API-Key und wird abgelehnt. Ohne Key: Warnung beim Start, Test-Engines laufen.
- `ELEVENLABS_API_KEY`: ElevenLabs-Key; gewinnt über `ai.elevenlabs.key_file`.
- Key-Dateien werden alle 10 s neu gelesen; Umgebungsvariablen nur beim Start der App. Keys stehen nie in Szene, `config.json` oder Log.

### 4.6 expressions.json und gestures.json

- `expressions.json` (Pfad `connection.paths.expressions`): Objekt Name → {Morph-Anzeigename: Wert}. Ergänzt/überschreibt die eingebauten Presets `neutral`, `happy`, `smile`, `sad`, `angry`, `surprised`, `thinking` (Morph-Namen TODO(verify)). Einträge, die kein Objekt sind (z. B. `_comment`), werden übersprungen. Vorlage `examples/expressions.json`.
- `gestures.json` (Pfad `connection.paths.gestures`): Objekt Name → Definition mit `kind`:
  - `head`: `name` (`nod`, `shake`, `tilt`), optional `duration` (Standard 1.2 s), `amplitude` (1).
  - `pose`: `path` einer Pose-Datei (lädt über PosePresets, TODO(verify)); erscheint auch im Pose-Menü und im KI-Tool `pose`.
  - `timeline`: `storable` (Standard `VamTimeline.AtomPlugin`), `animation`.
  - `trigger`: `storable` und `action`, oder `param` + `value` (+ `value_type` `float`/`bool`/`string`/`chooser`).
  - Vorlage `examples/gestures.json`.

## 5. Hinweise für Nutzer (Hub)

- AIBody ist ein Plugin für Virt-A-Mate 1.22 mit einer separaten Python-Begleit-App. Es gibt einer Figur eine Stimme und Körpersteuerung durch eine KI.
- Das VaM-Plugin enthält keinen Netzwerkcode und braucht „Allow Plugins Network Access“ nicht; es tauscht nur lokale Dateien mit der Begleit-App aus.
- Die Begleit-App verbindet sich mit externen Diensten: xAI (api.x.ai) und optional ElevenLabs. Dabei werden Mikrofon-Aufnahmen bzw. getippter Text und die Antworten an diese Dienste übertragen. Es gelten deren Nutzungsbedingungen und Datenschutzbestimmungen.
- Nötig ist ein eigener, kostenpflichtiger API-Key von console.x.ai. Ein Grok-Abo (SuperGrok / X Premium) oder ein grok.com-Login funktioniert nicht. Die API-Kosten trägt der Nutzer.
- API-Keys liegen nur lokal (Umgebungsvariable oder Key-Datei) und werden nicht in Szene, `.var` oder `config.json` gespeichert und im Log geschwärzt.
- Ohne Key läuft nur ein Offline-Testbetrieb (Echo und Summton).
- KI-erzeugte Sprache und KI-gesteuertes Verhalten können falsch, unpassend oder unerwartet sein. Die KI ist kein Mensch und hat kein Bewusstsein.
- Experimentell: bisher nur gegen API-Stubs kompiliert und gegen nachgebaute Server getestet, noch nicht in VaM und nicht mit einem echten Key geprüft.
- Kein offizielles Produkt von und nicht verbunden mit xAI, ElevenLabs oder Meshed VR.

## License

[LGPL-2.1](LICENSE).
