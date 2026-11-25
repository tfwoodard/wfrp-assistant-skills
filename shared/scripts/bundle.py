#!/usr/bin/env python3
"""The library bundle: the library's rules data in one plain-text file (layout §1, "Library bundle").

    bundle.py make <library root> [--out library-bundle.json]     the Librarian, after an import
    bundle.py unpack <library-bundle.json> <folder>                 a player's agent, in its sandbox
    bundle.py check <library-bundle.json> <library.json>            is the bundle current?

An agent whose scripts can't see Google Drive (ChatGPT, the Gemini app) attaches this one file and
unpacks it into a folder the scripts can read as a library root. It holds `library.json` and every
file under `library-data/` (each entry's .json and .md, and each category's `_index.json`), and
nothing from `campaigns/`: campaign files change between sessions and `gm/` is the GM's alone, so an
agent reads those from Drive and puts them under `<folder>/campaigns/<slug>/` itself.

`make` also writes the bundle's stamp ("bundle": {"made", "imports", "files"}) into the library's
`library.json`, so an agent that reads `library.json` from Drive can tell whether the bundle it has
is the current one (`check`).
"""
import argparse, datetime, json, os, sys

FORMAT = 1


def stamp_of(root):
    log = os.path.join(root, 'library-data', '_import-log.json')
    imports = 0
    if os.path.exists(log):
        with open(log, encoding='utf-8') as f:
            data = json.load(f)
        imports = len(data if isinstance(data, list) else data.get('imports', data.get('log', [])))
    return imports


def make(root, out=None, now=None):
    """Write the bundle of ROOT to OUT (default ROOT/library-bundle.json) and its stamp into ROOT's
    library.json. Returns (out, stamp)."""
    with open(os.path.join(root, 'library.json'), encoding='utf-8') as f:
        raw = f.read()
        library = json.loads(raw)
    if not library.get('wfrp_library'):
        raise SystemExit(f'{root} is not a library (library.json without "wfrp_library": true)')
    files = {}
    data = os.path.join(root, 'library-data')
    for cat in sorted(os.listdir(data)) if os.path.isdir(data) else []:
        d = os.path.join(data, cat)
        if cat.startswith('.') or not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not (name.endswith('.json') or name.endswith('.md')):
                continue
            with open(os.path.join(d, name), encoding='utf-8') as f:
                files[f'library-data/{cat}/{name}'] = f.read()
    for name in sorted(os.listdir(data)) if os.path.isdir(data) else []:
        if name.endswith('.json') and os.path.isfile(os.path.join(data, name)):
            with open(os.path.join(data, name), encoding='utf-8') as f:
                files[f'library-data/{name}'] = f.read()
    stamp = {'made': (now or datetime.datetime.now(datetime.timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ'),
             'imports': stamp_of(root), 'files': len(files) + 1}
    library['bundle'] = stamp
    text = json.dumps(library, ensure_ascii=False, indent=2) + '\n'
    files['library.json'] = text
    out = out or os.path.join(root, 'library-bundle.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'wfrp_library_bundle': FORMAT, 'stamp': stamp, 'files': dict(sorted(files.items()))},
                  f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
    with open(os.path.join(root, 'library.json'), 'w', encoding='utf-8') as f:
        f.write(text)
    return out, stamp


def load(path):
    with open(path, encoding='utf-8') as f:
        b = json.load(f)
    if b.get('wfrp_library_bundle') != FORMAT:
        raise SystemExit(f'{path} is not a library bundle this script reads (format {b.get("wfrp_library_bundle")})')
    return b


def unpack(path, folder):
    """Write every file of the bundle under FOLDER; returns how many. Paths that would leave FOLDER
    are refused."""
    b = load(path)
    base = os.path.abspath(folder)
    n = 0
    for rel, text in b['files'].items():
        dest = os.path.abspath(os.path.join(base, rel))
        if not dest.startswith(base + os.sep) or rel.startswith(('campaigns/', 'campaigns\\')):
            raise SystemExit(f'the bundle names a file it may not hold: {rel}')
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(text)
        n += 1
    return n


def check(path, library_json):
    """(current?, what to say). LIBRARY_JSON is the library.json read from Drive, a path or its text."""
    b = load(path)
    if os.path.exists(library_json):
        with open(library_json, encoding='utf-8') as f:
            library_json = f.read()
    stamp = (json.loads(library_json).get('bundle') or {})
    if stamp == b['stamp']:
        return True, f'the bundle is current (made {stamp["made"]}, after {stamp["imports"]} imports)'
    if not stamp:
        return False, "the library's library.json has no bundle stamp: ask the Librarian to make the bundle"
    return False, (f'the bundle is out of date: it was made {b["stamp"]["made"]}, the library\'s is from {stamp["made"]}. '
                   'Attach the library-bundle.json that is in the library now')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('make'); p.add_argument('root'); p.add_argument('--out')
    p = sub.add_parser('unpack'); p.add_argument('bundle'); p.add_argument('folder')
    p = sub.add_parser('check'); p.add_argument('bundle'); p.add_argument('library_json')
    a = ap.parse_args(argv)
    if a.cmd == 'make':
        out, stamp = make(a.root, a.out)
        print(f'{out}: {stamp["files"]} files, made {stamp["made"]}; library.json stamped: upload both')
    elif a.cmd == 'unpack':
        n = unpack(a.bundle, a.folder)
        print(f'{n} files in {a.folder}: a library root for the scripts (--library {a.folder}). '
              'Campaign files are not in the bundle: read them from Drive into campaigns/<slug>/')
    else:
        ok, said = check(a.bundle, a.library_json)
        print(said)
        return 0 if ok else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
