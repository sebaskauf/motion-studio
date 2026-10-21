# Sound-Quellen für die Bibliothek

Stand 20.10.2026, alle Links an diesem Tag geprüft. Lizenzen ändern sich: Vor dem ersten Laden die Lizenzseite einmal selbst öffnen.
Die Bibliothek liegt in `<Arbeitsordner>/sounds/` (Dateien unter `files/<quelle>/`, Katalog `katalog.json`). Gepflegt wird sie nur mit `ms sound …` (Skill motion-sound-bibliothek). `ms` ist der Einstieg im Studio-Ordner (`~/.claude/motion-studio/ms`).

## Grundregeln

- **Lokal zuerst.** Jeder Sound kommt aus der eigenen Bibliothek. Externe Quellen nur für echte Lücken, gute Funde werden eingelesen und bleiben.
- **Nur Lizenzen, die kommerzielle Nutzung in Social-Media-Videos ohne Pflicht-Nennung erlauben.** Unklar = nicht nehmen.
- **Keine Massen-Downloads** von Seiten, die das verbieten (Pixabay, Mixkit, Zapsplat). Einzelne Sounds von Hand oder per `ms sound laden mixkit <nummer>`.
- **Keine Sounds aus Code erzeugen** (Sinus, Rauschen, Hüllkurven). Das klingt billig und fällt sofort auf.
- Lizenztext und Herkunft stehen pro Sound im Katalog (`lizenz`, `quelle`). Beim Einlesen immer `--lizenz` angeben.

## Einrichten in dieser Reihenfolge

| Nr. | Quelle | Link | Lizenz | Laden | Hinweis |
|---|---|---|---|---|---|
| 1 | Kenney, 7 Audio-Packs | https://kenney.nl/assets/category:Audio | CC0 1.0, kommerziell, ohne Nennung | `ms sound laden kenney --ja` | 10,8 MB, rund 520 Sounds. Klicks, Impacts, UI, Sci-Fi, Karten, Münzen. Kaum Whooshes und Plopps |
| 2 | Mixkit | https://mixkit.co/free-sound-effects/ | Mixkit Sound Effects Free License, kommerziell, ohne Nennung | `ms sound laden mixkit <nummer> --name "…" --ja` | einzeln, ohne Konto, keine API. Gut für Whoosh, Pop, Übergänge, Benachrichtigungen |
| 3 | Sonniss GDC Game Audio Bundle 2026 | https://gdc.sonniss.com | frei, kommerziell, ohne Nennung | von Hand (Browser oder Torrent), dann `ms sound einlesen` | 7,47 GB Profi-Aufnahmen. Laut Lizenz kein KI-Training. Nur die Ordner einlesen, die du brauchst |
| 4 | Pixabay | https://pixabay.com/sound-effects/ | Pixabay Content License, ohne Nennung | nur einzeln von Hand, dann `ms sound einlesen` | Die Pixabay-API kennt kein Audio, Massen-Download ist verboten. Musik: Content-ID-Risiko (siehe unten) |
| 5 | Freesound | https://freesound.org | pro Sound verschieden, **nur CC0 nehmen** | von Hand (Konto nötig), dann `ms sound einlesen` | API-Schlüssel: https://freesound.org/apiv2/apply. Mit dem Schlüssel gibt es nur Suche und Vorschau-Dateien, Originale erst mit OAuth-Login. Kommerzielle API-Nutzung nur nach Absprache mit Freesound |
| 6 | KI für Lücken | siehe unten | je Anbieter | Datei erzeugen, dann `ms sound einlesen` | nur, wenn 1 bis 5 nichts Passendes haben |

### 1. Kenney (Pflicht, gratis)

Die sieben Packs: impact-sounds, interface-sounds, sci-fi-sounds, digital-audio, ui-audio, rpg-audio, casino-audio.
Einzelseiten: `https://kenney.nl/assets/<pack>`. Lizenz: https://creativecommons.org/publicdomain/zero/1.0/
```
ms sound laden kenney          # zeigt Links und Größe, lädt nichts
ms sound laden kenney --ja     # lädt, entpackt nach sounds/files/kenney/<pack>/, liest ein
```
Findet das Werkzeug einen Download-Link nicht mehr (Kenney hat die Seite umgebaut): Zip im Browser laden, entpacken, `ms sound einlesen <ordner> --quelle kenney --lizenz "CC0 1.0"`.

### 2. Mixkit (gratis, einzeln)

Kategorien: `https://mixkit.co/free-sound-effects/<kategorie>/`, zum Beispiel `whoosh`, `pop`, `click`, `transition`, `notification`, `swoosh`, `game`.
Lizenz: https://mixkit.co/license/#sfxFree (kommerziell und privat frei, ohne Nennung, nicht als eigene Sound-Sammlung weitergeben oder verkaufen).
Die Nummer eines Sounds steht in der Adresse seiner Vorschau: `assets.mixkit.co/active_storage/sfx/<nummer>/<nummer>-preview.mp3`.
```
ms sound laden mixkit 1489 --name "whoosh luft"          # Größe ansagen
ms sound laden mixkit 1489 --name "whoosh luft" --ja     # laden + einlesen
```
Achtung: Auf den Listenseiten steht der Titel nicht immer beim richtigen Sound. Nach dem Laden anhören (Abhörseite) oder `ms sound info <id>` (KI-Klasse).

### 3. Sonniss GDC Bundle (gratis, groß)

Jedes Jahr zur GDC frei, 2026: über 7,47 GB von 17 Herstellern, lizenzfrei für kommerzielle Projekte, ohne Nennung. Download im Browser oder per Torrent.
Nicht alles einlesen: Ordner mit Whooshes, Impacts, UI, Foley auswählen und je Ordner `ms sound einlesen <ordner> --quelle sonniss --lizenz "Sonniss GDC 2026, lizenzfrei, ohne Nennung" --verlinken` (verlinken spart Platz).
Lange Atmos (über 10 s) sind für Motion-Reels selten nützlich.

### 4. Pixabay (gratis, nur von Hand)

Lizenz-Zusammenfassung: https://pixabay.com/service/license-summary/ (frei nutzbar, ohne Nennung, nicht unverändert als eigene Datei verkaufen).
Massen-Downloads und Scraping sind verboten, die API liefert kein Audio. Also: einzelne Sounds im Browser laden, in einen Ordner legen, einlesen.

### 5. Freesound (gratis, nur CC0)

Konto anlegen, beim Suchen links nach Lizenz „Creative Commons 0“ filtern. CC-BY verlangt Namensnennung, CC-BY-NC verbietet kommerzielle Nutzung: beides nicht nehmen.
Der API-Schlüssel (https://freesound.org/apiv2/apply, kommt in `<Arbeitsordner>/.env` als `FREESOUND_API_KEY`) erlaubt Suche und Vorschau-Dateien. Für die Bibliothek die Originale von Hand laden.

### 6. KI für echte Lücken (kostet)

| Werkzeug | Link | Lizenz und Kosten | Wofür |
|---|---|---|---|
| ElevenLabs Sound Effects | https://elevenlabs.io/sound-effects | kommerziell ab Starter-Plan (6 USD/Monat, https://elevenlabs.io/pricing), kostet Credits pro Erzeugung | kurze, beschreibbare Effekte |
| Stable Audio Open 1.0 (lokal) | https://huggingface.co/stabilityai/stable-audio-open-1.0 | Stability AI Community License: kommerziell frei bis 1 Mio. USD Jahresumsatz (https://stability.ai/license). Modell erst nach Annahme der Lizenz auf Hugging Face | bis 47 s, läuft lokal, langsam ohne starke Grafikkarte |
| Higgsfield (Mirelo) | über den Higgsfield-MCP im Agenten | Credits je Auftrag | **nur Impacts, Booms, Schläge**. Kleine UI- und Papier-Sounds kamen in unseren Tests stumm oder falsch zurück |

Ablauf: Kosten nennen, Ja holen, erzeugen, Datei speichern, `ms sound einlesen <datei> --quelle ki-<anbieter> --lizenz "<Lizenz laut Plan>"`, anhören, Anschlag prüfen (`ms sound info <id>`, Feld `anschlag`).

## Nicht nehmen

| Quelle | Warum |
|---|---|
| BBC Sound Effects (sound-effects.bbcrewind.co.uk) | RemArc-Lizenz nur für private, Bildungs- und Forschungszwecke. Kommerzielle Nutzung, also auch ein Kanal mit Werbung oder Kunden, braucht eine kostenpflichtige Lizenz |
| Zapsplat gratis | kostenlose Stufe nur mit Pflicht-Nennung, automatisches Laden nicht erlaubt |
| Sounds aus fremden Videos oder Reels | nicht deine Rechte, auch nicht „nur kurz“ |

## Musik

- **Content-ID:** Freie Musik von Pixabay und ähnlichen Seiten ist teils von Dritten in Content-ID-Systemen registriert. Folge: Anspruch auf dein Video, Monetarisierung weg oder Sperre. Musik deshalb nur mit Lizenz, die Social Media ausdrücklich erlaubt, oder selbst erstellt.
- **Am sichersten:** Musik beim Posten in der App wählen (Instagram, TikTok) und im Mix `ms mix <folge> --musik aus`.
- Musikbett im Mix: `ms mix <folge> --musik <datei>` legt es leise unter die Stimme (Standard 20 dB darunter) und duckt es, solange gesprochen wird.
- Viele Motion-Kanäle laufen ganz ohne Musik. Was das Vorbild macht, steht in der BIBEL (Analyse „Musik ja/nein“).

## Unsere Lehren

1. **Pegel nach Gehör, nicht nur nach Messung.** Sounds mit gleicher gemessener Lautheit wirken unterschiedlich laut. Lange und helle Sounds (viel Energie über 8 kHz) wirken lauter. Deshalb hat jeder Sound eine Korrektur `trim_db`, die du auf der Abhörseite festlegst. Ohne Urteil schätzt der Mix sie.
2. **Effekte gehören unter die Stimme.** Der Mix hält den Effekt-Bus mindestens 10 dB unter der Stimme, solange sie spricht. Ziel im Bericht: Median 12 dB oder mehr darunter.
3. **Familien statt fester Allzweck-Sounds.** Derselbe Plopp zwanzigmal klingt billig. 3 bis 10 Varianten pro Familie (`@plopp`, `@whoosh`, `@klick`, `@landen`), der Mix wechselt reihum.
4. **Lange, rauschende oder schleifende Sounds in Sprechpausen.** Unter laufender Rede überdecken sie Silben.
5. **Sub-Boom nie allein.** Handylautsprecher geben unter 150 Hz fast nichts wieder. Ein tiefer Boom braucht immer einen Mitten-Impact dazu.
6. **Keine Code-Synthese.** Lieber eine Lücke mit einem echten Sound aus Quelle 2 bis 6 füllen.
7. **Gegenprobe im fertigen Mix.** Die Maschine hört kurze Fenster des Effekt-Busses an (`ms sound gegenprobe <folge>`). So fielen auf: ein Klebeband, das wie eine Taube klang, und ein Applaus mit Stimmen, der mit der Sprecherstimme konkurrierte.
8. **Gute Funde bleiben.** Was du für eine Folge holst, wird eingelesen, abgehört und steht der nächsten Folge zur Verfügung.
