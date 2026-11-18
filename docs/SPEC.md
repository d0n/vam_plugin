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
- Heartbeat beider Seiten; Timeout 6 s → Status „DISCONNECTED“, automatischer Neuaufbau; alte Befehle werden verworfen.
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
- Realtime optional (Schalter „Use realtime voice“ = `auto`): Grok Voice über `wss://api.x.ai/v1/realtime`, Kette als Fallback.
- `chain`: genau die unter Voice > AI Character gewählten Engines.
- Test-Engines `null` / `echo` / `tone` als Offline-Betrieb und Fallback ohne Key.
- Proaktives Sprechen nach einstellbarer Stille; die KI bekommt Uhrzeit und Zeit seit dem letzten Austausch mit.

## Mikrofon
- Aufnahme, Geräteliste, VAD und Echo-Sperre nur in der Begleit-App.
- Push-to-Talk wird im Plugin geschaltet und an die App gemeldet; Push-to-Talk unterbricht die laufende Antwort.
- Gerätemenü listet die Mikrofone der App (ein Eintrag je Gerät), Eintrag „System default microphone“, Knopf „Refresh microphones“, Statuszeile mit Geräteanzahl bzw. Fehlergrund; Wahl wird angewendet und gespeichert.
- „System default microphone“ steht immer im Menü, auch ohne Liste der App (Version 16). Menüeinträge = Gerätenamen ohne Zusätze.
- Ohne Liste der App sagt das Infofeld klar, warum (Version 20): rot „companion app not running. Start it: python -m aibody_companion --vam-root "<VaM>"“, wenn kein Heartbeat der App da ist; rot „link is off“, wenn *Active* aus ist; „no answer from the running companion app“ nur, wenn die App läuft. Das Menü wird beim Öffnen, bei „Refresh microphones“ und beim Aufbau des Tabs immer neu gesetzt (mindestens „System default microphone“). Läuft die App, aber keine Liste kam, fragt das Plugin alle 10 s erneut; die App schickt die Liste außerdem nach jedem `ready` des Plugins.
- Infofeld (Tab Client Character) zeigt: wie viele Mikrofone von der App empfangen wurden, Host-API, Uhrzeit von Anfrage und Antwort, die Einträge des Menüs, Auswahl, Windows-Standardgerät (Version 16).
- Test ohne VaM und App: `tools/mic_test.py` (Geräte roh, je Host-API, Liste wie die App sie schickt; optional in den Plugin-Eingang).

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
- Alle Erklär-, Hilfe-, Status- und Pfadtexte stehen in EINEM großen Infofeld links (immer sichtbar). Seit Version 16 nur die Infos des offenen Tabs: oben eine Zeile mit Version und Startergebnis (Fehler rot), dann „Info: <Tab>“. Voice: Hilfe, Key- und Engine-Status, Verbindung. AI Character: Posen, Hinweise, Körper-Status. Client Character: Push-to-Talk, Mikrofon. Config: config.json, Kanal, Selbsttest, Recent events (Verbose log), Startup log. Seit Version 17: Feld 1800 hoch (etwa so hoch wie der längste Tab rechts), links nur dieses Feld (keine Kopfzeile darüber oder darunter), Texte gekürzt, Modus und Engines nur einmal (Engine-Status), Hinweis auf Umgebungsvariablen nur, solange ein Key fehlt.
- Keine leeren Auswahllisten: ohne Posen entfallen Posen-Auswahl und „Apply pose“ (Version 16).
- Namen sind selbsterklärend: „AI Character“ und „Client Character“, nie nur „AI“ oder „Client“.
- Sprache der Plugin-Oberfläche und der Ausgaben der Begleit-App (Konsole, Log, `tools/mic_test.py`): Englisch nach internationalem Standard, verständlich unabhängig von der Systemsprache (Leon, 18.11.2026, Version 18). Übersetzt werden nur eigene Texte: Feldnamen, Beschriftungen, Überschriften, Info- und Statustexte und eigene feste Einträge (z. B. „System default microphone“). Inhalte, die Betriebssystem oder VaM in ihrer Sprache liefern (Mikrofon-Gerätenamen, Namen der Windows-Standardgeräte, Host-API-Namen, Fehlermeldungen des Systems), bleiben genau so, wie das System sie benennt. Gespeicherte Namen (JSONStorable, config.json-Schlüssel, Protokoll-Nachrichten) bleiben unverändert; Zuordnung alt → neu in `docs/TRANSLATION_V18.md`.
- Keine leeren Platzhalter-Felder. Ein Eingabefeld zeigt in VaM nur seinen Wert, deshalb steht darüber eine Beschriftung.
- „Posen“ statt „Post“: der frühere Tab „Post“ ist entfallen (die offene Frage „Post oder Port“ ist damit erledigt); Posen liegen im Tab AI Character.
- Tabs:
  - Voice:
    - Voice Mode: Simple Q&A mode, Active, Use realtime voice, API Reconnect, Test tone via companion, Play test tone, Stop speaking.
    - Voice > AI Character: AI mode, Voice, Speech-to-text, Language model, Text-to-speech, Proactive, Proactive idle.
  - AI Character: Poses (Auswahl, Apply pose, Reload poses; per Sprache über die KI oder hier); Expression and gesture (Auswahl, Show expression, Reset expression, Reload expressions, Play gesture); Body (this Person only) (Body control, Lautstärke, Idle, Atmung, Breath morph mit Beschriftung).
  - Client Character: microphone and push-to-talk (Mic enabled, Mic mode, Mic device, Refresh microphones, Push-to-talk active, Push-to-talk interrupts speech, Show level meter, Mikrofon-Regler), Voice barge-in (headphones).
  - Config (früher Config und Erweitert): Reload Config JSON, Companion inbox poll interval (s) (wie oft das Plugin den Eingang der Companion-App abfragt; gespeicherter Name „File poll interval (s)“), Verbose log.
- Nur in config.json bzw. Begleit-App (kein Menüfeld): Kanal (`connection.channel`, `--channel`), Key-Datei-Pfade. Entfernte Einträge und ihre ursprüngliche Absicht: `docs/BACKLOG.md`, „Entfernte Menüeinträge (Version 15)“.

## Protokollierung
- Verbose log (Tab Config / `advanced.verbose_log` / `-v`): pro Runde Trace mit Runden-Nummer und Zeit in Konsole und `<VaM>/Saves/PluginData/AIBody/logs/companion.log` (1 MB × 5); im Plugin `[debug]`-Zeilen und *Recent events*.

- Selbsttest im Statusfeld (seit Version 13): Person-Atom, Kopf-Audio, Morphs, Pose-Speicher (`PosePresets` mit `presetBrowsePath`), Anzahl Posen und Pose-Dateien, Atem-Morph gefunden, Ausdrucks-Morphs x von y (fehlende Namen), Timeline-Storable für `timeline`-Gesten, PluginData beschreibbar, Companion-Heartbeat.
- Die Körper-Prüfungen werden höchstens alle 5 s neu berechnet und als `selftest` in `ready`/`heartbeat` gesendet; die Begleit-App schreibt sie bei jeder Änderung einmal als „Plugin self-test: …“ in Konsole und `companion.log` (Warnung, wenn etwas fehlt). Keine neue Einstellung, keine neue VaM-Schnittstelle.

## Latenz
- Gemessen vom Ende der Nutzersprache (VAD-Ende, PTT loslassen, Enter; Realtime: speech_stopped) bis zum ersten Ton (speech_started des Plugins).
- Aufschlüsselung: STT, LLM first token, first sentence, TTS, file write, to plugin, plugin start (Realtime: server first audio, segment, to plugin, plugin start).
- Pro Runde eine Logzeile; letzter Wert und Mittel der letzten 10 im Statusfeld (*Live*, „Latency to first sound“).

## Änderungen
- 18.11.2026 (nach Version 20, noch nicht umgesetzt): Knopf „Simple Q&A mode“ heißt „Question and Answer“, zweizeilig mittig „Question“ / „& Answer“; Funktion unverändert (Leon).
- 18.11.2026 (nach Version 20, noch nicht umgesetzt): Feld „XAI API Token“ ist ein einfaches Freitextfeld ohne Formatprüfung, im Tab Voice, Abschnitt Voice Mode, bei API Reconnect; Hinweis „(beware: scenes save it)“ darunter; bisherige Ablehnung eingefügter Keys entfällt dafür (Leon).
- 18.11.2026 (nach Version 20, noch nicht umgesetzt): Die zwei Infotextfelder unten im Tab AI Character wandern ins große Infofeld links; rechts stehen nur Bedienelemente (Leon).
- 18.11.2026 (nach Version 19, noch nicht umgesetzt): xAI-API-Token wird ingame über ein Freitextfeld „XAI API Token“ gesetzt (Hauptweg); `setx XAI_API_KEY` nur optionale Alternative; kein Feld für ElevenLabs; kurzer englischer Hinweis in Klammern am Feld, dass der Token im Klartext in Szene/config.json gespeichert wird, z. B. „(beware: scenes save it)“ (Leon).
- 17.11.2026 (v0.7.4): Erste Fassung des Spec-Logs.
- 17.11.2026: README auf Deutsch (Zweck, Szene, zwei Figuren, vollständige Einstellungsreferenz, Hinweise für den Hub); bisheriger README-Inhalt nach `docs/TECHNIK.md`.
- 17.11.2026 (Version 12): Versionsschema Version = Paketnummer; Szene mit zwei Personen (AI Character weiblich mit AIBody, Client Character männlich mit Camera Background Color); Regler im Plugin decken die vollen config.json-Bereiche ab.
- 17.11.2026 (Version 13): Erweiterter Selbsttest (Pose-Speicher, Posen, Atem-Morph, Ausdrucks-Morphs, Timeline) im Statusfeld und als „Plugin self-test“ im Log der Begleit-App; Quellennennung im README (Abschnitt 6).
- 18.11.2026 (Version 20): Mikrofon-Menü: Leon sah ein leeres Menü und „no answer from the companion app“, obwohl die Begleit-App sehr wahrscheinlich nicht lief (die Meldung hing nur an der Dateiverbindung, nicht am Heartbeat der App). Jetzt: roter Hinweis mit Startbefehl, solange die App nicht läuft; „no answer“ nur bei laufender App; Menü wird beim Öffnen, bei „Refresh microphones“ und beim Tab-Aufbau immer mit einer neuen Liste gesetzt (mindestens „System default microphone“); erneute Anfrage alle 10 s, solange die App läuft und keine Liste kam; die App schickt die Liste auch nach jedem `ready` und schreibt die Rohzahlen (PortAudio-Geräte, mit Eingang, in der gelisteten Host-API) ins Log. Warum das Menü in VaM gar keinen Eintrag zeigte, ist nicht bewiesen (TODO(verify): Screenshot der Zeile „Mic device menu: N entries“).
- 18.11.2026 (Version 19): Regler im Tab Config in der Oberfläche umbenannt: „Companion inbox poll interval (s)“ statt „File poll interval (s)“, weil er die Abfrage des Eingangs der Companion-App (`Saves/PluginData/AIBody/<Kanal>/inbox/`: Sprache, Posen, Ausdrücke) steuert und nicht config.json (wird nie automatisch neu geladen). Nur die angezeigte Beschriftung ändert sich (`UIDynamicSlider.label` nach `CreateSlider`, Nachweis E26 in `docs/API_AUDIT.md`); gespeicherter Name „File poll interval (s)“, config.json-Schlüssel `advanced.file_poll_interval_s` und Abfrageverhalten unverändert. Kurzer Hinweis dazu im Infofeld des Tabs Config.
- 18.11.2026 (Version 18): Plugin-Oberfläche auf Englisch (Beschriftungen, Überschriften, Infofeld, Status- und Logzeilen, Selbsttest, eigener Menüeintrag „System default microphone“ statt „Standard (System-Mikrofon)“); Konsolen-, Log- und Statustexte der Begleit-App und Ausgabe von `tools/mic_test.py` ebenfalls Englisch; Bezeichner und Kommentare im Code Englisch. Vom System gelieferte Namen (Mikrofone, Host-APIs) bleiben unverändert. Gespeicherte Szenen bleiben gültig: Storable-Namen, config.json-Schlüssel und Protokoll unverändert, alter Mikrofon-Eintrag „Standard (System-Mikrofon)“ wird beim Laden als Systemstandard gelesen, rote Markierung erkennt auch die deutschen Texte älterer Begleit-Apps. Zuordnung alt → neu: `docs/TRANSLATION_V18.md`.
- 18.11.2026 (Version 17): Infofeld 1800 hoch, Kopfzeile links entfernt, Infotexte je Tab gekürzt (keine doppelte Engine-Zeile, kein Ordner im Tab Voice), Knopf „Reload expressions (expressions.json)“ im Abschnitt Expression and gesture statt „Reload Expressions“ unter Körper. Keine neuen Funktionen, keine gespeicherten Namen geändert.
- 18.11.2026 (Version 16): Mikrofon-Menü zeigt immer „Standard (System-Mikrofon)“ (seit Version 18 „System default microphone“) und die empfangenen Mikrofone (ohne getrennte Anzeigenamen); Infofeld mit Anzahl, Quelle, Uhrzeit und Menüeinträgen; `tools/mic_test.py`. Infofeld höher und nur mit den Infos des offenen Tabs (Selbsttest und Startup log im Tab Config). Keine leere Posen-Auswahl.
- 17.11.2026 (Version 15): Menü neu nach Leons Rückmeldung aus dem VaM-Test: Tabs Voice (Voice Mode, Voice > AI Character), AI Character (mit Posen), Client Character, Config (Config + Erweitert zusammengelegt). Ein großes Infofeld links für alle Hilfe- und Statustexte; keine Textfelder in den Tabs. Beschriftung „Posen“ statt „Post“ (Frage „Post oder Port“ erledigt, Tab Post entfällt). Entfernt: Tabs AI, Post, Erweitert, Feld Channel, Key-Datei-Felder, Platzhalter Delay, Titelzeile je Tab. Key-Datei-Pfade und Kanal nur noch in config.json; die Datei gewinnt bei den Key-Datei-Pfaden.
