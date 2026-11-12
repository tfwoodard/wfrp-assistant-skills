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
text in a size the chapter uses rarely (a size used as much as a sidebar's
text is text, not headings). `fonts` lists every size with how many characters use it; `body_size` is
the commonest. `gutters` gives each page's gutter x (null: one column).

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
plain text); its lines carry `table` too.

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
BOX_MIN = (100, 24)                      # points: a smaller image isn't a boxed panel
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


def find_gutter(words, width, left=0.0):
    """The x of the gutter between `left` and `left + width`, or None. Counts, for each point
    across the middle, the words that cross it; the gutter is the middle of the widest run that at
    most a few cross."""
    lo, hi = int(left + width * GUTTER_ZONE[0]), int(left + width * GUTTER_ZONE[1])
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
        # But two columns' lines can share a baseline, so a jump in type size across the gutter
        # (a quote in one column, a heading in the other) is two lines.
        sl = max(c['size'] for c in left[-1]['chars'])
        sr = max(c['size'] for c in right[0]['chars'])
        size = max(sl, sr)
        if right[0]['x0'] - left[-1]['x1'] < max(4.0, 0.6 * size) and max(sl, sr) < 1.25 * min(sl, sr):
            return [('full', raw)]
    return [(c, ws) for c, ws in (('left', left), ('right', right)) if ws]


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
    furniture = top < height * MARGIN_TOP or bottom > height * (1 - MARGIN_BOTTOM) or \
        bool(re.fullmatch(r'\d{1,4}', text))
    return {'page': page_no, 'column': column, 'top': round(top, 1), 'baseline': ws[0]['baseline'],
            'x0': round(min(w['x0'] for w in ws), 1), 'x1': round(max(w['x1'] for w in ws), 1),
            'text': text, 'size': size, 'bold': all(s['bold'] for s in spans),
            'italic': all(s['italic'] for s in spans), 'font': font, 'spans': spans,
            'words': [[w['text'], round(w['x0'], 1), round(w['x1'], 1)] for w in ws],
            'furniture': furniture}


def order_lines(words, gutter, page_no, height):
    """Words of one region -> lines in reading order: split at the gutter, then read in bands."""
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
            out += [make_line(ws, page_no, side, height) for b, c, ws in segs if c == side and prev <= b < bnd]
        out += [make_line(ws, page_no, 'full', height) for b, c, ws in segs if c == 'full' and b == bnd]
        prev = bnd
    return out


def find_boxes(page):
    """Boxed panels: background images that don't fill the page (sidebars, tables), clipped to the
    page, largest first-inside-out; a box inside another is dropped."""
    area = page.width * page.height
    boxes = []
    for im in page.images:
        x0, top = max(0.0, im['x0']), max(0.0, im['top'])
        x1, bottom = min(page.width, im['x1']), min(page.height, im['bottom'])
        w, h = x1 - x0, bottom - top
        if w < BOX_MIN[0] or h < BOX_MIN[1] or w * h > 0.8 * area:
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


def page_lines(page, page_no, icon_fonts=(), marks=None, shapes=None, regions=None, icon_text=None):
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
    boxes = find_boxes(page) if regions is not None else []
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
    gutter = find_gutter([w for w in body if w['top'] >= page.height * MARGIN_TOP and
                          w['bottom'] <= page.height * (1 - MARGIN_BOTTOM) and
                          max(c['size'] for c in w['chars']) <= usual], page.width)
    out = order_lines(body, gutter, page_no, page.height)
    for i, box in enumerate(boxes):
        bw = [w for w in words if in_box.get(id(w)) == i]
        if not bw:
            continue
        bid = f'{page_no}.{i + 1}'
        bl = order_lines(bw, find_gutter(bw, box[2] - box[0], box[0]), page_no, page.height)
        for l in bl:
            l['box'] = bid
        region = {'id': bid, 'kind': 'box', 'page': page_no, 'bbox': [round(v, 1) for v in box]}
        table = read_table(page, box, bl)
        if table:
            for l in bl:
                if id(l) in table['line_ids']:
                    l['table'] = bid
            region.update(kind='table', table_bbox=table['bbox'], columns=table['columns'], rows=table['rows'])
        regions.append(region)
        out += bl
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
    # A size larger than the body's is a heading size only when it is rare: a size set as often as
    # a fifth of the body text (a sidebar's text, a quote) is text, not headings.
    larger = sorted((s for s in sizes if s > body + 0.4 and sizes[s] < max(HEADING_SHARE * sizes[body], 200)), reverse=True)
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
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        if first + offset < 1 or last + offset > n:
            sys.exit(f'printed pages {first}-{last} with offset {offset} are PDF pages '
                     f'{first + offset}-{last + offset}, outside the PDF\'s 1-{n}')
        lines, marks, shapes, empty, gutters, regions = [], [], [], [], {}, []
        for p in range(first, last + 1):
            got, gutter = page_lines(pdf.pages[p + offset - 1], p, icon_fonts, marks, shapes,
                                     regions if boxes else None, icon_text)
            gutters[str(p)] = None if gutter is None else round(gutter, 1)
            if not got:
                empty.append(p)
            lines += got
    sizes, body = assign_headings(lines)
    return {'pages': f'{first}-{last}', 'page_offset': offset, 'body_size': body,
            'icon_fonts': list(icon_fonts),
            'fonts': [{'size': s, 'chars': c} for s, c in sorted(sizes.items(), reverse=True)],
            'gutters': gutters, 'pages_without_text': empty, 'lines': lines, 'marks': marks, 'shapes': shapes,
            'regions': regions}


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
    else:
        json.dump(doc, sys.stdout, ensure_ascii=False, indent=0)
        sys.stdout.write('\n')


if __name__ == '__main__':
    main()
