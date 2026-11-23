---
name: wfrp-import
description: Import Warhammer Fantasy Roleplay game material (careers, species, skills, talents, spells, trappings, creatures, rules, tables, lore) from a source into the private Google Drive library — a rulebook or supplement PDF, an adventure, a Google Doc or homebrew document, or pasted text. Use when the user asks to add a source, import a chapter, check what's been imported, or re-import after errata; or when another WFRP skill reports missing entries.
---

# Import

Read `references/library-layout.md` first, especially §3 (sources), §4
(entries), and §6 (importing). Follow its formats exactly: the other skills
depend on them.

**Before any import work, check for an unfinished import.** A session can stop
partway (a usage limit, a closed laptop) and resume with no memory of what it
did. Run `python3 scripts/import_journal.py show` (it finds the journal itself;
keep scratch in `scratch/` under the working directory). If the repo's hook is
set up (`.claude/settings.json`), the journal is already in front of you. If an
import is open, finish it before starting anything new (§6 below). Do this
before replying to every message while an import is open.

## 1. Work out what's being imported

- **Which source?** Match the user's words to a `code` or `title` in
  `library.json` → `sources`, or in the active campaign's `campaign_sources`.
  If it's new, go to **Add a source** first.
- **Library or campaign?** Library sources are imported by the Librarian.
  Campaign sources (adventures, the GM's homebrew) are imported by that
  campaign's GM, into the campaign's `library-data/`, or `gm/library-data/` for
  GM-only material. If there's no edit access to the target folder, stop and
  say who can import it.
- **Which chapter?** One chapter per run, from the source's chapter list.
- **Already imported?** If the chapter's status is `imported` or `problems`,
  confirm this is a re-import (errata or a better extraction) and ask why, for
  the log.

## 2. Add a source

1. Agree on a `code` (layout §3: unique across the library and all campaign
   sources; homebrew as `HB-<NAME>`), the title and the edition (`4e` unless
   the book says otherwise).
2. For a PDF, put it (or check it's) in `sources/<code>/` in the library and
   read the chapter list from its bookmarks:

   ```
   python3 scripts/pdf_outline.py "<local folder>/sources/CRB/<file>.pdf" --depth 2 --out scratch/chapters.json
   ```

   It reports the page offset (printed page 1's PDF page) from the PDF's page
   labels; if it can't, find printed page 1 in the PDF and pass
   `--page-offset`. Show the list beside the book's contents page, drop
   bookmarks that aren't chapters (cover, credits, index, adverts), and fix
   titles to match the contents. Record `page_offset` on the source.
   A Google Doc, file or pasted source: its top-level headings, or a single
   `all` chapter if it's short.
3. Every chapter starts as `not-imported`. Write the source to `library.json`
   (library sources) or `campaign.json` → `campaign_sources` (campaign
   sources). For a campaign source, also add its code to the front of the
   campaign's `sources`, unless the GM says otherwise.
4. Show the chapter list and suggest where to start. For a new library, the
   Rulebook's chapters on species, careers, skills and talents, and rules come
   first: the character skill needs them.

## 3. Read the chapter

### PDF (`kind: pdf`)

PDFs import only where the whole file is on disk (layout §6, docs/adr/0001):
Claude Code with the library's local folder, or a cloud session linked to the
Librarian's computer with the folder connected (copy the PDF into scratch with
the device tools). If neither is available, say so and stop. Never copy the
PDF or anything read from it into the repo.

1. Read the chapter's pages by layout into scratch:

   ```
   python3 scripts/pdf_layout.py BOOK.pdf --pages 30-109 --page-offset 2 --out scratch/ch3-layout.json
   python3 scripts/pdf_layout.py BOOK.pdf --pages 87 --page-offset 2 --text    # look at a page
   ```

   It orders each page's lines by column, marks page furniture (running heads,
   page numbers) and gives heading levels from type size. A boxed panel's lines
   in the foot margin are content, not furniture, and so is a column's last line
   when it dips into that margin. `check_coverage.py` prints every line set aside
   as `page furniture`: read them each time, because a body line there is a fault
   to fix, not a line to leave out. A handout set to the edges of its page puts
   its title and last line in the margins: name those lines with `--margin-lines`. If it reports pages
   with no text layer, look at the page images and ask before running OCR.
2. Check it's the chapter it should be: its first heading matches the chapter
   list. If not, say so and stop.
3. Look at a few pages with `--text` and at the page images where the layout is
   unusual (career pages, stat lines, tables). Write the chapter's **plan**:
   which heading level starts an entry, which sections hold which category,
   what's left out (art credits, flavour quotes the Librarian doesn't want),
   and every same-name decision (below). Keep it in Drive beside the source
   (`sources/<code>/plans/<chapter>.json`), never in the repo.

   **Which headings are entries** is settled with the Librarian as plain
   questions, not by listing every heading. Run `heading_levels.py
   scratch/ch3-layout.json`: it shows each heading size (level 1 is the
   largest) with how many headings it has and a few examples. Ask which sizes
   start an entry ("the big ones like *Dread* and *Wick Rot*, or the smaller
   ones like *Tools of Trimming* too?"), then run it again with `--levels 2,3`
   and show the numbered list of headings that would become entries. Ask which
   of them aren't entries of their own (they stay sections of the entry
   before), and whether any entry is missing from the list. Write the answers
   as the plan's `"entry_levels": [2, 3]`, `"not_entries": [{"text": "Tools of
   Trimming", "page": 1}]` (a bare string matches the heading on any page),
   and an `entries` line only for an entry that needs more than its name and
   page: another kind or category than the `defaults`, aliases, fields, a
   heading printed with more than the name, or one printed at another size.
   The converter makes the rest from their headings, in page order, and lists
   them in the report's `entries_from_levels`. A heading at an entry level that
   is in neither list is still an error, so nothing is placed by accident.
   `plan_levels.py PLAN LAYOUT --write` rewrites an older plan that lists every
   entry this way, only where the output of the converter that reads it stays exactly the same; a
   plan with open errors (an unplaced heading) or with entries that split their
   headings into entries of their own stays as it is.
4. Convert with the converter for that kind of chapter, then check coverage:

   ```
   python3 scripts/convert_<kind>.py scratch/ch3-layout.json --plan PLAN.json \
       --out scratch/out-ch3 --taken careers=<careers/_index.json> ...
   python3 scripts/check_coverage.py scratch/ch3-layout.json scratch/out-ch3
   ```

   Read only the pages the converter handles into the layout you check
   coverage against: a chapter's career pages, say, and not its pages of rules
   prose, which another converter imports.

   Converters so far:

   | Kind | Script | Plan says |
   |---|---|---|
   | Careers (one per page: advance scheme, career path) | `convert_careers.py` | each career's name, page and class; the level icons (a glyph font, or a drawn shape's point count, from `pdf_layout.py`'s `marks` and `shapes`); the scheme's header labels. Run `pdf_layout.py` with the plan's `--icon-fonts`. |
   | Rules prose (sections, conditions, psychology, symptoms; diseases with their labelled fields; boxed sidebars and ruled tables) | `convert_rules.py` | the entries in order, by name and page (and `heading` when the book prints more than the name), their `kind`, or another `category` (with its `kind`) and `field_labels`; an `intro` entry for text before the first; `starts_at` for an entry with no heading of its own (a letter: the start of its first line), `subheadings` for body-size lines that head its sections, `not_headings` for large lines that are body text (a signature, a pull quote), `headings_as_rows` to make an entry's headings and their text one table (a timeline's dates and events), `audience: gm` for an entry only the GM should see, `career: {class}` for a career printed inside the chapter (its species line and the box with its advance scheme and career path are read as `convert_careers.py` reads them, with the plan's `level_icons` and `scheme_columns`; its other text stays prose; a career that prints no species line names its `species`, and one whose levels print no status, trappings or earning skill is `bare`, as a familiar's), `fields` for index fields the book states in prose (a skill's characteristic), `split_headings` ({category, kind, dividers, name_flags}) to make an entry's subheadings entries of their own (a list of qualities; `name_flags: {"rated": "Rating"}` flags traits that take a rating; its `field_labels` read each new entry's labelled lines as fields (a potion's "Onset Time"), its `text_labels` keep a labelled paragraph as prose after them (a cursed item's "Description"), its `audience` marks them all; a box's `to` can name one of the new entries), `stat_blocks` to read a creature's profile (characteristics row, Traits, Optional) into its fields, and `describes_items` to move bold-labelled descriptions ("**Coat:** ...") to the trappings they name; a table plan's `items` ({kind, fields}) makes a price table one trapping per row (group rows, (2H), footnote marks), `split_column` splits a cell holding two columns, and the plan's `rename` ({"<table>/<group>/<name>": name}) tells same-named items apart; boxes to send elsewhere (`to`), make entries (`entry`; `entries` for a box of several pieces under their own headings, such as adventure hooks: check the report's `returned_to_text`), read as a stat block (`profile`: an NPC's or creature's box gives its `stat_blocks` entry `characteristics`, `title`, `traits`, `skills`, `talents`, `spells`, `trappings`, `marks` and `special`; in another entry it becomes a profile block), read as the page's own `text` (a tinted backdrop taken for a box), or leave out as `diagram`s; tables to write to `tables/` too, with title, `about`, `roll_column`, `columns`, `banner`/`banner_rows`/`header_row` fixes (a title or a label over some columns, read as the header or as the first rows), `row_groups` ([[label, rows], ...]) when the first column labels groups of rows and prints each label once beside its group, `fold` (with `fold_join` for side-by-side parts sharing a key column) and the boxes they're `continued_in`; `text_tables` for tables printed without rules (the header line, its `columns`, and how many `rows`). Run `pdf_layout.py` with `--boxes`, and `--icon-text` for icons printed in the text; check its `drop_capitals` and the report's `ornaments`. Pass `--taken CATEGORY=_index.json` for every category the chapter writes to: a slug another source holds in that category gets the source's code after it and is listed under `same_name`; give each one a relation in the plan. A slug another chapter of the same source holds is an error: give the entry a `slug`. A word the report leaves wrongly hyphenated at a line end goes in the plan's `whole_words`. Notes printed at an angle (handwriting on pinned scraps) are read level, scrap by scrap in the order they start down the page (`tilt`, `scrap` on their lines), each scrap its own paragraphs: check their order against the page, and list larger handwriting under `not_headings`. |
   | Skills and talents ("Name (Char) basic" headings; talents with Max and Tests lines) | `convert_skills_talents.py` | a `convert_rules.py` plan for the chapter's rules sections, boxes and tables, plus the `skills` and `talents` page ranges and their `section`. The skills and talents themselves are found by their headings, not listed; a heading at their level that doesn't read as one is an error. Check the report's `field_lines_joined` and `labels_as_printed`. Run `pdf_layout.py` with `--boxes`. |

   | Spells and prayers (lists of spells, blessings or miracles, each with CN, Range, Target and Duration lines) | `convert_spells.py` | a `convert_rules.py` plan for the chapter's rules sections, boxes and tables, plus its `lists`: each list's heading, page, `kind` (petty, arcane, lore, blessing, miracle, ritual) and `lore` (a lore's or a god's name), `not_spells` for plain subheadings printed at the spells' size, `audience` to mark all its spells (a nemesis's own), and `"entry": false` for a list heading that holds no text of its own. A spell printed outside any list (in a box of its own) is an entry of the plan with category `spells`, its `kind` and its `field_labels`. The spells are found by their headings and field lines, not listed; a heading at their level without field lines is an error, and so is a spell without Range, Target or Duration (or CN, for petty, arcane and lore spells). A ritual's fields (CN, Type, Learning XP, Ingredients, Conditions, Sacrifices, Consequences) are read as a block, up to the blank line before its description; a missing one, or another bold label among them, is an error. Pass `--taken CATEGORY=_index.json` for each category and `--library-data` (the library's local `library-data` folder): a spell or section with the name of another source's is given the source's code and related to it by comparing their text (the same words: `reprint-of`; any difference: `replaces`), unless the plan gives the relation; check the report's `same_name`. Check the report's `field_lines_joined`, `labels_as_printed` and `labels_not_bold`. Run `pdf_layout.py` with `--boxes`. |

   `convert_rules.py`, `convert_skills_talents.py` and `convert_spells.py` name the files for other
   categories `<category>--<slug>`
   (`tables--outcomes.json`): write those to that category's folder without
   the prefix. Before writing, read its report's `box_placement` (which entry
   each sidebar went to) and fix any that read wrong with the plan's `to`.

   **If there's no converter for this kind of chapter yet** and it has more
   than about ten entries, stop and build one first (see Rules): a script
   that reads the layout JSON and a plan and writes each entry's `.json` and
   `.md` (`render_entry.py`), `_records.json` (index records) and
   `_report.json` (errors, left-out text, questions), with tests on an invented
   PDF in `tests/`, in its own pull request. The kinds the Rulebook still needs:
   species, spells and prayers, trappings (weapon and armour tables with qualities), creatures
   (characteristic lines and traits), and chapters of rules prose.
5. The report must have no errors, and `check_coverage.py` must account for
   every word: in an entry, or on the report's `left_out` list. Look at
   anything it reports missing.
   Then `check_names.py <library-data> <out>/_records.json` must find a
   relation (layout §4) on every new entry that shares a name with another,
   in any category; propose the role in the plan's `relations`, and the
   Librarian confirms.
6. The rules converter's report lists **`proposed_fields`** and
   **`proposed_relations`**: what the entries' own text states that the plan
   doesn't give (`scripts/detectors.py`). Examples: a condition that says it
   doesn't stack, a skill's characteristic and type from its bold lead line, a
   specialisation's base skill, an entry made from a box adding to the entry it
   is printed in, a rule named after a career ("Dwarf Engineer") adding to it.
   The box proposals are suggestions: the entry a box sits in isn't always the
   one it belongs to (a Wind's rule printed in its Order's section), so look at
   each. Show each to the Librarian with the sentence it
   comes from (`says`). Set the confirmed ones with the `set_with` command
   (`edit_entry.py ... --plan`), so the entry and the plan both carry them. A
   proposal with `plan` disagrees with what the plan already says: look at both.
   Run the converter with `--library-data` so specialisations find their base
   skill. A field the text states but no detector reads yet is worth a new
   detector (with tests on invented text) rather than a plan note:
   `plan_survey.py` shows which.

When a table or stat line can't be read from the text (drawn as art, or its
cells out of order), transcribe it from the page image, keeping every word,
show the Librarian, and say so in the chapter's notes.

### Google Doc, file, or pasted text

Read it through the connector, or from the conversation for `pasted`. For a
pasted source, also save the text as a file in the right `sources/` folder, so
it can be re-imported later.

### Homebrew document (layout §3)

The group's own homebrew is written in its homebrew document
(docs/adr/0003). When someone wants a homebrew career, talent, spell or item
added or changed:

1. Draft the entry with them in the books' style. Ask about every gap a ruling
   would otherwise fill and write the answer into the text, so the entry needs
   no ruling at the table.
2. Write the change into the document and save it.
3. Import the chapter like any other source.

## 4. Build entries

**Entries that share a name.** When an entry shares its name with one already
in the library or in the same chapter (pass every category's `_index.json`
with `--taken`), the two are related (layout §4). An entry that takes another
source's entry's name in the same category is by default a **version** of it
(`version-of`): the same thing as this source prints it, which each campaign's
source order chooses between. The converter writes that itself, or `reprint-of`
when `--library-data` shows the two are word for word the same, and lists each
under `same_name` for you to check. The plan's `relations` state only the
exceptions: `adds-to`, `distinct-from`, `updated-by`, and a `version-of` between
entries whose names or categories differ. Read both entries before writing one,
and ask the Librarian whenever it isn't certain.

A slug's suffix (`dagger-hepg`) keeps files apart and nothing more: nobody
using the library sees it. That is enough when the two entries are read
together (`adds-to`, `version-of`, `reprint-of`). When they are different things
in one category (`distinct-from`: an elf-made dagger with its own price beside
the Rulebook's), change the **name** in the plan (`rename` for a price table's
items, the entry's `name` otherwise) so people can tell them apart; the slug
follows. The converter refuses `distinct-from` between two entries of one name
in one category.

**Rules that change another entry.** A relation isn't only for shared names.
When a section changes how something elsewhere in the library works, give it
`adds-to` that entry, whatever either is called: a sidebar that lets Elves
take a talent more than once adds to the talent; a supplement's rewrite of
that sidebar is a version of it and adds to the talent too. A lookup of the talent
then brings them up, and the character builder points at them. Without the
relation they are only found by someone who already knows to look.

A talent, skill, trait or spell printed inside a rules section ("New Talent:",
"Skill:", "New Trait:" headings) is an entry of its own in its category, not
part of the section. So is a new specialisation that has rules of its own (a
new kind of *Trained*, a Channelling skill for one lore): name it as printed,
with the brackets, and give it `adds-to` the entry for its group.

**Formulas.** What a rule does to a character's number, and later what it
requires or limits, is written once on its entry for the character builder to
evaluate (ADR 0005). The entry in the library is their only home: never put
them in a plan (the converters refuse one that has `formulas`). Set them with
`set_formulas.py` on the entry's file in the local copy of the library, which
rewrites its `.md` too, then upload both and check their sizes:

```
python3 scripts/set_formulas.py <library-data>/talents/<slug>.json --effects '[{"on": "WP", "add": 5, "at": 1}]'
python3 scripts/set_formulas.py <library-data>/tables/<slug>.json --row "<a cell of the row>" --effects '[...]'
python3 scripts/set_formulas.py <entry>.json --show        # its formulas and its numbered blocks
```

`at` is the number (from 0) of the block that says so; a table's row is named
by the whole text of one of its cells and needs no `at`, and the table may be in
a sidebar. A rule for Elders (ADR 0008) also takes `--lived-through '{"table":
"<title>", "column": "<the column naming each Time>"}'`, a grant `"from":
"elder-career"`, and for each Time's row `--row-fields '{"careers": 1,
"psychology": [...], "burdens": [{"text": "...", "only_earliest": true}]}'`
beside its `--effects` (which may `set` a value, or change `extra_points`); give
the entry `adds-to` a creation rule with `edit_entry.py` so the builder reads it. On every re-import,
pass the converter `--formulas-from <library-data>`: it copies each entry's
formulas from the entry it replaces, and lists as questions any that no longer
fit, to be written again. Never write a formula unasked or in bulk: propose it
beside its sentence when a rule is first applied to a character, and set it
once the Librarian confirms. The text stays the authority; a formula is a
reading of it, and one that is lost is simply written again.

A plan's `defaults` (`{"kind": "condition"}`, `{"category": "lore", "kind":
"other"}`) give every entry it lists the kind or category it doesn't name, so
write a chapter's common kind once, not on each line. Any key but an entry's
identity (name, page, heading, slug, aliases, starts_at) can be a default,
including an instruction every entry takes (`"stat_blocks": true`); an entry
that doesn't take it says `false`. `plan_defaults.py PLAN
--write` rewrites an existing plan that way, only where every entry still
means the same.

To see what the plans tell the converters that they could find for themselves,
run `scripts/plan_survey.py --library <root>`. It sorts every plan item into
facts (fields, relations, who an entry is for), the map (which headings are
entries, kinds, tables, names) and layout (one printing's quirks), and counts
what a signal in the entry's own text or a chapter-wide default already
accounts for: the to-do list for detectors. Its report names entries, so it
stays out of the repo.

To correct an entry's fields or relations after an import (a skill's
characteristic the converter missed, an `adds-to` the plan lacked), use
`scripts/edit_entry.py --library <root> <category>/<slug> --set FIELD=VALUE
--relation ROLE:TARGET --plan sources/<SRC>/plans/<chapter>.json`. It rewrites
the `.json`, renders the `.md` again, changes only that entry's line in
`_index.json`, and gives the plan the same fields and relations in its own
layout, so a re-import keeps them. Upload the files it lists. Formulas and
summaries go through `set_formulas.py` instead.

A **summary** (`--summary "..."`) is one line in your own words of what an
entry does, printed under a spell on the character sheet. The same rules
apply: on the entry only, carried over on re-import, written when a character
first takes the spell and shown to the Librarian, never the book's sentences.
Name a bonus in full ("Willpower Bonus yards") so the sheet prints the
character's number, and say who makes every Test it names ("if you pass…",
"if the target passes…"). Where a talent's specialisations are different
benefits (Blood of Aenarion's Magical or Martial Prodigy), put what every
character gets in the summary and each benefit in its own
(`--specialisation "Magical Prodigy" --summary "..."`): the sheet prints only
the one taken. Write plain sentences.

**Headings with nothing under them.** A heading whose only contents are other
entries ("Skills and Talents" over talents that are entries themselves, or a
list whose every item its `split_headings` made an entry) would
make an entry with no text: the report lists those under `empty_entries`. Mark
the plan's entry `"heading_only": true` and no entry is written; the heading's
words count as left out and the report lists it under `headings_only`. Keep the
marked entry in the plan: it still ends the section before it, and it is the
record of what was left out, so removing the mark brings the entry back. Say
in the chapter's notes which headings were left out this way.

**GM-only material.** Mark it `audience: "gm"` in the plan: adventures and
adventure hooks (boxed or printed in the text), and the NPCs a book offers as
patrons or adversaries, with their profiles, ambitions and "as Patron" text.
A patron's hooks are entries of their own, related to the NPC (`adds-to`);
split a box of hooks with the box's `entries`. Careers, spells, items and the
rules a player uses stay unmarked. Ask the Librarian about anything else that
reads as the GM's.

**A source of an older edition** (layout §8 "Editions"): its plan also lists
every rule it holds (career, spell, talent, creature) with the 4e entry that
updated it, if any, under the same name or another. Show the Librarian that
list and import only after they confirm it; each match becomes an
`updated-by` relation.

**Tables.** Show each table to the importer and write it only after they
confirm it. Take every number from the source, never from memory. The
converter lists them in its report's `tables_to_confirm`; show each one's rows
(or, for a long table, its size and first and last rows, offering the rest) and
compare its row count with the page image. A table printed as a flowchart or
picture is a `diagram`: transcribe it by hand, keeping every word, show it, and
note it in the chapter's notes. A table of text that no reader can take off the
page (marks on lines of their own, labels beside the middle of their rows, cells
that wrap) goes in the plan's `hand_tables`: the converter checks the transcript
against the page letter for letter and refuses one that differs.

**Grouped skills and talents.** `Lore (Any)`, `Melee (Basic)`: one entry for
the group, with its specialisations listed in `fields`, as layout §4 says.

## 5. Write

**Settle every question before the bookkeeping.** Gather every open question
(same-name decisions, tables to confirm, hand transcriptions to show), settle
them with the Librarian, apply the answers, then merge and write the
bookkeeping once per chapter. Entry files can be written as soon as they're
ready.

1. Write entry files to the target `library-data/<category>/` in batches of
   10–20, and record each batch in the journal.
2. Merge with `scripts/merge_import.py` from the current files (don't rebuild
   them by hand):

   ```
   # after each batch: index only
   python3 scripts/merge_import.py --out scratch/new --index <index> \
       --records scratch/out-ch3/_records.json --edition 4e --slugs <this batch's slugs>

   # at the end: index, log record, chapter status
   python3 scripts/merge_import.py --out scratch/new --index <index> \
       --records scratch/out-ch3/_records.json --edition 4e --log <import log> --library <library.json> \
       --source CRB --chapter ch3 --category careers \
       --log-notes "<what was imported, what was left out>" --chapter-notes "<short summary>" [--failed N]
   ```

   A chapter whose entries span several categories has one `_records.json`;
   each record carries `_category`. Merge it into each category's index in
   turn. For a campaign target, `--library` expects `library.json`'s layout, so
   update `campaign.json` by hand.
3. Write the merged `_index.json` files, then `_import-log.json`, then
   `library.json` last.
4. For a re-import, overwrite each entry, and trash entry files the merge says
   the chapter no longer has.

### Writing to the library

**Local folder first.** When the library's local folder can be reached
(layout §1), write straight into it, over the old files, and let Drive sync. In
a cloud session linked to the Librarian's computer, connect the folder once,
stage the files in the session's outputs folder, and copy them over in batches
with the device tools. Give every staged file a path not used before in the
session (a new folder per batch): writing a changed file from a path already
written once has been seen to send the earlier copy while reporting success.
Then list the folder and check every file's size against the local copy, and
stage each bookkeeping file (`library.json`, indexes, the log) back and compare
it byte for byte (`cmp`).

**Through the connector** (only when the folder can't be reached): print files
with `scripts/print_upload.py <files> --list`, then `--part 1`, `--part 2`…,
and upload the text between the markers exactly, with
`disableConversionToGoogleType: true` and `contentMimeType` `text/markdown` or
`application/json`. If the header says the file ends with a newline, the upload
must too; a `fileSize` one byte short means it was dropped. Check each upload's
size, and check content with a download and `scripts/compare_download.py`. The
connector can't edit in place: write the new file and trash the old one. Give
each file over about 20 KB its own background agent.

### Recording progress

Record every finished step in the journal **as it happens**, with
`scripts/import_journal.py --dir scratch` (`--help` lists every command):

| When | Run |
|---|---|
| Before any step that writes or takes a while | `doing "writing career entries, batch 2 of 6"` |
| You ask the Librarian a question | `waiting "the question, in a line"` |
| The Librarian answers | `answered "the decision, in a line"` (first, before acting on it) |
| You push a branch or open a pull request | `repo BRANCH --pr N`; when merged, `repo BRANCH --status merged` |
| First chapter of the session | `drive --root ID --library-data ID --folder careers=ID --file careers/_index.json=ID:SIZE ...` |
| The pages are read | `start crb-ch3 --source CRB --category careers --pages 30-109 --page ch3-layout.json` |
| The report and coverage are checked | `phase crb-ch3 converted --out out-ch3` |
| A hand edit, or anything a resumed session must know | `note crb-ch3 "..."` |
| After each write batch | `uploaded crb-ch3 slug=ID:SIZE ...` (refuses a size that doesn't match the converter's file) |
| All entries written | `phase crb-ch3 uploaded`, then after the merge `phase crb-ch3 merged` |
| Each bookkeeping file written | `bookkeeping careers/_index.json NEWID:SIZE` |
| Each old file trashed | `trashed OLDID` |
| The chapter is finished | `phase crb-ch3 bookkeeping`, `clean crb-ch3`, then `done crb-ch3` |

In the local folder, use the file's path for its ID.

### Resuming after an interruption

Read `show` first. **Waiting:** the Librarian's message may answer that
question; record it with `answered` before doing anything. **Step under way:**
it may be half done; check its result before redoing it. **Entries not yet
written:** the last one may have reached Drive unrecorded; look for it first.
**Phase `uploaded`:** re-run the merge from the downloaded bookkeeping files.
**Phase `merged`:** check each bookkeeping file's current ID and size before
writing. Tell the Librarian you resumed an interrupted import and what was left.

## 6. Report

Give counts (added, updated, skipped, failed), list every failure with its
section and page, and name the next `not-imported` chapter.

## Import status

When asked what's been imported, list each source with its chapters and
statuses (from `library.json` and the active campaign's `campaign_sources`),
counts per category from the `_index.json` files, and the last few log
records.

## Rules

- Write only inside the library's Drive folder. Never write source content to
  the repo, an artifact, or anywhere shared. Scratch files in the session
  workspace are fine; delete them at the end (`import_journal.py clean`).
- GM-only campaign sources and their entries stay in `gm/`.
- Keep the source's exact wording. Don't paraphrase, summarise or fix it.
- Build a converter before importing a kind of chapter with more than about ten
  entries: a script with tests on an invented PDF (drawn in the test with
  reportlab), in its own pull request, never with source text in the repo.
  Build smaller one-offs (a single table) by hand, show them, and check them.
  Before writing a one-off script for a chapter, ask whether the problem is a
  pattern (a table's title read into its first row, labelled details, a box of
  several tables): if another chapter or book could print it the same way, fix
  the converter or `pdf_layout.py`, with a test, and give the plan an option.
- No silent exceptions in checks. A check, including a throwaway scratch
  script, that skips or excuses anything says so in its output.
- Do repeated work with the repo's scripts rather than inline code written
  fresh each time. If a step keeps needing one-off code, it needs a script.
