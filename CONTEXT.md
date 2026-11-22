# WFRP Assistant

Skills that help a group run Warhammer Fantasy Roleplay (4th edition) at the table, using game material the group owns, kept in a private library.

## Language

### Importing

**Import**:
Turning a source into entries in the library data.
_Avoid_: Ingest, extract, parse

**Source**:
A document that entries are imported from: a rulebook or supplement PDF, an adventure, or a homebrew document.
_Avoid_: Book (when homebrew is meant)

**Library source**:
A source imported by the Librarian into the shared library, available to any campaign that puts it in play.

**Campaign source**:
A source imported by a campaign's GM into that campaign only, such as a published adventure or the GM's own homebrew. Other campaigns never see it.
_Avoid_: Private source

**Sources in play**:
The ordered list of sources a campaign uses.
_Avoid_: Enabled books, allowed books

**Edition**:
The WFRP edition a source was written for (4e, 2e, 1e), and the edition a campaign plays by.
_Avoid_: Version, ruleset

**Chapter**:
One part of a source, as listed in its table of contents, with its printed page range. A chapter is imported in one go and tracked as not imported, imported, or imported with problems.
_Avoid_: Section, page (as the unit of import)

**Plan**:
How the import reads one chapter: which headings start entries, which category each section holds, and (for now) the decisions about same-named entries. A helper for importing only: nothing reads it at runtime, and content such as formulas is never kept in it. Kept in Drive beside the source.
_Avoid_: Config, mapping

**Version**:
One of two or more entries for the same thing in different sources (a weapon as the Rulebook prints it and as a supplement revises it), joined by a *version-of* mark. A campaign uses the version from the source that comes first in its sources.
_Avoid_: Override, duplicate

**Entry**:
One imported game item, such as a career, talent, spell, creature, rule, or table, along with the source, chapter, section and page it came from.
_Avoid_: Record, item

**Relation**:
How an entry relates to an entry of the same name elsewhere: it *adds to* it, is a *version of* it, is a *reprint of* it, or is *distinct from* it. An older edition's entry can be *updated by* a newer edition's. An entry can also *count as* another for rules purposes.
_Avoid_: Override (as the general term), duplicate

**Audience**:
Who an entry is for: everyone, or only the GM.
_Avoid_: Visibility (that's for campaign sources)

**Homebrew document**:
A Markdown source the group writes in Drive to hold its own homebrew, one per scope (the library, a campaign, or a campaign's GM-only material). It is the master copy.

**Cross-reference**:
A table the Librarian builds to link names or entries across sources, citing where each one appears. It belongs to no source.

**Library data**:
All the entries imported into the library.

### People

**Librarian**:
The one person who maintains the library: imports library sources, corrects entries, and sets library-wide house rules.
_Avoid_: Owner, admin, GM (when the library role is meant)

**GM**:
The Games Master of one campaign, who controls that campaign's configuration, campaign sources, and GM-only notes.
_Avoid_: DM, owner

**Player**:
A member of the group who plays a character in a campaign.
_Avoid_: User

### Characters

**Character record**:
The JSON file that holds everything about one character in a campaign: their choices and facts, each pointing at the library entry it comes from. The readable sheet is generated from it.
_Avoid_: Character file, sheet (when the data is meant)

**Career**:
One of the game's careers (Rat Catcher, Witch Hunter), with its class and four levels. A character is in one career at a time, at one of its levels.
_Avoid_: Class (that's the career's group: Peasants, Warriors…), job

**Career level**:
One of a career's four steps (Rat Hunter, Rat Catcher, Sewer Jack, Exterminator), with its status and the characteristics, skills, talents and trappings it lets a character advance or needs.
_Avoid_: Rank, tier

**Advance**:
One purchase of experience: a characteristic or skill advance, a talent taken, or a career change.
_Avoid_: Level-up

**Effect**:
What a rule does to one of a character's numbers (a talent that adds to Wounds or to a starting characteristic), written as a formula on the entry that says so, or in the character record for a one-off case, because the builder can't read a rule's text.
_Avoid_: Modifier, bonus (a characteristic's bonus is its tens digit)

**Formula**:
An effect, a check or a grant written on the entry that states the rule, in a small fixed vocabulary, for the builder to evaluate. A reading of the entry's text, confirmed by the Librarian; the text stays the authority.
_Avoid_: Script, code, automation

**Grant**:
What a creation rule gives a new character to share out (so many skills at so many advances, so many advances in all, one talent), and from which list: the species' or the first career level's. Advances recorded as gained from the species or the career at creation are checked against the grants (ADR 0007).
_Avoid_: Allowance, budget

**Note**:
One thing the group needs to remember now (an NPC's name, a place, an item, a faction, a thread, a fact), in the campaign notebook (`notes.json`). While it matters it prints on the sheets, the party's on every one and a character's own on theirs; once it doesn't it is *retired*: kept in the notebook and in searches, gone from the sheets.
_Avoid_: Reminder, memo

**History** (of a campaign):
The scraps remembered from sessions nobody wrote up, in `sessions/history.md`: only what someone remembers, each scrap with its session when known.
_Avoid_: Backfill, reconstructed sessions

**Elder**:
A character older than its species' usual age, born in an earlier *Time* of the rule's table. Each Time lived through gives an earlier career (advances on its first level's skills) and a burden. The record says when the Elder was born and which careers they followed; the rule's entry says the rest (ADR 0008).
_Avoid_: Veteran, old character

**Summary**:
One line in Claude's own words of what an entry does, written on the entry (`fields.summary`) for the printed sheet, so a spell's or talent's effect is at hand without the book. Never the book's sentences. A talent whose specialisations are different benefits has one more line per specialisation (`fields.summaries`), printed after the shared one for the specialisation taken. Kept on re-import like a formula.
_Avoid_: Description, blurb, abstract

**Difference**:
A place where a character record and the rules disagree, found by the builder and given an id. It is reported, never corrected.
_Avoid_: Error, violation, illegal

**Exception**:
A difference the group has accepted for one character, written in the character record with why. A house rule accepts a difference for every character in a campaign.
_Avoid_: Override, waiver

**Party ambitions**:
The short- and long-term goals the party sets together, alongside each character's own ambitions.
