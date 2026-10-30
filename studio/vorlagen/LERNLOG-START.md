# Lernlog

Nach jeder Folge und jedem gelernten Kanal schreibt motion-regie hier 3 bis 5 Zeilen dazu: Datum, was gebaut wurde,
was geklappt hat, was nicht (mit Ursache), Messwerte, Kosten, Dauer. Neueste Einträge unten.
Motion-Studio liest beim Start nur Startwissen, Lehren und die letzten Einträge (`ms lernlog --kurz`). Du kannst selbst Zeilen
ergänzen, zum Beispiel dein Urteil zu einer Folge. Ältere Einträge wandern mit `ms lernlog archivieren` nach LERNLOG-ARCHIV.md.

## Startwissen (aus dem Bau von Motion-Studio, gilt bis eigene Erfahrung es ersetzt)
- 2D-Nachbau (Collage, Typo, UI) in HyperFrames: im Pilot wurden ΔE 5,2 und SSIM 0,84 erreicht. Realistisches Ziel für 2D.
- 3D-Nachbau in Three.js: ΔE 16 bei Ziel 15, knapp verfehlt. Licht, Materialien und Kamerawinkel sind die größten Hebel.
- Figuren-Animation auf Profi-Niveau ist nicht belegt. Szene, Licht und Kamera klappen. Figuren, Rig und Schauspiel sind der Engpass.
- Blender headless mit EEVEE: in der Beispielszene 1,5 bis 1,9 s pro Bild (1080×1920, Apple M3 Pro, Rechner nebenbei ausgelastet), ein 20-s-Reel also 15 bis 19 Minuten. Dichtere Szenen (mehr Lichter, Glas, Figuren) dauern länger, wie viel ist nicht gemessen: am ersten Entwurf selbst messen und hier eintragen. Cycles ist für Serien zu langsam.
- Jede Aussage im Skript bekommt eine eigene sichtbare Aktion genau auf dem Wort. Pro Szene mindestens ein Wow-Moment.
- Ton: Pegel nach Gehör prüfen, nicht nur messen. Helle, lange Sounds wirken lauter als gemessen. Ein tiefer Boom braucht einen Impact in den Mitten, sonst hört man ihn am Handy nicht. Gleiche Aktion bekommt dieselbe Sound-Familie, Varianten reihum. Keine im Code erzeugten Sounds.
- Prüfen heißt ansehen: Jeder Kontaktbogen wird einmal angesehen (der Prüfer alle, die Regie die Übersicht und die Stellen mit Befund), bevor der Nutzer das Video sieht. Er soll keinen Fehler als Erster finden.
- Eine Änderung pro Runde. Nach drei Fehlversuchen an derselben Szene den Nutzer fragen statt weiter zu raten.
- Nie ein ganzes Video roh in den Arbeitsspeicher laden. Frames immer streamen.

## Lehren
(Eine Zeile je Lehre, die für jede Folge gilt. Kurz halten, sie wird bei jedem Start gelesen.)

## Einträge
