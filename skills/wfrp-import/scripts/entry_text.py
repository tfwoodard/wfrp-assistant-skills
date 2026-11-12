"""Text helpers shared by the converters: lines from pdf_layout.py -> entry text and blocks.

Pure functions, no I/O. Each takes the converter's `report` where it has something
to say, so nothing is decided silently.
"""
import re

ROLL = re.compile(r'^\s*(\d{1,3})\s*(?:[–—-]\s*(\d{1,3}))?\s*$')
NUMBER = re.compile(r'^\s*([+−–-]?)\s*(\d{1,3}(?:,\d{3})*|\d+)\s*$')


def slugify(s):
    s = s.lower().replace('’', '').replace("'", '')
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def norm(s):
    """For matching headings: lower case, straight quotes, single spaces."""
    return re.sub(r'\s+', ' ', s.replace('’', "'").replace('‘', "'")).strip().lower()


def marked(line):
    """A line's text with italic and bold spans marked as Markdown. Punctuation after a styled run
    stays outside its marks, and neighbouring italic runs join."""
    out = []
    for sp in line['spans']:
        m = re.match(r'^(.*?)([,;:.]*)$', sp['text'], re.S)
        t, tail = m.group(1), m.group(2)
        if not t:
            out.append(sp['text'])
            continue
        if sp['italic'] and sp['bold']:
            t = f'***{t}***'
        elif sp['italic']:
            t = f'*{t}*'
        elif sp['bold']:
            t = f'**{t}**'
        out.append(t + tail)
    return re.sub(r'(?<!\*)\*(\s+)\*(?!\*)', r'\1', ' '.join(out))


def plain(s):
    return re.sub(r'\*+', '', s).strip()


SMALL_WORDS = {'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'from', 'in', 'into', 'of', 'on', 'or', 'the',
               'to', 'with'}


def fix_case(text):
    """Display type set in small capitals reads back in a jumble of cases ("CharaCteristiC and
    skill"). Such a heading is title-cased; the words stay the same. Anything else is unchanged."""
    if not re.search(r'[a-z][A-Z]|\b[a-z]+[A-Z]|^[a-z]', text):
        return text
    out = []
    for i, orig in enumerate(text.split(' ')):
        w = orig.lower()
        if re.fullmatch(r'[A-Z]{2,3}', orig):            # an acronym (XP, SL) stays as printed
            out.append(orig)
        elif i and w in SMALL_WORDS:
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:])
    return ' '.join(out)


def split_items(s):
    """Split a printed list at commas outside parentheses."""
    items, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            items.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        items.append(cur.strip())
    return items


def vocabulary(lines):
    """Every word the lines print whole (not broken at a line end), lower-cased: the evidence for
    whether a word broken across lines is hyphenated or only split."""
    vocab = set()
    for l in lines:
        words = l['text'].split()
        for i, w in enumerate(words):
            if i == len(words) - 1 and w.endswith('-'):
                continue
            vocab.add(re.sub(r'^[^\w]+|[^\w-]+$', '', w).lower())
    return vocab


def join_lines(parts, report, where, vocab=None):
    """Join a run of line texts into one string. A line ending in a hyphen joins the next with no
    space. With `vocab` (vocabulary()), the hyphen is dropped when the book prints the joined word
    whole elsewhere and never hyphenated (a word split only to fit the line), and kept when it
    prints the hyphenated form or neither; each case is reported: `dehyphenated` for the ones
    dropped (check_coverage.py credits them), a question for the ones kept."""
    out = ''
    for p in parts:
        end = re.search(r'-(\*{0,3})$', out)
        if not out:
            out = p
        elif end:
            marks = end.group(1)
            if marks and p.startswith(marks) and not p.startswith(marks + '*'):
                out, p = out[:-len(marks)], p[len(marks):]     # one styled run across the line break
            head = re.search(r'([\w’\']+)-$', out)
            tail = re.match(r'^\*{0,3}([\w’\']+)', p)
            if vocab is not None and head and tail:
                whole = (head.group(1) + tail.group(1)).lower()
                hyph = (head.group(1) + '-' + tail.group(1)).lower()
                if whole in vocab and hyph not in vocab:
                    report.setdefault('dehyphenated', []).append(
                        {'entry': where, 'from': head.group(1) + '-' + tail.group(1), 'to': head.group(1) + tail.group(1)})
                    out = out[:-1] + p
                    continue
                kind = 'hyphen-join' if hyph in vocab else 'hyphen-unresolved'
            else:
                kind = 'hyphen-join'
            report['questions'].append({'entry': where, 'kind': kind, 'text': out[-20:] + p[:20]})
            out += p
        else:
            out += ' ' + p
    return out


def new_paragraph(l, prev):
    return (prev is None or l['column'] != prev['column'] or l['page'] != prev['page'] or
            l.get('box') != prev.get('box') or l['baseline'] - prev['baseline'] > 1.6 * prev['size'] or
            l['baseline'] < prev['baseline'])


def blocks_from_lines(lines, report, where, vocab=None, base_level=None):
    """Lines -> content blocks: headings (lines marked `heading` by pdf_layout.py, at a smaller size
    than the entry's own when `base_level` is given), bulleted lists (lines starting "•"), and
    paragraphs (a new one at a column, page or box change or a wider gap)."""
    blocks, buf, items, prev, bullet_x0 = [], [], [], None, None

    def flush():
        nonlocal buf, items
        if buf:
            blocks.append({'type': 'paragraph', 'text': join_lines(buf, report, where, vocab)})
        if items:
            blocks.append({'type': 'list', 'ordered': False,
                           'items': [join_lines(i, report, where, vocab) for i in items]})
        buf, items = [], []

    for l in lines:
        text = marked(l)
        if l.get('heading') and (base_level is None or l['heading'] > base_level):
            flush()
            if blocks and blocks[-1]['type'] == 'heading' and prev is not None and prev.get('heading') == l['heading'] \
                    and l['baseline'] - prev['baseline'] < 1.6 * l['size']:
                blocks[-1]['text'] = fix_case(blocks[-1]['text'] + ' ' + plain(text))   # one heading, two lines
            else:
                blocks.append({'type': 'heading', 'level': l['heading'], 'text': fix_case(plain(text))})
            prev = l
            continue
        bullet = re.match(r'^\s*[•●▪]\s*', plain(l['text']))
        if bullet:
            if buf:
                flush()
            items.append([re.sub(r'^\s*\**\s*[•●▪]\s*', '', text)])
            bullet_x0 = l['x0']
        elif items and prev is not None and not new_paragraph(l, prev) and l['x0'] > bullet_x0 + 1:
            items[-1].append(text)
        else:
            if items or new_paragraph(l, prev):
                flush()
            buf.append(text)
        prev = l
    flush()
    return blocks


def cell_value(s):
    """A table cell as data: "—" is None; "+N", "−N" and plain numbers are numbers; a roll ("01–09",
    "00") is {"min", "max"}; anything else is the printed text."""
    t = plain(s).strip()
    if t in ('—', '–', '-', ''):
        return None
    m = NUMBER.match(t)
    if m:
        n = int(m.group(2).replace(',', ''))
        return -n if m.group(1) in ('−', '–', '-') else n
    return t


def roll_value(s):
    m = ROLL.match(plain(s))
    if not m:
        return cell_value(s)
    lo, hi = m.group(1), m.group(2) or m.group(1)
    to_n = lambda v: 100 if v in ('00', '000') else int(v)
    return {'min': to_n(lo), 'max': to_n(hi)}


def table_data(columns, rows, report, where, roll_column=None):
    """Rows of cells -> `data`: one object per row keyed by the column headers in words. An empty
    cell in a leading column, under a cell that isn't, takes the value above (a cell printed once
    for several rows); every such fill is reported."""
    keys = [slugify(c).replace('-', '_') or f'column_{i + 1}' for i, c in enumerate(columns)]
    data, above = [], {}
    for r, row in enumerate(rows):
        obj = {}
        lead = True
        for i, (k, cell) in enumerate(zip(keys, row)):
            if not cell.strip() and lead and i in above and any(c.strip() for c in row[i + 1:]):
                obj[k] = above[i]
                report.setdefault('filled_down', []).append({'entry': where, 'row': r + 1, 'column': columns[i] if
                                                             i < len(columns) else k})
                continue
            if cell.strip():
                lead = False
            obj[k] = roll_value(cell) if i == roll_column else cell_value(cell)
            above[i] = obj[k]
        data.append(obj)
    return data
