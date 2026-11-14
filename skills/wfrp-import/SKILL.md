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
   page numbers) and gives heading levels from type size. If it reports pages
   with no text layer, look at the page images and ask before running OCR.
2. Check it's the chapter it should be: its first heading matches the chapter
   list. If not, say so and stop.
3. Look at a few pages with `--text` and at the page images where the layout is
   unusual (career pages, stat lines, tables). Write the chapter's **plan**:
   which heading level starts an entry, which sections hold which category,
   what's left out (art credits, flavour quotes the Librarian doesn't want),
   and every same-name decision (below). Keep it in Drive beside the source
   (`sources/<code>/plans/<chapter>.json`), never in the repo.
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
   | Rules prose (sections, conditions, psychology, symptoms; diseases with their labelled fields; boxed sidebars and ruled tables) | `convert_rules.py` | the entries in order, by name and page (and `heading` when the book prints more than the name), their `kind`, or another `category` with `field_labels`; an `intro` entry for text before the first; boxes to send elsewhere (`to`), make entries, or leave out as `diagram`s; tables to write to `tables/` too, with title, `about`, `roll_column`, `banner`/`header_row` fixes and the boxes they're `continued_in`; `text_tables` for tables printed without rules (the header line, its `columns`, and how many `rows`). Run `pdf_layout.py` with `--boxes`, and `--icon-text` for icons printed in the text. |
   | Skills and talents ("Name (Char) basic" headings; talents with Max and Tests lines) | `convert_skills_talents.py` | a `convert_rules.py` plan for the chapter's rules sections, boxes and tables, plus the `skills` and `talents` page ranges and their `section`. The skills and talents themselves are found by their headings, not listed; a heading at their level that doesn't read as one is an error. Check the report's `field_lines_joined` and `labels_as_printed`. Run `pdf_layout.py` with `--boxes`. |

   | Spells and prayers (lists of spells, blessings or miracles, each with CN, Range, Target and Duration lines) | `convert_spells.py` | a `convert_rules.py` plan for the chapter's rules sections, boxes and tables, plus its `lists`: each list's heading, page, `kind` (petty, arcane, lore, blessing, miracle) and `lore` (a lore's or a god's name), and `"entry": false` for a list heading that holds no text of its own. The spells are found by their headings and field lines, not listed; a heading at their level without field lines is an error, and so is a spell without Range, Target or Duration (or CN, for petty, arcane and lore spells). Check the report's `field_lines_joined`, `labels_as_printed` and `labels_not_bold`. Run `pdf_layout.py` with `--boxes`. |

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
with `--taken`), the plan must say how they relate, under `relations` (layout
§4): `adds-to`, `replaces`, `reprint-of`, `updated-by`, or `distinct-from`.
Read both entries before deciding, never decide from source precedence, and
ask the Librarian whenever it isn't certain. Mark GM-only material with
`audience: "gm"`. The decisions live in the plan, so a re-import keeps them.

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
note it in the chapter's notes.

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
- No silent exceptions in checks. A check, including a throwaway scratch
  script, that skips or excuses anything says so in its output.
- Do repeated work with the repo's scripts rather than inline code written
  fresh each time. If a step keeps needing one-off code, it needs a script.
