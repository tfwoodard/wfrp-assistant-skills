#!/usr/bin/env python3
"""Print a character's sheet: an HTML page laid out for Letter paper, and a PDF of it.

    character_pdf.py RECORD --library ROOT --campaign SLUG [--out DIR] [--pdf]
        -> DIR/<slug>.html, DIR/<slug>.md (the markdown sheet, build_character.py --md), and
           DIR/<slug>.pdf with --pdf: everything to upload beside the record, from one build

The sheet is the build (build_character.py) of the record, never the record's own numbers, on three
pages: (1) characteristics with their bonuses, the attributes (Wounds, Movement, Fate and Fortune,
Resilience and Resolve, Corruption, Encumbrance, XP), then two balanced columns that flow on: the
career and a "To do" box (earlier levels still to complete, differences from the rules, what the
record says is to settle, what the build couldn't work out) above the basic skills, then the
advanced skills and the talents, each with a one-line summary; (2) weapons, armour by location, trappings in their
containers, money, spells each with a one-line summary of what it does (the entry's `summary`, as
for each talent on the first page),
ambitions (the character's, then the party's name, members and ambitions), psychology, mutations, and an Elder's
Time of birth, earlier careers and burdens (these follow on from the first page, so no page is left
nearly empty); (3) a page of its own to mark in play: Wounds, Fortune, Resolve and Corruption as
boxes, Advantage (a tally at +10 each, or one box where a house rule sets `"advantage": "on-off"`),
and every condition in play with boxes to count it. Nothing is printed on a filled background, to
save ink: a box already marked (a Wound taken, Fortune spent) shows a cross. Accepted differences, house rules and
what rules add are on the markdown sheet (build_character.py --md), not the printed one.

The PDF is printed with Playwright when it is installed, otherwise with a local Chrome, Edge or
Chromium in headless mode. Without one, open the HTML in a browser and print it (Letter,
background graphics on). Nothing in the record is changed.
"""
import argparse, html, json, os, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_character as bc  # noqa: E402
from library import Library, cli  # noqa: E402

CSS = r"""
@page{size:Letter;margin:11mm 12mm}
*{box-sizing:border-box}
:root{--fg:#1d1b18;--muted:#6b645a;--line:#c9c0b2;--accent:#7a1f1f;--soft:#f4efe6}
body{font-family:Georgia,'Times New Roman',serif;color:var(--fg);font-size:10.5px;margin:0;line-height:1.3}
.page{max-width:780px;margin:0 auto}
.page.new{break-before:page}
h1{font-size:26px;margin:0;letter-spacing:.02em}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--accent);margin:10px 0 4px;
   border-bottom:1.5px solid var(--accent);padding-bottom:1px;break-after:avoid}
.head{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2.5px solid var(--accent);padding-bottom:5px;gap:14px}
.head .what{font-size:12px;margin-top:2px}
.head .who{text-align:right;color:var(--muted);font-size:10.5px;line-height:1.5}
.head .who b{color:var(--fg);font-weight:normal}
.chars{display:grid;grid-template-columns:repeat(10,1fr);gap:4px;margin:8px 0 6px}
.ch{border:1.5px solid var(--fg);border-radius:6px;text-align:center;padding:3px 2px 4px}
.ch .lab{font-size:9px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.ch .cur{font-size:20px;line-height:1.1;font-variant-numeric:tabular-nums}
.ch .bon{display:inline-block;border:1px solid var(--line);border-radius:8px;padding:0 6px;font-size:10px}
.ch .how{font-size:8.5px;color:var(--muted);margin-top:2px}
.attrs{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;margin-bottom:4px}
.at{border:1px solid var(--line);text-align:center;padding:3px 2px}
.at b{display:block;font-size:14px;font-weight:normal;font-variant-numeric:tabular-nums}
.at span{font-size:8.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.at i{display:block;font-size:8.5px;color:var(--muted);font-style:normal}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}
table{border-collapse:collapse;width:100%}
th{text-align:left;font-size:8.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:normal;
   border-bottom:1px solid var(--line);padding:1px 3px}
td{padding:1px 3px;border-bottom:1px solid #ece6da;vertical-align:top}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tr{break-inside:avoid}
.car{font-size:9px;color:var(--accent)}
.cite{color:var(--muted);font-size:8.5px}
.box{border:1px solid var(--line);padding:4px 6px;margin:4px 0;break-inside:avoid}
.box.warn{border-color:var(--accent)}
.small{font-size:9.5px}
ul{margin:2px 0 2px 16px;padding:0} li{margin:1px 0}
.armour{display:grid;grid-template-columns:repeat(6,1fr);gap:4px}
.armour div{border:1px solid var(--line);text-align:center;padding:2px}
.armour b{display:block;font-size:14px;font-weight:normal}
.armour span{font-size:8.5px;color:var(--muted);text-transform:uppercase}
.track{display:inline-block;width:11px;height:11px;border:1px solid var(--fg);border-radius:2px;margin-right:2px;vertical-align:middle}
.track.on{text-align:center;font-size:9px;line-height:10px;vertical-align:middle}
.trk .track.on{font-size:12px;line-height:15px} .cond .track.on{font-size:10px;line-height:12px}
.todo{border:1.5px solid var(--accent);padding:4px 8px;margin:6px 0;break-inside:avoid;font-size:9.5px}
.todo b.t{display:block;color:var(--accent);text-transform:uppercase;letter-spacing:.06em;font-size:10px;margin-bottom:2px}
.todo ul{margin:1px 0 3px 16px}
.spell{border-bottom:1px solid #ece6da;padding:3px 0;break-inside:avoid}
.flow{column-count:2;column-gap:16px}
.keep{break-inside:avoid}
.flow h2:first-child,.flow .box:first-child{margin-top:0}
.flow table{break-inside:auto}
.spell .nm{font-size:11px;font-weight:bold}
.spell .st{color:var(--muted);font-size:9px;margin-left:6px}
.spell .sum{margin:1px 0 0 10px}
.play h2{margin-top:12px}
.trk{display:flex;flex-wrap:wrap;gap:3px;align-items:center;margin:3px 0}
.trk .track{width:16px;height:16px;margin:0}
.trk .lab{width:120px;font-size:11px}
.cond{border-bottom:1px solid #ece6da;padding:3px 0;break-inside:avoid}
.note{padding:2px 0;break-inside:avoid;font-size:9pt}
.cond .ch2{display:flex;align-items:center;gap:4px}
.cond .cn{width:90px;font-weight:bold} .cond .track{width:13px;height:13px}
.cond .sum{font-size:9.5px;margin:1px 0 0 0}
"""


def short(cite):
    """"(CRB, ch. 4 › Master Talent List, p. 132)" -> "(CRB p. 132)": the source and page are enough on paper."""
    m = re.match(r"\((\w+),.*?(p\. [\d–-]+)\)\s*$", cite or "")
    return f"({m.group(1)} {m.group(2)})" if m else (cite or "")


def e(x):
    return html.escape("" if x is None else str(x))


def table(cols, rows, num=()):
    head = "".join(f'<th class="{"n" if i in num else ""}">{e(c)}</th>' for i, c in enumerate(cols))
    body = "".join("<tr>" + "".join(f'<td class="{"n" if i in num else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def boxes(n, filled=0):
    return "".join('<span class="track on">✕</span>' if i < filled else '<span class="track"></span>' for i in range(max(0, int(n or 0))))


def todo(m):
    """Everything still to do on the character, in one box: earlier career levels to complete,
    differences from the rules, what the record says is still to settle, and what the build couldn't
    work out. Empty when there is nothing."""
    parts = []
    gaps = (m.get("career") or {}).get("to_complete") or []
    owed = m.get("to_complete") or []
    if gaps or owed:
        parts.append("<b>Still to complete</b><ul>" + "".join(
            f"<li>{e(g['career'])} {e(g['level'])} ({e(g['level_name'])}): {e('; '.join(g['missing']))}</li>" for g in gaps) + "".join(
            f"<li>{e(o['what'] or o['text'])}</li>" for o in owed) + "</ul>")
    if m["differences"]:
        parts.append("<b>Differs from the rules</b><ul>" + "".join(
            f"<li>{e(d['text'])} <span class='cite'>{e(d['id'])}</span></li>" for d in m["differences"]) + "</ul>")
    if m.get("incomplete"):
        parts.append("<b>To settle</b><ul>" + "".join(f"<li>{e(x if isinstance(x, str) else x.get('what'))}</li>" for x in m["incomplete"]) + "</ul>")
    if m["notes"]:
        parts.append("<b>Not worked out</b><ul>" + "".join(f"<li>{e(n)}</li>" for n in m["notes"]) + "</ul>")
    return f'<div class="todo"><b class="t">To do</b>{"".join(parts)}</div>' if parts else ""


def page_one(m):
    c, sp, d = m.get("career") or {}, m["species"], m.get("details") or {}
    who = []
    if m.get("player"): who.append(f"Player <b>{e(m['player'])}</b>")
    who.append(" · ".join(f"{k.title()} <b>{e(v)}</b>" for k, v in d.items() if v not in (None, "")))
    out = [f'<div class="head"><div><h1>{e(m.get("name") or m.get("slug"))}</h1>'
           f'<div class="what">{e(sp.get("name"))}{" (" + e(sp["origin"]) + ")" if sp.get("origin") else ""} · {e(c.get("class"))} · '
           f'{e(c.get("name"))} {e(c.get("level"))}: <b>{e(c.get("level_name"))}</b> · Status {e(c.get("status"))}</div></div>'
           f'<div class="who">{"<br>".join(w for w in who if w)}</div></div>']
    out.append('<div class="chars">' + "".join(
        f'<div class="ch"><div class="lab">{e(bc.CHAR_NAME[k])}</div><div class="cur">{v["current"]}</div>'
        f'<div class="bon">{v["bonus"]}</div><div class="how">{v["initial"]} + {v["advances"]}</div></div>'
        for k, v in ((k, m["characteristics"][k]) for k in bc.CHARS)) + "</div>")
    w, mv, f, r, co, en, x = m["wounds"], m["movement"], m["fate"], m["resilience"], m["corruption"], m["encumbrance"], m["xp"]
    st = m.get("state") or {}
    attrs = [("Wounds", f'{w["max"] - w["taken"]} / {w["max"]}', w["formula"]),
             ("Movement", mv["base"], f'Walk {mv["walk"]} · Run {mv["run"]}'),
             ("Fate · Fortune", f'{f["fate"]} · {f["fortune"] - st.get("fortune_spent", 0)}', ""),
             ("Resilience · Resolve", f'{r["resilience"]} · {r["resolve"] - st.get("resolve_spent", 0)}', r.get("motivation") or ""),
             ("Corruption", f'{co["points"]} / {co["threshold"]}', ""),
             ("Encumbrance", f'{en["carried"]} / {en["max"]}', ""),
             ("XP", x["current"], f'{x["spent"]} spent of {x["total"]}')]
    out.append('<div class="attrs">' + "".join(f'<div class="at"><span>{e(a)}</span><b>{e(b)}</b><i>{e(i)}</i></div>' for a, b, i in attrs) + "</div>")
    callouts = todo(m)
    def skills(rows):
        return table(["Skill", "", "Char", "Adv", "Total"],
                     [[e(s["name"]), '<span class="car">career</span>' if s["career"] else "", e(s["characteristic"]),
                       e(s["advances"]), f"<b>{e(s['total'])}</b>"] for s in rows], num=(3, 4))
    flow = f'{callouts}<h2>Basic skills</h2>{skills(m["skills"]["basic"])}<h2>Advanced skills</h2>{skills(m["skills"]["advanced"])}'
    seen, rows = set(), []
    for t in m["talents"]:
        first = (t["ref"], t.get("summary")) not in seen          # the same words twice print once
        seen.add((t["ref"], t.get("summary")))
        summary = (e(t["summary"]) if t.get("summary") else "<i>No summary yet: read the entry.</i>") if first else "<i>As above.</i>"
        rows.append(f'<div class="spell"><span class="nm">{e(t["name"])}</span><span class="st">'
                    f'{e(t["times"])}{" of " + e(t["max"]) if t.get("max") is not None else ""}'
                    f'{" · Tests: " + e(t["tests"]) if t.get("tests") else ""} · {e(short(t["cite"]))}</span>'
                    f'<div class="sum">{summary}</div></div>')
    out.append(f'<div class="flow">{flow}<h2>Talents</h2>' + "".join(rows) + "</div>")
    return '<div class="page">' + "".join(out) + "</div>"


def page_two(m):
    out = []
    weapons = [t for t in m["trappings"] if t.get("weapon")]
    if weapons:
        out.append('<div class="keep"><h2>Weapons</h2>' + table(["Weapon", "Group", "Reach / range", "Damage", "Qualities and flaws"], [
            [e(t["name"]), e(t["weapon"].get("group")), e(t["weapon"].get("reach") or t["weapon"].get("range")),
             f"<b>{e(t['weapon'].get('damage'))}</b> <span class='cite'>{e(t['weapon'].get('damage_text'))}</span>",
             e(", ".join(t["weapon"].get("qualities") or []))] for t in weapons]) + "</div>")
    out.append('<div class="keep"><h2>Armour</h2><div class="armour">' + "".join(
        f"<div><span>{e(k)}</span><b>{e(v)}</b></div>" for k, v in m["armour"].items()) + "</div></div>")
    if m["trappings"]:
        rows = []
        for t in m["trappings"]:
            notes = [k for k in ("worn", "stowed") if t.get(k)] + ([t["notes"]] if t.get("notes") else [])
            if t.get("armour"): notes.insert(0, f"AP {t['armour']['ap']}: {', '.join(t['armour']['locations'])}")
            rows.append([("&nbsp;&nbsp;&nbsp;" * t["depth"]) + ("└ " if t["depth"] else "") + e(t["name"]), e(t["qty"]), e(t["enc"]),
                         e(t["counts"]), e("; ".join(notes))])
        out.append("<h2>Trappings</h2>" + table(["Trapping", "Qty", "Enc", "Counts", ""], rows, num=(1, 2, 3)))
    money = m.get("money") or {}
    out.append(f'<div class="box small"><b>Money</b>: {e(money.get("gc", 0))} gc · {e(money.get("ss", 0))} ss · {e(money.get("d", 0))} d</div>')
    side = []
    mine = [(k.title(), v) for k, v in (m.get("ambitions") or {}).items() if v]
    party = list(bc.party_lines(m.get("party") or {}).items())
    if mine or party:                       # the character's own, then the party's, in one section
        side.append("<h2>Ambitions</h2><ul>" + "".join(f"<li>{e(k)}: {e(v)}</li>" for k, v in mine) + "</ul>"
                    + ('<div class="small"><b>Party</b></div><ul>' + "".join(f"<li>{e(k)}: {e(v)}</li>" for k, v in party)
                       + "</ul>" if party else ""))
    for title, key in (("Psychology", "psychology"), ("Mutations", "mutations")):
        if m.get(key):
            side.append(f"<h2>{title}</h2><ul>" + "".join(
                f"<li>{e(x)}</li>" if isinstance(x, str) else
                f"<li>{e(x['name'])}" + (f": {e('; '.join(x['cells']))}" if x.get("cells") else "") +
                (f" <span class='cite'>{e(x.get('cite'))}</span>" if x.get("cite") else "") + "</li>" for x in m[key]) + "</ul>")
    if m.get("elder"):                       # where they were born, the careers before this one, what it costs them
        side.append("<h2>Elder</h2><ul>" + "".join(f"<li>{e(x[2:])}</li>" for x in bc.elder_lines(m["elder"])) + "</ul>")
    st = m.get("state") or {}
    for title, key in (("Conditions", "conditions"), ("Critical wounds", "critical_wounds"), ("Insanities", "insanities")):
        if st.get(key):
            side.append(f"<h2>{title}</h2><ul>" + "".join(f"<li>{e(x if isinstance(x, str) else x.get('name') or json.dumps(x))}</li>"
                                                       for x in st[key]) + "</ul>")
    if side:
        out.append(f'<div class="cols"><div>{"".join(side[:len(side) // 2 + len(side) % 2])}</div><div>{"".join(side[len(side) // 2 + len(side) % 2:])}</div></div>')
    if m["spells"]:
        out.append("<h2>Spells</h2>" + "".join(
            f'<div class="spell"><span class="nm">{e(s["name"])}</span><span class="st">{e(s["lore"] or s["kind"])} · CN {e(s["cn"])} · '
            f'Range {e(s["range"])} · Target {e(s["target"])} · Duration {e(s["duration"])} · {e(short(s["cite"]))}</span>'
            f'<div class="sum">{e(s["summary"]) if s.get("summary") else "<i>No summary yet: read the entry.</i>"}</div></div>'
            for s in m["spells"]))
    return '<div class="page">' + "".join(out) + "</div>"


def page_play(m, conditions=()):
    """A page to mark during a session: Wounds, Fortune and Resolve as boxes (those already taken or
    spent filled in), and each condition in play with boxes to count it."""
    w, f, r, st = m["wounds"], m["fate"], m["resilience"], m.get("state") or {}
    out = [f'<div class="head"><div><h1>{e(m.get("name") or m.get("slug"))}</h1><div class="what">In play</div></div></div>']
    def row(label, n, filled, note=""):
        return f'<div class="trk"><span class="lab">{e(label)} <span class="cite">{e(note)}</span></span>{boxes(n, filled)}</div>'
    out.append("<h2>Wounds</h2>" + row(f"Wounds ({w['max']})", w["max"], w["taken"]))
    co = m["corruption"]
    out.append('<div class="cols"><div><h2>Fortune and Resolve</h2>' +
               row(f"Fortune ({f['fortune']})", f["fortune"], st.get("fortune_spent", 0)) +
               row(f"Resolve ({r['resolve']})", r["resolve"], st.get("resolve_spent", 0)) +
               '</div><div><h2>Corruption</h2>' +
               row(f"Corruption ({co['threshold']})", max(co["threshold"], co["points"]), co["points"]) + '</div></div>')
    adv = m.get("advantage") or {"style": "count"}
    if adv["style"] == "on-off":
        out.append("<h2>Advantage</h2>" + f'<div class="trk"><span class="lab">Advantage</span>{boxes(1)}'
                   f'<span class="cite">&nbsp;{e(adv.get("house_rule") or "had or not")}</span></div>')
    else:
        out.append("<h2>Advantage</h2>" + f'<div class="trk"><span class="lab">Advantage <span class="cite">+10 each</span></span>{boxes(10)}'
                   f'<span class="cite">&nbsp;{e(adv.get("cite") or "")}</span></div>')
    if m.get("remember"):                   # the campaign notebook's current notes: the party's, then this character's
        out.append("<h2>Remember</h2><div class='flow'>" + "".join(
            f'<div class="note"><b>{e(n["name"])}</b> <span class="cite">{e(n["kind"])}</span> {e(n["text"])}</div>'
            for n in sorted(m["remember"], key=lambda n: bool(n.get("for")))) + "</div>")
    have = {}
    for x in st.get("conditions") or []:
        n = x if isinstance(x, str) else x.get("name")
        have[bc.norm(n)] = 1 if isinstance(x, str) else int(x.get("count", 1))
    if conditions:
        def bonuses(text):          # "Toughness Bonus Rounds" -> "3 Rounds", in this character's numbers
            return re.sub(r"\b(%s) Bonus\b" % "|".join(bc.CHAR_NAME.values()),
                          lambda x: str(m["characteristics"][bc.NAME_CHAR[bc.norm(x.group(1))]]["bonus"]), text or "")
        out.append("<h2>Conditions</h2><div class='flow'>" + "".join(
            f'<div class="cond"><div class="ch2"><span class="cn">{e(c["name"])}</span>{boxes(6, have.get(bc.norm(c["name"]), 0))}'
            f'<span class="cite">{e(short(c.get("cite", "")))}</span></div>'
            + (f'<div class="sum">{e(bonuses(c["summary"]))}</div>' if c.get("summary") else "") + "</div>" for c in conditions) + "</div>")
    elif st.get("conditions"):
        out.append("<h2>Conditions</h2><ul>" + "".join(f"<li>{e(k)}: {v}</li>" for k, v in have.items()) + "</ul>")
    return '<div class="page new play">' + "".join(out) + "</div>"


def conditions_in_play(lib):
    """The conditions in play, from the library's rules: [{name, ref, cite}]."""
    out = []
    for _, r in lib.index("rules"):
        if r.get("kind") == "condition":
            ref = f"rules/{r['slug']}"
            try:
                ce = lib.entry(ref)
                out.append({"name": r["name"], "ref": ref, "cite": bc.cite(ce, bc.chapter_titles(lib)),
                            "summary": ce.get("fields", {}).get("summary")})
            except Exception: out.append({"name": r["name"], "ref": ref})
    return sorted(out, key=lambda c: c["name"])


def document(m, conditions=()):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(m.get("name"))}</title>'
            f"<style>{CSS}</style></head><body>{page_one(m)}{page_two(m)}{page_play(m, conditions)}</body></html>")


def find_browser():
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "msedge", "chrome"):
        p = shutil.which(name)
        if p: return p
    for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if os.path.exists(p): return p
    return None


def to_pdf(html_path, pdf_path):
    url = "file:///" + os.path.abspath(html_path).replace(os.sep, "/").lstrip("/")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page()
            pg.goto(url)
            pg.pdf(path=pdf_path, format="Letter", print_background=True, prefer_css_page_size=True)
            b.close()
        return
    except Exception:
        pass
    browser = find_browser()
    if browser:
        with tempfile.TemporaryDirectory() as prof:
            try:
                r = subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer", "--no-first-run",
                                    f"--user-data-dir={prof}", f"--print-to-pdf={os.path.abspath(pdf_path)}", url],
                                   capture_output=True, timeout=90)
                if r.returncode == 0 and os.path.exists(pdf_path): return
            except subprocess.TimeoutExpired:
                pass
    sys.exit("Couldn't print a PDF (no Playwright, Chrome, Edge or Chromium that works here). Open the HTML in a browser "
             "and print it: Letter, background graphics on.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("record")
    ap.add_argument("--library", required=True)
    ap.add_argument("--campaign")
    ap.add_argument("--out", default=".")
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args()
    with open(a.record, encoding="utf-8") as f:
        record = json.load(f)
    lib = Library(a.library, a.campaign)
    m = bc.build(record, lib)
    os.makedirs(a.out, exist_ok=True)
    base = os.path.join(a.out, m.get("slug") or bc.slug(m.get("name") or "character"))
    with open(base + ".html", "w", encoding="utf-8") as f:
        f.write(document(m, conditions_in_play(lib)))
    print("wrote", base + ".html")
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write(bc.markdown(m))
    print("wrote", base + ".md")
    if a.pdf:
        to_pdf(base + ".html", base + ".pdf")
        print("wrote", base + ".pdf")
    import summaries_owed
    n = len(summaries_owed.owed(m, lib))
    if n:
        print(f"{n} {'summary' if n == 1 else 'summaries'} still to write for the sheet: summaries_owed.py lists them "
              "with each entry's text")


if __name__ == "__main__":
    cli(main)
