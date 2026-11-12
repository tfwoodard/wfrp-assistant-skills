#!/usr/bin/env python3
"""Read a chapter's PDF pages as lines with their layout (docs/adr/0002).

    pdf_layout.py BOOK.pdf --pages 30-109 [--page-offset 2] --out ch3-layout.json
    pdf_layout.py BOOK.pdf --pages 87 --page-offset 2 --text      # a readable view, for planning
    pdf_layout.py BOOK.pdf --pages 46-116 --icon-fonts IconFont OtherIcons --out ...

`--pages` are printed page numbers (library-layout.md §3); --page-offset is the
number of PDF pages before printed page 1 (the source's `page_offset`).

Characters are grouped into lines by their **baseline**, so large and small
capitals set on one line stay together, and into words by the space between
them. Each page's **gutter** is found from where its words lie: an x position
near the middle that (almost) no word crosses. A line is split at the gutter
into its left and right parts; a line with a word across it is "full" width.
On a page with no gutter every line is "full". Lines are read in bands: a full
line ends a band, and within a band the left column is read before the right.

Each line records:

    {"page": 87, "column": "left" | "right" | "full", "top": 112.4, "baseline": 121.1,
     "x0": 51.0, "x1": 290.2, "text": "Lamp Warden", "size": 14.0, "bold": true, "italic": false,
     "font": "CaslonAntique-Bold", "spans": [{"text", "size", "bold", "italic"}],
     "words": [["Lamp", 51.0, 70.2], ...], "furniture": false, "heading": 2}

`spans` splits the line where its style changes; `words` gives each word's
text, x0 and x1, for tables and rows of labels. `furniture` marks running
heads, footers and bare page numbers (lines in the top or bottom margin).
`heading` is a level (1 = largest type) for lines set larger than the body
text. `fonts` lists every size with how many characters use it; `body_size` is
the commonest. `gutters` gives each page's gutter x (null: one column).

Icons. Books mark things with symbol glyphs (a career level's cross) and small
vector drawings (its shield or skull). Glyphs in a font named by --icon-fonts
(a part of the font's name is enough) are taken out of the text and listed
under `marks` ({"page", "x0", "x1", "top", "bottom", "font", "text"}). Small
filled drawings (both sides under 20 points) are listed under `shapes`
({"page", "x0", "x1", "top", "bottom", "pts"}); `pts`, the number of points in
the path, tells one drawn icon from another.

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
BASELINE_TOLERANCE = 1.5                 # points between baselines on one line
WORD_GAP = 0.18                          # a gap wider than this x the type size splits words
GUTTER_ZONE = (0.38, 0.62)               # where to look for a gutter, as fractions of the width
SHAPE_MAX = 20                           # points: larger drawings aren't icons


def parse_pages(s):
    a, _, b = s.partition('-')
    a = int(a)
    b = int(b) if b else a
    if b < a:
        sys.exit(f'--pages {s}: the range runs backwards')
    return a, b


def font_name(f):
    return f.split('+', 1)[-1]


def baseline(c, height):
    m = c.get('matrix')
    return round(height - m[5], 1) if m else round(c['bottom'], 1)


def make_words(chars, height):
    """Characters -> words, each on one baseline, split at space characters and at gaps wider
    than WORD_GAP x the type size."""
    rows = []
    for c in sorted(chars, key=lambda c: (baseline(c, height), c['x0'])):
        b = baseline(c, height)
        if rows and abs(b - rows[-1][0]) <= BASELINE_TOLERANCE:
            rows[-1][1].append(c)
        else:
            rows.append((b, [c]))
    groups = []
    for b, row in rows:
        cur = []
        for c in sorted(row, key=lambda c: c['x0']):
            if c['text'].isspace():
                if cur:
                    groups.append((b, cur))
                cur = []
                continue
            if cur and c['x0'] - cur[-1]['x1'] > WORD_GAP * min(c['size'], cur[-1]['size']):
                groups.append((b, cur))
                cur = []
            cur.append(c)
        if cur:
            groups.append((b, cur))
    return [{'text': ''.join(c['text'] for c in cs), 'x0': min(c['x0'] for c in cs),
             'x1': max(c['x1'] for c in cs), 'top': min(c['top'] for c in cs),
             'bottom': max(c['bottom'] for c in cs), 'baseline': b, 'chars': cs} for b, cs in groups]


def slanted(c):
    """True for text set oblique by slanting a roman font (its text matrix skews), as some books
    print their italics."""
    m = c.get('matrix')
    return bool(m and m[0] and abs(m[2] / m[0]) > 0.1)


def style(c):
    f = font_name(c.get('fontname', ''))
    return {'size': round(float(c.get('size', 0)), 1), 'bold': bool(BOLD.search(f)),
            'italic': bool(ITALIC.search(f)) or slanted(c), 'font': f}


def word_style(w):
    """The style most of a word's characters have. A word of large and small capitals takes the
    larger size."""
    counts = collections.Counter()
    for c in w['chars']:
        s = style(c)
        counts[(s['size'], s['bold'], s['italic'], s['font'])] += 1
    (size, bold, italic, font), _ = counts.most_common(1)[0]
    return {'size': max(k[0] for k in counts), 'bold': bold, 'italic': italic, 'font': font}


def find_gutter(words, width):
    """The x of the page's gutter, or None. Counts, for each point across the middle of the page,
    the words that cross it; the gutter is the middle of the widest run that at most a few cross."""
    lo, hi = int(width * GUTTER_ZONE[0]), int(width * GUTTER_ZONE[1])
    if len(words) < 12:
        return None
    rows = len({w['baseline'] for w in words})
    allowed = max(0, rows // 50)
    cover = [0] * (hi - lo + 1)
    for w in words:
        for x in range(max(lo, int(w['x0']) + 1), min(hi, int(w['x1'])) + 1):
            cover[x - lo] += 1
    best, run = None, None
    for i, n in enumerate(cover + [allowed + 1]):
        if n <= allowed:
            run = (run[0], i) if run else (i, i)
        elif run:
            if best is None or run[1] - run[0] > best[1] - best[0]:
                best = run
            run = None
    if best is None or best[1] - best[0] < 2:
        return None
    return lo + (best[0] + best[1]) / 2


def segments(raw, gutter):
    """One baseline's words -> [(column, words)], split where the gutter falls between two words."""
    if gutter is None:
        return [('full', raw)]
    left = [w for w in raw if w['x1'] <= gutter]
    right = [w for w in raw if w['x0'] >= gutter]
    if len(left) + len(right) < len(raw):          # a word crosses the gutter: a full-width line
        return [('full', raw)]
    if left and right:
        # A space between two words of one full-width line can fall on the gutter too; the
        # gap between columns is wider than a word space.
        size = max(c['size'] for c in left[-1]['chars'] + right[0]['chars'])
        if right[0]['x0'] - left[-1]['x1'] < max(4.0, 0.6 * size):
            return [('full', raw)]
    return [(c, ws) for c, ws in (('left', left), ('right', right)) if ws]


def make_line(ws, page_no, column, height):
    spans = []
    weights = collections.Counter()
    for w in ws:
        st = word_style(w)
        weights[(st['size'], st['font'])] += len(w['text'])
        if spans and all(spans[-1][k] == st[k] for k in ('size', 'bold', 'italic')):
            spans[-1]['text'] += ' ' + w['text']
        else:
            spans.append({'text': w['text'], 'size': st['size'], 'bold': st['bold'], 'italic': st['italic']})
    (size, font), _ = weights.most_common(1)[0]
    top = min(w['top'] for w in ws)
    bottom = max(w['bottom'] for w in ws)
    text = ' '.join(w['text'] for w in ws)
    furniture = top < height * MARGIN_TOP or bottom > height * (1 - MARGIN_BOTTOM) or \
        bool(re.fullmatch(r'\d{1,4}', text))
    return {'page': page_no, 'column': column, 'top': round(top, 1), 'baseline': ws[0]['baseline'],
            'x0': round(min(w['x0'] for w in ws), 1), 'x1': round(max(w['x1'] for w in ws), 1),
            'text': text, 'size': size, 'bold': all(s['bold'] for s in spans),
            'italic': all(s['italic'] for s in spans), 'font': font, 'spans': spans,
            'words': [[w['text'], round(w['x0'], 1), round(w['x1'], 1)] for w in ws],
            'furniture': furniture}


def page_lines(page, page_no, icon_fonts=(), marks=None, shapes=None):
    """One page -> (lines in reading order, gutter x or None). Icon glyphs go to `marks`, small
    drawings to `shapes`, when those lists are given."""
    chars = []
    for c in page.chars:
        f = font_name(c.get('fontname', ''))
        if icon_fonts and any(k.lower() in f.lower() for k in icon_fonts):
            if marks is not None:
                marks.append({'page': page_no, 'x0': round(c['x0'], 1), 'x1': round(c['x1'], 1),
                              'top': round(c['top'], 1), 'bottom': round(c['bottom'], 1),
                              'font': f, 'text': c['text']})
            continue
        chars.append(c)
    if shapes is not None:
        for cv in page.curves:
            if cv['x1'] - cv['x0'] < SHAPE_MAX and cv['bottom'] - cv['top'] < SHAPE_MAX and cv.get('fill'):
                shapes.append({'page': page_no, 'x0': round(cv['x0'], 1), 'x1': round(cv['x1'], 1),
                               'top': round(cv['top'], 1), 'bottom': round(cv['bottom'], 1),
                               'pts': len(cv.get('pts') or [])})
    words = make_words(chars, page.height)
    # Running heads and footers often cross the middle; only the body decides the gutter.
    body = [w for w in words if w['top'] >= page.height * MARGIN_TOP and
            w['bottom'] <= page.height * (1 - MARGIN_BOTTOM)]
    gutter = find_gutter(body, page.width)
    rows = collections.defaultdict(list)
    for w in words:
        rows[w['baseline']].append(w)
    segs = []                       # (baseline, column, words)
    for b, raw in rows.items():
        for col, ws in segments(sorted(raw, key=lambda w: w['x0']), gutter):
            segs.append((b, col, ws))
    segs.sort(key=lambda s: s[0])
    # A full-width line ends a band; within a band, read the left column, then the right.
    bounds = sorted({b for b, c, _ in segs if c == 'full'}) + [float('inf')]
    out, prev = [], float('-inf')
    for bnd in bounds:
        for side in ('left', 'right'):
            out += [make_line(ws, page_no, side, page.height) for b, c, ws in segs if c == side and prev <= b < bnd]
        out += [make_line(ws, page_no, 'full', page.height) for b, c, ws in segs if c == 'full' and b == bnd]
        prev = bnd
    return out, gutter


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


def read(pdf_path, first, last, offset, icon_fonts=()):
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        if first + offset < 1 or last + offset > n:
            sys.exit(f'printed pages {first}-{last} with offset {offset} are PDF pages '
                     f'{first + offset}-{last + offset}, outside the PDF\'s 1-{n}')
        lines, marks, shapes, empty, gutters = [], [], [], [], {}
        for p in range(first, last + 1):
            got, gutter = page_lines(pdf.pages[p + offset - 1], p, icon_fonts, marks, shapes)
            gutters[str(p)] = None if gutter is None else round(gutter, 1)
            if not got:
                empty.append(p)
            lines += got
    sizes, body = assign_headings(lines)
    return {'pages': f'{first}-{last}', 'page_offset': offset, 'body_size': body,
            'icon_fonts': list(icon_fonts),
            'fonts': [{'size': s, 'chars': c} for s, c in sorted(sizes.items(), reverse=True)],
            'gutters': gutters, 'pages_without_text': empty, 'lines': lines, 'marks': marks, 'shapes': shapes}


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
    ap.add_argument('--icon-fonts', nargs='*', default=[], help='fonts whose glyphs are icons, not text')
    ap.add_argument('--out', help='write the layout JSON here')
    ap.add_argument('--text', action='store_true', help='print a readable view instead of JSON')
    a = ap.parse_args(argv)
    first, last = parse_pages(a.pages)
    doc = read(a.pdf, first, last, a.page_offset, a.icon_fonts)
    if doc['pages_without_text']:
        print('no text layer on printed pages ' + ', '.join(map(str, doc['pages_without_text'])) +
              ': look at the page images, and ask before running OCR', file=sys.stderr)
    if a.text:
        sys.stdout.write(text_view(doc))
    elif a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=0)
            f.write('\n')
        print(f'{len(doc["lines"])} lines, {len(doc["marks"])} marks, {len(doc["shapes"])} shapes, '
              f'body size {doc["body_size"]} -> {a.out}', file=sys.stderr)
    else:
        json.dump(doc, sys.stdout, ensure_ascii=False, indent=0)
        sys.stdout.write('\n')


if __name__ == '__main__':
    main()
