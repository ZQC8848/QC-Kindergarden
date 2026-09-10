#!/usr/bin/env python3
"""Work out which chat-history records the next qc-taste update should read.

Run from the repository root:  python tools/taste_scan.py [--json]

Update mode used to say "read conversations since `evidence_through`", which is a date.
That silently skips a record whose session started before the cursor but was archived
after it — exactly what happened on 2026-09-09, when a 09-07 methodology session was
exported two days later and a date cursor would have ignored it forever.

So the cursor is per file instead: `consumed_records` in taste-rules.yaml stores each
archive's path, sha256 and line count at the time it was mined. A file is in scope when

  * its path is not in the list at all  -> read the whole file, or
  * its sha256 differs from the record  -> read from the recorded line count onward
    (exports grow: a session archived mid-run is re-exported later with more turns).

Two streams are scanned. ai-chat-history is where QC's seeds and instructions live;
story-candidates is where the review pipeline's verdicts land, and `rejected` is the
heaviest evidence type the protocol recognises. Each judged round counts as one record.

Exit code 0 always; this reports, it never decides. Finding nothing in scope is a normal
outcome and means the update may legitimately stop there.

Requires no dependencies: the YAML it reads is a fixed shape written by this project.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / '.agents' / 'skills' / 'qc-taste' / 'references' / 'taste-rules.yaml'
HISTORY = ROOT / 'ResearchAssets' / 'ai-chat-history'
CANDIDATES = ROOT / 'ResearchAssets' / 'story-candidates'


def digest_round(d: Path):
    """Fingerprint a whole review round: every candidate file plus round.json.

    Rounds are the second evidence stream, and the one the story pipeline exists to
    produce. `rejected` is the heaviest evidence type in the protocol, and until this
    was added the cursor could not see a single one of them: it scanned only
    ai-chat-history, so six fully tagged rejections read as "nothing new".

    A round re-fingerprints whenever any verdict changes, which is what should bring it
    back into scope — a round is only worth mining once QC has judged it.
    """
    crlf, lf = b'\r\n', b'\n'
    blob = b''.join(p.read_bytes().replace(crlf, lf) for p in sorted(d.iterdir()) if p.is_file())
    return hashlib.sha256(blob).hexdigest(), len(list(d.glob('c-*.md')))


def digest(path: Path):
    """(sha256, line count) of a text record, hashed on LF-normalised bytes.

    Normalising matters: without it a CRLF checkout changes every byte, every record
    reports as `changed`, and the whole archive comes back into scope on a machine that
    merely has a different core.autocrlf.
    """
    data = path.read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest(), data.count(b'\n') + (0 if data.endswith(b'\n') else 1)


def consumed():
    """Parse the `consumed_records:` block. Deliberately narrow: one shape, loudly checked."""
    if not RULES.exists():
        sys.exit(f'[taste-scan] not found: {RULES.relative_to(ROOT)}')
    text = RULES.read_text(encoding='utf-8')
    block = re.search(r'^consumed_records:\s*$(.*?)(?=^\S|\Z)', text, re.S | re.M)
    if not block:
        sys.exit(
            '[taste-scan] no `consumed_records:` block in taste-rules.yaml. '
            'The incremental cursor is required; see references/update-protocol.md.'
        )
    records = {}
    for entry in re.finditer(
        r'-\s+path:\s*"([^"]+)"\s*\n\s+sha256:\s*"([0-9a-f]{64})"\s*\n\s+lines:\s*(\d+)', block.group(1)
    ):
        records[entry.group(1)] = {'sha256': entry.group(2), 'lines': int(entry.group(3))}
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true', help='machine-readable output')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    seen = consumed()
    scope, unchanged, missing = [], [], []

    records = [(p, digest) for p in sorted(HISTORY.glob('*.md')) if p.name != 'README.md']
    records += [(d, digest_round) for d in sorted(CANDIDATES.glob('*-r*')) if d.is_dir()]

    for path, fingerprint in records:
        rel = path.relative_to(ROOT).as_posix()
        sha, lines = fingerprint(path)
        record = seen.get(rel)
        if record is None:
            scope.append({'path': rel, 'reason': 'new', 'from_line': 1, 'to_line': lines})
        elif record['sha256'] != sha:
            # Re-exported. Only the appended turns are unread; earlier lines may have been
            # rewritten too, which is why the reason is reported rather than assumed benign.
            scope.append(
                {
                    'path': rel,
                    'reason': 'changed',
                    'from_line': min(record['lines'] + 1, lines),
                    'to_line': lines,
                    'was_lines': record['lines'],
                }
            )
        else:
            unchanged.append(rel)

    for rel in seen:
        if not (ROOT / rel).exists():
            missing.append(rel)

    if args.json:
        print(json.dumps({'in_scope': scope, 'unchanged': unchanged, 'missing': missing}, ensure_ascii=False, indent=2))
        return 0

    if not scope:
        print(f'[taste-scan] nothing new: {len(unchanged)} record(s) already mined.')
        print('  No update is required. Stopping here is a valid outcome.')
    else:
        print(f'[taste-scan] {len(scope)} record(s) in scope:')
        for item in scope:
            unit = 'candidates' if '/story-candidates/' in item['path'] else 'lines'
            span = (f"{item['to_line']} {unit}" if unit == 'candidates'
                    else f"lines {item['from_line']}-{item['to_line']}")
            extra = f" (was {item['was_lines']} {unit})" if item['reason'] == 'changed' else ''
            print(f"  {item['reason']:8} {item['path']}  {span}{extra}")
        print(f'\n  {len(unchanged)} record(s) already mined, skipped.')
    if missing:
        print('\n  recorded but no longer on disk (renamed or deleted?):')
        for rel in missing:
            print(f'    {rel}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
