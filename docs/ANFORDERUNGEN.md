# AIBody – Anforderungskatalog (Single Source of Truth)

> **Nicht bindend.** Sammlung aller Ziele und Ideen aus Chat und Anrufen (Stand: 17.11.2026, nach Release v0.7.1). Zum Bearbeiten, Ergänzen und Nachschlagen gedacht, keine Arbeitsanweisung.
> Repo: https://github.com/d0n/vam_plugin · Aktueller Release: [v0.7.1](https://github.com/d0n/vam_plugin/releases/tag/v0.7.1) (`d0n.AIBody.8.var`) · Testanleitung: [`docs/TESTPROTOKOLL.md`](https://github.com/d0n/vam_plugin/blob/main/docs/TESTPROTOKOLL.md)

**Ziel:** Ein Virt-A-Mate-Plugin (VaM 1.22), das einer KI einen virtuellen Körper gibt. Die KI spricht mit Lippensync, reagiert mit Mimik, Gestik und Posen, und hört über das Mikrofon zu.

---

## 1. Muss jetzt

*Ohne diese Punkte läuft gar nichts. K.O.-Kriterien und der minimale erste Stand.*

### Laden und Sandbox
- [ ] **Das Plugin lädt in VaM 1.22 ohne Fehler im Log.** C# 6, geladen über eine `.cslist`. *(Noch nicht in VaM getestet.)*
- [x] **Laden in einem Schritt:** ein Plugin, eine `.cslist` (`Custom/Scripts/d0n/AIBody/AIBody.cslist`), genau eine MVRScript-Klasse und eine flache Dateiliste. Der Nutzer fügt es einmal im Plugins-Tab der KI-Figur hinzu.
- [x] **Strenge Sandbox (seit v0.6.1):** null `UnityWebRequest`, null `UnityEngine.Networking`, kein `WWW`, `System.IO`, `System.Net`, `Process`, keine Reflection, kein `DllImport` und kein Unity-`Microphone`. Ein Scan bricht den Build ab, sobald so etwas auftaucht.
- [x] **Nur belegte APIs:** Was nicht durch VaM-Doku oder öffentlichen Code bekannter Plugins gedeckt ist, fliegt raus statt umgangen zu werden. Die Belege stehen in `docs/API_AUDIT.md`.
- [x] **Dateizugriff nur über `FileManagerSecure`.**
- [x] **Keine Netzwerkfreigabe nötig:** „Allow Plugins Network Access“ bleibt aus.
- [ ] **Auf die Figur legen und wieder entfernen,** Szene speichern und neu laden, ohne Exceptions und ohne spürbaren FPS-Einbruch. *(Seit v0.6.2 läuft jede Init-Phase einzeln abgesichert, mit Statusfeld und Selbsttest; in VaM noch nicht getestet, siehe Testprotokoll T6.)*

### Installation
- [x] **Eine einzige `.var`** (`d0n.AIBody.8.var`) kommt nach `<VaM-Hauptordner>/AddonPackages/`.
- [ ] **Alte AIBody-Pakete löschen:** `d0n.AIBody.1` bis `d0n.AIBody.7.var`, `d0n.AIBodySession.*`, `d0n.AIBodyPerson.*`, `d0n.AIBodyPerson2.*`. Bei Szenen, die mit einer älteren Version gespeichert sind, alten Plugin-Eintrag entfernen und neu hinzufügen. *(Liste in README und Release-Notes; ob beim Nutzer erledigt, prüft Testprotokoll T1.)*
- [x] **Release-Notes auf Deutsch** mit vollem Pfad ab dem VaM-Hauptordner und dem Ladeort.

### Verbindung zur Begleit-App
- [x] **Begleit-App (Python, „companion app“)** läuft neben VaM: `python -m aibody_companion --vam-root "C:/VaM"`.
- [x] **Datei-Transport** über `Saves/PluginData/AIBody/<channel>/`, in beide Richtungen: Befehle rein, Events raus (Status, Sprechbeginn, Sprechende). Protokoll v3.
- [x] **Heartbeat und Status-Anzeige** im Plugin.
- [ ] **Robust:** Fehlt die App oder stürzt sie ab, bleibt das Plugin stabil, zeigt den Status an und verbindet sich von selbst neu. *(v0.6.3: im Code fertig, mit Python-Tests; in VaM noch nicht getestet, siehe Testprotokoll T6. Heartbeat-Timeout 6 s → Status „GETRENNT“ mit einer Logzeile, automatischer Neuaufbau beim nächsten Heartbeat (ready + config neu), keine Logflut; alte Befehle werden verworfen (Plugin leert seine Inbox beim Start, App löscht nicht abgeholte Befehle nach 10 s), Outbox ohne App höchstens 20 Dateien; App-Neustart mitten im Sprechen bricht die alte Sprachausgabe ab; die App leert den Kanal beim Start. v0.7.0: erneut durchgesehen und per End-to-End-Simulation getestet (echte Begleit-App + nachgebaute Plugin-Seite auf dem Datei-Kanal: App-Absturz → „GETRENNT“ nach 6 s mit einer Logzeile, Outbox ≤ 20, App-Neustart → automatisch wieder verbunden, alte Sprachausgabe gestoppt; Plugin weg → Mikrofon nicht gesperrt, keine Heartbeat-Flut). Die Plugin-Seite der Simulation ist ein Python-Nachbau des C#-Codes, kein echtes VaM.)*

### Mikrofon
- [x] **Mikrofon nur in der Begleit-App:** Aufnahme, Geräteliste, Sprachaktivitätserkennung und Echo-Sperre, damit die KI sich nicht selbst hört.
- [x] **Push-to-Talk** wird im Plugin geschaltet und als Datei an die App gemeldet.

### Sprachausgabe
- [ ] **VaMs eigener Audio-Lader:** `NormalizeMediaPath` → `URLAudioClipManager.QueueClip` → `PlayNow` auf der Kopf-Audioquelle (`HeadAudioSource`), dazu VaMs eingebauter Lippensync. *(Im Code drin, in VaM noch nicht bestätigt; Testprotokoll T3.)*
- [x] **Audio nur als lokale Datei**, kein Download per URL.

### Grundsteuerung des Körpers
- [ ] **Gesichtsausdrücke über Morphs, Atmung und Kopf-Leerlauf.** *(Morph-Namen noch nicht bestätigt; Testprotokoll T5. Seit v0.6.3 ist der Atem-Morph auch in `config.json` einstellbar.)*
- [ ] **Posen über Pose-Presets** *(der Name des Pose-Speichers ist noch nicht bestätigt)* **und Gesten über Timeline-Aktionen** (`Play <Name>`).

### Konfiguration
- [ ] **JSON-Config für die Eingabeparameter:** Kanal, Engine-Wahl, Mikrofon, Push-to-Talk und Pfade, als JSON-Datei, die Plugin und App gemeinsam lesen bzw. über den Datei-Transport abgleichen. *(v0.6.3: im Code fertig, mit Python-Tests und Schema; in VaM noch nicht getestet. Die Werte im Plugin-Menü (mit der Szene gespeichert) gewinnen und werden zurückgeschrieben; eine Szene ohne gespeicherte AIBody-Werte übernimmt die Datei einmal; die App legt die Datei mit Standardwerten an und liest Kanal, Mikrofon und Engines, `--channel` gewinnt. Doku: `docs/CONFIG.md`, Schema: `protocol/schema/config.schema.json`. v0.7.0: Rundlauf App → Datei → Plugin → Datei → App per End-to-End-Simulation getestet. Dabei gefunden und behoben: VaM schreibt Zahlen und true/false als Text (`"2.5"`, `"true"`, Beleg E21 in `docs/API_AUDIT.md`); die App hatte solche Werte bisher verworfen – Mikrofon-Einstellungen aus dem Plugin, Push-to-Talk und die vom Plugin geschriebenen config.json-Werte wären ignoriert worden. Neu: Abschnitt `ai` (nur Begleit-App: Persona, Sprache, Fallback, xAI-/ElevenLabs-Einstellungen, Pfad der Key-Datei), den das Plugin beim Schreiben unverändert lässt.)*
- **Fakt – Ort der Config (entschieden 15.11.2026):** eine globale Datei `<VaM-Hauptordner>/Saves/PluginData/AIBody/config.json`, nicht pro Kanal (der Kanal ist ein Wert darin). Belege: bekannte Plugins legen ihre Daten in einen eigenen Ordner unter `Saves/PluginData` (Timeline: `Saves/PluginData/Timeline/settings.json` als globale Standardwerte, Keybindings: `Saves/PluginData/Keybindings`, Scripter schreibt per `FileManagerSecure.WriteAllText` unter `Saves/PluginData/Scripter`); VaMs offizielle API-Doku zu `FileManagerSecure.WriteAllText` sagt, dass das Anlegen von Dateien über VaMs Bestätigungssystem laufen kann. Eine offizielle Liste erlaubter Schreibordner gibt es nicht. Links: `docs/API_AUDIT.md`, Abschnitt „Config file location“ (E10, E19, E20).
- [ ] **Config-Menü in Kategorien (Tabs) statt einer langen Liste** – *vom Nutzer am 15.11.2026 gewünscht.* Tabs: Status, Verbindung (Kanal, Pfade), Engines, Mikrofon & PTT, Körper, Erweitert; Statusfeld und Selbsttest bleiben immer oben links sichtbar; `config.json` hat dieselben Kategorien (ein Objekt pro Tab). *(v0.6.3: im Code fertig über Tab-Buttons und VaMs `Create*`/`Remove*`, belegt in `docs/API_AUDIT.md` E17/E18; in VaM noch nicht getestet, Testprotokoll T4.)*
- [x] **Config-Menü im Plugin:** Kanal, Mikrofonwahl (Liste kommt von der App), Push-to-Talk, Engine-Menüs und Verbindungsstatus. Die Einstellungen werden mit der Szene gespeichert. *(Seit v0.6.3 in Tabs, siehe unten.)*

### Stand der KI
- **Fakt – was xAI für Sprache anbietet (geprüft auf docs.x.ai am 17.11.2026):** Spracherkennung **und** Sprachausgabe sind dokumentiert: `POST /v1/stt` (Modell `grok-voice-transcribe-2.0`, auch als WebSocket-Stream), `POST /v1/tts` (Stimmen z. B. `eve`, Formate mp3/wav/pcm), dazu Sprache-zu-Sprache über `wss://api.x.ai/v1/realtime` (Modell `grok-voice-latest`; seit v0.7.1 als Modus `realtime` genutzt: die Antwort-Audiodaten werden in WAV-Stücke geschnitten und über den Datei-Transport abgespielt). Links: `docs/CONFIG.md`, Abschnitt „What xAI offers for speech“.
- [x] **Test-Engines** (`null` / `echo` / `tone`) bleiben als Offline-Betrieb und als Fallback erhalten. Spracherkennung, KI und Sprachausgabe sind per Konfiguration (`engines` in `config.json` bzw. Tab Engines) austauschbar.

### Erster echter Test in VaM (offen – Anleitung: `docs/TESTPROTOKOLL.md`)
- [ ] Lädt das Plugin aus der `.var`? Fragt VaM, ob Plugins aus dem Paket erlaubt sind? *(T1)*
- [ ] Akzeptieren `ReadAllText` und `DeleteFile` die Pfade, die `GetFiles` liefert? *(T2)*
- [ ] Spielt der Kopf den Clip aus `Saves/PluginData` mit Lippensync ab? Funktionieren der `PlayNow`-Retry und die Erkennung von Start und Ende? *(T3)*
- [ ] Aktualisiert sich das Menü, wenn sich die Auswahlliste ändert, und funktioniert das Textfeld? Wechseln die Tabs sauber? *(T4)*
- [ ] Stimmen der Name des Pose-Speichers, die Morph-Namen für die Ausdrücke und der Atem-Morph? *(T5)*
- [ ] Hinzufügen, Entfernen, Speichern, Neuladen ohne Exceptions und FPS-Einbruch; „GETRENNT“ und automatischer Neuaufbau, wenn die App beendet und neu gestartet wird? Wird `config.json` ohne Rückfrage angelegt? *(T6)*
- [ ] Realtime-Modus mit echtem xAI-Key: verbindet, antwortet flüssig, lässt sich unterbrechen; proaktives Sprechen nach Stille? *(T8)*

---

## 2. Wollen wir auf jeden Fall

*Geplant, aber nach dem ersten lauffähigen Stand.*

- [ ] **Echte KI-Engines** in der Begleit-App für Spracherkennung, LLM und Sprachausgabe, dazu bessere Sprachaktivitätserkennung und Unterbrechen beim Reinreden. *(v0.7.0: Engines im Code fertig, aber **noch nie gegen die echten APIs gelaufen** (keine Keys vorhanden), nur gegen einen nachgebauten Server getestet – deshalb nicht abgehakt. Vorhanden: Spracherkennung `xai` (`POST /v1/stt`), LLM `xai` (Grok `grok-4.7`, `POST /v1/responses` mit Streaming, Persona über `instructions`, Gesprächsfaden über `previous_response_id`, Ausgabe satzweise, damit die Sprachausgabe schon beim ersten Satz startet), Sprachausgabe `xai` (`POST /v1/tts`) und `elevenlabs` (REST, austauschbarer Adapter). Keys nur über `XAI_API_KEY` / `ELEVENLABS_API_KEY` oder den Pfad einer Key-Datei in `config.json`; ohne Key „nicht konfiguriert“ im Tab Engines und automatischer Fallback auf `null` / `echo` / `tone`. Unterbrechen beim Reinreden: per Push-to-Talk wird die laufende Antwort jetzt abgebrochen; bessere Sprachaktivitätserkennung ist noch offen. Netzwerk nur in der Begleit-App, das Plugin bleibt ohne Netzwerkcode. v0.7.1: zusätzlich Modus `realtime` (Grok Voice über `wss://api.x.ai/v1/realtime`, eine dauerhafte WebSocket-Verbindung): Mikrofon wird gestreamt, der Server erkennt das Sprechende, die Antwort wird in Stücke geschnitten und ab dem ersten Stück gesprochen, Ausdrücke/Gesten über ein Funktions-Tool, Unterbrechen per Push-to-Talk bzw. mit Headset per Stimme, Neuverbindung mit Backoff. `ai.mode` `auto` nimmt Realtime, wenn ein xAI-Key da ist, sonst die Kette; Anzeige im Tab Engines. Ebenfalls nur gegen einen nachgebauten Server getestet, siehe Testprotokoll T8.)*
- [ ] **Proaktives Sprechen nach Stille** *(vom Nutzer am 17.11.2026 gewünscht)*: Nach einer einstellbaren Zeit ohne Gespräch darf die KI von sich aus etwas sagen – oder bewusst schweigen. Dazu bekommt sie bei jedem Gesprächsschritt die aktuelle Uhrzeit und die Zeit seit dem letzten Austausch mit, weil sie selbst keine Uhr hat. *(v0.7.1: im Code fertig: `ai.proactive` (an/aus, `idle_seconds`, Standard 90 s, Hinweistext), im Plugin Schalter **Proactive** und Regler **Proactive idle (s)** im Tab Engines; Realtime per `conversation.item.create` + `response.create`, Kette per LLM-Aufruf (`llm: xai`). Antwortet die KI mit `[silent]`, wird nichts abgespielt; nach unbeantworteten Anstößen verdoppelt sich die Wartezeit (bis 8×). In VaM noch nicht getestet (T8).)*
- [ ] **Aufteilung in Session und Person, erneut aufgreifen:** ein Session-Teil für die Verbindung, Mikrofon und Status, der Szenenwechsel überlebt, und ein Person-Teil pro Körper. *(So umgesetzt in v0.3/v0.4, dann zugunsten des Ladens in einem Schritt zurückgestellt. Code liegt unter `legacy/`.)*
- [ ] **Session-Anbindung**, also Laden beim VaM-Start über „Set Current As User Defaults“ für den Session-Teil.
- [ ] **Zweite Figur als eigene Instanz:** ein eigenständiges Person-Plugin mit eigenem Paket, eigenen Namen und fester Kennung. Die beiden Figuren werden nie zu einem Plugin zusammengelegt, und Befehle landen nie bei der falschen Figur. *(In v0.4 als `AIBodyPerson2` umgesetzt, derzeit zurückgestellt.)*
- [ ] **Client auf eigener Figur bzw. eigenem Atom,** getrennt vom Körper. *(v0.5-Ansatz, zurückgestellt.)*
- [ ] **Ein Schritt trotz mehrerer Teile:** ein Bootstrap-Plugin, das die übrigen Teile per `MVRPluginManager.CreatePlugin()` + `pluginURLJSON` auf die richtigen Figuren setzt (wie AcidBubbles Keybindings), oder ein mitgeliefertes Plugin-Preset in der `.var`. Kein Verlass auf zwei MVRScripts in einer `.cslist`, das ist nicht belegt.
- [ ] **Blicksteuerung.** Bis dahin wird Glance empfohlen.
- [ ] **Demo- bzw. Anleitungsszene.**
- [ ] **Doku und Veröffentlichung auf dem VaM Hub** in der Kategorie „Plugins + Scripts“ mit Tags. Die Lizenzfrage bleibt außen vor.
- [ ] **Quellennennung:** MacGruber wird bei einer Veröffentlichung als eine der Hauptquellen genannt, deren Code studiert wurde. Dasselbe gilt sinngemäß für weitere Vorbilder wie AcidBubbles oder VamDeluxe.

---

## 3. Nice to have

- [ ] **Lebendigkeit wie bei MacGruber Life:** Atmung mit Audio-Sync, Blinzeln, Blickverhalten. Selbst gebaut oder sauber neben Life lauffähig.
- [ ] **Eigene Trigger-Aktionen im Stil von LogicBricks** und eine engere Timeline-Anbindung.
- [ ] **Zustands-Trigger**, z. B. „spricht“, „hört zu“, „denkt“ als Auslöser für Szenen-Logik.
- [ ] **Viseme-Lippensync** statt des eingebauten Lippensyncs.
- [ ] **Emotionen auf Morphs abbilden** und Gestik passend zum Gesagten.
- [ ] **Personas als reine Datenordner** im DollMaster-Stil: JSON plus Sounds, Auswahl in Plugin und App. Personas laden **keine** Plugins, das ist laut DollMaster-Quellcode auch dort nicht so.
- [ ] **Männliche Personas** als Vorbild bzw. Kompatibilität, z. B. nach dem Muster von Jackaroos [Dollmaster Male Personas](https://hub.virtamate.com/resources/dollmaster-male-personas.3058/). Ein Plugin pro Figur mit eigener Persona, umbenannte Dateien gegen Kollisionen.
- [ ] **Sub-Plugins bzw. Verschachtelung.** Derzeit gibt es keinen belegten Weg in VaM, nur den Bootstrap per `CreatePlugin()`.
- [ ] **Interaktive Story-Szenen** nach dem Muster von VAMStory: Steuerung auf einem eigenen leeren Atom, Körper-Plugins auf der Figur, Atom bleibt immer an.
- [ ] **Komfortable UI** nach dem Vorbild von MacGruber Utils.
- [ ] **Bedienung in VR.**
- [ ] **Mehrere Figuren gleichzeitig,** über die zweite Instanz hinaus.
- [ ] **Persönlichkeitsprofile und Gedächtnis** der KI.
- [ ] **Später Kompatibilität mit VaM2.**
- [ ] **Szenen-Vorlage Green Screen / Passthrough** (Wunsch des Nutzers vom 17.11.2026): AIBody auf der Person plus Sallys Szenen-Plugin *Camera Background Color* mit #00FF00. Entwurf: `examples/scenes/AIBody_GreenScreen.json`, Anleitung `docs/SZENE_GREENSCREEN.md`. Plugin-Pfad, Klasse und Parameter aus dem Original-Paket belegt; nicht in VaM getestet.
- [ ] **Optionaler HTTP-Transport.** Aktuell **gestrichen**, weil er gegen die Sandbox-Regel verstößt. Nur wieder aufgreifen, falls VaM das irgendwann offiziell erlaubt.

---

## Feste Rahmenbedingungen
- LICENSE und `licenseType` „FC“ in `meta.json` nicht anfassen, die Lizenzfrage bleibt außen vor.
- Push direkt auf `main` in sinnvollen Commits ist freigegeben.
- Release-Beschreibungen auf Deutsch, mit vollem Pfad ab dem VaM-Hauptordner.

## Lernquellen
- MacGruber: [LogicBricks](https://hub.virtamate.com/resources/logicbricks.1975/), [Life](https://hub.virtamate.com/resources/life.165/), [Benchmark](https://hub.virtamate.com/resources/benchmark.11336/), [Utils](https://hub.virtamate.com/resources/macgruber-utils.40744/)
- AcidBubbles: Timeline, Glance, Keybindings (Bootstrap per `CreatePlugin`)
- VamDeluxe: [DeluxePlugin / DollMaster](https://github.com/vamdeluxe/DeluxePlugin) (Audio-Lader, Personas als Daten)
- hazmhox: [VAMStory](https://hub.virtamate.com/resources/vamstory.28256/) (Story-Steuerung auf eigenem Atom)
