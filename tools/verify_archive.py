#!/usr/bin/env python3
"""Verify original-file bytes, image provenance, page previews, links, and Git coverage."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import base64
import hashlib
import json
import os
import subprocess

IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif'}

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def verify(root, check_originals=False, check_git=False):
    errors, warnings = [], []
    def read(p): return json.loads((root / p).read_text())
    manifest = read('90_来源/完整收录清单.json')
    images = read('90_来源/设计图清单.json')
    embedded = read('90_来源/原型内嵌图清单.json')
    docs = read('90_来源/文档提取清单.json')
    paths = [x['archive'] for x in manifest['items']]
    if len(paths) != len(set(paths)):
        errors.append('Duplicate archive path in manifest')
    original_matching = 0
    for x in manifest['items']:
        p = root / x['archive']
        if x['kind'] == 'symlink':
            if not p.is_symlink() or os.readlink(p) != x['link_target']:
                errors.append('Symlink mismatch: ' + x['archive'])
            continue
        if not p.is_file() or p.stat().st_size != x['bytes'] or sha(p) != x['sha256']:
            errors.append('Archive bytes mismatch: ' + x['archive'])
        if check_originals and not x.get('historical'):
            original = Path(x['original'])
            if not original.is_file():
                warnings.append('Original unavailable: ' + x['original'])
            elif sha(original) != x['sha256']:
                errors.append('Original differs from imported snapshot: ' + x['original'])
            else:
                original_matching += 1

    # Every project file under the user-specified source directory must be inventoried.
    source_root = Path('/Users/qijiankang/Documents/器灵')
    if check_originals and source_root.is_dir():
        expected = {x['original'] for x in manifest['items'] if x['group'] == '指定目录原件'}
        observed = set()
        for directory, dirs, files in os.walk(source_root):
            dirs[:] = [n for n in dirs if n not in {'.git', '__MACOSX'}
                       and Path(directory)/n != source_root/'知识库']
            for name in files:
                if name == '.DS_Store' or name.startswith('._'): continue
                observed.add(str(Path(directory)/name))
        for p in sorted(observed - expected): errors.append('Unarchived source file: ' + p)
        for p in sorted(expected - observed): errors.append('Source disappeared after inventory: ' + p)

    expected_images = {x['archive'] for x in manifest['items'] if Path(x['archive']).suffix.lower() in IMAGE_SUFFIXES}
    image_aliases = {z['path'] for x in images for z in x['aliases']}
    if not expected_images <= image_aliases:
        errors.append('Standalone images missing from gallery manifest')
    if not {x['path'] for x in embedded} <= image_aliases:
        errors.append('Embedded images missing from gallery manifest')
    for x in images:
        for a in x['aliases']:
            if not (root/a['path']).is_file() or sha(root/a['path']) != x['sha256']:
                errors.append('Image alias bytes mismatch: ' + a['path'])
        if not (root/x['thumbnail']).is_file():
            errors.append('Missing image thumbnail: ' + x['thumbnail'])

    # Read the JSON data in the archived prototype; never execute its scripts.
    prototypes = {}
    for x in embedded:
        if x['source'] not in prototypes:
            text = (root/x['source']).read_text()
            records = json.JSONDecoder().raw_decode(text.split('const screens=', 1)[1])[0]
            prototypes[x['source']] = {z['id']: z for z in records}
        data = base64.b64decode(prototypes[x['source']][x['screen_id']]['src'].split(',', 1)[1], validate=True)
        if hashlib.sha256(data).hexdigest() != x['sha256']:
            errors.append('Embedded image differs from prototype: ' + x['path'])
    for source, records in prototypes.items():
        expected_ids = {z['id'] for z in records.values() if z.get('src', '').startswith('data:image/')}
        actual_ids = {x['screen_id'] for x in embedded if x['source'] == source}
        if expected_ids != actual_ids: errors.append('Prototype screen coverage mismatch: ' + source)

    expected_docs = {x['archive'] for x in manifest['items'] if Path(x['archive']).suffix.lower() in {'.docx', '.pdf'}}
    if expected_docs != {p for d in docs for p in d['originals']}:
        errors.append('Word/PDF extraction coverage mismatch')
    for d in docs:
        for p in d['originals']:
            if sha(root/p) != d['original_sha256']: errors.append('Document origin mismatch: ' + p)
        if sha(root/d['text']) != d['text_sha256']: errors.append('Extracted text mismatch: ' + d['text'])
        if len(d['previews']) != d['pages']: errors.append('Document page count mismatch: ' + d['id'])
        for p in d['previews']:
            if not (root/p).is_file() or sha(root/p) != d['preview_sha256'][p]:
                errors.append('Document page preview mismatch: ' + p)
        if 'rendered_pdf' in d and sha(root/d['rendered_pdf']) != d['rendered_pdf_sha256']:
            errors.append('Word reading PDF mismatch: ' + d['rendered_pdf'])

    class Links(HTMLParser):
        def __init__(self): super().__init__(); self.targets = []
        def handle_starttag(self, tag, attrs):
            self.targets.extend(value for key, value in attrs if key in {'href', 'src'} and value)
    html_links = 0
    for p in (root/'82_设计图').rglob('*.html'):
        parser = Links(); parser.feed(p.read_text())
        for link in parser.targets:
            url = urlsplit(link)
            if url.scheme or url.netloc or not url.path: continue
            html_links += 1
            if not (p.parent/unquote(url.path)).exists():
                errors.append('Broken gallery link: ' + str(p.relative_to(root)) + ' -> ' + link)

    git_matching = 0
    if check_git:
        proc = subprocess.run(['git', '-C', str(root), 'ls-files', '-s', '-z'], capture_output=True, check=True)
        index = {}
        for raw in proc.stdout.split(b'\0'):
            if not raw: continue
            meta, name = raw.split(b'\t', 1)
            mode, oid, stage = meta.decode().split()
            index[name.decode()] = (mode, oid, stage)
        for x in manifest['items']:
            name = x['archive']
            if name not in index:
                errors.append('Original not tracked by Git: ' + name); continue
            data = (root/name).read_bytes() if x['kind'] == 'file' else x['link_target'].encode()
            oid = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            expected_mode = '120000' if x['kind'] == 'symlink' else ('100755' if x['mode'] & 0o111 else '100644')
            if index[name] != (expected_mode, oid, '0'):
                errors.append('Git does not store the exact original bytes/mode: ' + name)
            else: git_matching += 1
        for p in (root/'81_文档检索').rglob('*'):
            if p.is_file() and str(p.relative_to(root)) not in index:
                errors.append('Document output not tracked: ' + str(p.relative_to(root)))
        for p in (root/'82_设计图').rglob('*'):
            if p.is_file() and str(p.relative_to(root)) not in index:
                errors.append('Gallery output not tracked: ' + str(p.relative_to(root)))

    return {'archived_original_files': len(paths), 'archived_original_bytes': sum(x.get('bytes',0) for x in manifest['items']),
            'specified_directory_files': sum(x['group']=='指定目录原件' for x in manifest['items']),
            'preserved_prior_versions': sum(bool(x.get('historical')) for x in manifest['items']),
            'standalone_image_files': len(expected_images), 'extracted_prototype_images': len(embedded),
            'unique_design_images': len(images), 'unique_documents_extracted': len(docs),
            'document_preview_pages': sum(d['pages'] for d in docs), 'gallery_links_checked': html_links,
            'archive_originals_matching': original_matching if check_originals else None,
            'git_original_blobs_matching': git_matching if check_git else None,
            'errors': errors, 'warnings': warnings}

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check-originals', action='store_true')
    ap.add_argument('--check-git', action='store_true')
    args = ap.parse_args()
    report = verify(Path(__file__).resolve().parents[1], args.check_originals, args.check_git)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(bool(report['errors']))
