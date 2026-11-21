---
name: wfrp-character-sheet
description: Create, advance, and look after Warhammer Fantasy Roleplay (4e) characters using the group's private library in Google Drive, checking every choice against the rules, and build a readable character sheet. Use when a player wants to make a character (random or chosen species, career and characteristics), spend XP, change career, record wounds, corruption, mutations or trappings, check a character is legal, or get a sheet to read or print.
---

# Character sheet

When an answer depends on a rule's exact wording, send it as a file, by default
and without asking, as layout §5 ("Exact wording") describes
(`scripts/excerpt.py`); never write the book's text into the reply.

Read `references/library-layout.md` for where data lives (§9 for characters),
and `references/character-record.md` before writing or changing a record.

## Storage

Each character lives in the campaign's `characters/` folder:

- `<slug>.json`: the **character record**, the source of truth. It holds only
  the character's choices and facts, each pointing at the library entry it
  comes from.
- `<slug>.md`: the readable sheet, built from the record and the library by
  `scripts/build_character.py`. Rebuild it whenever the record or the library
  changes. Never edit it by hand.

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
library, and the campaign's `creation` options (layout §8). The record is made
and filled in with `apply.py`, and `options.py` shows what is left to give:

```
python3 scripts/apply.py <slug>.json ... start --name "Ilsa" --species "High Elves" --origin Saphery --species-how chosen --career Mage --career-how rolled
python3 scripts/apply.py <slug>.json ... initial WS=40 BS=33 S=28 T=30 I=55 Ag=44 Dex=33 Int=50 WP=50 Fel=37 --how rearranged
python3 scripts/apply.py <slug>.json ... points --fate 1 --resilience 1
python3 scripts/apply.py <slug>.json ... buy --skill Cool --count 5 --how species
python3 scripts/apply.py <slug>.json ... buy --talent "Petty Magic" --how career
python3 scripts/options.py <slug>.json --library <root> --campaign <slug>
```

`start` and `initial` set the XP total to what the creation steps gave (the
creation rules' formulas; nothing when `starting_xp_bonus` is false). Each
`--how species` or `--how career` line is checked against the creation rules'
grants (ADR 0007): options.py's "Creation" lists, per grant, what is left, what
has been taken and the list it comes from, and the species' talents not yet
taken, and how many random talents are left to roll on their table (roll d100
on it, show the roll, and `buy --talent ... --how species` the result).

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
   wealth from the career level's status. While the record is being created,
   options.py lists them, each marked had or to add, with its choices ("Chalk
   or Chisel"), dice ("1d10 sheets of Parchment": roll for how many) and
   container, and the money roll. Add each with `apply.py ... item "Sling Bag"
   --id bag`, `item "Writing Kit" --in bag`, and the money with `money --ss 7`.
6. **Details**: name, age, height, eyes, hair, ambitions, and the party's
   ambitions (to `campaign.json`).
7. **Finish**: `apply.py ... finish` says what creation still had to give (a
   grant not used up, a trapping not taken, an empty purse) and ends creation.
   Go through what it lists with the player before building the sheet.

Use real dice for rolls the player makes, and read the row for their roll
with `--result`; when asked to roll for them, `roll.py` rolls and shows every
die:

```
python3 scripts/roll.py --library <root> --campaign <slug> table "Random Species"
python3 scripts/roll.py ... table "Random Class and Career" --column "High Elf" [--result 37]
python3 scripts/roll.py ... table "Random Talents"
python3 scripts/roll.py ... characteristics --species "High Elves"
python3 scripts/roll.py ... dice 6d10
```

Say which table was rolled on (the output cites it) and show the roll. The bonus XP isn't written by hand: `--species-how`,
`--career-how` and `initial --how` say how each step was settled, and the build
works it out. Creation XP is spent with `buy` (`--how xp`) on the first career
level's characteristics, skills and talents.

## Advancing

Asked what a character can buy, or what a level still needs:

```
python3 scripts/options.py <record>.json --library <root> --campaign <slug>
```

It lists the career's characteristics, skills and talents with the price of
the next advance in each, what completing the current level still needs and
the least XP that takes, and earlier levels left unfinished. Prices follow the
campaign's house rules where the builder has a setting for them. Anything
outside the career costs double and isn't listed: price it with a dry run.

For every purchase:

```
python3 scripts/apply.py <record>.json --library <root> --campaign <slug> --dry-run buy --skill "Lore (Reikland)" --count 2
python3 scripts/apply.py <record>.json ... buy --talent "Hardy" --session 7
python3 scripts/apply.py <record>.json ... buy --characteristic WP --count 5
python3 scripts/apply.py <record>.json ... buy --spell "Dart"
```

1. Run it with `--dry-run` first and show the player what it prints: the
   price, XP to spend before and after, the numbers that move, and anything
   the purchase brings with it (a talent past its Max, XP the character
   doesn't have, double price outside the career, a difference it clears).
2. For a talent, read its entry, and the entries the sheet says add to it,
   before saying it can be bought: the build knows prices and maximums, not
   the conditions written in a talent's text. If the talent changes a number
   and its entry carries no formula (the tool says so), follow
   `references/character-record.md`, "Effects on entries".
3. When the player agrees, run it again without `--dry-run`, with the
   `--session` it was bought in. It writes the line into `advances` and the
   `changelog`; never write a price by hand. Then rebuild the sheet.

Something given in play rather than bought is `--how free`, with `--notes`
saying why. `apply.py ... log "<text>"` adds a changelog line for anything else.

Explain any rule that blocks a purchase and offer legal alternatives. If the GM
allows it anyway, write it in the record's `exceptions` with the difference's
`id` and why, or, when the group plays it that way for everyone, as a house
rule in `campaign.json` (layout §8). The build then lists it as accepted.

## Play-time changes

Between adventures, Earning money tests the current career's
`earning_skill` (from the career entry) at the career level's status, as the
library's rules for Earning say.

Wounds, Fortune and Resolve spent, Corruption points, mutations, conditions
that last between sessions, Critical Wounds, insanities, trappings gained or
lost, and money: write each to the record when the player or GM says so, with
a `changelog` line. Offer the Corruption test or mutation roll when the rules
call for one, but let the GM decide.

## Building the sheet

```
python3 scripts/build_character.py <record>.json --library <root> --campaign <slug> --md --out <slug>.md
```

The script works out every number from the library (never do the sums by
hand, and never edit its output): characteristics and bonuses, career, level
and status, movement, Wounds, Fate and Resilience, the Corruption threshold,
Encumbrance, every basic skill and the advanced ones taken, talents with their
maximum, spells in the character's own numbers, trappings with weapon damage
and armour by location, and XP. Without `--md` it prints the same as JSON.
When the library is reached through the Drive connector, run
`scripts/needs.py` first: it lists the library files to fetch, all at once.

The sheet has three lists to go through with the player, and to mention every
time they aren't empty:

- **Differs from the rules**: each with its `id` and the rule. The build never
  alters the record to fit; the sheet shows what the record says.
- **To settle**: the record's `incomplete`.
- **Not worked out**: what the build couldn't do and why (an entry without a
  field it needs, a table that stops short, a price it can't read). Work those
  out from the library yourself, with citations, and say that you did.

After the sheet, add a one-line summary of each talent in your own words with
its citation, when the player asks for one.

For a sheet to print or keep beside the table:

```
python3 scripts/character_pdf.py <record>.json --library <root> --campaign <slug> --out <dir> --pdf
```

It writes `<slug>.html` and `<slug>.pdf` (two Letter pages): characteristics,
attributes, the career with what its earlier levels still need, skills and
talents on the first; weapons, armour, trappings, money, spells, ambitions,
psychology and the notes (differences, accepted ones and why, house rules,
what rules add, what wasn't worked out) on the second. Upload both beside the
record. Without a browser that prints (Playwright, Chrome, Edge or Chromium),
it says so: send the HTML and the player prints it from a browser.

## A character kept on a sheet

For a character someone has kept by hand in the group's spreadsheet, read it
with `scripts/read_sheet_export.py`, write the record from what it says
(`references/character-record.md`, "A character kept on a sheet"), and build
with `--shown` to list where the sheet's numbers and the rules' differ. Expect
differences: the table may play house rules nobody has written down. Report
them all, change nothing, and let the player and GM say which are mistakes,
which are exceptions and which are house rules.

For a new character, offer to add it to the campaign's `party` in
`campaign.json`.

## Checking a character

Asked "is this character legal?", rebuild it and report the build's
differences, each with the rule that decides it. Then check what the build
can't: read each talent's entry for conditions written in its text (a talent
that may be taken once whatever its specialisation, a prerequisite), together
with every entry the sheet lists under "Rules that add to these talents" (a
later book's change to the talent decides, not the talent's own text), and
that each talent that changes a number has its effect, on its entry or in the
record (the sheet's "What rules add" lists what was applied). What the species and
the first career gave at creation is checked against the grants on the creation
rules; where those carry none yet, the sheet says so, and you read the rules. Do the same before saying a
purchase is or isn't allowed. Change nothing until the player or GM
agrees.
