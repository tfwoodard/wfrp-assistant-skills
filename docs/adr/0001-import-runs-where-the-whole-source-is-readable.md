# Importing runs wherever the whole source can be read

Carried over from the DnD Assistant (its ADR 0001), and more central here:
WFRP's books are PDFs, and the Google Drive connector can't read a whole
rulebook-sized PDF or pick out a page range. So importing a PDF runs where the
full file is on disk: Claude Code on the Librarian's computer (through Google
Drive for desktop), or a cloud session linked to that computer with the
library folder connected. Small files and Google Docs import through the
connector from anywhere. Every other skill (lookups, characters, sessions) uses
only the connector or the local folder, so play-time use works from any
device, including a phone.

## Considered Options

- **Split PDFs into chapter files** so everything fits the connector. Rejected:
  it pushes tedious prep onto the Librarian for every book, and the split files
  are more copies of the book to keep private.
- **Upload the PDF into the conversation.** Rejected as the default: it works
  for a one-off, but the import's scripts need the file on disk, and a large
  rulebook is past upload limits.
