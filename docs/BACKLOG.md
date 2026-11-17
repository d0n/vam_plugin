# AIBody – Backlog

Zurückgestellte Ideen und Wünsche. Keine Priorität, keine zeitliche Reihenfolge. Was als „cool“ / „nice to have“ genannt wird, aber nicht dran ist, kommt hierher statt in den Code.
Vereinbarter Umfang: [`SPEC.md`](SPEC.md) · Stand umgesetzt/offen: [`ANFORDERUNGEN.md`](ANFORDERUNGEN.md).
Format: **Idee** – Herkunft, Datum – Notiz / warum zurückgestellt.
Grundregel seit v0.6.0: erst Lauffähigkeit (eine `.cslist`, ein MVRScript, ein Ladeschritt + Begleit-App); alles mit zweitem Ladeschritt, zweitem Plugin oder Plugin-zu-Plugin-Brücke wartet, bis das eine Plugin in VaM 1.22 geprüft ist.

## Menü und Bedienung
- **Info-/Pfadanzeige im Menü** (Kanal-, Audio-, config.json-Ordner) – Leon, 17.11.2026 – In v0.7.4 entfernt (Menü zeigt nur Einstellbares). Leon versteht die Absicht, will sie erst, wenn es dort etwas Sinnvolles einzustellen gibt (dann im Tab Erweitert). Bis dahin stehen die Pfade einmal im VaM-Log.
- **In-Game-Testplugin à la Timeline** – Leon, 17.11.2026 – Noch keine Spezifikation. Teilweise abgedeckt: erweiterter Selbsttest im Statusfeld mit Ausgabe im Log der Begleit-App (Version 13); ein eigenes Testplugin bleibt ohne Spezifikation.
- **Direktes API-Key-Textfeld im Plugin** – Leon, 17.11.2026 – Key läge im Klartext in Szene und config.json. Unentschieden, nicht gebaut; bis dahin Pfad einer Key-Datei oder `XAI_API_KEY`.
- **Delay-Einstellung** – Leon, 17.11.2026 – Platzhalter „Delay (s)“ im Tab AI ohne Funktion; keine Spezifikation, was verzögert werden soll.
- **Aufteilung Session-Config vs. Person-Config** – Leon, 17.11.2026 – Welche Einstellung gilt pro Sitzung, welche pro Person; zurückgestellt bis nach den Tests in VaM.
- **Push-to-Talk-Erklärung als Mouseover/Tooltip** – Leon, 17.11.2026 – Kein belegter Sandbox-Weg für einen VaM-Schalter (einziges Beispiel via5/VUI baut ein eigenes UI-System), siehe `API_AUDIT.md`; bis dahin Erklärtext unter dem Schalter.
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
- **Blicksteuerung / Look-at** (Blick zur Kamera beim Zuhören, Look-at-Tool für die KI) – Anforderungskatalog – Plugin hat keine Blicksteuerung, daher kein Look-at-Tool (v0.7.4); bis dahin Glance.
- **Personas als Datenordner** `Saves/PluginData/AIBody/personas/<name>/` (JSON + Sounds, DollMaster-Stil, lädt keine Plugins), auch männliche Personas (Jackaroos Dollmaster Male Personas) – Anforderungskatalog – Braucht Persona-Auswahl in Plugin und App.
- **Zustände als Trigger** (idle, hört zu, denkt, spricht) für Szenen-Logik – Anforderungskatalog – Nicht begonnen.
- **Viseme-Lippensync** aus TTS-Zeitdaten statt VaMs Audio-Lippensync – Anforderungskatalog – Nicht begonnen.
- **Emotionen auf Morphs**, Gestik passend zum Gesagten – Anforderungskatalog – Teilweise über Tool-Aufrufe (v0.7.4); Abbildung von Emotionen auf Morphs nicht begonnen.
- **Lebendigkeit wie MacGruber Life** (Atmung mit Brustbewegung und Atemgeräusch, Herzschlag, Blinzeln, Schwanken) – Anforderungskatalog – Bis dahin Life auf derselben Figur.
- **LogicBricks-artige Reaktionen** auf Szenen-Ereignisse (Berührung, Nähe, Trigger) und Rückmeldung an die App, engere Timeline-Anbindung – Anforderungskatalog – Nicht begonnen.
- **Persönlichkeitsprofile und Gedächtnis** der KI – Anforderungskatalog – Nicht begonnen.

## Begleit-App
- **Lokale Engines** (STT faster-whisper/Vosk, LLM über Ollama o. Ä., TTS Piper/XTTS) – Backlog v0.6.0 – Cloud-Engines xAI/ElevenLabs sind umgesetzt (v0.7.0), lokale nicht.
- **Bessere Sprachaktivitätserkennung** (webrtcvad/Silero) – Anforderungskatalog, TODO in `companion/aibody_companion/audio/vad.py` – Derzeit Energie-VAD, austauschbar über `is_speech(frame)`.
- **Unterbrechen per Stimme ohne Kopfhörer** (Echo-Unterdrückung, z. B. WebRTC AEC) – TODO in `companion/aibody_companion/audio/echo_gate.py` – Bis dahin Echo-Sperre; per Stimme nur mit Kopfhörer, Push-to-Talk immer.

## Endgültig gestrichen (kein Backlog)
- **HTTP-Transport / Netzwerkcode im Plugin** (entfernt v0.6.1) – nur falls VaM das offiziell erlaubt.
- **Mikrofon in VaM** – bleibt in der Begleit-App.
- **APIs ohne öffentlichen, funktionierenden Plugin-Beleg** für die Sandbox von VaM 1.22 – siehe `API_AUDIT.md`.
