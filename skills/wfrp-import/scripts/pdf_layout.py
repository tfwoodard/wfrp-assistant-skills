#!/usr/bin/env python3
"""Read a chapter's PDF pages as lines with their layout (docs/adr/0002).

    pdf_layout.py BOOK.pdf --pages 30-109 [--page-offset 2] --out ch3-layout.json
    pdf_layout.py BOOK.pdf --pages 87 --page-offset 2 --text      # a readable view, for planning

`--pages` are printed page numbers (library-layout.md §3); --page-offset is the
number of PDF pages before printed page 1 (the source's `page_offset`).

Each page's words are split into columns, then grouped into lines in reading
order: a full-width line (a chapter title, a wide table) ends a band, and within
a band the left column is read before the right. Each line records:

    {"page": 87, "column": "left" | "right" | "full", "top": 112.4, "x0": 51.0,
     "text": "Rat Catcher", "size": 14.0, "bold": true, "italic": false,
     "font": "CaslonAntique-Bold", "spans": [{"text", "size", "bold", "italic"}],
     "furniture": false, "heading": 2}

`spans` splits the line where its style changes ("***Skills:*** Animal Care…").
`furniture` marks running heads, footers and bare page numbers (lines in the
top or bottom margin); they are page furniture, not book text, and converters
leave them out. `heading` is a level (1 = largest type) for lines set larger
than the body text, from the chapter's own sizes; `fonts` in the output lists
every size with how many characters use it, and `body_size` the commonest,
so a plan can say which levels are entries.

The output is the book's text: write it to scratch outside the repo, never
commit it. Needs pdfplumber.
"""
import argparse
import collections
import json
import re
import sys

import pdfplumber

BOLD = re.compile(r'bold|black|heavy|semibold|demi', re.I)
ITALIC = re.compile(r'italic|oblique', re.I)
MARGIN_TOP, MARGIN_BOTTOM = 0.06, 0.06   # fractions of the page height
LINE_TOLERANCE = 2.5                     # points between word tops on one line
GUTTER = 6                               # points either side of the page's middle
GAP = 12                                 # points: a wider gap across the middle splits columns


def parse_pages(s):
    a, _, b = s.partition('-')
    a = int(a)
    b = int(b) if b else a
    if b < a:
        sys.exit(f'--pages {s}: the range runs backwards')
    return a, b


def style(w):
    font = w.get('fontname', '')
    return {'size': round(float(w.get('size', 0)), 1), 'bold': bool(BOLD.search(font)),
            'italic': bool(ITALIC.search(font)), 'font': font}


def group_lines(words):
    """Words -> lines, top to bottom, each line's words left to right."""
    lines = []
    for w in sorted(words, key=lambda w: (round(w['top'], 1), w['x0'])):
        if lines and abs(w['top'] - lines[-1][0]['top']) <= LINE_TOLERANCE:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(l, key=lambda w: w['x0']) for l in lines]


def make_line(ws, page_no, column, height):
    spans = []
    for w in ws:
        st = style(w)
        if spans and all(spans[-1][k] == st[k] for k in ('size', 'bold', 'italic')):
            spans[-1]['text'] += ' ' + w['text']
        else:
            spans.append({'text': w['text'], 'size': st['size'], 'bold': st['bold'], 'italic': st['italic']})
    weights = collections.Counter()
    for w in ws:
        weights[(style(w)['size'], style(w)['font'])] += len(w['text'])
    (size, font), _ = weights.most_common(1)[0]
    top = min(w['top'] for w in ws)
    bottom = max(w['bottom'] for w in ws)
    text = ' '.join(w['text'] for w in ws)
    furniture = top < height * MARGIN_TOP or bottom > height * (1 - MARGIN_BOTTOM) or \
        bool(re.fullmatch(r'\d{1,4}', text))
    return {'page': page_no, 'column': column, 'top': round(top, 1), 'x0': round(min(w['x0'] for w in ws), 1),
            'text': text, 'size': size, 'bold': all(s['bold'] for s in spans),
            'italic': all(s['italic'] for s in spans), 'font': font, 'spans': spans,
            'furniture': furniture}


def segments(raw, mid):
    """One raw line (words at the same height across the page) -> segments, split where the
    gap between neighbouring words is wide and straddles the page's middle (the gutter
    between columns). Each segment is (column, words): "full" when it crosses the middle."""
    segs, cur = [], [raw[0]]
    for w in raw[1:]:
        gap = w['x0'] - cur[-1]['x1']
        if gap > GAP and cur[-1]['x1'] <= mid + GUTTER and w['x0'] >= mid - GUTTER:
            segs.append(cur)
            cur = [w]
        else:
            cur.append(w)
    segs.append(cur)
    out = []
    for seg in segs:
        x0, x1 = seg[0]['x0'], max(w['x1'] for w in seg)
        out.append(('left' if x1 <= mid + GUTTER else 'right' if x0 >= mid - GUTTER else 'full', seg))
    return out


def page_lines(page, page_no):
    words = page.extract_words(extra_attrs=['fontname', 'size'], keep_blank_chars=False, use_text_flow=False)
    mid = page.width / 2
    segs = []                       # (top, column, words)
    for raw in group_lines(words):
        for col, ws in segments(raw, mid):
            segs.append((min(w['top'] for w in ws), col, ws))
    segs.sort(key=lambda x: x[0])
    # A full-width line ends a band; within a band, read the left column, then the right.
    bounds = sorted({t for t, c, _ in segs if c == 'full'}) + [float('inf')]
    out, prev = [], float('-inf')
    for b in bounds:
        for side in ('left', 'right'):
            out += [make_line(ws, page_no, side, page.height) for t, c, ws in segs if c == side and prev <= t < b]
        out += [make_line(ws, page_no, 'full', page.height) for t, c, ws in segs if c == 'full' and t == b]
        prev = b
    return out


def assign_headings(lines):
    sizes = collections.Counter()
    for l in lines:
        if not l['furniture']:
            for s in l['spans']:
                sizes[s['size']] += len(s['text'])
    if not sizes:
        return sizes, None
    body = sizes.most_common(1)[0][0]
    larger = sorted((s for s in sizes if s > body + 0.4), reverse=True)
    level = {s: i + 1 for i, s in enumerate(larger)}
    for l in lines:
        if not l['furniture'] and l['size'] in level:
            l['heading'] = level[l['size']]
    return sizes, body


def read(pdf_path, first, last, offset):
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        if first + offset < 1 or last + offset > n:
            sys.exit(f'printed pages {first}-{last} with offset {offset} are PDF pages '
                     f'{first + offset}-{last + offset}, outside the PDF\'s 1-{n}')
        lines = []
        empty = []
        for p in range(first, last + 1):
            got = page_lines(pdf.pages[p + offset - 1], p)
            if not got:
                empty.append(p)
            lines += got
    sizes, body = assign_headings(lines)
    return {'pages': f'{first}-{last}', 'page_offset': offset, 'body_size': body,
            'fonts': [{'size': s, 'chars': c} for s, c in sorted(sizes.items(), reverse=True)],
            'pages_without_text': empty, 'lines': lines}


def text_view(doc):
    out = []
    for l in doc['lines']:
        tag = ('F' if l['furniture'] else f'H{l["heading"]}' if l.get('heading') else '  ')
        style_ = ('B' if l['bold'] else ' ') + ('I' if l['italic'] else ' ')
        out.append(f'p{l["page"]:<4} {l["column"][0].upper()} {tag:>3} {l["size"]:>5} {style_} {l["text"]}')
    return '\n'.join(out) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf')
    ap.add_argument('--pages', required=True, help='printed page range, e.g. 30-109 or 87')
    ap.add_argument('--page-offset', type=int, default=0)
    ap.add_argument('--out', help='write the layout JSON here')
    ap.add_argument('--text', action='store_true', help='print a readable view instead of JSON')
    a = ap.parse_args(argv)
    first, last = parse_pages(a.pages)
    doc = read(a.pdf, first, last, a.page_offset)
    if doc['pages_without_text']:
        print('no text layer on printed pages ' + ', '.join(map(str, doc['pages_without_text'])) +
              ': look at the page images, and ask before running OCR', file=sys.stderr)
    if a.text:
        sys.stdout.write(text_view(doc))
    elif a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=0)
            f.write('\n')
        print(f'{len(doc["lines"])} lines, body size {doc["body_size"]} -> {a.out}', file=sys.stderr)
    else:
        json.dump(doc, sys.stdout, ensure_ascii=False, indent=0)
        sys.stdout.write('\n')


if __name__ == '__main__':
    main()
