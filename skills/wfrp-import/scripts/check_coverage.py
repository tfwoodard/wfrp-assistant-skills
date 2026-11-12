#!/usr/bin/env python3
"""Check that a chapter's converted entries lost no words of its pages.

    check_coverage.py LAYOUT.json OUT_DIR [--ignore WORD ...]

Counts every word of the chapter's lines in LAYOUT.json (from pdf_layout.py;
page furniture left out) and every word in the entries a converter wrote to
OUT_DIR (each <slug>.json's name and content), plus the strings its
`_report.json` lists under `left_out` (art credits, captions, anything left out
on purpose). A word the pages have more often than the output is listed with
the line it came from. Exit status 1 when any word is missing.

`--ignore` excuses a word, and the output says every word it excused and how
often: no silent exceptions.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

WORD = re.compile(r"[\w’'+−–-]+")
SKIP_KEYS = {'slug', 'source', 'chapter', 'section', 'page', 'level', 'type', 'id', 'relations', 'audience',
             'kind', 'edition', 'ordered', 'before', 'start', 'span', 'data', 'fields'}


def words(s):
    """Lower-cased words, split at hyphens too, so a word hyphenated across two lines on the
    page ("tried-" / "and-tested") counts the same as the joined word ("tried-and-tested")."""
    s = re.sub(r'\*+', ' ', s).replace('\u00ad', '').lower()
    out = []
    for w in WORD.findall(s):
        out += [p.strip("’'–") for p in re.split(r'[-−]', w) if p.strip("’'–")]
    return out


def strings(x, key=None):
    """Every printed string in an entry: names, text, cells and labels, but not its bookkeeping
    fields or the typed `data` copy of a table (that would count its cells twice)."""
    if key in SKIP_KEYS:
        return
    if isinstance(x, str):
        yield x
    elif isinstance(x, (int, float)) and not isinstance(x, bool) and key not in (None,):
        yield str(x)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v, '')
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from strings(v, k)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('layout')
    ap.add_argument('out')
    ap.add_argument('--ignore', nargs='*', default=[])
    a = ap.parse_args(argv)

    with open(a.layout, encoding='utf-8') as f:
        doc = json.load(f)
    page = collections.Counter()
    where = {}
    for l in doc['lines']:
        if l.get('furniture'):
            continue
        for w in words(l['text']):
            page[w] += 1
            where.setdefault(w, f'p{l["page"]}: {l["text"]}')

    got = collections.Counter()
    for p in sorted(glob.glob(os.path.join(a.out, '*.json'))):
        name = os.path.basename(p)
        with open(p, encoding='utf-8') as f:
            data = json.load(f)
        if name == '_report.json':
            for s in data.get('left_out', []):
                got.update(words(s if isinstance(s, str) else s.get('text', '')))
        elif not name.startswith('_'):
            for s in strings({'name': data.get('name', ''), 'content': data.get('content', [])}):
                got.update(words(s))

    ignored = {w.lower() for w in a.ignore}
    missing, excused = [], []
    for w, n in sorted(page.items()):
        short = n - got.get(w, 0)
        if short > 0:
            (excused if w in ignored else missing).append((w, short))
    for w, n in excused:
        print(f'excused: {w!r} x{n} (--ignore)')
    for w, n in missing:
        print(f'missing: {w!r} x{n}  first seen {where[w]}')
    if not missing:
        print(f'every word of {sum(page.values())} is accounted for')
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main())
