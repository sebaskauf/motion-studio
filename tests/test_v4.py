"""Offline-Tests für den Stand v4 (30.10.2026): Tagesbau, Modelle, MCP, Wochenbremse, Vorrat, Posten, Ideen, Stil-Skill,
Lernlog, Verbrauch, Warten, Studio. Startet nie eine Claude-Sitzung und legt keine tmux-Sitzung an.
  python3 -m unittest discover -s tests -v        (im Repo-Ordner)"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / 'studio' / 'tools'
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO / 'studio' / 'dashboard'))


def schreibe(p: Path, daten) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(daten, ensure_ascii=False) if not isinstance(daten, str) else daten, encoding='utf-8')
    return p


class Basis(unittest.TestCase):
    """Eigener Arbeitsordner und Claude-Ordner je Test, Module frisch geladen."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='ms-v4-'))
        self.arbeit = self.tmp / 'arbeit'
        self.cfg = self.tmp / 'cfg'
        (self.arbeit / 'kanaele').mkdir(parents=True)
        (self.arbeit / 'folgen').mkdir(parents=True)
        self.cfg.mkdir()
        self.env_alt = {k: os.environ.get(k) for k in ('MS_ARBEIT', 'CLAUDE_CONFIG_DIR', 'MS_SITZUNG', 'MS_KEINE_FENSTER')}
        os.environ.update(MS_ARBEIT=str(self.arbeit), CLAUDE_CONFIG_DIR=str(self.cfg), MS_KEINE_FENSTER='1')
        os.environ.pop('MS_SITZUNG', None)
        for m in ('_ms', '_konfig', '_vorrat', '_verbrauch', 'starten', 'autopilot', 'posten', 'ideen', 'stil', 'lernlog', 'verbrauch'):
            if m in sys.modules:
                importlib.reload(sys.modules[m])
        import starten
        starten._tmux = lambda: None          # nie tmux anfassen
        starten.liste = lambda muster=None: []

    def tearDown(self):
        for k, v in self.env_alt.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    # Bausteine
    def kanal(self, slug='k1', phase='bereit', pilot=None):
        d = self.arbeit / 'kanaele' / slug
        schreibe(d / 'STATUS.json', {'id': slug, 'art': 'kanal', 'titel': slug, 'vorbild': '@vorbild', 'phase': phase,
                                     'phasen': {}, 'pilot': pilot, 'messwerte': {'delta_e': 4.8, 'ssim': 0.73}})
        return d

    def folge(self, fid, kanal='k1', art='folge', phase='fertig', quelle='eigen', upload=True, erstellt='2026-10-30T10:00:00+01:00', **felder):
        d = self.arbeit / 'folgen' / fid
        st = {'id': fid, 'art': art, 'titel': fid, 'kanal': kanal, 'phase': phase, 'phasen': {}, 'kosten': [], 'erstellt': erstellt}
        if quelle:
            st['quelle'] = quelle
        st.update(felder)
        schreibe(d / 'STATUS.json', st)
        if upload:
            schreibe(d / 'upload' / f'{fid}.mp4', 'video')
            schreibe(d / 'upload' / 'CAPTION.md', 'Hook. Nutzen. #tag')
        return d

    def profil(self, plattformen='Instagram Reels, TikTok'):
        schreibe(self.arbeit / 'PROFIL.md', f'# Profil\n\n## Kanal und Inhalt\n- Plattformen: {plattformen}\n')


class KonfigTest(Basis):
    def test_standard_und_abo(self):
        import _konfig
        c = _konfig.konfig()
        self.assertEqual(c['pro_tag'], 1)
        self.assertEqual(c['modell'], 'sonnet')
        self.assertEqual(c['modell_planung'], 'opus')
        self.assertEqual(c['modell_regie'], 'opusplan')
        c = _konfig.abo_setzen(c, 'max20')
        self.assertEqual((c['pro_tag'], c['parallel'], c['wochen_bremse']), (3, 2, 70))
        with self.assertRaises(SystemExit):
            _konfig.abo_setzen(c, 'team')

    def test_alte_modell_ids(self):
        import _konfig
        schreibe(self.arbeit / 'autopilot.json', {'modell': 'claude-sonnet-5-5', 'pro_tag': 5})
        c = _konfig.konfig()
        self.assertEqual(c['modell'], 'sonnet')
        self.assertEqual(c['pro_tag'], 5)    # Einstellung des Nutzers bleibt

    def test_sitzung_optionen(self):
        import _konfig
        c = _konfig.konfig()
        a = _konfig.sitzung_optionen('autobau', c)
        self.assertEqual((a['modell'], a['mcp'], a['bypass'], a['chrome']), ('opus', [], True, False))
        self.assertEqual(_konfig.sitzung_optionen('autobau-b', c)['modell'], 'sonnet')
        p = _konfig.sitzung_optionen('autopost', c)   # 31.10.: Autopilot-Posten lief vorher ohne Chrome, Bypass und schlanke MCPs
        self.assertEqual((p['chrome'], p['bypass'], p['mcp'], p['modell']), (True, True, [], 'sonnet'))
        for art in ('posten', 'posten-einrichten', 'autopost'):
            self.assertTrue(_konfig.sitzung_optionen(art, c)['chrome'], art)
            self.assertEqual(_konfig.sitzung_optionen(art, c)['mcp'], [], art)
        self.assertEqual(_konfig.sitzung_optionen('folge', c)['modell'], 'opusplan')
        self.assertIsNone(_konfig.sitzung_optionen('einrichten', c)['mcp'])
        c['mcp_stimme'] = ['voicestudio']
        self.assertEqual(_konfig.sitzung_optionen('autobau', c)['mcp'], ['voicestudio'])
        self.assertEqual(_konfig.sitzung_optionen('autobau-b', c)['mcp'], [])
        c['mcp_stimme'] = 'alle'
        self.assertIsNone(_konfig.sitzung_optionen('autobau', c)['mcp'])
        c['staffel'] = False
        self.assertEqual(_konfig.sitzung_optionen('autobau', {**c, 'mcp_stimme': []})['modell'], 'sonnet')
        self.assertTrue(p['bypass'])

    def test_mcp_ohne_zugangsdaten(self):
        import _konfig
        schreibe(self.cfg / '.claude.json', {'mcpServers': {
            'voicestudio': {'type': 'http', 'url': 'http://localhost:3900/mcp/'},
            'geheim': {'command': 'x', 'env': {'TOKEN': 'abc'}}}})
        server, fehlt = _konfig.mcp_server(['voicestudio', 'geheim', 'gibtsnicht'])
        self.assertEqual(list(server), ['voicestudio'])
        self.assertEqual(fehlt, ['geheim', 'gibtsnicht'])


class StartenTest(Basis):
    def test_befehl_schlank(self):
        import starten
        cmd = starten.claude_befehl('Auftrag', modell='opus', denkstufe='high', ohne_gedaechtnis=True, bypass=True,
                                    mcp=['voicestudio'], chrome=True)
        self.assertEqual(cmd[-3:], ['--agent', 'motion-regie', 'Auftrag'])
        self.assertIn('--strict-mcp-config', cmd)
        cfg = json.loads(cmd[cmd.index('--mcp-config') + 1])
        self.assertEqual(cfg['mcpServers']['voicestudio']['url'], 'http://localhost:3900/mcp/')
        self.assertIn('--chrome', cmd)
        self.assertEqual(cmd[cmd.index('--settings') + 1], '{"autoMemoryEnabled":false}')
        leer = starten.claude_befehl('A', mcp=[])
        self.assertEqual(json.loads(leer[leer.index('--mcp-config') + 1]), {'mcpServers': {}})
        self.assertNotIn('--strict-mcp-config', starten.claude_befehl('A', mcp=None))

    def test_auftraege(self):
        import starten
        self.kanal()
        self.folge('2026-10-30-eins')
        self.assertIn('Stufe A', starten.auftrag_text('autobau', kanal='k1'))
        self.assertIn('Stufe B für Folge 2026-10-30-eins', starten.auftrag_text('autobau-b', folge='2026-10-30-eins'))
        self.assertIn('vor „Veröffentlichen“', starten.auftrag_text('posten-einrichten', kanal='k1'))
        self.assertIn('Autopilot-Posten', starten.auftrag_text('autopost', folge='2026-10-30-eins'))
        erg = starten.starten('posten', folge='2026-10-30-eins', trocken=True)
        self.assertIn('--chrome', erg['befehl'])
        erg = starten.starten('autopost', folge='2026-10-30-eins', trocken=True)
        for teil in ('--chrome', '--strict-mcp-config', 'bypassPermissions'):
            self.assertIn(teil, erg['befehl'])
        self.assertIn('MS_ARBEIT', erg['umgebung'])


class VorratTest(Basis):
    def test_nur_eigene_folgen(self):
        import _vorrat
        self.profil()
        self.kanal()
        self.folge('2026-10-30-eigen')
        self.folge('2026-10-30-pilot', art='pilot', quelle=None)
        self.folge('2026-10-30-kopie', art='kopie', quelle=None)
        self.folge('2026-10-29-alt', quelle=None)                          # alte Folge ohne quelle
        self.folge('2026-10-30-roh', phase='szenen')
        self.folge('2026-10-30-fremd', kanal='k2')
        self.assertEqual([v['folge_id'] for v in _vorrat.vorrat('k1')], ['2026-10-30-eigen'])
        self.assertEqual(_vorrat.ungepostet('k1'), 1)
        v = _vorrat.vorrat('k1')[0]
        self.assertTrue(v['postbar'])
        self.assertEqual(v['offen'], ['instagram', 'tiktok'])
        self.assertIn('nie gepostet', _vorrat.eintrag(_vorrat._ms.status_lesen(self.arbeit / 'folgen/2026-10-30-pilot'))['grund'])

    def test_pruefung_nicht_bestanden(self):
        import _vorrat
        self.profil()
        self.kanal()
        d = self.folge('2026-10-30-eigen')
        schreibe(d / 'PRUEFBERICHT.md', '# Prüfbericht\n\n**Gesamturteil: nicht abnahmefähig**\n')
        self.assertEqual(_vorrat.vorrat('k1')[0]['grund'], 'Prüfung nicht bestanden')


class PostenTest(Basis):
    def test_ergebnis_und_fehler(self):
        import _vorrat
        import posten
        self.profil('Instagram, TikTok')
        self.kanal()
        self.folge('2026-10-30-eigen')
        e = posten.ergebnis('2026-10-30-eigen', 'instagram', 'https://www.instagram.com/reel/abc/', None)
        self.assertEqual(e['offen'], ['tiktok'])
        e = posten.ergebnis('2026-10-30-eigen', 'tiktok', None, 'Upload hing bei 0 %')
        self.assertFalse(e['ok'])
        st = _vorrat._ms.status_lesen(self.arbeit / 'folgen/2026-10-30-eigen')
        self.assertTrue(st['fehler'].startswith('Posten auf TikTok fehlgeschlagen'))
        self.assertFalse(_vorrat.vorrat('k1')[0]['postbar'])
        posten.erledigt('2026-10-30-eigen')
        st = _vorrat._ms.status_lesen(self.arbeit / 'folgen/2026-10-30-eigen')
        self.assertNotIn('fehler', st)
        self.assertTrue(_vorrat.vorrat('k1')[0]['postbar'])
        e = posten.ergebnis('2026-10-30-eigen', 'tiktok', 'https://www.tiktok.com/@x/video/1', None)
        st = _vorrat._ms.status_lesen(self.arbeit / 'folgen/2026-10-30-eigen')
        self.assertEqual(st['phase'], 'gepostet')
        self.assertEqual(_vorrat.vorrat('k1'), [])

    def test_freigabe_braucht_ablauf(self):
        import _vorrat
        import posten
        d = self.kanal()
        with self.assertRaises(SystemExit):
            posten.freigabe('k1', 'instagram', 'ja passt')
        schreibe(d / 'posten' / 'instagram.md', '# Ablauf Instagram\n')
        with self.assertRaises(SystemExit):
            posten.freigabe('k1', 'instagram', '')           # ohne Zitat keine Freigabe
        posten.freigabe('k1', 'instagram', 'ja passt so')
        self.assertEqual(list(_vorrat.freigaben('k1')), ['instagram'])
        posten.freigabe('k1', 'instagram', None, zurueck=True)
        self.assertEqual(_vorrat.freigaben('k1'), {})

    def test_pruefen_pilot_nie(self):
        import posten
        self.kanal()
        self.folge('2026-10-30-pilot', art='pilot', quelle=None)
        self.assertFalse(posten.pruefen('2026-10-30-pilot')['postbar'])
        r = subprocess.run([sys.executable, str(TOOLS / 'posten.py'), 'pruefen', '2026-10-30-pilot'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


class StueckeTest(Basis):
    """Upload in voller Qualität über Stücke (Methode vom 18.10.2026, Sebastian 31.10.)."""

    def video(self, fid):
        d = self.folge(fid, upload=False)
        (d / 'upload').mkdir(parents=True, exist_ok=True)
        if not shutil.which('ffmpeg'):
            self.skipTest('ffmpeg fehlt')
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=720x1280:rate=30:duration=2',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2', '-c:v', 'libx264', '-b:v', '4M', '-c:a', 'aac',
                        '-shortest', str(d / 'upload' / f'{fid}.mp4')], check=True)
        return d

    def test_stuecke_und_wiederverwenden(self):
        import posten
        posten.STUECK_BYTES = 200_000
        d = self.video('2026-10-31-eigen')
        e = posten.datei('2026-10-31-eigen')
        self.assertTrue(e['neu'])
        self.assertGreater(e['anzahl'], 2)
        roh = b''.join(Path(x['pfad']).read_bytes() for x in e['stuecke'])
        self.assertEqual(roh, (d / 'upload' / 'post.mp4').read_bytes())
        self.assertTrue(all(x['groesse'] <= 200_000 for x in e['stuecke']))
        self.assertEqual(e['name'], '2026-10-31-eigen.mp4')
        self.assertFalse(posten.datei('2026-10-31-eigen')['neu'])   # zweiter Aufruf nimmt die vorhandenen Stücke
        self.assertGreater(posten._ms.probe(d / 'upload' / 'post.mp4').get('dauer') or 0, 1.5)   # nicht neu kodiert, gleiche Länge

    def test_javascript_im_browser_nachgestellt(self):
        if not shutil.which('node'):
            self.skipTest('node fehlt')
        import posten
        posten.STUECK_BYTES = 150_000
        self.video('2026-10-31-eigen')
        e = posten.datei('2026-10-31-eigen')
        teile = {x['name']: x['pfad'] for x in e['stuecke']}
        schritte = {s: posten.js(s, '2026-10-31-eigen') for s in ('auffangen', 'pruefen', 'einsetzen', 'aufraeumen')}
        stub = r"""
const fs = require('fs');
globalThis.window = globalThis;
class DataTransfer { constructor() { this.l = []; this.items = {add: f => this.l.push(f)}; } get files() { return this.l; } }
globalThis.DataTransfer = DataTransfer;
const felder = [];
function feld(attrs) { const f = {type: 'file', accept: attrs.accept || '', name: attrs.name || '', id: '', multiple: !!attrs.multiple,
  attrs: {...attrs}, files: [], events: [], getAttribute(k) { return this.attrs[k] ?? null; },
  setAttribute(k, v) { this.attrs[k] = v; }, set type(v) {}, get type() { return 'file'; }, style: {},
  addEventListener(t, cb) { this.cb = cb; }, dispatchEvent(ev) { this.events.push(ev.type); }, remove() { felder.splice(felder.indexOf(this), 1); } };
  felder.push(f); return f; }
feld({accept: 'image/*'}); const plattform = feld({accept: 'video/mp4,video/quicktime'});
globalThis.document = {
  createElement: () => feld({}),
  body: {appendChild: () => {}},
  querySelector: sel => sel.includes('CLAUDE CHUNK UPLOAD') ? felder.find(f => f.attrs['aria-label'] === 'CLAUDE CHUNK UPLOAD') || null : null,
  querySelectorAll: sel => sel.includes('CLAUDE CHUNK UPLOAD') ? felder.filter(f => f.attrs['aria-label'] === 'CLAUDE CHUNK UPLOAD') : felder.slice(),
};
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const lauf = code => { const i = code.lastIndexOf('JSON.stringify('); return new AsyncFunction(code.slice(0, i) + 'return ' + code.slice(i))(); };
(async () => {
  const S = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const a = JSON.parse(await lauf(S.js.auffangen));
  const unser = felder.find(f => f.attrs['aria-label'] === 'CLAUDE CHUNK UPLOAD');
  const namen = Object.keys(S.teile).sort();
  // file_upload je Stück: Feld bekommt genau eine Datei, change feuert
  for (const n of namen.slice(0, -1)) { unser.files = [new File([fs.readFileSync(S.teile[n])], n)]; unser.cb(); }
  const p1 = JSON.parse(await lauf(S.js.pruefen));
  const letzte = namen[namen.length - 1];
  unser.files = [new File([fs.readFileSync(S.teile[letzte])], letzte)]; unser.cb();
  const p2 = JSON.parse(await lauf(S.js.pruefen));
  const ein = JSON.parse(await lauf(S.js.einsetzen));
  const buf = Buffer.from(await plattform.files[0].arrayBuffer());
  const r = JSON.parse(await lauf(S.js.aufraeumen));
  console.log(JSON.stringify({a, p1, p2, ein, name: plattform.files[0].name, gleich: buf.equals(fs.readFileSync(S.datei)),
    events: plattform.events, rest: typeof window.claudeChunks, felder_rest: felder.filter(f => f.attrs['aria-label']).length}));
})().catch(e => { console.log(JSON.stringify({fehler: String(e.stack || e)})); });
"""
        f = self.tmp / 'stub.js'
        f.write_text(stub, encoding='utf-8')
        daten = self.tmp / 'daten.json'
        daten.write_text(json.dumps({'js': schritte, 'teile': teile, 'datei': e['datei']}), encoding='utf-8')
        r = subprocess.run(['node', str(f), str(daten)], capture_output=True, text=True, timeout=60)
        aus = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertNotIn('fehler', aus, aus.get('fehler'))
        self.assertTrue(aus['a']['feld'])
        self.assertFalse(aus['p1']['alles_gut'])
        self.assertEqual(len(aus['p1']['fehlt']), 1)
        self.assertTrue(aus['p2']['alles_gut'], aus['p2'])
        self.assertTrue(aus['ein']['eingesetzt'], aus['ein'])
        self.assertTrue(aus['ein']['groesse_ok'])
        self.assertEqual(aus['ein']['feld']['accept'], 'video/mp4,video/quicktime')   # nicht das Bildfeld, nicht unser Feld
        self.assertTrue(aus['gleich'])
        self.assertEqual(aus['name'], '2026-10-31-eigen.mp4')
        self.assertEqual(aus['events'], ['input', 'change'])
        self.assertEqual((aus['rest'], aus['felder_rest']), ('undefined', 0))

    def test_falsches_stueck_wird_erkannt(self):
        if not shutil.which('node'):
            self.skipTest('node fehlt')
        import posten
        posten.STUECK_BYTES = 150_000
        self.video('2026-10-31-eigen')
        posten.datei('2026-10-31-eigen')
        code = posten.js('pruefen', '2026-10-31-eigen')
        stub = ("globalThis.window = globalThis; const fs = require('fs');\n"
                "const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;\n"
                "const code = fs.readFileSync(process.argv[2], 'utf8'); const i = code.lastIndexOf('JSON.stringify(');\n"
                "window.claudeChunks = {}; const soll = JSON.parse(code.split('\\n')[0].slice(13, -1));\n"
                "for (const n of Object.keys(soll)) window.claudeChunks[n] = new File([Buffer.alloc(soll[n][0])], n);\n"
                "new AsyncFunction(code.slice(0, i) + 'return ' + code.slice(i))().then(x => console.log(x));\n")
        f = self.tmp / 'stub2.js'
        f.write_text(stub, encoding='utf-8')
        c = self.tmp / 'code.js'
        c.write_text(code, encoding='utf-8')
        r = subprocess.run(['node', str(f), str(c)], capture_output=True, text=True, timeout=60)
        aus = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertFalse(aus['alles_gut'])
        self.assertEqual(len(aus['falsch']), aus['soll'])


class IdeenTest(Basis):
    def test_eigene_zuerst_und_abhaken(self):
        import ideen
        self.kanal()
        ideen.neu('k1', 'System-Idee eins', eigen=False, notiz='Top-Video')
        ideen.neu('k1', 'Meine Idee', eigen=True)
        d = ideen.lesen('k1')
        self.assertEqual(d['offen'][0]['idee'], 'Meine Idee')
        self.assertTrue(d['knapp'])
        self.assertFalse(d['schema'])
        ideen.nutzen('k1', 'Meine Idee', '2026-10-30-x')
        d = ideen.lesen('k1')
        self.assertEqual([e['idee'] for e in d['offen']], ['System-Idee eins'])
        self.assertIn('Folge 2026-10-30-x', (self.arbeit / 'kanaele/k1/IDEEN.md').read_text(encoding='utf-8'))

    def test_neu_folge_mit_idee(self):
        self.kanal()
        import ideen
        ideen.neu('k1', 'Warum Akkus im Winter schwächeln', eigen=True)
        env = dict(os.environ, MS_SITZUNG='ms-autobau-test')
        r = subprocess.run([sys.executable, str(TOOLS / 'neu.py'), 'folge', 'akku', '--kanal', 'k1', '--idee', 'Warum Akkus im Winter schwächeln'],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        fid = Path(r.stdout.strip()).name
        st = json.loads((self.arbeit / 'folgen' / fid / 'STATUS.json').read_text(encoding='utf-8'))
        self.assertEqual((st['art'], st['quelle'], st['sitzung']), ('folge', 'eigen', 'ms-autobau-test'))
        self.assertEqual(ideen.lesen('k1')['offen'], [])
        r = subprocess.run([sys.executable, str(TOOLS / 'neu.py'), 'folge', 'ohne', '--kanal', 'k1'], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)    # ohne --idee/--pilot/--kopie kein Anlegen


class AutopilotTest(Basis):
    def test_reset_zeiten(self):
        import autopilot
        j = datetime(2026, 10, 30, 14, 0)
        self.assertEqual(autopilot.reset_zeit('You hit your limit · resets 3pm', j), datetime(2026, 10, 30, 15, 0))
        self.assertEqual(autopilot.reset_zeit('resets 9am', j), datetime(2026, 10, 31, 9, 0))
        self.assertEqual(autopilot.reset_zeit('Weekly limit reached · Resets Nov 5 at 2am', j), datetime(2026, 11, 5, 2, 0))
        self.assertEqual(autopilot.reset_zeit('resets in 2h 10m', j), j + timedelta(hours=2, minutes=10))
        self.assertIsNone(autopilot.reset_zeit('usage limit reached', j))
        z = {}
        autopilot.limit_merken(z, 'resets 3pm', j)
        self.assertEqual(z['limit_bis'], '2026-10-30T15:02')

    def test_stopps(self):
        import _konfig
        import autopilot
        self.profil()
        self.kanal()
        cfg = {**_konfig.konfig(), 'an': True, 'kanal': 'k1', 'fenster': ['00:00', '23:59'], 'puffer': 2}
        j = datetime.now()
        self.assertIsNone(autopilot.stopp(cfg, {}, j))
        self.folge('2026-10-30-a')
        self.folge('2026-10-30-b')
        self.folge('2026-10-30-pilot', art='pilot', quelle=None)
        self.assertEqual(autopilot.stopp(cfg, {}, j)[0], 'puffer')
        cfg['puffer'] = 5
        self.assertEqual(autopilot.stopp(cfg, {'woche': {'prozent': 61.0}}, j)[0], 'bremse')
        self.assertIsNone(autopilot.stopp(cfg, {'woche': {'prozent': 59.0}}, j))
        self.assertEqual(autopilot.stopp(cfg, {'limit_bis': (j + timedelta(hours=1)).isoformat(timespec='minutes')}, j)[0], 'limit')

    def test_lauf_trocken(self):
        import autopilot
        self.kanal()
        schreibe(self.arbeit / 'autopilot.json', {'an': True, 'kanal': 'k1', 'fenster': ['00:00', '23:59'], 'abo': 'max5'})
        e = autopilot.lauf(trocken=True)
        self.assertTrue(e['gestartet'], e)
        self.assertIn('--model opus', e['befehl_text'])
        self.assertIn('Stufe A', e['befehl_text'])
        self.assertFalse((self.arbeit / 'autopilot' / 'zustand.json').exists())   # trocken schreibt nichts
        self.assertEqual(e['posten']['stopp'], 'aus')

    def test_staffel_uebergabe(self):
        import autopilot
        self.kanal()
        self.folge('2026-10-30-a', phase='storyboard', upload=False, sitzung='ms-autobau-1030-0900', stufe='A-fertig')
        gestartet = []

        def fake(art, cfg, kanal=None, folge=None, trocken=False):
            gestartet.append((art, folge))
            return {}, {'art': 'kopflos', 'log': f'/tmp/{art}.log', 'start': datetime.now().isoformat(timespec='seconds'), 'pid': 0}
        autopilot._sitzung_starten = fake
        z = {'baue': [{'art': 'kopflos', 'log': '/x/ms-autobau-1030-0900.log', 'start': datetime.now().isoformat(timespec='seconds'),
                       'pid': 0, 'stufe': 'A'}]}
        autopilot.aufraeumen(z, datetime.now())
        self.assertEqual(gestartet, [('autobau-b', '2026-10-30-a')])
        self.assertEqual(z['baue'][0]['stufe'], 'B')

    def test_stufe_a_fertig_stoesst_an(self):
        self.kanal()
        self.folge('2026-10-30-a', phase='storyboard', upload=False)
        env = dict(os.environ, MS_KEIN_ANSTOSS='1')
        r = subprocess.run([sys.executable, str(TOOLS / 'status.py'), '2026-10-30-a', '--stufe', 'A-fertig'], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((self.arbeit / 'folgen/2026-10-30-a/STATUS.json').read_text(encoding='utf-8'))['stufe'], 'A-fertig')
        import status
        aufrufe = []
        echt = subprocess.Popen
        subprocess.Popen = lambda cmd, **kw: aufrufe.append((cmd, kw.get('start_new_session')))
        try:
            os.environ.pop('MS_KEIN_ANSTOSS', None)
            status.anstossen()
        finally:
            subprocess.Popen = echt
        self.assertEqual(aufrufe[0][0][-2:], [str(TOOLS / 'autopilot.py'), 'anstossen'])

    def test_posten_schritt(self):
        import autopilot
        import _konfig
        import posten
        self.profil('Instagram')
        d = self.kanal()
        self.folge('2026-10-30-a')
        cfg = {**_konfig.konfig(), 'kanal': 'k1', 'posten': True, 'post_zeit': '00:00'}
        self.assertEqual(autopilot.posten_stopp(cfg, {}, datetime.now())[0][0], 'frei')
        schreibe(d / 'posten' / 'instagram.md', '# Ablauf\n')
        posten.freigabe('k1', 'instagram', 'ja')
        g, kand = autopilot.posten_stopp(cfg, {}, datetime.now())
        self.assertIsNone(g)
        self.assertEqual(kand['folge_id'], '2026-10-30-a')
        posten.ergebnis('2026-10-30-a', 'instagram', None, 'nicht eingeloggt')
        self.assertEqual(autopilot.posten_stopp(cfg, {}, datetime.now())[0][0], 'fehler')


class VerbrauchTest(Basis):
    def _protokoll(self, name, folge_text, schritte, modell='claude-opus-5-5'):
        import _verbrauch
        d = _verbrauch.projekt_ordner(self.arbeit)
        zeilen = [json.dumps({'type': 'user', 'message': {'content': f'Arbeite an folgen/{folge_text}'}})]
        from datetime import timezone
        jetzt = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        for i, u in enumerate(schritte):
            e = {'type': 'assistant', 'timestamp': jetzt, 'message': {'id': f'm{i}', 'model': modell, 'usage': u}}
            zeilen += [json.dumps(e), json.dumps(e)]        # Streaming-Doppel zählt nur einmal
        schreibe(d / f'{name}.jsonl', '\n'.join(zeilen) + '\n')
        return d

    def test_folge_und_woche(self):
        import _verbrauch
        u = {'input_tokens': 1_000_000, 'output_tokens': 100_000, 'cache_read_input_tokens': 10_000_000}
        self.assertEqual(_verbrauch.gewicht(u), 2_500_000)
        self._protokoll('s1', '2026-10-30-a 2026-10-30-a', [u])
        v = _verbrauch.folge_verbrauch('2026-10-30-a')
        self.assertEqual(len(v['sitzungen']), 1)
        self.assertAlmostEqual(v['gesamt_M'], 2.5, places=2)          # Streaming-Doppel nur einmal gezählt
        self.assertAlmostEqual(v['rollen']['regie'], 2.5, places=2)
        w = _verbrauch.wochen_anteil({'abo': 'max20'})
        self.assertAlmostEqual(w['gewichtet_M'], 2.5, places=1)
        self.assertAlmostEqual(w['prozent'], round(2.5 / 9.8, 1), places=1)
        self.assertIsNone(_verbrauch.wochen_anteil({'abo': ''})['prozent'])

    def test_woche_reset(self):
        import _verbrauch
        j = datetime(2026, 10, 30, 12, 0).astimezone()        # Freitag
        self.assertEqual(_verbrauch.woche_start({'woche_reset': 'do 02:00'}, j).strftime('%a %H:%M'), 'Thu 02:00')
        self.assertEqual((j - _verbrauch.woche_start({}, j)).days, 7)


class StilTest(Basis):
    def _pilot(self):
        self.kanal('k1', phase='kit', pilot='folgen/2026-10-23-pilot')
        p = self.folge('2026-10-23-pilot', art='pilot', quelle=None, upload=False, vorlage={'id': 'v1'})
        schreibe(p / 'build' / 'scenes.json', [{'id': 's1', 'start': 0, 'dur': 3.2, 'art': '2d'}, {'id': 's2', 'start': 3.14, 'dur': 4.1, 'art': '2d'},
                                               {'id': 's3', 'start': 7.18, 'dur': 2.0, 'art': '3d-web'}])
        schreibe(p / 'build' / 'compositions' / 's1.html', 'function chipZeigen(el, t){} tl.to(a,{duration: 0.3, ease: "power2.out"})')
        schreibe(self.arbeit / 'kanaele/k1/kit/captions.json', {'an': True, 'schrift': 'Montserrat', 'groesse': 74, 'y': 1470})

    def test_anlegen_pruefen_nichts_verschwindet(self):
        import stil
        self._pilot()
        p = stil.anlegen('k1')
        self.assertTrue(p.exists())
        e = stil.pruefen('k1')
        self.assertFalse(e['ok'])
        self.assertTrue(any('AUSFÜLLEN' in m for m in e['maengel']))
        text = p.read_text(encoding='utf-8').replace('AUSFÜLLEN', 'gefüllt')
        text = text.replace('## Bausteine', '### Typ A\n### Typ B\n### Typ C\n### Typ D\n\n## Bausteine', 1)
        text = text.replace('| `chipZeigen(el, t)`', '| `a(x)` | k | z | w |\n| `b(x)` | k | z | w |\n| `c(x)` | k | z | w |\n| `d(x)` | k | z | w |\n| `chipZeigen(el, t)`')
        text = text.replace('## Übergänge', 'Regeln: 0,30 s, 85 %, 0,12 s, 2 %, 4 s, 1,08 s.\n\n## Übergänge')
        text = text.replace('| gefüllt | | | |', '| `e(x)` | k | z | w |').replace('| gefüllt | | |', '| Regel | 10 px | Bogen |')
        text = text.replace('| Captions | Lage und Stil', '| Caption-Oberkante | y 1470 ±10 px | Bogen |\n| Hintergrund | ΔE unter 3 | Paarbild |\n| Captions | Lage und Stil')
        p.write_text(text, encoding='utf-8')
        e = stil.pruefen('k1')
        self.assertTrue(e['ok'], e)
        stil.sichern('k1')
        p.write_text(text.replace('| `b(x)` | k | z | w |\n', ''), encoding='utf-8')
        e = stil.pruefen('k1')
        self.assertFalse(e['ok'])
        self.assertTrue(any('nichts darf verschwinden' in m for m in e['maengel']), e)

    def test_kein_doppeltes_anlegen(self):
        import stil
        self._pilot()
        stil.anlegen('k1')
        with self.assertRaises(SystemExit):
            stil.anlegen('k1')
        stil.anlegen('k1', neu=True)
        self.assertTrue(list((stil.pfad('k1').parent / '_ueberholt').glob('SKILL-*.md')))


class LernlogTest(Basis):
    def test_kurz_und_archiv(self):
        import lernlog
        eintraege = '\n'.join(f'- {i:02d}.10.2026 · Folge {i}\n  Geklappt: x' for i in range(1, 46))
        schreibe(self.arbeit / 'LERNLOG.md', f'# Lernlog\n\n## Startwissen\n- a\n\n## Lehren\n- immer b\n\n## Einträge\n{eintraege}\n')
        k = lernlog.kurz(3)
        self.assertIn('immer b', k)
        self.assertIn('Folge 45', k)
        self.assertNotIn('Folge 41', k)
        self.assertIn('ms lernlog archivieren', k)
        lernlog.archivieren(30)
        self.assertIn('Folge 15', (self.arbeit / 'LERNLOG-ARCHIV.md').read_text(encoding='utf-8'))
        rest = (self.arbeit / 'LERNLOG.md').read_text(encoding='utf-8')
        self.assertNotIn('Folge 15\n', rest)
        self.assertIn('Folge 16', rest)
        self.assertIn('## Lehren', rest)


class WarteTest(Basis):
    def test_bauer_und_render(self):
        d = self.folge('2026-10-30-a', upload=False)
        schreibe(d / 'build' / 'fertig_bauer-1.json', {'szenen': ['s1']})
        r = subprocess.run([sys.executable, str(TOOLS / 'warte.py'), '2026-10-30-a', '--bauer', 'bauer-1', '--max', '0.05', '--takt', '0.1'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = subprocess.run([sys.executable, str(TOOLS / 'warte.py'), '2026-10-30-a', '--bauer', 'bauer-2', '--max', '0.01', '--takt', '0.1'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        schreibe(d / 'out' / 'v1.mp4', 'x')
        schreibe(d / 'out' / 'render_v1.log', 'Render v1 …\nBefunde: keine\nfertig: out/v1.mp4 (40 s)\n')
        r = subprocess.run([sys.executable, str(TOOLS / 'warte.py'), '2026-10-30-a', '--render', 'v1', '--max', '0.05', '--takt', '0.1'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        schreibe(d / 'out' / 'render_v2.log', 'ABBRUCH: hyperframes lint meldet Fehler\n')
        r = subprocess.run([sys.executable, str(TOOLS / 'warte.py'), '2026-10-30-a', '--render', 'v2', '--max', '0.05', '--takt', '0.1'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)


class StudioTest(Basis):
    def test_stand_mitglied(self):
        self.profil('Instagram')
        d = self.kanal()
        self.folge('2026-10-30-a')
        self.folge('2026-10-30-pilot', art='pilot', quelle=None)
        import ideen
        ideen.neu('k1', 'Meine Idee', eigen=True)
        schreibe(self.arbeit / 'autopilot.json', {'an': True, 'kanal': 'k1', 'puffer': 1, 'fenster': ['00:00', '23:59']})
        import server
        importlib.reload(server)
        import starten
        starten.liste = lambda muster=None: []
        starten._tmux = lambda: None
        s = server.stand()
        self.assertEqual([v['folge_id'] for v in s['vorrat']], ['2026-10-30-a'])
        self.assertTrue(s['vorrat'][0]['postbar'])
        self.assertEqual(s['ideen']['offen'][0]['idee'], 'Meine Idee')
        tags = [h['tag'] for h in s['hinweise']]
        self.assertIn('PUFFER VOLL', tags)
        self.assertIn('IDEEN', tags)
        self.assertIn('posten-einrichten', [a['art'] for a in s['aktionen']])
        self.assertFalse(s['steuerung']['autopilot']['an'])
        schreibe(d / 'posten' / 'instagram.md', '# Ablauf\n')
        import posten
        posten.freigabe('k1', 'instagram', 'ja')
        server._AP_CACHE.clear()
        s = server.stand()
        self.assertIn('autopilot-an', [a['art'] for a in s['aktionen']])


    def test_neu_versuchen_startet_posten(self):
        self.profil('Instagram')
        self.kanal()
        self.folge('2026-10-30-a')
        import posten
        posten.ergebnis('2026-10-30-a', 'instagram', None, 'nicht eingeloggt')
        import server
        importlib.reload(server)
        import starten
        aufrufe = []
        starten.starten = lambda art, **kw: aufrufe.append((art, kw.get('folge'))) or {'sitzung': 'ms-posten-test'}
        e = server._posten_starten('2026-10-30-a')
        self.assertEqual(aufrufe, [('posten', '2026-10-30-a')])
        self.assertIn('Posten gestartet', e['meldung'])
        st = json.loads((self.arbeit / 'folgen/2026-10-30-a/STATUS.json').read_text(encoding='utf-8'))
        self.assertNotIn('fehler', st)
        self.folge('2026-10-30-pilot', art='pilot', quelle=None)
        with self.assertRaises(SystemExit):
            server._posten_starten('2026-10-30-pilot')


class SeiteTest(unittest.TestCase):
    def test_javascript_syntax(self):
        if not shutil.which('node'):
            self.skipTest('node fehlt')
        html = (REPO / 'studio' / 'dashboard' / 'index.html').read_text(encoding='utf-8')
        teile = html.split('<script>')
        self.assertGreater(len(teile), 1)
        js = '\n'.join(t.split('</script>')[0] for t in teile[1:])
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(js)
        r = subprocess.run(['node', '--check', f.name], capture_output=True, text=True)
        os.unlink(f.name)
        self.assertEqual(r.returncode, 0, r.stderr[:800])


class InstallTest(unittest.TestCase):
    def test_install_ergaenzt_auto_gedaechtnis(self):
        if not shutil.which('bash'):
            self.skipTest('bash fehlt')
        tmp = Path(tempfile.mkdtemp(prefix='ms-inst-'))
        try:
            cfg, arbeit = tmp / 'cfg', tmp / 'arbeit'
            schreibe(cfg / 'motion-studio' / 'config.json', {'dashboard_port': 18999})    # kein laufendes Studio anfassen
            schreibe(arbeit / '.claude' / 'settings.json', {'permissions': {'allow': ['Bash(ls *)']}})
            r = subprocess.run(['bash', str(REPO / 'install.sh'), '--arbeit', str(arbeit)], capture_output=True, text=True,
                               env=dict(os.environ, CLAUDE_CONFIG_DIR=str(cfg)))
            self.assertEqual(r.returncode, 0, r.stdout[-800:] + r.stderr[-800:])
            s = json.loads((arbeit / '.claude' / 'settings.json').read_text(encoding='utf-8'))
            self.assertIs(s['autoMemoryEnabled'], False)
            self.assertEqual(s['permissions']['allow'], ['Bash(ls *)'])
            self.assertTrue((arbeit / '.claude' / 'settings.json.vor-v4').exists())
            for a in ('motion-bauer', 'motion-pruefer', 'motion-analyse'):
                self.assertIn('model: sonnet', (cfg / 'agents' / f'{a}.md').read_text(encoding='utf-8'))
            for skill in ('motion-posten', 'motion-ideen'):
                self.assertTrue((cfg / 'skills' / skill / 'SKILL.md').exists())
            rest = subprocess.run(['grep', '-rl', '-e', '__HEIM__', '-e', '__ARBEIT__', str(cfg / 'agents'), str(cfg / 'skills')],
                                  capture_output=True, text=True).stdout.strip()
            self.assertEqual(rest, '')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
