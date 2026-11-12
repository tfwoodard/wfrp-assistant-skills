#!/usr/bin/env python3
"""Build the new versions of a library's bookkeeping files after an import.

The Drive connector can't edit files in place, so each import ends with the
same three rewrites (SKILL.md, "Write"):

  <category>/_index.json   merge the new index records, sorted by slug
  _import-log.json         append one record for this run
  library.json             set the chapter's status, date and notes

This script does those rewrites locally, from copies of the current files, and
writes the new versions to --out for upload. It keeps each file's layout (one
index or log record per line; library.json untouched except the one chapter
line), so an upload changes only what the import changed.

Inputs may be the JSON file itself, the base64 `content` the Drive connector's
download returns, or that whole download result saved as JSON.

Usage, after every batch of 10-20 entries (index only):
  merge_import.py --out DIR --index _index.json --records _records.json --edition 4e \\
      --slugs dao,darkmantle,...

At the end of the run (index, log, and chapter status):
  merge_import.py --out DIR --index _index.json --records _records.json --edition 4e \\
      --log _import-log.json --library library.json \\
      --source CRB --chapter ch3 --category careers \\
      --log-notes "..." --chapter-notes "..." [--failed N] [--date YYYY-MM-DD]

A re-import of the same source and chapter replaces that chapter's records:
records with the same slug count as updated, and records the new import no
longer has are removed from the index and listed, so their entry files can be
moved to the trash. A slug that belongs to a different source or chapter is an
error: the converter should have given it a source suffix (--taken).

Prints what changed and the byte size of every file written. Exit status 2 if
an input can't be used.
"""
import argparse
import base64
import binascii
import datetime
import json
import os
import re
import sys


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def read_text(path):
    """The file's JSON text, decoding a Drive download (base64) if needed."""
    with open(path, encoding='utf-8') as f:
        raw = f.read()
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    if isinstance(data, dict) and isinstance(data.get('content'), str) and 'wfrp_library' not in data:
        raw, data = data['content'], None  # a saved download result
    if data is None:
        try:
            raw = base64.b64decode(re.sub(r'\s+', '', raw), validate=True).decode('utf-8')
            json.loads(raw)
        except (binascii.Error, ValueError, UnicodeDecodeError):
            die(f'{path}: neither JSON nor a base64 Drive download of JSON')
    return raw


def lines_json(records):
    return '[\n' + ',\n'.join('  ' + json.dumps(r, ensure_ascii=False) for r in records) + '\n]\n'


def merge_index(index, records, source, chapter):
    """Returns (merged, added, updated, removed)."""
    new = {r['slug']: {k: v for k, v in r.items() if not k.startswith('_')} for r in records}
    old = {r['slug']: r for r in index}
    for slug, r in new.items():
        o = old.get(slug)
        if o and (o['source'], o.get('chapter')) != (r['source'], r.get('chapter')):
            die(f'slug {slug!r} already belongs to {o["source"]} {o.get("chapter")}; '
                'run the converter with --taken so it gets a source suffix')
    added = sorted(s for s in new if s not in old)
    updated = sorted(s for s in new if s in old)
    removed = []
    if chapter:
        removed = sorted(s for s, o in old.items()
                         if (o['source'], o.get('chapter')) == (source, chapter) and s not in new)
    merged = [o for s, o in old.items() if s not in new and s not in removed] + list(new.values())
    merged.sort(key=lambda r: r['slug'])
    return merged, added, updated, removed


def set_chapter(text, source, chapter, status, date, notes):
    """Replace one chapter line in library.json, leaving every other byte as it was."""
    m = re.search(r'"code":\s*"' + re.escape(source) + r'"', text)
    if not m:
        die(f'library.json: no source with code {source}')
    nxt = re.search(r'"code":\s*"', text[m.end():])
    end = m.end() + nxt.start() if nxt else len(text)
    line_re = re.compile(r'^([ \t]*)(\{[^\n]*"id":\s*"' + re.escape(chapter) + r'"[^\n]*\})(,?)$', re.M)
    lm = line_re.search(text, m.end(), end)
    if not lm:
        die(f'library.json: no one-line chapter {chapter!r} in source {source}')
    old = json.loads(lm.group(2))
    style = lambda o: '{ ' + json.dumps(o, ensure_ascii=False)[1:-1] + ' }'
    if style(old) != lm.group(2):
        die(f'library.json: chapter {chapter!r} line is not in the usual layout; edit it by hand')
    new = dict(old, status=status, date=date, notes=notes)
    out = text[:lm.start(2)] + style(new) + text[lm.end(2):]
    json.loads(out)
    return out, old


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', required=True)
    ap.add_argument('--index', help="the category's current _index.json (omit if it doesn't exist yet)")
    ap.add_argument('--records', required=True, help='_records.json from the converter, or built by hand')
    ap.add_argument('--slugs', help='merge only these records (comma-separated): one batch')
    ap.add_argument('--log', help='current _import-log.json')
    ap.add_argument('--library', help='current library.json')
    ap.add_argument('--edition', choices=('4e', '2e', '1e'),
                    help="the source's rules edition (library.json or campaign.json), written on each record")
    ap.add_argument('--source')
    ap.add_argument('--chapter')
    ap.add_argument('--category', help='for the log record, e.g. careers')
    ap.add_argument('--log-notes', default='')
    ap.add_argument('--chapter-notes', default='')
    ap.add_argument('--failed', type=int, default=0, help='entries that failed checks')
    ap.add_argument('--skipped', type=int, default=0)
    ap.add_argument('--date', default=datetime.date.today().isoformat())
    args = ap.parse_args()

    final = bool(args.log or args.library)
    if final and args.slugs:
        die('--slugs is for batch merges; the final run merges every record')
    if final and not (args.source and args.chapter and args.category):
        die('--log and --library need --source, --chapter and --category')

    records = json.loads(read_text(args.records))
    if args.slugs:
        want = set(args.slugs.split(','))
        unknown = want - {r['slug'] for r in records}
        if unknown:
            die(f'not in --records: {", ".join(sorted(unknown))}')
        records = [r for r in records if r['slug'] in want]
    # converters tag each record with the index it goes in ("_category"); keep this index's
    # (named by --category, or the index's folder) and drop the tag. An older import's
    # "category" that only names the index is dropped too.
    cat = args.category or (os.path.basename(os.path.dirname(os.path.abspath(args.index))) if args.index else None)
    if cat and any(r.get('_category') not in (None, cat) for r in records):
        other = sorted({r['_category'] for r in records if r.get('_category') not in (None, cat)})
        print(f'--records: keeping the {cat} records; leaving out {", ".join(other)} (merge those into their own indexes)')
        records = [r for r in records if r.get('_category') in (None, cat)]
    for r in records:
        r.pop('_category', None)
        if cat and r.get('category') == cat:
            r.pop('category')
    if args.source and any(r['source'] != args.source for r in records):
        die(f'--records has entries from a source other than {args.source}')
    for r in records:
        if args.edition:
            r['edition'] = args.edition
        elif not r.get('edition'):
            die(f'{r["slug"]}: no edition; pass --edition with the source\'s edition (layout §3)')

    os.makedirs(args.out, exist_ok=True)
    written = []

    def write(name, text):
        path = os.path.join(args.out, name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        written.append((name, os.path.getsize(path)))

    index = json.loads(read_text(args.index)) if args.index else []
    for r in index:                     # left by an older import: the index's own name as a field
        if cat and r.get('category') == cat:
            r.pop('category')
    # Batch merges never remove records: only the final run knows the whole chapter.
    merged, added, updated, removed = merge_index(index, records, args.source,
                                                  args.chapter if final else None)
    write('_index.json', lines_json(merged))
    print(f'_index.json: {len(index)} -> {len(merged)} records '
          f'({len(added)} added, {len(updated)} updated, {len(removed)} removed)')
    if removed:
        print('  No longer in this chapter; move their entry files to the trash: ' + ', '.join(removed))

    if args.log:
        log = json.loads(read_text(args.log))
        log.append({'date': args.date, 'source': args.source, 'chapter': args.chapter,
                    'category': args.category, 'added': len(added), 'updated': len(updated),
                    'skipped': args.skipped, 'failed': args.failed, 'notes': args.log_notes})
        write('_import-log.json', lines_json(log))
        print(f'_import-log.json: {len(log)} records')

    if args.library:
        status = 'problems' if args.failed else 'imported'
        text, old = set_chapter(read_text(args.library), args.source, args.chapter,
                                status, args.date, args.chapter_notes)
        write('library.json', text)
        print(f'library.json: {args.source} {args.chapter} {old["status"]} -> {status}')

    print('Bytes per file (compare with the fileSize Drive reports after each upload):')
    for name, size in written:
        print(f'  {size:>7}  {name}')


if __name__ == '__main__':
    main()
