---
name: motion-sound-bibliothek
description: "Sound-Bibliothek von Motion-Studio einrichten und pflegen: Quellen mit Links und Lizenzen (Kenney, Mixkit, Sonniss, Pixabay, Freesound, KI für Lücken), Laden, Einlesen, Katalog, Suche, Abhörseite mit Pegel nach Gehör, Familien, Sperren, fehlende Sounds ergänzen. Laden beim Setup (Stufe Sound) und bei \"Sound-Bibliothek\", \"Sounds laden\", \"Kenney\", \"Mixkit\", \"Sounds abhören\", \"Sound zu laut\", \"Familie anlegen\", \"Sound sperren\", \"der Sound nervt\", \"Sound fehlt\", \"neue Sounds\"."
---

# motion-sound-bibliothek

Die Bibliothek liegt in `__ARBEIT__/sounds/`: Dateien unter `files/<quelle>/`, Katalog `katalog.json` (je Sound: Dauer, Lautheit, Peak, Anschlag, Helligkeit, Tags, Familie, Urteil, Korrektur `trim_db`, gesperrt).
Alle Quellen, Links und Lizenzen: `__HEIM__/referenz/SOUND-QUELLEN.md`. Lies sie einmal, bevor du etwas lädst.
Katalog nie von Hand bearbeiten, nur über `__HEIM__/ms sound …`.

## Grundregeln
- Lokal zuerst. Extern nur für echte Lücken, Funde werden eingelesen und bleiben.
- Nur Lizenzen mit kommerzieller Nutzung ohne Pflicht-Nennung. Bei Unklarheit: nicht nehmen.
- Keine Massen-Downloads (Pixabay, Mixkit, Zapsplat verbieten das). Mixkit nur einzeln.
- Nie Sounds aus Code erzeugen.
- Kosten (ElevenLabs, Higgsfield): vorher Betrag nennen, Ja holen, erst dann erzeugen.
- `trim_db` und `urteil` sind das Ohr des Nutzers. Nie selbst ändern, nur über die Abhörseite oder auf seine Ansage.

## Einrichten (einmal, Setup-Stufe Sound)

**1. Kenney (gratis, CC0).**
```
__HEIM__/ms sound laden kenney          # zeigt die 7 Packs mit Link und Größe (zusammen rund 11 MB)
__HEIM__/ms sound laden kenney --ja     # lädt, entpackt, liest ein: rund 520 Sounds
```
Größe dem Nutzer nennen. Kostet nichts, also direkt laden.

**2. Lücken von Kenney mit Mixkit schließen.** Kenney hat kaum Whooshes und weiche Plopps. Hol je 4 bis 6 Stück einzeln:
- Seiten `https://mixkit.co/free-sound-effects/whoosh/`, `…/pop/`, `…/click/`, `…/transition/` mit WebFetch lesen. Die Nummer steht in der Vorschau-Adresse `…/sfx/<nummer>/<nummer>-preview.mp3`.
- Je Sound: `__HEIM__/ms sound laden mixkit <nummer> --name "<was es ist>" --ja`. Höchstens 20 pro Sitzung.
- Titel auf Mixkit-Listen sitzen manchmal beim Nachbarn. Darum nach dem Laden anhören (Schritt 4).

**3. KI-Felder (optional, wenn die Setup-Stufe KI installiert ist).**
`__HEIM__/ms sound ki` rechnet für jeden Sound die AST-Klasse (was die Maschine hört) und einen CLAP-Vektor (Textsuche). Mac: rund 4 Minuten für 500 Sounds. Ohne KI läuft alles, die Suche ist dann reine Textsuche in Namen und Tags.

**4. Abhören (der wichtigste Schritt).**
```
__HEIM__/ms sound abhoeren --neu --server       # Seite auf 127.0.0.1, speichert jedes Urteil sofort
```
Startet einen kleinen Server (läuft, bis Strg+C). Im Agenten im Hintergrund starten und dem Nutzer die Adresse geben. Chrome oder Firefox nehmen (Safari spielt .ogg nicht überall).
Ohne Server: `ms sound abhoeren --neu` schreibt `sounds/abhoeren.html`, der Nutzer öffnet sie, klickt am Ende „Export“, dann `ms sound urteile <datei.json>`.

Erkläre dem Nutzer vorher in drei Sätzen:
- Alle Sounds spielen gleich laut nach Messung. Wirkt einer trotzdem lauter, Regler nach links, bis er gleich laut wirkt. Lange und helle Sounds wirken fast immer lauter, als die Messung sagt. Orange Zahl = geschätzte Korrektur, noch nicht gehört.
- „Behalten“ für brauchbare Sounds, „Raus“ für kratzige, grelle, verrauschte, mit Stimmen oder Musik drin. Raus heißt: der Mix nimmt ihn nie.
- Taste A spielt erst die Referenz, dann den Sound: so lässt sich die Lautstärke am besten vergleichen. Familie kann direkt in das Feld.

Nicht alle 500 auf einmal. Gute Portionen: `--quelle mixkit`, `--familie plopp`, `--ids "kenney/impact-*"`, oder genau die Sounds, die der letzte Mix als „ohne Urteil“ meldet.

**5. Familien anlegen.** Familien bringen Abwechslung: der Mix wechselt reihum die Variante, nie zweimal dieselbe hintereinander.
```
__HEIM__/ms sound familie plopp  "mixkit/*pop*" "kenney/drop-00*" "kenney/pluck-*"  --einsatz "etwas erscheint"
__HEIM__/ms sound familie whoosh "mixkit/*whoosh*" "kenney/card-slide-*"            --einsatz "Bewegung, Szenenwechsel"
__HEIM__/ms sound familie klick  "kenney/click-*"                                   --einsatz "Klick, Schalter, Fokus"
__HEIM__/ms sound familie landen "kenney/impact-wood-medium-*" "kenney/impact-soft-medium-*" --einsatz "etwas landet dumpf"
__HEIM__/ms sound familie                                                           # alle Familien zeigen
```
Ein Muster ohne Treffer (z. B. `mixkit/*whoosh*`, solange nichts von Mixkit geladen ist) wird mit WARNUNG übersprungen, die anderen Muster zählen. Trifft kein Muster, wird die Familie nicht angelegt.

**Nur Kenney (ohne Mixkit):** Kenney hat keinen echten Whoosh. Ersatz, im Katalog geprüft (Stand der 7 Kenney-Packs):
| Familie | Kenney-Muster | Varianten | Charakter |
|---|---|---|---|
| `@whoosh` | `kenney/card-slide-*` | 8 (0,46 bis 0,67 s) | Karte wischt über den Tisch, weicher Wisch |
| `@whoosh` (härter) | `kenney/card-shove-*` | 4 (0,7 bis 0,8 s) | kräftiger Schub |
| `@plopp` | `kenney/drop-00*` + `kenney/pluck-*` | 4 + 2 (0,1 bis 0,3 s) | kurzer, weicher Tropfen/Zupfer |
| `@klick` | `kenney/click-*` | 3 | Klick |
| `@landen` | `kenney/impact-wood-medium-*`, `kenney/impact-soft-medium-*` | 5 + 5 | dumpfer Aufprall |
Danach abhören (`ms sound abhoeren --familie whoosh --server`): Ersatz klingt anders als ein Luft-Whoosh. Passt er nicht zum Kanal, einen einzelnen Mixkit-Whoosh laden und zur Familie geben.
Pro Familie 3 bis 10 Varianten mit ähnlicher Länge und ähnlichem Charakter. Danach `ms sound abhoeren --familie <name>` und gegenhören: eine Variante, die heraussticht, mit `--entfernen` rausnehmen.
Weitere Familien je Kanal nach Bedarf (`papier`, `glanz`, `fehler`, `erfolg`, `schlag`). Ein Sound gehört zu höchstens einer Familie.

**6. Art setzen (für die Warnungen im Mix).**
`__HEIM__/ms sound setzen <ids|muster> --art allzweck|motiv|nische|hook`
- allzweck: darf öfter vorkommen (besser über Familie). motiv: gleiche Aktion bekommt immer diesen Sound (wiedererkennbar). nische: nur für genau eine Sache (Glas zerspringt). hook: für den ersten Treffer.

**Gate Einrichten:** `__HEIM__/ms check --stufe sound` meldet ok (mindestens 500 Sounds). `__HEIM__/ms sound familie` zeigt `@plopp`, `@klick`, `@landen` mit je 3 oder mehr Varianten und `@whoosh` mit 3 oder mehr Varianten aus dem Kenney-Ersatz (`kenney/card-slide-*`) ODER mit mindestens einem Mixkit-Whoosh (ein einzelner reicht, Ersatz dazu für die Abwechslung). Alle Familien-Mitglieder abgehört. `ms check` prüft die Familien nicht, nur die Anzahl der Sounds.

## Pflege im Betrieb

**Suchen:** `__HEIM__/ms sound suche "glas klirrt" --n 10` (deutsch oder englisch; englische Fachwörter treffen besser: click, pop, whoosh, impact, chime). Mit KI: Textsuche plus CLAP-Ähnlichkeit, Spalte „hört“ zeigt die AST-Klasse.
**Ansehen:** `ms sound info <id>`, `ms sound liste --urteil offen --n 50`, `ms sound liste --familie whoosh`.
**Ausschnitt:** Ist nur ein Teil eines langen Sounds brauchbar: `ms sound setzen <id> --von 0.2 --bis 0.9`.
**Unter Sprache leiser:** Schleift oder rauscht ein Sound unter laufender Rede: `ms sound setzen <id> --unter-stimme -3` (wirkt nur, solange gesprochen wird).

**Sperren:** Sagt der Nutzer zu einem fertigen Video „der Sound nervt“ oder „der muss raus“:
`__HEIM__/ms sound sperren <id> --grund "<Zitat und Folge>"`. Jeder Mix mit diesem Sound bricht danach ab. Entsperren nur auf seine Ansage: `--weg`.
Unterschied: `urteil raus` kommt von der Abhörseite (Sound unbrauchbar), `gesperrt` ist ein ausdrückliches Verbot nach einem echten Video.

## Fehlt ein Sound? (in dieser Reihenfolge)
1. `ms sound suche` mit zwei, drei Wörtern auf Deutsch und Englisch. Familien prüfen (`ms sound familie`).
2. Mixkit einzeln (`ms sound laden mixkit <nummer> --ja`), dann Kenney-Packs nochmal durchsuchen (Tags).
3. Von Hand: Sonniss-Ordner, Pixabay einzeln, Freesound nur CC0. Dateien in einen Ordner, dann
   `__HEIM__/ms sound einlesen <ordner> --quelle <name> --lizenz "<Lizenztext>" [--verlinken]`.
4. KI erst zuletzt, mit Kostenansage: ElevenLabs Sound Effects, Stable Audio Open lokal, Higgsfield (nur Impacts, Booms, Schläge).
   Ergebnis einlesen mit `--quelle ki-<anbieter>`.
5. Neu Eingelesenes immer abhören lassen (`ms sound abhoeren --neu --server`), bevor es in einen fertigen Mix geht. Bis dahin schätzt der Mix die Korrektur.

## Befehle
| Befehl | Wofür |
|---|---|
| `ms sound laden kenney [--ja]` | 7 CC0-Packs |
| `ms sound laden mixkit <nr> [--name] [--ja]` | ein Mixkit-Sound |
| `ms sound einlesen <ordner\|datei> --quelle q --lizenz "…"` | eigene Funde übernehmen (kopiert, `--verlinken` verlinkt) |
| `ms sound ki [--neu]` | AST-Klassen und CLAP-Vektoren nachrüsten |
| `ms sound suche "…"` | finden |
| `ms sound abhoeren [--neu] [--server]` | Urteil und Pegel nach Gehör |
| `ms sound urteile <export.json>` | Export der Seite übernehmen |
| `ms sound familie [<name> <ids…>]` | Familien |
| `ms sound setzen <ids…> …` | Art, Ausschnitt, Tags, Notiz, Urteil auf Ansage |
| `ms sound sperren <ids…> --grund "…"` | Verbot |
| `ms sound gegenprobe <folge>` | Maschine hört den fertigen Effekt-Bus an (Skill motion-ton-mix) |

## Fallen
- Abhörseite und `ms sound …` gleichzeitig: Der Server schreibt jedes Urteil sofort. Andere Befehle danach ausführen, sonst überschreiben sie sich nicht, aber die Seite zeigt den alten Stand bis zum Neuladen.
- Ein Sound in zwei Familien geht nicht: `familie` verschiebt ihn und sagt das an.
- Gelöscht wird nichts. Unbrauchbares bekommt `urteil raus`, Dateien bleiben liegen.
