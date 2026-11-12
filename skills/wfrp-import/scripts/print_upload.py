#!/usr/bin/env python3
"""Print files for upload through the Drive connector, in parts that fit a tool result.

The Drive connector takes a file's text inline, so each file has to be read
into the conversation before it is uploaded. A plain `cat` of a large file is
cut off, and it doesn't show whether the file ends with a newline (the usual
cause of an upload that comes out one byte short). This prints each file
between markers with its byte size and final-newline state, splits files that
are too big at line boundaries, and packs small files together, so every part
fits in one tool result.

    print_upload.py FILE [FILE ...] [--max-chars 25000] [--part N]
    print_upload.py FILE [FILE ...] --list

Upload the text between a file's BEGIN and END markers exactly, joining its
parts in order. If the header says "ends with newline: yes", the uploaded text
must end with a newline. Then check that Drive's fileSize equals the bytes in
the header.
"""
import argparse
import os
import sys


def chunks_for(path, max_chars):
    with open(path, encoding='utf-8', newline='') as f:
        text = f.read()
    size = len(text.encode('utf-8'))
    ends_nl = text.endswith('\n')
    lines = text.splitlines(keepends=True)
    groups, cur, cur_len, start = [], [], 0, 1
    for i, line in enumerate(lines, 1):
        if cur and cur_len + len(line) > max_chars:
            groups.append((start, i - 1, ''.join(cur)))
            cur, cur_len, start = [], 0, i
        cur.append(line)
        cur_len += len(line)
    if cur or not groups:
        groups.append((start, start + len(cur) - 1, ''.join(cur)))
    name = os.path.basename(path)
    out = []
    for k, (a, b, body) in enumerate(groups, 1):
        head = (f'=== BEGIN {name} | part {k}/{len(groups)} | lines {a}-{b} of {len(lines)} | '
                f'{size} bytes | ends with newline: {"yes" if ends_nl else "no"} ===\n')
        if not body.endswith('\n'):
            body += '\n'  # marker on its own line; the header records the real ending
        out.append(head + body + f'=== END {name} | part {k}/{len(groups)} ===\n')
    return name, size, ends_nl, len(lines), out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    p.add_argument('files', nargs='+')
    p.add_argument('--max-chars', type=int, default=25000,
                   help='largest part to print (default 25000, which fits a tool result)')
    p.add_argument('--part', type=int, default=1, help='which part to print (default 1)')
    p.add_argument('--list', action='store_true', help='only list sizes and part counts')
    a = p.parse_args(argv)

    pages, page = [], ''
    summary = []
    for path in a.files:
        name, size, ends_nl, nlines, chunks = chunks_for(path, a.max_chars)
        summary.append((name, size, ends_nl, nlines, len(chunks)))
        for c in chunks:
            if page and len(page) + len(c) > a.max_chars:
                pages.append(page)
                page = ''
            page += c
    if page:
        pages.append(page)

    if a.list:
        for name, size, ends_nl, nlines, n in summary:
            print(f'{name}\t{size} bytes\t{nlines} lines\tends with newline: '
                  f'{"yes" if ends_nl else "no"}\t{n} part(s)')
        print(f'{len(pages)} print part(s) at --max-chars {a.max_chars}')
        return 0
    if not 1 <= a.part <= len(pages):
        print(f'--part must be 1..{len(pages)}', file=sys.stderr)
        return 2
    sys.stdout.write(pages[a.part - 1])
    nxt = f'; next: --part {a.part + 1}' if a.part < len(pages) else '; that was the last part'
    print(f'--- print part {a.part} of {len(pages)}{nxt} ---')
    return 0


if __name__ == '__main__':
    sys.exit(main())
