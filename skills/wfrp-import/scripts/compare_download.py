#!/usr/bin/env python3
"""Check a file downloaded from Drive against the local copy it should match.

After correcting a library file (SKILL.md, "Correcting a file already on
Drive"), upload it, download the new Drive file, save the download, and run:

    compare_download.py LOCAL DOWNLOAD [--original ORIGINAL]

DOWNLOAD may be the connector's whole download result saved as JSON, its
base64 `content`, or the decoded file. The two must be byte for byte the same;
otherwise the differing lines are printed and the exit status is 1. Copying a
download by hand can slip, so a mismatch means: check the copy of the download
first, then the upload.

With --original (the file as it was before the edit), it also prints which
lines the edit changed, so you can confirm they're only the ones you meant.
"""
import argparse
import base64
import binascii
import difflib
import json
import re
import sys


def read_download(path):
    with open(path, 'rb') as f:
        raw = f.read()
    text = raw.decode('utf-8', errors='replace').strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get('content'), str):
            return base64.b64decode(data['content'], validate=True)
    except (ValueError, binascii.Error):
        pass
    if text and re.fullmatch(r'[A-Za-z0-9+/\s]+=*', text) and len(re.sub(r'\s', '', text)) % 4 == 0:
        try:
            return base64.b64decode(re.sub(r'\s', '', text), validate=True)
        except binascii.Error:
            pass
    return raw


def lines(b):
    return b.decode('utf-8', errors='replace').splitlines(keepends=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('local', help='the file that was uploaded')
    ap.add_argument('download', help='the download of the uploaded Drive file')
    ap.add_argument('--original', help='the file before the edit, to list the intended changes')
    a = ap.parse_args()

    with open(a.local, 'rb') as f:
        local = f.read()
    got = read_download(a.download)

    if a.original:
        with open(a.original, 'rb') as f:
            orig = f.read()
        changed = [l for l in difflib.unified_diff(lines(orig), lines(local), 'original', 'edited', n=0)
                   if l[:1] in '+-' and not l.startswith(('+++', '---'))]
        print(f'The edit changed {len(changed)} line(s):')
        for l in changed:
            print('  ' + l.rstrip('\n'))

    if got == local:
        print(f'Identical: the download matches {a.local} ({len(local)} bytes).')
        return
    print(f'DIFFERENT: download {len(got)} bytes, local {len(local)} bytes.')
    sys.stdout.writelines(difflib.unified_diff(lines(local), lines(got), 'local', 'download', n=1))
    sys.exit(1)


if __name__ == '__main__':
    main()
