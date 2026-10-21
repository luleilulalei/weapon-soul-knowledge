#!/usr/bin/env python3
"""Verify portable knowledge records; does not test hardware or application behavior."""
from pathlib import Path
from urllib.parse import unquote, urlparse
import argparse
import hashlib
import json
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check-originals', action='store_true')
parser.add_argument('--check-delivery', action='store_true')
parser.add_argument('--report', action='store_true', help='Save a stable verification report')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
errors, warnings = [], []

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(name):
    return json.loads((root / name).read_text())

sources = read('90_来源/本地文件清单.json')
chats = read('90_来源/聊天覆盖清单.json')
assets = read('90_来源/V072交付附件清单.json')
snapshots = {r['snapshot']: r for r in sources + chats}
for name, row in snapshots.items():
    path = root / name
    if not path.is_file():
        errors.append('Missing evidence: ' + name)
    elif sha(path) != row['sha256']:
        errors.append('Evidence hash mismatch: ' + name)

originals_checked = 0
if args.check_originals:
    for row in sources:
        p = Path(row['original'])
        if not p.is_file():
            warnings.append('Original unavailable: ' + str(p))
        elif sha(p) != row['sha256']:
            warnings.append('Original changed since snapshot: ' + str(p))
        else:
            originals_checked += 1

delivery_checked = 0
if args.check_delivery:
    for row in assets:
        p = Path(row['destination'])
        if not p.is_file() or sha(p) != row['sha256']:
            errors.append('Delivery missing or changed: ' + str(p))
        else:
            delivery_checked += 1

canonical = [p for p in root.rglob('*.md')
             if '.git' not in p.parts and '文档快照' not in p.parts and '聊天摘录' not in p.parts]
links_checked = 0
pattern = re.compile(r'\[[^\]]+\]\((?:<([^>]+)>|([^\s)]+)(?:\s+"[^"]*")?)\)')
for p in canonical:
    content = p.read_text()
    if re.search(r'\[\[(.*?)\]\]', content):
        errors.append('Unresolved source reference: ' + str(p.relative_to(root)))
    for match in pattern.finditer(content):
        link = match.group(1) or match.group(2)
        if urlparse(link).scheme or link.startswith('#'):
            continue
        target = unquote(link.split('#', 1)[0])
        if not target:
            continue
        q = p.parent / target
        links_checked += 1
        if not q.exists():
            errors.append(f'Broken link in {p.relative_to(root)}: {target}')

for c in chats:
    if c['has_more']:
        warnings.append('Chat has unread pages: ' + c['id'])

# Check tracked and new files without staging them or changing the repository.
git = subprocess.run(['git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], capture_output=True)
if git.returncode:
    errors.append('Cannot enumerate Git files')
else:
    for raw in set(git.stdout.split(b'\0')):
        if not raw:
            continue
        rel = raw.decode()
        p = root / rel
        if p.is_file() and p.stat().st_size > 5 * 1024 * 1024:
            errors.append('Unexpected large repository file: ' + rel)
        if p.name == '.DS_Store' or p.suffix in {'.pem', '.key'} or p.name.startswith('.env'):
            errors.append('Unexpected local or credential file: ' + rel)

report = {
    'date': '2026-10-21',
    'scope': 'Knowledge links, archived evidence hashes, optional original/delivery consistency; not product verification',
    'status': 'passed' if not errors else 'failed',
    'local_source_paths': len(sources),
    'unique_document_snapshots': len(set(r['snapshot'] for r in sources)),
    'chat_snapshots': len(chats),
    'visible_turns': sum(r['turns'] for r in chats),
    'unavailable_cloud_assistant_references': sum(r['unavailable_assistant_references'] for r in chats),
    'canonical_markdown_files': len(canonical),
    'internal_links_checked': links_checked,
    'original_files_matching': originals_checked if args.check_originals else None,
    'delivery_files_matching': delivery_checked if args.check_delivery else None,
    'errors': errors,
    'warnings': warnings,
}
if args.report:
    (root / '99_维护/校验报告.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(bool(errors))
