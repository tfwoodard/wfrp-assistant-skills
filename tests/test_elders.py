"""Elders: Times lived through, earlier careers and burdens, from an invented creation rule."""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_build_character import SCRIPTS, Case, para, record  # noqa: E402

sys.path.insert(0, SCRIPTS)
import build_character as bc  # noqa: E402
import character_pdf  # noqa: E402
from library import Library  # noqa: E402

AGES = {'type': 'table', 'title': 'Ages of the Rock', 'columns': ['Age', 'Born in', 'Cost'],
        'rows': [['young', 'Low Tide', 'none'], ['old', 'High Tide', 'a little'], ['ancient', 'Storm', 'a lot']]}
FIELDS = {
    'lived_through': {'table': 'Ages of the Rock', 'column': 'Born in'},
    'grants': [{'id': 'years', 'how': 'elder', 'kind': 'skill', 'from': 'elder-career',
                'total': {'rolled': 6, 'chosen': 4}, 'most': 3, 'at': 0}],
    'rows': {'Low Tide': {'careers': 0},
             'High Tide': {'careers': 1, 'effects': [{'on': 'extra_points', 'add': -1}],
                           'burdens': [{'text': 'One fewer extra point.'},
                                       {'text': 'Each week, an easy gull test.', 'only_earliest': True}]},
             'Storm': {'careers': 1, 'effects': [{'on': 'fate', 'set': 0}, {'on': 'resilience', 'set': 0},
                                                 {'on': 'extra_points', 'set': 0}],
                       'psychology': ['Fear of Gulls'],
                       'burdens': [{'text': 'Starts with no Fate or Resilience.'},
                                   {'text': 'Each week, a hard gull test.', 'only_earliest': True}]}}}


class Elders(Case):
    def setUp(self):
        super().setUp()
        d = os.path.join(self.root, 'library-data', 'rules')
        e = {'slug': 'old-keepers', 'name': 'Old Keepers', 'source': 'LAMP', 'chapter': 'ch2', 'section': 'Old Keepers',
             'page': 40, 'relations': [{'role': 'adds-to', 'to': 'rules/career-skills-and-talents'}], 'fields': FIELDS,
             'content': [para('Some keepers are older.'), {'type': 'sidebar', 'content': [AGES]}]}
        with open(os.path.join(d, 'old-keepers.json'), 'w') as f: json.dump(e, f)
        with open(os.path.join(d, '_index.json')) as f: idx = json.load(f)
        idx.append({k: v for k, v in e.items() if k not in ('content', 'fields')})
        with open(os.path.join(d, '_index.json'), 'w') as f: json.dump(idx, f)

    def elder(self, born, careers, lines=(), **over):
        r = record(**over)
        r['species']['elder'] = {'born': born, 'careers': careers}
        r['advances'] += [dict(l, how='elder') for l in lines]
        return r

    def test_an_elder_born_in_a_time_gets_its_career_and_burdens(self):
        r = self.elder('High Tide', [{'time': 'High Tide', 'ref': 'careers/warden', 'how': 'rolled'}],
                       [{'skill': 'skills/watch', 'count': 3, 'time': 'High Tide'},
                        {'skill': 'skills/rowing', 'count': 2, 'time': 'High Tide'}],
                       extra_points={'fate': 1, 'resilience': 0})
        m = self.build(r)
        self.assertEqual([i for i in self.ids(m) if i.startswith(('elder', 'creation', 'extra'))], [])
        el = m['elder']
        self.assertEqual((el['born'], el['careers'][0]['name'], el['careers'][0]['given'], el['careers'][0]['left']),
                         ('High Tide', 'Warden', 5, 1))
        self.assertEqual([t for b in el['burdens'] for t in b['text']], ['One fewer extra point.', 'Each week, an easy gull test.'])
        watch = next(s for s in m['skills']['basic'] if s['name'] == 'Watch')
        self.assertEqual(watch['advances'], 5 + 3)                             # the species' 5 and the Elder's 3
        self.assertIn('extra-points', self.ids(self.build(self.elder('High Tide', r['species']['elder']['careers']))))

    def test_every_time_lived_through_and_only_the_earliest_once_only_burden(self):
        careers = [{'time': 'High Tide', 'ref': 'careers/warden', 'how': 'chosen'}]
        r = self.elder('Storm', careers, [{'skill': 'skills/watch', 'count': 4, 'time': 'High Tide'},
                                          {'skill': 'skills/signals', 'specialisation': 'Flag', 'count': 1, 'time': 'High Tide'},
                                          {'skill': 'skills/watch', 'count': 1, 'time': 'Low Tide'}],
                       extra_points={'fate': 0, 'resilience': 0})
        m = self.build(r)
        ids = self.ids(m)
        for i in ('creation:old-keepers/years:times', 'creation:old-keepers/years:high-tide',
                  'creation:old-keepers/years:high-tide:signals-flag', 'creation:old-keepers/years:time-low-tide',
                  'elder:psychology/fear-of-gulls'):
            self.assertIn(i, ids, i)
        self.assertNotIn('extra-points', ids)                                  # set to 0 after taking one off
        self.assertEqual((m['fate']['fate'], m['resilience']['resilience']), (0, 0))
        text = [t for b in m['elder']['burdens'] for t in b['text']]
        self.assertEqual(text, ['One fewer extra point.', 'Starts with no Fate or Resilience.', 'Each week, a hard gull test.'])
        r['psychology'] = ['Fear of Gulls (the big ones)']
        r['species']['elder']['careers'].append({'time': 'Storm', 'ref': 'careers/warden', 'how': 'rolled'})
        ids = self.ids(self.build(r))
        self.assertNotIn('elder:psychology/fear-of-gulls', ids)
        self.assertNotIn('creation:old-keepers/years:times', ids)

    def test_a_time_the_table_lacks_and_elder_lines_without_an_elder(self):
        self.assertIn('elder:born', self.ids(self.build(self.elder('Drought', []))))
        r = record()
        r['advances'].append({'skill': 'skills/watch', 'count': 1, 'how': 'elder', 'time': 'High Tide'})
        self.assertIn('elder:not-elder', self.ids(self.build(r)))
        self.assertNotIn('elder', self.build(record()))

    def test_both_sheets_show_the_elder(self):
        m = self.build(self.elder('High Tide', [{'time': 'High Tide', 'ref': 'careers/warden', 'how': 'rolled'}],
                                  extra_points={'fate': 1, 'resilience': 0}))
        md = bc.markdown(m)
        part = md[md.index('## Elder'):]
        for s in ('- Born in the High Tide (LAMP', '- High Tide: Warden (rolled), 0 advances, 6 left',
                  '- Burden: One fewer extra point.', '- Burden: Each week, an easy gull test.'):
            self.assertIn(s, part, s)
        self.assertIn('Extra points -1', md[md.index('## What rules add'):])
        html = character_pdf.document(m)
        self.assertIn('<h2>Elder</h2>', html)
        self.assertIn('Burden: Each week, an easy gull test.', html)

    def test_set_formulas_writes_them_on_a_table_in_a_sidebar(self):
        p = os.path.join(self.root, 'library-data', 'rules', 'old-keepers.json')
        with open(p) as f: e = json.load(f)
        e['fields'] = {}
        with open(p, 'w') as f: json.dump(e, f)
        sf = os.path.join(SCRIPTS, '..', '..', 'wfrp-import', 'scripts', 'set_formulas.py')
        run = lambda *a: subprocess.run([sys.executable, sf, p, *a], capture_output=True, text=True)
        self.assertEqual(run('--lived-through', json.dumps(FIELDS['lived_through'])).returncode, 0)
        self.assertIn('no column', run('--lived-through', '{"table": "Ages of the Rock", "column": "Tide"}').stderr)
        self.assertEqual(run('--grants', json.dumps(FIELDS['grants'])).returncode, 0)
        r = run('--row', 'Storm', '--effects', json.dumps(FIELDS['rows']['Storm']['effects']),
                '--row-fields', json.dumps({k: v for k, v in FIELDS['rows']['Storm'].items() if k != 'effects'}))
        self.assertEqual(r.returncode, 0, r.stderr)
        for row in ('High Tide', 'Low Tide'):
            spec = FIELDS['rows'][row]
            args = ['--row', row, '--row-fields', json.dumps({k: v for k, v in spec.items() if k != 'effects'})]
            if 'effects' in spec: args += ['--effects', json.dumps(spec['effects'])]
            self.assertEqual(run(*args).returncode, 0)
        self.assertIn('"burdens" lists', run('--row', 'Storm', '--row-fields', '{"burdens": ["just words"]}').stderr)
        with open(p) as f: got = json.load(f)['fields']
        self.assertEqual(got, FIELDS)

    def test_apply_writes_the_elder_and_its_advances(self):
        p = os.path.join(self.root, 'mara.json')
        with open(p, 'w') as f: json.dump(record(extra_points={'fate': 1, 'resilience': 0}), f)
        run = lambda *a: subprocess.run([sys.executable, os.path.join(SCRIPTS, 'apply.py'), p, '--library', self.root,
                                         '--campaign', 'rock', *a], capture_output=True, text=True)
        r = run('elder', '--born', 'High Tide', '--career', 'High Tide=Warden:rolled')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('To give from the High Tide career: 6 advances', r.stdout)
        self.assertIn('Burden: One fewer extra point.', r.stdout)
        with open(p) as f: rec = json.load(f)
        self.assertEqual(rec['species']['elder'], {'born': 'High Tide', 'careers': [{'time': 'High Tide', 'ref': 'careers/warden', 'how': 'rolled'}]})
        self.assertEqual(rec['xp'], {'total': 100})                             # a finished record keeps its XP
        r = run('buy', '--skill', 'Watch', '--count', '3', '--how', 'elder', '--time', 'High Tide')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("from the Elder's career in the High Tide", r.stdout)
        self.assertIn('Still to give from the High Tide career (Warden): 3 advances', r.stdout)
        self.assertIn('--time', run('buy', '--skill', 'Watch', '--how', 'elder').stderr)


if __name__ == '__main__':
    import unittest
    unittest.main()
