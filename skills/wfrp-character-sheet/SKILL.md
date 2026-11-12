---
name: wfrp-character-sheet
description: Create, advance, and look after Warhammer Fantasy Roleplay (4e) characters using the group's private library in Google Drive, checking every choice against the rules, and build a readable character sheet. Use when a player wants to make a character (random or chosen species, career and characteristics), spend XP, change career, record wounds, corruption, mutations or trappings, check a character is legal, or get a sheet to read or print.
---

# Character sheet

Read `references/library-layout.md` for where data lives (§9 for characters),
and `references/character-record.md` before writing or changing a record.

## Storage

Each character lives in the campaign's `characters/` folder:

- `<slug>.json`: the **character record**, the source of truth. It holds only
  the character's choices and facts, each pointing at the library entry it
  comes from.
- `<slug>.md`: the readable sheet, built from the record and the library.
  Rebuild it whenever the record or the library changes. Never edit it by
  hand.

Never copy into the record what a rule decides: a talent's text, a weapon's
damage, a characteristic bonus, a career level's skills. Those are read from
the library each time, so a corrected entry shows up on the next build.

## Before anything

Resolve the library and the active campaign (layout §1, §8). Find entries as
layout §8 describes (never `gm/` data or `audience: gm` entries: sheets are
player-visible), and offer only options that pass the sources in play and
`allowed`. Say which rule rules out an option the player asks for. If
something needed isn't imported (species, careers, skills, talents, the random
tables), say which source and chapter the Librarian should import, with
`wfrp-import`, and stop rather than filling it from memory.

## Creating a character

Follow the Rulebook's character creation, step by step, as imported in the
library, and the campaign's `creation` options (layout §8):

1. **Species**: roll on the library's species table or choose, as `creation`
   allows, and record which, since keeping a roll earns bonus XP.
2. **Class and career**: roll on the species' column of the career table or
   choose, the same way. The character starts at level 1 of the career.
3. **Characteristics**: roll each from the species' formula, or allocate as the
   rules allow; record the rolls. Fate and Resilience from the species, plus
   the extra points as the player assigns them.
4. **Skills and talents**: the species' skills and talents, then the career
   level 1 advances the rules give at creation; check every choice against the
   lists in the entries.
5. **Trappings**: the class's and career level's trappings, and starting
   wealth from the career level's status.
6. **Details**: name, age, height, eyes, hair, ambitions, and the party's
   ambitions (to `campaign.json`).

Use real dice for rolls the player makes; when asked to roll for them, say
which table and show each roll. Record bonus XP for kept rolls only when
`starting_xp_bonus` isn't false.

## Advancing

For every purchase:

1. Check it's allowed now: a characteristic, skill or talent of the
   character's current career level (or an earlier level of the same career),
   or something the rules allow outside the career at the higher cost; a
   talent's maximum; a career change's cost and whether the current level is
   complete.
2. Work out the XP cost from the library's advance cost table (an import must
   have confirmed it), given the number of advances already bought.
3. Show the cost and the new total, then write the advance into the record's
   `advances` with the session it was bought in, and update `xp.spent`.

Explain any rule that blocks a purchase and offer legal alternatives. If the GM
allows an exception, record it in `notes` and in `changelog`.

## Play-time changes

Wounds, Fortune and Resolve spent, Corruption points, mutations, conditions
that last between sessions, Critical Wounds, insanities, trappings gained or
lost, and money: write each to the record when the player or GM says so, with
a `changelog` line. Offer the Corruption test or mutation roll when the rules
call for one, but let the GM decide.

## Building the sheet

Read the record and every entry it points at, then write `<slug>.md`:
characteristics (initial, advances, current, bonus), career and level with
status, skills with their characteristic and advances, talents with their
taken count and a one-line summary in your words with a citation, spells,
trappings with encumbrance against the limit, Fate/Fortune/Resilience/Resolve,
wounds (worked out from the rules, with Hardy and other talents that change
them), movement, corruption and mutations, psychology, ambitions, XP current /
spent / total. Show anything still to settle from the record's `incomplete`
at the top. Show the numbers that changed since the last build, with the math
the first time.

For a new character, offer to add it to the campaign's `party` in
`campaign.json`.

## Checking a character

Asked "is this character legal?", rebuild it and check every choice and every
advance against the library, and the XP spent against the advance costs.
Report each problem with the rule that decides it, and change nothing until
the player or GM agrees.
