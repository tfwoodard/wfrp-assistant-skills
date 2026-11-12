#!/usr/bin/env python3
"""Progress journal for library imports, kept in the session's scratch directory.

A session can stop partway through an import (a usage limit, a closed laptop)
and resume with no memory of what it did. The scratch directory survives, so
record each finished step here as it happens, and run `show` before doing any
import work: it says what is done and what comes next.

    import_journal.py --dir SCRATCH drive --root ID --library-data ID --folder careers=ID \\
        --file library.json=ID:SIZE --file _import-log.json=ID:SIZE --file careers/_index.json=ID:SIZE
    import_journal.py --dir SCRATCH start crb-ch3 --source CRB --category careers \\
        --pages 30-109 --page ch3-layout.json
    import_journal.py --dir SCRATCH phase crb-ch3 converted --out out-ch3
    import_journal.py --dir SCRATCH note crb-ch3 "Rat Catcher's table transcribed from the page image"
    import_journal.py --dir SCRATCH uploaded crb-ch3 rat-catcher=1nAq...:2435 witch-hunter=1zJr...:3269
    import_journal.py --dir SCRATCH phase crb-ch3 merged
    import_journal.py --dir SCRATCH bookkeeping careers/_index.json NEWID:SIZE   # old ID queued for trash
    import_journal.py --dir SCRATCH trashed OLDID
    import_journal.py --dir SCRATCH clean crb-ch3 [extra scratch files...]
    import_journal.py --dir SCRATCH done crb-ch3
    import_journal.py --dir SCRATCH show
    import_journal.py --dir SCRATCH doing "uploading career entries, part 2 of 4"   # before a step
    import_journal.py --dir SCRATCH waiting "Asked: split the Chapter 1 sections how?"
    import_journal.py --dir SCRATCH answered "One entry per section"
    import_journal.py --dir SCRATCH repo feat/glossary-converter --pr 20 --status open
    import_journal.py show --hook        # finds the journal itself; silent when nothing is open

Phases, in order: read, converted, uploading, uploaded, merged, bookkeeping, done.
`uploaded` checks each size against the converter's output file and refuses a mismatch.
`doing` notes a step before it starts; the next record of progress clears it, so a
step still listed after a stop may be half done. `waiting` holds the question put
to the Librarian until `answered` records the reply. `repo` tracks branches and
pull requests. `show` prints these first.
`clean` deletes the chapter's saved page, its converter output, and any other
scratch files named, all inside --dir; it lists what it deleted.
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone

PHASES = ['read', 'converted', 'uploading', 'uploaded', 'merged', 'bookkeeping', 'done']
NEXT = {
    'read': 'run the converter on the saved page and read its report',
    'converted': 'upload the entries (check Drive for each before uploading)',
    'uploading': 'upload the remaining entries listed below',
    'uploaded': 'run merge_import.py into new/',
    'merged': 'upload the bookkeeping files from new/ and trash the old ones',
    'bookkeeping': 'trash the old bookkeeping files listed below, clean the chapter scratch, mark done',
}


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def load(d):
    p = os.path.join(d, 'journal.json')
    if not os.path.exists(p):
        j = {}
    else:
        with open(p, encoding='utf-8') as f:
            j = json.load(f)
    for k, v in (('drive', {}), ('chapters', {}), ('trash', []), ('repo', {}), ('asked', [])):
        j.setdefault(k, v)
    return j


def find_journal():
    """The scratch directory holding journal.json: under the working directory, its
    parent (a session whose working directory holds the repo clone), or home."""
    cwd = os.getcwd()
    for base in dict.fromkeys((cwd, os.path.dirname(cwd), os.path.expanduser('~'))):
        for root, dirs, files in os.walk(base):
            if root[len(base):].count(os.sep) >= 3:
                dirs[:] = []
            dirs[:] = [x for x in dirs if not x.startswith('.') and x not in ('node_modules',)]
            if 'journal.json' in files:
                return root
    return None


def is_open(j):
    return bool(j.get('waiting') or j.get('doing') or j['trash']
                or any(c['phase'] != 'done' for c in j['chapters'].values())
                or any(r.get('status') == 'open' for r in j['repo'].values()))


def save(d, j):
    p = os.path.join(d, 'journal.json')
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(j, f, indent=1, ensure_ascii=False)
        f.write('\n')
    os.replace(tmp, p)  # never leave a half-written journal


def id_size(v):
    i, _, s = v.rpartition(':')
    if not i or not s.isdigit():
        sys.exit(f'expected ID:SIZE, got {v!r}')
    return i, int(s)


def chapter(j, name):
    if name not in j['chapters']:
        sys.exit(f'no chapter {name!r} in the journal; run start first')
    return j['chapters'][name]


def expected(d, ch):
    """slug -> byte size of each entry the converter wrote for this chapter."""
    out = ch.get('out')
    if not out:
        return {}
    out = out if os.path.isabs(out) else os.path.join(d, out)
    if not os.path.isdir(out):
        return {}
    return {f[:-3]: os.path.getsize(os.path.join(out, f))
            for f in sorted(os.listdir(out)) if f.endswith('.md')}


def show(d, j):
    if j.get('waiting'):
        w = j['waiting']
        print(f'WAITING FOR THE LIBRARIAN (asked {w["at"]}): {w["text"]}')
        print('  Their next message may be the answer: record it with `answered`.')
    if j.get('doing'):
        print(f'STEP UNDER WAY when last recorded ({j["doing"]["at"]}): {j["doing"]["text"]}')
        print('  It may be half done: check before redoing it.')
    open_repo = {b: r for b, r in j['repo'].items() if r.get('status') == 'open'}
    if open_repo:
        print('Open repo work:')
        for b, r in sorted(open_repo.items()):
            print(f'  {b}' + (f' (PR #{r["pr"]})' if r.get('pr') else '') + ': open; check whether it was merged')
    if j['asked']:
        print('Recent decisions by the Librarian:')
        for a in j['asked'][-5:]:
            print(f'  {a["at"]}: {a["question"]} -> {a["answer"]}')
    dr = j['drive']
    if dr:
        print('Drive:')
        for k in ('root', 'library-data'):
            if k in dr:
                print(f'  {k}: {dr[k]}')
        for k, v in sorted(dr.get('folders', {}).items()):
            print(f'  folder {k}: {v}')
        for k, v in sorted(dr.get('files', {}).items()):
            print(f'  current {k}: {v["id"]} ({v["size"]} bytes)')
    if j['trash']:
        print('Still to trash (old bookkeeping files):')
        for t in j['trash']:
            print(f'  {t["id"]}  {t["file"]}')
    open_chapters = [(n, c) for n, c in j['chapters'].items() if c['phase'] != 'done']
    if not open_chapters:
        print('No import in progress.')
    for name, ch in open_chapters:
        print(f'\n{name} ({ch.get("source", "")}, {ch.get("category", "")}): phase {ch["phase"]}'
              f' since {ch["updated"]}')
        for k in ('pages', 'page', 'out'):
            if ch.get(k):
                print(f'  {k}: {ch[k]}')
        for n in ch.get('notes', []):
            print(f'  note: {n}')
        exp = expected(d, ch)
        up = ch.get('uploaded', {})
        if exp:
            todo = [s for s in exp if s not in up]
            print(f'  entries: {len(up)} of {len(exp)} uploaded')
            if todo and ch['phase'] in ('converted', 'uploading'):
                print('  not yet uploaded: ' + ', '.join(todo))
                print('  (one of these may have reached Drive just before the stop: search Drive'
                      ' for its title first, and record it if the size matches)')
        print(f'  next: {NEXT.get(ch["phase"], "")}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', help='scratch directory holding journal.json (show finds it if omitted)')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('drive', help='record library folder IDs and current bookkeeping files')
    p.add_argument('--root')
    p.add_argument('--library-data')
    p.add_argument('--folder', action='append', default=[], metavar='CATEGORY=ID')
    p.add_argument('--file', action='append', default=[], metavar='PATH=ID:SIZE')

    p = sub.add_parser('start', help='begin a chapter')
    p.add_argument('chapter')
    p.add_argument('--source', required=True)
    p.add_argument('--category', required=True)
    p.add_argument('--pages', help="the chapter's printed page range, e.g. 30-109")
    p.add_argument('--page', help='saved page text file')

    p = sub.add_parser('phase', help='mark a chapter step finished')
    p.add_argument('chapter')
    p.add_argument('phase', choices=PHASES)
    p.add_argument('--out', help="the converter's output directory")

    p = sub.add_parser('note', help='record a hand edit or anything a resumed session must know')
    p.add_argument('chapter')
    p.add_argument('text')

    p = sub.add_parser('uploaded', help='record uploaded entries as SLUG=ID:SIZE')
    p.add_argument('chapter')
    p.add_argument('items', nargs='+')

    p = sub.add_parser('bookkeeping', help='record a new bookkeeping upload; queues the old ID for trash')
    p.add_argument('file', help='e.g. careers/_index.json, _import-log.json, library.json')
    p.add_argument('new', metavar='ID:SIZE')

    p = sub.add_parser('trashed', help='record that an old file was trashed')
    p.add_argument('id')

    p = sub.add_parser('done', help='mark a chapter finished')
    p.add_argument('chapter')

    p = sub.add_parser('clean', help="delete a chapter's scratch files (page, converter output, extras)")
    p.add_argument('chapter')
    p.add_argument('paths', nargs='*', help='other scratch files or directories to delete')
    p = sub.add_parser('doing', help='note a step before starting it (cleared by the next record)')
    p.add_argument('text', nargs='?')
    p.add_argument('--clear', action='store_true')
    p = sub.add_parser('waiting', help='record the question put to the Librarian')
    p.add_argument('text')
    p = sub.add_parser('answered', help="record the Librarian's answer to the waiting question")
    p.add_argument('text')
    p = sub.add_parser('repo', help='record a branch and its pull request')
    p.add_argument('branch')
    p.add_argument('--pr', type=int)
    p.add_argument('--status', choices=['open', 'merged', 'closed'], default='open')
    p = sub.add_parser('show', help='print what is done and what comes next')
    p.add_argument('--hook', action='store_true',
                   help='for a session or prompt hook: find the journal, print nothing unless work is open')

    a = ap.parse_args()
    d = a.dir
    if d is None:
        if a.cmd != 'show':
            sys.exit('--dir is required except for show')
        d = find_journal()
        if d is None:
            if not a.hook:
                print('No journal found.')
            return
    j = load(d)

    if a.cmd == 'show':
        if a.hook and not is_open(j):
            return
        try:
            if a.hook:
                print(f'IMPORT JOURNAL ({os.path.join(d, "journal.json")}): read this before replying.')
            show(d, j)
        except BrokenPipeError:  # output cut short (show | head): not an error
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return
    if a.cmd == 'clean':
        ch = chapter(j, a.chapter)
        if PHASES.index(ch['phase']) < PHASES.index('bookkeeping'):
            sys.exit(f'{a.chapter} is at phase {ch["phase"]}; clean only after its bookkeeping')
        root = os.path.realpath(d)
        targets = [x for x in (ch.get('page'), ch.get('out')) if x] + a.paths
        gone = []
        for t in targets:
            p = os.path.realpath(t if os.path.isabs(t) else os.path.join(d, t))
            if os.path.commonpath([root, p]) != root or p == root:
                sys.exit(f'{t}: not inside the scratch directory {d}; nothing deleted')
            if os.path.basename(p) == 'journal.json':
                sys.exit('refusing to delete the journal; nothing deleted')
        for t in targets:
            p = os.path.realpath(t if os.path.isabs(t) else os.path.join(d, t))
            if os.path.isdir(p):
                shutil.rmtree(p)
                gone.append(t + '/')
            elif os.path.exists(p):
                os.remove(p)
                gone.append(t)
        print('Deleted: ' + (', '.join(gone) if gone else 'nothing (already gone)'))
        ch.setdefault('notes', []).append('scratch cleaned: ' + (', '.join(gone) or 'nothing'))
        ch['updated'] = now()
        save(d, j)
        return
    if a.cmd == 'doing':
        if a.clear or not a.text:
            j.pop('doing', None)
        else:
            j['doing'] = {'text': a.text, 'at': now()}
        save(d, j)
        return
    if a.cmd == 'waiting':
        j['waiting'] = {'text': a.text, 'at': now()}
        save(d, j)
        return
    if a.cmd == 'answered':
        q = j.pop('waiting', None)
        j['asked'].append({'question': q['text'] if q else '(no waiting question recorded)',
                           'answer': a.text, 'at': now()})
        save(d, j)
        return
    if a.cmd == 'repo':
        r = j['repo'].setdefault(a.branch, {})
        if a.pr:
            r['pr'] = a.pr
        r['status'] = a.status
        r['at'] = now()
        save(d, j)
        return
    if a.cmd != 'note':
        j.pop('doing', None)  # a record of progress finishes the step that was under way
    if a.cmd == 'drive':
        dr = j['drive']
        if a.root:
            dr['root'] = a.root
        if a.library_data:
            dr['library-data'] = a.library_data
        for f in a.folder:
            k, _, v = f.partition('=')
            dr.setdefault('folders', {})[k] = v
        for f in a.file:
            k, _, v = f.partition('=')
            i, s = id_size(v)
            dr.setdefault('files', {})[k] = {'id': i, 'size': s}
    elif a.cmd == 'start':
        if a.chapter in j['chapters'] and j['chapters'][a.chapter]['phase'] != 'done':
            sys.exit(f'{a.chapter} is already in progress (phase {j["chapters"][a.chapter]["phase"]}); '
                     'run show and resume it')
        j['chapters'][a.chapter] = {'source': a.source, 'category': a.category, 'pages': a.pages,
                                    'page': a.page, 'phase': 'read', 'updated': now(),
                                    'notes': [], 'uploaded': {}}
    elif a.cmd == 'phase':
        ch = chapter(j, a.chapter)
        if a.out:
            ch['out'] = a.out
        if a.phase in ('uploaded', 'merged', 'bookkeeping', 'done'):
            missing = [s for s in expected(d, ch) if s not in ch['uploaded']]
            if missing:
                sys.exit(f'{len(missing)} entries not recorded as uploaded: {", ".join(missing)}')
        ch['phase'] = a.phase
        ch['updated'] = now()
    elif a.cmd == 'note':
        ch = chapter(j, a.chapter)
        ch['notes'].append(a.text)
        ch['updated'] = now()
    elif a.cmd == 'uploaded':
        ch = chapter(j, a.chapter)
        exp = expected(d, ch)
        bad = []
        for it in a.items:
            slug, _, v = it.partition('=')
            i, s = id_size(v)
            if exp and slug not in exp:
                bad.append(f'{slug}: not in the converter output')
            elif exp and exp[slug] != s:
                bad.append(f'{slug}: Drive size {s}, local {exp[slug]}')
            else:
                ch['uploaded'][slug] = {'id': i, 'size': s}
        if ch['phase'] in ('read', 'converted'):
            ch['phase'] = 'uploading'
        ch['updated'] = now()
        if bad:
            save(d, j)
            sys.exit('not recorded:\n  ' + '\n  '.join(bad))
    elif a.cmd == 'bookkeeping':
        i, s = id_size(a.new)
        files = j['drive'].setdefault('files', {})
        old = files.get(a.file)
        if old and old['id'] != i:
            j['trash'].append({'file': a.file, 'id': old['id']})
        files[a.file] = {'id': i, 'size': s}
    elif a.cmd == 'trashed':
        j['trash'] = [t for t in j['trash'] if t['id'] != a.id]
    elif a.cmd == 'done':
        ch = chapter(j, a.chapter)
        if j['trash']:
            sys.exit('old bookkeeping files still to trash: '
                     + ', '.join(t['id'] for t in j['trash']))
        missing = [s for s in expected(d, ch) if s not in ch['uploaded']]
        if missing:
            sys.exit(f'{len(missing)} entries not recorded as uploaded: {", ".join(missing)}')
        ch['phase'] = 'done'
        ch['updated'] = now()
    save(d, j)


if __name__ == '__main__':
    main()
