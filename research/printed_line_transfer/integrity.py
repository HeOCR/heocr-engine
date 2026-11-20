"""Fail closed on altered frozen crops, references, splits, PAGE files and base model."""
import hashlib
import json
import subprocess
from pathlib import Path

BASE_SHA = '0b5a0c3c0d66599095068f94234e86f563e17182a34b863d7e4941ef54b9e362'
FONTS = {'alef': 'a32adcc953ac356906901778460083dc207d4560cb586fd9ea24ec5b186969ed',
         'noto': '838341dcb5c33b3160dc6077637049fd9c49564323215e1e2754d6754bb1a463'}
LINE_FREEZE_SHA = '4853d5842c11606572a9bb9548d200fa0d51fbf5bd62e45f3f69ceca3be216e2'
PAGE_HASHES_SHA = '6f956ac0e5b9fdc0d2a57b4c27a2fbedebf23b2d5289a2b1d1c0b5ccad170f50'
GENERATOR_SHA = '7800e9f4500e6dcdbfe3b533f3bee6223206219b133c49c9a2b8bbeb265b744e'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generator_hash(source):
    root = source / 'hocrsyngen'
    files = sorted(f for f in root.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.suffix != '.pyc')
    digest = hashlib.sha256()
    for f in files:
        digest.update(str(f.relative_to(root)).encode() + b'\0' + bytes.fromhex(sha(f)))
    return digest.hexdigest()


def verify_fonts(root):
    for name, expected in FONTS.items():
        if sha(root / 'inputs' / 'fonts' / f'{name}.ttf') != expected:
            raise ValueError(f'{name} font hash mismatch')


def verify(root, require_xml=False):
    root = root.resolve()
    verify_fonts(root)
    freeze = root / 'line-freeze.json'
    if sha(freeze) != LINE_FREEZE_SHA or sha(freeze) != (root / 'line-freeze.sha256').read_text().strip():
        raise ValueError('line freeze hash mismatch')
    groups = json.loads(freeze.read_text())['splits']
    if set(groups) != {'train', 'validation', 'test'}:
        raise ValueError('unexpected split set')
    seen, text_by_split = set(), {}
    expected_xml = set()
    for split, rows in groups.items():
        images = []
        text_by_split[split] = set()
        for row in rows:
            image = (root / row['image']).resolve()
            label = (root / row['label']).resolve()
            if not image.is_relative_to(root / 'lines' / split) or not label.is_relative_to(root / 'lines' / split):
                raise ValueError('path outside split')
            if image in seen or label != image.with_suffix('.gt.txt'):
                raise ValueError('duplicate image or mismatched label')
            if sha(image) != row['image_sha256'] or sha(label) != row['label_sha256']:
                raise ValueError('crop or label changed')
            seen.add(image)
            images.append(image)
            text_by_split[split].add(label.read_text(encoding='utf-8'))
            expected_xml.add(image.with_suffix('.xml'))
        actual = {x.resolve() for x in (root / 'lines' / split).glob('*.png')}
        if actual != set(images) or (root / f'{split}.lst').read_text().splitlines() != [str(x) for x in images]:
            raise ValueError('crop set or list differs from freeze')
        if {x.resolve() for x in (root / 'lines' / split).glob('*.gt.txt')} != {x.with_suffix('.gt.txt') for x in images}:
            raise ValueError('label set differs from freeze')
        if require_xml and (root / f'{split}-xml.lst').read_text().splitlines() != [str(x.with_suffix('.xml')) for x in images]:
            raise ValueError('PAGE list differs from freeze')
    for a, b in [('train', 'validation'), ('train', 'test'), ('validation', 'test')]:
        if text_by_split[a] & text_by_split[b]:
            raise ValueError('cross-split text overlap')
    if require_xml:
        if sha(root / 'pagexml-hashes.json') != PAGE_HASHES_SHA:
            raise ValueError('PAGE hash receipt mismatch')
        xml = json.loads((root / 'pagexml-hashes.json').read_text())
        actual = {x.resolve() for x in (root / 'lines').rglob('*.xml')}
        if actual != expected_xml or set(xml) != {str(x.relative_to(root)) for x in expected_xml}:
            raise ValueError('PAGE set differs from freeze')
        if any(sha(root / name) != digest for name, digest in xml.items()):
            raise ValueError('PAGE XML changed')
    return groups


def tool_info(path, name):
    path = path.resolve()
    result = subprocess.run([str(path), '--version'], capture_output=True, text=True, timeout=20, check=True)
    version = result.stdout.strip()
    if version != f'{name}, version 7.0.2':
        raise ValueError(f'unsupported {name} version: {version}')
    return {'version': version, 'executable_sha256': sha(path)}
