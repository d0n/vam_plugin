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
- LICENSE und `licenseType` „FC“ in `meta.json` nicht anfassen; Lizenzfrage außen vor.
- Keine Secrets im Repo; API-Keys nie im Log (geschwärzt), nie in Szene oder config.json.
- Code und README auf Englisch; Release-Notes auf Deutsch mit vollen Pfaden ab VaM-Hauptordner, Ladeort (Plugins-Tab der Person) und Bitte um Screenshot, rote `AIBody:`-Logzeilen und Konsolenausgabe der Begleit-App.
- Sinnvolle Commits direkt auf `main`, jeder Commit einzeln grün (Tests, ruff, Plugin-Check, Schema-Check).

## Verbindung
- Datei-Transport über `<VaM>/Saves/PluginData/AIBody/<Kanal>/` in beide Richtungen (Befehle rein, Events raus), Protokoll v3 (`protocol/PROTOCOL.md`, Schemas `protocol/schema/`).
- Heartbeat beider Seiten; Timeout 6 s → Status „GETRENNT“, automatischer Neuaufbau; alte Befehle werden verworfen.
- Plugin bleibt stabil ohne Begleit-App.

## Gemeinsame Konfiguration
- Eine globale Datei `<VaM>/Saves/PluginData/AIBody/config.json` (Kanal ist ein Wert darin), von Plugin und App gelesen; Schema `protocol/schema/config.schema.json`, Doku `docs/CONFIG.md`.
- Werte im Plugin-Menü (mit der Szene gespeichert) gewinnen und werden zurückgeschrieben; Szene ohne AIBody-Werte übernimmt die Datei einmal.
- Abschnitt `ai` gehört der Begleit-App; das Plugin setzt dort nur seine Menüwerte (Modus, Stimme, Proactive, Voice barge-in, Key-Datei-Pfade).

## API-Keys
- xAI braucht einen API-Key von console.x.ai; ein Grok-Abo / grok.com-Token funktioniert nicht. Statusanzeige und Hinweise sagen das.
- Key nur über Umgebungsvariable `XAI_API_KEY` / `ELEVENLABS_API_KEY` (gewinnt) oder den Pfad einer Key-Datei; ein ins Pfadfeld eingefügter Key wird abgelehnt und nicht gespeichert.
- Key-Status je Anbieter: konfiguriert / fehlt / abgelehnt (mit Grund).

## KI-Modi
- Standard `qa` (Einfacher Q&A): Spracherkennung xAI → Grok → Stimme xAI, nur Sprache, keine Körpersteuerung durch die KI, kein proaktives Sprechen.
- Realtime optional (Schalter „Echtzeit (Realtime) verwenden“ = `auto`): Grok Voice über `wss://api.x.ai/v1/realtime`, Kette als Fallback.
- `chain`: genau die im Tab AI gewählten Engines.
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

## Menü
- Das Menü zeigt nur, was sich einstellen lässt. Reine Info-/Pfadanzeigen gibt es nicht; eine Pfadanzeige nur im Tab Erweitert, wenn es dort etwas Sinnvolles einzustellen gibt.
- Erklär- und Statustexte, die zu einem Bedienelement gehören (Modus-Hilfe, PTT-Erklärung, Key-/Engine-Status, Mikrofon-Status), bleiben.
- Links immer sichtbar: Statusfeld (Selbsttest, Live-Status, Start-Log).
- Tabs:
  - Voice Mode: Einfacher Q&A-Modus, Active, Echtzeit (Realtime) verwenden, API Reconnect, Test-Ton über Companion, Test-Ton abspielen, Stop speaking.
  - AI: Engines (Speech-to-text, Language model, Text-to-speech inkl. ElevenLabs), Key-Datei-Pfade + Key-Status, Delay (Platzhalter), Proactive, Proactive idle; Engine-Status (aktiver Modus, bereit / nicht konfiguriert, Fallback).
  - AI Character: AI mode, Voice; Pose (Auswahl, Pose anwenden, Posen neu laden); Ausdruck und Geste (Auswahl, Ausdruck zeigen, Reset expression, Geste abspielen); Körper (Body control, Lautstärke, Idle, Atmung, Atem-Morph, Reload Expressions).
  - Client Character: Mikrofon-Einstellungen inkl. Gerätemenü, Push-to-Talk mit Erklärtext, Voice barge-in (headphones).
  - Post: Channel. (Bezeichnung als Konstante `AIBodyPlugin.PostTabLabel`.)
  - Config: Reload Config JSON + Ergebnis.
  - Erweitert: File poll interval, Verbose log.

## Protokollierung
- Verbose log (Tab Erweitert / `advanced.verbose_log` / `-v`): pro Runde Trace mit Runden-Nummer und Zeit in Konsole und `<VaM>/Saves/PluginData/AIBody/logs/companion.log` (1 MB × 5); im Plugin `[debug]`-Zeilen und *Letzte Ereignisse*.

## Latenz
- Gemessen vom Ende der Nutzersprache (VAD-Ende, PTT loslassen, Enter; Realtime: speech_stopped) bis zum ersten Ton (speech_started des Plugins).
- Aufschlüsselung: STT, LLM erstes Token, erster Satz, TTS, Datei, an Plugin, Plugin-Start (Realtime: Server erstes Audio, Segment, an Plugin, Plugin-Start).
- Pro Runde eine Logzeile; letzter Wert und Mittel der letzten 10 im Statusfeld (*Live*, „Latenz bis zum ersten Ton“).

## Änderungen
- 17.11.2026 (v0.7.4): Erste Fassung des Spec-Logs.
