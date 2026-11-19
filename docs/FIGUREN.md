# Mehrere Figuren (Version 28)

Eine Begleit-App kann mehrere Figuren bedienen. Jede Figur ist ein eigenes AIBody-Plugin in der Szene mit **eigenem Kanal**; die App führt für jeden Kanal ein eigenes Gespräch (eigene Persona, eigenes Gedächtnis, eigener Verlauf, eigene Stimme) und teilt sich **ein Mikrofon**.

## Einrichten

1. In VaM bei jeder Figur: Tab **Config** > Feld **Channel** (Buchstaben, Ziffern, `-`, `_`). Beispiel: `anna` und `marc`. Das Plugin startet die Verbindung neu, sobald du eine Sekunde nicht mehr tippst; der neue Kanal steht danach auch in `config.json` (`connection.channel`) und in der Szene.
2. **Eine** App für alle Kanäle starten:
   `python -m aibody_companion --vam-root "D:\VaM" --channel anna,marc`
   Oder dauerhaft in `config.json`: `"ai": { "channels": "anna,marc" }` (die Kommandozeile gewinnt). Mehr als acht Kanäle werden nicht bedient.
3. Pro Figur im Menü Persona, Stimme, Modus usw. einstellen. Diese Werte gehören zum jeweiligen Plugin (zum Kanal); gemeinsam ist nur die Datei `config.json` (jeder schreibt hinein) und das Mikrofon.

## Wer antwortet?

- Der Nutzer nennt den **Namen einer Figur am Anfang oder am Ende** des Satzes („Anna, wie war dein Tag?“, „Wie war dein Tag, Marc?“): diese Figur antwortet. Gemeint sind die ersten fünf und die letzten drei Wörter; ein Name mitten im Satz („Gestern habe ich mit Anna geredet …“) gilt als Thema, nicht als Anrede. Kommen zwei Namen vor, gewinnt der frühere.
- Gültige Namen einer Figur: der `name` ihrer Persona, der Ordnername der Persona und der Kanalname (`-` und `_` zählen als Leerzeichen). Namen unter drei Buchstaben werden nicht erkannt.
- Ohne Namen antwortet die Figur, die **zuletzt gesprochen** oder zuletzt angesprochen wurde. Beim Start ist es die erste im `--channel`.
- Figuren, deren Plugin nicht verbunden ist, werden nicht gewählt (solange mindestens eine verbunden ist).
- **Kette (Chain):** die Spracherkennung läuft nur einmal, dann übergibt die App den Satz an die genannte Figur. **Realtime:** der Server der aktiven Figur hört mit; sobald sein Transkript den Namen einer anderen Figur enthält, bricht die App die Antwort der ersten ab (sie kann schon ein Wort gesagt haben) und gibt den Satz als Nutzertext an die genannte Figur. Der Server-Verlauf der ersten Figur behält den Satz ohne Antwort.
- Eingaben in der Konsole der App folgen derselben Regel.

## Raum und Echo

- Das Mikrofon ist ein Gerät; seine Einstellungen kommen von dem Plugin, das zuletzt eine Konfiguration geschickt hat (Menüs der Tabs Client Character sollten bei allen Figuren gleich stehen).
- Das Audio geht nur an die aktive Figur (eine Spracherkennung, ein Satz = eine Antwort).
- Spricht eine Figur, bleibt das Mikrofon für **alle** zu (Echo-Sperre über alle Figuren): eine Figur hält die andere nicht für den Nutzer.
- Der Zeitgeber „Speech delay timer“ (von sich aus sprechen) startet bei jeder Aktivität neu, egal von wem; eine Figur fängt nur an, wenn keine andere gerade arbeitet oder spricht.
- Jede Figur zeigt im Infofeld (Tab Voice): „Figures in this app: anna, marc. The user talks to: marc (another figure)“.

## Grenzen

- Die Figuren sprechen nicht miteinander (kein „Regie“-Werkzeug): das braucht Schleifenschutz; steht im BACKLOG.
- Ein Kanal-Wechsel im Menü wirkt in der App erst nach dem Neustart der App (die App kennt ihre Kanäle beim Start).
- „Reload Config JSON“ liest den Kanal nicht neu (jede Figur behält ihren).
- Nicht in VaM getestet (TESTPROTOKOLL T17).

## Eine App je Figur (geht weiter)

Wie vorher: je Figur eine App mit `--channel`. Nachteil: jede App öffnet das Mikrofon und hört jede Figur als Nutzer; gemeinsame `config.json`. Für mehrere Figuren ist die eine App besser.
