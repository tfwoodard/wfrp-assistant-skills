# PDFs are read by layout, not as flat text

The DnD Assistant first imported from flattened page text. It dropped heading
levels, ran table columns together and couldn't tell a list's last item from
the heading after it, so every chapter needed hand-split tables and heuristics
that kept breaking (its ADR 0003). It only became reliable once the importer
read the source's real structure.

WFRP's PDFs are two-column pages with sidebars, boxed career schemes, stat
lines, and tables, which flat extraction mangles the same way. So the import
reads each page as text spans with position, font, size and weight
(`pdf_layout.py`, on pdfplumber), orders them by column, and finds headings
from font size and weight. Each kind of chapter (careers, talents, spells,
bestiary) gets a converter that builds entries from those lines and a plan,
with tests on an invented PDF.

When a page's structure can't be read from its text (a table drawn as art),
Claude looks at the page image, transcribes it, and records that in the
chapter's notes.

## Considered Options

- **Flat text with heuristics.** Rejected: the lesson above.
- **OCR every page.** Rejected: the books have a text layer, and OCR adds
  errors to wording the library must keep exactly. OCR only for scanned PDFs,
  and only after asking.
- **Use a community data set (e.g. a VTT module's JSON).** Rejected as a base:
  its wording and structure aren't the book's, and the group plays by the books.
  It may still be a useful cross-check.
