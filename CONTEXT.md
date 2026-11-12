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
How one chapter splits into entries: which headings start entries, which category each section holds, and the decisions about same-named entries. Kept in Drive beside the source.
_Avoid_: Config, mapping

**Entry**:
One imported game item, such as a career, talent, spell, creature, rule, or table, along with the source, chapter, section and page it came from.
_Avoid_: Record, item

**Relation**:
How an entry relates to an entry of the same name elsewhere: it *adds to* it, *replaces* it, is a *reprint of* it, or is *distinct from* it. An older edition's entry can be *updated by* a newer edition's. An entry can also *count as* another for rules purposes.
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

**Party ambitions**:
The short- and long-term goals the party sets together, alongside each character's own ambitions.
