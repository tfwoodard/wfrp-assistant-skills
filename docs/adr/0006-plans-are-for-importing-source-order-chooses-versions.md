# A plan is only for importing; the campaign's source order chooses between versions

Two things had drifted, both inherited from the DnD Assistant.

**Plans were becoming a second library.** A chapter's plan exists because the
books' text can't be in the repo: it tells the converters how to read the
pages (which headings are entries, where a table's columns fall, which box
belongs to which section). It is a necessary helper for importing and nothing
else. But anything that had to survive a re-import was being put there, and so
the plan was collecting decisions about the content: formulas (ADR 0005) most
recently. Nobody reads a plan to learn what the library says.

**Which book's version is used was decided per entry, at import.** When a
later book reprints something with changes (a weapon's new profile, a revised
spell), the newer entry was marked as *replacing* the older, and that mark
decided the matter for every campaign. With five books that was 129 separate
marks, each written into a plan, and a campaign that had both books but
preferred the older rules had no way to say so. The Librarian had taken it
that book precedence was a setting: every book's entries are imported and
kept, and a campaign says which books it uses and which come first.

## Decisions

1. **A plan holds only what the import needs to read the source.** It takes no
   part in anything at runtime, and it is not where content decisions are kept.
   Formulas live on the entry and only there. A plan that has `formulas` is
   refused. (Relations stay in plans for now: the import uses them to name
   files and to check every shared name has been looked at. See below.)

2. **Which books are used, and which come first, are campaign settings.**
   `campaign.json`'s `sources` lists the sources in play, highest precedence
   first.

3. **`replaces` now means "these are versions of one thing".** Of the versions
   whose sources are in play, a campaign uses the one whose source comes first
   in its `sources`, whichever way the mark points. The direction of the mark
   only decides between versions the campaign ranks the same (two entries of one
   source), and when no campaign is chosen. The other versions are not offered,
   and a lookup says which source took precedence.

4. **The other per-entry marks stay as they are**, because they are facts about
   the content, not preferences: `adds-to` (read both), `distinct-from` (same
   name, different things), `reprint-of` (identical text).

## Consequences

- No entry changes. The 129 existing marks are read differently, and an order
  for a campaign's `sources` that puts each newer book before the one it revises
  gives exactly the choices made before. A campaign listing the Rulebook first
  gets the Rulebook's versions.
- A campaign's `sources` order now matters, so creating a campaign has to ask
  for it, or default to newest first.
- The name `replaces` no longer says what the mark does. Renaming it
  (`version-of`) means rewriting those entries, their indexes and plans; left
  until something else needs them rewritten.
- Still open: whether the import should treat a shared name as a version by
  default, without a line in the plan, leaving plans to state only the
  exceptions. That would take most of the remaining relations out of plans.

## Later, the same day: both open points settled

- **The mark is renamed `version-of`.** Every entry, index and plan that wrote
  `replaces` is rewritten once (`migrate_version_of.py`); readers accept the old
  name too, so a library part-way through keeps working. A plan that still
  writes `replaces` is refused.
- **A shared name is a version by default.** An entry that takes another
  source's entry's exact name in its category is written `version-of` it by
  the converter (or `reprint-of`, when the texts are compared and identical),
  with no line in the plan. Plans state only the exceptions.
