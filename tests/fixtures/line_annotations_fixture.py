"""Hand-made hocrsyngen_line_annotations.v1 fixture: original synthetic pixels and project-written lines.

Images are generated at test time, so no image is committed. Lines mix Hebrew with digits, Latin
and brackets to exercise bidi handling.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

WIDTH, HEIGHT = 240, 160
# Physical lines as (text, logical_line_index, logical_join, occluded). A body line may wrap ("space"),
# a ledger row is drawn as separate cells ("cell"), and a stamp is drawn but absent from logical_order.
SAMPLES = (
    ("printed_letter", [("שלום עולם", 0, None, False), ("סימן 96", 1, None, False)]),
    ("printed_form", [('התשלום (שולם) בסך 1,250.50 ש"ח', 0, None, False),
                      ("קובץ report.pdf נשלח", 1, None, True), ("אישור", None, None, True)]),
    ("handwritten_note", [("א-ב: 12/03/2024", 0, None, False), ("אותיות סופיות", 1, None, False),
                          ("ךםןףץ", 1, "space", False)]),
    ("ledger", [("פריט 3", 0, None, False), ("מתוך 7", 0, "cell", False), ("סוף הרשימה.", 1, None, False)]),
)
JOINERS = {"space": " ", "cell": " | "}


def logical_order(lines) -> str:
    rows: dict[int, str] = {}
    for text, logical, join, _ in lines:
        if logical is not None:
            rows[logical] = rows[logical] + JOINERS[join] + text if join else text
    return "\n".join(rows[index] for index in sorted(rows))


def line_geometry(index: int) -> tuple[list[list[int]], list[list[int]]]:
    top = 10 + index * 40
    polygon = [[20, top], [220, top], [220, top + 30], [20, top + 30]]
    baseline = [[20, top + 24], [220, top + 24]]
    return polygon, baseline


def build_batch(root: Path, samples=SAMPLES) -> tuple[Path, Path]:
    """Write assets, generation_manifest.json and line_annotations.json under `root`."""
    manifest = {"manifest_version": "fixture", "samples": []}
    pages = []
    for number, (template, lines) in enumerate(samples):
        sample_id = f"fixture-s00000007-{number:06d}"
        page_id = f"{sample_id}-page-0001"
        asset = f"assets/{sample_id}/page_0001.png"
        image = Image.new("L", (WIDTH, HEIGHT), 255)
        draw = ImageDraw.Draw(image)
        for index in range(len(lines)):
            polygon, _ = line_geometry(index)
            draw.rectangle([polygon[0][0] + 5 * number, polygon[0][1] + 8, polygon[2][0] - 10, polygon[2][1] - 6],
                           fill=40 + 10 * index)
        path = root / asset
        path.parent.mkdir(parents=True)
        image.save(path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["samples"].append({"sample_id": sample_id, "provenance": {"template_id": template, "seed": 7},
                                    "text": {"logical_order": logical_order(lines), "unicode_normalization": "NFC"},
                                    "pages": [{"page_id": page_id, "asset_path": asset, "sha256": sha,
                                               "width": WIDTH, "height": HEIGHT, "media_type": "image/png"}]})
        pages.append({"sample_id": sample_id, "page_id": page_id, "page_sha256": sha, "width": WIDTH,
                      "height": HEIGHT, "lines": [
                          {"line_index": index, "region": "stamp" if logical is None else "body", "text": text,
                           "polygon": line_geometry(index)[0], "baseline": line_geometry(index)[1],
                           "logical_line_index": logical, "logical_join": join, "occluded": occluded}
                          for index, (text, logical, join, occluded) in enumerate(lines)]})
    manifest_path = root / "generation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    annotations = {"schema": "hocrsyngen_line_annotations.v1",
                   "generation_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                   "coordinate_space": "final_page_pixels", "pages": pages}
    annotations_path = root / "line_annotations.json"
    annotations_path.write_text(json.dumps(annotations, ensure_ascii=False, indent=2), encoding="utf-8")
    return annotations_path, manifest_path


FAKE_KETOS = """#!{python}
import json, os, re, sys
from pathlib import Path
args = sys.argv[1:]
if os.environ.get('FAKE_KETOS_CALLS'):
    with open(os.environ['FAKE_KETOS_CALLS'], 'a', encoding='utf-8') as stream:
        stream.write(json.dumps(args) + '\\n')
if args == ['--version']:
    print('ketos, version 7.0.2')
    sys.exit(0)
if 'compile' in args:
    listing = Path(args[args.index('-F') + 1]).read_text(encoding='utf-8').splitlines()
    lines = sum(Path(path).read_text(encoding='utf-8').count('<TextLine ') for path in listing)
    Path(args[args.index('-o') + 1]).write_text(json.dumps({{'lines': lines}}), encoding='utf-8')
    sys.exit(0)
work = Path(args[-1]).parent
train = json.loads(Path(args[-1]).read_text(encoding='utf-8'))['lines']
validation = json.loads((work / 'validation.arrow').read_text(encoding='utf-8'))['lines']
print(f"Training set {{train - int(os.environ.get('FAKE_KETOS_DROP', '0'))}} lines, validation set {{validation}} "
      "lines, alphabet 41 symbols", file=sys.stderr)
checkpoints = Path(args[args.index('-o') + 1])
checkpoints.mkdir()
# Shaped like ketos 7.0.2 -v output and files; its weights metadata keeps no metrics.
for epoch, errors in enumerate((300, 179, 179)):
    print(f'[11/02/26 06:52:34] INFO     validation run: total chars 358.0 errors {{errors}}.0 accuracy '
          f'{{1 - errors / 358}}      vgsl.py:352', file=sys.stderr)
    (checkpoints / f'checkpoint_{{epoch:02d}}-{{1 - errors / 358:.4f}}.ckpt').write_bytes(b'checkpoint')
meta = {{'0f': {{'_tasks': ['recognition'], '_model': 'TorchVGSLModel', 'metrics': [], 'accuracy': []}}}}
header = json.dumps({{'__metadata__': {{'kraken_meta': json.dumps(meta)}}}}).encode()
(checkpoints / 'best_0.5000.safetensors').write_bytes(len(header).to_bytes(8, 'little') + header + b'weights')
# Real ketos 7.0.2 builds EarlyStopping without verbose=True and logs no stop message; FAKE_KETOS_QUIET mimics it.
if not os.environ.get('FAKE_KETOS_QUIET'):
    print('Monitored metric val_accuracy did not improve in the last 10 records. Signaling Trainer to stop.',
          file=sys.stderr)
sys.exit(int(os.environ.get('FAKE_KETOS_EXIT', '0')))
"""


def write_fake_ketos(path: Path, python: str) -> Path:
    path.write_text(FAKE_KETOS.format(python=python), encoding="utf-8")
    path.chmod(0o755)
    return path
