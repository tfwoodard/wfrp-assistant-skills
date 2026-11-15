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
near the middle that (almost) no word crosses (words set larger than the body
text, like a title across both columns, aren't counted); a page set in three columns has
two, one near each third (its columns are left, middle and right). A line is split at the gutter
into its left and right parts; a line with a word across it is "full" width.
On a page with no gutter every line is "full". Lines are read in bands: a full
line ends a band, and within a band the left column is read before the right.

Each line records:

    {"page": 87, "column": "left" | "middle" | "right" | "full", "top": 112.4, "baseline": 121.1,
     "x0": 51.0, "x1": 290.2, "text": "Lamp Warden", "size": 14.0, "bold": true, "italic": false,
     "font": "CaslonAntique-Bold", "spans": [{"text", "size", "bold", "italic"}],
     "words": [["Lamp", 51.0, 70.2], ...], "furniture": false, "heading": 2}

`spans` splits the line where its style changes; `words` gives each word's
text, x0 and x1, for tables and rows of labels. `furniture` marks running
heads, footers and bare page numbers (lines in the top or bottom margin).
`heading` is a level (1 = largest type) for lines set larger than the body
text in a size the chapter uses rarely (a size used as much as a sidebar's
text is text, not headings). `fonts` lists every size with how many characters use it; `body_size` is
the commonest. `gutters` gives each page's gutter x positions (null: one column).

Icons. Books mark things with symbol glyphs (a career level's cross) and small
vector drawings (its shield or skull). Glyphs in a font named by --icon-fonts
(a part of the font's name is enough) are taken out of the text and listed
under `marks` ({"page", "x0", "x1", "top", "bottom", "font", "text"}). Small
filled drawings (both sides under 20 points) are listed under `shapes`
({"page", "x0", "x1", "top", "bottom", "pts"}); `pts`, the number of points in
the path, tells one drawn icon from another. An icon printed inline in the
text ("the lamp marked with ✦") can be kept in its line: --icon-text
IconFont=✦ pts:12=◆ puts that text where the glyph or drawing stands.

Boxes and tables (--boxes). Panels printed on a background image that doesn't
fill the page (sidebars, boxed tables) are read as regions of their own: each
gets its own column check, its lines come after the page's body lines and carry
`box` (its id, "<page>.<n>"), and the page's gutter is found from the text
outside them. A box with ruled rows (rules, or shaded row bands) is read as a
table: `regions` lists each box ({"id", "kind": "box" | "table", "page",
"bbox"}), and a table adds "columns" (the header cells) and "rows" (cells as
plain text); its lines carry `table` too. An illustration cut out with a soft mask
(mostly see-through) is not a panel, even where its rectangle runs over text;
nor is a rectangle the page's lines run across (a word over its edge, or a line
carrying on into it, on a quarter of its rows). A box's own lines are read in
one or two columns, never three: a table's columns aren't text columns. A box holding
several ruled tables, each under its own larger title, is read as one region per table,
numbered "<box id>.<n>" (216.1.1, 216.1.2).
`image_notes` lists each one set aside, and any mask that couldn't be read.

The output is the book's text: write it to scratch outside the repo, never
commit it. Needs pdfplumber.
"""
import argparse
import collections
import json
import re
import sys

import pdfplumber
from pdfminer.pdffont import PDFSimpleFont

# Some fonts' character maps send a capital's code to its lower-case letter (code 84, "T" in the
# font's standard encoding, read as "t"), so the text loses its capitals though the page shows
# them. In a simple font a code in A-Z stands for that capital: read it so, and count each fix by
# font (`case_fixed` in the output). Small-caps fonts ("-SC" in the name) are left alone: they set
# their small capitals at those codes too, and entry_text.fix_case() restores those words.
CASE_FIXED = collections.Counter()
_to_unichr = PDFSimpleFont.to_unichr


def _to_unichr_keeping_capitals(self, cid):
    u = _to_unichr(self, cid)
    if 65 <= cid <= 90 and u == chr(cid + 32) and 'SC' not in str(getattr(self, 'basefont', '')):
        CASE_FIXED[str(getattr(self, 'basefont', '?'))] += 1
        return chr(cid)
    return u


PDFSimpleFont.to_unichr = _to_unichr_keeping_capitals

BOLD = re.compile(r'bold|black|heavy|semibold|demi', re.I)
ITALIC = re.compile(r'italic|oblique', re.I)
MARGIN_TOP, MARGIN_BOTTOM = 0.06, 0.06   # fractions of the page height
BASELINE_TOLERANCE = 1.5                 # points between baselines on one line
WORD_GAP = 0.18                          # a gap wider than this x the type size splits words
GUTTER_ZONE = (0.38, 0.62)               # where to look for a gutter, as fractions of the width
THIRDS_ZONES = ((0.25, 0.42), (0.58, 0.75))   # where a three-column page's two gutters fall
THIRD_SHARE = 0.2                        # ...and the least share of its words each column holds
SHAPE_MAX = 20                           # points: larger drawings aren't icons
BOX_MIN = (100, 24)                      # points: a smaller image isn't a boxed panel
RUN_ON_GAP = 4.0                         # points: a word this near a box's edge is on the same line
RUN_OVER_SHARE = 0.25                    # a box with this share of its lines crossing its edges is no panel
PANEL_OPAQUE = 0.75                      # a masked image less opaque than this is an illustration
HEADING_SHARE = 0.08                     # a larger size used for more than this share of the body's characters is text


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
        kept = []
        for c in sorted(row, key=lambda c: c['x0']):
            # A glyph printed twice in the same place (a shadow or outline effect) is one glyph.
            if any(k['text'] == c['text'] and abs(k['x0'] - c['x0']) < 0.15 * max(c['x1'] - c['x0'], 1) and
                   abs(k['top'] - c['top']) < 1 for k in kept[-3:]):
                continue
            kept.append(c)
        for c in kept:
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


def find_gutters(words, width, left=0.0, three=True):
    """The x of each gutter between `left` and `left + width`: two, one near each third, when the
    page is set in three columns (each holding a good share of the words; not looked for when
    `three` is false); else one near the middle; else none."""
    thirds = [find_gutter(words, width, left, z) for z in THIRDS_ZONES] if three else [None]
    if all(t is not None for t in thirds):
        edges = [float('-inf')] + thirds + [float('inf')]
        counts = [sum(1 for w in words if edges[i] <= (w['x0'] + w['x1']) / 2 < edges[i + 1]) for i in range(3)]
        if min(counts) >= THIRD_SHARE * len(words):
            return thirds
    g = find_gutter(words, width, left)
    return [] if g is None else [g]


def word_size(w):
    return max(c['size'] for c in w['chars']) if w.get('chars') else w.get('size', 0)


def body_words(words):
    """The words set at most a point larger than the commonest size: titles and headings set
    larger, which may run across both columns, left out."""
    sizes = collections.Counter(round(word_size(w)) for w in words)
    if not sizes:
        return words
    body = sizes.most_common(1)[0][0]
    return [w for w in words if round(word_size(w)) <= body + 1]


def find_gutter(words, width, left=0.0, zone=None):
    """The x of the gutter in `zone` (fractions of the width; default the middle) between `left`
    and `left + width`, or None. Counts, for each point across the zone, the words that cross it;
    the gutter is the middle of the widest run that at most a few cross."""
    zone = zone or GUTTER_ZONE
    lo, hi = int(left + width * zone[0]), int(left + width * zone[1])
    words = body_words(words)          # a title set across both columns doesn't hide the gutter
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


def column_names(n):
    return {1: ['left', 'right'], 2: ['left', 'middle', 'right']}.get(n, [])


def segments(raw, gutters):
    """One baseline's words -> [(column, words)], split where the gutters fall between words."""
    if not gutters:
        return [('full', raw)]
    names = column_names(len(gutters))
    edges = [float('-inf')] + list(gutters) + [float('inf')]
    parts = [[w for w in raw if w['x0'] >= edges[i] and w['x1'] <= edges[i + 1]] for i in range(len(names))]
    if sum(len(p) for p in parts) < len(raw):     # a word crosses a gutter: a full-width line
        return [('full', raw)]
    filled = [i for i, p in enumerate(parts) if p]
    for a, b in zip(filled, filled[1:]):
        left, right = parts[a], parts[b]
        # A space between two words of one full-width line can fall on a gutter too; the
        # gap between columns is wider than a word space.
        # But two columns' lines can share a baseline, so a jump in type size across the gutter
        # (a quote in one column, a heading in the other) is two lines.
        sl = max(c['size'] for c in left[-1]['chars'])
        sr = max(c['size'] for c in right[0]['chars'])
        size = max(sl, sr)
        if right[0]['x0'] - left[-1]['x1'] < max(4.0, 0.6 * size) and max(sl, sr) < 1.25 * min(sl, sr):
            return [('full', raw)]
    return [(names[i], parts[i]) for i in filled]


def glued(prev, w):
    """True when an inline icon and the word beside it touch on the page ("✠," prints no space)."""
    icon = prev['chars'][0].get('fontname') == 'Icon' or w['chars'][0].get('fontname') == 'Icon'
    return icon and w['x0'] - prev['x1'] < 1.0


def make_line(ws, page_no, column, height):
    spans = []
    weights = collections.Counter()
    text = ''
    for k, w in enumerate(ws):
        st = word_style(w)
        sep = '' if k and glued(ws[k - 1], w) else ' '
        text = text + sep + w['text'] if text else w['text']
        weights[(st['size'], st['font'])] += len(w['text'])
        if spans and all(spans[-1][k2] == st[k2] for k2 in ('size', 'bold', 'italic')):
            spans[-1]['text'] += sep + w['text']
        else:
            spans.append({'text': w['text'], 'size': st['size'], 'bold': st['bold'], 'italic': st['italic']})
    (size, font), _ = weights.most_common(1)[0]
    top = min(w['top'] for w in ws)
    bottom = max(w['bottom'] for w in ws)
    # A bare number is furniture when it is the page's own number (a table's "99" is not).
    furniture = top < height * MARGIN_TOP or bottom > height * (1 - MARGIN_BOTTOM) or \
        text.strip() == str(page_no)
    return {'page': page_no, 'column': column, 'top': round(top, 1), 'baseline': ws[0]['baseline'],
            'x0': round(min(w['x0'] for w in ws), 1), 'x1': round(max(w['x1'] for w in ws), 1),
            'text': text, 'size': size, 'bold': all(s['bold'] for s in spans),
            'italic': all(s['italic'] for s in spans), 'font': font, 'spans': spans,
            'words': [[w['text'], round(w['x0'], 1), round(w['x1'], 1)] for w in ws],
            'furniture': furniture}


def order_lines(words, gutters, page_no, height):
    """Words of one region -> lines in reading order: split at the gutters, then read in bands."""
    rows = collections.defaultdict(list)
    for w in words:
        rows[w['baseline']].append(w)
    segs = []                       # (baseline, column, words)
    for b, raw in rows.items():
        for col, ws in segments(sorted(raw, key=lambda w: w['x0']), gutters):
            segs.append((b, col, ws))
    segs.sort(key=lambda s: s[0])
    # A full-width line ends a band; within a band, read the columns left to right.
    bounds = sorted({b for b, c, _ in segs if c == 'full'}) + [float('inf')]
    out, prev = [], float('-inf')
    for bnd in bounds:
        for side in column_names(len(gutters)):
            out += [make_line(ws, page_no, side, height) for b, c, ws in segs if c == side and prev <= b < bnd]
        out += [make_line(ws, page_no, 'full', height) for b, c, ws in segs if c == 'full' and b == bnd]
        prev = bnd
    return out


def mask_opacity(im):
    """The share of an image its soft mask leaves opaque (0-1), or None: no mask, or one that can't
    be read (then the caller says so)."""
    mask = im['stream'].attrs.get('SMask')
    if mask is None:
        return None
    try:
        import io
        from PIL import Image
        m = mask.resolve()
        filters = m.attrs.get('Filter')
        filters = [f.name if hasattr(f, 'name') else str(f) for f in
                   (filters if isinstance(filters, list) else [filters])]
        if any(f.strip('/').strip("'") in ('DCTDecode', 'JPXDecode') for f in filters):
            img = Image.open(io.BytesIO(m.get_rawdata())).convert('L')
        else:
            w, h = m.attrs['Width'], m.attrs['Height']
            img = Image.frombytes('L', (w, h), m.get_data()[:w * h])
        hist = img.histogram()
        return sum(hist[128:]) / max(1, sum(hist))
    except Exception:  # noqa: BLE001 - reported by the caller
        return None


def text_runs_over(box, words, page_no, notes):
    """True when the page's text runs over the box's side edges rather than sitting inside it: a
    panel's text has a margin, but a picture's rectangle can lie under the text flowing past it.
    Such a box (a quarter or more of its lines with a word across an edge, or carrying on into it
    from a word space away) is set aside, and listed in
    `notes`."""
    x0, top, x1, bottom = box
    inside = [w for w in words if top <= (w['top'] + w['bottom']) / 2 <= bottom and
              x0 <= (w['x0'] + w['x1']) / 2 <= x1]
    rows = {round(w['baseline']) for w in inside}
    ids = {id(w) for w in inside}
    level = [w for w in words if top <= (w['top'] + w['bottom']) / 2 <= bottom]
    crossing = {round(w['baseline']) for w in level if any(w['x0'] < e - 1 and w['x1'] > e + 1 for e in (x0, x1))}
    # ...or a line of the page carries on into it, a word space from its edge.
    crossing |= {round(w['baseline']) for w in words if id(w) not in ids and round(w['baseline']) in rows and
                 (0 <= x0 - w['x1'] < RUN_ON_GAP or 0 <= w['x0'] - x1 < RUN_ON_GAP)}
    if rows and len(crossing) >= max(1, RUN_OVER_SHARE * len(rows)):
        if notes is not None:
            notes.append({'page': page_no, 'bbox': [round(v, 1) for v in box],
                          'note': f'text runs over its edges ({len(crossing)} of {len(rows)} lines): not a box'})
        return True
    return False


def find_boxes(page, page_no, notes=None):
    """Boxed panels: background images that don't fill the page (sidebars, tables), clipped to the
    page, largest first-inside-out; a box inside another is dropped. A picture cut out with a soft
    mask (an illustration: mostly see-through outside the figure) is not a panel, though its
    rectangle may run over the text beside it; a panel is opaque. Each image set aside, and each
    mask that couldn't be read (kept as a box), goes in `notes`."""
    area = page.width * page.height
    boxes = []
    for im in page.images:
        x0, top = max(0.0, im['x0']), max(0.0, im['top'])
        x1, bottom = min(page.width, im['x1']), min(page.height, im['bottom'])
        w, h = x1 - x0, bottom - top
        if w < BOX_MIN[0] or h < BOX_MIN[1] or w * h > 0.8 * area:
            continue
        where = {'page': page_no, 'bbox': [round(v, 1) for v in (x0, top, x1, bottom)]}
        if 'SMask' in im['stream'].attrs:
            opaque = mask_opacity(im)
            if opaque is None:
                if notes is not None:
                    notes.append(dict(where, note='image mask could not be read: kept as a box'))
            elif opaque < PANEL_OPAQUE:
                if notes is not None:
                    notes.append(dict(where, note=f'illustration ({opaque:.0%} opaque): not a box'))
                continue
        boxes.append((x0, top, x1, bottom))
    boxes = [b for b in boxes if not any(o != b and o[0] <= b[0] and o[1] <= b[1] and o[2] >= b[2] and
                                         o[3] >= b[3] for o in boxes)]
    return sorted(set(boxes), key=lambda b: (b[1], b[0]))


def merge_near(values, tol=2.0):
    out = []
    for v in sorted(values):
        if not out or v - out[-1] > tol:
            out.append(v)
    return out


def read_table(page, box, lines):
    """A ruled table inside `box`, or None. Rows are separated by horizontal rules and by the edges
    of shaded row bands; the header is the line just above the first rule, and the last row runs
    down from the last rule while its lines stay inside the table's width. Columns come from
    vertical rules, or from the header's word positions where there are none. Cells hold plain
    text, their words in reading order."""
    x0, top, x1, bottom = box
    inside = lambda o: o['x0'] >= x0 - 2 and o['x1'] <= x1 + 2 and o['top'] >= top - 2 and o['bottom'] <= bottom + 2
    hl = [l for l in page.lines if inside(l) and abs(l['top'] - l['bottom']) < 1 and l['x1'] - l['x0'] > 20]
    vl = [l for l in page.lines if inside(l) and abs(l['x0'] - l['x1']) < 1 and l['bottom'] - l['top'] > 6]
    bands = [r for r in page.rects if inside(r) and r['x1'] - r['x0'] > 15 and 4 < r['bottom'] - r['top'] < 60]
    rules = merge_near([l['top'] for l in hl] + [r['top'] for r in bands] + [r['bottom'] for r in bands])
    if len(rules) < 2:
        return None
    tx0 = min([l['x0'] for l in hl] + [r['x0'] for r in bands])
    tx1 = max([l['x1'] for l in hl] + [r['x1'] for r in bands])
    within = [l for l in lines if l['x0'] >= tx0 - 3 and l['x1'] <= tx1 + 3]
    above = sorted((l for l in within if l['baseline'] <= rules[0] + 1), key=lambda l: -l['baseline'])
    # The header: bold lines just above the first rule, gathered upwards while they stay close
    # together. Lines above it that aren't bold are a first data row (a table continued from the
    # page before has no header).
    header, first_row = [], []
    for l in above:
        prev = (header or first_row)[-1] if (header or first_row) else None
        if prev and prev['baseline'] - l['baseline'] > 1.8 * l['size']:
            break
        if header and l['size'] > header[0]['size'] + 0.5:     # the table's title, set larger
            break
        if not all(sp['bold'] for sp in l['spans']):
            if header:
                break
            first_row.append(l)
            continue
        header.append(l)
    if not header and not first_row and not any(rules[0] < l['baseline'] <= rules[-1] for l in within):
        return None
    # The last row: lines below the last rule, while they stay within the table and close together.
    tail, prev = [], rules[-1]
    for l in sorted((l for l in lines if l['baseline'] > rules[-1]), key=lambda l: l['baseline']):
        if l['x0'] < tx0 - 3 or l['x1'] > tx1 + 3 or l['top'] - prev > 1.8 * l['size']:
            break
        tail.append(l)
        prev = l['baseline']
    end = (tail[-1]['baseline'] + 2) if tail else rules[-1]
    edges = ([min(l['baseline'] for l in first_row) - 1] if first_row else []) + \
        [rules[0] - 0.01] + rules[1:] + ([end] if tail else [])
    if vl:
        cols = merge_near([l['x0'] for l in vl], 3)
    else:
        starts, last = [], None
        for t, a, b in sorted((w for l in (header or first_row) for w in l['words']), key=lambda w: w[1]):
            if last is None or a - last > 8:
                starts.append(a - 2)
            last = b
        cols = starts[1:]
    bounds = [tx0 - 3] + [c for c in cols if tx0 < c < tx1] + [tx1 + 3]
    ncol = len(bounds) - 1
    hdr_cells = [[] for _ in range(ncol)]
    rows = [[[] for _ in range(ncol)] for _ in range(len(edges) - 1)]
    used = set()
    seen = set()
    for l in sorted(within + tail, key=lambda l: (l['baseline'], l['x0'])):
        if id(l) in seen:
            continue
        seen.add(id(l))
        if l in header:
            target = hdr_cells
        else:
            r = next((i for i in range(len(edges) - 1) if edges[i] < l['baseline'] <= edges[i + 1] + 0.5), None)
            if r is None:
                continue
            target = rows[r]
        used.add(id(l))
        for t, a, b in l['words']:
            c = next((i for i in range(ncol) if bounds[i] <= (a + b) / 2 < bounds[i + 1]), ncol - 1)
            target[c].append(t)
    rows = [[' '.join(c) for c in r] for r in rows]
    rows = [r for r in rows if any(r)]
    return {'bbox': [round(tx0, 1), round(min([h['top'] for h in header + first_row] + [rules[0]]), 1),
                     round(tx1, 1), round(end, 1)],
            'columns': [' '.join(c) for c in hdr_cells], 'rows': rows, 'line_ids': used}


def titled_tables(page, box, lines):
    """A box holding several ruled tables, each under its own title (a line set well larger than
    the box's text), split into one part per table: [(sub-box,
    its lines)]. A box that isn't split this way, or whose parts don't each read as a table, is
    one part."""
    sizes = collections.Counter(l['size'] for l in lines)
    if not sizes:
        return [(box, lines)]
    body = sizes.most_common(1)[0][0]
    titles = sorted((l for l in lines if l['size'] >= body + 3),
                    key=lambda l: l['top'])
    cuts = [t['top'] - 2 for t in titles if t['top'] - box[1] > 3 * body]   # not the box's own heading
    if not cuts or len(titles) < 2:
        return [(box, lines)]
    edges = [box[1]] + cuts + [box[3]]
    parts = []
    for y0, y1 in zip(edges, edges[1:]):
        sub = (box[0], y0, box[2], y1)
        sl = [l for l in lines if y0 <= l['top'] < y1]
        if not sl or not read_table(page, sub, sl):
            return [(box, lines)]
        parts.append((sub, sl))
    return parts


def icon_words(page, words, icon_text, marks_here, shapes_here):
    """Words standing in for icons printed inline in the text, for icons --icon-text names: a glyph
    in a named font, or a drawing with a given number of points ("pts:57"). Each sits on the
    baseline of the text beside it; one with no text beside it is left out."""
    out = []
    items = [(m, icon_text.get(next((k for k in icon_text if not k.startswith('pts:') and
                                      k.lower() in m['font'].lower()), None)))
             for m in marks_here if not m['text'].isspace()]
    items += [(sh, icon_text.get(f'pts:{sh["pts"]}')) for sh in shapes_here]
    for it, text in items:
        if not text:
            continue
        cy = (it['top'] + it['bottom']) / 2
        near = [w for w in words if w['top'] - 2 <= cy <= w['bottom'] + 2 and
                (abs(w['x0'] - it['x1']) < 12 or abs(it['x0'] - w['x1']) < 12)]
        if not near:
            continue
        ref = min(near, key=lambda w: min(abs(w['x0'] - it['x1']), abs(it['x0'] - w['x1'])))
        c = dict(ref['chars'][0], text=text, x0=it['x0'], x1=it['x1'], fontname='Icon', matrix=None)
        out.append({'text': text, 'x0': it['x0'], 'x1': it['x1'], 'top': ref['top'], 'bottom': ref['bottom'],
                    'baseline': ref['baseline'], 'chars': [c]})
    return out


def page_lines(page, page_no, icon_fonts=(), marks=None, shapes=None, regions=None, icon_text=None,
               notes=None):
    """One page -> (lines in reading order, gutter x or None). Icon glyphs go to `marks`, small
    drawings to `shapes`, when those lists are given. With `regions` (a list), boxed panels are
    read as regions of their own: their lines follow the page's body lines, tagged with the box,
    and each box and ruled table is added to `regions`."""
    chars, marks_here, shapes_here = [], [], []
    for c in page.chars:
        f = font_name(c.get('fontname', ''))
        if icon_fonts and any(k.lower() in f.lower() for k in icon_fonts):
            marks_here.append({'page': page_no, 'x0': round(c['x0'], 1), 'x1': round(c['x1'], 1),
                               'top': round(c['top'], 1), 'bottom': round(c['bottom'], 1),
                               'font': f, 'text': c['text']})
            continue
        chars.append(c)
    for cv in page.curves:
        if cv['x1'] - cv['x0'] < SHAPE_MAX and cv['bottom'] - cv['top'] < SHAPE_MAX and cv.get('fill'):
            shapes_here.append({'page': page_no, 'x0': round(cv['x0'], 1), 'x1': round(cv['x1'], 1),
                                'top': round(cv['top'], 1), 'bottom': round(cv['bottom'], 1),
                                'pts': len(cv.get('pts') or [])})
    if marks is not None:
        marks += marks_here
    if shapes is not None:
        shapes += shapes_here
    words = make_words(chars, page.height)
    if icon_text:
        words += icon_words(page, words, icon_text, marks_here, shapes_here)
    boxes = find_boxes(page, page_no, notes) if regions is not None else []
    boxes = [b for b in boxes if not text_runs_over(b, words, page_no, notes)]
    in_box = {}
    for w in words:
        cx, cy = (w['x0'] + w['x1']) / 2, (w['top'] + w['bottom']) / 2
        for i, (x0, top, x1, bottom) in enumerate(boxes):
            if x0 <= cx <= x1 and top <= cy <= bottom:
                in_box[id(w)] = i
                break
    # Running heads and footers often cross the middle, and a large title can sit off-centre;
    # only the body's text, at its usual sizes, decides the gutter.
    body = [w for w in words if id(w) not in in_box]
    sizes = sorted(c['size'] for w in body for c in w['chars'])
    usual = sizes[len(sizes) // 2] * 1.4 if sizes else 0
    gutters = find_gutters([w for w in body if w['top'] >= page.height * MARGIN_TOP and
                            w['bottom'] <= page.height * (1 - MARGIN_BOTTOM) and
                            max(c['size'] for c in w['chars']) <= usual], page.width)
    out = order_lines(body, gutters, page_no, page.height)
    for i, box in enumerate(boxes):
        bw = [w for w in words if in_box.get(id(w)) == i]
        if not bw:
            continue
        bid = f'{page_no}.{i + 1}'
        # A box is one or two columns; a table's columns inside it are not text columns.
        bl = order_lines(bw, find_gutters(bw, box[2] - box[0], box[0], three=False), page_no, page.height)
        parts = titled_tables(page, box, bl)
        for k, (sub, sl) in enumerate(parts):
            sid = bid if len(parts) == 1 else f'{bid}.{k + 1}'
            for l in sl:
                l['box'] = sid
            region = {'id': sid, 'kind': 'box', 'page': page_no, 'bbox': [round(v, 1) for v in sub]}
            table = read_table(page, sub, sl)
            if table:
                for l in sl:
                    if id(l) in table['line_ids']:
                        l['table'] = sid
                region.update(kind='table', table_bbox=table['bbox'], columns=table['columns'],
                              rows=table['rows'])
            regions.append(region)
            out += sl
    return out, gutters


def assign_headings(lines):
    sizes = collections.Counter()
    for l in lines:
        if not l['furniture']:
            for s in l['spans']:
                sizes[s['size']] += len(s['text'])
    if not sizes:
        return sizes, None
    body = sizes.most_common(1)[0][0]
    # A size larger than the body's is a heading size only when it is rare: a size set as often as
    # a fifth of the body text (a sidebar's text, a quote) is text, not headings.
    larger = sorted((s for s in sizes if s > body + 0.4 and sizes[s] < max(HEADING_SHARE * sizes[body], 200)), reverse=True)
    # Nor is the size a box's text is mostly set in (its body), however few boxes the pages have.
    per_box = collections.defaultdict(collections.Counter)
    for l in lines:
        if l.get('box') and not l.get('table') and not l['furniture']:
            for s in l['spans']:
                per_box[l['box']][s['size']] += len(s['text'])
    # (A box holding little but its title, over a table, has no body to go by.)
    box_bodies = {c.most_common(1)[0][0] for c in per_box.values() if c and c.most_common(1)[0][1] >= 200}
    larger = [s for s in larger if all(abs(s - b) > 0.4 for b in box_bodies)]
    level = {s: i + 1 for i, s in enumerate(larger)}
    for l in lines:
        if l['furniture']:
            continue
        # A heading that runs on in smaller type ("Bell Ringing (Str) basic") is set by its lead:
        # a bold span at a heading size, a word or more long (not a drop capital).
        lead = l['spans'][0] if l['spans'] else None
        if (lead and lead['bold'] and lead['size'] in level and lead['size'] > l['size'] and
                len(re.findall(r'[^\W\d_]', lead['text'])) >= 3):
            l['size'] = lead['size']
        if l['size'] in level:
            l['heading'] = level[l['size']]
    return sizes, body


def read(pdf_path, first, last, offset, icon_fonts=(), boxes=False, icon_text=None):
    CASE_FIXED.clear()
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        if first + offset < 1 or last + offset > n:
            sys.exit(f'printed pages {first}-{last} with offset {offset} are PDF pages '
                     f'{first + offset}-{last + offset}, outside the PDF\'s 1-{n}')
        lines, marks, shapes, empty, gutters, regions, notes = [], [], [], [], {}, [], []
        for p in range(first, last + 1):
            got, gutters_here = page_lines(pdf.pages[p + offset - 1], p, icon_fonts, marks, shapes,
                                     regions if boxes else None, icon_text, notes)
            gutters[str(p)] = [round(g, 1) for g in gutters_here] or None
            if not got:
                empty.append(p)
            lines += got
    sizes, body = assign_headings(lines)
    return {'pages': f'{first}-{last}', 'page_offset': offset, 'body_size': body,
            'icon_fonts': list(icon_fonts),
            'fonts': [{'size': s, 'chars': c} for s, c in sorted(sizes.items(), reverse=True)],
            'gutters': gutters, 'pages_without_text': empty, 'lines': lines, 'marks': marks, 'shapes': shapes,
            'regions': regions, 'image_notes': notes, 'case_fixed': dict(CASE_FIXED)}


def text_view(doc):
    out = []
    for l in doc['lines']:
        tag = ('F' if l['furniture'] else 'T' if l.get('table') else f'H{l["heading"]}' if l.get('heading') else
               'B' if l.get('box') else '  ')
        style_ = ('B' if l['bold'] else ' ') + ('I' if l['italic'] else ' ')
        out.append(f'p{l["page"]:<4} {l["column"][0].upper()} {tag:>3} {l["size"]:>5} {style_} {l["text"]}')
    return '\n'.join(out) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf')
    ap.add_argument('--pages', required=True, help='printed page range, e.g. 30-109 or 87')
    ap.add_argument('--page-offset', type=int, default=0)
    ap.add_argument('--icon-fonts', nargs='*', default=[], help='fonts whose glyphs are icons, not text')
    ap.add_argument('--boxes', action='store_true', help='read boxed panels and their ruled tables as regions')
    ap.add_argument('--icon-text', nargs='*', default=[], metavar='ICON=TEXT',
                    help='put TEXT in the line where an icon is printed inline: FONT=TEXT for a glyph in an '
                         '--icon-fonts font, pts:N=TEXT for a drawing with N points')
    ap.add_argument('--out', help='write the layout JSON here')
    ap.add_argument('--text', action='store_true', help='print a readable view instead of JSON')
    a = ap.parse_args(argv)
    first, last = parse_pages(a.pages)
    icon_text = dict(x.split('=', 1) for x in a.icon_text)
    doc = read(a.pdf, first, last, a.page_offset, a.icon_fonts, a.boxes, icon_text)
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
        for font, k in doc['case_fixed'].items():
            print(f'font {font}: {k} capitals its character map read as lower case, kept as capitals',
                  file=sys.stderr)
        for n in doc['image_notes']:
            print(f'p{n["page"]} image {n["bbox"]}: {n["note"]}', file=sys.stderr)
    else:
        json.dump(doc, sys.stdout, ensure_ascii=False, indent=0)
        sys.stdout.write('\n')


if __name__ == '__main__':
    main()
