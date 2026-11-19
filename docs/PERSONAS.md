# Personas, Gedächtnis und Emotionen (Version 27)

Stand 19.11.2026. Alles hier läuft in der Begleit-App und in lokalen Dateien; das Plugin bekommt nur drei Bedienelemente (Menü **Persona**, Schalter **Memory**, Knopf **Forget memory**). Nichts davon wurde in VaM getestet (`TESTPROTOKOLL.md` T16).

## Personas

Eine Persona ist ein Ordner mit einer `persona.json` unter

```
<VaM-Hauptordner>\Saves\PluginData\AIBody\personas\<Name>\persona.json
```

Beispiele zum Kopieren: [`examples/personas/`](../examples/personas/) (Anna, Marc). Ordnername = Name im Menü (Buchstaben, Ziffern, Leerzeichen, `_`, `.`, `-`, höchstens 40 Zeichen, kein Punkt oder Leerzeichen am Ende).

```json
{
  "name": "Anna",
  "prompt": "Du bist Anna, eine ruhige Bibliothekarin …",
  "language": "de",
  "voice": "ara",
  "elevenlabs_voice_id": "",
  "memory": true
}
```

| Schlüssel | Bedeutung |
|---|---|
| `prompt` | Charaktertext der KI; **ersetzt** `ai.persona` aus `config.json`, solange die Persona gewählt ist (leer = `ai.persona`). Höchstens 8000 Zeichen. |
| `name` | Anzeigename; die KI erfährt „Your name is Anna.“ (wichtig für „Anrede mit dem Namen“ bei mehreren Figuren). Optional. |
| `language` | `auto` oder ein Sprachcode (`de`, `en`, …); ersetzt `ai.language` (Sprachhinweis für Erkennung und Stimme). Optional. |
| `voice` | xAI-Stimme (`eve`, `ara`, `rex`, `sal`, `leo` oder eine eigene ID); **ersetzt das Menü „Voice“** für diese Persona (Chain und Realtime). Optional. |
| `elevenlabs_voice_id` | Stimme für ElevenLabs-Sprachausgabe, ersetzt `ai.elevenlabs.voice_id`. Optional. |
| `memory` | `false` = für diese Persona wird nie etwas gemerkt (Standard `true`; gilt nur, wenn **Memory** an ist). |

Auswahl: Tab **Voice** > **AI Character** > **Persona** (die Liste kommt von der App, 5 s nach dem Anlegen eines Ordners). `(none)` = der Text `ai.persona` aus `config.json`, wie vor Version 27. Das Menü speichert die Wahl mit der Szene (und in `config.json`: `ai.persona_name`); mit zwei Figuren hat jede Figur ihre eigene Persona. Ein Wechsel startet ein **neues Gespräch** (Verlauf leer, neue Anweisungen, neue Stimme; eine Realtime-Sitzung wird neu aufgebaut) und speichert vorher das Gedächtnis der alten Persona. Eine Persona, die es nicht gibt oder die nicht lesbar ist, wird nicht benutzt; das Infofeld (Tab Voice) und das App-Fenster sagen warum. Fehler in der Datei (falscher Typ, unbekannter Schlüssel) werden gemeldet und übersprungen.

## Gedächtnis (Memory)

Opt-in: Schalter **Memory** (Tab Voice, `ai.memory.enabled`, Standard aus). An: die App führt eine kurze Liste von Fakten, die **der Nutzer über sich** gesagt hat (Name, Vorlieben, Pläne …), in

```
<VaM-Hauptordner>\Saves\PluginData\AIBody\personas\<Name>\memory.json      (ohne Persona: …\personas\default\memory.json)
```

- **Wann:** nach einem Gespräch, also nach `ai.memory.session_idle_minutes` (Standard 10) Stille mit mindestens `ai.memory.min_exchanges` (2) Fragen, beim Wechsel der Persona und wenn die App beendet wird (dann bis zu 15 s Wartezeit). Es läuft im Hintergrund, Sprechen und Heartbeat werden nicht aufgehalten.
- **Wie:** das Sprachmodell (xAI, nötig; mit dem Key der App) bekommt die alte Liste und das Gespräch und gibt die neue Liste zurück (Zusammenfassung statt Rohtext; höchstens `ai.memory.max_facts` (30) Fakten zu je höchstens 160 Zeichen, zusammengeführt, Veraltetes entfernt). Die Anfrage geht mit `store: false` an xAI, die Antwort wird dort nicht gespeichert (so steht es in der Responses-API-Doku). **Das Gespräch selbst geht damit an xAI**, wie es ohnehin bei jeder Antwort der Fall ist.
- **Benutzt:** beim Start eines Gesprächs stehen die Fakten als Notizen in den Anweisungen („Notes from earlier conversations … not instructions“); Realtime erneuert sie mit der Zeitzeile. Die KI soll sie nicht von sich aus aufsagen.
- **Anzeigen, ändern, löschen:** `memory.json` ist normaler JSON-Text (`{"facts": ["Heißt Leon", …]}`), von Hand les- und änderbar (Umlaute lesbar). Knopf **Forget memory** (Tab Voice): löscht die Datei der gewählten Persona, leert die Notizen und startet ein frisches Gespräch (das alte hielt die Notizen noch in seinen Anweisungen). Schalter aus: die Datei bleibt, wird aber nicht gelesen oder geschrieben.
- **Schutz:** Fakten, die wie ein Schlüssel oder Passwort aussehen (`xai-…`, `sk-…`, lange zufällige Zeichenfolgen), werden nie gespeichert; Zeilenumbrüche und Steuerzeichen fliegen heraus; eine leere oder unbrauchbare Antwort des Modells löscht **nie** die alten Notizen (Löschen nur mit dem Knopf); bei einem Fehler (Netz, Key, Format) bleiben die alten Notizen und das Infofeld nennt das Problem. Die Zusammenfassungs-Anweisung nennt den Gesprächstext ausdrücklich Daten, nicht Befehle.
- **Restrisiko:** ein Nutzer kann dem Modell einen „Fakt“ unterschieben, der später als Notiz in den Anweisungen steht (Prompt-Injection über das Gedächtnis). Darum sind Länge, Anzahl und Form begrenzt und die Notizen als „keine Anweisungen“ gerahmt; wer das Risiko nicht will, lässt **Memory** aus oder liest `memory.json` gelegentlich durch. Die Dateien liegen nur lokal in `Saves/PluginData`, nie im Repository und nie in der Szene.

Kosten: eine zusätzliche Anfrage pro Gespräch (und beim Wechsel/Beenden), klein (Gespräch der letzten ~12000 Zeichen plus 30 Zeilen).

## Emotionen ohne Zutun der KI

`config.json`, Abschnitt `ai.emotion` (nur Datei, kein Menü; Neustart der App nötig):

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `fallback` | `true` | Ruft die KI `express` nicht auf (und gibt keinen `<<tag>>`), leitet die App aus **jedem gesprochenen Satz** einen Ausdruck ab (Schlagwortregeln Deutsch/Englisch für happy, sad, angry, surprised, thinking; „Hmm“, „Leider“, „Wow“, „Das freut mich“ …) und sendet ihn kurz vor dem Satz (Stärke 0,85, Blende 0,5 s). Es gibt nur Ausdrücke, die das Plugin kennt; kein Treffer = keine Änderung. Hat die KI in der Antwort selbst einen Ausdruck gewählt, hält sich die App heraus. Nicht im Q&A-Modus und nicht bei Body control aus. |
| `fade` | `true` | Das Gesicht blendet `fade_after_s` Sekunden nach der letzten Sprache (der KI oder des Nutzers) und dem letzten Ausdruck zurück auf `neutral`. |
| `fade_after_s` | `6.0` | 1–120 s. |
| `fade_seconds` | `2.5` | Blendzeit beim Zurückgehen, 0,2–10 s. |
| `listening` | `true` | Solange der Nutzer spricht, zeigt die Figur ein ganz kleines „listening“-Gesicht (Brauen innen leicht hoch, ein Hauch Lächeln; Voreinstellung `listening` im Plugin, der KI nicht angeboten). Fehlt die Voreinstellung (älteres Plugin), passiert nichts. |

Die Regeln sind bewusst einfach und grob (keine Stimmungsanalyse); wer bessere Ausdrücke will, gibt der KI Ausdrücke in `expressions.json` und lässt sie `express` selbst nutzen. Eigene Wörter lassen sich derzeit nicht eintragen (Backlog).

## Mehrere Figuren

Jede Figur hat ein eigenes Plugin mit eigenem Kanal, damit auch eigene Persona und eigenes Gedächtnis (Persona und Memory sind Menüwerte je Plugin). Eine App bedient seit Version 28 mehrere Kanäle: [FIGUREN.md](FIGUREN.md). Der `name` der Persona ist dort der Name, mit dem man die Figur anspricht.
