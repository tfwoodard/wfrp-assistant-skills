"""Tests for skills/wfrp-import/scripts/import_journal.py.

Run: python3 -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts', 'import_journal.py')


class JournalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        out = os.path.join(self.d, 'out-q')
        os.mkdir(out)
        for slug, text in (('quillback', 'a' * 10), ('mirewight', 'b' * 20)):
            with open(os.path.join(out, slug + '.md'), 'w') as f:
                f.write(text)

    def tearDown(self):
        self.tmp.cleanup()

    def j(self, *args, ok=True):
        r = subprocess.run([sys.executable, SCRIPT, '--dir', self.d, *args],
                           capture_output=True, text=True)
        if ok:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        else:
            self.assertNotEqual(r.returncode, 0, r.stdout)
        return r.stdout + r.stderr

    def journal(self):
        with open(os.path.join(self.d, 'journal.json')) as f:
            return json.load(f)

    def test_resume_after_a_stop_mid_upload(self):
        self.j('drive', '--root', 'R', '--folder', 'careers=M',
               '--file', 'careers/_index.json=OLDIDX:100')
        self.j('start', 'careers-q', '--source', 'CRB', '--category', 'careers',
               '--pages', '30-109', '--page', 'q-page.txt')
        self.j('phase', 'careers-q', 'converted', '--out', 'out-q')
        self.j('note', 'careers-q', 'Quote removed by hand')
        self.j('uploaded', 'careers-q', 'quillback=ID1:10')
        # The session stops here. A resumed session runs show:
        s = self.j('show')
        self.assertIn('careers-q (CRB, careers): phase uploading', s)
        self.assertIn('entries: 1 of 2 uploaded', s)
        self.assertIn('not yet uploaded: mirewight', s)
        self.assertIn('note: Quote removed by hand', s)
        self.assertIn('pages: 30-109', s)
        self.assertIn('current careers/_index.json: OLDIDX (100 bytes)', s)

    def test_size_mismatch_is_refused(self):
        self.j('start', 'careers-q', '--source', 'CRB', '--category', 'careers')
        self.j('phase', 'careers-q', 'converted', '--out', 'out-q')
        out = self.j('uploaded', 'careers-q', 'quillback=ID1:10', 'mirewight=ID2:19', ok=False)
        self.assertIn('mirewight: Drive size 19, local 20', out)
        self.assertEqual(list(self.journal()['chapters']['careers-q']['uploaded']), ['quillback'])

    def test_cannot_merge_before_every_entry_is_uploaded(self):
        self.j('start', 'careers-q', '--source', 'CRB', '--category', 'careers')
        self.j('phase', 'careers-q', 'converted', '--out', 'out-q')
        self.j('uploaded', 'careers-q', 'quillback=ID1:10')
        self.assertIn('mirewight', self.j('phase', 'careers-q', 'merged', ok=False))
        self.j('uploaded', 'careers-q', 'mirewight=ID2:20')
        self.j('phase', 'careers-q', 'merged')

    def test_bookkeeping_queues_old_ids_until_trashed(self):
        self.j('drive', '--file', 'careers/_index.json=OLDIDX:100', '--file', 'library.json=OLDLIB:50')
        self.j('start', 'careers-q', '--source', 'CRB', '--category', 'careers')
        self.j('phase', 'careers-q', 'converted', '--out', 'out-q')
        self.j('uploaded', 'careers-q', 'quillback=ID1:10', 'mirewight=ID2:20')
        self.j('phase', 'careers-q', 'merged')
        self.j('bookkeeping', 'careers/_index.json', 'NEWIDX:120')
        self.j('bookkeeping', 'library.json', 'NEWLIB:55')
        s = self.j('show')
        self.assertIn('OLDIDX  careers/_index.json', s)
        self.assertIn('current library.json: NEWLIB (55 bytes)', s)
        self.assertIn('OLDLIB', self.j('done', 'careers-q', ok=False))
        self.j('trashed', 'OLDIDX')
        self.j('trashed', 'OLDLIB')
        self.j('done', 'careers-q')
        self.assertIn('No import in progress.', self.j('show'))

    def test_start_refuses_a_chapter_already_in_progress(self):
        self.j('start', 'careers-q', '--source', 'CRB', '--category', 'careers')
        self.assertIn('already in progress',
                      self.j('start', 'careers-q', '--source', 'CRB', '--category', 'careers', ok=False))

    def finished_upload(self):
        with open(os.path.join(self.d, 'q-page.txt'), 'w') as f:
            f.write('page')
        self.j('start', 'careers-q', '--source', 'CRB', '--category', 'careers', '--page', 'q-page.txt')
        self.j('phase', 'careers-q', 'converted', '--out', 'out-q')
        self.j('uploaded', 'careers-q', 'quillback=ID1:10', 'mirewight=ID2:20')

    def test_clean_deletes_the_chapter_scratch(self):
        self.finished_upload()
        with open(os.path.join(self.d, 'lists.txt'), 'w') as f:
            f.write('x')
        self.assertIn('bookkeeping', self.j('clean', 'careers-q', ok=False))
        self.j('phase', 'careers-q', 'merged')
        self.j('phase', 'careers-q', 'bookkeeping')
        out = self.j('clean', 'careers-q', 'lists.txt')
        self.assertIn('q-page.txt', out)
        self.assertEqual(sorted(os.listdir(self.d)), ['journal.json'])
        self.assertIn('scratch cleaned', self.j('show') + json.dumps(self.journal()))

    def test_clean_refuses_paths_outside_the_scratch_dir(self):
        self.finished_upload()
        self.j('phase', 'careers-q', 'merged')
        self.j('phase', 'careers-q', 'bookkeeping')
        with tempfile.TemporaryDirectory() as other:
            keep = os.path.join(other, 'keep.txt')
            with open(keep, 'w') as f:
                f.write('x')
            self.assertIn('not inside', self.j('clean', 'careers-q', keep, ok=False))
            self.assertTrue(os.path.exists(keep))
        self.assertIn('journal', self.j('clean', 'careers-q', 'journal.json', ok=False))
        self.assertTrue(os.path.exists(os.path.join(self.d, 'q-page.txt')))

    def test_show_survives_a_closed_pipe(self):
        self.finished_upload()
        r = subprocess.run(f'{sys.executable} {SCRIPT} --dir {self.d} show | head -1',
                           shell=True, capture_output=True, text=True)
        self.assertNotIn('Traceback', r.stderr)


    def test_waiting_question_and_answer(self):
        self.j('waiting', 'Split chapter 1 how?')
        s = self.j('show')
        self.assertTrue(s.startswith('WAITING FOR THE LIBRARIAN'), s)
        self.assertIn('Split chapter 1 how?', s)
        self.j('answered', 'One entry per section')
        s = self.j('show')
        self.assertNotIn('WAITING', s)
        self.assertIn('Split chapter 1 how? -> One entry per section', s)

    def test_doing_is_cleared_by_progress_but_not_by_notes(self):
        self.j('start', 'careers-q', '--source', 'CRB', '--category', 'careers')
        self.j('doing', 'converting Q')
        self.j('note', 'careers-q', 'a note')
        self.assertIn('STEP UNDER WAY', self.j('show'))
        self.j('phase', 'careers-q', 'converted', '--out', 'out-q')
        self.assertNotIn('STEP UNDER WAY', self.j('show'))

    def test_repo_work_is_listed_until_merged(self):
        self.j('repo', 'feat/x', '--pr', '7')
        self.assertIn('feat/x (PR #7): open', self.j('show'))
        self.j('repo', 'feat/x', '--status', 'merged')
        self.assertNotIn('feat/x', self.j('show'))

    def test_hook_finds_the_journal_and_is_silent_when_nothing_is_open(self):
        def hook():
            return subprocess.run([sys.executable, SCRIPT, 'show', '--hook'], cwd=self.tmp.name,
                                  capture_output=True, text=True, env={**os.environ, 'HOME': self.tmp.name})
        self.assertEqual(hook().stdout, '')            # no journal at all
        self.j('repo', 'feat/x', '--status', 'merged')
        self.assertEqual(hook().stdout, '')            # journal, nothing open
        self.j('waiting', 'Which chapter next?')
        out = hook().stdout
        self.assertIn('IMPORT JOURNAL', out)
        self.assertIn('Which chapter next?', out)


if __name__ == '__main__':
    unittest.main()
