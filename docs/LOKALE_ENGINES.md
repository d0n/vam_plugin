# Lokale Engines, Silero und Stimm-Unterbrechung (Version 29)

Alles hier läuft in der Begleit-App auf dem eigenen Rechner. Das Plugin ändert sich nur um den Eintrag „Silero“ im Menü **VAD engine**.

## Ollama als Sprachmodell (kein Schlüssel, keine Cloud)

1. [Ollama](https://ollama.com) installieren und ein Modell holen, z. B. `ollama pull llama3.2` (oder `qwen3:8b`, `gemma3`; für gute deutsche Sätze lohnt ein größeres Modell). Ollama lauscht auf `http://127.0.0.1:11434`.
2. In VaM: Tab Voice > AI Character > **Language model** = `ollama` (oder `engines.llm` in `config.json`). Der Modus muss **chain** sein (oder qa/auto ohne xAI-Schlüssel); Realtime ist xAI-only.
3. Einstellungen in `config.json` unter `ai.ollama` (nur Datei, Neustart der App): `base_url` (Standard `http://127.0.0.1:11434`), `model` (`llama3.2`), `max_output_tokens` (400), `temperature` (0,7), `keep_alive` (`10m`: so lange bleibt das Modell im Speicher), `max_messages` (40 Gesprächsrunden, die die App bei jeder Frage mitschickt), `timeout_s` (120).

Was anders ist als bei xAI: Ollama kennt kein Gespräch, die App hält den Verlauf selbst (Persona und Stilregeln als Systemnachricht). **Keine Körper-Werkzeuge** (Funktionsaufrufe lokaler Modelle sind zu uneinheitlich): Ausdruck und Geste kommen wie bei der Kette üblich über ein `<<happy nod>>`-Kürzel am Anfang der Antwort; hält sich das Modell nicht daran, greift der Emotions-Rückfall. Sprache (STT) und Stimme (TTS) bleiben xAI oder ElevenLabs bzw. die Testengines; **das Gedächtnis fasst bei gewähltem Ollama ebenfalls lokal zusammen** (nichts geht an xAI). Ist Ollama nicht erreichbar oder das Modell nicht installiert, sagt die Statuszeile es klar (`ollama serve` bzw. `ollama pull <Modell>`) und der Testmodell-Rückfall antwortet.

Nicht in VaM getestet und nicht gegen ein echtes Ollama (T18).

## Silero als Sprachaktivitätserkennung (onnxruntime, ohne torch)

1. `python -m pip install onnxruntime` (bringt numpy mit).
2. Die Modelldatei `silero_vad.onnx` (MIT-Lizenz, Version 5) von <https://github.com/snakers4/silero-vad/tree/master/src/silero_vad/data> laden und nach `<VaM>/Saves/PluginData/AIBody/models/silero_vad.onnx` legen (oder den Pfad in der Umgebungsvariablen `AIBODY_SILERO_MODEL` angeben). Die Datei gehört **nicht** ins Paket und nicht ins Repository.
3. Tab Client Character > **VAD engine** = `Silero`. `Auto` nimmt Silero, sobald die Datei da ist (sonst WebRTC, sonst den eingebauten Detektor). **VAD strictness** 0 bis 3 setzt die Schwelle der Sprachwahrscheinlichkeit (0,3 / 0,4 / 0,5 / 0,65); **VAD threshold** bleibt eine Untergrenze für den Pegel.

Das Infofeld zeigt, was wirklich läuft (`silero (onnxruntime), strictness 2`) oder warum nicht (Datei fehlt, onnxruntime fehlt, falsche Modellversion). Bei einem Fehler im laufenden Betrieb entscheidet die Pegelregel weiter. Silero hört 32-ms-Stücke; die App sammelt die 30-ms-Frames dazu. Läuft das Modell auf der CPU mit einem Thread, kostet ein Stück Bruchteile einer Millisekunde.

## Stimm-Unterbrechung ohne Kopfhörer (Pegelregel)

Schlüssel `ai.barge_in` in `config.json` (nur Datei, **aus** als Standard):

| Schlüssel | Standard | Bedeutung |
|---|---|---|
| `enabled` | false | Regel an |
| `ratio` | 2.0 | wie viel lauter als das gelernte Echo die Stimme sein muss |
| `min_ms` | 600 | so lange muss es durchgehend lauter sein |
| `floor` | 0.02 | darunter (Pegel 0 bis 1) ist es nie der Nutzer |

Während die Figur spricht (ab dem gemeldeten `speech_started`), lernt die App den Echo-Pegel am Mikrofon als langsam abklingenden Spitzenwert (die ersten 450 ms nur lernen). Hält eine Strecke von `min_ms` deutlich über `ratio` mal Echo, gilt sie als der Nutzer: Die Figur (bei mehreren Figuren alle) hört auf, die Echo-Sperre öffnet sich, die laute Strecke geht als Anfang der Äußerung weiter an die Erkennung (Kette) bzw. an den Realtime-Server. Nur im Modus Voice activation, nicht bei Push-to-Talk (der unterbricht ohnehin).

Grenzen: Es ist eine Regel, keine Echo-Löschung. Eine leise Stimme oder laute Lautsprecher lösen nicht aus; ein sehr lauter Satz der Figur, ein Türknall oder Husten kann auslösen. Mit Kopfhörer bleibt der Schalter **Voice barge-in (headphones)** besser. Zum Einstellen `ratio` und `min_ms` ändern und mit dem Pegelmesser vergleichen (T18).

## Was nicht dabei ist

faster-whisper (lokale Spracherkennung) und Piper (lokale Stimme) sind Backlog (siehe BACKLOG.md); Tool-Aufrufe für Ollama ebenso.
