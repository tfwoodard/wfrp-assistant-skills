# Plan packs

Chapter plans for the WFRP 4e books, with **no text from the books in them**.
A pack says how a chapter of a book splits into library entries: which headings
start an entry, which pages hold which tables, what kind of rule each entry is.
Every name and heading is a fingerprint (a hash), which the import tool turns
back into text from **your own copy** of the book. Without the book, a pack is
page numbers and hashes.

This is an unofficial, fan-made, non-commercial project, not affiliated with
Games Workshop or Cubicle 7. Warhammer Fantasy Roleplay is a trademark of
Games Workshop. You need to own the books.

## Layout

```
packs/<source>/<first 12 characters of the PDF's SHA-256>/edition.json
packs/<source>/<first 12 characters of the PDF's SHA-256>/<chapter>.json
```

Packs are kept by the exact PDF they were made from, because a corrected or
reprinted PDF can move headings and pages. `edition.json` gives that PDF's
SHA-256, its size in bytes and the book's title, and lists its chapters. A
newer PDF of the same book gets a folder of its own beside the old one.

## Using them

The `wfrp-import` skill does this for you: before it plans a chapter, it runs
`plan_pack.py find` on your PDF and offers the matching pack. By hand:

```
python3 skills/wfrp-import/scripts/plan_pack.py find YOUR.pdf --packs packs/ --source CRB
python3 skills/wfrp-import/scripts/plan_pack.py layout_command packs/CRB/<folder>/ch5.json --pdf YOUR.pdf
#   run the command it prints, to read your copy's pages the way the pack expects
python3 skills/wfrp-import/scripts/plan_pack.py install packs/CRB/<folder>/ch5.json ch5-layout.json \
    --out ch5-plan.json --pdf YOUR.pdf --library-data <your library-data>
```

Install lists anything it couldn't rebuild from your copy. A pack never holds
formulas, summaries or other rules text: your Librarian writes those for your
own library.
