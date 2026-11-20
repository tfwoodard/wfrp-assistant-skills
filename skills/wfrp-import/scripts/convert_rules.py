#!/usr/bin/env python3
"""Convert chapters of rules prose into rules entries, with their sidebars and tables.

    pdf_layout.py BOOK.pdf --pages 148-191 --boxes --out LAYOUT.json
    convert_rules.py LAYOUT.json --plan PLAN.json --out OUT_DIR [--taken rules=<rules/_index.json> ...]

PLAN.json (kept in Drive beside the source, never in the repo):

    {
      "source": "CRB", "chapter": "ch5",
      "entries": [
        {"name": "Tests", "page": 149, "kind": "procedure"},
        {"name": "Ablaze", "page": 169, "kind": "condition", "aliases": ["Ablaze Condition"]},
        {"name": "Fear", "heading": "Fear (Rating)", "page": 190, "kind": "psychology"},
        {"name": "Blood Rot", "page": 186, "category": "diseases",
         "field_labels": ["Contraction", "Incubation", "Duration", "Symptoms"]}
      ],
      "boxes": {
        "150.3": {"diagram": "Resolving Actions flowchart"},
        "151.1": {"entry": {"name": "Options: Fast SL", "kind": "procedure"}},
        "153.4": {"to": "Tests"}
      },
      "tables": {
        "152.2": {"slug": "outcomes", "title": "Outcomes Table", "about": "What each SL range means", "roll_column": null},
        "47.1": {"title": "Advance Costs", "banner": true, "header_row": true},
        "174.1": {"slug": "head-critical-wounds", "title": "Head Critical Wounds", "roll_column": 0,
                  "continued_in": ["175.1"]}
      },
      "text_tables": [{"page": 160, "header": "Wicks Owned Oil Cost", "columns": ["Wicks Owned", "Oil Cost"],
                       "rows": 4, "title": "Oil Costs"}],
      "relations": {"tests": [{"role": "adds-to", "to": "rules/tests"}],
                    "tables/oil-costs": [{"role": "adds-to", "to": "rules/oil-costs"}]}
    }

"relations" is keyed by slug, or by <category>/<slug> where two entries share a slug; a table's
can also go in its "tables" plan as "relations".

Entries. Each planned entry starts at a heading on its page whose words match
its name (or its "heading", when the book prints more: "Fear (Rating)"), and
runs until the next planned entry's heading. An entry is a rules entry (its
"kind": procedure, condition, psychology, glossary) unless it names another
"category" (diseases, lore), which keeps the plan's "kind" when it gives one
(lore: god, place...). "field_labels" read the text after those bold labels
("**Harbour Master**: ...", run together or a line each) into the entry's fields
(where prose follows the last one with no blank line, the fields end at a line that stops
well short of the column's width),
and a missing one is an error; the paragraph they're printed in becomes a fields
block, items in printed order, with any text before the first label kept. Smaller headings
inside it become heading blocks. A heading the plan doesn't place, at the size
of the current entry's own heading or larger, is an error: it would be a
sibling entry nobody decided on. An entry with no heading of its own (a
letter, say, that opens with an address) can instead start at the first line on
its page whose text begins with its "starts_at"; every heading inside it is then
a subheading. "subheadings" names lines inside an entry, printed at body size
(a letter's bold section names), to read as its deepest subheadings, and
"not_headings" ([{"page", "text"}]) lines printed large that are body text (a
signature); a line either names that isn't found is an error. An entry's
"headings_as_rows" ([heading column, text column]) makes its headings and the
text under each one table (a timeline: dates and events; "row_bands" names the
headings that are eras, heading the rows below them). Lines with no
letter or digit printed below body size (flourishes) are left out and listed
under `ornaments`. Text before the first planned entry (the
chapter's title page) is left out and listed, unless the plan gives an
"intro" entry ({"name", "kind"}) for it; the chapter's title (its largest
heading) is left out either way.

An entry's "fields" ({"characteristic": "Int", "advanced": true}) are index fields the book
states in its prose, for an entry of another category (a skill described in a chapter of rules).

Careers. An entry with "career": {"class": "Burghers"} is a career printed inside the chapter:
the line under its heading is its species, and the box holding "<Name> Advance Scheme" and
"Career Path" (on its page or the next; two careers' schemes may share a box) is read as
convert_careers.py reads a career page, with the plan's "level_icons" and "scheme_columns"
(run pdf_layout.py with the icon fonts). It is written to careers/ with a career's fields; its
description, any sections printed after it and its sidebars stay its prose, the levels after
the description. A line of the scheme's box that isn't read is an error.

Slugs. --taken CATEGORY=_index.json (repeatable) gives the slugs other sources' entries hold,
category by category: an entry whose slug is taken in its own category gets the source's code
after it, and is listed under `same_name`. Each needs a relation to the entry whose name it
took: the plan's "relations" (replaces, reprint-of, adds-to, distinct-from), or, with
--library-data (the library's local library-data folder), the one comparing them gives: the
same name, fields and words are a reprint-of, any difference (a price, a quality) a replaces
(`same_name` says which, for checking). With
neither it is an error. A table whose planned slug is taken is an error.

Boxes (pdf_layout.py --boxes). A box becomes a sidebar, under its own title
(its heading lines), in the entry whose text runs just above it on its page in
the columns it spans; with no text above it there, in the entry running into
the page. The plan
can send it to another entry ("to"), or a copy to each of several (a list),
make it an entry of its own ("entry"), make each heading in it an entry ("entries": the fields
every one takes, as {"category": "lore", "kind": "other", "audience": "gm"} for a box of adventure
hooks; lines above its first heading are the page's text set over its edge, and rejoin the line
above the box: `returned_to_text`), read it as a stat block ("profile": the fields of a
"stat_blocks" entry, creatures.box_profile(), with skills, talents, spells, trappings, marks
and other labelled paragraphs; a profile block in any other entry's text),
read it as the page's own text ("text": a tinted backdrop the layout took for a box; or
"text_lines": 2, only its first lines, where a box overlaps the end of the column above it),
or mark it a diagram ("diagram": a flowchart or picture with words, left out
and listed for transcription by hand). A box read as a ruled table becomes a
table block; a table the plan lists under "tables" is also written as an entry
of its own in tables/ (when it gives a "slug"), with `about` and, when it is a
roll table, its roll column's values as {"min", "max"}. The plan can also give
a table's "title", say its read header is a "banner" printed across the
columns (and that so are its first "banner_rows": N rows; one that is the title is dropped), name the "row_groups" its
first column labels ([[label, rows], ...]: each label is printed once beside its group),
name the table "stacked" under it ({"title", "columns"}: set below with no rule between),
or that its first row is its "header_row", and name its "columns" (when the header
isn't printed or isn't read). A last column empty in the header and every row is dropped
(`empty_columns`). A table's title printed inside its frame, read into the first
row's cells, is taken out of them (`titles_stripped`). A row with only its first cell filled,
in a table of three or more columns, heads the rows below it (a group: `group_rows`); so does a
row whose one filled cell is in capitals (a band across the columns), in any table.
"continued_in" lists boxes
on later pages holding the rest of its rows, which join it (a header printed again over them is
left out). "fold": 2 reads a table
printed in two side-by-side halves (the same columns twice) down the left half, then the right;
with "fold_join" (and "header_row", the parts' labels printed above them) parts that share
their first column are joined on it instead, each part's other columns named "<label>: <column>";
"from_columns": N reads a box's unruled lines, set in N columns, as a table.
"flowed": [a table's plan, ...] reads a box of roll tables flowed down its columns, one table
for each plan (flow_tables()). A price table's "items" may name the book's own slips and
repeats: "marks_without_notes", "listed_again", "listed_elsewhere" (items.item_rows()); the
plan's "shared_labels" gives one description to several items (describe_items()), and an
entry's "split_labels" makes entries of its bold-labelled paragraphs (split_at_labels()). A table printed without rules is
listed under "text_tables": its header line (the columns' words, together), its columns and how
many rows follow; each row is split at its widest gaps, and a row without a clear gap is an
error.

Writes per entry <slug>.json and <slug>.md (render_entry.py), with `_category`
in `_records.json` (rules or tables), and `_report.json`:

- `errors` (exit status 1): a planned entry not found, an unplanned sibling
  heading, a box the plan names that isn't there.
- `questions`: line-end hyphens kept (`hyphen-join` when the book prints the
  hyphenated word elsewhere, `hyphen-unresolved` when it prints neither form).
  A word wrongly left hyphenated goes in the plan's "whole_words".
- `dehyphenated`: words split at a line end and joined without the hyphen,
  because the book prints them whole elsewhere; check_coverage.py credits them.
- `filled_down`: table cells printed once for several rows, copied into `data`.
- `tables_to_confirm`: every table, to show the Librarian before it is written.
- `diagrams`: boxes left out for transcription by hand.
- `box_placement`: which entry each box went to, for the Librarian to check.
- `titles_stripped`, `group_rows`: tables whose title came out of row 1, and their group rows.
- `folded_keys`: a "fold_join" table's key column as printed in its later parts, kept once.
- `same_name`: entries whose slug another source's entry in their category already had.
- `left_out`: everything printed that no entry holds.
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_entry import render  # noqa: E402
import items  # noqa: E402
import creatures  # noqa: E402
import convert_careers  # noqa: E402
from entry_text import (blocks_from_lines, fix_case, join_lines, marked, merge_lines, norm, plain, slugify,  # noqa: E402
                        split_items, split_row, table_data, vocabulary)


SUBHEADING = 99      # the heading level given to a plan's "subheadings": below every printed level


def read_labelled(content, labels, fields, report, name, text_labels=()):
    """An entry's "field_labels": the text after each bold label ("**Contraction:** ..."), up to
    the next bold label or the paragraph's end, becomes a field, and the labelled lines a fields
    block. Its "text_labels" ("Description") are labels too, but their text is the entry's prose:
    no field, and a paragraph of its own after the fields. Returns the content."""
    if not labels:
        return content
    text = '\n'.join(b['text'] for b in content if b['type'] == 'paragraph')
    for lab in labels:
        pat = re.compile(r'\*{2,3}' + re.escape(lab) + r':?\*{2,3}:?\s*(.*?)(?=\s*\*{2,3}[A-Z][^*\n]{0,40}:\*{2,3}|\s*\*{2,3}[A-Z][^*\n]{0,40}\*{2,3}:|\n|$)', re.S)
        hit = pat.search(text)
        if hit and plain(hit.group(1)):
            fields[slugify(lab).replace('-', '_')] = plain(hit.group(1))
        else:
            report['errors'].append({'error': f'{name}: no {lab!r} line'})
    return labelled_to_fields(content, labels, text_labels)


def split_at_headings(content, lines, spec, report, where):
    """An entry's "split_headings" ({"category", "kind"}): each of its top subheadings, with the
    blocks under it, becomes an entry of its own (a list of weapon qualities); the text before
    the first stays the entry's. A "dividers" heading ({heading: kind}, "Armour Flaws") is no
    entry: it and its text stay the entry's, and the headings after it take its kind. Returns
    (the entry's content, the new entries). "name_flags" ({field: regex}) gives each new entry a
    field that is true when its name matches ({"rated": "Rating"} for "Armour (Rating)").
    "field_labels" and "text_labels" are read in each new entry as an entry's own are (a
    potion's "Onset Time"; a cursed item's "Description"). The new entries take its "audience",
    or the entry's own. A box the plan sends "to" one of the new entries by name goes with it;
    any other box of the entry lands where its text does: after the last heading's, unless
    "sidebars": "entry" keeps them all with the entry (boxes about the whole section, set
    after its last short heading)."""
    opt = spec['split_headings']
    dividers = {norm(k): v for k, v in opt.get('dividers', {}).items()}
    kind, seen = opt.get('kind'), set()
    heads = [b['level'] for b in content if b['type'] == 'heading']
    if not heads:
        report['errors'].append({'error': f'{where}: split_headings, but the entry has no headings'})
        return content, []
    top = min(heads)
    keep, subs, after = [], [], 0
    sent = [b for b in content if b.get('_sub')]          # boxes the plan sends "to" a new entry
    for b in [b for b in content if not b.get('_sub')]:
        if b['type'] == 'heading' and b['level'] == top and norm(b['text']) in dividers:
            kind = dividers[norm(b['text'])]          # "Armour Flaws": the headings after it are flaws
            seen.add(norm(b['text']))
            keep.append(b)
            subs.append(None)
        elif b['type'] == 'heading' and b['level'] == top:
            hit = next((i for i, l in enumerate(lines) if i >= after and l.get('heading') and
                        norm(b['text']).startswith(norm(fix_case(plain(l['text']))))), None)
            if hit is None:
                report['errors'].append({'error': f'{where}: no page for the heading {b["text"]!r}'})
            page = lines[hit]['page'] if hit is not None else spec['page']
            after = hit + 1 if hit is not None else after
            subs.append({'name': b['text'], 'category': opt['category'], 'kind': kind,
                         'page': page, 'section': spec['name'], 'content': [],
                         'audience': opt.get('audience', spec.get('audience')),
                         'fields': dict({'kind': kind} if kind else {},
                                        **{f: bool(re.search(pat, b['text']))
                                           for f, pat in opt.get('name_flags', {}).items()})})
        elif subs and subs[-1] is None:
            keep.append(b)                            # a divider's own text stays the entry's
        elif subs and b['type'] == 'sidebar' and opt.get('sidebars') == 'entry':
            keep.append(b)                            # the plan says the boxes are the section's, not the last heading's
        elif subs:
            if b['type'] == 'heading':
                b = dict(b, level=b['level'] - (top - 2))
            subs[-1]['content'].append(b)
        else:
            keep.append(b)
    for d in set(dividers) - seen:
        report['errors'].append({'error': f'{where}: no divider heading {d!r}'})
    subs = [x for x in subs if x]
    for b in sent:
        home = next((x for x in subs if norm(x['name']) == norm(b['_sub'])), None)
        if home is None:
            report['errors'].append({'error': f'{where}: a box is sent to {b["_sub"]!r}, which is not one of '
                                              'its split headings'})
        else:
            home['content'].append({k: v for k, v in b.items() if k != '_sub'})
    for x in subs:
        x['content'] = read_labelled(x['content'], opt.get('field_labels', ()), x['fields'], report, x['name'],
                                     opt.get('text_labels', ()))
    return keep, subs


def split_at_labels(content, lines, spec, report, where):
    """An entry's "split_labels" ({"category", "kind", "names": [...] or {name: kind}}): each
    paragraph opening with one of those names as a bold label ("**Hooked:** ...") becomes an
    entry of its own, without the label, and takes the blocks after it up to the next named
    label or the next heading (a quality's own labelled cases stay with it). The rest stays
    the entry's. A name with no such paragraph is an error. Returns (the entry's content, the
    new entries)."""
    opt = spec['split_labels']
    names = opt['names'] if isinstance(opt['names'], dict) else {n: opt.get('kind') for n in opt['names']}
    kinds = {norm(n): k for n, k in names.items()}
    keep, subs, cur, after = [], [], None, 0
    for b in content:
        lab = items.label(b['text']) if b['type'] == 'paragraph' else None
        if lab and norm(lab[0]) in kinds and norm(lab[0]) not in {norm(x['name']) for x in subs}:
            kind = kinds[norm(lab[0])]
            hit = next((i for i, l in enumerate(lines) if i >= after and
                        norm(plain(l['text'])).startswith(norm(lab[0]))), None)
            if hit is None:
                report['errors'].append({'error': f'{where}: no page for the label {lab[0]!r}'})
            after = hit + 1 if hit is not None else after
            cur = {'name': lab[0], 'category': opt['category'], 'kind': kind,
                   'page': lines[hit]['page'] if hit is not None else spec['page'], 'section': spec['name'],
                   'content': [{'type': 'paragraph', 'text': lab[1]}],
                   'audience': opt.get('audience', spec.get('audience')),
                   'fields': dict({'kind': kind} if kind else {},
                                  **{f: bool(re.search(pat, lab[0])) for f, pat in opt.get('name_flags', {}).items()})}
            subs.append(cur)
            report['left_out'].append(lab[0])         # the label: the entry's name again
        elif b['type'] == 'heading':
            cur = None
            keep.append(b)
        elif cur is not None:
            cur['content'].append(b)
        else:
            keep.append(b)
    for n in names:
        if norm(n) not in {norm(x['name']) for x in subs}:
            report['errors'].append({'error': f'{where}: split_labels, but no paragraph is labelled {n!r}'})
    return keep, subs


def describe_items(found, describers, plan, report):
    """Paragraphs that open with an item's name as a bold label ("**Coat:** Protects ..."), in
    entries marked "describes_items", move to that item, without the label. A label naming no
    item stays where it is and is listed under `labels_kept`; two items of one name are an error,
    unless the plan's "rename" ({"<table>/<name>" or "<table>/<group>/<name>": new name})
    tells them apart; a label two renamed items share goes to the one whose table is in the
    describing entry. The plan's "shared_labels" ({label: [item names]}) gives one description
    of several items ("Lance and Demi-Lance") to each of them, label and all. (The plan's "item_slugs", {"<table>/<name>": slug}, gives an item a slug
    other than its name's, after any renaming.)"""
    for it in found:
        ren = plan.get('rename', {})
        new = ren.get(f'{it["region"]}/{it["fields"].get("group", "")}/{it["name"]}') or \
            ren.get(f'{it["region"]}/{it["name"]}')
        if new:
            report.setdefault('renamed', []).append({'region': it['region'], 'from': it['name'], 'to': new})
            it['name'] = new
    by_name = {}
    for it in found:
        by_name.setdefault(norm(it['name']), []).append(it)
    for key, its in by_name.items():
        if len(its) > 1:
            report['errors'].append({'error': f'{len(its)} items named {its[0]["name"]!r} '
                                              f'(tables {", ".join(i["region"] for i in its)}): rename them'})
    for where, content in describers:
        for b in list(content):
            lab = items.label(b['text']) if b['type'] == 'paragraph' else None
            if not lab:
                continue
            match = [it for it in found if items.same_item(it['name'], lab[0])]
            if len(match) > 1:        # two of one name once renamed: the one whose table is in this entry
                match = [it for it in match if it['section'] == where] or match
            shared = [it for n in plan.get('shared_labels', {}).get(lab[0], ()) for it in found
                      if norm(it['name']) == norm(n)]
            if shared:                # one description of several items ("Lance and Demi-Lance"): to each
                for it in shared:
                    it.setdefault('content', []).append({'type': 'paragraph', 'text': b['text']})
                content.remove(b)
                report.setdefault('descriptions_shared', []).append({'label': lab[0], 'items': [it['name'] for it in shared]})
                continue
            if len(match) == 1:
                match[0].setdefault('content', []).append({'type': 'paragraph', 'text': lab[1]})
                content.remove(b)
                report.setdefault('descriptions_moved', []).append(match[0]['name'])
                report['left_out'].append(lab[0])     # the label: the item's name again
            else:
                report.setdefault('labels_kept', []).append({'entry': where, 'label': lab[0],
                                                             'items': len(match)})


OWN = '#own'      # in `taken`: {category: {slug: chapter}} for this source's own entries


def free_slug(slug, cat, name, plan, taken, used_slugs, report):
    """The entry's slug, with the source's code after it when another source's entry in its
    category has it already (`taken`: {category: slugs}; a bare set is checked for every
    category) or an entry of this chapter does. A slug taken by another source is listed under
    `same_name`, for the plan to say how the two relate (replaces, reprint-of, distinct-from).
    A slug another chapter of this source holds is an error: the plan must give a different one."""
    theirs = slug in (taken.get(cat, ()) if isinstance(taken, dict) else taken)
    own = taken.get(OWN, {}).get(cat, {}) if isinstance(taken, dict) else {}
    if slug in own and own[slug] != plan['chapter'] and report is not None:
        # Re-importing a chapter rewrites its own entries; another chapter's would be lost.
        report['errors'].append({'error': f'{cat}/{slug} ({name}): {plan["source"]} {own[slug]} already has an '
                                          'entry with this slug; give this one a "slug" in the plan'})
    if theirs or (cat, slug) in used_slugs:
        if theirs and report is not None:
            report.setdefault('same_name', []).append({'category': cat, 'name': name, 'taken': slug})
        slug = f'{slug}-{plan["source"].lower()}'
        if slug in own and own[slug] != plan['chapter'] and report is not None:
            # ...and so would the one that took the source's code in another chapter.
            report['errors'].append({'error': f'{cat}/{slug} ({name}): {plan["source"]} {own[slug]} already has an '
                                              'entry with this slug; give this one a "slug" in the plan, or, for an '
                                              'item the book lists again, name its row in "listed_elsewhere"'})
    used_slugs.add((cat, slug))
    return slug


def all_text(value):
    """Every word an entry's content holds, as one string of letters and digits: two printings of
    a text compare equal however their lines broke."""
    if isinstance(value, dict):
        return ''.join(all_text(v) for k, v in value.items() if k not in ('type', 'level', 'data'))
    if isinstance(value, list):
        return ''.join(all_text(v) for v in value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)                                  # a casting number, an encumbrance
    return re.sub(r'[\W_]+', '', plain(value).lower()) if isinstance(value, str) else ''


def same_entry(a, b):
    """Whether two entries say the same thing throughout: name, fields (a price, a quality, a
    casting number) and text. An item's whole statement is its fields, so text alone won't do."""
    return all(all_text(a.get(k)) == all_text(b.get(k)) for k in ('name', 'fields', 'content'))


def relate_same_name(cat, entry, rec, plan, library, report):
    """An entry that took another source's entry's name (the last under `same_name`) needs a
    relation to it. The plan's stands (but not distinct-from: two different things in one
    category need two names, since a slug's suffix is seen by no one); without one, the two texts are compared, when the
    library's entries are at hand (--library-data): the same name, fields and words make it a
    reprint-of, any difference a replaces. With neither it is an error: nobody decided."""
    item = report['same_name'][-1]
    theirs = item['taken']
    if entry.get('relations'):
        item['relation'] = 'from the plan'
        if any(r == {'role': 'distinct-from', 'to': f'{cat}/{theirs}'} for r in entry['relations']):
            # A slug's suffix is the tools' business: nobody using the library sees it.
            report['errors'].append({'error': f'{cat}/{entry["slug"]}: {entry["name"]!r} is distinct from '
                                              f'{cat}/{theirs} yet has its name. Rename it in the plan, so that '
                                              'people can tell the two apart'})
        return
    path = os.path.join(library, cat, theirs + '.json') if library else None
    if not path or not os.path.exists(path):
        report['errors'].append({'error': f'{cat}/{entry["slug"]}: another source has {cat}/{theirs}. Give the two '
                                          'a relation in the plan, or pass --library-data to compare their text'})
        return
    with open(path, encoding='utf-8') as f:
        other = json.load(f)
    role = 'reprint-of' if same_entry(entry, other) else 'replaces'
    entry['relations'] = rec['relations'] = [{'role': role, 'to': f'{cat}/{theirs}'}]
    item['relation'] = role


def relate_again(cat, entry, rec, library, report):
    """For a converter that fills an entry's fields after convert() compared it (a spell's
    casting number and range): the comparison once more, with the fields in. A relation the
    plan gave stands."""
    item = next((x for x in report.get('same_name', []) if x['category'] == cat and x['name'] == entry['name'] and
                 x.get('relation') in ('reprint-of', 'replaces')), None)
    path = os.path.join(library, cat, item['taken'] + '.json') if item and library else None
    if not path or not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:
        role = 'reprint-of' if same_entry(entry, json.load(f)) else 'replaces'
    entry['relations'] = rec['relations'] = [{'role': role, 'to': f'{cat}/{item["taken"]}'}]
    item['relation'] = role


def read_career(e, entries, lines, layout, plan, report):
    """A career printed inside a chapter (the plan entry's "career": {"class": ...}): its species
    line, under its heading, and the box holding its advance scheme and career path, read as
    convert_careers.py reads a career page. Both are taken out of the entry's text, which stays
    prose (its description, any sections on the pages after, its sidebars). Returns the species
    line's block, the `career_levels` block and the career's fields. A career that prints no
    species line names its "species" in the plan; one whose levels print no status, trappings or
    skill for Earning money is "bare": true (a familiar's); one whose book set no level 1 skill
    in italics says "earning_skill": false, one with a fifth level "levels": 5, one entered part-way "first_level": 3 with its "levels", one whose scheme is titled with a
    shorter name that name as "scheme" ("Lamp Warden of the Reach" over a "Lamp Warden Advance Scheme"), and the report's `excused` says the check was let off."""
    name, page = e['spec']['name'], e['spec']['page']
    missing = [k for k in ('level_icons', 'scheme_columns') if k not in plan]
    if missing:
        report['errors'].append({'error': f'{name}: a career needs the plan\'s {" and ".join(missing)}'})
        return None, None, {}
    first = e['lines'][0] if e['lines'] and not e['lines'][0].get('heading') else None
    species, species_block = [], None
    if 'species' in e['spec']['career']:        # the book prints no species line (a familiar's career)
        species = list(e['spec']['career']['species'])
    elif first is None:
        report['errors'].append({'career': name, 'error': 'no species line after the heading'})
    else:
        e['lines'] = e['lines'][1:]
        species = split_items(plain(first['text']))
        species_block = {'type': 'paragraph', 'text': marked(first)}
    fields = {'class': e['spec']['career'].get('class'), 'species': species}
    if not fields['class']:
        report['errors'].append({'career': name, 'error': 'the plan gives no class'})
    titled = e['spec']['career'].get('scheme', name)      # the scheme's title may shorten the career's name
    for i, l in enumerate(lines[:-1]):                    # ...and may be set on two lines ("HEARTH PRIEST" / "ADVANCE SCHEME")
        nxt = lines[i + 1]
        if l.get('box') and nxt.get('box') == l['box'] and norm(l['text']) == norm(titled) and \
                norm(nxt['text']) == 'advance scheme' and e['spec']['page'] <= l['page'] <= page + 1:
            lines[i:i + 2] = [dict(l, text=f'{l["text"]} {nxt["text"]}', spans=l['spans'] + nxt['spans'],
                                   words=l.get('words', []) + nxt.get('words', []), baseline=nxt['baseline'])]
            break
    bid = next((l['box'] for l in lines if l.get('box') and e['spec']['page'] <= l['page'] <= page + 1 and
                norm(l['text']) == norm(titled + ' advance scheme')), None)
    if bid is None:
        report['errors'].append({'career': name, 'error': 'no box holding its advance scheme'})
        return species_block, None, fields
    for other in entries:
        if bid in other['boxes']:
            other['boxes'].remove(bid)
    box = [l for l in lines if l.get('box') == bid]
    start = next(i for i, l in enumerate(box) if norm(l['text']) == norm(titled + ' advance scheme'))
    stop = next((i for i, l in enumerate(box) if i > start and norm(l['text']).endswith(' advance scheme')), len(box))
    mine = box[start:stop]            # a box can hold two careers' schemes, one after the other
    on_page = mine[0]['page']
    marks = [m for m in layout.get('marks', []) if m['page'] == on_page]
    shapes = [x for x in layout.get('shapes', []) if x['page'] == on_page]
    block, level_fields, used = convert_careers.career_levels(name, mine, marks, shapes, plan, report,
                                                               bare=bool(e['spec']['career'].get('bare')),
                                                               earning_marked=e['spec']['career'].get('earning_skill', True)
                                                               is not False,
                                                               count=e['spec']['career'].get('levels', 4),
                                                               first=e['spec']['career'].get('first_level', 1),
                                                               titled=titled)
    unread = [l['text'] for i, l in enumerate(mine) if i not in used] + \
        ([l['text'] for l in box[:start]] if not any(norm(l['text']).endswith(' advance scheme') for l in box[:start]) else [])
    if unread:
        report['errors'].append({'career': name, 'error': f'lines in the scheme\'s box that were not read: {unread}'})
    fields.update(level_fields)
    return species_block, block, fields


REPLACES = re.compile(r'replaces? the (\d)(?:st|nd|rd|th) level of the (.+?) Career\b')
INSTEAD = re.compile(r'corresponding Characteristic with (\w+)')


def level_updates(lines, report, where):
    """An entry of "level_updates" (single career levels a book offers in place of levels of
    careers printed elsewhere, each under its own heading): every level line ("Guild Warden —
    Silver 3", in bold) with the Skills, Talents and Trappings under it becomes a
    `career_levels` block of that one level, numbered by the sentence above it ("... replace
    the 2nd level of the Warden (Some Book) or Keeper (Other Book page 9) Career"). Returns
    the lines and what each level replaces, for the entry's `level_updates` field: title,
    status, level, replaces [{career, source}], characteristic (when the level changes the one
    its career level gives), skills, talents, trappings. A level line with no such sentence
    above it is an error."""
    out, found, since = [], [], 0
    i = 0
    while i < len(lines):
        l = lines[i]
        m = convert_careers.LEVEL_LINE.match(plain(l['text'])) if not l.get('heading') and not l.get('block') and \
            l['spans'] and l['spans'][0]['bold'] and l['bold'] else None
        if l.get('heading'):
            since = len(out) + 1
        if not m:
            out.append(l)
            i += 1
            continue
        raw, label, buf, j = {}, None, [], i + 1
        while j < len(lines) and not lines[j].get('heading') and not lines[j].get('block') and \
                lines[j].get('box') == l.get('box'):
            x = lines[j]
            lead = plain(x['spans'][0]['text']).rstrip(':') if x['spans'] and x['spans'][0]['bold'] else None
            if lead in convert_careers.LABELS:
                if label:
                    raw[label] = join_lines(buf, report, where)
                label = lead
                report['left_out'].append(x['spans'][0]['text'])
                rest = ' '.join(marked({'spans': [sp]}) for sp in x['spans'][1:])
                buf = [rest] if rest else []
            elif label:
                buf.append(marked(x))
            else:
                break
            j += 1
        if label:
            raw[label] = join_lines(buf, report, where)
        title, status = m.group('title'), m.group('status')
        said = ' '.join(plain(x['text']) for x in out[since:])
        r = REPLACES.search(said)
        if not r or 'Skills' not in raw or 'Talents' not in raw:
            report['errors'].append({'error': f'{where}: the level {title!r} has no "replace the Nth level of the ... '
                                              'Career" sentence above it, or no Skills or Talents under it'})
            out.append(l)
            i += 1
            continue
        level = {'title': title, 'status': status, 'characteristics': []}
        rec = {'title': title, 'status': status, 'level': int(r.group(1)),
               'replaces': [{'career': c.split(' (')[0].strip(), 'source': c.partition(' (')[2].rstrip(') ')}
                            for c in r.group(2).split(' or ')]}
        ch = INSTEAD.search(said)
        if ch:
            rec['characteristic'] = ch.group(1)
        for lab in convert_careers.LABELS:
            if lab in raw:
                level[lab.lower()] = [x for x in split_items(raw[lab]) if x]
                rec[lab.lower()] = [plain(x) for x in level[lab.lower()]]
        if 'Trappings' not in raw:
            report['questions'].append({'entry': where, 'kind': 'level-without-trappings',
                                        'text': f'{title}: no Trappings are printed for this level'})
        out.append(dict(merge_lines(lines[i:j], {'type': 'career_levels', 'first_level': rec['level'], 'levels': [level]}),
                        heading=None))
        found.append(rec)
        i = j
    if not found:
        report['errors'].append({'error': f'{where}: "level_updates", but no level line was found'})
    return out, found


def add_entry(spec, out, records, plan, taken, used_slugs):
    """An entry made from part of another (a split heading, a price-table row): written and
    indexed like the plan's own."""
    cat, name = spec['category'], spec['name']
    fields = dict(spec.get('fields') or ({'kind': spec['kind']} if spec.get('kind') else {}))
    # a slug is one entry's within its category
    slug = free_slug(spec.get('slug') or slugify(name), cat, name, plan, taken, used_slugs, spec.get('_report'))
    entry = {'slug': slug, 'name': name, 'source': plan['source'], 'chapter': plan['chapter'],
             'section': spec['section'], 'page': spec['page'], 'level': 1, 'fields': fields,
             'content': spec['content']}
    if cat == 'rules':
        entry['kind'] = fields.get('kind', 'procedure')
    rel = plan.get('relations', {}).get(f'{cat}/{slug}') or plan.get('relations', {}).get(slug)
    if rel:
        entry['relations'] = rel
    if spec.get('audience'):
        entry['audience'] = spec['audience']
    out.append((cat, entry))
    rec = {'slug': slug, 'name': name, 'source': plan['source'], 'chapter': plan['chapter'],
           'section': spec['section'], 'page': spec['page'], '_category': cat}
    rec.update(fields)
    if spec.get('audience'):
        rec['audience'] = spec['audience']
    if rel:
        rec['relations'] = rel
    records.append(rec)
    if slug != (spec.get('slug') or slugify(name)) and spec.get('_report') and \
            spec['_report'].get('same_name', [{}])[-1].get('name') == name and 'relation' not in spec['_report']['same_name'][-1]:
        relate_same_name(cat, entry, rec, plan, spec.get('_library'), spec['_report'])


def headings_to_rows(content, columns, report, where, bands=()):
    """An entry's run of headings, each followed by its text (a timeline's dates, a glossary's
    terms), as one table with `columns` [heading, text]: each heading a row, its paragraphs joined
    in the second cell. Text before the first heading stays as it is; anything else under a
    heading (a list, a sidebar) is an error. The headings the plan names as `bands` (a timeline's
    eras) have no text of their own: each heads the rows below it, as a table's group."""
    head = next((i for i, b in enumerate(content) if b['type'] == 'heading'), None)
    if head is None:
        report['errors'].append({'error': f'{where}: headings_as_rows, but the entry has no headings'})
        return content
    rows, groups, named, under_band = [], [], {norm(x) for x in bands}, None
    for b in content[head:]:
        if b['type'] == 'heading' and norm(b['text']) in named:
            groups.append({'before': len(rows), 'text': b['text']})
            under_band = b['text']
        elif b['type'] == 'heading':
            rows.append([b['text'], ''])
            under_band = None
        elif under_band:
            report['errors'].append({'error': f'{where}: {under_band!r} is a band in the plan, but has text under it'})
        elif b['type'] == 'paragraph':
            rows[-1][1] = (rows[-1][1] + ' ' + b['text']).strip()
        else:
            report['errors'].append({'error': f'{where}: a {b["type"]} under {rows[-1][0]!r} '
                                              f'can\'t go in a row'})
    empty = [r[0] for r in rows if not r[1]]
    if empty:
        report['errors'].append({'error': f'{where}: no text under {", ".join(map(repr, empty))}'})
    unmet = [x for x in bands if norm(x) not in {norm(g['text']) for g in groups}]
    if unmet:
        report['errors'].append({'error': f'{where}: no heading for the band {", ".join(map(repr, unmet))}'})
    block = {'type': 'table', 'title': '', 'columns': list(columns), 'rows': rows,
             'data': table_data(list(columns), rows, report, where, None)}
    if groups:
        block['groups'] = groups
    return content[:head] + [block]


def page_column(line, gutters):
    """The column ("left", "middle", "right") a line sits in between a page's gutters, or
    "full" when it crosses one."""
    names = {1: ['left', 'right'], 2: ['left', 'middle', 'right']}.get(len(gutters))
    if not names:
        return 'full'
    edges = [float('-inf')] + list(gutters) + [float('inf')]
    for i, name in enumerate(names):
        if line['x0'] >= edges[i] and line['x1'] <= edges[i + 1]:
            return name
    return 'full'


def boxes_as_text(lines, boxes_plan, report, gutters=None):
    """Boxes the plan marks "text" (a tinted backdrop read as a box), and the first "text_lines"
    lines of a box that overlaps the end of a column, are read as the page's columns: their lines lose the box and take the page column (from its `gutters`) they sit
    in, and the page is read again, top to bottom between its full-width lines, column by
    column from the left."""
    pages = {}
    for bid, bp in boxes_plan.items():
        if bp.get('text') or bp.get('text_lines'):
            hit = [l for l in lines if l.get('box') == bid]
            if not bp.get('text'):                   # only its first lines: the box overlaps the column's end
                hit = hit[:bp['text_lines']]
            if not hit:
                report['errors'].append({'error': f'the plan reads box {bid} as text, but it has no lines'})
            for l in hit:
                l['box'] = None
                l['column'] = page_column(l, (gutters or {}).get(str(l['page'])) or [])
                pages[l['page']] = True
    if not pages:
        return lines
    rank = {'full': -1, 'left': 0, 'middle': 1, 'right': 2}

    def key(l):
        fulls = [x['baseline'] for x in lines if x['page'] == l['page'] and x['column'] == 'full' and not x.get('box')]
        above = sum(1 for b in fulls if b < l['baseline'] or (b == l['baseline'] and l['column'] != 'full'))
        return (above, rank.get(l['column'], 2), l['baseline'], l['x0'])
    out = []
    for page in dict.fromkeys(l['page'] for l in lines):
        on = [l for l in lines if l['page'] == page]
        if page in pages:
            on = sorted([l for l in on if not l.get('box')], key=key) + [l for l in on if l.get('box')]
        out += on
    return out


def heading_runs(lines):
    """Index of each heading start -> (text, last index): a heading printed over two lines is one."""
    runs, i = {}, 0
    while i < len(lines):
        l = lines[i]
        if l.get('heading') and not l.get('box'):
            j, text = i, plain(l['text'])
            while (j + 1 < len(lines) and lines[j + 1].get('heading') == l['heading'] and
                   not lines[j + 1].get('box') and lines[j + 1]['column'] == l['column'] and
                   lines[j + 1]['page'] == l['page'] and
                   lines[j + 1]['baseline'] - lines[j]['baseline'] < 1.6 * l['size']):
                j += 1
                text += ' ' + plain(lines[j]['text'])
            runs[i] = (text, j)
            i = j + 1
        else:
            i += 1
    return runs


def box_parts(box_lines):
    """A box's lines -> (title, body lines, table lines): the title is its leading heading lines."""
    title, i = [], 0
    while i < len(box_lines) and box_lines[i].get('heading') and not box_lines[i].get('table'):
        title.append(plain(box_lines[i]['text']))
        i += 1
    body = [l for l in box_lines[i:] if not l.get('table')]
    return fix_case(' '.join(title)), body, [l for l in box_lines if l.get('table')]


def labelled_to_fields(content, labels, text_labels=()):
    """Each paragraph holding the plan's bold labels ("**Contraction:** ... **Incubation:** ...")
    becomes a fields block, its items in printed order; text before the first label stays a
    paragraph. Neighbouring fields blocks join. A `text_labels` label ("**Description:** ...")
    ends the fields: it and the text after it stay a paragraph, markup and all."""
    out = []
    for b in content:
        hits = []
        if b['type'] == 'paragraph':
            for lab in list(labels) + list(text_labels):
                m = re.search(r'\*{2,3}' + re.escape(lab) + r':?\*{2,3}:?\s*', b['text'])
                if m:
                    hits.append((m.start(), m.end(), lab))
        if not hits:
            out.append(b)
            continue
        hits.sort()
        prose = next((k for k, h in enumerate(hits) if h[2] in text_labels), len(hits))
        rest = b['text'][hits[prose][0]:].strip() if prose < len(hits) else ''
        hits = hits[:prose] + ([(hits[prose][0], None, None)] if rest else [])
        if b['text'][:hits[0][0]].strip():
            out.append(dict(b, text=b['text'][:hits[0][0]].strip()))
        items = [{'label': lab, 'text': plain(b['text'][end:(hits[k + 1][0] if k + 1 < len(hits) else None)])}
                 for k, (_, end, lab) in enumerate(hits) if lab]
        if items and out and out[-1]['type'] == 'fields' and not out[-1].get('title'):
            out[-1]['items'] += items
        elif items:
            out.append({'type': 'fields', 'title': '', 'items': items})
        if rest:
            out.append(dict(b, text=rest))
    return out


def strip_title(row, title):
    """The table's title, when its words lead cells of the first row ("Lamp Mishaps table
    Soot: ..." or "OILS BY Tallow" / "TOWER Rush"), taken out of them. Returns the row
    and whether the whole title was found; a title only partly there leaves the row alone."""
    want = [norm(w) for w in title.split()]
    out, k = list(row), 0
    for i, cell in enumerate(out):
        words = cell.split()
        n = 0
        while k < len(want) and n < len(words) and norm(words[n]) == want[k]:
            n, k = n + 1, k + 1
        if n:
            out[i] = ' '.join(words[n:])
        if k == len(want):
            return out, True
    return list(row), False


def unstack(region, plan_t, report, where):
    """Two tables set one under the other with no rule between, read as one: the second's title
    and header ran into the row above them. The plan's "stacked" ({"title", "columns"}) names the
    second table; the row whose cells end with its header is cleaned of title and header, and the
    rows below it are the second table's. -> (the first table's region, the second's or None)."""
    st = (plan_t or {}).get('stacked')
    if not st:
        return region, None
    heads = st['columns']
    title = [norm(w) for w in st['title'].split()]
    for k, row in enumerate(region['rows']):
        if len(row) != len(heads) or not all(norm(c).endswith(norm(h)) for c, h in zip(row, heads)):
            continue
        clean, at = [], 0
        for c, h in zip(row, heads):
            words = c.split()
            words = words[:len(words) - len(h.split())]                    # the header's label
            m = min(len(words), len(title) - at)                          # the title's next words
            while m and [norm(w) for w in words[len(words) - m:]] != title[at:at + m]:
                m -= 1
            at += m
            clean.append(' '.join(words[:len(words) - m]))
        if at != len(title):
            break
        return (dict(region, rows=region['rows'][:k] + [clean]),
                dict(region, id=region['id'] + 'b', columns=list(heads), rows=region['rows'][k + 1:]))
    report['errors'].append({'error': f'{where}: table {region["id"]}: no row ends with the header of the '
                                      f'table the plan stacks under it ({st["title"]!r})'})
    return region, None


def label_row_groups(rows, groups, report, where, rid):
    """A table whose first column labels groups of rows, each label printed once beside its group
    (centred on it, or over two lines, or run across the first two cells of a group of one row).
    The plan's "row_groups" names them in order, [[label, number of rows], ...]; every row of a
    group then carries its label. The labels must be the first column's words, in order."""
    if not groups:
        return rows
    out, at = [], 0
    for label, n in groups:
        part = [list(r) for r in rows[at:at + n]]
        at += n
        printed = ' '.join(r[0] for r in part if r[0].strip())
        if len(part) == n == 1 and norm(printed + ' ' + part[0][1]) == norm(label):
            part[0][1] = ''                   # one row, its name set across the first two cells
        elif len(part) != n or norm(printed) != norm(label):
            report['errors'].append({'error': f'{where}: table {rid} prints {printed!r} beside the {n} rows the '
                                              f'plan groups as {label!r}'})
            return rows
        for r in part:
            r[0] = label
        out += part
    if at != len(rows):
        report['errors'].append({'error': f'{where}: table {rid} has {len(rows)} rows; the plan\'s row_groups '
                                          f'cover {at}'})
        return rows
    return out


def table_block(region, title, plan_t, report, where):
    cols, rows, banners, width, title = table_cells(region, title, plan_t, report, where)
    plan_t = plan_t or {}
    rows = label_row_groups(rows, plan_t.get('row_groups'), report, where, region['id'])
    groups, kept = [], []
    for r in rows:                    # a row with only its first cell filled heads the rows below
        only = [c.strip() for c in r if c.strip()]
        if width > 2 and r and r[0].strip() and not any(c.strip() for c in r[1:]):
            groups.append({'before': len(kept), 'text': r[0].strip()})
        elif (only and len(only) <= max(1, width // 3) and all(c.isupper() for c in only) and
              len(re.sub(r'[^A-Za-z]', '', ''.join(only))) >= 3):
            # ...and so does a band in capitals across the columns, whichever cells it was read into
            groups.append({'before': len(kept), 'text': fix_case(' '.join(only))})
        else:
            kept.append(r)
    if groups:
        rows = kept
        report.setdefault('group_rows', []).append({'entry': where, 'region': region['id'],
                                                    'groups': [g['text'] for g in groups]})
    names = cols if cols else [f'Column {i + 1}' for i in range(width)]
    block = {'type': 'table', 'title': title, 'columns': cols or [''] * width,
             'rows': rows, 'data': table_data(names, rows, report, where, plan_t.get('roll_column'))}
    if banners:
        block['banners'] = banners
    if groups:
        block['groups'] = groups
    report['tables_to_confirm'].append({'entry': where, 'region': region['id'], 'page': region['page'],
                                        'title': block['title'], 'columns': len(names), 'rows': len(rows)})
    return block


def table_cells(region, title, plan_t, report, where):
    """A table region's (columns, rows, banners, width, title) as its plan reads them: a cell
    holding two columns split ("split_column"), a banner, rows of banners ("banner_rows": the
    title printed in the frame, a label over some columns), a header row, folded halves, a title
    printed in the first row, and the columns' names."""
    cols, rows = list(region.get('columns') or []), [list(r) for r in region['rows']]
    plan_t = plan_t or {}
    if plan_t.get('split_column'):
        sc = plan_t['split_column']
        cols, rows = items.split_column(cols, rows, sc['index'], sc['words'], report,
                                        f'{where}: table {region["id"]}')
    banners = []
    if plan_t.get('banner'):          # the header read is a banner printed across the columns
        text = ' '.join(c for c in cols if c.strip())
        start = next((i for i, c in enumerate(cols) if c.strip()), 0)
        if norm(text) != norm(plan_t.get('title') or title or ''):      # the table's title is no banner
            banners.append({'text': text, 'start': start, 'span': len(cols) - start})
        cols = []
    for _ in range(plan_t.get('banner_rows', 0)):      # rows above the header, each one banner
        if not rows:
            break
        row = rows.pop(0)
        text = ' '.join(c for c in row if c.strip())
        start = next((i for i, c in enumerate(row) if c.strip()), 0)
        if text and norm(text) != norm(plan_t.get('title') or title or ''):
            banners.append({'text': text, 'start': start, 'span': len(row) - start})
    labels = []
    if plan_t.get('header_row'):      # the first row read is the header (printed below a rule)
        labels = cols                 # what was read as the header is then each part's label
        cols, rows = rows[0], rows[1:]
    dropped = 0                       # a last column with nothing in it, header or rows: a frame's edge
    while len(cols) > 1 and rows and all(len(r) == len(cols) for r in rows) and \
            not cols[-1].strip() and not any(r[-1].strip() for r in rows) and not any(c.strip() for c in labels[len(cols) - 1:]):
        cols, rows, labels, dropped = cols[:-1], [r[:-1] for r in rows], labels[:len(cols) - 1], dropped + 1
    if dropped:
        report.setdefault('empty_columns', []).append({'entry': where, 'region': region['id'], 'dropped': dropped})
        banners = [dict(b, span=min(b['span'], len(cols) - b['start'])) for b in banners if b['start'] < len(cols)]
    if plan_t.get('fold'):            # one table printed in side-by-side halves: read down each
        n = plan_t['fold']
        k = len(cols) // n
        if k == 0 or len(cols) != k * n or any(cols[i * k:(i + 1) * k] != cols[:k] for i in range(n)):
            report['errors'].append({'error': f'{where}: table {region["id"]} is not {n} copies of '
                                     f'one set of columns: {cols}'})
        elif plan_t.get('fold_join'):   # parts sharing their first column: one row per key
            names = [' '.join(c for c in labels[i * k:(i + 1) * k] if c.strip()) or f'Part {i + 1}'
                     for i in range(n)]
            if any([r[i * k] for r in rows] != [r[0] for r in rows] for i in range(n)):
                report['errors'].append({'error': f'{where}: table {region["id"]}: the {n} parts don\'t '
                                         f'share their first column'})
            else:
                # The key column printed once per part is kept once; the copies are listed.
                report.setdefault('folded_keys', []).append(
                    {'entry': where, 'region': region['id'],
                     'cells': [c for i in range(1, n) for c in [cols[i * k]] + [r[i * k] for r in rows]]})
                vals = cols[1:k]
                cols = [cols[0]] + [f'{nm}: {v}' for nm in names for v in vals]
                rows = [[r[0]] + [c for i in range(n) for c in r[i * k + 1:(i + 1) * k]] for r in rows]
        else:
            rows = [r[i * k:(i + 1) * k] for i in range(n) for r in rows]
            rows = [r for r in rows if any(c.strip() for c in r)]
            cols = cols[:k]
    width = max([len(cols)] + [len(r) for r in rows])
    title = plan_t.get('title') or title
    if title and rows:                # a title printed inside the table's frame, read into row 1
        rows[0], stripped = strip_title(rows[0], title)
        if stripped:
            report.setdefault('titles_stripped', []).append({'entry': where, 'region': region['id'],
                                                             'title': title})
    if plan_t.get('columns'):         # the columns' names, when the header isn't printed or read
        if len(plan_t['columns']) != width:
            report['errors'].append({'error': f'{where}: table {region["id"]} has {width} columns, '
                                     f'the plan names {len(plan_t["columns"])}'})
        else:
            cols = list(plan_t['columns'])
    if not any(c.strip() for c in cols):
        cols = []
    return cols, rows, banners, width, title


CELL_GAP = 8.0      # points: words further apart than this on a line are in different cells


def keyed_rows(run, ncol, report, where):
    """The rows of an unruled table whose last column wraps: every row opens with a key (the
    first column), set level with any one line of its text, which may run above and below it.
    Cells start at the columns' left edges, found from where the lines' cells begin; a line of
    text belongs to the key nearest it. Returns the rows, or None after an error."""
    cells = []                                        # (baseline, x0, text)
    for l in run:
        cur = None
        for w, a, b in l['words']:
            if cur is None or a - cur[3] > CELL_GAP:
                cur = [l['baseline'], a, [w], b]
                cells.append(cur)
            else:
                cur[2].append(w)
                cur[3] = b
    starts = []
    for x in sorted(c[1] for c in cells):
        if not starts or x - starts[-1][-1] > CELL_GAP:
            starts.append([x])
        else:
            starts[-1].append(x)
    starts = [s[0] for s in sorted(starts, key=len, reverse=True)[:ncol]]
    starts.sort()
    if len(starts) != ncol:
        report['errors'].append({'error': f'{where}: {ncol} columns planned, but its cells start at {len(starts)} places'})
        return None
    col = lambda x: max(k for k, s in enumerate(starts) if x >= s - CELL_GAP / 2) if x >= starts[0] - CELL_GAP / 2 else 0
    keys = sorted({c[0] for c in cells if col(c[1]) == 0})
    if not keys:
        report['errors'].append({'error': f'{where}: no line opens with a key'})
        return None
    rows = [[[] for _ in range(ncol)] for _ in keys]
    for base, x, words, _ in sorted(cells, key=lambda c: (c[0], c[1])):
        k = min(range(len(keys)), key=lambda n: abs(keys[n] - base))
        rows[k][col(x)].append(' '.join(words))
    rows = [[' '.join(c) for c in r] for r in rows]
    short = [r[0] for r in rows if not r[-1]]
    if short:
        report['errors'].append({'error': f'{where}: no text beside {", ".join(map(repr, short))}'})
        return None
    return rows


def keyed_text_table(lines, t, i, report, where):
    """A "keyed" text table (see keyed_rows): it runs from its header to the end of its page, or
    to the line the plan's "ends_before" starts. "more" ([pages]) lists pages where it goes on
    under the same header; the header there, and any line above it that is also printed above
    the first header (the title and its note, said again), are left out once."""
    def body(page, at):
        end = next((k for k in range(at + 1, len(lines)) if lines[k]['page'] != page or lines[k].get('block') or
                    (t.get('ends_before') and norm(plain(lines[k]['text'])).startswith(norm(t['ends_before'])))), len(lines))
        return at + 1, end
    a, b = body(t['page'], i)
    rows = keyed_rows(lines[a:b], len(t['columns']), report, where)
    drop, run = set(), lines[i:b]
    above = {norm(plain(l['text'])) for l in lines[:i] if l['page'] == t['page']}
    for page in t.get('more', []):
        j = next((k for k, l in enumerate(lines) if l['page'] == page and norm(plain(l['text'])) == norm(t['header'])), None)
        if j is None:
            report['errors'].append({'error': f'{where}: no header on page {page}'})
            return lines
        a2, b2 = body(page, j)
        more = keyed_rows(lines[a2:b2], len(t['columns']), report, f'{where}, page {page}')
        rows = rows + more if rows is not None and more is not None else None
        again = [k for k in range(j) if lines[k]['page'] == page and norm(plain(lines[k]['text'])) in above]
        report['left_out'] += [lines[k]['text'] for k in again + [j]]
        drop |= set(again) | set(range(j, b2))
    if rows is None:
        return lines
    cols = t['columns']
    block = {'type': 'table', 'title': t.get('title', ''), 'columns': cols, 'rows': rows,
             'data': table_data(cols, rows, report, where, t.get('roll_column'))}
    report['tables_to_confirm'].append({'entry': where, 'region': 'text', 'page': t['page'], 'title': block['title'],
                                        'columns': len(cols), 'rows': len(rows)})
    merged = merge_lines(run, block)
    return [merged if k == i else l for k, l in enumerate(lines) if (k not in drop and not i < k < b) or k == i]


def hand_tables(lines, plans, report):
    """Tables transcribed by hand (the plan's "hand_tables"), for a table no reader can take off
    the page: marks on lines of their own, labels set beside the middle of the rows they head,
    cells that wrap. Each names its "page" and the line it "starts" at, and runs to the end of
    that page, of "through_page", or to the line "ends_before" starts; it gives "title",
    "columns", "rows", and may give "footnotes", "groups" and "also" (what the page prints besides: the
    title as printed, a header printed again) and "added" (a column heading of the transcript's
    own, for a column the page leaves bare). The transcript is checked against the page:
    letter for letter, spaces aside, the two must hold the same, or it is an error that lists
    the words on one side only. The lines are replaced by one carrying the table block; with a
    "slug" the table is an entry of its own as well (as a ruled table's is), and with
    "in_text": false only that (a table set after the last of a run of short entries, which
    is none of theirs). Returns the lines
    and the tables that are to be entries."""
    entries = []
    for t in plans:
        where = f'hand table {t["title"]!r} on page {t["page"]}'
        i = next((k for k, l in enumerate(lines) if l['page'] == t['page'] and not l.get('block') and
                  norm(plain(l['text'])) == norm(t['starts'])), None)
        if i is None:
            report['errors'].append({'error': f'{where}: no line {t["starts"]!r}'})
            continue
        last = t.get('through_page', t['page'])
        end = next((k for k in range(i + 1, len(lines)) if lines[k]['page'] > last or (
            t.get('ends_before') and norm(plain(lines[k]['text'])).startswith(norm(t['ends_before'])))), len(lines))
        run = lines[i:end]
        said = list(t['columns']) + [c for r in t['rows'] for c in r] + list(t.get('footnotes', [])) + list(t.get('also', [])) + \
            [g['text'] for g in t.get('groups', [])]
        for x in t.get('added', []):                  # a heading the transcript gives a column the page leaves bare
            said.remove(x)
        if any(len(r) != len(t['columns']) for r in t['rows']):
            report['errors'].append({'error': f'{where}: a row with other than {len(t["columns"])} cells'})
            continue
        letters = lambda texts: collections.Counter(''.join(plain(x) for x in texts).replace(' ', '').casefold())
        printed = [l['text'] for l in run]
        if letters(printed) != letters(said):
            a = collections.Counter(w for x in printed for w in plain(x).split())
            b = collections.Counter(w for x in said for w in plain(x).split())
            report['errors'].append({'error': f'{where}: the transcript and the page differ',
                                     'only_on_the_page': sorted((a - b).elements())[:40],
                                     'only_in_the_transcript': sorted((b - a).elements())[:40]})
            continue
        block = {'type': 'table', 'title': t['title'], 'columns': list(t['columns']), 'rows': [list(r) for r in t['rows']],
                 'data': table_data(list(t['columns']), t['rows'], report, where, t.get('roll_column'))}
        if t.get('footnotes'):
            block['footnotes'] = list(t['footnotes'])
        if t.get('groups'):                           # {"before": row, "text"}: a label heading the rows below it
            block['groups'] = [dict(g) for g in t['groups']]
        report.setdefault('hand_tables', []).append({'title': t['title'], 'page': t['page'], 'rows': len(t['rows']),
                                                     'lines': len(run), 'checked': 'letter for letter'})
        report['tables_to_confirm'].append({'entry': where, 'region': 'by hand', 'page': t['page'], 'title': t['title'],
                                            'columns': len(t['columns']), 'rows': len(t['rows'])})
        report['left_out'] += list(t.get('also', []))
        apart = bool(t.get('slug')) and t.get('in_text') is False     # its own entry only: not in the text it follows
        lines = lines[:i] + ([] if apart else [dict(merge_lines(run, block), heading=None)]) + lines[end:]
        if t.get('slug'):
            entries.append((t, block))
    return lines, entries


def text_tables(lines, plans, report):
    """Tables printed without rules, as the plan describes them: the header line (its words, which
    must be the columns' words), then `rows` lines, each split into cells at its widest gaps. The
    lines are replaced by one carrying the table block. A row whose gap is no wider than the gaps
    between its words is not a table row: an error. With "keyed": true the table's last column
    wraps and each row opens with a key (keyed_text_table())."""
    for t in plans:
        where = f'text table {t["header"]!r} on page {t["page"]}'
        i = next((k for k, l in enumerate(lines) if l['page'] == t['page'] and not l.get('block') and
                  norm(plain(l['text'])) == norm(t['header'])), None)
        if i is None:
            report['errors'].append({'error': f'{where}: no such line'})
            continue
        if norm(' '.join(t['columns'])) != norm(t['header']):
            report['errors'].append({'error': f'{where}: the columns {t["columns"]} are not its words'})
            continue
        if t.get('keyed'):
            lines = keyed_text_table(lines, t, i, report, where)
            continue
        run = lines[i:i + 1 + t['rows']]
        rows = []
        for l in run[1:]:
            w = l['words']
            gaps = sorted(w[k + 1][1] - w[k][2] for k in range(len(w) - 1))
            cells = split_row(l, len(t['columns']))
            wide = gaps[-(len(t['columns']) - 1):] if gaps else []
            one_word_cells = len(w) == len(t['columns'])           # every word a cell: no gap to judge
            if (not cells or l['page'] != t['page'] or l['column'] != run[0]['column'] or
                    (not one_word_cells and min(wide or [0]) < 3 * gaps[len(gaps) // 2])):
                report['errors'].append({'error': f'{where}: {l["text"]!r} is not a row of it'})
                rows = None
                break
            rows.append(cells)
        if rows is None:
            continue
        cols = t['columns']
        block = {'type': 'table', 'title': t.get('title', ''), 'columns': cols, 'rows': rows,
                 'data': table_data(cols, rows, report, where, t.get('roll_column'))}
        report['tables_to_confirm'].append({'entry': where, 'region': 'text', 'page': t['page'],
                                            'title': block['title'], 'columns': len(cols), 'rows': len(rows)})
        lines = lines[:i] + [merge_lines(run, block)] + lines[i + len(run):]
    return lines


def column_tables(lines, regions, tables_plan, report):
    """A box whose table has no rules, set in columns ("from_columns": 2): its lines below the
    title, read column by column, are the table's columns, a line to a cell, the first line of each
    being its header. The box becomes a table region and those lines its table lines. Columns of
    different lengths are an error."""
    for bid, t in tables_plan.items():
        if not t.get('from_columns'):
            continue
        body = [l for l in lines if l.get('box') == bid and not l.get('heading') and not l.get('table')]
        cols = {}
        for l in body:
            cols.setdefault(l['column'], []).append(plain(l['text']))
        if bid not in regions or len(cols) != t['from_columns'] or len({len(c) for c in cols.values()}) != 1:
            report['errors'].append({'error': f'box {bid}: not {t["from_columns"]} columns of equal length: '
                                     f'{ {k: len(v) for k, v in cols.items()} }'})
            continue
        grid = list(zip(*cols.values()))
        regions[bid] = dict(regions[bid], kind='table', columns=list(grid[0]), rows=[list(r) for r in grid[1:]])
        for l in body:
            l['table'] = True


def join_continued(regions, plan, report):
    """A table continued in other boxes (the plan's "continued_in") takes their rows. A header
    printed again over the rest is left out: it is said once. Returns the boxes joined on."""
    merged = set()
    for bid, t in plan.get('tables', {}).items():
        for cont in t.get('continued_in', []):
            if cont in regions and regions[cont].get('kind') == 'table' and bid in regions:
                regions[bid]['rows'] = regions[bid]['rows'] + regions[cont]['rows']
                merged.add(cont)
                again = ' '.join(regions[cont].get('columns') or [])
                if again.strip():
                    report['left_out'].append(again)
            else:
                plan.setdefault('_missing', []).append(cont)
    return merged


ROLL_RANGE = re.compile(r'^\d{1,3}\s*[–—-]\s*\d{1,3}$|^\d{1,3}$')
DICE = re.compile(r'^\d*d\d+$', re.I)


def flow_tables(regions, lines, plan, report):
    """A box of roll tables flowed down its columns (the plan's "flowed": [a table's plan, one
    for each, in printed order]): each table is a line in capitals (its title), a header
    opening with the dice ("1d100 Place") and rows that open with a roll ("01–05"); a table
    runs on from the foot of one column to the top of the next, and a row's text may wrap
    above and below its roll. The words are placed by where they are printed, since the
    layout reads such a box as one wide table. The first table keeps the box's id, the others
    take "<box>.2", "<box>.3"; the box's lines above the first title stay its text. The
    titles are left out (the plan's "title" names each table)."""
    for bid, t in list(plan.get('tables', {}).items()):
        specs = t.get('flowed')
        if not specs or bid not in regions:
            continue
        own = [l for l in lines if l.get('box') == bid and l.get('words')]
        words = [(l['baseline'], a, b, w, l) for l in own for w, a, b in l['words']]
        starts = []                                   # the x where each column's rolls begin
        for x in sorted(a for _, a, _, w, _ in words if ROLL_RANGE.match(w) and '–' in w or DICE.match(w)):
            if not starts or x - starts[-1] > 12:
                starts.append(x)
        if not starts:
            report['errors'].append({'error': f'table {bid}: "flowed", but no line opens with a roll'})
            continue
        tables, cur, top, owner = [], None, None, {}  # owner: (column, baseline) -> its table
        for c, x0 in enumerate(starts):
            x1 = starts[c + 1] - 6 if c + 1 < len(starts) else float('inf')
            mine = [w for w in words if x0 - 6 <= w[1] < x1]
            by_line = {}
            for w in mine:
                by_line.setdefault(round(w[0], 1), []).append(w)
            segment = []                              # (baseline, roll or None, text) under one header

            def close():
                rolls = [r for r in segment if r[1]]
                for k, (base, roll, text) in enumerate(rolls):
                    lo = (rolls[k - 1][0] + base) / 2 if k else float('-inf')
                    hi = (rolls[k + 1][0] + base) / 2 if k + 1 < len(rolls) else float('inf')
                    cur['rows'].append([roll, ' '.join(t for b, _, t in segment if lo < b <= hi and t)])
                if segment and not rolls:
                    report['errors'].append({'error': f'table {bid}: text with no roll beside it: '
                                                      f'{" ".join(t for _, _, t in segment)!r}'})
                segment.clear()

            bases = sorted(by_line)
            leads = {b: (min(by_line[b], key=lambda w: w[1])[3] if min(w[1] for w in by_line[b]) < x0 + 6 else '')
                     for b in bases}
            for n, base in enumerate(bases):
                ws = sorted(by_line[base], key=lambda w: w[1])
                lead = leads[base]
                text = ' '.join(w[3] for w in ws)
                # A title: capitals, with the dice header on the next line.
                titled = text.isupper() and n + 1 < len(bases) and bool(DICE.match(leads[bases[n + 1]]))
                if (top is None and not titled) or (top is not None and base < top):
                    continue                          # above the first title: the box's own text
                if titled:
                    if cur:
                        close()
                    cur = {'title': text, 'columns': None, 'rows': []}
                    tables.append(cur)
                    top = base if top is None else top
                    report['left_out'].append(text)
                elif DICE.match(lead):                # the header; printed again where a table runs on
                    close()
                    head = [lead, ' '.join(w[3] for w in ws[1:])]
                    if cur['columns'] is None:
                        cur['columns'] = head
                    else:
                        report['left_out'].append(' '.join(head))
                elif ROLL_RANGE.match(lead):
                    segment.append((base, lead, ' '.join(w[3] for w in ws[1:])))
                else:
                    segment.append((base, None, text))
                owner[(c, base)] = len(tables) - 1
            if cur:
                close()
        if len(tables) != len(specs):
            report['errors'].append({'error': f'table {bid}: "flowed" plans {len(specs)} tables, but the box '
                                              f'holds {len(tables)}: {[x["title"] for x in tables]}'})
            continue
        sids = [bid if k == 0 else f'{bid}.{k + 1}' for k in range(len(tables))]
        for sid, tab, spec in zip(sids, tables, specs):
            if tab['columns'] is None or any(not r[1] for r in tab['rows']):
                report['errors'].append({'error': f'table {sid} ({tab["title"]}): no header, or a roll with no text'})
            regions[sid] = dict(regions[bid], id=sid, kind='table', columns=tab['columns'] or ['', ''], rows=tab['rows'])
            plan['tables'][sid] = dict({x: y for x, y in t.items() if x != 'flowed'} if sid == bid else {}, **spec)
        for l in own:                                 # a line read across the columns: one line in each
            parts = {}
            for w, a, b in l['words']:
                c = max((n for n, x in enumerate(starts) if a >= x - 6), default=0)
                if (c, round(l['baseline'], 1)) in owner:
                    parts.setdefault(c, []).append([w, a, b])
            if parts:
                at = next(n for n, x in enumerate(lines) if x is l)
                lines[at:at + 1] = [
                    {**{k: v for k, v in l.items() if k != 'heading'}, 'words': ws, 'text': ' '.join(w for w, _, _ in ws),
                     'x0': ws[0][1], 'x1': ws[-1][2], 'box': sids[owner[(c, round(l['baseline'], 1))]], 'table': True}
                    for c, ws in sorted(parts.items())]
        report.setdefault('flowed_tables', []).append(
            {'box': bid, 'tables': [{'title': x['title'], 'rows': len(x['rows'])} for x in tables]})


def convert(layout, plan, taken=(), library=None):
    report = {'errors': [], 'questions': [], 'left_out': [], 'tables_to_confirm': [], 'diagrams': [], 'sizes': {}}
    regions = {r['id']: dict(r) for r in layout.get('regions', [])}
    merged = join_continued(regions, plan, report)
    lines = [dict(l) for l in layout['lines'] if not l['furniture']]
    flow_tables(regions, lines, plan, report)
    body = layout.get('body_size', 0)
    orn = [l for l in lines if l['size'] < body and not re.search(r'[^\W_]', l['text']) and
           not re.match(r'^\s*[•●▪]', l['text'])]
    if orn:                                           # flourishes: no letter or digit, below body size
        report['ornaments'] = [{'page': l['page'], 'text': l['text']} for l in orn]
        report['left_out'] += [l['text'] for l in orn]
        lines = [l for l in lines if l not in orn]
    lines = boxes_as_text(lines, plan.get('boxes', {}), report, layout.get('gutters', {}))
    vocab = vocabulary(lines) | {w.lower() for w in plan.get('whole_words', [])}
    for nh in plan.get('not_headings', []):           # large lines that are body text
        hit = [l for l in lines if l['page'] == nh['page'] and l.get('heading') and
               norm(plain(l['text'])) == norm(nh['text'])]
        if not hit:
            report['errors'].append({'error': f'not_headings: no heading {nh["text"]!r} on page {nh["page"]}'})
        for l in hit:
            l['heading'] = None
    for spec in plan['entries']:                      # body-size lines that are subheadings
        for sub in spec.get('subheadings', []):
            hit = [l for l in lines if l['page'] >= spec['page'] and not l.get('heading') and
                   not l.get('box') and norm(plain(l['text'])) == norm(sub)]
            if not hit:
                report['errors'].append({'error': f'{spec["name"]}: no subheading line {sub!r} '
                                         f'from page {spec["page"]}'})
            if hit:
                hit[0]['heading'] = SUBHEADING
    lines, by_hand = hand_tables(lines, plan.get('hand_tables', []), report)
    lines = text_tables(lines, plan.get('text_tables', []), report)
    column_tables(lines, regions, plan.get('tables', {}), report)
    boxes_plan = plan.get('boxes', {})
    tables_plan = plan.get('tables', {})
    for cont in plan.pop('_missing', []):
        report['errors'].append({'error': f'the plan continues a table in {cont}, which was not read as a table'})
    for bid in list(boxes_plan) + list(tables_plan):
        if bid not in regions:
            report['errors'].append({'error': f'the plan names box {bid}, which pdf_layout.py did not find'})

    planned = list(plan['entries'])
    runs = heading_runs(lines)
    intro = plan.get('intro')
    # Walk the lines, cutting entries at planned headings.
    entries = []          # {"spec", "level", "lines": [...], "boxes": [ids]}
    current, pending = None, list(planned)
    seen_boxes = set()
    pending_boxes = []
    split_leads = []      # (box, its lines above its first heading), for boxes split into entries
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.get('box'):
            bid = l['box']
            if bid not in seen_boxes and bid in merged:
                seen_boxes.add(bid)                       # its rows are in the table it continues
            elif bid not in seen_boxes:
                seen_boxes.add(bid)
                bp = boxes_plan.get(bid, {})
                target = ('to', bp['to']) if 'to' in bp else ('auto', current)
                if 'diagram' in bp:
                    report['diagrams'].append({'box': bid, 'page': l['page'], 'note': bp['diagram']})
                    report['left_out'] += [x['text'] for x in lines if x.get('box') == bid]
                elif 'entry' in bp:
                    e = {'spec': dict(bp['entry'], page=l['page']), 'level': None, 'lines': [], 'boxes': [bid],
                         'own_box': True}
                    entries.append(e)
                elif 'entries' in bp:
                    # A box of several short pieces, each under its own heading (adventure hooks):
                    # an entry apiece. Lines above the first heading are the page's own text, set
                    # over the box's edge; they go back where they were printed (below).
                    at = [k for k, x in enumerate(lines) if x.get('box') == bid]
                    box_runs = {}             # heading start -> (text, last index), within the box
                    for k in at:
                        x = lines[k]
                        prev = lines[k - 1] if k - 1 in at else None
                        if not x.get('heading'):
                            continue
                        first = next((f for f, (_, last) in box_runs.items() if last == k - 1), None)
                        if first is not None and prev.get('heading') == x['heading'] and \
                                x['baseline'] - prev['baseline'] < 1.6 * x['size']:
                            box_runs[first] = (box_runs[first][0] + ' ' + plain(x['text']), k)
                        else:
                            box_runs[k] = (plain(x['text']), k)
                    starts = sorted(box_runs)
                    if not starts:
                        report['errors'].append({'error': f'box {bid}: the plan splits it into entries, but it '
                                                          'has no heading'})
                    else:
                        split_leads.append((bid, [lines[k] for k in at if k < starts[0]]))
                        for n, k in enumerate(starts):
                            text, last = box_runs[k]
                            end = starts[n + 1] if n + 1 < len(starts) else at[-1] + 1
                            entries.append({'spec': dict(bp['entries'], name=fix_case(plain(text)), page=lines[k]['page']),
                                            'level': None, 'lines': [lines[m] for m in at if last < m < end],
                                            'boxes': []})
                else:
                    pending_boxes.append((bid, target))
            i += 1
            continue
        start = next((p for p in pending if p.get('starts_at') and p['page'] == l['page'] and
                      norm(plain(l['text'])).startswith(norm(p['starts_at']))), None)
        if start:
            pending.remove(start)
            current = {'spec': start, 'level': 1, 'size': 99, 'lines': [], 'boxes': []}
            entries.append(current)
        elif i in runs:
            text, last = runs[i]
            match = next((p for p in pending if p['page'] == l['page'] and
                          norm(p.get('heading', p['name'])) == norm(text)), None)
            if match:
                pending.remove(match)
                current = {'spec': match, 'level': l['heading'], 'size': l['size'], 'lines': [], 'boxes': []}
                entries.append(current)
                i = last + 1
                continue
            if current is not None and l['size'] >= current['size']:
                report['errors'].append({'error': f'heading {text!r} on page {l["page"]} is at the level of '
                                         f'{current["spec"]["name"]!r} but the plan doesn\'t place it'})
        if current is None and i in runs and l['heading'] == 1:
            # The chapter's title, over one line or two: left out whole, before the intro starts.
            last = runs[i][1]
            report['left_out'] += [x['text'] for x in lines[i:last + 1]]
            i = last + 1
            continue
        if current is None and intro:
            current = {'spec': dict(intro, page=l['page']), 'level': 1, 'size': 99, 'lines': [], 'boxes': []}
            entries.append(current)
        if current is None:
            report['left_out'].append(l['text'])
        else:
            current['lines'].append(l)
        i += 1
    for p in pending:
        what = f'line starting {p["starts_at"]!r}' if p.get('starts_at') else f'heading {p["name"]!r}'
        report['errors'].append({'error': f'no {what} on page {p["page"]}'})

    # A box goes to the entry whose text runs just above it on its page, in the columns it spans;
    # with no text above it there, to the entry running into the page. The plan's "to" overrides.
    owner = {id(x): e for e in entries for x in e['lines']}
    report['box_placement'] = []
    expanded = []
    for bid, target in pending_boxes:          # "to" can name several entries: one copy in each
        if target[0] == 'to' and isinstance(target[1], list):
            expanded += [(bid, ('to', name)) for name in target[1]]
        else:
            expanded.append((bid, target))
    for bid, lead in split_leads:
        if not lead:
            continue
        region = regions.get(bid, {})
        x0, top, x1, _ = region.get('bbox', (0, 0, 0, 0))
        above = [x for x in lines if not x.get('box') and id(x) in owner and x['page'] == region.get('page') and
                 x['baseline'] < top and x['x1'] > x0 and x['x0'] < x1]
        if not above:
            report['errors'].append({'error': f'box {bid}: lines above its first heading, but no text above the '
                                              f'box to return them to: {[x["text"] for x in lead]}'})
            continue
        last = max(above, key=lambda x: x['baseline'])
        home = owner[id(last)]['lines']
        k = next(n for n, x in enumerate(home) if x is last)
        # They carry on the line above the box: same column, no box, so they join its paragraph.
        home[k + 1:k + 1] = [dict(x, box=None, column=last['column']) for x in lead]
        report.setdefault('returned_to_text', []).append({'box': bid, 'entry': owner[id(last)]['spec']['name'],
                                                          'text': ' '.join(x['text'] for x in lead)})
    for bid, target in expanded:
        if target[0] == 'to':
            name = target[1]
            target = next((e for e in entries if norm(e['spec']['name']) == norm(name)), None)
            if target is None:
                # An entry made from a heading of a "split_headings" entry: the box goes with it.
                target = next((e for e in entries if e['spec'].get('split_headings') and any(
                    x.get('heading') and norm(fix_case(plain(x['text']))) == norm(name) for x in e['lines'])), None)
                if target is not None:
                    target.setdefault('box_sub', {})[bid] = name
            if target is None:
                report['errors'].append({'error': f'box {bid}: the plan sends it to {name!r}, an entry '
                                         'that does not exist'})
                continue
        elif isinstance(target, tuple):
            region = regions.get(bid, {})
            x0, top, x1, _ = region.get('bbox', (0, 0, 0, 0))
            page = region.get('page')
            body = [x for x in lines if not x.get('box') and id(x) in owner]
            above = [x for x in body if x['page'] == page and x['baseline'] < top and x['x1'] > x0 and x['x0'] < x1]
            if above:
                target = owner[id(max(above, key=lambda x: x['baseline']))]
            else:
                before = [x for x in body if x['page'] < page]
                target = owner[id(before[-1])] if before else target[1]
        if target is None:
            report['left_out'] += [x['text'] for x in lines if x.get('box') == bid]
            report['questions'].append({'entry': None, 'kind': 'box-before-first-entry',
                                        'text': f'box {bid} left out'})
            continue
        target['boxes'].append(bid)
        title = box_parts([x for x in lines if x.get('box') == bid])[0]
        report['box_placement'].append({'box': bid, 'title': title, 'entry': target['spec']['name']})

    out, records = [], []
    used_slugs = set()
    found_items, describers = [], []
    for e in entries:
        spec = e['spec']
        name = spec['name']
        career = read_career(e, entries, lines, layout, plan, report) if spec.get('career') else None
        updates = None
        if spec.get('level_updates'):
            e['lines'], updates = level_updates(e['lines'], report, name)
        content = blocks_from_lines(e['lines'], report, name, vocab, e['level'],
                                    list(spec.get('field_labels') or (spec.get('split_headings') or {}).get('field_labels', ())) +
                                    list(spec.get('text_labels') or (spec.get('split_headings') or {}).get('text_labels', ())))
        # Subheadings take consecutive levels below the entry's own, whatever sizes the book used.
        ranks = sorted({b['level'] for b in content if b['type'] == 'heading'})
        for b in content:
            if b['type'] == 'heading':
                b['level'] = (e['level'] or 1) + 1 + ranks.index(b['level'])
        box_profiles = []
        for bid in e['boxes']:
            bl = [x for x in lines if x.get('box') == bid]
            if boxes_plan.get(bid, {}).get('profile'):
                # A stat block in a box of its own: the entry's fields when the entry is the
                # creature (stat_blocks), a profile block in its text otherwise. What the box
                # prints after the profile is read as the entry's prose.
                prof, after = creatures.box_profile(bl, report, name)
                if prof:
                    box_profiles.append(prof)
                    if not spec.get('stat_blocks'):
                        content.append(creatures.profile_block(prof))
                    content += blocks_from_lines(after, report, name, vocab) if after else []
                    continue
            title, body, tlines = box_parts(bl)
            region = regions.get(bid, {})
            inner = blocks_from_lines(body, report, name, vocab, None,
                                      spec.get('field_labels', ()) if e.get('own_box') else ())
            plan_t = tables_plan.get(bid) or {}
            if region.get('kind') == 'table' and plan_t.get('items'):
                # A price table: one trapping per row; its footnotes go to the items they mark.
                where = f'{name}: table {bid}'
                cols, rows, _, _, _ = table_cells(region, title, plan_t, report, where)
                report['left_out'].append(' '.join(region.get('columns') or []))  # the header: field names
                if norm(' '.join(cols)) != norm(' '.join(region.get('columns') or [])):
                    report['left_out'].append(' '.join(cols))      # ...when the plan found it a row down
                notes, rest = items.footnotes(body)
                inner = blocks_from_lines(rest, report, name, vocab) if rest else []
                for it in items.item_rows(cols, rows, plan_t['items'], notes, report, where):
                    found_items.append(dict(it, region=bid, page=region['page'], section=name))
                if not inner:
                    if title:
                        report['left_out'].append(title)      # the price table's title
                    continue
            elif region.get('kind') == 'table':
                first, second = unstack(region, plan_t, report, name)
                inner.append(table_block(first, title, plan_t, report, name))
                if second:
                    inner.append(table_block(second, plan_t['stacked']['title'], plan_t['stacked'], report, name))
            if e.get('own_box'):
                if title and norm(title) != norm(name):
                    inner.insert(0, {'type': 'heading', 'level': 2, 'text': title})
                elif title:
                    report['left_out'].append(title)      # the entry's own name, as its heading
                content += inner
            else:
                content.append(dict({'type': 'sidebar', 'title': title, 'content': inner},
                                    **({'_sub': e['box_sub'][bid]} if bid in e.get('box_sub', {}) else {})))
        if spec.get('headings_as_rows'):
            content = headings_to_rows(content, spec['headings_as_rows'], report, name, spec.get('row_bands', ()))
        split = []
        if spec.get('split_headings'):
            content, split = split_at_headings(content, e['lines'], spec, report, name)
        if spec.get('split_labels'):
            content, more = split_at_labels(content, e['lines'], spec, report, name)
            split += more
        if spec.get('stat_blocks') and not spec.get('category'):
            report['errors'].append({'error': f'{name}: stat_blocks needs a category (creatures)'})
        if spec.get('describes_items'):
            describers.append((name, content))
        cat = 'careers' if career else spec.get('category', 'rules')
        fields = {'kind': spec.get('kind', 'procedure')} if cat == 'rules' else \
            ({'kind': spec['kind']} if spec.get('kind') else {})
        fields.update(spec.get('fields', {}))      # index fields the book states in its prose
        if updates:
            fields['level_updates'] = updates
        if career:
            # The species line opens the entry; the levels follow its description, before any
            # sections and sidebars printed after them.
            species_block, levels_block, fields = career
            at = next((k for k, b in enumerate(content) if b['type'] in ('heading', 'sidebar')), len(content))
            content = ([species_block] if species_block else []) + content[:at] + \
                ([levels_block] if levels_block else []) + content[at:]
        if spec.get('stat_blocks') and box_profiles:
            fields.update(creatures.profile_fields(box_profiles, name, report))
        elif spec.get('stat_blocks'):
            content, prof = creatures.stat_blocks(content, report, name)
            fields.update(prof)
        content = read_labelled(content, spec.get('field_labels', ()), fields, report, name,
                                spec.get('text_labels', ()))
        slug = free_slug(spec.get('slug') or slugify(name), cat, name, plan, taken, used_slugs, report)
        entry = {'slug': slug, 'name': name, 'source': plan['source'], 'chapter': plan['chapter'],
                 'section': spec.get('heading', name), 'page': spec['page'], 'level': e['level'] or 1,
                 'fields': fields, 'content': content}
        if cat == 'rules':
            entry['kind'] = spec.get('kind', 'procedure')
        if spec.get('aliases'):
            entry['aliases'] = spec['aliases']
        if spec.get('audience'):
            entry['audience'] = spec['audience']
        if spec.get('heading') and norm(spec['heading']) != norm(name):
            report['left_out'].append(spec['heading'])     # printed as the heading of the entry it names
        rel = plan.get('relations', {}).get(f'{cat}/{slug}') or plan.get('relations', {}).get(slug)
        if rel:
            entry['relations'] = rel
        out.append((cat, entry))
        rec = {'slug': slug, 'name': name, 'source': plan['source'], 'chapter': plan['chapter'],
               'section': entry['section'], 'page': spec['page'], '_category': cat}
        # (the index holds what a search filters on: a career's advances and an NPC's skills,
        # talents, spells and trappings stay in the entry)
        unlisted = (('advances',) if career else ()) + \
            (('skills', 'talents', 'spells', 'trappings', 'marks', 'special') if cat == 'creatures' else ())
        rec.update({k: v for k, v in fields.items() if k not in unlisted})
        if spec.get('aliases'):
            rec['aliases'] = spec['aliases']
        if spec.get('audience'):
            rec['audience'] = spec['audience']
        if rel:
            rec['relations'] = rel
        records.append(rec)
        same = report.get('same_name', [])
        if same and 'relation' not in same[-1] and same[-1]['name'] == name and same[-1]['category'] == cat:
            relate_same_name(cat, entry, rec, plan, library, report)
        for sub in split:
            add_entry(dict(sub, _report=report, _library=library), out, records, plan, taken, used_slugs)

    describe_items(found_items, describers, plan, report)
    for it in found_items:
        add_entry({'name': it['name'], 'category': 'trappings', 'page': it['page'], 'section': it['section'],
                   'slug': plan.get('item_slugs', {}).get(f'{it["region"]}/{it["name"]}'),
                   'fields': it['fields'], 'content': it.get('content', []), '_report': report,
                   '_library': library},
                  out, records, plan, taken, used_slugs)
    if found_items:
        report['items'] = len(found_items)

    for bid, t in tables_plan.items():
        if not t.get('slug'):
            continue
        region = regions.get(bid)
        if not region or region.get('kind') != 'table':
            report['errors'].append({'error': f'the plan lists {bid} as a table, but it was not read as one'})
            continue
        if isinstance(taken, dict) and t['slug'] in taken.get('tables', ()):
            report['errors'].append({'error': f'table {bid}: another source\'s table has the slug {t["slug"]!r}'})
        title = box_parts([x for x in lines if x.get('box') == bid])[0]
        block = table_block(region, title, t, {'tables_to_confirm': []}, t['title'])   # reported with its entry
        host = next((n for n, en in ((en['name'], en) for _, en in out) if any(
            b.get('type') == 'sidebar' and b['content'] and b['content'][-1] is not None and
            b['content'][-1].get('type') == 'table' and b['content'][-1]['title'] == block['title']
            for b in en['content'])), None)
        entry = {'slug': t['slug'], 'name': t['title'], 'source': plan['source'], 'chapter': plan['chapter'],
                 'section': host or t['title'], 'page': region['page'], 'level': 1,
                 'fields': {'about': t.get('about', ''), 'roll': t.get('roll')}, 'content': [block]}
        rec = {'slug': t['slug'], 'name': t['title'], 'source': plan['source'], 'chapter': plan['chapter'],
               'section': entry['section'], 'page': region['page'], 'about': t.get('about', ''),
               'roll': t.get('roll'), '_category': 'tables'}
        rel = t.get('relations') or plan.get('relations', {}).get(f'tables/{t["slug"]}')
        if rel:
            entry['relations'] = rec['relations'] = rel
        out.append(('tables', entry))
        records.append(rec)
    for t, block in by_hand:
        if isinstance(taken, dict) and t['slug'] in taken.get('tables', ()):
            report['errors'].append({'error': f'hand table {t["title"]!r}: another source\'s table has the slug {t["slug"]!r}'})
        host = next((en['name'] for _, en in out if any(b is block or (b.get('type') == 'sidebar' and block in b['content'])
                                                        for b in en['content'])), None)
        fields = {'about': t.get('about', ''), 'roll': t.get('roll')}
        entry = {'slug': t['slug'], 'name': t['title'], 'source': plan['source'], 'chapter': plan['chapter'],
                 'section': host or t['title'], 'page': t['page'], 'level': 1, 'fields': fields, 'content': [block]}
        rec = {'slug': t['slug'], 'name': t['title'], 'source': plan['source'], 'chapter': plan['chapter'],
               'section': entry['section'], 'page': t['page'], 'about': fields['about'], 'roll': fields['roll'],
               '_category': 'tables'}
        rel = t.get('relations') or plan.get('relations', {}).get(f'tables/{t["slug"]}')
        if rel:
            entry['relations'] = rec['relations'] = rel
        out.append(('tables', entry))
        records.append(rec)
    return out, records, report


def read_taken(args, source):
    """--taken CATEGORY=_index.json ... -> {category: the slugs other sources' entries hold}, and
    under OWN the chapter of each slug this source holds already."""
    taken = {OWN: {}}
    for t in args:
        cat, _, path = t.partition('=')
        with open(path, encoding='utf-8') as f:
            recs = json.load(f)
        taken.setdefault(cat, set()).update(r['slug'] for r in recs if r.get('source') != source)
        taken[OWN].setdefault(cat, {}).update({r['slug']: r.get('chapter') for r in recs if r.get('source') == source})
    return taken


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('layout')
    ap.add_argument('--plan', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--taken', action='append', default=[],
                    help='CATEGORY=_index.json of entries already in the library (repeatable)')
    ap.add_argument('--library-data', help="the library's library-data folder (its local copy): an entry "
                    "that takes another source's entry's name is compared with it there")
    a = ap.parse_args(argv)
    with open(a.layout, encoding='utf-8') as f:
        layout = json.load(f)
    with open(a.plan, encoding='utf-8') as f:
        plan = json.load(f)
    entries, records, report = convert(layout, plan, read_taken(a.taken, plan['source']), a.library_data)
    return write_outputs(entries, records, report, a.out)


def write_outputs(entries, records, report, out):
    """Write each entry's .json and .md (rules entries by slug, others as <category>--<slug>),
    `_records.json` and `_report.json`; print the counts. Returns the exit status."""
    os.makedirs(out, exist_ok=True)
    for cat, e in entries:
        for ext, text in (('json', json.dumps(e, ensure_ascii=False, indent=1) + '\n'), ('md', render(e))):
            name = f'{e["slug"]}.{ext}' if cat == 'rules' else f'{cat}--{e["slug"]}.{ext}'
            with open(os.path.join(out, name), 'w', encoding='utf-8') as f:
                f.write(text)
            report['sizes'][name] = len(text.encode('utf-8'))
    with open(os.path.join(out, '_records.json'), 'w', encoding='utf-8') as f:
        f.write('[\n' + ',\n'.join(json.dumps(r, ensure_ascii=False) for r in records) + '\n]\n')
    with open(os.path.join(out, '_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
        f.write('\n')
    counts = ', '.join(f'{sum(1 for c, _ in entries if c == k)} {k}' for k in sorted({c for c, _ in entries}))
    print(f'{counts}; {len(report["errors"])} errors, {len(report["questions"])} questions, '
          f'{len(report["tables_to_confirm"])} tables to confirm -> {out}', file=sys.stderr)
    return 1 if report['errors'] else 0

if __name__ == '__main__':
    sys.exit(main())
