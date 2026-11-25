"""The repo's packs/ folder: every plan pack is filed under the PDF it was made from, and holds no
text but the tool's own words, its source code and the PDF's icon fonts (plan_pack.py)."""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PACKS = os.path.join(ROOT, 'packs')
sys.path.insert(0, os.path.join(ROOT, 'skills', 'wfrp-import', 'scripts'))
import plan_pack  # noqa: E402

HEX = re.compile(r'^[0-9a-f]{20}$')
EDITION_KEYS = {'source', 'title', 'pdf_sha256', 'pdf_bytes', 'chapters'}


def editions():
    if not os.path.isdir(PACKS):
        return
    for src in sorted(os.listdir(PACKS)):
        d = os.path.join(PACKS, src)
        if os.path.isdir(d):
            for v in sorted(os.listdir(d)):
                yield src, v, os.path.join(d, v)


def readable(v, path, said):
    """Every string in a pack's plan that isn't a fingerprint, a tool word or a plain part."""
    if path and path[0] in plan_pack.PLAIN_TREES:
        return
    if isinstance(v, str):
        if path and path[-1] in ('#', '#slug', '#n'):
            if not HEX.match(v):
                said.append(('/'.join(map(str, path)), v))
            return
        if path and path[-1] == 'in' or plan_pack.TOOL_WORD.match(v) or not re.search(r'[^\W\d_]', v):
            return
        said.append(('/'.join(map(str, path)), v))
    elif isinstance(v, list):
        for i, x in enumerate(v):
            readable(x, path + [i], said)
    elif isinstance(v, dict):
        for k, x in v.items():
            if not (k in ('#', '#slug', '#n', '#w') or plan_pack.TOOL_WORD.match(k) or re.match(r'^\d+(\.\d+)?$', k)
                    or re.match(r'^#(:|slug:([a-z-]+/)?)[0-9a-f]{20}$', k) or k.startswith('#w:')):
                said.append(('/'.join(map(str, path + [k])), k))
            if k.startswith('#w:'):
                readable({'#w': json.loads(k[3:])}, path + ['#w'], said)
            readable(x, path + [k], said)


class PacksTreeTest(unittest.TestCase):
    def test_each_folder_is_one_pdf(self):
        for src, v, d in editions():
            with self.subTest(folder=f'{src}/{v}'):
                with open(os.path.join(d, 'edition.json'), encoding='utf-8') as f:
                    ed = json.load(f)
                self.assertLessEqual(set(ed), EDITION_KEYS)
                self.assertEqual(ed['source'], src)
                self.assertEqual(ed['pdf_sha256'][:12], v)
                files = {n[:-5] for n in os.listdir(d) if n.endswith('.json') and n != 'edition.json'}
                self.assertEqual(files, set(ed['chapters']))
                for c in files:
                    with open(os.path.join(d, c + '.json'), encoding='utf-8') as f:
                        pack = json.load(f)
                    self.assertLessEqual(set(pack), plan_pack.PACK_KEYS)
                    self.assertEqual((pack['source'], pack['name'], pack['pdf_sha256']), (src, c, ed['pdf_sha256']))
                    self.assertEqual(pack['chapter'], ed['chapters'][c]['chapter'])
                    self.assertEqual(len(pack['left_out']), ed['chapters'][c]['left_out'])

    def test_no_pack_holds_text(self):
        for src, v, d in editions():
            for n in sorted(os.listdir(d)):
                if n == 'edition.json' or not n.endswith('.json'):
                    continue
                with self.subTest(pack=f'{src}/{v}/{n}'):
                    with open(os.path.join(d, n), encoding='utf-8') as f:
                        pack = json.load(f)
                    said = []
                    readable(pack['plan'], [], said)
                    said = [s for s in said if s[0] not in ('source', 'chapter')]
                    self.assertEqual(said, [], 'readable text in a pack')
                    for p in pack['left_out']:
                        for step in p.split('/'):
                            self.assertTrue(step.isdigit() or plan_pack.TOOL_WORD.match(step)
                                            or re.match(r'^#[0-9a-f]{20}$', step) or re.match(r'^\d+\.\d+$', step), p)
                    for line in pack['layout'].get('margin_lines', []):
                        self.assertIsInstance(line, dict, 'a margin line in words')


if __name__ == '__main__':
    unittest.main()
