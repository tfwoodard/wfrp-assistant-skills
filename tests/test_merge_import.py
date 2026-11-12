"""Tests for skills/wfrp-import/scripts/merge_import.py (invented records only).

Run: python3 -m unittest discover tests
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts', 'merge_import.py')


def rec(slug, chapter='careers-q', source='CRB', **kw):
    return dict({'slug': slug, 'name': slug.title(), 'source': source, 'chapter': chapter,
                 'cr': '1', 'xp': 200, 'type': 'Fey', 'tags': []}, **kw)


def lines_json(rs):
    return '[\n' + ',\n'.join('  ' + json.dumps(r, ensure_ascii=False) for r in rs) + '\n]\n'


LIBRARY = """{
  "wfrp_library": true,
  "layout_version": 3,
  "sources": [
    {
      "code": "DMG24",
      "chapters": [
        { "id": "app-a", "title": "Appendix A: Lore", "status": "not-imported", "date": null, "notes": "" }
      ]
    },
    {
      "code": "CRB",
      "chapters": [
        { "id": "careers-q", "title": "Careers (Q)", "status": "not-imported", "date": null, "notes": "" },
        { "id": "app-a", "title": "Appendix A: Animals", "status": "not-imported", "date": null, "notes": "" }
      ]
    }
  ],
  "house_rules": []
}
"""


class MergeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.out = os.path.join(self.d, 'out')
        self.write('index.json', lines_json([rec('alpha', 'careers-p'), rec('zeta', 'careers-p')]))
        self.write('records.json', lines_json([rec('quill'), rec('quartz')]))
        self.write('log.json', lines_json([{'date': '2026-01-01', 'source': 'CRB', 'chapter': 'careers-p',
                                            'category': 'careers', 'added': 2, 'updated': 0,
                                            'skipped': 0, 'failed': 0, 'notes': 'p'}]))
        self.write('library.json', LIBRARY)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        with open(os.path.join(self.d, name), 'w', encoding='utf-8') as f:
            f.write(text)

    def read(self, name):
        with open(os.path.join(self.out, name), encoding='utf-8') as f:
            return f.read()

    def run_merge(self, *extra, final=True):
        args = [sys.executable, SCRIPT, '--out', self.out, '--index', os.path.join(self.d, 'index.json'),
                '--records', os.path.join(self.d, 'records.json'), '--edition', '4e']
        if final:
            args += ['--log', os.path.join(self.d, 'log.json'), '--library', os.path.join(self.d, 'library.json'),
                     '--source', 'CRB', '--chapter', 'careers-q', '--category', 'careers',
                     '--date', '2026-02-02', '--log-notes', 'two blocks', '--chapter-notes', 'Q done']
        return subprocess.run(args + list(extra), capture_output=True, text=True)

    def test_final_run_writes_all_three(self):
        r = self.run_merge()
        self.assertEqual(r.returncode, 0, r.stderr)
        idx = json.loads(self.read('_index.json'))
        self.assertEqual([x['slug'] for x in idx], ['alpha', 'quartz', 'quill', 'zeta'])
        self.assertEqual(self.read('_index.json'), lines_json(idx))
        self.assertEqual({x['slug']: x.get('edition') for x in idx if x['slug'] in ('quartz', 'quill')},
                         {'quartz': '4e', 'quill': '4e'})            # new records carry the source's edition
        log = json.loads(self.read('_import-log.json'))
        self.assertEqual(log[-1], {'date': '2026-02-02', 'source': 'CRB', 'chapter': 'careers-q',
                                   'category': 'careers', 'added': 2, 'updated': 0, 'skipped': 0,
                                   'failed': 0, 'notes': 'two blocks'})
        lib = self.read('library.json')
        self.assertEqual(lib, LIBRARY.replace(
            '{ "id": "careers-q", "title": "Careers (Q)", "status": "not-imported", "date": null, "notes": "" }',
            '{ "id": "careers-q", "title": "Careers (Q)", "status": "imported", "date": "2026-02-02", "notes": "Q done" }'))
        size = os.path.getsize(os.path.join(self.out, 'library.json'))
        self.assertIn(f'{size:>7}  library.json', r.stdout)

    def test_chapter_id_is_matched_within_its_source(self):
        r = self.run_merge()
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run([sys.executable, SCRIPT, '--out', self.out, '--records', os.path.join(self.d, 'records.json'),
                            '--edition', '4e', '--library', os.path.join(self.d, 'library.json'), '--source', 'CRB',
                            '--chapter', 'app-a', '--category', 'careers'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        lib = json.loads(self.read('library.json'))
        self.assertEqual(lib['sources'][0]['chapters'][0]['status'], 'not-imported')  # DMG24 app-a
        self.assertEqual(lib['sources'][1]['chapters'][1]['status'], 'imported')      # CRB app-a

    def test_edition_is_required(self):
        args = [sys.executable, SCRIPT, '--out', self.out, '--index', os.path.join(self.d, 'index.json'),
                '--records', os.path.join(self.d, 'records.json')]
        r = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn('no edition', r.stderr)

    def test_failures_mark_chapter_problems(self):
        self.run_merge('--failed', '1')
        self.assertIn('"status": "problems"', self.read('library.json'))
        self.assertEqual(json.loads(self.read('_import-log.json'))[-1]['failed'], 1)

    def test_batch_merge_takes_only_listed_slugs(self):
        r = self.run_merge('--slugs', 'quill', final=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([x['slug'] for x in json.loads(self.read('_index.json'))], ['alpha', 'quill', 'zeta'])
        self.assertFalse(os.path.exists(os.path.join(self.out, 'library.json')))

    def test_reimport_updates_and_removes(self):
        self.write('index.json', lines_json([rec('alpha', 'careers-p'), rec('quill'), rec('quiet')]))
        r = self.run_merge()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([x['slug'] for x in json.loads(self.read('_index.json'))], ['alpha', 'quartz', 'quill'])
        self.assertIn('move their entry files to the trash: quiet', r.stdout)
        last = json.loads(self.read('_import-log.json'))[-1]
        self.assertEqual((last['added'], last['updated']), (1, 1))

    def test_slug_owned_by_another_source_is_refused(self):
        self.write('index.json', lines_json([rec('quill', 'all', source='HB-TEST')]))
        r = self.run_merge()
        self.assertEqual(r.returncode, 2)
        self.assertIn('--taken', r.stderr)

    def test_reads_drive_downloads(self):
        b64 = base64.b64encode(LIBRARY.encode()).decode()
        self.write('library.json', json.dumps({'id': 'x', 'title': 'library.json', 'content': b64}))
        self.write('log.json', base64.b64encode(lines_json([]).encode()).decode())
        r = self.run_merge()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"status": "imported"', self.read('library.json'))
        self.assertEqual(len(json.loads(self.read('_import-log.json'))), 1)

    def test_converter_private_keys_are_dropped(self):
        self.write('records.json', lines_json([rec('quill', _pb=2)]))
        self.run_merge(final=False)
        self.assertNotIn('_pb', self.read('_index.json'))


    def test_records_for_other_indexes_are_left_out_and_the_category_tag_dropped(self):
        self.write('index.json', lines_json([rec('alpha', 'careers-p', category='careers'), rec('zeta', 'careers-p')]))
        self.write('records.json', lines_json([rec('quill', _category='careers'), rec('quartz', _category='rules'),
                                               rec('quiet', _category='careers', category='origin')]))
        r = self.run_merge()
        self.assertIn('leaving out rules', r.stdout)
        idx = json.loads(self.read('_index.json'))
        self.assertEqual([x['slug'] for x in idx], ['alpha', 'quiet', 'quill', 'zeta'])
        self.assertEqual([x.get('category') for x in idx], [None, 'origin', None, None])   # a real category field stays
        self.assertNotIn('_category', self.read('_index.json'))


if __name__ == '__main__':
    unittest.main()
