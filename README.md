# WFRP Assistant Skills

Claude skills for running **Warhammer Fantasy Roleplay, 4th edition** at the
table. They import game material from **sources you own** (Cubicle 7 PDFs and
your own homebrew) into a private library, then use it to:

| Skill | What it does |
|---|---|
| `wfrp-library-setup` | Creates, connects, upgrades, and checks your private library in Google Drive; creates campaigns and sets up sharing |
| `wfrp-import` | Imports careers, talents, skills, spells, trappings, creatures, rules and tables from a source, one chapter at a time |
| `wfrp-rules-lookup` | Answers rules questions mid-session, citing chapter, section and page |
| `wfrp-character-sheet` | Creates characters (random or chosen species, career and characteristics), spends XP on advances and career changes, checks each choice against the rules, and builds a readable sheet |
| `wfrp-session-notes` | Turns your notes or transcripts into session notes, then searches them, writes "previously on…" recaps, and tracks open threads, XP and corruption |

Words like *source*, *entry*, *chapter*, *career*, *Librarian*, and *GM* have
specific meanings here; see [`CONTEXT.md`](CONTEXT.md).

## No copyrighted content lives in this repo

This repository contains **only skill instructions and tooling**. Your sources,
everything imported from them, and your campaigns live in a **Google Drive
folder you control**, shared only with your group. The skills read and write
that folder through Google Drive for desktop or Claude's Google Drive
connector.

`.gitignore` blocks the local config file, PDFs, transcripts, and the library's
folder names, in case something lands in a clone by accident. Test fixtures are
invented. Please keep it that way in pull requests.

You need your own legal copies of the books.

## How it fits together

```
 GitHub (public)                  Google Drive (private, your group only)
 ┌───────────────────────┐        ┌──────────────────────────────────────────┐
 │ skills/*/SKILL.md     │        │ WFRP Assistant/                          │
 │ shared/library-layout │─reads─▶│  library.json  ← sources + chapter lists │
 │ (no game content)     │ writes │  sources/      ← PDFs, homebrew docs     │
 └───────────────────────┘        │  library-data/<category>/ ← entries      │
            ▲                     │  campaigns/<slug>/campaign.json          │
            │                     │    characters/ sessions/                 │
            │                     │    sources/ library-data/  ← homebrew    │
            │                     │    gm/         ← the campaign's GM only  │
            │                     └──────────────────────────────────────────┘
 wfrp-library.config.json (gitignored): Drive folder ID, local path, default campaign
```

The full folder layout, file formats, and rules are in
[`shared/library-layout.md`](shared/library-layout.md). Design decisions are in
[`docs/adr/`](docs/adr/).

## Roles

- **Librarian:** the one person who maintains the shared library: adds
  sources, imports them, and sets library-wide house rules.
- **GM:** runs one campaign, controls its settings, imports its adventures and
  homebrew, and is the only one who can open its `gm/` folder.
- **Players:** can view the library and edit their campaign's characters and
  sessions.

One person can be both Librarian and GM.

## Setup

### 1. Connect Google Drive

In claude.ai, open **Settings → Connectors** and connect **Google Drive**.
Everyone in the group who uses the skills needs this. The Librarian also
needs **Google Drive for desktop**, so PDFs can be imported from the computer
(see [ADR 0001](docs/adr/0001-import-runs-where-the-whole-source-is-readable.md)).

### 2. Install the skills

**Claude Code (plugin):**

```
/plugin marketplace add tfwoodard/wfrp-assistant-skills
/plugin install wfrp-assistant@wfrp-assistant-skills
```

**claude.ai (upload):** the Librarian packages the skills and puts them in the
library's Drive:

```bash
./scripts/package-skills.sh     # writes dist/players/ (and dist/gm/ when there are GM skills)
```

Players download the zips in the library's `skills/` folder and upload each
under **Settings → Capabilities → Skills**. The Librarian uses library setup
and import from this repo; they aren't packaged.

### 3. Create or connect the library

Ask Claude: *"Set up a new WFRP library in my Drive folder &lt;folder URL&gt;"*
(or *"connect to the WFRP library at &lt;folder URL&gt;"*). Whoever creates it
is the Librarian. Then ask Claude to share it with your group.

### 4. Create a campaign

Ask Claude: *"Create a campaign called The Enemy Within, GM'd by me."* Each
campaign's `campaign.json` holds its sources in play, house rules, character
creation options (random or chosen species, career and characteristics), bans,
the party, party ambitions and the current Imperial date. To change any of
these, just ask.

### 5. Import

Importing happens one **chapter** at a time, from where the whole PDF can be
read: Claude Code on the Librarian's computer, or a claude.ai session linked to
it through the Claude desktop app.

1. Put the PDF in the library's `sources/<code>/` folder (for example
   `sources/CRB/`) and ask *"add the WFRP Rulebook as a source"*. Claude reads
   the chapter list from the PDF's bookmarks (`pdf_outline.py`) and checks it
   with you.
2. Ask *"import chapter 3 of the Rulebook"*. Claude reads the chapter's pages
   by layout (`pdf_layout.py`), proposes a plan, converts, checks that every
   word landed somewhere, and writes the entries.
3. Ask *"what's left to import?"* at any time.

Entries keep the source's exact wording and are cited by chapter, section and
page, e.g. *(CRB, ch. 5 › Fear, p. 190)*. Tables are shown to you for
confirmation before they're written.

**Homebrew** lives in a homebrew document: a Markdown file per library or
campaign, imported a chapter at a time
([ADR 0003](docs/adr/0003-homebrew-is-written-in-a-library-document.md)).

### 6. Record sessions

After each game, give Claude your notes or a transcript:

> *"Add tonight's session from these notes: …"*

The original is saved unedited in `sessions/raw/`. Claude writes a structured
session file (summary, events, NPCs, loot, XP, corruption, rulings, open
threads). Then ask things like *"When did we first meet Josef?"* or *"Give me a
previously-on for tonight."* Anything secret goes in the campaign's `gm/`
folder, which players can't open.

## Configuration

The skills look for the library in this order, and use the first one they find:

1. **`wfrp-library.config.json`** (Claude Code). Copy the example and fill it in:

   ```bash
   cp wfrp-library.config.example.json wfrp-library.config.json
   ```

   ```json
   {
     "drive_folder_id": "1AbC...xyz",
     "drive_folder_name": "WFRP Assistant",
     "drive_local_path": "I:\\My Drive\\WFRP Assistant",
     "default_campaign": "the-enemy-within",
     "edition": "4e",
     "layout_version": 1
   }
   ```

   - `drive_folder_id`: the last part of the folder's URL,
     `https://drive.google.com/drive/folders/`**`1AbC...xyz`**.
   - `drive_local_path`: where Google Drive for desktop shows the library on
     your computer (backslashes doubled in JSON). Needed for importing PDFs.
   - `default_campaign` (optional): the campaign used when you don't name one.

   This file is **gitignored**. Don't commit it.

2. **Project instructions** (claude.ai). Uploaded skills can't read a local
   file, so put lines like these in your claude.ai Project's instructions:

   > WFRP library: https://drive.google.com/drive/folders/1AbC...xyz
   > WFRP library folder: I:\My Drive\WFRP Assistant
   > Default campaign: the-enemy-within

3. **Automatic discovery.** If neither is set, the skills search your Drive for
   a `library.json` containing `"wfrp_library": true` and ask you to confirm if
   there's more than one.

To check the connection at any time, ask *"check my WFRP library"*.

## Developing

```
.claude-plugin/        plugin + marketplace manifests
.claude/settings.json  hook that shows an unfinished import at every prompt
CONTEXT.md             glossary of the project's terms
docs/adr/              design decisions
docs/agents/           settings for agent skills (issues, labels, domain docs)
shared/                reference files shared by all skills (edit here)
skills/<name>/         SKILL.md + references/ (references are synced copies)
skills/wfrp-import/scripts/pdf_outline.py     PDF bookmarks -> chapter list with printed pages
skills/wfrp-import/scripts/pdf_layout.py      PDF pages -> lines (by baseline and column) with style, icons
skills/wfrp-import/scripts/check_coverage.py  check converted entries lost no words of the pages
skills/wfrp-import/scripts/convert_careers.py  career pages -> career entries (scheme, career path)
skills/wfrp-import/scripts/convert_rules.py    rules prose -> rules, disease and table entries, with sidebars and tables
skills/wfrp-import/scripts/entry_text.py      text helpers the converters share (styles, hyphens, lists, table data)
skills/wfrp-import/scripts/render_entry.py    entry .json -> Markdown
skills/wfrp-import/scripts/merge_import.py    merge index records, log, chapter status
skills/wfrp-import/scripts/import_journal.py  progress journal for resuming an import
skills/wfrp-import/scripts/print_upload.py    print files for connector uploads
skills/wfrp-import/scripts/compare_download.py  check a Drive download against the upload
tests/                 tests; fixture PDFs are generated from invented text
scripts/sync-shared.sh copy shared/ into each skill  (--check to verify)
scripts/package-skills.sh  zip the player and GM skills for claude.ai
```

Run the tests with `python3 -m unittest discover tests`. The PDF tools need
`pdfplumber` (`pip install pdfplumber`); the tests also need `reportlab` to
generate their fixture PDFs.

## License

The contents of this repository (skill instructions, the library spec, and
scripts) are released under the [MIT License](LICENSE).

This license covers only what's in this repo. It doesn't cover your sources,
anything imported from them, or your group's campaign files, none of which
are, or should ever be, stored here. Warhammer Fantasy Roleplay is a trademark
of Games Workshop; this project is unofficial and not affiliated with Games
Workshop or Cubicle 7.
