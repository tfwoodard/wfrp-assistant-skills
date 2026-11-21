#!/usr/bin/env python3
"""Print a character's sheet: an HTML page laid out for Letter paper, and a PDF of it.

    character_pdf.py RECORD --library ROOT --campaign SLUG [--out DIR] [--pdf]
        -> DIR/<slug>.html (and DIR/<slug>.pdf with --pdf)

The sheet is the build (build_character.py) of the record, never the record's own numbers:
characteristics with their bonuses, the attributes (Wounds, Movement, Fate and Fortune, Resilience
and Resolve, Corruption, Encumbrance, XP), the career and what its earlier levels still need, the
skills and talents, then weapons, armour by location, trappings (in their containers), money,
spells, ambitions, psychology and mutations, and the notes: differences from the rules, accepted
ones and why, what the build couldn't work out, and the house rules it used. Nothing the build
reports is left off the printed sheet.

The PDF is printed with Playwright when it is installed, otherwise with a local Chrome, Edge or
Chromium in headless mode. Without one, open the HTML in a browser and print it (Letter,
background graphics on). Nothing in the record is changed.
"""
import argparse, html, json, os, shutil, subprocess, sys, tempfile

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
.at{border:1px solid var(--line);background:var(--soft);text-align:center;padding:3px 2px}
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
.box.warn{border-color:var(--accent);background:#fbf3f1}
.small{font-size:9.5px}
ul{margin:2px 0 2px 16px;padding:0} li{margin:1px 0}
.armour{display:grid;grid-template-columns:repeat(6,1fr);gap:4px}
.armour div{border:1px solid var(--line);text-align:center;padding:2px}
.armour b{display:block;font-size:14px;font-weight:normal}
.armour span{font-size:8.5px;color:var(--muted);text-transform:uppercase}
.track{display:inline-block;width:11px;height:11px;border:1px solid var(--fg);border-radius:2px;margin-right:2px;vertical-align:middle}
.track.on{background:var(--fg)}
"""


def e(x):
    return html.escape("" if x is None else str(x))


def table(cols, rows, num=()):
    head = "".join(f'<th class="{"n" if i in num else ""}">{e(c)}</th>' for i, c in enumerate(cols))
    body = "".join("<tr>" + "".join(f'<td class="{"n" if i in num else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def boxes(n, filled=0):
    return "".join(f'<span class="track{" on" if i < filled else ""}"></span>' for i in range(max(0, int(n or 0))))


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
             ("Fate · Fortune", f'{f["fate"]} · {f["fortune"] - st.get("fortune_spent", 0)}', f"Fortune {f['fortune']} a session"),
             ("Resilience · Resolve", f'{r["resilience"]} · {r["resolve"] - st.get("resolve_spent", 0)}', r.get("motivation") or ""),
             ("Corruption", f'{co["points"]} / {co["threshold"]}', ""),
             ("Encumbrance", f'{en["carried"]} / {en["max"]}', ""),
             ("XP", x["current"], f'{x["spent"]} spent of {x["total"]}')]
    out.append('<div class="attrs">' + "".join(f'<div class="at"><span>{e(a)}</span><b>{e(b)}</b><i>{e(i)}</i></div>' for a, b, i in attrs) + "</div>")
    gaps = c.get("to_complete") or []
    path = c.get("path") or []
    if path or gaps:
        lines = [f"{e(p['class'])}: {e(p['name'])} ({e(', '.join(p['levels']))})" for p in path]
        lines += [f"<b>Still to complete</b> in {e(g['career'])} {e(g['level'])} ({e(g['level_name'])}): {e('; '.join(g['missing']))}" for g in gaps]
        out.append(f'<div class="box{" warn" if gaps else ""} small">' + "<br>".join(lines) + "</div>")
    if m["differences"]:
        out.append('<div class="box warn small"><b>Differs from the rules</b><ul>' +
                   "".join(f"<li>{e(d['text'])} <span class='cite'>{e(d['id'])}</span></li>" for d in m["differences"]) + "</ul></div>")
    def skills(rows):
        return table(["Skill", "", "Char", "Adv", "Total"],
                     [[e(s["name"]), '<span class="car">career</span>' if s["career"] else "", e(s["characteristic"]),
                       e(s["advances"]), f"<b>{e(s['total'])}</b>"] for s in rows], num=(3, 4))
    out.append(f'<div class="cols"><div><h2>Basic skills</h2>{skills(m["skills"]["basic"])}</div>'
               f'<div><h2>Advanced skills</h2>{skills(m["skills"]["advanced"])}'
               f'<h2>Talents</h2>' + table(["Talent", "Taken", "Tests"],
                    [[e(t["name"]) + f' <span class="cite">{e(t["cite"])}</span>',
                      e(t["times"]) + (f" of {e(t['max'])}" if t.get("max") is not None else ""), e(t.get("tests") or "")]
                     for t in m["talents"]]) + "</div></div>")
    return '<div class="page">' + "".join(out) + "</div>"


def page_two(m):
    out = []
    weapons = [t for t in m["trappings"] if t.get("weapon")]
    if weapons:
        out.append("<h2>Weapons</h2>" + table(["Weapon", "Group", "Reach / range", "Damage", "Qualities and flaws"], [
            [e(t["name"]), e(t["weapon"].get("group")), e(t["weapon"].get("reach") or t["weapon"].get("range")),
             f"<b>{e(t['weapon'].get('damage'))}</b> <span class='cite'>{e(t['weapon'].get('damage_text'))}</span>",
             e(", ".join(t["weapon"].get("qualities") or []))] for t in weapons]))
    out.append('<h2>Armour</h2><div class="armour">' + "".join(
        f"<div><span>{e(k)}</span><b>{e(v)}</b></div>" for k, v in m["armour"].items()) + "</div>")
    if m["trappings"]:
        rows = []
        for t in m["trappings"]:
            notes = [k for k in ("worn", "stowed") if t.get(k)] + ([t["notes"]] if t.get("notes") else [])
            if t.get("armour"): notes.insert(0, f"AP {t['armour']['ap']}: {', '.join(t['armour']['locations'])}")
            rows.append([("&nbsp;&nbsp;&nbsp;" * t["depth"]) + ("└ " if t["depth"] else "") + e(t["name"]), e(t["qty"]), e(t["enc"]),
                         e(t["counts"]), e("; ".join(notes))])
        out.append("<h2>Trappings</h2>" + table(["Trapping", "Qty", "Enc", "Counts", ""], rows, num=(1, 2, 3)))
    money = m.get("money") or {}
    out.append(f'<div class="box small"><b>Money</b>: {e(money.get("gc", 0))} gc · {e(money.get("ss", 0))} ss · {e(money.get("d", 0))} d'
               f' &nbsp; <b>Encumbrance</b>: {e(m["encumbrance"]["carried"])} of {e(m["encumbrance"]["max"])}</div>')
    if m["spells"]:
        out.append("<h2>Spells</h2>" + table(["Spell", "Lore", "CN", "Range", "Target", "Duration"], [
            [e(s["name"]) + f' <span class="cite">{e(s["cite"])}</span>', e(s["lore"] or s["kind"]), e(s["cn"]), e(s["range"]),
             e(s["target"]), e(s["duration"])] for s in m["spells"]], num=(2,)))
    side = []
    if m.get("ambitions"):
        side.append("<h2>Ambitions</h2><ul>" + "".join(f"<li>{e(k.title())}: {e(v)}</li>" for k, v in m["ambitions"].items() if v) + "</ul>")
    for title, key in (("Psychology", "psychology"), ("Mutations", "mutations")):
        if m.get(key):
            side.append(f"<h2>{title}</h2><ul>" + "".join(
                f"<li>{e(x)}</li>" if isinstance(x, str) else
                f"<li>{e(x['name'])}" + (f": {e('; '.join(x['cells']))}" if x.get("cells") else "") +
                (f" <span class='cite'>{e(x.get('cite'))}</span>" if x.get("cite") else "") + "</li>" for x in m[key]) + "</ul>")
    st = m.get("state") or {}
    for title, key in (("Conditions", "conditions"), ("Critical wounds", "critical_wounds"), ("Insanities", "insanities")):
        if st.get(key):
            side.append(f"<h2>{title}</h2><ul>" + "".join(f"<li>{e(x if isinstance(x, str) else x.get('name') or json.dumps(x))}</li>"
                                                       for x in st[key]) + "</ul>")
    notes = []
    if m.get("incomplete"):
        notes.append("<b>To settle</b><ul>" + "".join(f"<li>{e(x if isinstance(x, str) else x.get('what'))}</li>" for x in m["incomplete"]) + "</ul>")
    if m["accepted"]:
        notes.append("<b>Accepted differences</b><ul>" + "".join(f"<li>{e(d['text'])} <i>({e(d['why'])})</i></li>" for d in m["accepted"]) + "</ul>")
    if m.get("house_rules"):
        notes.append("<b>House rules used</b><ul>" + "".join(f"<li>{e(h.get('text') or h.get('house_rule'))}</li>"
                                                         for h in m["house_rules"].values()) + "</ul>")
    if m.get("effects"):
        notes.append("<b>What rules add</b> (in the numbers above)<ul>" + "".join(
            f"<li>{e(bc.CHAR_NAME.get(x['on'], x['on'].replace('_', ' ').capitalize()))} " +
            (f"× {e(x['multiply'])}" if "multiply" in x else f"{'+' if x['add'] >= 0 else ''}{e(x['add'])}") +
            f" <span class='cite'>{e(x['from'])}</span></li>" for x in m["effects"]) + "</ul>")
    if m["notes"]:
        notes.append("<b>Not worked out</b><ul>" + "".join(f"<li>{e(n)}</li>" for n in m["notes"]) + "</ul>")
    out.append(f'<div class="cols"><div>{"".join(side)}</div><div><h2>Notes</h2><div class="small">{"".join(notes) or "None."}</div></div></div>')
    return '<div class="page new">' + "".join(out) + "</div>"


def document(m):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(m.get("name"))}</title>'
            f"<style>{CSS}</style></head><body>{page_one(m)}{page_two(m)}</body></html>")


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
    m = bc.build(record, Library(a.library, a.campaign))
    os.makedirs(a.out, exist_ok=True)
    base = os.path.join(a.out, m.get("slug") or bc.slug(m.get("name") or "character"))
    with open(base + ".html", "w", encoding="utf-8") as f:
        f.write(document(m))
    print("wrote", base + ".html")
    if a.pdf:
        to_pdf(base + ".html", base + ".pdf")
        print("wrote", base + ".pdf")


if __name__ == "__main__":
    cli(main)
