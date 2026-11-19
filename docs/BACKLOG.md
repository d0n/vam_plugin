# AIBody – Backlog

Zurückgestellte Ideen und Wünsche. Keine Priorität, keine zeitliche Reihenfolge. Was als „cool“ / „nice to have“ genannt wird, aber nicht dran ist, kommt hierher statt in den Code.
Vereinbarter Umfang: [`SPEC.md`](SPEC.md) · Stand umgesetzt/offen: [`ANFORDERUNGEN.md`](ANFORDERUNGEN.md).
Format: **Idee** – Herkunft, Datum – Notiz / warum zurückgestellt.
Grundregel seit v0.6.0: erst Lauffähigkeit (eine `.cslist`, ein MVRScript, ein Ladeschritt + Begleit-App); alles mit zweitem Ladeschritt, zweitem Plugin oder Plugin-zu-Plugin-Brücke wartet, bis das eine Plugin in VaM 1.22 geprüft ist.

## Machbarkeit (19.11.2026)

Bewertung aller Einträge dieser Datei und der Nice-to-haves des Katalogs vom 13.11.2026 (im Chat geschrieben, nie eingecheckt; „Katalog 1–8“ unten sind ihre Nummern: 1 Lebendigkeit wie Life, 2 Trigger-UI/LogicBricks/Timeline, 3 HTTP-Transport, 4 Emotionen/Gestik, 5 Komfort-UI wie MacGruber Utils, 6 VR, mehrere Figuren, Persönlichkeit und Gedächtnis, 7 Demo-Szene/Doku/Hub, 8 VaM2). Nur Bewertung, bis ein Eintrag unter „Umgesetzt“ steht. Maßstab: nur Sandbox-Regeln wie in `API_AUDIT.md` (belegte APIs, `FileManagerSecure`, ein Plugin / eine `.cslist`, kein Netzwerk im Plugin, keine Geheimnisse im Repository). Urteile: **machbar** (Ansatz, Aufwand S/M/L, Risiko, was ein VaM-Test klären muss), **teilweise machbar**, **geht nicht** (Grund). Die Reihenfolge am Ende ist ein Vorschlag aus der Analyse; die Grundregel „keine Priorität“ dieser Datei bleibt, Leon entscheidet.

Die drei Listen sind getrennt: **Umgesetzt** (steht im Code, mit Version), **Won't work** (Grund, wann neu bewerten) und **Backlog** (machbar, noch nicht gebaut). Aufwand: S = Stunden, M = ein bis zwei Tage, L = mehrere Tage.

### Umgesetzt

*(noch nichts aus dieser Bewertung; wird bei jedem Release ergänzt)*

### Won't work (zum späteren Neubewerten)

| Eintrag | Grund | Neu bewerten, wenn … |
|---|---|---|
| **HTTP / Netzwerk im Plugin** (Katalog 3) | Feste Regel (kein `UnityWebRequest`, kein `UnityEngine.Networking`). Zusätzlich hängt es in VaM an der Einstellung „Allow Plugins Network Access“ (standardmäßig aus, laut MeshedVR die riskanteste Einstellung). Ersatz siehe unten bei „Transport“. | die Regel von Leon geändert wird |
| **Client-Logik auf eigenem Atom** (Mikrofon, Engines, Status auf der Figur des Nutzers) | Braucht ein zweites Plugin und eine Plugin-zu-Plugin-Brücke (verstößt gegen „ein Plugin / eine `.cslist`“). Nutzen gering: Mikrofon und Engines laufen ohnehin in der Begleit-App. | ein zweites Plugin erlaubt ist |
| **Session-/Person-Plugins trennen**, **Session-Bootstrap** per `CreatePlugin()`, **Sub-Plugins / Verschachtelung** | Alle drei brauchen ein weiteres Plugin oder einen API-Aufruf ohne Beleg (`MVRPluginManager.CreatePlugin`, `pluginURLJSON`). Gegen die Ein-Plugin-Regel und gegen „nur belegte APIs“. | ein belegter Aufruf und die Erlaubnis für ein zweites Plugin vorliegen |
| **Viseme-Lippensync aus TTS-Zeitdaten** | VaM macht den Lippensync selbst aus dem Audio der `HeadAudioSource`, über die AIBody ohnehin abspielt (E1). Eigene Visem-Morphs würden gegen VaMs Lippensync arbeiten oder von ihm überschrieben; Zeitdaten der TTS-Engines sind dafür nicht nötig und bei xAI TTS nicht belegt (TODO(verify)). Kein Gewinn. | VaM den Lippensync abschaltbar macht (belegt) und eine Engine Visem-Zeiten liefert |
| **Herzschlag, Atemgeräusche** aus Life nachbauen | Die Aufnahmen von Life sind lizenziert und liegen als AssetBundle vor (nicht in unserem Paket nutzbar); eigene Geräusche würden sich die `HeadAudioSource` mit der Sprache teilen und sie unterbrechen. Atmung als Brust-Morph gibt es schon (E4). Wer Life-Atemgeräusche will, nutzt Life neben AIBody (siehe „Lebendigkeit“). | eine eigene, lizenzfreie Atemgeräusch-Sammlung und eine zweite `AudioSource` belegt sind |
| **Push-to-Talk-Erklärung als Tooltip/Mouseover** | Kein belegter Sandbox-Weg für einen VaM-Schalter (einzige Fundstelle: via5/VUI mit eigenem UI-System). Der Erklärtext im Infofeld bleibt. | ein belegtes Muster auftaucht |
| **Echte Echo-Unterdrückung (AEC), z. B. WebRTC** | Das Referenzsignal (was die Figur gerade abspielt) liegt in VaM, nicht in der Begleit-App; die Latenz zwischen WAV-Datei und Lautsprecher ist unbekannt und schwankt. Eine AEC ohne genaues Referenzsignal löscht schlecht. Ersatz im Backlog: Unterbrechen per Stimme mit Pegel-/Längenregel. | VaM den Abspielzeitpunkt melden kann oder die Begleit-App selbst abspielt |
| **Blick auf Spiegel** | Kein belegter Zugriff auf Spiegelbilder; kaum Nutzen. | – |
| **VaM2-Kompatibilität** | VaM2 hat laut MeshedVR (Entwicklungsbericht Oktober 2026) noch keine Plugins; sie sind das Hauptziel von Beta 1.3 ohne Termin, die Sicherheitsarbeit (eingeschränktes Dateisystem, Ersatz für Systemklassen) läuft noch. Es gibt keine API, gegen die man prüfen kann. Vorbereitung ist schon da: Protokoll v3 und Begleit-App kennen VaM nicht, nur den Dateikanal. | Beta 1.3 mit Plugin-Kit und Dokumentation erschienen ist |

### Backlog: machbar, noch offen

**Transport (Katalog 3, Ersatz für HTTP):** *teilweise machbar, ohne Plugin-Netzwerk.* Der Dateikanal bleibt der einzige Weg zwischen Plugin und App und reicht (Abfrage alle 0,1 s). Was sich im Prinzip anders lösen lässt, liegt alles in der Begleit-App: (a) **Fernsteuerung/Web-Oberfläche in der App** (lokaler HTTP- oder WebSocket-Server, nur 127.0.0.1, Token): Handy-Bedienfeld, Szenenskripte, OSC/MIDI, Streaming-Overlays; sie schreiben dieselben Befehle in den Dateikanal. Aufwand M, kein VaM-Test nötig. (b) **VaM und App auf zwei Rechnern** über einen geteilten Ordner (SMB, Syncthing) mit `--vam-root` auf den Freigabepfad: geht schon heute, nur zu dokumentieren und zu testen (S; Risiko Latenz und Sperrung beim Schreiben). (c) VaMs eigenes Laden von Audio per `http://`-URL (so macht es das Voxta-Plugin) wäre nur ein Audiokanal, braucht die Nutzereinstellungen „Enable Web Images and Audio“ und `whitelist_domains.json` und bringt für Befehle nichts: nicht empfohlen. Nebenbei: Voxta (AcidBubbles) nutzt SignalR mit „Allow Plugins Network Access“; AIBody braucht diese Einstellung nicht, das ist ein Vorteil.

**Lebendigkeit wie Life (Katalog 1):** *teilweise umgesetzt, Rest machbar.* Stand: Atmung (Brust-Morph mit Sinus, E4), Leerlauf-Kopfbewegung (E6), Blicksteuerung (Version 25). Fehlt: (a) **Blinzeln**: VaM hat ein eigenes Auto-Blinzeln (`EyelidControl`, Param `blinkEnabled`, Beleg E29: MacGruber Eyes 0.1.0 L40-41 schaltet es aus und treibt den Morph „Eyes Closed“ selbst); eigener Blink-Regler mit Intervall, Lidschlag am Blickwechsel und beim Sprechbeginn: S–M, VaM-Test (Morphname, Kollision mit VaMs Auto-Blinzeln). (b) **Blickverhalten** (Mikrosprünge, Wegschauen beim Nachdenken, Blick wandert): als Standardblick „Natural“ in `GazeController`, M, VaM-Test. (c) **Zusammenspiel statt Nachbau:** Life (Gaze, Eyes, Breathing) läuft als eigenes Plugin; AIBody erkennt es an der Storable-ID (Muster E8/E28, `EndsWith`, Namensräume `MacGruber.Gaze` / `MacGruber.Eyes` aus den Quellen E29) und hält sich aus Augen und Blinzeln heraus; die Kopf-Leerlaufbewegung zieht ihren eigenen Versatz wieder ab und verträgt sich mit Life (TODO(verify)). Geht nicht: Herzschlag und Atemgeräusche (siehe Won't work).

**Eigene Aktionen im Trigger-UI, LogicBricks-Stil, Timeline (Katalog 2) und „Zustände als Trigger“, „LogicBricks-artige Reaktionen“, „Story-Szenen“:** *machbar, zwei Stufen.* Stufe 1 (S–M, nur belegte APIs, ohne Trigger-Klasse): **Eingänge** als `JSONStorableAction` (E9, E12), die VaMs Trigger-UI, Timeline und LogicBricks als Ziel anbieten (Blick, Blinzeln, Ausdrücke, Gesten), eine Zeichenketten-Eigenschaft „Scene event“, die Szenen per Trigger setzen und die als Ereignis `scene_event` an die App geht (die KI darf darauf reagieren oder schweigen), und **Zustandswerte** (`AI speaking`, `User speaking` als Bool-Storables), die andere Plugins lesen können (E13). Stufe 2 (L): **echte ausgehende Trigger** („Beim Sprechbeginn“, „Beim Sprechende“, „Bei Hören“) mit VaMs eigenem Trigger-UI. Beleg: Timeline `CustomTrigger : Trigger` (L9, `InitTriggerUI`, `OpenTriggerActionsPanel`) und MacGruber_Utils `EventTrigger` (Hub-Plugin VamMoan, enthält eine Kopie: `new EventTrigger(this, name)`, `SimpleTriggerHandler.LoadAssets()` lädt die Panels aus VaMs AssetBundle `z_ui2`, `OpenPanelActionStart()`, `Trigger()`, Speichern über `GetJSON`/`LateRestoreFromJSON`). `MacGruber_Utils.cs` steht unter CC BY (Namensnennung nötig, Datei dürfte als eine zusätzliche Quelldatei in dieselbe `.cslist`); der Weg nutzt AssetBundle-Laden und Coroutinen, die bisher nicht im Audit stehen (nachtragen als E30). Risiko: hoch (Trigger-Panel in VaM-Version abhängig), VaM-Test zwingend. Timeline-Anbindung beider Richtungen läuft über diese Aktionen und Trigger; AIBody startet Timeline-Animationen schon heute (E8, E9). Eine eigene Story-Engine (VAMStory) ist **geht nicht** (nicht AIBodys Aufgabe); die KI als Regisseur über Szenen-Ereignisse dagegen ja.

**Emotionen auf Morphs, Gestik passend zum Gesagten (Katalog 4):** *teilweise umgesetzt, Rest machbar.* Stand: Tool `express` und `pose`, voreinstellbare Ausdrücke aus `expressions.json`, Blenden, Halten. Offen: (a) **Emotions-Rückfall**: kommt in einer Antwort kein Tool-Aufruf, wird der Ausdruck aus der Antwort abgeleitet (Schlagwort-Regeln oder ein Emotions-Tag der KI), in der Begleit-App, S–M; (b) **Abklingen** auf Neutral nach dem Sprechen (Leerlauf-Ausdruck), S; (c) **Mikro-Ausdrücke** beim Zuhören (Brauen), M. Kein neuer VaM-Aufruf, VaM-Test nur für Stärke und Morphnamen.

**Komfortable UI à la MacGruber Utils, Bedienung in VR (Katalog 5, 6):** *teilweise machbar.* Wir nutzen VaMs eigene `UIDynamic`-Bausteine (E16–E18, E24–E27); `MacGruber_Utils.cs` bietet darüber hinaus vor allem `EventTrigger` (siehe oben), Slider/Button-Helfer sind schon gleichwertig vorhanden. Komfort lässt sich ohne die Bibliothek heben (S): Abschnittsüberschriften, kurze Hilfe im Infofeld, „Gaze now“-Zeilen, Voreinstellungsgruppen. In VR funktionieren die Plugin-Menüs wie jede VaM-Oberfläche; die Menügröße ist begrenzt. **Push-to-Talk** gibt es schon als Aktionen (`Push-to-talk start/stop/toggle`), die jeder VR-Controller-Trigger, Keybindings oder Logic-Brick auslösen kann (TODO(verify) in VR). Mikrofon: immer das Systemstandard-Eingabegerät, in VR also das Headset-Mikrofon als Windows-Standard setzen. Blick auf „Camera / player“ nutzt `centerCameraTarget` und damit die VR-Kopfposition (E12). Offen: Texteingabe in VR (die Eingabefelder brauchen die VaM-Tastatur, TODO(verify)). VaM-Test in VR nötig.

**Mehrere Figuren, Kanal im Menü, Session-/Person-Config (Katalog 6):** *machbar, M–L.* Ansatz A (läuft heute schon, nur dokumentieren, S): je Figur ein Plugin mit eigenem Kanal (`Channel`), je Kanal eine Begleit-App (`--channel`); Nachteil: gleiche Mikrofone in jeder App, gemeinsame `config.json`. Ansatz B (besser, L): **eine App, mehrere Figuren**: je Kanal ein Gespräch mit eigener Persona, ein Mikrofon, Wer-antwortet-Regel (Anrede mit dem Namen der Figur, sonst die zuletzt angesprochene) und optional ein „Regie“-Tool, mit dem eine Figur die andere anspricht. Braucht Personas (siehe unten) und ein Kanalfeld im Menü, danach auch die Aufteilung Session-/Person-Config (Einstellungen je Persona). Risiko: Mikrofon-Zuordnung, Echo zwischen Figuren, doppelte Audiodateien. VaM-Test mit zwei Personen nötig.

**Personas als Datenordner, Persönlichkeitsprofile und Gedächtnis (Katalog 6):** *machbar, M, nur in der Begleit-App.* Ordner `Saves/PluginData/AIBody/personas/<name>/` mit `persona.json` (Prompt, Sprache, Stimme, Ausdrücke, Tool-Freigaben) und `memory.json`. Gedächtnis ohne neue APIs: nach jeder Sitzung fasst die KI die wichtigsten Fakten über den Nutzer zusammen (Zusammenfassung statt Rohtext), sie werden beim Start in die Anweisungen gelegt; Obergrenze für Größe und Kosten; Löschen/Anzeigen per `config.json` und Menüschalter „Memory“. Menü: Auswahl der Persona kommt als Liste aus dem Heartbeat, nicht aus dem Plugin (S). Risiken: Datenschutz (alles bleibt lokal in `Saves/PluginData`, nicht im Repository), Kosten pro Gespräch, Halluzinationen im Gedächtnis (Hinweis „nur Fakten, die der Nutzer sagte“).

**Lokale Engines (Begleit-App):** *machbar, je Engine M, keine Sandbox-Frage.* Reihenfolge nach Nutzen: LLM über Ollama (lokale HTTP-Schnittstelle, ähnlich `pipeline/http.py`; Tool-Aufrufe je nach Modell), STT mit faster-whisper, TTS mit Piper. Optionale Abhängigkeiten wie bei `webrtcvad`; Tests mit Fakes. Risiko: Modellgröße, Latenz, GPU; keine VaM-Tests.

**Silero-VAD:** *teilweise machbar (neu bewertet).* Silero läuft auch ohne `torch` mit `onnxruntime` und dem kleinen ONNX-Modell (MIT-Lizenz), als optionale Engine hinter `make_vad` (wie WebRTC). Aufwand S–M, Risiko: Abhängigkeit (`onnxruntime`), Modelldatei muss mitgeliefert oder geladen werden; Test mit echtem Mikrofon nötig. Bisherige Aussage „würde torch erzwingen“ ist damit überholt.

**Unterbrechen per Stimme ohne Kopfhörer:** *teilweise machbar (ohne echte AEC).* Regel statt Echo-Löschung: Während die Figur spricht, zählt Sprache nur, wenn sie deutlich lauter als der gemessene Echopegel ist (gelernt aus dem eigenen Sprechen) und länger als etwa 0,6 s dauert. S–M, Risiko: Fehlauslösung; Test mit Lautsprechern nötig.

**Mitgelieferte Plugin-Presets:** *machbar, S.* Ein Plugin-Preset (`.vap`) für Personen im Paket unter `Custom/Atom/Person/Plugins/`, das die `.cslist` einträgt. Risiko: Format von VaM (VaM-Test: Preset laden, Plugin erscheint), `licenseType` bleibt unberührt.

**Demo-Szene, Doku, Hub-Veröffentlichung (Katalog 7):** *teilweise machbar.* Demo-Szene gibt es als JSON (`examples/scenes/AIBody_GreenScreen.json`); fehlt: eine Szene **im Paket** (Szenen-`.var` mit Abhängigkeit auf `d0n.AIBody`, ohne Token), Vorschaubild, Hub-Beschreibung (Deutsch/Englisch). Hub: Voxta zeigt, dass ein Plugin mit externer Begleit-Software auf dem Hub geht (Plugin als Hub-Referenz, nicht kopieren; Kategorie, Tag, Anleitung, Credits). Offen und nur von Leon zu entscheiden: Konto, Lizenz (`FC`, unverändert), Preis, ob die App im Repository oder separat verteilt wird, Altersfreigabe/Inhaltsregeln des Hubs. Vor einer Veröffentlichung: Token-Scan der Szene, Abschnitt über das Netzwerkverhalten der App (die App nutzt xAI/ElevenLabs im Internet, das Plugin nicht).

**Kleine Menü-Punkte:** *machbar, S, warten auf Entscheidung von Leon:* „Key-Datei-Pfad im Menü, beschriftet“ (mit `UiPage.TextInput` und Beschriftung), „Delay-Einstellung“ (Spezifikation fehlt), „Info-/Pfadanzeige“ (steht im Infofeld Tab Config seit Version 15), „In-Game-Testplugin“ (teilweise: der Selbsttest im Infofeld deckt es ab; ein eigenes Plugin ginge nur als weiterer Tab, S, nicht als zweites Plugin).

### Empfohlene Reihenfolge (Vorschlag, keine Priorität)

1. **Szenen-Anbindung Stufe 1** (Aktionen, „Scene event“, Zustandswerte) – klein, belegt, öffnet Timeline und LogicBricks und die Story-Szenen.
2. **Natürlicher Blick und Blinzeln** samt Life-Erkennung – baut auf der Blicksteuerung auf, kleines Risiko.
3. **Emotions-Rückfall und Abklingen** – Begleit-App, kein VaM-Risiko.
4. **Personas und Gedächtnis** – Begleit-App, Voraussetzung für mehrere Figuren.
5. **Mehrere Figuren** (eine App, mehrere Kanäle) und Kanal im Menü.
6. **Demo-Szene im Paket und Hub-Beschreibung** (Entscheidung von Leon nötig).
7. **Lokale Engines** (Ollama zuerst), **Silero per ONNX**, **Stimm-Unterbrechung per Regel**.
8. **Trigger-UI Stufe 2** (echte ausgehende Trigger) – größtes Risiko, erst nach VaM-Tests der Stufe 1.
9. **Fernsteuerung/Web-Oberfläche in der App**, **Mitgelieferte Plugin-Presets**.


## Menü und Bedienung
- **Info-/Pfadanzeige im Menü** (Kanal-, Audio-, config.json-Ordner) – Leon, 17.11.2026 – In v0.7.4 aus den Tabs entfernt (Menü zeigt nur Einstellbares). Seit Version 15 stehen config.json-Pfad und Kanal mit Ordner im Infofeld links (Tab Config); weitere Pfade einmal im VaM-Log.
- **In-Game-Testplugin à la Timeline** – Leon, 17.11.2026 – Noch keine Spezifikation. Teilweise abgedeckt: erweiterter Selbsttest im Statusfeld mit Ausgabe im Log der Begleit-App (Version 13); ein eigenes Testplugin bleibt ohne Spezifikation.
- **Key-Datei-Pfad im Menü, beschriftet** – Version 15 – Die Felder „xAI key file“ / „ElevenLabs key file“ erschienen in VaM als leere, unbeschriftete Kästen und wurden entfernt; der Pfad steht nur noch in config.json (`ai.xai.key_file`, `ai.elevenlabs.key_file`) bzw. als Umgebungsvariable. Rückkehr als beschriftetes Feld möglich, wenn Leon es will.
- **Kanal im Menü** – Version 15 – später überdenken. Feld „Channel“ (zeigte nur `default`) entfernt; Kanal in config.json `connection.channel` oder `--channel`. Sinnvoll erst mit mehreren Figuren (siehe „Zweite Figur“), dann mit Beschriftung.
- ~~**Direktes API-Key-Textfeld im Plugin**~~ – Leon, 17.11.2026 – entschieden am 18.11.2026 und in Version 21 gebaut: Feld „XAI API Token“ im Tab Voice (Klartext in der Szene; seit der nächsten Version 24 im Klartext in config.json `ai.xai.api_key` und in der Szene nur maskiert). Offen bleibt nur ein ElevenLabs-Feld (von Leon ausdrücklich nicht gewünscht).
- **Delay-Einstellung** – Leon, 17.11.2026 – Platzhalter „Delay (s)“ im Tab AI ohne Funktion, seit Version 15 aus dem Menü entfernt; keine Spezifikation, was verzögert werden soll (Kandidaten: Pause vor der Antwort, Wartezeit bis Sprechende-Erkennung – beides von Leon zu entscheiden).
- **Menüs, die nur „default“ zeigen** – Leon, 18.11.2026 – später überdenken. Geprüft in Version 16: keins mehr vorhanden (Feld Channel und Tab Post schon in Version 15 entfernt). Die Engine-Auswahlen (Speech-to-text, Language model, Text-to-speech) zeigen vor der ersten Verbindung zur App nur den eingestellten Wert (`null` / `echo` / `tone`), danach die Liste der App; sie bleiben, weil einstellbar. Ohne Posen entfällt die Posen-Auswahl.
- **Aufteilung Session-Config vs. Person-Config** – Leon, 17.11.2026 – Welche Einstellung gilt pro Sitzung, welche pro Person; zurückgestellt bis nach den Tests in VaM.
- **Push-to-Talk-Erklärung als Mouseover/Tooltip** – Leon, 17.11.2026 – Kein belegter Sandbox-Weg für einen VaM-Schalter (einziges Beispiel via5/VUI baut ein eigenes UI-System), siehe `API_AUDIT.md`; bis dahin Erklärtext, seit Version 15 im Infofeld links (Tab Client Character).
- **Komfortable UI à la MacGruber Utils**, **Bedienung in VR** – Anforderungskatalog – Nicht begonnen.

## Laden und Aufbau
- **Client-Logik auf eigenem Atom** (Mikrofon, Engines, Status auf der Figur des Nutzers oder einem Empty) – v0.5.0 (`legacy/v0.5`) – Seit Version 12 hat die Szene eine männliche Client-Person, aber nur als sichtbaren Körper mit Hintergrund-Plugin; AIBody liegt nicht darauf. Braucht Plugin-zu-Plugin-Brücke (`GetStorableIDs`, `plugin#`-IDs, String-Param-Callbacks), unbelegt.
- **Zweite Figur bzw. mehrere Figuren** (eigene Instanz, Ziel pro Befehl, Persona pro Figur) – v0.4 `AIBodyPerson2` / v0.5 Atom-Routing – Zurückgestellt.
- **Session/Person-Plugins trennen**, Session-Anbindung über „Set Current As User Defaults“ – v0.3/v0.4 (Code unter `legacy/`) – Zugunsten des Ladens in einem Schritt zurückgestellt.
- **Session-Bootstrap**: Plugin setzt AIBody per `MVRPluginManager.CreatePlugin()` + `pluginURLJSON` auf die richtige Figur (Keybindings-Muster) – Anforderungskatalog – API unbelegt, zusätzliches Plugin.
- **Mitgelieferte Plugin-Presets** (`Custom/Atom/Person/Plugins/...`) – Backlog v0.6.0 – Nicht begonnen.
- **Sub-Plugins / Verschachtelung** (ein Einstiegs-Plugin lädt weitere `.cslist`) – Anforderungskatalog – Kein belegter Weg außer Bootstrap.
- **Interaktive Story-Szenen à la VAMStory** (Steuerung auf eigenem Atom) – Anforderungskatalog – Nicht begonnen.
- **VaM2-Kompatibilität** – Anforderungskatalog – Später.

## Figur
- **Blicksteuerung, Rest:** Grundfunktion (Tool `look_at`, Menü „Gaze“) ist seit Version 25 umgesetzt (siehe SPEC). Offen: Mikro-Sakkaden und Zufallsblicke wie in Glance, Blinzeln, Blick auf Spiegel, automatisches Wegschauen beim Nachdenken ohne Tool-Aufruf, Erkennung von Life per Name.
- **Personas als Datenordner** `Saves/PluginData/AIBody/personas/<name>/` (JSON + Sounds, DollMaster-Stil, lädt keine Plugins), auch männliche Personas (Jackaroos Dollmaster Male Personas) – Anforderungskatalog – Braucht Persona-Auswahl in Plugin und App.
- **Zustände als Trigger** (idle, hört zu, denkt, spricht) für Szenen-Logik – Anforderungskatalog – Nicht begonnen.
- **Viseme-Lippensync** aus TTS-Zeitdaten statt VaMs Audio-Lippensync – Anforderungskatalog – Nicht begonnen.
- **Emotionen auf Morphs**, Gestik passend zum Gesagten – Anforderungskatalog – Teilweise über Tool-Aufrufe (v0.7.4); Abbildung von Emotionen auf Morphs nicht begonnen.
- **Lebendigkeit wie MacGruber Life** (Atmung mit Brustbewegung und Atemgeräusch, Herzschlag, Blinzeln, Schwanken) – Anforderungskatalog – Bis dahin Life auf derselben Figur.
- **LogicBricks-artige Reaktionen** auf Szenen-Ereignisse (Berührung, Nähe, Trigger) und Rückmeldung an die App, engere Timeline-Anbindung – Anforderungskatalog – Nicht begonnen.
- **Persönlichkeitsprofile und Gedächtnis** der KI – Anforderungskatalog – Nicht begonnen.

## Begleit-App
- **Lokale Engines** (STT faster-whisper/Vosk, LLM über Ollama o. Ä., TTS Piper/XTTS) – Backlog v0.6.0 – Cloud-Engines xAI/ElevenLabs sind umgesetzt (v0.7.0), lokale nicht.
- **Silero-VAD (neuronal)** – bewusst nicht umgesetzt (würde torch/onnxruntime erzwingen). Die bessere Sprachaktivitätserkennung (eingebauter Detektor mit lernendem Grundpegel, optional webrtcvad) ist seit 19.11.2026 umgesetzt, siehe SPEC; weitere Engines passen hinter `make_vad` in `audio/vad.py`.
- **Unterbrechen per Stimme ohne Kopfhörer** (Echo-Unterdrückung, z. B. WebRTC AEC) – TODO in `companion/aibody_companion/audio/echo_gate.py` – Bis dahin Echo-Sperre; per Stimme nur mit Kopfhörer, Push-to-Talk immer.

## Entfernte Menüeinträge (Version 15) und ihre ursprüngliche Absicht

Leons Rückmeldung nach dem VaM-Test von Version 14 (17.11.2026): Platzhalter und leere Felder weg, Infos in ein großes Feld. Vor dem Entfernen festgehalten (Quellen: Code-Kommentare, Commits, SPEC, ANFORDERUNGEN, BACKLOG):

- **Tab „Post“** – Commit c601b87 (17.11.2026 19:59, Menü nach Leons Wunsch), vorher Tab „Verbindung“ (v0.6.3). Absicht: Verbindungseinstellungen; Bezeichnung so, wie Leon sie sagte, im Code als Konstante `PostTabLabel` mit dem Vermerk „vielleicht Port gemeint“. Inhalt zuletzt nur das Feld Channel (Pfadanzeigen schon in v0.7.4 entfernt). Entscheidung Leon 17.11.2026: „Post“ heißt „Posen“; Posen liegen im Tab AI Character, der Tab entfällt.
- **Feld „Channel“ (zeigte nur `default`)** – seit v0.6.3. Absicht: Kanal = Unterordner `Saves/PluginData/AIBody/<Kanal>/` und `Custom/Sounds/AIBody/<Kanal>/`, damit mehrere Plugin-/App-Paare getrennt laufen. Bleibt gültig: `connection.channel` in config.json, `--channel` der App; Speicherwert in der Szene bleibt. Zukunft: BACKLOG „Kanal im Menü“.
- **Felder „xAI key file“ / „ElevenLabs key file“** (in VaM leere Kästen ohne Beschriftung, Leons „leere Questions“) – Commit c601b87. Absicht: Pfad einer Textdatei mit dem Key statt des Keys selbst (kein Klartext-Key in Szene/config.json); eingefügter Key wurde abgelehnt. Bleibt gültig über config.json (`ai.xai.key_file`, `ai.elevenlabs.key_file`) und Umgebungsvariablen; die Datei gewinnt bei jedem Start. Zukunft: BACKLOG „Key-Datei-Pfad im Menü, beschriftet“.
- **Regler „Delay (s) – Platzhalter, ohne Funktion“** – Commit c601b87, von Leon angefragt, Absicht nie spezifiziert („was soll verzögert werden?“), nicht gespeichert. Zukunft: BACKLOG „Delay-Einstellung“.
- **Titelzeile je Tab** (Textfeld nur mit dem Tab-Namen, z. B. nur „AI“) – seit v0.6.3. Absicht: zeigen, welcher Tab offen ist. Ersatz: „Info: <Tab>“ im Infofeld links.
- **Tab „AI“** – Commit c601b87, vorher Tab „Engines“ (v0.7.0). Absicht: Engines, Key-Dateien, Key-/Engine-Status, Proactive. Inhalt jetzt unter Voice > AI Character; Status im Infofeld.
- **Textfeld „Engines: waiting for the companion app …“** (Engine-Status) – v0.7.0 (Commit 4ea1d45). Absicht: je Engine gewählt / aktiv / Fallback mit Grund zeigen. Nützlich, deshalb im Infofeld (Tab Voice), sobald die App den ersten Heartbeat schickt; vorher sagt *Live* „Companion app: not seen yet“.
- **Textfeld Key-Status** („API-Keys: warte auf die Companion-App …“) – v0.7.0/c601b87. Absicht: konfiguriert / fehlt / abgelehnt je Anbieter mit Hinweis auf console.x.ai. Im Infofeld (Tab Voice).
- **Hilfetexte Einfacher Q&A und AI mode, Push-to-Talk-Erklärung, Mikrofon-Status, Ergebnis von Reload Config JSON** – v0.7.2–v0.7.4. Absicht: Erklärung bzw. Rückmeldung direkt am Bedienelement (Tooltip ohne belegte API). Im Infofeld beim jeweiligen Tab.
- **Tab „Erweitert“** – v0.6.3. Absicht: selten gebrauchte Einstellungen (File poll interval, Verbose log). Zusammengelegt mit Config.

## Endgültig gestrichen (kein Backlog)
- **HTTP-Transport / Netzwerkcode im Plugin** (entfernt v0.6.1) – nur falls VaM das offiziell erlaubt.
- **Mikrofon in VaM** – bleibt in der Begleit-App.
- **APIs ohne öffentlichen, funktionierenden Plugin-Beleg** für die Sandbox von VaM 1.22 – siehe `API_AUDIT.md`.
