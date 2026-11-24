#!/usr/bin/env python3
"""Plan packs: a chapter plan with no book text in it, to share with other groups who own the book.

    plan_pack.py export PLAN.json LAYOUT.json --out PACK.json [--pdf BOOK.pdf] [--library-data DIR]
    plan_pack.py install PACK.json LAYOUT.json --out PLAN.json [--pdf BOOK.pdf] [--library-data DIR]

A plan names entries, headings, tables and table cells in the book's own words, so it can't be
shared. A pack keeps the plan's shape, its page numbers, the tool's own words (kinds,
categories, relation roles, dice) and the PDF's icon fonts and symbols, and puts a fingerprint (a hash) in place of every other string
and every other dictionary key: {"#": ...} for text, {"#slug": ...} for a slug, which is made from
a name. Install rebuilds each fingerprint from the installer's own copy of the book: every line,
heading and run of words in their layout of the chapter, and the slugs of their own library. So a
pack carries none of the book's words, and what it rebuilds comes from the installer's own pages.

A value the installer's book can't give back (a heading the Librarian renamed, a hand-typed
table row, a stat not printed as one run of words) is left out of the pack and listed in its
"left_out" by position only; an entry or table whose name is left out is left out whole. Export
checks the pack by installing it on the same layout and library: the rebuilt plan must be the plan
with exactly those values left out, or it writes nothing. The converter's own checks then show an
installer what is left to do (a heading the plan no longer places is an error).
"""
import argparse, copy, hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entry_text import fix_case, slugify  # noqa: E402

SALT = 'wfrp-plan-pack:'
TOOL_WORD = re.compile(r'^[a-z0-9][a-z0-9_.+-]*$')         # kinds, categories, roles, dice, field names
SLUG_PATH = re.compile(r'^[a-z][a-z-]*/[a-z0-9][a-z0-9-]*$')  # "trappings/dagger-elven"
PLAIN_KEYS = {'source', 'chapter'}                          # which book and chapter: said as they are
PLAIN_TREES = {'icon_fonts', 'icon_text', 'level_icons'}    # the PDF's fonts and symbols, for its layout
SLUG_MAPS = {'relations'}                                   # dictionaries keyed by slugs
CONTENT_KEYS = {'fields', 'rows', 'footnotes', 'added'}     # numbers here are the book's, not the plan's
NGRAM = 12                                                  # the longest run of words looked for
NAMES = ('name', 'title')                                   # an item that loses these goes whole


def fp(s):
    return hashlib.sha256((SALT + s).encode('utf-8')).hexdigest()[:20]


def pdf_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# --- what a book can give back ---------------------------------------------------------------

def forms(t):
    t = t.strip()
    out = {t, fix_case(t), t.lower(), t.upper(), t.title(), t.rstrip('.:,;'), fix_case(t.rstrip('.:,;'))}
    return {x for x in out if x}


def texts(layout):
    """Every string the installer's layout can give: each line, each pair of neighbouring lines
    joined, every run of up to NGRAM words in them, in a few cases (as printed, title case,
    capitals, small capitals mended)."""
    lines = [l['text'] for l in layout['lines'] if l.get('text')]
    pieces = set(lines)
    for a, b in zip(lines, lines[1:]):
        pieces.add(a + ' ' + b)
        if a.endswith('-'):
            pieces.add(a[:-1] + b)
            pieces.add(a + b)
    out = set()
    for p in pieces:
        words = p.split()
        for i in range(len(words)):
            for j in range(i + 1, min(len(words), i + NGRAM) + 1):
                out |= forms(' '.join(words[i:j]))
        out |= forms(p)
    return out


def library_slugs(library_data):
    out = set()
    if not library_data or not os.path.isdir(library_data):
        return out
    for cat in os.listdir(library_data):
        path = os.path.join(library_data, cat, '_index.json')
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as f:
            for r in json.load(f):
                if isinstance(r, dict) and r.get('slug'):
                    out.add(r['slug'])
    return out


def books_words(layout, library_data, sources=()):
    """{fingerprint: text} and {slug fingerprint: slug} the installer's book and library give."""
    words = texts(layout)
    text = {fp(t): t for t in words}
    slugs = library_slugs(library_data)
    suffixes = [''] + ['-' + s.lower() for s in sources]
    for t in words:
        s = slugify(t)
        if s:
            slugs.update(s + x for x in suffixes)
    return text, {fp('slug:' + s): s for s in slugs}


WORD = re.compile(r"[^\W_][\w'’.-]*|[^\w\s]+|_+|\s+")


def words_of(s):
    """s as words, spaces and punctuation; the words are what a book must give back."""
    return WORD.findall(s)


def is_word(piece):
    return bool(re.match(r'[^\W_]', piece))


def by_words(s, text):
    """s rebuilt word by word ({"#w": [...]}: a fingerprint for each word, spaces and punctuation as
    they are), or None when a word isn't printed in the chapter."""
    pieces = words_of(s)
    if ''.join(pieces) != s:
        return None
    out = []
    for p in pieces:
        if is_word(p):
            if fp(p) not in text:
                return None
            out.append({'#': fp(p)})
        else:
            out.append(p)
    return {'#w': out}


def text_value(s, text):
    """A string of the book's: its fingerprint, or word by word, or None."""
    if fp(s) in text:
        return {'#': fp(s)}
    return by_words(s, text)


# --- export ----------------------------------------------------------------------------------

def slug_value(s):
    """A slug in a pack: its category (a tool word) as it is, the slug by its fingerprint."""
    cat, _, bare = s.rpartition('/')
    return {'#slug': fp('slug:' + bare), **({'in': cat} if cat else {})}


def slug_key(s):
    cat, _, bare = s.rpartition('/')
    return '#slug:' + (cat + '/' if cat else '') + fp('slug:' + bare)


def is_slug_position(path):
    """A slug's place: a "slug", or a relation's "to" (a box's "to" names an entry instead)."""
    keys = [p for p in path if isinstance(p, str)]
    return bool(keys) and (keys[-1] == 'slug' or (keys[-1] == 'to' and 'relations' in keys))


def pack_value(v, path, in_content, text):
    """v with every string and key of the book's in fingerprints. v is the plan as `without` left
    it, so every such string has one."""
    if path and path[0] in PLAIN_TREES:
        return v
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return {'#n': fp(str(v))} if in_content else v
    if isinstance(v, str):
        if path and path[-1] in PLAIN_KEYS and len(path) == 1:
            return v
        if is_slug_position(path) or SLUG_PATH.match(v):
            return slug_value(v)
        if TOOL_WORD.match(v) and not in_content:
            return v
        return text_value(v, text)
    if isinstance(v, list):
        return [pack_value(x, path + [i], in_content, text) for i, x in enumerate(v)]
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            content = in_content or k in CONTENT_KEYS
            if path and path[-1] in SLUG_MAPS or SLUG_PATH.match(k):
                key = slug_key(k)
            elif TOOL_WORD.match(k) or re.match(r'^\d+(\.\d+)?$', k):
                key = k
            elif fp(k) in text:
                key = '#:' + fp(k)
            else:
                key = '#w:' + json.dumps(by_words(k, text)['#w'], ensure_ascii=False)
            out[key] = pack_value(x, path + [k], content, text)
        return out
    raise ValueError(f'a {type(v).__name__} at {"/".join(path)}')


# --- install ---------------------------------------------------------------------------------

class Missing(Exception):
    pass


def unpack_value(v, text, slugs, path, left):
    if isinstance(v, dict) and len(v) == 1 and next(iter(v)) == '#w':
        return rebuild_words(v['#w'], text)
    if path and path[0] in PLAIN_TREES:
        return v
    if isinstance(v, dict) and '#slug' in v and set(v) <= {'#slug', 'in'}:
        if v['#slug'] not in slugs:
            raise Missing()
        return (v['in'] + '/' if 'in' in v else '') + slugs[v['#slug']]
    if isinstance(v, dict) and len(v) == 1 and next(iter(v)) in ('#', '#n'):
        (kind, h), = v.items()
        table = text
        if h not in table:
            raise Missing()
        got = table[h]
        if kind == '#n':
            return json.loads(got) if re.match(r'^-?\d+(\.\d+)?$', got) else got
        return got
    if isinstance(v, list):
        out = []
        for i, x in enumerate(v):
            try:
                y = unpack_value(x, text, slugs, path + [i], left)
            except Missing:
                left.append(path + [i])
                continue
            if isinstance(x, dict) and any(n in x for n in NAMES) and not any(n in y for n in NAMES):
                left.append(path + [i, 'whole'])      # an entry that lost its name goes whole
                continue
            out.append(y)
        return out
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if k.startswith('#w:'):
                try:
                    key = rebuild_words(json.loads(k[3:]), text)
                except Missing:
                    left.append(path + [k])
                    continue
            elif k.startswith('#slug:'):
                cat, _, h = k[len('#slug:'):].rpartition('/')
                if h not in slugs:
                    left.append(path + [k])
                    continue
                key = (cat + '/' if cat else '') + slugs[h]
            elif k.startswith('#:'):
                h = k[2:]
                if h not in text:
                    left.append(path + [k])
                    continue
                key = text[h]
            else:
                key = k
            try:
                out[key] = unpack_value(x, text, slugs, path + [key], left)
            except Missing:
                left.append(path + [key])
        return out
    return v


def rebuild_words(pieces, text):
    out = []
    for p in pieces:
        if isinstance(p, dict):
            if p['#'] not in text:
                raise Missing()
            out.append(text[p['#']])
        else:
            out.append(p)
    return ''.join(out)


def install(pack, layout, library_data):
    text, slugs = books_words(layout, library_data, [pack.get('source', '')])
    left = []
    return unpack_value(pack['plan'], text, slugs, [], left), left


# --- the check -------------------------------------------------------------------------------

def without(plan, text, slugs):
    """The plan as an install can rebuild it: each value the book can't give is taken out, and a
    list item that loses its name or title goes whole. Returns (that plan, the paths taken out)."""
    gone = []

    def can(v, path, in_content):
        """v as rebuilt, or raises Missing."""
        if path and path[0] in PLAIN_TREES:
            return v
        if isinstance(v, bool) or v is None:
            return v
        if isinstance(v, (int, float)):
            if in_content and fp(str(v)) not in text:
                raise Missing()
            return v
        if isinstance(v, str):
            if path and path[-1] in PLAIN_KEYS and len(path) == 1:
                return v
            if is_slug_position(path) or SLUG_PATH.match(v):
                if fp('slug:' + v.rpartition('/')[2]) not in slugs:
                    raise Missing()
                return v
            if TOOL_WORD.match(v) and not in_content:
                return v
            if text_value(v, text) is None:
                raise Missing()
            return v
        if isinstance(v, list):
            out = []
            for i, x in enumerate(v):
                try:
                    y = can(x, path + [i], in_content)
                except Missing:
                    gone.append(path + [i])
                    continue
                if isinstance(x, dict) and any(n in x for n in NAMES) and not any(n in y for n in NAMES):
                    gone.append(path + [i, 'whole'])
                    continue
                out.append(y)
            return out
        if isinstance(v, dict):
            out = {}
            for k, x in v.items():
                if path and path[-1] in SLUG_MAPS or SLUG_PATH.match(k):
                    ok = fp('slug:' + k.rpartition('/')[2]) in slugs
                elif TOOL_WORD.match(k) or re.match(r'^\d+(\.\d+)?$', k):
                    ok = True
                else:
                    ok = text_value(k, text) is not None
                if not ok:
                    gone.append(path + [k])
                    continue
                try:
                    out[k] = can(x, path + [k], in_content or k in CONTENT_KEYS)
                except Missing:
                    gone.append(path + [k])
            return out
        return v

    return can(plan, [], False), gone


def export(plan, layout, library_data, pdf=None):
    text, slugs = books_words(layout, library_data, [plan.get('source', '')])
    kept, gone = without(plan, text, slugs)
    pack = {'pack': 1, 'source': plan.get('source'), 'chapter': plan.get('chapter'),
            'pages': layout.get('pages'), 'plan': pack_value(kept, [], False, text),
            'left_out': ['/'.join(step(x) for x in p) for p in gone]}
    if pdf:
        pack['pdf_sha256'] = pdf_sha256(pdf)
    rebuilt, left = install(pack, layout, library_data)
    if rebuilt != kept or left:
        raise SystemExit('the pack does not rebuild the plan: nothing written'
                         + (f' ({len(left)} values not rebuilt)' if left else ''))
    said = json.dumps(pack, ensure_ascii=False)
    plain = {plan.get(k) for k in PLAIN_KEYS} | {s for k in PLAIN_TREES for s in strings(plan.get(k))}
    leaks = sorted({s for s in strings(plan) if len(s) > 3 and s not in plain and not TOOL_WORD.match(s) and s in said})
    if leaks:
        raise SystemExit(f'the pack still holds {len(leaks)} of the plan\'s own strings: nothing written')
    return pack, kept


def step(x):
    """A step of a path, as a pack may show it: an index or a tool word as it is, anything else
    (a key in the book's words) by its fingerprint."""
    if isinstance(x, int) or TOOL_WORD.match(str(x)) or re.match(r'^\d+(\.\d+)?$', str(x)):
        return str(x)
    return '#' + fp(str(x))


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)
    elif isinstance(v, dict):
        for k, x in v.items():
            yield k
            yield from strings(x)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('export', 'install'):
        p = sub.add_parser(name)
        p.add_argument('src', help='the plan (export) or the pack (install)')
        p.add_argument('layout')
        p.add_argument('--out', required=True)
        p.add_argument('--pdf', help="the book's PDF: export records its SHA-256, install compares it")
        p.add_argument('--library-data', help='the library, whose slugs relations point at')
    a = ap.parse_args(argv)
    with open(a.src, encoding='utf-8') as f:
        src = json.load(f)
    with open(a.layout, encoding='utf-8') as f:
        layout = json.load(f)
    if a.cmd == 'export':
        pack, kept = export(src, layout, a.library_data, a.pdf)
        out = json.dumps(pack, ensure_ascii=False, indent=1) + '\n'
        print(f'{a.out}: {len(pack["left_out"])} values left out, the rest rebuilds from the book', file=sys.stderr)
    else:
        if a.pdf and src.get('pdf_sha256') and pdf_sha256(a.pdf) != src['pdf_sha256']:
            print('this PDF is not the one the pack was made from: pages may differ, check what is left out', file=sys.stderr)
        plan, left = install(src, layout, a.library_data)
        out = json.dumps(plan, ensure_ascii=False, indent=1) + '\n'
        print(f'{a.out}: rebuilt; {len(src.get("left_out", []))} values were left out of the pack'
              + (f', {len(left)} more not found in this book: ' + ', '.join('/'.join(map(str, p)) for p in left[:20]) if left else ''),
              file=sys.stderr)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
