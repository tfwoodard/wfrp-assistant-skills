# Homebrew is written in a library document

Carried over from the DnD Assistant (its ADR 0004). The master copy of a
group's homebrew is a **homebrew document**: one Markdown file per scope (the
library, a campaign, or a campaign's GM-only material), kept in that scope's
`sources/` folder in Drive and imported like any other source. Each `#` heading
is a chapter (Careers, Talents, Spells…), and entries are written the way the
books write them, so the same converters and checks apply. Changing a homebrew
entry means editing the document and importing that chapter again.

## Considered Options

- **Write the entries' JSON directly, with no source document.** Rejected:
  every other entry traces back to a source, the import's checks would be
  skipped, and editing JSON by hand is error-prone for a GM.
- **One document per item or per kind.** Rejected for now: one document per
  scope is one file to find and one `campaign_sources` entry, and chapters
  already allow importing one kind at a time.
