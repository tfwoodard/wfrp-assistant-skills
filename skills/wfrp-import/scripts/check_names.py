#!/usr/bin/env python3
"""Check that every new entry sharing a name with another entry has a decision on it.

    check_names.py LIBRARY_DATA_DIR OUT_DIR/_records.json [more _records.json ...]

Names are compared allowing for case, a leading "The", words in brackets, punctuation and a
plural "s" or "es" ("Witch!" and "Witches" match "Witch"). The other entry can be in any
category of the library (every <category>/_index.json under LIBRARY_DATA_DIR) or among the new
records themselves. A new record must have a `relations` entry pointing at each entry it shares a
name with (layout §4), or the pair is listed and the exit status is 1. Pairs that have one are
listed too, so the output says what was checked.
"""
import json
import os
import re
import sys


def name_key(name):
    n = re.sub(r'\([^)]*\)', '', name.lower())
    n = re.sub(r'^\s*the\s+', '', n)
    n = re.sub(r'[^\w ]', '', n).strip()
    return re.sub(r'(es|s)$', '', n)


def check(library_dir, record_files):
    seen = {}
    for cat in sorted(os.listdir(library_dir)):
        p = os.path.join(library_dir, cat, '_index.json')
        if os.path.isfile(p):
            with open(p, encoding='utf-8') as f:
                for r in json.load(f):
                    seen.setdefault(name_key(r['name']), []).append((f'{cat}/{r["slug"]}', r))
    new = []
    for path in record_files:
        with open(path, encoding='utf-8') as f:
            new += json.load(f)
    new_ids = {f'{r["_category"]}/{r["slug"]}' for r in new}
    for k in seen:      # a re-import replaces its own earlier records
        seen[k] = [(i, r) for i, r in seen[k] if i not in new_ids]
    missing, decided = [], []
    for r in new:
        me = f'{r["_category"]}/{r["slug"]}'
        to = {x['to'] for x in r.get('relations', [])}
        for other, o in seen.get(name_key(r['name']), []):
            if other in to or me in {x['to'] for x in o.get('relations', [])}:
                decided.append((me, other))
            else:
                missing.append((me, other))
        seen.setdefault(name_key(r['name']), []).append((me, r))
    return missing, decided


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    missing, decided = check(argv[0], argv[1:])
    for me, other in decided:
        print(f'ok       {me} and {other}: related')
    for me, other in missing:
        print(f'MISSING  {me} shares a name with {other}: give it a relation')
    print(f'{len(decided)} shared names related, {len(missing)} without a decision')
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main())
