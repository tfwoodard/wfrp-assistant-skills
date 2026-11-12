# WFRP Assistant Skills

Claude skills for Warhammer Fantasy Roleplay (4th edition), backed by a private
Google Drive library imported from the group's own PDFs.

## Repo rules

- Never commit copyrighted or private content: sources (PDFs, homebrew),
  anything imported from them, chapter plans, campaign files, character
  records, session notes, or transcripts. They live in Drive only.
- Test fixtures must be invented. Never commit real book text, even a line, even
  in a test or a commit message. Generate fixture PDFs in the test itself
  (reportlab) from invented words.
- Use the terms in `CONTEXT.md`.
- `wfrp-library.config.json` is gitignored and must stay that way. The
  library's Drive folder ID and local path go there or in the claude.ai
  Project's instructions, never in a tracked file.
- `shared/library-layout.md` is the source of truth for the library format. After
  editing anything in `shared/`, run `./scripts/sync-shared.sh` and commit the
  synced `skills/*/references/` copies. `./scripts/sync-shared.sh --check` verifies them.
- Bump `version` in `.claude-plugin/plugin.json` when skills change.
- Player and GM skills are shared as zips in the library's Drive (layout §7);
  the Librarian's skills (`wfrp-library-setup`, `wfrp-import`) stay in the repo.
  `scripts/package-skills.py` says which skill goes where. Whenever you pull a
  `main` that changed, run `./scripts/package-skills.sh` and compare each
  `dist/<folder>/manifest.json` with the one in Drive: upload the zips whose
  SHA-256 changed, plus that folder's `README.md` and `manifest.json`, to the
  library's `skills/` (players) and every campaign's `gm/skills/` (GM). Then
  tell the Librarian which skills changed, so the group can re-upload them.
- Run the tests with `python3 -m unittest discover tests` before pushing.

## Library operations

- During imports and bulk updates, treat Drive uploads and downloads as trivial.
  The connection is unmetered and fast. When a library file needs checking or
  correcting, download it and fix it; don't weigh whether the transfer is worth it.
  Bulk reads that would crowd the conversation can go to a background agent.
- Prefer the library's local folder (layout §1) over the connector whenever it
  can be reached: PDFs need it, and a chapter's hundreds of files go through it
  in seconds.
- During an import, these are expected and authorized by the Librarian; don't
  stop to ask about them:
  - uploading or writing files to the library's Drive folders;
  - moving a library file to the Drive trash once its replacement is uploaded
    and its size verified;
  - deleting the import's own scratch files (`import_journal.py clean`);
  - pushing a feature branch and opening a pull request (never merging);
  - uploading packaged skills to the library's skill folders.

## Lessons carried over from the DnD Assistant

These cost real time on tfwoodard/dnd-assistant-skills; don't relearn them.

- **Read structure, don't guess it.** Flattened page text lost headings and ran
  table columns together, and every chapter needed heuristics that kept
  breaking. Read PDFs with positions and fonts (`pdf_layout.py`) and build the
  entries from that (docs/adr/0002).
- **A converter per kind of chapter, with tests.** Before importing a kind of
  chapter with more than about ten entries (careers, talents, spells, a
  bestiary), write a converter with tests on an invented page, in its own pull
  request. One-offs (a single table) are done by hand, shown, and checked.
- **Count every word.** A chapter's coverage check accounts for every word on
  its pages: in an entry, or on the left-out list (art credits, page furniture).
- **No silent exceptions in checks.** A check that skips or excuses a case says
  so in its output.
- **Journal every step as it happens.** Sessions stop mid-import (usage limits,
  closed laptops). `import_journal.py` records progress and conversation state,
  and the hook in `.claude/settings.json` shows it at every prompt.
- **Settle questions before bookkeeping.** Gather every open question, settle it,
  then merge indexes, the log and `library.json` once (`merge_import.py`).
- **Never retype a file.** Upload generated files unchanged, check each size
  against Drive, and compare downloads with `compare_download.py`.
- **Records point at rules; they don't copy them.** Characters hold choices and
  references; sheets are rebuilt from the library.

## Agent skills

### Issue tracker

Issues live in GitHub Issues on tfwoodard/wfrp-assistant-skills, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default labels: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
