#!/usr/bin/env python3
"""One-off: rewrite the version mark's old name, "replaces", as "version-of" (ADR 0006) in a local
copy of the library: every entry's .json and .md, every index, and every chapter plan.

    migrate_version_of.py LIBRARY_ROOT [--write]

Without --write it only lists what would change. Only a relation's "role" is touched: the same
word anywhere else (a career level that "replaces" another, prose) is left alone. An entry's .md
is rendered again from its .json, and must have been what the renderer gives before the change,
or the entry is listed as not migrated instead of being overwritten. Prints the files changed,
relative to LIBRARY_ROOT, one per line, for uploading and checking.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_entry import render  # noqa: E402


def rename(x):
    """Rewrite the role in place wherever a relation ({"role", "to"}) appears; returns how many."""
    n = 0
    if isinstance(x, dict):
        if x.get('role') == 'replaces' and 'to' in x:
            x['role'] = 'version-of'
            n += 1
        n += sum(rename(v) for v in x.values())
    elif isinstance(x, list):
        n += sum(rename(v) for v in x)
    return n


def load(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def main():
    args = [a for a in sys.argv[1:] if a != '--write']
    if len(args) != 1:
        sys.exit(__doc__)
    root, write = args[0], '--write' in sys.argv
    changed, skipped, marks = [], [], 0
    for base, _, files in sorted(os.walk(root)):
        rel = os.path.relpath(base, root).replace(os.sep, '/')
        parts = rel.split('/')
        if not ('library-data' in parts or (parts[-1:] == ['plans'] and 'sources' in parts)):
            continue
        for name in sorted(files):
            if not name.endswith('.json'):
                continue
            path = os.path.join(base, name)
            text = load(path)
            if '"replaces"' not in text:
                continue
            data = json.loads(text)
            before = json.loads(text)
            n = rename(data)
            if not n:
                continue
            entry = 'library-data' in parts and not name.startswith('_')
            md = os.path.splitext(path)[0] + '.md'
            if entry and (not os.path.exists(md) or load(md) != render(before)):
                skipped.append(f'{rel}/{name}: its .md is missing or isn\'t what the renderer gives; not migrated')
                continue
            # each kind of file as its writer formats it, so only the role changes
            if entry:
                out = json.dumps(data, ensure_ascii=False, indent=1) + '\n'
            elif name == '_index.json':
                out = '[\n' + ',\n'.join('  ' + json.dumps(r, ensure_ascii=False) for r in data) + '\n]\n'
            else:
                out = text.replace('"role": "replaces"', '"role": "version-of"')
                if json.loads(out) != data:
                    skipped.append(f'{rel}/{name}: the role is written in a way this tool doesn\'t rewrite; not migrated')
                    continue
            if entry and out.replace('"role": "version-of"', '"role": "replaces"') != text or \
                    name == '_index.json' and out.replace('"role": "version-of"', '"role": "replaces"') != text:
                skipped.append(f'{rel}/{name}: isn\'t formatted as its writer formats it; not migrated')
                continue
            marks += n
            changed.append(f'{rel}/{name}')
            if write:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(out)
            if entry:
                changed.append(f'{rel}/{os.path.basename(md)}')
                if write:
                    with open(md, 'w', encoding='utf-8') as f:
                        f.write(render(data))
    print('\n'.join(changed))
    print(f'{marks} marks in {len(changed)} files {"rewritten" if write else "to rewrite (run again with --write)"}; '
          f'{len(skipped)} not migrated', file=sys.stderr)
    for s in skipped:
        print('  ' + s, file=sys.stderr)
    return 1 if skipped else 0


if __name__ == '__main__':
    sys.exit(main())
