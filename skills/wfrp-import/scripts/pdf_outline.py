#!/usr/bin/env python3
"""Read a PDF's bookmarks as a source's chapter list (library-layout.md §3).

    pdf_outline.py BOOK.pdf [--page-offset N] [--depth 2] [--out chapters.json]

Prints a JSON list of chapters, one per top-level bookmark:

    {"id": "ch3", "title": "Chapter 3: Class and Careers", "pages": "30-109",
     "pdf_pages": "32-111", "status": "not-imported", "date": null, "notes": ""}

`pages` are printed page numbers: PDF page number minus --page-offset (the
number of pages before printed page 1, such as a cover and contents). When the
PDF has page labels and no offset is given, the offset is read from the labels
and reported. A chapter ends on the page before the next one starts; the last
runs to the end of the PDF. With --depth 2 or more, each chapter also lists its
sub-bookmarks under `sections` (title and printed page), for writing its plan.

Bookmarks are a starting point, not the truth: show the list to the Librarian
and check it against the book's contents page. Bookmarks for covers, credits,
adverts and the index are listed too; drop the ones that aren't chapters.
Needs pypdf. Never reads page text.
"""
import argparse
import json
import re
import sys

from pypdf import PdfReader

NUMBERED = re.compile(r'^\s*(chapter|appendix|part)\s+([0-9ivxlc]+|[a-z])\b', re.I)


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-') or 'section'


def chapter_id(title, seen):
    m = NUMBERED.match(title)
    if m:
        kind = {'chapter': 'ch', 'appendix': 'app', 'part': 'part'}[m.group(1).lower()]
        cid = kind + m.group(2).lower()
    else:
        cid = slug(title)[:40]
    base, n = cid, 2
    while cid in seen:
        cid, n = f'{base}-{n}', n + 1
    seen.add(cid)
    return cid


def walk(reader, items, depth, level=1):
    """Outline (pypdf's nested lists) -> [{"title", "pdf_page" (1-based), "children"}]."""
    out = []
    for it in items:
        if isinstance(it, list):
            if out and level < depth:
                out[-1]['children'] += walk(reader, it, depth, level + 1)
            continue
        try:
            page = reader.get_destination_page_number(it) + 1
        except Exception:  # a bookmark with no page (an external link): listed, with no page
            page = None
        out.append({'title': str(it.title).strip(), 'pdf_page': page, 'children': []})
    return out


def offset_from_labels(reader):
    """The offset implied by the PDF's page labels: the first page labelled "1"."""
    if '/PageLabels' not in reader.trailer['/Root']:
        return None                  # pypdf makes up "1", "2", … when the PDF has no labels
    labels = getattr(reader, 'page_labels', None) or []
    for i, lab in enumerate(labels):
        if str(lab).strip() == '1':
            return i
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf')
    ap.add_argument('--page-offset', type=int, help='PDF page number of printed page 1, minus 1')
    ap.add_argument('--depth', type=int, default=1, help='bookmark levels to list (default 1)')
    ap.add_argument('--out', help='write the JSON here instead of printing it')
    a = ap.parse_args(argv)

    reader = PdfReader(a.pdf)
    total = len(reader.pages)
    offset = a.page_offset
    if offset is None:
        offset = offset_from_labels(reader)
        if offset is not None:
            print(f'page offset {offset}, from the PDF\'s page labels', file=sys.stderr)
        else:
            offset = 0
            print('no page labels and no --page-offset: printed pages are taken to equal PDF pages; '
                  'check against the book and pass --page-offset', file=sys.stderr)
    tops = walk(reader, reader.outline, max(a.depth, 1))
    if not tops:
        sys.exit('the PDF has no bookmarks: take the chapter list from its contents page instead')

    seen, chapters = set(), []
    starts = [t['pdf_page'] for t in tops]
    for i, t in enumerate(tops):
        start = t['pdf_page']
        nxt = next((s for s in starts[i + 1:] if s is not None), None)
        end = (nxt - 1) if nxt else total
        ch = {'id': chapter_id(t['title'], seen), 'title': t['title']}
        if start is None:
            ch['pages'] = ch['pdf_pages'] = None
            ch['notes'] = 'bookmark has no page'
            print(f'no page for bookmark {t["title"]!r}', file=sys.stderr)
        else:
            end = max(end, start)
            ch['pages'] = f'{start - offset}-{end - offset}'
            ch['pdf_pages'] = f'{start}-{end}'
        ch.update({'status': 'not-imported', 'date': None})
        ch.setdefault('notes', '')
        if a.depth > 1:
            ch['sections'] = [{'title': c['title'],
                               'page': None if c['pdf_page'] is None else c['pdf_page'] - offset}
                              for c in t['children']]
        chapters.append(ch)

    text = json.dumps(chapters, indent=1, ensure_ascii=False) + '\n'
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f'{len(chapters)} chapters -> {a.out}', file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    main()
