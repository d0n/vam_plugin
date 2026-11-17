# AIBody – Spezifikation (Spec-Log)

Vereinbarter Stand, was gilt. Status (umgesetzt/offen): [`ANFORDERUNGEN.md`](ANFORDERUNGEN.md). Zurückgestellte Ideen: [`BACKLOG.md`](BACKLOG.md).

## Ziel
- Virt-A-Mate-Plugin (VaM 1.22), das einer KI einen Körper gibt: Sprechen mit Lippensync, Ausdrücke, Gesten, Posen; Zuhören über Mikrofon.
- Zwei Teile: Plugin `AIBody` (C#) auf der Person + Begleit-App `aibody_companion` (Python) neben VaM.

## Feste Rahmenbedingungen
- Sandbox: kein `UnityWebRequest`, kein `UnityEngine.Networking`, kein `WWW`, `System.IO`, `System.Net`, `Process`, keine Reflection, kein `DllImport`, kein Unity-`Microphone`. Build-Scan bricht ab (`tools/check_plugin.py`).
- Nur belegte VaM-APIs (Belege in `docs/API_AUDIT.md`); Unbelegtes wird markiert (`TODO(verify)`) oder weggelassen, nicht umgangen.
- Dateizugriff im Plugin nur über `FileManagerSecure`.
- Netzwerk nur in der Begleit-App; Plugin ohne Netzwerkcode; „Allow Plugins Network Access“ bleibt aus.
- C# 6.
- Ein Plugin, eine `.cslist` (`Custom/Scripts/d0n/AIBody/AIBody.cslist`), genau eine MVRScript-Klasse; Laden in einem Schritt im Plugins-Tab der Person.
- Eine `.var` (`d0n.AIBody.<N>.var`) nach `<VaM>/AddonPackages/`.
- Versionsschema ab Version 12: Version = Paketnummer `<N>` der `.var`; gleich in Plugin-Anzeige (`PluginVersion`), Begleit-App (`__version__`, pyproject), `packaging/AIBody.json` und Git-Tag/Release `v<N>`. Ältere Tags (bis v0.7.4 = Paket 11) bleiben.
- LICENSE und `licenseType` „FC“ in `meta.json` nicht anfassen; Lizenzfrage außen vor.
- Keine Secrets im Repo; API-Keys nie im Log (geschwärzt), nie in Szene oder config.json.
- Code auf Englisch; README auf Deutsch (Leon, 17.11.2026 22:11; technische Details englisch in `docs/TECHNIK.md`); Release-Notes auf Deutsch mit vollen Pfaden ab VaM-Hauptordner, Ladeort (Plugins-Tab der Person) und Bitte um Screenshot, rote `AIBody:`-Logzeilen und Konsolenausgabe der Begleit-App.
- Sinnvolle Commits direkt auf `main`, jeder Commit einzeln grün (Tests, ruff, Plugin-Check, Schema-Check).

## Verbindung
- Datei-Transport über `<VaM>/Saves/PluginData/AIBody/<Kanal>/` in beide Richtungen (Befehle rein, Events raus), Protokoll v3 (`protocol/PROTOCOL.md`, Schemas `protocol/schema/`).
- Heartbeat beider Seiten; Timeout 6 s → Status „GETRENNT“, automatischer Neuaufbau; alte Befehle werden verworfen.
- Plugin bleibt stabil ohne Begleit-App.

## Gemeinsame Konfiguration
- Eine globale Datei `<VaM>/Saves/PluginData/AIBody/config.json` (Kanal ist ein Wert darin), von Plugin und App gelesen; Schema `protocol/schema/config.schema.json`, Doku `docs/CONFIG.md`.
- Werte im Plugin-Menü (mit der Szene gespeichert) gewinnen und werden zurückgeschrieben; Szene ohne AIBody-Werte übernimmt die Datei einmal.
- Abschnitt `ai` gehört der Begleit-App; das Plugin setzt dort nur seine Menüwerte (Modus, Stimme, Proactive, Voice barge-in) und reicht die Key-Datei-Pfade aus der Datei durch (seit Version 15 kein Menüfeld; die Datei gewinnt bei jedem Start).

## API-Keys
- xAI braucht einen API-Key von console.x.ai; ein Grok-Abo / grok.com-Token funktioniert nicht. Statusanzeige und Hinweise sagen das.
- Key nur über Umgebungsvariable `XAI_API_KEY` / `ELEVENLABS_API_KEY` (gewinnt) oder den Pfad einer Key-Datei (`ai.xai.key_file` / `ai.elevenlabs.key_file` in config.json); ein dort eingetragener Key wird abgelehnt und nicht gespeichert.
- Key-Status je Anbieter: konfiguriert / fehlt / abgelehnt (mit Grund).

## KI-Modi
- Standard `qa` (Einfacher Q&A): Spracherkennung xAI → Grok → Stimme xAI, nur Sprache, keine Körpersteuerung durch die KI, kein proaktives Sprechen.
- Realtime optional (Schalter „Echtzeit (Realtime) verwenden“ = `auto`): Grok Voice über `wss://api.x.ai/v1/realtime`, Kette als Fallback.
- `chain`: genau die unter Voice > AI Character gewählten Engines.
- Test-Engines `null` / `echo` / `tone` als Offline-Betrieb und Fallback ohne Key.
- Proaktives Sprechen nach einstellbarer Stille; die KI bekommt Uhrzeit und Zeit seit dem letzten Austausch mit.

## Mikrofon
- Aufnahme, Geräteliste, VAD und Echo-Sperre nur in der Begleit-App.
- Push-to-Talk wird im Plugin geschaltet und an die App gemeldet; Push-to-Talk unterbricht die laufende Antwort.
- Gerätemenü listet die Mikrofone der App (ein Eintrag je Gerät), Eintrag „Standard (System-Mikrofon)“, Knopf „Mikrofone neu laden“, Statuszeile mit Geräteanzahl bzw. Fehlergrund; Wahl wird angewendet und gespeichert.

## Sprachausgabe
- Antwort als lokale WAV-Datei, abgespielt über VaMs Audio-Lader auf der Kopf-Audioquelle mit eingebautem Lippensync; kein Download per URL.
- Audio-Ordner `Custom/Sounds/AIBody/<Kanal>/`; bei „nicht ladbar“ einmal Wechsel nach `Saves/PluginData/AIBody/<Kanal>/audio/`.
- Sprache hängt nicht an Ausdrücken; Test-Ton direkt und über die Begleit-App.

## Körpersteuerung
- Ausdrücke über Morphs, Atmung, Kopf-Leerlauf; Gesten über Timeline-Aktionen; Posen über Pose-Presets.
- Die KI steuert den Körper per Tool-Aufruf (Realtime: function_call; Kette: `/v1/responses` mit tools): `express` (Ausdruck/Geste), `pose` (nur wenn Posen vorhanden). Jeder Tool-Aufruf bekommt ein Ergebnis.
- Keine Tools in `qa` und bei Body control aus.
- Posen: Steuerung per Sprache über die KI, zusätzlich manuelles Menü (Auswahl + anwenden) im Tab AI Character.

## Szene
- Mitgelieferte Szene `examples/scenes/AIBody_GreenScreen.json`: zwei Personen, die sich ansehen.
  - `AI Character`: weiblich (VaM-Standardfigur `Female 3`), AIBody im Plugins-Tab.
  - `Client Character`: männlich (`Male 1`), sichtbarer Körper des Nutzers, Sallys *Camera Background Color* (#00FF00, Skybox aus) direkt im Plugins-Tab dieser Person (Abhängigkeit `Sally.CameraBackgroundColor.7`).
  - Nur eingebaute Standard-Figuren, keine Fremd-Looks; kein Raum, kein Szenen-Plugin.
- AIBody kennt kein Client-Atom; Nutzereingabe über Begleit-App (Mikrofon, Push-to-Talk, Konsole) und Tab Client Character im AIBody-Plugin.

## Menü
- Das Menü zeigt nur, was sich einstellen lässt. In den Tabs stehen nur Bedienelemente (Knöpfe, Schalter, Regler, Auswahlen, beschriftete Eingabefelder), keine Text- oder Statusfelder (Leon, 17.11.2026, Version 15).
- Alle Erklär-, Hilfe-, Status- und Pfadtexte stehen in EINEM großen Infofeld links (immer sichtbar): oben „Info: <Tab>“ mit Hilfe und Status zum offenen Tab, darunter Selbsttest, Live-Status, Letzte Ereignisse (Verbose log), Start-Protokoll.
- Namen sind selbsterklärend: „AI Character“ und „Client Character“, nie nur „AI“ oder „Client“.
- Keine leeren Platzhalter-Felder. Ein Eingabefeld zeigt in VaM nur seinen Wert, deshalb steht darüber eine Beschriftung.
- „Posen“ statt „Post“: der frühere Tab „Post“ ist entfallen (die offene Frage „Post oder Port“ ist damit erledigt); Posen liegen im Tab AI Character.
- Tabs:
  - Voice:
    - Voice Mode: Einfacher Q&A-Modus, Active, Echtzeit (Realtime) verwenden, API Reconnect, Test-Ton über Companion, Test-Ton abspielen, Stop speaking.
    - Voice > AI Character: AI mode, Voice, Speech-to-text, Language model, Text-to-speech, Proactive, Proactive idle.
  - AI Character: Posen (Auswahl, Pose anwenden, Posen neu laden; per Sprache über die KI oder hier); Ausdruck und Geste (Auswahl, Ausdruck zeigen, Reset expression, Geste abspielen); Körper (Body control, Lautstärke, Idle, Atmung, Atem-Morph mit Beschriftung, Reload Expressions).
  - Client Character: Mikrofon und Push-to-Talk (Mic enabled, Mic mode, Mic device, Mikrofone neu laden, Push-to-talk active, Push-to-talk interrupts speech, Show level meter, Mikrofon-Regler), Voice barge-in (headphones).
  - Config (früher Config und Erweitert): Reload Config JSON, File poll interval, Verbose log.
- Nur in config.json bzw. Begleit-App (kein Menüfeld): Kanal (`connection.channel`, `--channel`), Key-Datei-Pfade. Entfernte Einträge und ihre ursprüngliche Absicht: `docs/BACKLOG.md`, „Entfernte Menüeinträge (Version 15)“.

## Protokollierung
- Verbose log (Tab Config / `advanced.verbose_log` / `-v`): pro Runde Trace mit Runden-Nummer und Zeit in Konsole und `<VaM>/Saves/PluginData/AIBody/logs/companion.log` (1 MB × 5); im Plugin `[debug]`-Zeilen und *Letzte Ereignisse*.

- Selbsttest im Statusfeld (seit Version 13): Person-Atom, Kopf-Audio, Morphs, Pose-Speicher (`PosePresets` mit `presetBrowsePath`), Anzahl Posen und Pose-Dateien, Atem-Morph gefunden, Ausdrucks-Morphs x von y (fehlende Namen), Timeline-Storable für `timeline`-Gesten, PluginData beschreibbar, Companion-Heartbeat.
- Die Körper-Prüfungen werden höchstens alle 5 s neu berechnet und als `selftest` in `ready`/`heartbeat` gesendet; die Begleit-App schreibt sie bei jeder Änderung einmal als „Plugin-Selbsttest: …“ in Konsole und `companion.log` (Warnung, wenn etwas fehlt). Keine neue Einstellung, keine neue VaM-Schnittstelle.

## Latenz
- Gemessen vom Ende der Nutzersprache (VAD-Ende, PTT loslassen, Enter; Realtime: speech_stopped) bis zum ersten Ton (speech_started des Plugins).
- Aufschlüsselung: STT, LLM erstes Token, erster Satz, TTS, Datei, an Plugin, Plugin-Start (Realtime: Server erstes Audio, Segment, an Plugin, Plugin-Start).
- Pro Runde eine Logzeile; letzter Wert und Mittel der letzten 10 im Statusfeld (*Live*, „Latenz bis zum ersten Ton“).

## Änderungen
- 17.11.2026 (v0.7.4): Erste Fassung des Spec-Logs.
- 17.11.2026: README auf Deutsch (Zweck, Szene, zwei Figuren, vollständige Einstellungsreferenz, Hinweise für den Hub); bisheriger README-Inhalt nach `docs/TECHNIK.md`.
- 17.11.2026 (Version 12): Versionsschema Version = Paketnummer; Szene mit zwei Personen (AI Character weiblich mit AIBody, Client Character männlich mit Camera Background Color); Regler im Plugin decken die vollen config.json-Bereiche ab.
- 17.11.2026 (Version 13): Erweiterter Selbsttest (Pose-Speicher, Posen, Atem-Morph, Ausdrucks-Morphs, Timeline) im Statusfeld und als „Plugin-Selbsttest“ im Log der Begleit-App; Quellennennung im README (Abschnitt 6).
- 17.11.2026 (Version 15): Menü neu nach Leons Rückmeldung aus dem VaM-Test: Tabs Voice (Voice Mode, Voice > AI Character), AI Character (mit Posen), Client Character, Config (Config + Erweitert zusammengelegt). Ein großes Infofeld links für alle Hilfe- und Statustexte; keine Textfelder in den Tabs. Beschriftung „Posen“ statt „Post“ (Frage „Post oder Port“ erledigt, Tab Post entfällt). Entfernt: Tabs AI, Post, Erweitert, Feld Channel, Key-Datei-Felder, Platzhalter Delay, Titelzeile je Tab. Key-Datei-Pfade und Kanal nur noch in config.json; die Datei gewinnt bei den Key-Datei-Pfaden.
