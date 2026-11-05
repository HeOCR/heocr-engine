import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent / 'fixtures'))
from line_annotations_fixture import SAMPLES, build_batch, write_fake_ketos  # noqa: E402

from heocr_engine.cli import EngineError, main  # noqa: E402
from heocr_engine.kraken import KrakenRecognizer  # noqa: E402
from heocr_engine.training import (BASE_DIR, Hyperparameters, MIX_ASSIGNMENT, MIX_BUCKETS,  # noqa: E402
                                   MIX_GEOMETRIES, MIX_SHARES, PAGE_NS, POLYGONIZER_HEIGHT, RECT_PAD,
                                   TRAINING_SCHEMA_ID, assign_splits, load_annotated_pages, mix_assignment,
                                   mix_geometry, mix_shares, prepare_kraken_data, rect_polygon,
                                   safetensors_kraken_metadata, train_kraken, validate_training_run)

R3H_BUCKETS = ('kraken',) * 6 + ('sidecar', 'rect')

HAS_KRAKEN = importlib.util.find_spec('kraken') is not None
NS = {'p': PAGE_NS}


class TrainingTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.batch = self.root / 'batch'
        self.annotations, self.manifest = build_batch(self.batch)

    def rewrite(self, change, manifest=False):
        """Apply `change` to the annotations (or manifest) JSON and keep the manifest hash consistent."""
        path = self.manifest if manifest else self.annotations
        document = json.loads(path.read_text(encoding='utf-8'))
        change(document)
        path.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
        if manifest:
            annotations = json.loads(self.annotations.read_text(encoding='utf-8'))
            annotations['generation_manifest_sha256'] = hashlib.sha256(self.manifest.read_bytes()).hexdigest()
            self.annotations.write_text(json.dumps(annotations, ensure_ascii=False), encoding='utf-8')


class ConverterTests(TrainingTestCase):
    def test_page_xml_round_trips_text_and_geometry(self):
        out = self.root / 'data'
        summary = prepare_kraken_data(self.annotations, self.manifest, out, validation_fraction=0.25)
        source = json.loads(self.annotations.read_text(encoding='utf-8'))
        for page in source['pages']:
            xml_path = out / 'pages' / (page['page_sha256'] + '.xml')
            tree = ET.parse(xml_path)
            element = tree.find('p:Page', NS)
            self.assertEqual(element.get('readingDirection'), 'right-to-left')
            self.assertTrue((out / 'pages' / element.get('imageFilename')).is_file())
            lines = tree.findall('.//p:TextLine', NS)
            self.assertEqual(len(lines), len(page['lines']))
            for line, expected in zip(lines, page['lines']):
                # Text stays in logical order; ketos does the display reordering itself.
                self.assertEqual(line.find('p:TextEquiv/p:Unicode', NS).text, expected['text'])
                points = lambda tag: [[int(v) for v in p.split(',')]  # noqa: E731
                                      for p in line.find(tag, NS).get('points').split()]
                self.assertEqual(points('p:Coords'), expected['polygon'])
                self.assertEqual(points('p:Baseline'), expected['baseline'])
        self.assertEqual(summary['train']['samples'] + summary['validation']['samples'], len(SAMPLES))
        self.assertEqual(summary['validation']['samples'], 1)
        self.assertEqual(summary['train']['lines'] + summary['validation']['lines'],
                         sum(len(lines) for _, lines in SAMPLES))
        # Stamp text outside logical_order is real drawn text and is trained on; occlusion is only counted.
        for key, expected in (('lines_outside_logical_order', 1), ('occluded_lines', 2)):
            self.assertEqual(summary['train'][key] + summary['validation'][key], expected)
        self.assertIn('אישור', '\n'.join((out / 'pages' / name).read_text(encoding='utf-8')
                                         for name in os.listdir(out / 'pages') if name.endswith('.xml')))
        dataset = (out / 'dataset.json').read_text(encoding='utf-8')
        self.assertNotIn(str(self.root), dataset)
        listed = [Path(p) for name in ('train', 'validation')
                  for p in (out / f'{name}.txt').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(sorted(listed), sorted((out / 'pages').resolve().glob('*.xml')))

    def test_output_is_deterministic(self):
        first = prepare_kraken_data(self.annotations, self.manifest, self.root / 'a')
        second = prepare_kraken_data(self.annotations, self.manifest, self.root / 'b')
        self.assertEqual(first, second)
        for path in (self.root / 'a' / 'pages').iterdir():
            self.assertEqual(path.read_bytes(), (self.root / 'b' / 'pages' / path.name).read_bytes())

    def test_split_is_by_sample_and_order_independent(self):
        samples = {f'sample-{i:03d}' for i in range(200)}
        split = assign_splits(samples, 0.1, 3)
        self.assertEqual(split, assign_splits(set(sorted(samples, reverse=True)), 0.1, 3))
        self.assertEqual(sum(value == 'validation' for value in split.values()), 20)
        self.assertNotEqual(split, assign_splits(samples, 0.1, 4))
        for fraction in (0, 0.6, float('nan')):
            with self.subTest(fraction=fraction), self.assertRaises(EngineError):
                assign_splits(samples, fraction, 0)
        with self.assertRaises(EngineError):
            assign_splits({'only'}, 0.1, 0)

    def test_invalid_annotations_fail_closed(self):
        def line(change):
            return lambda doc: change(doc['pages'][0]['lines'][0])
        cases = {
            'schema': lambda doc: doc.update(schema='hocrsyngen_line_annotations.v2'),
            'manifest hash': lambda doc: doc.update(generation_manifest_sha256='0' * 64),
            'coordinates': lambda doc: doc.update(coordinate_space='normalized'),
            'page hash': lambda doc: doc['pages'][0].update(page_sha256='0' * 64),
            'page size': lambda doc: doc['pages'][0].update(width=241),
            'unknown page': lambda doc: doc['pages'][0].update(page_id='other'),
            'duplicate page': lambda doc: doc['pages'].append(doc['pages'][0]),
            'duplicate line': lambda doc: doc['pages'][0]['lines'].append(doc['pages'][0]['lines'][0]),
            # U+FB2A is a composition exclusion, so it is never NFC.
            'not NFC': line(lambda ln: ln.update(text='\ufb2aלום')),
            'newline': line(lambda ln: ln.update(text='שלום\nעולם')),
            'bidi control': line(lambda ln: ln.update(text='שלום‏')),
            'outer space': line(lambda ln: ln.update(text='שלום ')),
            'empty': line(lambda ln: ln.update(text='')),
            'outside page': line(lambda ln: ln.update(polygon=[[0, 0], [241, 0], [0, 5]])),
            'float point': line(lambda ln: ln.update(baseline=[[0.5, 1], [3, 1]])),
            'bool point': line(lambda ln: ln.update(baseline=[[True, 1], [3, 1]])),
            'short baseline': line(lambda ln: ln.update(baseline=[[1, 1]])),
            'right-to-left baseline': line(lambda ln: ln.update(baseline=[[200, 30], [20, 30]])),
            'logical index past logical_order': line(lambda ln: ln.update(logical_line_index=2)),
            'logical index type': line(lambda ln: ln.update(logical_line_index='0')),
            'unknown join': line(lambda ln: ln.update(logical_join='newline')),
            'join without logical line': line(lambda ln: ln.update(logical_line_index=None, logical_join='space')),
            'missing occluded': line(lambda ln: ln.pop('occluded')),
            'occluded not bool': line(lambda ln: ln.update(occluded=1)),
        }
        original = self.annotations.read_text(encoding='utf-8')
        for name, change in cases.items():
            with self.subTest(name), self.assertRaises(EngineError):
                self.annotations.write_text(original, encoding='utf-8')
                self.rewrite(change)
                load_annotated_pages(self.annotations, self.manifest)
        self.annotations.write_text(original, encoding='utf-8')
        (self.batch / 'outside.png').write_bytes(b'x')
        for asset in ('../outside.png', '/etc/hosts', 'assets/../../outside.png'):
            with self.subTest(asset=asset), self.assertRaises(EngineError):
                self.rewrite(lambda doc: doc['samples'][0]['pages'][0].update(asset_path=asset), manifest=True)
                load_annotated_pages(self.annotations, self.manifest)

    def test_changed_image_and_reused_output_fail(self):
        prepare_kraken_data(self.annotations, self.manifest, self.root / 'data')
        with self.assertRaises(EngineError):
            prepare_kraken_data(self.annotations, self.manifest, self.root / 'data')
        next(self.batch.glob('assets/*/page_0001.png')).write_bytes(b'\x89PNG\r\n\x1a\nchanged')
        with self.assertRaises(EngineError):
            prepare_kraken_data(self.annotations, self.manifest, self.root / 'other')

    @unittest.skipUnless(HAS_KRAKEN, 'kraken is not installed')
    def test_kraken_parses_the_page_xml(self):
        from kraken.lib.xml import XMLPage
        out = self.root / 'data'
        prepare_kraken_data(self.annotations, self.manifest, out)
        source = {page['page_sha256']: page for page in json.loads(self.annotations.read_text())['pages']}
        for xml_path in (out / 'pages').glob('*.xml'):
            container = XMLPage(xml_path).to_container()
            expected = source[xml_path.stem]['lines']
            self.assertEqual(container.type, 'baselines')
            self.assertEqual([line.text for line in container.lines], [line['text'] for line in expected])
            self.assertEqual([[list(p) for p in line.baseline] for line in container.lines],
                             [line['baseline'] for line in expected])
            self.assertEqual({line.base_dir for line in container.lines}, {'R'})


class FakePolygonizer:
    """Stands in for kraken's calculate_polygonal_environment: a box around each baseline, shifted by the
    baseline's index, reaching past the page so clamping shows; `fail` lines get None."""

    def __init__(self, fail=()):
        self.fail, self.calls = set(fail), []

    def __call__(self, image, baselines, scale=None):
        self.calls.append((image.mode, image.size, baselines, scale))
        return [None if (bl[0][1], len(self.calls)) in self.fail else
                [(bl[0][0] - 3, bl[0][1] - 20 - n), (bl[-1][0] + 400, bl[-1][1] - 20 - n),
                 (bl[-1][0] + 400, bl[-1][1] + 4), (bl[0][0] - 3, bl[0][1] + 4)]
                for n, bl in enumerate(baselines)]


class LinePolygonTests(TrainingTestCase):
    def lines_in(self, out):
        result = {}
        for path in (out / 'pages').glob('*.xml'):
            for line in ET.parse(path).findall('.//p:TextLine', NS):
                result[path.stem, line.get('id')] = [[int(v) for v in point.split(',')] for point in
                                                    line.find('p:Coords', NS).get('points').split()]
        return result

    def test_sidecar_is_the_default_and_unchanged(self):
        default = prepare_kraken_data(self.annotations, self.manifest, self.root / 'a')
        explicit = prepare_kraken_data(self.annotations, self.manifest, self.root / 'b', line_polygons='sidecar')
        self.assertEqual(default, explicit)
        self.assertEqual(default['line_polygons'], 'sidecar')
        self.assertNotIn('polygonizer', default)
        for path in (self.root / 'a' / 'pages').glob('*.xml'):
            self.assertEqual(path.read_bytes(), (self.root / 'b' / 'pages' / path.name).read_bytes())
        dataset = json.loads((self.root / 'a' / 'dataset.json').read_text(encoding='utf-8'))
        self.assertNotIn('lines_dropped_by_polygonizer', dataset['pages'][0])

    def test_kraken_polygons_replace_sidecar_polygons_and_failures_are_counted(self):
        # The second page's first line (baseline y=34 on the first call for it) fails to polygonize.
        fake = FakePolygonizer(fail={(34, 2)})
        out = self.root / 'data'
        summary = prepare_kraken_data(self.annotations, self.manifest, out, validation_fraction=0.25,
                                      line_polygons='kraken', polygonizer=fake)
        pages = json.loads(self.annotations.read_text(encoding='utf-8'))['pages']
        self.assertEqual(len(fake.calls), len(pages))
        for (mode, size, baselines, scale), page in zip(fake.calls, sorted(pages, key=lambda p: p['sample_id'])):
            self.assertEqual((mode, size, scale), ('L', (240, 160), (POLYGONIZER_HEIGHT, 0)))
            self.assertEqual(baselines, [line['baseline'] for line in page['lines']])
        written = self.lines_in(out)
        self.assertEqual(len(written), sum(len(page['lines']) for page in pages) - 1)
        first = sorted(pages, key=lambda p: p['sample_id'])[0]
        # Box from the fake polygonizer, clamped to the 240x160 page.
        self.assertEqual(written[first['page_sha256'], 'l0'], [[17, 14], [240, 14], [240, 38], [17, 38]])
        self.assertNotIn((sorted(pages, key=lambda p: p['sample_id'])[1]['page_sha256'], 'l0'), written)
        self.assertEqual(summary['line_polygons'], 'kraken')
        self.assertEqual(summary['polygonizer']['dropped_lines'], 1)
        self.assertEqual(summary['polygonizer']['height'], POLYGONIZER_HEIGHT)
        self.assertEqual(summary['train']['lines_dropped_by_polygonizer']
                         + summary['validation']['lines_dropped_by_polygonizer'], 1)
        self.assertEqual(summary['train']['lines'] + summary['validation']['lines'], len(written))
        dataset = json.loads((out / 'dataset.json').read_text(encoding='utf-8'))
        self.assertEqual(sum(page['lines_dropped_by_polygonizer'] for page in dataset['pages']), 1)
        self.assertNotIn(str(self.root), json.dumps(dataset, ensure_ascii=False))

    def test_native_height_and_a_crashing_polygonizer(self):
        fake = FakePolygonizer()
        prepare_kraken_data(self.annotations, self.manifest, self.root / 'native', line_polygons='kraken',
                            polygonizer=fake, polygonizer_height=0)
        self.assertEqual({call[3] for call in fake.calls}, {None})

        def crash_on_ledger(image, baselines, scale=None):
            if len(baselines) == 3 and baselines[1][0][1] == 74 and len(crashed) == 0:
                crashed.append(True)
                raise ValueError('degenerate page')
            return FakePolygonizer()(image, baselines, scale)
        crashed = []
        # A polygonizer exception drops that page's lines, counted, instead of failing the run.
        summary = prepare_kraken_data(self.annotations, self.manifest, self.root / 'crash', validation_fraction=0.25,
                                      line_polygons='kraken', polygonizer=crash_on_ledger)
        self.assertEqual(crashed, [True])
        self.assertEqual(summary['polygonizer']['dropped_lines'], 3)

    def test_bad_settings_fail(self):
        for options in ({'line_polygons': 'blla'}, {'line_polygons': 'kraken', 'task': 'segmentation'},
                        {'line_polygons': 'kraken', 'polygonizer_height': 10},
                        {'polygonizer_height': True}):
            with self.subTest(options=options), self.assertRaises(EngineError):
                prepare_kraken_data(self.annotations, self.manifest, self.root / 'x', **options)
        blocked = dict.fromkeys(('kraken', 'kraken.lib', 'kraken.lib.segmentation'))
        with patch.dict(sys.modules, blocked), self.assertRaisesRegex(EngineError, 'kraken installed'):
            prepare_kraken_data(self.annotations, self.manifest, self.root / 'y', line_polygons='kraken')

    @unittest.skipUnless(HAS_KRAKEN, 'kraken is not installed')
    def test_real_polygonizer_matches_a_direct_call(self):
        from kraken.lib.segmentation import calculate_polygonal_environment
        from PIL import Image
        out = self.root / 'data'
        prepare_kraken_data(self.annotations, self.manifest, out, line_polygons='kraken')
        written = self.lines_in(out)
        for page in json.loads(self.annotations.read_text(encoding='utf-8'))['pages']:
            image = Image.open(self.batch / 'assets' / page['sample_id'] / 'page_0001.png').convert('L')
            direct = calculate_polygonal_environment(image, [line['baseline'] for line in page['lines']],
                                                     scale=(POLYGONIZER_HEIGHT, 0))
            for line, polygon in zip(page['lines'], direct):
                key = (page['page_sha256'], f"l{line['line_index']}")
                if polygon is None:
                    self.assertNotIn(key, written)
                else:
                    self.assertEqual(written[key], [[min(max(int(v), 0), b) for v, b in zip(point, (240, 160))]
                                                    for point in polygon])


class BidiRoundTripTests(unittest.TestCase):
    """Training and inference must apply inverse reorderings for a perfect model to score zero CER."""

    LINES = [line[0] for _, lines in SAMPLES for line in lines] + ['123 שלום', 'מחיר: $5.', 'שלום [א] {ב}']

    def test_training_and_inference_share_direction(self):
        recognizer = KrakenRecognizer(Path('kraken'), Path('seg'), Path('rec'))
        self.assertEqual(recognizer.base_dir, BASE_DIR)
        args = Hyperparameters().ketos_args()
        self.assertNotIn('--no-reorder', args)

    @unittest.skipUnless(HAS_KRAKEN, 'kraken is not installed')
    def test_kraken_reorder_round_trip(self):
        from kraken.containers import BaselineLine, BaselineOCRRecord
        from kraken.lib.functional_im_transforms import text_reorder

        def infer(display):
            # What `kraken ocr --reorder --base-dir R` does with a line predicted in display order.
            line = BaselineLine(id='l', baseline=None, boundary=None, text='')
            record = BaselineOCRRecord(display, [((0, 0), (0, 0))] * len(display), [1.0] * len(display), line,
                                       display_order=True)
            return record.logical_order(BASE_DIR).prediction

        for text in self.LINES:
            with self.subTest(text=text):
                # ketos train --reorder --base-dir R turns the logical ground truth into this target.
                target = text_reorder(text, BASE_DIR)
                self.assertNotEqual(target, text)
                self.assertEqual(infer(target), text)
        # Training without reordering would make a perfect model's output come back scrambled.
        self.assertNotEqual(infer(SAMPLES[0][1][0][0]), SAMPLES[0][1][0][0])


class MixGeometryTests(LinePolygonTests):
    def prepare(self, name, **options):
        options = {'validation_fraction': 0.25, 'line_polygons': 'mix', 'polygonizer': FakePolygonizer(), **options}
        return prepare_kraken_data(self.annotations, self.manifest, self.root / name, **options)

    def source_lines(self):
        return {(page['page_sha256'], f"l{line['line_index']}"): (page, line)
                for page in json.loads(self.annotations.read_text(encoding='utf-8'))['pages']
                for line in page['lines']}

    def test_assignment_is_a_deterministic_hash_of_page_sha_and_line_index(self):
        sha = 'ab' * 32
        key = hashlib.sha256(f'{sha}\0{7}'.encode()).digest()
        self.assertEqual(mix_geometry(sha, 7), ('kraken', 'kraken', 'sidecar', 'rect')[int.from_bytes(key[:8], 'big') % 4])
        self.assertEqual([mix_geometry(sha, n) for n in range(50)], [mix_geometry(sha, n) for n in range(50)])
        first, second = self.prepare('a'), self.prepare('b')
        self.assertEqual(first, second)
        for path in (self.root / 'a' / 'pages').glob('*.xml'):
            self.assertEqual(path.read_bytes(), (self.root / 'b' / 'pages' / path.name).read_bytes())
        dataset = json.loads((self.root / 'a' / 'dataset.json').read_text(encoding='utf-8'))
        source = {page['page_sha256']: page for page in json.loads(self.annotations.read_text(encoding='utf-8'))['pages']}
        for entry in dataset['pages']:
            expected = dict.fromkeys(MIX_GEOMETRIES, 0)
            for line in source[entry['page_sha256']]['lines']:
                expected[mix_geometry(entry['page_sha256'], line['line_index'])] += 1
            self.assertEqual(entry['lines_by_geometry'], expected)

    def test_shares_are_within_tolerance(self):
        self.assertEqual(MIX_SHARES, {'kraken': 0.5, 'sidecar': 0.25, 'rect': 0.25})
        counts = dict.fromkeys(MIX_GEOMETRIES, 0)
        for page in range(400):
            sha = hashlib.sha256(f'page {page}'.encode()).hexdigest()
            for line in range(25):
                counts[mix_geometry(sha, line)] += 1
        for name, share in MIX_SHARES.items():
            self.assertAlmostEqual(counts[name] / 10_000, share, delta=0.02)
        summary = self.prepare('data')
        total = sum(summary[split]['lines_by_geometry'][name] for split in ('train', 'validation')
                    for name in MIX_GEOMETRIES)
        self.assertEqual(total, sum(len(lines) for _, lines in SAMPLES))

    def test_rect_geometry(self):
        polygon = [(10, 40), (90, 44), (88, 60), (12, 58)]
        self.assertEqual(rect_polygon(polygon, 240, 160, 0.25), [(10, 35), (90, 35), (90, 65), (10, 65)])
        self.assertEqual(rect_polygon(polygon, 240, 160, 0.01), [(10, 39), (90, 39), (90, 61), (10, 61)])
        self.assertEqual(rect_polygon(polygon, 240, 160, -0.1), [(10, 42), (90, 42), (90, 58), (10, 58)])
        self.assertEqual(rect_polygon(polygon, 240, 50, 0.5), [(10, 30), (90, 30), (90, 50), (10, 50)])
        self.assertEqual(rect_polygon([(0, 5), (9, 5), (9, 6)], 20, 20, -0.2), [(0, 5), (9, 5), (9, 6), (0, 6)])
        # Every written line has its mix geometry: kraken from the polygonizer, sidecar as is, rect padded.
        self.prepare('data', rect_pad=0.2)
        written, seen = self.lines_in(self.root / 'data'), set()
        boxes = FakePolygonizer()
        for (sha, line_id), (page, line) in self.source_lines().items():
            geometry = mix_geometry(sha, line['line_index'])
            seen.add(geometry)
            points = [tuple(point) for point in written[sha, line_id]]
            if geometry == 'sidecar':
                self.assertEqual(points, [tuple(point) for point in line['polygon']])
            elif geometry == 'rect':
                self.assertEqual(points, rect_polygon(line['polygon'], page['width'], page['height'], 0.2))
            else:
                box = boxes(Image.new('L', (1, 1)), [other['baseline'] for other in page['lines']])[line['line_index']]
                clamp = [(min(max(x, 0), page['width']), min(max(y, 0), page['height'])) for x, y in box]
                self.assertEqual(points, clamp)
        self.assertEqual(seen, set(MIX_GEOMETRIES))

    def test_split_stays_per_sample_and_validation_uses_the_mix(self):
        for seed in (0, 1, 2):
            with self.subTest(split_seed=seed):
                summary = self.prepare(f'seed{seed}', split_seed=seed)
                dataset = json.loads((self.root / f'seed{seed}' / 'dataset.json').read_text(encoding='utf-8'))
                sides = {}
                for entry in dataset['pages']:
                    sides.setdefault(entry['sample_id'], set()).add(entry['split'])
                    sides.setdefault(entry['page_sha256'], set()).add(entry['split'])
                self.assertTrue(all(len(value) == 1 for value in sides.values()))
                for split in ('train', 'validation'):
                    counts = summary[split]['lines_by_geometry']
                    self.assertEqual(sum(counts.values()), summary[split]['lines'])
                    self.assertEqual(counts, {name: sum(entry['lines_by_geometry'][name] for entry in dataset['pages']
                                                        if entry['split'] == split) for name in MIX_GEOMETRIES})
                # A line's geometry depends on its page and index only, never on its split.
                for (sha, line_id), (page, line) in self.source_lines().items():
                    self.assertIn((sha, line_id), self.lines_in(self.root / f'seed{seed}'))
        self.assertEqual(summary['line_polygons'], 'mix')
        self.assertEqual(summary['line_geometry'], {'mode': 'mix', 'buckets': list(MIX_BUCKETS), 'shares': MIX_SHARES,
                                                    'assignment': MIX_ASSIGNMENT,
                                                    'rect': {'source': 'sidecar polygon bounding box',
                                                             'vertical_pad': RECT_PAD}})

    def test_only_kraken_lines_are_dropped(self):
        pages = sorted(json.loads(self.annotations.read_text(encoding='utf-8'))['pages'], key=lambda p: p['sample_id'])
        # The polygonizer is called once per page with a kraken line, in page order.
        called = [page for page in pages
                  if any(mix_geometry(page['page_sha256'], line['line_index']) == 'kraken' for line in page['lines'])]
        lines = [(n, line, mix_geometry(page['page_sha256'], line['line_index']))
                 for n, page in enumerate(called) for line in page['lines']]
        kraken = [(n, line['line_index']) for n, line, geometry in lines if geometry == 'kraken']
        others = [(n, line['line_index']) for n, line, geometry in lines if geometry != 'kraken']
        self.assertTrue(kraken and others)

        def failing(targets):
            calls = []

            def polygonize(image, baselines, scale=None):
                calls.append(True)
                boxes = FakePolygonizer()(image, baselines, scale)
                return [None if (len(calls) - 1, index) in targets else box for index, box in enumerate(boxes)]
            return polygonize
        total = sum(len(page['lines']) for page in pages)
        summary = self.prepare('k', polygonizer=failing({kraken[0]}))
        self.assertEqual(summary['polygonizer']['dropped_lines'], 1)
        self.assertEqual(summary['train']['lines'] + summary['validation']['lines'], total - 1)
        # Sidecar and rect lines keep their geometry even where the polygonizer fails on them.
        summary = self.prepare('o', polygonizer=failing(set(others)))
        self.assertEqual(summary['polygonizer']['dropped_lines'], 0)
        self.assertEqual(summary['train']['lines'] + summary['validation']['lines'], total)

    def test_default_buckets_are_unchanged(self):
        # Golden values from heocr-engine 8355674 (before --mix-buckets): R3g's assignment and its record text.
        self.assertEqual(MIX_ASSIGNMENT, "sha256('<page_sha256>\\0<line_index>'), first 8 bytes big-endian mod 4: "
                                         "0-1 kraken, 2 sidecar, 3 rect")
        shas = [hashlib.sha256(f'golden page {n}'.encode()).hexdigest() for n in range(4)]
        golden = [['sidecar', 'kraken', 'sidecar', 'sidecar', 'kraken', 'sidecar'],
                  ['rect', 'sidecar', 'rect', 'kraken', 'kraken', 'kraken'],
                  ['sidecar', 'rect', 'rect', 'rect', 'sidecar', 'rect'],
                  ['kraken', 'sidecar', 'rect', 'rect', 'kraken', 'rect']]
        for buckets in ((), (MIX_BUCKETS,), (list(MIX_BUCKETS),)):
            self.assertEqual([[mix_geometry(sha, index, *buckets) for index in range(6)] for sha in shas], golden)
        # On the fixture, an explicit default list writes the same data as no list.
        default, explicit = self.prepare('a'), self.prepare('b', mix_buckets=list(MIX_BUCKETS))
        self.assertEqual(default, explicit)
        for path in (self.root / 'a' / 'pages').glob('*.xml'):
            self.assertEqual(path.read_bytes(), (self.root / 'b' / 'pages' / path.name).read_bytes())

    def test_eight_buckets(self):
        self.assertEqual(mix_shares(R3H_BUCKETS), {'kraken': 0.75, 'sidecar': 0.125, 'rect': 0.125})
        self.assertEqual(mix_assignment(R3H_BUCKETS), "sha256('<page_sha256>\\0<line_index>'), first 8 bytes "
                                                      "big-endian mod 8: 0-5 kraken, 6 sidecar, 7 rect")
        self.assertEqual(mix_assignment(('kraken', 'rect', 'kraken')).split(': ')[1], '0 kraken, 1 rect, 2 kraken')
        counts = dict.fromkeys(MIX_GEOMETRIES, 0)
        for page in range(400):
            sha = hashlib.sha256(f'page {page}'.encode()).hexdigest()
            for line in range(25):
                counts[mix_geometry(sha, line, R3H_BUCKETS)] += 1
        for name, share in mix_shares(R3H_BUCKETS).items():
            self.assertAlmostEqual(counts[name] / 10_000, share, delta=0.015)
        summary = self.prepare('data', mix_buckets=R3H_BUCKETS)
        self.assertEqual(summary['line_geometry']['buckets'], list(R3H_BUCKETS))
        self.assertEqual(summary['line_geometry']['shares'], mix_shares(R3H_BUCKETS))
        written, source = self.lines_in(self.root / 'data'), self.source_lines()
        for (sha, line_id), (page, line) in source.items():
            if mix_geometry(sha, line['line_index'], R3H_BUCKETS) == 'sidecar':
                self.assertEqual(written[sha, line_id], line['polygon'])
        self.assertEqual(sum(summary[split]['lines_by_geometry'][name] for split in ('train', 'validation')
                             for name in MIX_GEOMETRIES), len(source))

    def test_bad_buckets_fail_closed(self):
        for buckets in (('kraken', 'blla'), (), ('sidecar', 'rect'), ('kraken',) * 17, 'kraken', ('kraken', 3)):
            with self.subTest(buckets=buckets), self.assertRaises(EngineError):
                self.prepare('x', mix_buckets=buckets)
            self.assertFalse((self.root / 'x').exists())
        with self.assertRaisesRegex(EngineError, 'for --line-polygons mix'):
            self.prepare('x', line_polygons='kraken', mix_buckets=R3H_BUCKETS)
        for value in ('kraken,blla', '', 'sidecar,rect'):
            with self.subTest(cli=value), patch('sys.stderr', io.StringIO()):
                self.assertEqual(main(['prepare-kraken-data', str(self.annotations), str(self.manifest),
                                       str(self.root / 'z'), '--line-polygons', 'mix', '--mix-buckets', value]), 1)

    def test_bad_mode_or_pad_fails_closed(self):
        for options in ({'line_polygons': 'mixed'}, {'line_polygons': 'mix', 'task': 'segmentation'},
                        {'rect_pad': 0.6}, {'rect_pad': -0.3}, {'rect_pad': float('nan')}, {'rect_pad': True},
                        {'rect_pad': '0.1'}):
            with self.subTest(options=options), self.assertRaises(EngineError):
                self.prepare('x', **options)
            self.assertFalse((self.root / 'x').exists())
        blocked = dict.fromkeys(('kraken', 'kraken.lib', 'kraken.lib.segmentation'))
        with patch.dict(sys.modules, blocked), self.assertRaisesRegex(EngineError, 'kraken installed'):
            self.prepare('y', polygonizer=None)
        with patch('sys.stderr', io.StringIO()):
            self.assertEqual(main(['prepare-kraken-data', str(self.annotations), str(self.manifest),
                                   str(self.root / 'z'), '--line-polygons', 'mix', '--rect-pad', '0.9']), 1)


class TrainKrakenTests(TrainingTestCase):
    def setUp(self):
        super().setUp()
        self.ketos = write_fake_ketos(self.root / 'ketos', sys.executable)
        self.calls = self.root / 'calls.jsonl'
        self.corpus = self.root / 'corpus.txt'
        self.corpus.write_text('שורה אחת\nשורה שתיים\n', encoding='utf-8')
        env = patch.dict(os.environ, {'FAKE_KETOS_CALLS': str(self.calls)})
        env.start()
        self.addCleanup(env.stop)

    def train(self, **changes):
        options = {'corpora': (self.corpus,), 'device': 'mps', 'seed': 11, 'validation_fraction': 0.25}
        options.update(changes)
        return train_kraken(self.annotations, self.manifest, self.root / 'work', self.ketos, **options)

    def test_record_describes_a_from_scratch_run(self):
        record = self.train()
        self.assertEqual(validate_training_run(record), [])
        self.assertEqual(record['schema_version'], TRAINING_SCHEMA_ID)
        self.assertEqual(record['init'], 'from_scratch')
        self.assertEqual(record['model_licence']['status'], 'Needs verification')
        self.assertFalse(record['model_licence']['published'])
        self.assertEqual(record['trainer']['version'], '7.0.2')
        model = self.root / 'work' / 'checkpoints' / 'best_0.5000.safetensors'
        self.assertEqual(record['output']['model_sha256'], hashlib.sha256(model.read_bytes()).hexdigest())
        self.assertEqual(record['data']['corpora'][0]['sha256'], hashlib.sha256(self.corpus.read_bytes()).hexdigest())
        self.assertEqual(record['data']['annotations_sha256'],
                         hashlib.sha256(self.annotations.read_bytes()).hexdigest())
        self.assertEqual(record['outcome']['stopped_by'], 'early_stopping')
        self.assertEqual(record['outcome']['best_epoch'], 1)
        self.assertEqual(record['outcome']['epochs_completed'], 3)
        self.assertEqual(record['outcome']['validation_metric']['best'], 0.5)
        self.assertEqual(record['outcome']['lines_dropped_by_ketos'], {'train': 0, 'validation': 0})
        self.assertEqual(record['outcome']['validation_history'][1],
                         {'run': 1, 'chars': 358, 'errors': 179, 'val_accuracy': 0.5})
        self.assertNotIn(str(self.root), json.dumps(record, ensure_ascii=False))
        train = record['commands']['train']
        self.assertEqual(train[0], '<ketos>')
        self.assertEqual(train[train.index('-d') + 1], 'mps')
        self.assertEqual(train[train.index('--base-dir') + 1], 'R')
        self.assertIn('--reorder', train)
        self.assertFalse({'-i', '--load', '--resume'} & set(train))
        calls = [json.loads(line) for line in self.calls.read_text(encoding='utf-8').splitlines()]
        self.assertEqual([call[0] if call[0] == '--version' else call[call.index('compile') if 'compile' in call
                                                                          else call.index('train')]
                          for call in calls], ['--version', 'compile', 'compile', 'train'])
        self.assertEqual(calls[-1][calls[-1].index('-s') + 1], '11')
        self.assertEqual(record['run']['environment'], {'PYTORCH_ENABLE_MPS_FALLBACK': '1'})

    def test_cli_writes_record_once(self):
        record = self.root / 'record.json'
        argv = ['train-kraken', str(self.annotations), str(self.manifest), str(self.root / 'work'), str(record),
                '--ketos', str(self.ketos), '--corpus', str(self.corpus), '--validation-fraction', '0.25',
                '--quit', 'fixed', '--epochs', '3']
        self.assertEqual(main(argv), 0)
        written = json.loads(record.read_text(encoding='utf-8'))
        self.assertEqual(validate_training_run(written), [])
        self.assertEqual(written['outcome']['stopped_by'], 'epoch_limit')
        with patch('sys.stderr', io.StringIO()):
            self.assertEqual(main(argv), 1)

    def test_kraken_line_polygons_are_recorded(self):
        with patch('heocr_engine.training.kraken_polygonizer', return_value=(FakePolygonizer(), '7.0.2')):
            record = self.train(line_polygons='kraken')
        self.assertEqual(validate_training_run(record), [])
        self.assertEqual(record['data']['line_polygons'], 'kraken')
        self.assertEqual(record['data']['polygonizer']['kraken_version'], '7.0.2')
        self.assertEqual(record['data']['polygonizer']['dropped_lines'], 0)
        for broken in ({'line_polygons': 'kraken', 'polygonizer': None}, {'line_polygons': 'other'},
                       {'line_polygons': 'sidecar'}):
            with self.subTest(broken=broken):
                bad = {**record, 'data': {**record['data'], **broken}}
                if broken.get('polygonizer') is None and 'polygonizer' in broken:
                    bad['data'].pop('polygonizer')
                self.assertTrue(validate_training_run(bad))

    def test_mix_line_geometry_is_recorded(self):
        with patch('heocr_engine.training.kraken_polygonizer', return_value=(FakePolygonizer(), '7.0.2')):
            record = self.train(line_polygons='mix', rect_pad=-0.1)
        self.assertEqual(validate_training_run(record), [])
        data = record['data']
        self.assertEqual((data['line_polygons'], data['line_geometry']['rect']['vertical_pad']), ('mix', -0.1))
        self.assertEqual(data['polygonizer']['dropped_lines'], 0)
        for split in ('train', 'validation'):
            self.assertEqual(sum(data[split]['lines_by_geometry'].values()), data[split]['lines'])
        uneven = {**data['train'], 'lines_by_geometry': {**data['train']['lines_by_geometry'], 'rect': 10**6}}
        for broken in ({'line_geometry': None}, {'line_geometry': {**data['line_geometry'], 'shares': {'kraken': 1.0}}},
                       {'line_geometry': {**data['line_geometry'], 'assignment': 'random'}},
                       {'line_geometry': {**data['line_geometry'], 'rect': {'vertical_pad': 2}}},
                       {'train': uneven}, {'line_polygons': 'kraken'}, {'polygonizer': None}):
            with self.subTest(broken=broken):
                bad = {**record, 'data': {**data, **broken}}
                for key in ('line_geometry', 'polygonizer'):
                    if key in broken and broken[key] is None:
                        bad['data'].pop(key)
                self.assertTrue(validate_training_run(bad))

    def test_mix_buckets_are_recorded_and_checked(self):
        with patch('heocr_engine.training.kraken_polygonizer', return_value=(FakePolygonizer(), '7.0.2')):
            record = self.train(line_polygons='mix', rect_pad=-0.14, mix_buckets=R3H_BUCKETS)
        self.assertEqual(validate_training_run(record), [])
        geometry = record['data']['line_geometry']
        self.assertEqual((geometry['buckets'], geometry['shares']), (list(R3H_BUCKETS), mix_shares(R3H_BUCKETS)))
        # An R3g record, made before `buckets` existed, reads as the default list and still validates.
        r3g = {**record, 'data': {**record['data'], 'line_geometry': {
            key: value for key, value in {**geometry, 'shares': MIX_SHARES, 'assignment': MIX_ASSIGNMENT}.items()
            if key != 'buckets'}}}
        self.assertEqual(validate_training_run(r3g), [])
        for broken in ({'buckets': ['kraken', 'blla']}, {'buckets': []}, {'buckets': ['sidecar', 'rect']},
                       {'buckets': ['kraken'] * 17}, {'shares': MIX_SHARES}, {'assignment': MIX_ASSIGNMENT},
                       {'buckets': list(MIX_BUCKETS)}):
            with self.subTest(broken=broken):
                bad = {**record, 'data': {**record['data'], 'line_geometry': {**geometry, **broken}}}
                self.assertTrue(validate_training_run(bad))

    def test_prepare_cli(self):
        with patch('sys.stdout', io.StringIO()) as stdout:
            self.assertEqual(main(['prepare-kraken-data', str(self.annotations), str(self.manifest),
                                   str(self.root / 'data')]), 0)
        self.assertEqual(json.loads(stdout.getvalue())['split']['unit'], 'sample')

    def test_crash_after_output_fails_closed(self):
        with patch.dict(os.environ, {'FAKE_KETOS_EXIT': '134'}), \
                self.assertRaisesRegex(EngineError, r'\Aketos failed with exit status 134\Z'):
            self.train()

    def test_dropped_lines_are_reported(self):
        with patch.dict(os.environ, {'FAKE_KETOS_DROP': '2'}):
            record = self.train()
        self.assertEqual(record['outcome']['lines_dropped_by_ketos']['train'], 2)

    def test_quiet_early_stop_is_inferred_from_history(self):
        # Accuracies 0.162, 0.5, 0.5: one run without improvement after the best.
        with patch.dict(os.environ, {'FAKE_KETOS_QUIET': '1'}):
            self.assertEqual(self.train(hyperparameters=Hyperparameters(lag=1))['outcome']['stopped_by'],
                             'early_stopping')
            shutil.rmtree(self.root / 'work')
            self.assertEqual(self.train(hyperparameters=Hyperparameters(lag=2))['outcome']['stopped_by'], 'unknown')
            shutil.rmtree(self.root / 'work')
            self.assertEqual(self.train(hyperparameters=Hyperparameters(lag=2, epochs=3))['outcome']['stopped_by'],
                             'epoch_limit')

    def test_bad_settings_fail_before_running(self):
        for changes in ({'device': 'gpu; rm'}, {'precision': 'fp8'}, {'seed': -1}, {'timeout': 0},
                        {'hyperparameters': Hyperparameters(quit='fixed', epochs=-1)},
                        {'hyperparameters': Hyperparameters(learning_rate=float('nan'))},
                        {'hyperparameters': Hyperparameters(optimizer='Lion')}):
            with self.subTest(changes=changes), self.assertRaises(EngineError):
                self.train(**changes)
        self.assertFalse(self.calls.exists())

    def test_validator_rejects_paths_and_loaded_weights(self):
        record = self.train()
        for change in (lambda r: r['commands']['train'].extend(['-i', 'x.safetensors']),
                       lambda r: r['data'].update(note='/Users/someone/batch'),
                       lambda r: r.update(init='fine_tuned'),
                       lambda r: r['text_order'].update(inference_base_dir='L'),
                       lambda r: r['output'].update(model_sha256='abc')):
            changed = json.loads(json.dumps(record))
            change(changed)
            with self.subTest(change=change):
                self.assertNotEqual(validate_training_run(changed), [])

    def test_safetensors_metadata_reader(self):
        bad = self.root / 'bad.safetensors'
        for raw in (b'', b'\xff' * 8, (5).to_bytes(8, 'little') + b'{"a":'):
            bad.write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaises(EngineError):
                safetensors_kraken_metadata(bad)


if __name__ == '__main__':
    unittest.main()
