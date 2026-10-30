---
name: motion-ideen
description: "Ideenliste eines Motion-Studio-Kanals (kanaele/<k>/IDEEN.md): eigene Ideen des Nutzers eintragen, aus seiner Herangehensweise und den Top-Videos des Vorbilds ein Schema schreiben, nach dem das System selbst Ideen findet, Liste auf 10 bis 20 auffüllen, knappe Liste nachfüllen. Eigene Ideen kommen immer zuerst. Laden bei \"Ideenliste\", \"Ideen für die nächsten Folgen\", \"Themen\", \"Serie\", \"Sprachnotiz mit Ideen\", \"Liste wird knapp\", \"Schema\"."
---

# motion-ideen

Die Ideenliste bestimmt, worüber die eigenen Folgen sind. Der Autopilot und motion-folge nehmen immer die oberste offene Idee:
zuerst die eigenen (`eigen`), dann die vom System (`system`). Das Vorbild liefert nie den Inhalt, nur Form, Länge und Tempo.

## Werkzeug
`__HEIM__/ms ideen <k>` (Liste, knapp ja/nein) · `… naechste` · `… neu "<Idee>" [--eigen] [--notiz "<warum>"] [--oben]` · `… nutzen "<Idee>" --folge <id>` (macht `ms neu folge --idee` selbst).
Datei: `__ARBEIT__/kanaele/<k>/IDEEN.md`, eine Idee pro Zeile `- [ ] eigen | Idee | Notiz`. Der Nutzer darf sie jederzeit selbst ändern.

## 1. Eigene Ideen eintragen
Ideen des Nutzers (auch als Sprachnotiz-Text): jede in einen kurzen Satz bringen, der das Thema UND den Dreh nennt („Warum Akkus im Winter schwächeln, gezeigt am Handy auf der Skipiste“), dann `ms ideen <k> neu "<Idee>" --eigen`. Seine Wortwahl behalten. Doppelte zusammenlegen, nichts weglassen, ohne zu fragen.

## 2. Schema schreiben
Abschnitt `## Schema` in IDEEN.md (Edit-Tool), höchstens 12 Zeilen:
- Herangehensweise des Nutzers (seine Regeln, was ein gutes Thema für ihn ausmacht), wörtlich, wenn er sie genannt hat.
- Was bei den Top-Videos des Vorbilds funktioniert (aus SKRIPT-BAUKASTEN.md und den Views im Register, `ms vorlagen liste --creator <vorbild>`): Themenfelder, Muster der Hooks, Serien.
- Nische, Zielgruppe und Twist aus PROFIL.md.
- Prüffragen für eine neue Idee: Kennt die Zielgruppe das Ding aus dem Alltag? Gibt es eine überraschende Ursache? Lässt es sich in 30 bis 45 s mit einer klaren Bildidee zeigen? Hat das Vorbild es schon gemacht (dann nur mit eigenem Dreh)?
Dem Nutzer zeigen, er ergänzt oder ändert. Seine Änderung gilt.

## 3. Auffüllen auf 10 bis 20
Nach dem Schema neue Ideen finden, jede mit einem Satz Begründung (`--notiz`). Quellen mit Datum nennen, wenn du recherchierst. Keine Themen, die schon als Folge existieren (`ms status --alle`). Eintragen mit `ms ideen <k> neu "<Idee>" --notiz "<Begründung>"` (ohne `--eigen`). Dem Nutzer die Liste zeigen, er streicht oder ergänzt.

## 4. Knappe Liste
`ms ideen <k>` meldet KNAPP unter 3 offenen Ideen, das Studio zeigt dann einen Hinweis. Die nächste Bau-Sitzung (motion-folge Schritt 1) füllt vor der Themenwahl nach dem Schema auf 10 auf. Ohne Schema: nach Nische und Top-Videos des Vorbilds auffüllen und im Studio fragen, ob das Schema so passt (`ms status kanal:<k> --wartet "…"`), aber nicht warten, um weiterzubauen.

## Fallen
- Eine Idee ist kein Video des Vorbilds. „Wie ein Touchscreen funktioniert“ beim Vorbild heißt für den Nutzer höchstens „dasselbe Thema mit eigenem Dreh“, nie dieselbe Geschichte.
- Idee zu breit („KI erklärt“): auf eine Frage zuspitzen, die eine Folge beantwortet.
