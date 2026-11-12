# WFRP Assistant: layout and lookup contract (layout_version 1)

This file is the single source of truth for how the skills find, read, and
write the private library. It is copied into each skill's `references/` folder
by `scripts/sync-shared.sh` so every skill stays self-contained when uploaded to
claude.ai. Edit it here, then run the script.

The library holds copyrighted material and the group's private play. It lives
in a Google Drive folder that only the group can open. **Nothing from the
library is ever written to the git repo.**

Terms used here (import, source, entry, chapter, Librarian, GM, career, …) are
defined in the repo's `CONTEXT.md`.

## 1. Locating the library

Resolve the library root folder in this order and stop at the first hit:

1. **Config file.** `wfrp-library.config.json` in the current working directory
   or plugin root (Claude Code). Use `drive_folder_id`, and `drive_local_path`
   if it's set (below).
2. **Conversation / Project context.** A Drive folder ID or URL the user gave in
   this conversation, or in the Project's instructions or docs. A folder URL
   looks like `https://drive.google.com/drive/folders/<FOLDER_ID>` (an account
   segment such as `/u/2/` may come before `folders`).
3. **Drive search.** Search Google Drive for a file named `library.json` whose
   contents contain `"wfrp_library": true`. Its parent folder is the root. If
   several match, list them and ask which to use.

If none resolve, stop and tell the user how to configure it (README >
Configuration). Do not guess.

After resolving, read `library.json` and check `layout_version`. If it is
higher than the version this file describes, warn that the skills may be out of
date. If it is lower, suggest running `wfrp-library-setup` to upgrade it.

Then resolve the **active campaign** (§8) when the task involves one: building
characters, session notes, or rules questions at the table.

### Local folder or connector

Google Drive for desktop can show the library as a folder on a computer
(`drive_local_path`: in the config file, or a line in the Project's
instructions such as "WFRP library folder: I:\My Drive\WFRP Assistant"). When
the session can reach that folder, read and write library files there
directly; Drive syncs them. A session can reach it when it is Claude Code on
that computer, or a cloud session linked to that computer through the Claude
desktop app with the folder connected (ask for access to the folder once, if it
isn't). Before using the folder, check that it holds `library.json` with
`"wfrp_library": true`.

Otherwise, and on phones, use the Google Drive connector. Both reach the same
files, so a skill can switch between them at any time.

Never copy library content into the repo, a public artifact, or any shared
location outside the library.

## 2. Folder structure

```
<Library root>/
├── library.json                 manifest and library source list (§3)
├── skills/                      player skill zips to upload to claude.ai (§7)
├── sources/                     files for library sources (PDFs, docs)
│   └── <code>/plans/            per-chapter import plans (§6)
├── library-data/                entries imported from library sources (§4)
│   ├── _import-log.json
│   ├── rules/                   rules prose, conditions, psychology, glossary
│   ├── tables/                  reference tables (hit locations, criticals, random careers…)
│   ├── species/
│   ├── careers/                 one file per career, its four levels inside
│   ├── skills/
│   ├── talents/
│   ├── spells/                  petty and arcane spells, lore spells, blessings, miracles
│   ├── trappings/               weapons, armour, and other trappings
│   ├── qualities/               weapon and armour qualities and flaws
│   ├── creatures/               bestiary entries and NPC profiles
│   ├── traits/                  creature traits
│   ├── diseases/
│   ├── mutations/
│   └── lore/                    gods, places, organisations, history
└── campaigns/
    └── <campaign-slug>/
        ├── campaign.json        campaign config (§8)
        ├── characters/          character records and their printed sheets
        ├── sessions/            session notes (§9)
        │   ├── _index.json
        │   ├── <yyyy-mm-dd>-s<NN>.md
        │   └── raw/             original notes and transcripts, unedited
        ├── sources/             files for player-visible campaign sources
        ├── library-data/        entries from player-visible campaign sources
        └── gm/                  shared with the campaign's GM only (§7)
            ├── skills/          GM skill zips to upload to claude.ai (§7)
            ├── sources/         files for GM-only campaign sources (adventures)
            ├── library-data/    entries from GM-only campaign sources
            ├── npcs/            NPC profiles the players haven't met
            └── sessions/        GM-only notes, one file per session
```

Every `library-data/` folder has the same category subfolders and the same
`_import-log.json`. Create missing category folders as needed.

## 3. Sources

### `library.json`

```json
{
  "wfrp_library": true,
  "layout_version": 1,
  "name": "WFRP Assistant",
  "edition": "4e",
  "sources": [
    {
      "code": "CRB",
      "title": "Warhammer Fantasy Roleplay Fourth Edition Rulebook",
      "kind": "pdf",
      "edition": "4e",
      "file": "sources/CRB/WFRP4e Core Rulebook.pdf",
      "page_offset": 0,
      "chapters": [
        { "id": "ch3", "title": "Chapter 3: Class and Careers", "pages": "30-109",
          "status": "imported", "date": "2026-11-20", "notes": "" }
      ]
    }
  ],
  "house_rules": []
}
```

Each source has:

| Field | Meaning |
|---|---|
| `code` | Short unique code, used in citations and entry `source` fields. Unique across the library **and** all campaign sources. Cubicle 7 books: `CRB` (the Rulebook), `WOM` (Winds of Magic), `UIA` (Up in Arms), `AOA` (Archives of the Empire), `EIS` (Enemy in Shadows), and so on. Homebrew: `HB-<NAME>`. |
| `title` | Full title. |
| `edition` | The WFRP edition the source was written for: `4e`, `2e` or `1e`. §8 says how editions mix in a campaign. |
| `kind` | `pdf`, `gdoc` (Google Doc), `file` (other text file, including a homebrew document), or `pasted` (text given in the conversation). |
| `file` | Path in Drive, relative to the folder holding `sources/`. Not used for `pasted`. |
| `page_offset` | Printed page number minus PDF page index, when they differ (a cover and front matter before printed page 1). `pages` and entry `page` fields are always **printed** page numbers; tools add the offset to find the PDF page. |
| `chapters` | The source's table of contents, recorded when the source is added. `pages` is the printed page range. `status` is `not-imported`, `imported`, or `problems` (imported, but some entries failed checks: `notes` says which). `date` is the last import. |

A source with no chapters (a one-page homebrew doc) is treated as a single
chapter with `id` `all`.

### Homebrew documents

Homebrew the group writes itself lives in a **homebrew document**: one Markdown
file per scope (the library, a campaign, or a campaign's GM-only material) in
that scope's `sources/` folder, with `kind: file` and a code like `HB-TEW`
(docs/adr/0003). It is the master copy: to change an entry, edit the document
and import that chapter again.

- Each `#` heading is a chapter (`Careers`, `Talents`, `Spells`…); chapter ids
  are the heading's slug. Text before the first `#` is a note to editors.
- Entries are written the way the books write them (a career's four levels and
  advance scheme, a spell's CN/Range/Target/Duration lines, a creature's
  characteristic line), so the import finds the same fields as for the books.
- A line `Table: <title>` above a table titles it.

`house_rules` is a list of short strings that apply to every campaign.

### Campaign sources

A campaign's own sources are listed in its `campaign.json` (§8) under
`campaign_sources`, with the same fields plus:

| Field | Meaning |
|---|---|
| `visibility` | `players` (files in the campaign's `sources/`, entries in its `library-data/`) or `gm` (files in `gm/sources/`, entries in `gm/library-data/`). A published adventure is a `gm` campaign source. |

## 4. Entries

Each category folder in a `library-data/` holds:

- **`_index.json`**: a JSON array with one compact record per entry. Skills
  filter on it first, then open only the entries they need. Each record has at
  least `slug`, `name`, `source`, `edition` (its source's, §3), `chapter`,
  `section`, `page`, the entry's `relations` and `audience` when it has them,
  plus category fields:

  | Category   | Extra index fields |
  |------------|--------------------|
  | rules      | `kind` (condition, psychology, procedure, glossary), `aliases` |
  | tables     | `about` (one line), `roll` (`d100`, `d10`…, when it is a roll table); `kind: cross-reference` on a cross-reference |
  | species    | `aliases` (e.g. "Halfling" for "Halflings") |
  | careers    | `class` (Academics, Burghers, Courtiers, Peasants, Rangers, Riverfolk, Rogues, Warriors), `species` (who may roll it), `levels` (the four level titles), `status` (the four statuses, e.g. "Brass 3") |
  | skills     | `characteristic`, `advanced` (true/false), `grouped` (true/false) |
  | talents    | `max` (as printed, e.g. "Initiative Bonus"), `tests` |
  | spells     | `kind` (petty, arcane, lore, blessing, miracle), `lore` (lore or god), `cn`, `range`, `target`, `duration` |
  | trappings  | `kind` (melee, ranged, ammunition, armour, item, …), `group` (weapon or armour group), `price`, `enc`, `availability` |
  | qualities  | `kind` (weapon-quality, weapon-flaw, armour-quality, armour-flaw) |
  | creatures  | `kind` (creature, npc), `species_type` (as printed), `traits` (trait names with their ratings) |
  | traits     | `rated` (true when it takes a rating, e.g. Armour (2)) |
  | diseases   | `contraction`, `incubation`, `duration` |
  | mutations  | `kind` (physical, mental) |
  | lore       | `kind` (god, place, organisation, history, other) |

- **`<slug>.json`**: the entry's data, for tools (character builders,
  calculations).
- **`<slug>.md`**: the same entry for reading, generated from the `.json`
  (`wfrp-import/scripts/render_entry.py`) and never edited by hand: correct the
  `.json` and render again. YAML front matter repeats the index fields, then
  the entry's content in the source's exact wording. Tables are Markdown
  tables, which render in chat; never HTML tables. Sidebars are block quotes
  with a bold title.

### The entry `.json`

```json
{
  "slug": "rat-catcher", "name": "Rat Catcher", "source": "CRB", "chapter": "ch3",
  "section": "Rat Catcher", "page": 87,
  "fields": { "class": "Peasants", "species": ["Human", "Halfling"],
              "levels": ["Rat Hunter", "Rat Catcher", "Sewer Jack", "Exterminator"] },
  "level": 2,
  "content": [ blocks ]
}
```

`relations` (when present) says how the entry relates to other entries, as
`[{"role": ..., "to": "<category>/<slug>"}]`:

| Role | Meaning | Using it |
|---|---|---|
| `adds-to` | adds to that entry (more lore, optional rules, a variant) | use both: that entry first, then this one |
| `replaces` | supersedes that entry (a revised career in a supplement, errata) | when both are in play, use this one and say the other exists |
| `reprint-of` | the same text printed again (a Starter Set copy of a Rulebook talent) | use either; cite the one whose source comes first in play |
| `distinct-from` | a different thing with the same name (the *Dodge* skill, the *Dodge* talent if any) | never combine them |
| `updated-by` | an older edition's rules for this were updated by that entry | in a campaign of the newer edition this entry doesn't exist (§8) |
| `counts-as` | for rules, also counts as that entry (a homebrew weapon that counts as a Hand Weapon) | use this entry's own stats; any rule naming that entry applies to this one too |

Every pair of entries that share a name (allowing for plurals, "The", and
parenthetical words) has a decision on the later entry. The import refuses an
entry that shares a name and has none. Grouped skills and talents with a
specialisation (`Lore (Reikland)`, `Melee (Basic)`) are one entry for the group
(`lore`, `melee`); the specialisations are listed in its `fields`.

`audience` is `"gm"` for an entry only the GM should see (an adventure's
secrets, a bestiary's GM advice). Without it, the entry is for everyone. Only
use a `gm` entry for the campaign's GM (§8), or when there's no campaign and
the user says they're the GM.

`fields` holds the index fields and any other values a tool needs, taken from
the source's words:

- a career's `advances`: per level, the `characteristics` advanced (`["WS",
  "T", "WP"]`), `skills`, `talents` and `trappings`, as printed, and `status`;
  its `career_path` text;
- a species' `characteristics` (the `2d10+20` formulas per characteristic as
  printed), `fate`, `resilience`, `extra_points`, `movement`, `skills` and
  `talents` choices, and random-talent rolls;
- a skill's `characteristic`; a talent's `max` and `tests`;
- a spell's `cn`, `range`, `target`, `duration`;
- a weapon's `damage`, `reach` or `range`, `qualities`; an armour's
  `locations`, `ap`, `qualities`; every trapping's `price`, `enc`,
  `availability`;
- a creature's `characteristics` (`{"M": 4, "WS": 30, …, "W": 12}`), `traits`
  and `optional_traits`.

`level` is the heading level of the entry's own title on the page.

`content` is a list of blocks, in the source's order. Text keeps the source's
wording, with bold and italic as Markdown marks (`***Label:***`):

| Block | Fields |
|---|---|
| `heading` | `level`, `text` |
| `paragraph` | `text` |
| `list` | `ordered`, `items` (strings, or `{"text", "items"}` for an item with a sublist) |
| `fields` | `title`, `items`: `[{"label", "text"}]` (a spell's "CN: 4" lines, a career's "Skills:" line) |
| `table` | `title`, `columns`, `rows` (cells as printed), `groups` (`{"before": row, "text"}` for rows that head the rows below), `footnotes`, and `data` |
| `sidebar` | `title`, `content` (blocks) |
| `profile` | `name`, `characteristics` (`{"M": 4, "WS": 30, …}` in the printed order), `lines` (`[{"label": "Traits", "text": "…"}]`, as printed) — a creature's or NPC's stat line |
| `career_levels` | `levels`: `[{"title", "status", "characteristics", "skills", "talents", "trappings"}]`, as printed — a career's advance scheme |

A table's `data` has one object per row, keyed by its column headers in words
(`"location"`, `"roll"`). "—" is `null`; plain, "+N" and "−N" numbers are
numbers; a roll range ("01–09") is `{"min": 1, "max": 9}` under the roll
column; anything else is the printed text. A row under a group row carries it
as `"group"`.

`chapter` is the chapter `id` from the source's chapter list. `section` is the
heading the entry sits under, as printed. `page` is the printed page the entry
starts on.

Slugs are lowercase, hyphenated, ASCII: `rat-catcher`, `strike-mighty-blow`,
`ablaze`. Each source's entries keep their own files even when names match: if
a slug is already taken by another source, add the source code
(`rat-catcher-hb-tew`).

### `_import-log.json`

A JSON array, newest last, one record per import run:
`{"date", "source", "chapter", "category", "added", "updated", "skipped", "failed", "notes"}`.
`updated` counts entries a re-import overwrote; `notes` says why (errata,
better extraction).

## 5. Citing

Cite every rule or entry by source, chapter, section and page:
`(CRB, ch. 5 › Fear, p. 190)`. Use the chapter's number or short title,
whichever the source uses.

If something came from a house rule, say so instead, and say whether it is a
library or a campaign house rule.

## 6. Importing

### Who imports where

| Who | Imports | Into |
|---|---|---|
| Librarian | library sources | `library-data/` |
| A campaign's GM | that campaign's campaign sources | the campaign's `library-data/` or `gm/library-data/` |

Nobody else writes entries. If the connector reports no edit access to the
target folder, stop and say who can import it.

### Where it runs

Importing runs wherever the whole source can be read (docs/adr/0001):

- `gdoc`, `pasted`, and small `file` sources: through the connector, anywhere.
- `pdf` sources: from the local folder (§1): Claude Code on the Librarian's
  computer, or a cloud session linked to it, so the whole PDF is on disk. A
  rulebook PDF is far past what the connector returns. If neither is
  available, say so and stop.
- A whole book writes hundreds of files, so write them to the local folder
  when it can be reached; through the connector, every file's text passes
  through the conversation.

### PDFs are read by layout, not as flat text

Cubicle 7's books are two-column pages with sidebars, boxed career schemes,
stat lines and tables. Flat text extraction runs columns and table cells
together (docs/adr/0002). The import reads each page's text spans with their
position, font, size and weight (`wfrp-import/scripts/pdf_layout.py`), orders
them by column, and finds headings from font size and weight. Each chapter's
**plan** says how the chapter splits into entries (which heading level is an
entry, which section holds which category) and lives in Drive beside the
source (`sources/<code>/plans/<chapter>.json`), never in the repo: it is the
book's outline.

When text extraction garbles a page (a table drawn as art, a stat line in an
image), look at the page image and transcribe it, and say so in the chapter's
notes. If the PDF is scanned (no text layer), ask before running OCR.

### Entries are written automatically, except tables

Write entries in batches, checking each one: required fields present, a
career's four levels all there, a creature's characteristic line complete, no
truncated text, every word of the chapter in an entry or the left-out list.
Report every failure with its chapter and section, and set the chapter's
status to `problems`.

**Tables** are the exception: show each table to the importer and write it only
after they confirm it, because characters and play depend on its numbers.

### Cross-references

A **cross-reference** is a table the Librarian builds rather than one a source
prints, such as the other names a source uses for a career. It lives in
`tables/` with `kind: cross-reference` in its front matter and index record, so
no one takes it for source text. Every row says where its information appears
(source, chapter, section, page). There is one per category, named
`<category>-name-synonyms`. Like any table, it's shown to the Librarian before
it's written.

### Re-importing

Re-importing a chapter overwrites its entries: in the local folder (§1), write
over each file; through the connector, write the new file and move the old one
to the Drive trash. Record the count in `updated` with the reason in `notes`.
No versions are kept; Drive's revision history covers the rare need.

## 7. Access

- **Library root**: the Librarian edits; everyone else in the group can view.
- **`campaigns/<slug>/`**: the campaign's GM and players can edit.
- **`campaigns/<slug>/gm/`**: shared with that campaign's GM only, with
  inherited access turned off (`inheritedPermissionsDisabled`), so players
  can't open it even though they can edit the rest of the campaign.

Skills never move GM-only material out of `gm/`, and never include it in
answers unless the user is that campaign's GM.

The skills themselves are shared the same way, as zips to upload in claude.ai
(Settings → Capabilities → Skills), each folder with a `README.md` and a
`manifest.json` (version and each zip's SHA-256):

- **`skills/`** at the library root: the player skills (rules lookup, character
  sheets, session notes). Everyone who can view the library can download them.
- **`campaigns/<slug>/gm/skills/`**: GM-only skills, when there are any. GMs
  also use the player skills.
- The Librarian's skills (library setup, import) aren't shared: the Librarian
  uses them from the repo.

## 8. Campaigns

Each folder in `campaigns/` is one campaign, configured by its `campaign.json`:

```json
{
  "name": "The Enemy Within",
  "slug": "the-enemy-within",
  "gm": "",
  "edition": "4e",
  "sources": ["EIS", "CRB", "UIA"],
  "campaign_sources": [
    { "code": "EIS", "title": "Enemy in Shadows", "kind": "pdf", "edition": "4e",
      "file": "gm/sources/EIS/Enemy in Shadows.pdf", "visibility": "gm", "chapters": [] }
  ],
  "house_rules": [],
  "creation": {
    "species": "random-or-choose",
    "career": "random-or-choose",
    "characteristics": "random-or-choose",
    "starting_xp_bonus": true
  },
  "allowed": {
    "species": "all",
    "careers": "all",
    "talents": { "exclude": [] },
    "spells": { "exclude": [] }
  },
  "party": [
    { "character": "characters/greta-falkenhayn.json", "player": "Sam" }
  ],
  "party_ambitions": { "short": "", "long": "" },
  "in_game_date": "",
  "notes": ""
}
```

| Field | Meaning |
|---|---|
| `slug` | Must match the folder name. |
| `gm` | Name or email of the campaign's GM. |
| `edition` | The WFRP edition the campaign plays by. Left out means the library's `edition`. |
| `sources` | The **sources in play**, in order of precedence: library source codes and this campaign's source codes. Only entries from these sources may be used. |
| `campaign_sources` | This campaign's own sources (§3). |
| `house_rules` | Added to the library's `house_rules`. Where they conflict, the campaign's win. |
| `creation` | How new characters are made: for species, career and characteristics, `random` (roll and keep), `random-or-choose` (roll, and choosing costs the Rulebook's XP bonus), or `choose`. `starting_xp_bonus` false turns the bonus XP for keeping rolls off. Left out means the Rulebook's rules. |
| `allowed.<category>` | `"all"`, or `{ "include": [slugs] }` (only these), or `{ "exclude": [slugs] }` (all but these). Applied after the `sources` filter. Categories left out mean `"all"`. |
| `party` | The current party. `character` is a path to the character's record, relative to the campaign folder. |
| `party_ambitions` | The party's short- and long-term ambitions, as the group wrote them. |
| `in_game_date` | The current date in the Imperial Calendar, as the GM writes it (e.g. "Festag, 33rd Nachexen 2512 IC"). |
| `notes` | Free text for the GM: setting, tone, things to keep in mind. |

When a campaign is created, campaign sources go first in `sources`, so the
GM's material overrides the library unless they reorder it.

**Choosing the active campaign**, in this order:

1. A campaign the user names in the conversation (match `name` or `slug`).
2. `default_campaign` in `wfrp-library.config.json`, or a campaign named in the
   Project's instructions or docs.
3. If `campaigns/` contains exactly one campaign, use it and say so.
4. Otherwise ask. If the user wants no campaign, use all library sources, with
   only the library's house rules.

**Finding entries for a campaign:**

1. Gather candidates from the library's `library-data/`, the campaign's
   `library-data/`, and, only if the user is the GM, the campaign's
   `gm/library-data/`.
2. Keep entries whose `source` is in `sources`, then apply `allowed`. Drop
   entries with `audience: gm` unless the user is the campaign's GM. Drop
   entries of another edition that are `updated-by` an entry.
3. Entries that share a name follow their `relations` (§4), not source order.
4. If a filter removes everything the user asked for, say which rule removed it
   rather than quietly widening the search. If the source is in play but the
   relevant chapter isn't imported yet (§3 chapter status), say that instead of
   "not found".

**Editions.** A campaign plays by one edition's rules. A source of an older
edition in its `sources` contributes only what the campaign's edition didn't
update: lore, places, adventures, and creatures read through the campaign's
edition's rules. An entry that's `updated-by` a newer one is never offered.
Which entries were updated is a judgment call; each chapter's import plan
proposes them and the Librarian confirms.

## 9. Characters

A character lives in the campaign's `characters/` folder:

- `<slug>.json`: the **character record**, the source of truth. It holds only
  the character's choices and facts (species, careers taken and their level,
  advances bought, talents taken, XP, trappings carried, wounds, corruption,
  mutations, psychology, ambitions), each pointing at the library entry it
  comes from as `<category>/<slug>`. The character-sheet skill's
  `references/character-record.md` gives the format.
- `<slug>.md` (and `<slug>.pdf` when printed): the readable sheet, built from
  the record and the library. Rebuild it whenever the record or the library
  changes. Never edit it by hand.

Never copy into the record what a rule decides: a talent's text, a weapon's
damage, a characteristic's bonus. The sheet works those out from the library
each time, so a corrected entry shows up on the next build.

## 10. Sessions

Session notes live in `campaigns/<slug>/sessions/`. They hold the group's
words and the GM's secrets, so they stay in Drive only.

### Session file: `<yyyy-mm-dd>-s<NN>.md`

`NN` is the session number, zero-padded to two digits (`s07`; `s112` past 99).

```markdown
---
session: 7
date: 2026-11-14
title: "Murder on the Reik"
in_game_date: "Bezahltag, 2nd Nachexen 2512 IC"
attendees: [Sam, Alex, Jo]
gm: Tom
raw:
  - raw/2026-11-14-s07-transcript.vtt
speakers:
  "Speaker 1": { player: Sam, character: Greta }
  "Speaker 4": { role: gm }
summary: "One or two sentences."
npcs: [Josef Quartjin, Gustav Fügler]
locations: [Weissbruck, the Berebeli]
factions: [Purple Hand]
items: []
quests: [Kastor Lieberung's inheritance]
tags: [river, investigation]
---

## Summary
## Events
## NPCs
## Loot and rewards
## Advancement
- XP awarded, and to whom; careers changed or completed.
## Corruption and wounds
- Corruption points, mutations, Critical Wounds and insanities that carry forward.
## Rulings
## Open threads
- ~~A thread this session resolved~~ (resolved: what happened)
## Open questions
```

Leave out sections that would be empty, except Summary.

### GM-only session notes

Secrets, prep, and anything the players haven't seen go in
`gm/sessions/<same file name>.md`, never in the shared session file. A raw
source that contains GM secrets (the GM's prep notes) is saved in
`gm/sessions/raw/` instead of `sessions/raw/`.

### `sessions/_index.json`

A JSON array with one record per session, sorted by `session`:

```json
{
  "session": 7, "date": "2026-11-14", "file": "2026-11-14-s07.md",
  "title": "Murder on the Reik", "in_game_date": "Bezahltag, 2nd Nachexen 2512 IC",
  "summary": "One or two sentences.",
  "npcs": [], "locations": [], "factions": [], "items": [], "quests": [], "tags": [],
  "xp_awarded": 100,
  "open_threads": [], "resolved_threads": []
}
```

The index only describes the shared file. `gm/sessions/` has its own
`_index.json` with the same shape, for GM-only searches.

Use the same spelling for a name across all sessions. If a session file or
folder is missing, create it rather than failing.

## 11. Writing

| Writes to | Who |
|---|---|
| `library.json`, `sources/` (files), `library-data/` | Librarian, through `wfrp-library-setup` and `wfrp-import` |
| a campaign's `campaign.json`, `sources/`, `library-data/`, `gm/` | that campaign's GM |
| a campaign's `characters/`, `sessions/` | the campaign's GM and players |

Files in `sessions/raw/` and `gm/sessions/raw/` are never edited after they're
saved. Update an `_index.json` in the same pass as the files it describes, so
it never points at missing files. In the local folder (§1), change a file by
writing over it; Drive keeps its revision history. The connector can't edit
file contents in place: to change a file through it, write the new version and
move the old one to the Drive trash.
