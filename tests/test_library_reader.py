"""The skills' library reader (shared/scripts/library.py), find_entry.py and excerpt.py, on a
small invented library.

Run: python3 -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'skills', 'wfrp-rules-lookup', 'scripts')
sys.path.insert(0, SCRIPTS)
import excerpt  # noqa: E402
import find_entry  # noqa: E402
from library import Library, MissingFiles, RefError, cite, norm  # noqa: E402


def para(text):
    return {'type': 'paragraph', 'text': text}


def head(text, level=2):
    return {'type': 'heading', 'level': level, 'text': text}


def write(root, cat, entries, base='library-data', md=True):
    d = os.path.join(root, base, cat)
    os.makedirs(d, exist_ok=True)
    idx = []
    for e in entries:
        e = dict({'source': 'LAMP', 'chapter': 'ch2', 'section': e['name'], 'page': 12, 'content': []}, **e)
        with open(os.path.join(d, e['slug'] + '.json'), 'w') as f:
            json.dump(e, f)
        if md:
            with open(os.path.join(d, e['slug'] + '.md'), 'w') as f:
                f.write(f'---\nname: {e["name"]}\n---\n# {e["name"]}\n\nThe text of {e["name"]}, as held.\n')
        idx.append({k: v for k, v in e.items() if k not in ('content', 'fields')})
    with open(os.path.join(d, '_index.json'), 'w') as f:
        json.dump(idx, f)


def library(root):
    write(root, 'skills', [
        {'slug': 'tending', 'name': 'Tending', 'fields': {'characteristic': 'Dex', 'grouped': True}},
        {'slug': 'watch', 'name': 'Watch'},
        {'slug': 'tending-beacons', 'name': 'Tending (Beacons)', 'source': 'PIER', 'relations': [{'role': 'adds-to', 'to': 'skills/tending'}]},
        {'slug': 'tending-wrecks', 'name': 'Tending (Wrecks)', 'source': 'OUT', 'relations': [{'role': 'adds-to', 'to': 'skills/tending'}]},
        {'slug': 'tending-secret', 'name': 'Tending (Secret Fires)', 'audience': 'gm', 'relations': [{'role': 'adds-to', 'to': 'skills/tending'}]}])
    write(root, 'talents', [
        {'slug': 'steady', 'name': 'Steady', 'fields': {'max': 'Toughness Bonus'}},
        {'slug': 'steady-pier', 'name': 'Steady', 'source': 'PIER', 'relations': [{'role': 'version-of', 'to': 'talents/steady'}]},
        {'slug': 'far-sight', 'name': 'Far Sight', 'source': 'OUT'}])
    write(root, 'trappings', [
        {'slug': 'lamp', 'name': 'Lamp'},
        {'slug': 'lamp-storm', 'name': 'Lamp (Storm)'},
        {'slug': 'wick', 'name': 'Wick', 'source': 'LAMP'},
        {'slug': 'wick-secret', 'name': 'Wick', 'source': 'PIER', 'audience': 'gm',
         'relations': [{'role': 'replaces', 'to': 'trappings/wick'}]}])
    write(root, 'rules', [
        {'slug': 'keeping-watch', 'name': 'Keeping Watch', 'aliases': ['Night watch'], 'content': [
            para('Keepers take the watch in turns.'), head('Turns'), para('Each turn lasts two bells.'),
            head('Long Turns', 3), para('A long turn lasts four.'),
            para('**Skills**: Watch, Tending (Wicks)'), para('They are tested at dusk.'),
            head('Relief'), para('A relief arrives at dawn.'),
            {'type': 'career_levels', 'first_level': 2, 'levels': [
                {'title': 'Warden', 'status': 'Silver 2', 'characteristics': ['I'], 'skills': ['Watch'], 'talents': ['Steady']}]},
            {'type': 'table', 'title': 'Bells', 'columns': ['Bell', 'Hour'], 'rows': [['1', 'Dusk'], ['2', 'Night']],
             'groups': [{'before': 1, 'text': 'Late'}], 'footnotes': ['* By the tower clock.']},
            {'type': 'sidebar', 'title': 'Fog', 'content': [para('In fog, ring the bell.')]}]},
        {'slug': 'watching', 'name': 'Watching the Coast', 'chapter': 'app1'},
        {'slug': 'the-hidden-stair', 'name': 'The Hidden Stair', 'audience': 'gm'}])
    with open(os.path.join(root, 'library.json'), 'w') as f:
        json.dump({'edition': '4e', 'sources': [{'code': 'LAMP', 'chapters': [{'id': 'app1', 'title': 'Appendix I: The Coast'}]}]}, f)
    c = os.path.join(root, 'campaigns', 'rock')
    os.makedirs(c)
    with open(os.path.join(c, 'campaign.json'), 'w') as f:
        json.dump({'slug': 'rock', 'sources': ['PIER', 'LAMP']}, f)
    write(root, 'rules', [{'slug': 'the-cellar', 'name': 'The Cellar', 'source': 'PIER'}], base='campaigns/rock/gm/library-data')


class ReaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        library(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def lib(self, gm=False, campaign='rock'):
        return Library(self.tmp.name, campaign, gm)

    # ---------------------------------------------------------- what is used
    def test_only_sources_in_play_and_never_gm_entries_for_players(self):
        lib = self.lib()
        self.assertIsNone(lib.find('talents', 'Far Sight'))
        self.assertIsNone(lib.find('rules', 'The Hidden Stair'))
        self.assertIsNone(lib.find('rules', 'The Cellar'))
        gm = self.lib(gm=True)
        self.assertEqual((gm.find('rules', 'The Hidden Stair'), gm.find('rules', 'The Cellar')),
                         ('rules/the-hidden-stair', 'rules/the-cellar'))
        self.assertEqual(Library(self.tmp.name).find('talents', 'Far Sight'), 'talents/far-sight')     # no campaign: everything

    def test_an_entry_another_in_play_replaces_is_not_used(self):
        lib = self.lib()
        self.assertEqual(lib.find('talents', 'Steady'), 'talents/steady-pier')
        self.assertEqual(lib.current('talents/steady'), 'talents/steady-pier')
        self.assertRaises(RefError, lib.entry, 'talents/steady')
        # A replacement only the GM sees doesn't hide the entry from players.
        self.assertEqual(lib.find('trappings', 'Wick'), 'trappings/wick')
        self.assertEqual(self.lib(gm=True).find('trappings', 'Wick'), 'trappings/wick-secret')

    def test_a_name_with_a_specialisation(self):
        lib = self.lib()
        self.assertEqual(lib.named('skills', 'Tending (Wicks)'), ('skills/tending', 'Wicks'))
        self.assertEqual(lib.named('skills', 'Watch'), ('skills/watch', None))
        self.assertEqual(lib.named('trappings', 'Lamp (Storm)'), ('trappings/lamp-storm', None))     # its own entry wins
        self.assertEqual(lib.named('trappings', 'Lamp (Brass)'), ('trappings/lamp', 'Brass'))
        self.assertEqual(lib.named('skills', 'Rowing (Fast)'), (None, None))

    # ---------------------------------------------------------- sections and text
    def test_a_section_by_heading_path_or_bold_lead(self):
        lib = self.lib()
        self.assertEqual(lib.text(lib.section('rules/keeping-watch#Turns › Long Turns')).split('\n')[0], 'A long turn lasts four.')
        self.assertEqual(lib.text(lib.section('rules/keeping-watch#Long Turns › Skills')),
                         'Watch, Tending (Wicks)\n\nThey are tested at dusk.')
        self.assertEqual(lib.find('rules', 'night watch'), 'rules/keeping-watch')            # an alias
        with self.assertRaises(RefError):
            lib.section('rules/keeping-watch#Tides')

    def test_text_of_levels_tables_and_sidebars(self):
        text = self.lib().text(self.lib().section('rules/keeping-watch#Relief'))
        self.assertIn('**Level 2: Warden** (Silver 2)\n- **Characteristics:** I\n- **Skills:** Watch\n- **Talents:** Steady', text)
        self.assertIn('| 1 | Dusk |\n| ***Late*** |  |\n| 2 | Night |\n\n* By the tower clock.', text)
        self.assertIn('> **Fog**\n>\n> In fog, ring the bell.', text)

    def test_citing(self):
        self.assertEqual(cite({'source': 'LAMP', 'chapter': 'ch2', 'section': 'Turns', 'page': 12}), '(LAMP, ch. 2 › Turns, p. 12)')
        self.assertEqual(cite({'source': 'LAMP', 'chapter': 'app1', 'name': 'Coast'}, {('LAMP', 'app1'): 'Appendix I: The Coast'}),
                         '(LAMP, Appendix I › Coast)')

    def test_a_file_that_is_not_here_is_named(self):
        os.rename(os.path.join(self.tmp.name, 'library-data', 'skills', 'watch.json'), os.path.join(self.tmp.name, 'w.json'))
        try:
            with self.assertRaises(MissingFiles) as c:
                self.lib().entry('skills/watch')
            self.assertEqual(c.exception.paths, ['library-data/skills/watch.json'])
            lenient = Library(self.tmp.name, 'rock', lenient=True)
            self.assertTrue(lenient.entry('skills/watch')['_missing'])
            self.assertEqual(lenient.missing, ['library-data/skills/watch.json'])
        finally:
            os.rename(os.path.join(self.tmp.name, 'w.json'), os.path.join(self.tmp.name, 'library-data', 'skills', 'watch.json'))

    # ---------------------------------------------------------- find_entry
    def test_find_entry_ranks_matches_and_explains_what_is_not_used(self):
        used, unused = find_entry.search(self.lib(), 'steady', ['talents'])
        self.assertEqual([h['ref'] for h in used], ['talents/steady-pier'])
        self.assertEqual([(h['ref'], h['unused']) for h in unused], [('talents/steady', "talents/steady-pier is used instead: PIER comes before LAMP in the campaign's sources")])
        self.assertEqual(find_entry.search(self.lib(), 'far sight', ['talents'])[1][0]['unused'], "OUT isn't one of the sources in play")
        self.assertEqual(find_entry.search(self.lib(), 'hidden stair', ['rules'])[1][0]['unused'], 'for the GM only')
        used, _ = find_entry.search(self.lib(), 'watch', ['rules', 'skills'])
        self.assertEqual([h['ref'] for h in used], ['skills/watch'])                    # the exact name beats names that start with it
        self.assertEqual(used[0]['cite'], '(LAMP, ch. 2 › Watch, p. 12)')
        used, _ = find_entry.search(self.lib(), 'watching', ['rules'])
        self.assertEqual(used[0]['cite'], '(LAMP, Appendix I › Watching the Coast, p. 12)')
        self.assertIn("version-of talents/steady: the same thing as that entry, as this source prints it: the campaign's source order says which is used",
                      find_entry.show(find_entry.search(self.lib(), 'steady', ['talents'])[0][0], self.lib(), False))

    def test_the_campaigns_source_order_decides_between_versions(self):
        def campaign(slug, sources):
            d = os.path.join(self.tmp.name, 'campaigns', slug)
            os.makedirs(d)
            with open(os.path.join(d, 'campaign.json'), 'w') as f:
                json.dump({'slug': slug, 'sources': sources}, f)
            return Library(self.tmp.name, slug)
        newest = self.lib()                                      # PIER, LAMP: the supplement's version
        self.assertEqual(newest.current('talents/steady'), 'talents/steady-pier')
        core = campaign('core-first', ['LAMP', 'PIER'])          # the same books, the other way round
        self.assertEqual(core.current('talents/steady-pier'), 'talents/steady')
        self.assertEqual(core.current('talents/steady'), 'talents/steady')
        rec = next(r for _, r in core.records('talents') if r['slug'] == 'steady-pier')
        self.assertEqual(core.hidden('talents', rec),
                         "talents/steady is used instead: LAMP comes before PIER in the campaign's sources")
        self.assertEqual(campaign('core-only', ['LAMP']).current('talents/steady'), 'talents/steady')
        none = Library(self.tmp.name)                            # no campaign: the one that replaces the other
        self.assertEqual(none.current('talents/steady'), 'talents/steady-pier')
        rec = next(r for _, r in none.records('talents') if r['slug'] == 'steady')
        self.assertEqual(none.hidden('talents', rec), 'talents/steady-pier is the version used')

    def test_an_entry_is_shown_with_the_entries_in_play_that_add_to_it(self):
        lib = self.lib()
        self.assertEqual(lib.added_by('skills/tending'), ['skills/tending-beacons'])     # not the one out of play, nor the GM's
        self.assertEqual(Library(self.tmp.name, 'rock', gm=True).added_by('skills/tending'),
                         ['skills/tending-beacons', 'skills/tending-secret'])
        self.assertEqual(lib.added_by('skills/watch'), [])
        used, _ = find_entry.search(lib, 'tending', ['skills'])
        self.assertEqual([h['ref'] for h in used], ['skills/tending'])
        self.assertEqual(used[0]['added_by'], [{'ref': 'skills/tending-beacons', 'name': 'Tending (Beacons)',
                                                'cite': '(PIER, ch. 2 › Tending (Beacons), p. 12)'}])
        self.assertIn('added to by `skills/tending-beacons` Tending (Beacons) (PIER, ch. 2 › Tending (Beacons), p. 12): read it as well',
                      find_entry.show(used[0], lib, False))

    def test_find_entry_as_a_command(self):
        cmd = [sys.executable, os.path.join(SCRIPTS, 'find_entry.py'), '--library', self.tmp.name, '--campaign', 'rock']
        r = subprocess.run(cmd + ['Night watch', '--category', 'rules'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('`rules/keeping-watch` (LAMP, ch. 2 › Keeping Watch, p. 12)', r.stdout)
        self.assertEqual(subprocess.run(cmd + ['tides'], capture_output=True, text=True).returncode, 1)
        self.assertIn('not a category: feats', subprocess.run(cmd + ['x', '--category', 'feats'], capture_output=True, text=True).stderr)

    # ---------------------------------------------------------- excerpt
    def test_an_excerpt_is_the_entrys_own_text_with_its_citation(self):
        lib = self.lib()
        md, why = excerpt.excerpt(lib, 'skills/watch')
        self.assertEqual((md, why), ('## Watch\n\n*(LAMP, ch. 2 › Watch, p. 12)*\n\nThe text of Watch, as held.\n', None))
        md, _ = excerpt.excerpt(lib, 'rules/keeping-watch#Turns › Long Turns')
        self.assertTrue(md.startswith('## Keeping Watch › Long Turns\n\n*(LAMP, ch. 2 › Long Turns, p. 12)*\n\nA long turn lasts four.'))

    def test_an_excerpt_the_campaign_does_not_use_is_refused_with_the_reason(self):
        lib = self.lib()
        self.assertEqual(excerpt.excerpt(lib, 'talents/steady'), (None, "not used in this campaign: talents/steady-pier is used instead: PIER comes before LAMP in the campaign's sources"))
        self.assertEqual(excerpt.excerpt(lib, 'rules/the-hidden-stair'), (None, 'not used in this campaign: for the GM only'))
        self.assertEqual(excerpt.excerpt(lib, 'rules/tides'), (None, 'not in the library'))
        self.assertIsNotNone(excerpt.excerpt(self.lib(gm=True), 'rules/the-hidden-stair')[0])

    def test_the_excerpt_command_prints_what_it_wrote_and_never_the_text(self):
        out = os.path.join(self.tmp.name, 'out', 'wording.md')
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'excerpt.py'), 'skills/watch', 'talents/steady', '--library',
                            self.tmp.name, '--campaign', 'rock', '--out', out], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)                               # one ref was refused
        self.assertIn('skills/watch', r.stdout)
        self.assertNotIn('as held', r.stdout + r.stderr)
        self.assertIn('talents/steady: not used in this campaign', r.stderr)
        with open(out) as f:
            self.assertIn('The text of Watch, as held.', f.read())


class Names(unittest.TestCase):
    def test_accents_quotes_and_spaces_do_not_make_names_differ(self):
        self.assertEqual(norm('Language  (Qu\u00e9lar\u00edn)'), norm('language (Quelarin)'))
        self.assertEqual(norm('Ring\u2019s Edge'), "ring's edge")


if __name__ == '__main__':
    unittest.main()
