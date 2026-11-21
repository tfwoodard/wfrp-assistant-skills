"""Read the library for the skills' scripts: entries, sections inside them, and their text.
The master copy is shared/scripts/library.py; scripts/sync-shared.sh copies it into the skills.

    lib = Library("/path/to/WFRP Assistant", campaign="the-enemy-within")
    lib.entry("careers/rat-catcher")                      # the entry's JSON
    lib.section("rules/advancing-through-your-career#Skill Advances")   # [blocks] under that heading
    lib.named("skills", "Melee (Basic)")                  # ("skills/melee", "Basic")
    lib.text(blocks)                                      # Markdown-style text
    lib.html(blocks)                                      # HTML

A **ref** is "<category>/<slug>" for a whole entry, plus "#<heading>" for part of it. Headings can
be a path ("Characteristic Advances › Costs"); each part is found below the one before. When the
last part isn't a heading, it names a paragraph that starts with it in bold ("**Skills**: ...").

Entries come from the campaign's own library-data first (its homebrew), then the library's, and
only from the campaign's sources in play (library-layout.md §8). An entry that another entry in
play *replaces* isn't used: the replacement is. Players never see `gm/` data or entries marked
`audience: gm`; pass gm=True for the GM.
"""
import html as _html
import json
import os
import re
import sys


def norm(s):
    s = (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def bare(heading):
    """A heading or bold lead without its closing colon or stop: 'Skills:' -> 'skills'."""
    return norm(heading).rstrip(":.").strip()


LEAD = re.compile(r"^\*{2,3}([^*]+?)[.:]?\*{2,3}:?\s*")
SPECIALISED = re.compile(r"^(.*?)\s*\(([^()]*)\)$")


class RefError(LookupError):
    pass


class MissingFiles(Exception):
    """Library files a read needed that aren't in this copy of the library (paths from its root).
    Not a RefError: the entry may well exist in Drive, it just hasn't been fetched here."""

    def __init__(self, paths):
        self.paths = list(paths)
        super().__init__("library files not here: " + ", ".join(self.paths))


CATEGORIES = ("rules", "tables", "species", "careers", "skills", "talents", "spells", "trappings",
              "qualities", "creatures", "traits", "diseases", "mutations", "lore")     # layout §2


def cli(main):
    """Run a script's main, turning a missing library file into one plain line instead of a traceback."""
    try:
        main()
    except MissingFiles as e:
        sys.exit(f"{e}\nFetch them from the library (same paths under its root) and run this again.")


def chapter_titles(lib):
    """{(source code, chapter id): title} from library.json and the campaign's own sources."""
    out = {}
    path = os.path.join(lib.root, "library.json")
    sources = (lib._json(path) or {}).get("sources", []) if os.path.exists(path) else []
    for s in sources + list((lib.campaign or {}).get("campaign_sources", [])):
        for c in s.get("chapters", []):
            if c.get("id") and c.get("title"): out[(s.get("code"), c["id"])] = c["title"]
    return out


def cite(rec, titles=None):
    """(CRB, ch. 5 › Fear, p. 190): the chapter's number, or its short title when it has none (layout §5)."""
    ch = rec.get("chapter") or ""
    m = re.match(r"ch(\d+)", ch)
    if m:
        ch = f"ch. {m.group(1)}"
    else:
        title = (titles or {}).get((rec.get("source"), ch), ch)
        ch = re.split(r":\s", title)[0] if re.match(r"(Appendix|Introduction)\b", title) else title
    page = f', p. {rec["page"]}' if rec.get("page") else ""
    return f'({rec.get("source")}, {ch} › {rec.get("section") or rec.get("name")}{page})'


class Library:
    def __init__(self, root, campaign=None, gm=False, lenient=False):
        """lenient: a missing file is noted in `missing` and read as empty, so one pass can list
        everything a build needs (needs.py). Otherwise a missing file raises MissingFiles."""
        self.root = root
        self.gm = gm
        self.lenient = lenient
        self.missing = []       # library files asked for that aren't here
        self.read = []          # library files read
        self.campaign = None
        self.sources = None
        self.roots = []
        if campaign:
            cdir = os.path.join(root, "campaigns", campaign)
            self.campaign = self._json(os.path.join(cdir, "campaign.json")) or {}
            self.sources = set(self.campaign.get("sources") or []) or None
            if gm:
                self.roots.append(os.path.join(cdir, "gm", "library-data"))
            self.roots.append(os.path.join(cdir, "library-data"))
        self.roots.append(os.path.join(root, "library-data"))
        self._index = {}
        self._records = {}
        self._entries = {}
        lib_edition = None
        lp = os.path.join(root, "library.json")
        if os.path.exists(lp):
            lib_edition = self._json(lp).get("edition")
        # the rules edition played by (layout §8 "Editions"): entries it updated don't exist
        self.edition = (self.campaign or {}).get("edition") or lib_edition or "4e"
        self._updated = None
        self._replaced = None
        self._added = None

    def rel(self, path):
        return os.path.relpath(path, self.root).replace(os.sep, "/")

    def _json(self, path):
        """A library file's JSON; when it isn't here: None if lenient (noted in `missing`), else MissingFiles."""
        if not os.path.exists(path):
            if self.rel(path) not in self.missing: self.missing.append(self.rel(path))
            if self.lenient: return None
            raise MissingFiles([self.rel(path)])
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if self.rel(path) not in self.read: self.read.append(self.rel(path))
        return data

    def absent_indexes(self):
        """The library's own category indexes that aren't here. A category with no entries yet has
        none, so this is a warning, not an error: but an index that exists in Drive and wasn't
        fetched makes its entries, and the editions' updated-by relations in it, invisible."""
        base = os.path.join(self.root, "library-data")
        return [self.rel(os.path.join(base, c, "_index.json")) for c in CATEGORIES
                if not os.path.exists(os.path.join(base, c, "_index.json"))]

    # ---------------------------------------------------------------- entries
    def updated(self):
        """Refs of entries that don't exist in this campaign's edition (layout §8 "Editions"): an older
        edition's entry updated by another (updated-by), or, in a campaign of the older edition, the
        entry that updated it."""
        if self._updated is None:
            gone = set()
            for r in self.roots:
                for cat in (os.listdir(r) if os.path.isdir(r) else []):
                    p = os.path.join(r, cat, "_index.json")
                    if not os.path.exists(p):
                        continue
                    for rec in self._json(p):
                        for rel in rec.get("relations", []):
                            if rel.get("role") != "updated-by":
                                continue
                            if rec.get("edition", self.edition) == self.edition:
                                gone.add(rel["to"])
                            else:
                                gone.add(f'{cat}/{rec["slug"]}')
            self._updated = gone
        return self._updated

    def replaced(self):
        """{ref: the ref that replaces it}: entries another entry *replaces* (layout §4), when the
        replacement is itself used here (its source in play, and not for the GM unless gm)."""
        if self._replaced is None:
            out = {}
            for r in self.roots:
                for cat in (os.listdir(r) if os.path.isdir(r) else []):
                    p = os.path.join(r, cat, "_index.json")
                    if not os.path.exists(p):
                        continue
                    for rec in self._json(p):
                        if (self.sources and rec.get("source") not in self.sources) or \
                                (rec.get("audience") == "gm" and not self.gm):
                            continue
                        for rel in rec.get("relations", []):
                            if rel.get("role") == "replaces":
                                out[rel["to"]] = f'{cat}/{rec["slug"]}'
            self._replaced = out
        return self._replaced

    def added_by(self, ref):
        """The refs of the entries used here that *add to* this one (layout §4): a supplement's extra
        rules for a talent, a new specialisation of a skill. An answer about the entry needs them too."""
        if self._added is None:
            out = {}
            for cat in CATEGORIES:
                for _, rec in self.index(cat):
                    for rel in rec.get("relations", []):
                        if rel.get("role") == "adds-to":
                            out.setdefault(rel["to"], []).append(f'{cat}/{rec["slug"]}')
            self._added = out
        return self._added.get(ref, [])

    def current(self, ref):
        """The ref to use for `ref`: itself, or the entry that replaces it here (followed to the end)."""
        seen = set()
        while ref in self.replaced() and ref not in seen:
            seen.add(ref)
            ref = self.replaced()[ref]
        return ref

    def index(self, category):
        """[(root, record)] for the category, sources in play only."""
        if category not in self._index:
            self._index[category] = [(r, rec) for r, rec in self.records(category)
                                     if not self.hidden(category, rec)]
        return self._index[category]

    def records(self, category):
        """[(root, record)] for the category, unfiltered: every record in every index here."""
        if category not in self._records:
            out = []
            for r in self.roots:
                p = os.path.join(r, category, "_index.json")
                if os.path.exists(p):
                    out += [(r, rec) for rec in self._json(p)]
            self._records[category] = out
        return self._records[category]

    def hidden(self, category, rec):
        """Why a record isn't used here (layout §8), or None when it is: its source isn't in play, it's
        for the GM, another entry in play replaces it, or the campaign's edition updated it."""
        if self.sources and rec.get("source") not in self.sources:
            return f'{rec.get("source")} isn\'t one of the sources in play'
        if rec.get("audience") == "gm" and not self.gm:
            return "for the GM only"
        by = self.replaced().get(f'{category}/{rec["slug"]}')
        if by:
            return f"{by} replaces it"
        if f'{category}/{rec["slug"]}' in self.updated():
            by = [x["to"] for x in rec.get("relations", []) if x.get("role") == "updated-by"]
            return f"the {self.edition} rules updated it" + (f' ({", ".join(by)})' if by else "")
        return None

    def entry(self, ref):
        key = ref.split("#", 1)[0]
        if key in self._entries:
            return self._entries[key]
        category, slug = key.split("/", 1)
        for r, rec in self.index(category):
            if rec["slug"] == slug:
                e = self._json(os.path.join(r, category, slug + ".json"))
                if e is None:       # lenient: stand in for the entry until it's fetched
                    e = {"slug": slug, "name": rec.get("name", slug), "source": rec.get("source"),
                         "fields": {}, "content": [], "_missing": True}
                e["content"] = nest(e.get("content", []))
                self._entries[key] = e
                return e
        raise RefError(f"{key}: not in the library (or not in this campaign's sources)")

    def find(self, category, name):
        """The ref of the entry in `category` called `name` (or with it as an alias), if exactly one."""
        n = norm(name)
        hits = [rec["slug"] for _, rec in self.index(category)
                if norm(rec["name"]) == n or n in (norm(a) for a in rec.get("aliases", []))]
        hits = sorted(set(hits))
        return f"{category}/{hits[0]}" if len(hits) == 1 else None

    def named(self, category, name):
        """(ref, specialisation) for a name as the books print it: "Melee (Basic)" is the Melee skill
        with the specialisation "Basic"; "Sixth Sense" is itself, with None. An entry whose own name
        has the brackets ("Shield (Buckler)") wins. (None, None) when nothing, or more than one
        entry, has the name."""
        ref = self.find(category, name)
        if ref:
            return ref, None
        m = SPECIALISED.match(name.strip())
        if m:
            ref = self.find(category, m.group(1))
            if ref:
                return ref, m.group(2).strip()
        return None, None

    def entries(self, category, **match):
        """Index records in `category` whose fields equal `match` (e.g. kind="action")."""
        return [rec for _, rec in self.index(category) if all(rec.get(k) == v for k, v in match.items())]

    # ---------------------------------------------------------------- sections
    def section(self, ref):
        """The blocks a ref points at: a whole entry's content, a heading's content, or a trait."""
        entry = self.entry(ref)
        if "#" not in ref:
            return entry.get("content", [])
        path = [p.strip() for p in re.split(r"\s*›\s*|\s*>\s*", ref.split("#", 1)[1]) if p.strip()]
        # each part is the first heading after the one before, in reading order (books don't always
        # nest options under their heading: "Maneuver Options" and "Parry" are both level 5)
        order = [b for b in _walk(entry.get("content", [])) if b.get("type") == "heading"]
        pos, hit = -1, None
        for i, part in enumerate(path):
            found = next((k for k in range(pos + 1, len(order)) if _matches(order[k], part)), None)
            if found is not None:
                pos, hit = found, order[found]
                continue
            if i == len(path) - 1:
                para = _find_lead(hit.get("content", []) if hit else entry.get("content", []), part)
                if para is not None:
                    return para
            raise RefError(f"{ref}: no heading or trait '{part}'")
        return hit.get("content", [])

    def heading_text(self, ref):
        """The heading a ref points at, as written ('Skill Advances')."""
        if "#" not in ref:
            return self.entry(ref)["name"]
        last = re.split(r"\s*›\s*|\s*>\s*", ref.split("#", 1)[1])[-1].strip()
        return last

    # ---------------------------------------------------------------- tables
    def table(self, ref, title):
        """A table (by title) inside a ref's blocks: {"columns": [...], "rows": [[...]]}."""
        for t in _walk(self.section(ref)):
            if t.get("type") == "table" and norm(t.get("title")) == norm(title):
                return t
        raise RefError(f"{ref}: no table '{title}'")

    # ---------------------------------------------------------------- text
    def text(self, blocks):
        return blocks_text(blocks)

    def html(self, blocks):
        return blocks_html(blocks)


def nest(blocks):
    """Entries store headings flat, each followed by its blocks. Put each heading's blocks (and
    deeper headings) in its "content", so a heading is a section."""
    root = {"level": 0, "content": []}
    stack = [root]
    for b in blocks:
        if b.get("type") == "heading" and not b.get("content"):
            lvl = b.get("level") or 6
            while stack[-1]["level"] >= lvl:
                stack.pop()
            h = dict(b, content=[])
            stack[-1]["content"].append(h)
            stack.append(h)
        else:
            stack[-1]["content"].append(b)
    return root["content"]


def _walk(blocks):
    for b in blocks or []:
        yield b
        if isinstance(b.get("content"), list):
            yield from _walk(b["content"])


def _matches(heading, part):
    return norm(heading.get("text")) == norm(part) or bare(heading.get("text")) == bare(part)


def _find_lead(blocks, part):
    """[the paragraph whose bold lead is `part`, with the lead removed, + following plain paragraphs]."""
    n = bare(part)
    flat = list(blocks or [])
    for i, b in enumerate(flat):
        if b.get("type") != "paragraph":
            continue
        m = LEAD.match(b.get("text", ""))
        if m and bare(m.group(1)) == n:
            out = [dict(b, text=b["text"][m.end():])]
            for nxt in flat[i + 1:]:
                if nxt.get("type") == "paragraph" and not LEAD.match(nxt.get("text", "")):
                    out.append(nxt)
                elif nxt.get("type") in ("list", "table"):
                    out.append(nxt)
                else:
                    break
            return out
    for b in flat:  # traits can sit under a heading of their own block list
        if isinstance(b.get("content"), list):
            hit = _find_lead(b["content"], part)
            if hit is not None:
                return hit
    return None


# ---------------------------------------------------------------------------- rendering
def _item_text(i):
    return i if isinstance(i, str) else (i.get("text") or "")


def blocks_text(blocks):
    out = []
    for b in blocks or []:
        t = b.get("type")
        if t == "paragraph":
            out.append(b.get("text", ""))
        elif t == "heading":
            out.append(f'**{b.get("text", "")}**')
            out.append(blocks_text(b.get("content", [])))
        elif t == "list":
            out.append("\n".join(f"- {_item_text(i)}" for i in b.get("items", [])))
        elif t == "fields":
            out.append("\n".join(f'**{i["label"]}:** {i["text"]}' for i in b.get("items", [])))
        elif t == "table":
            cols = b.get("columns", [])
            rows = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
            heads = {g["before"]: g["text"] for g in b.get("groups", [])}
            for n, r in enumerate(b.get("rows", [])):
                if n in heads:
                    rows.append("| " + " | ".join([f"***{heads[n]}***"] + [""] * (len(cols) - 1)) + " |")
                rows.append("| " + " | ".join(str(c) for c in r) + " |")
            out.append((f'*{b["title"]}*\n' if b.get("title") else "") + "\n".join(rows) +
                       "".join(f"\n\n{f}" for f in b.get("footnotes", [])))
        elif t == "sidebar":
            inner = blocks_text(b.get("content", []))
            out.append("\n".join("> " + ln if ln else ">" for ln in
                                 ((f'**{b["title"]}**\n\n' if b.get("title") else "") + inner).split("\n")))
        elif t == "profile":
            ch = b.get("characteristics") or {}
            lines = [f'**{b.get("name", "")}**'] if b.get("name") else []
            if ch:
                lines += ["| " + " | ".join(ch) + " |", "|" + "---|" * len(ch),
                          "| " + " | ".join("—" if v is None else str(v) for v in ch.values()) + " |"]
            lines += [f'**{ln["label"]}:** {ln["text"]}' for ln in b.get("lines", [])]
            out.append("\n".join(lines))
        elif t == "career_levels":
            first = b.get("first_level", 1)
            lines = []
            for n, lv in enumerate(b.get("levels", []), first):
                lines.append(f'**Level {n}: {lv.get("title", "")}**' + (f' ({lv["status"]})' if lv.get("status") else ""))
                for key, label in (("characteristics", "Characteristics"), ("skills", "Skills"),
                                   ("talents", "Talents"), ("trappings", "Trappings")):
                    if lv.get(key):
                        v = lv[key] if isinstance(lv[key], str) else ", ".join(lv[key])
                        lines.append(f"- **{label}:** {v}")
            out.append("\n".join(lines))
        elif isinstance(b.get("content"), list):
            out.append(blocks_text(b["content"]))
    return "\n\n".join(x for x in out if x)


def inline_html(s):
    s = _html.escape(s or "", quote=False)
    s = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<i>\1</i>", s)
    return s


def blocks_html(blocks):
    out = []
    for b in blocks or []:
        t = b.get("type")
        if t == "paragraph":
            out.append(f'<p>{inline_html(b.get("text"))}</p>')
        elif t == "heading":
            out.append(f'<p><b>{inline_html(b.get("text"))}</b></p>' + blocks_html(b.get("content", [])))
        elif t == "list":
            out.append("<ul>" + "".join(f"<li>{inline_html(_item_text(i))}</li>" for i in b.get("items", [])) + "</ul>")
        elif t == "fields":
            out.append("".join(f'<p><b>{inline_html(i["label"])}:</b> {inline_html(i["text"])}</p>'
                               for i in b.get("items", [])))
        elif t == "table":
            head = "".join(f"<th>{inline_html(c)}</th>" for c in b.get("columns", []))
            body = "".join("<tr>" + "".join(f"<td>{inline_html(str(c))}</td>" for c in r) + "</tr>"
                           for r in b.get("rows", []))
            cap = f'<caption>{inline_html(b["title"])}</caption>' if b.get("title") else ""
            out.append(f'<table class="t rt">{cap}<tr>{head}</tr>{body}</table>')
        elif isinstance(b.get("content"), list):
            out.append(blocks_html(b["content"]))
    return "".join(out)
