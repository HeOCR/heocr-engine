import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent / 'fixtures'))
from line_annotations_fixture import write_fake_ketos  # noqa: E402
from test_segmentation_training import SPLIT, SegmentationDataTests  # noqa: E402
from test_training import NS, TrainingTestCase  # noqa: E402

from heocr_engine.cli import EngineError, main  # noqa: E402
from heocr_engine.real_pages import (FILTER, REAL_PAGES_SCHEMA, accept_page, hocr_lines, load_real_pages,  # noqa: E402
                                     proxy_ratio, pseudo_label_pages)
from heocr_engine.segmentation_training import train_kraken_segmentation  # noqa: E402
from heocr_engine.training import prepare_kraken_data, validate_training_run  # noqa: E402

HAS_NUMPY = importlib.util.find_spec('numpy') is not None
HOCR = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body><div class='ocr_page' title='bbox 0 0 400 300'>
 <div class='ocr_carea' title="bbox 20 20 380 120">
  <p class='ocr_par'>
   <span class='ocr_header' title="bbox 120 20 280 40; baseline 0 -4; x_size 20"><span class='ocrx_word' title='bbox 120 20 280 40; x_wconf 90'>א</span></span>
   <span class='ocr_line' title="bbox 20 60 380 80; baseline 0.01 -3; x_size 18"><span class='ocrx_word' title='bbox 20 60 380 80; x_wconf 31'>ב</span></span>
   <span class='ocr_line' title="bbox 30 100 33 102; baseline 0 0"><span class='ocrx_word' title='bbox 30 100 33 102; x_wconf 10'>.</span></span>
   <span class='ocr_line' title="bbox 20 100 380 118; baseline 0 -2"></span>
  </p>
 </div>
 <div class='ocr_carea' title="bbox 20 200 380 260">
  <p class='ocr_par'><span class='ocr_line' title="bbox 20 220 390 240; baseline 0 -50"><span class='ocrx_word' title='bbox 20 220 390 240; x_wconf 70'>ג</span></span></p>
 </div>
</div></body></html>"""
EXCLUSIONS = {'eval_indexes': ['ws_index_1', 'ws_index_2']}


def page_image(path: Path, size=(400, 300)) -> str:
    image = Image.new('RGB', size, 'white')
    ImageDraw.Draw(image).rectangle((20, 60, 380, 80), fill='black')
    image.save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def real_manifest(root: Path, splits=('train', 'validation'), change=None) -> Path:
    pages = []
    for number, split in enumerate(splits):
        sha = page_image(root / f'p{number}.png', size=(400, 300 + number))
        pages.append({'page_id': f'real:ws_index_{9 + number}:p0001:w400', 'image': f'p{number}.png',
                      'image_sha256': sha, 'width': 400, 'height': 300 + number, 'split': split,
                      'source': {'index_key': f'ws_index_{9 + number}', 'commons_title': f'File:Book{number}.pdf',
                                 'licence_templates': ['PD-old-70'], 'gate_admitted': True, 'page': number},
                      'lines': [{'line_index': 0, 'region_index': 0, 'polygon': [[20, 60], [380, 60], [380, 80], [20, 80]],
                                 'baseline': [[20, 77], [380, 77]], 'tesseract_class': 'ocr_line'}],
                      'regions': [{'region_index': 0, 'type': 'body',
                                   'polygon': [[18, 58], [382, 58], [382, 82], [18, 82]], 'line_indices': [0]}]})
    document = {'schema': REAL_PAGES_SCHEMA, 'scan_provenance_sha256': '0' * 64,
                'label_source': {'tool': 'tesseract', 'version': 'tesseract 5.5.3', 'traineddata_sha256': '1' * 64,
                                 'traineddata_licence': 'Apache-2.0', 'psm': 3},
                'filter': FILTER, 'exclusions': EXCLUSIONS, 'pages': pages,
                'rejected': [{'image': 'q.png', 'reason': 'disagrees_with_proxy'},
                             {'image': 'r.png', 'reason': 'disagrees_with_proxy'}, {'image': 's.png', 'reason': 'too_few_lines'}]}
    if change:
        change(document)
    path = root / 'real_pages.json'
    path.write_text(json.dumps(document), encoding='utf-8')
    return path


class HocrTests(unittest.TestCase):
    def test_lines_are_tight_boxes_with_clamped_baselines_in_body_regions(self):
        lines, regions, stats = hocr_lines(HOCR, 384, 300)
        # The speck and the wordless line are dropped; low word confidence (31) is kept.
        self.assertEqual(len(lines), 3)
        self.assertEqual(stats['lines_dropped'], 2)
        self.assertEqual([line['tesseract_class'] for line in lines], ['ocr_header', 'ocr_line', 'ocr_line'])
        self.assertEqual(lines[1]['polygon'], [(20, 60), (380, 60), (380, 80), (20, 80)])
        self.assertEqual(lines[1]['baseline'], [(20, 77), (380, 80)])
        # Clipped to the page width, and a baseline offset beyond the box is clamped to its top.
        self.assertEqual(lines[2]['polygon'][1], (384, 220))
        self.assertEqual(lines[2]['baseline'], [(20, 220), (384, 220)])
        self.assertEqual([region['line_indices'] for region in regions], [[0, 1], [2]])
        self.assertEqual({region['type'] for region in regions}, {'body'})
        self.assertEqual(regions[0]['polygon'][0], (18, 18))
        self.assertEqual(stats['mean_word_confidence'], round((90 + 31 + 10 + 70) / 4, 2))

    def test_pages_are_kept_only_when_they_agree_with_the_proxy(self):
        lines, _, _ = hocr_lines(HOCR, 400, 300)
        self.assertEqual(proxy_ratio(lines, [(50, 2), (200, 3), (390, 0)]), 1.0)
        self.assertIsNone(proxy_ratio(lines, [(50, 0)]))
        self.assertIsNone(accept_page(lines, 1.0))
        self.assertEqual(accept_page(lines, 0.5), 'disagrees_with_proxy')
        self.assertEqual(accept_page(lines, None), 'disagrees_with_proxy')
        self.assertEqual(accept_page(lines[:2], 1.0), 'too_few_lines')

    @unittest.skipUnless(HAS_NUMPY, 'the strip proxy needs numpy')
    def test_strip_proxy_counts_text_rows_and_ignores_rules(self):
        from heocr_engine.real_pages import strip_proxy
        image = Image.new('L', (600, 800), 255)
        draw = ImageDraw.Draw(image)
        for row in range(10):  # glyph-sized blocks with gaps, as text is; a solid bar would read as a rule
            for x in range(60, 540, 14):
                draw.rectangle((x, 100 + 50 * row, x + 9, 118 + 50 * row), fill=0)
        draw.line((30, 60, 570, 60), fill=0, width=2)  # a rule: cleared
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        strips = strip_proxy(buffer.getvalue())
        self.assertEqual(len(strips), 12)
        self.assertEqual({rows for x, rows in strips if 80 < x < 520}, {10})


class LoadRealPagesTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_a_work_key_stands_in_for_an_index_key(self):
        def work_key(document):
            for page in document['pages']:
                source = page['source']
                source['work_key'] = 'nli:' + source.pop('index_key')
        pages, _, _ = load_real_pages(real_manifest(self.root, change=work_key))
        self.assertEqual([page['key'] for page in pages], ['nli:ws_index_9', 'nli:ws_index_10'])

    def test_manifest_loads_in_prepare_shape(self):
        pages, sha, header = load_real_pages(real_manifest(self.root))
        self.assertEqual([page['split'] for page in pages], ['train', 'validation'])
        self.assertEqual(pages[0]['template_id'], 'real_page')
        self.assertEqual(pages[0]['lines'][0]['region'], 'body')
        self.assertEqual(sha, hashlib.sha256((self.root / 'real_pages.json').read_bytes()).hexdigest())
        self.assertEqual(header['exclusions'], EXCLUSIONS)

    def test_bad_manifests_fail_closed(self):
        def image_changed(document):
            document['pages'][0]['image_sha256'] = 'f' * 64

        def outside(document):
            document['pages'][0]['image'] = '../p0.png'

        def line_outside_region(document):
            document['pages'][0]['regions'][0]['polygon'] = [[18, 58], [200, 58], [200, 82], [18, 82]]

        def no_exclusions(document):
            document['exclusions'] = {}

        def no_licence(document):
            del document['label_source']['traineddata_licence']

        def orphan_line(document):
            document['pages'][0]['regions'][0]['line_indices'] = []

        def index_in_both_splits(document):
            document['pages'][1]['source']['index_key'] = document['pages'][0]['source']['index_key']

        def eval_index(document):
            document['pages'][0]['source']['index_key'] = EXCLUSIONS['eval_indexes'][1]

        def no_key(document):
            document['pages'][0]['source']['index_key'] = None

        def empty_key(document):
            document['pages'][0]['source']['index_key'] = ' '

        def gate_not_admitted(document):
            document['pages'][1]['source']['gate_admitted'] = False

        def gate_missing(document):
            del document['pages'][1]['source']['gate_admitted']

        for change in (image_changed, outside, line_outside_region, no_exclusions, no_licence, orphan_line,
                       index_in_both_splits, eval_index, no_key, empty_key, gate_not_admitted, gate_missing):
            with self.subTest(change.__name__), self.assertRaises(EngineError):
                load_real_pages(real_manifest(self.root, change=change))


class RealPagesTrainingTests(TrainingTestCase):
    def setUp(self):
        super().setUp()
        self.rewrite(SegmentationDataTests.add_regions.__get__(self))
        (self.root / 'real').mkdir()
        self.real = real_manifest(self.root / 'real')

    def test_prepare_adds_real_pages_to_their_splits(self):
        out = self.root / 'data'
        summary = prepare_kraken_data(self.annotations, self.manifest, out, **SPLIT, task='segmentation',
                                      real_pages=self.real)
        real = summary['real_pages']
        self.assertEqual((real['train'], real['validation']),
                         ({'pages': 1, 'lines': 1, 'indexes': ['ws_index_9']},
                          {'pages': 1, 'lines': 1, 'indexes': ['ws_index_10']}))
        self.assertEqual(real['label_source']['traineddata_licence'], 'Apache-2.0')
        self.assertEqual(real['exclusions']['eval_indexes'], EXCLUSIONS['eval_indexes'])
        self.assertEqual(real['file_licence_templates'], {'PD-old-70': 2})
        self.assertEqual(real['rejected_by_reason'], {'disagrees_with_proxy': 2, 'too_few_lines': 1})
        self.assertEqual(summary['train']['pages_by_template']['real_page'], 1)
        real_sha = hashlib.sha256((self.root / 'real' / 'p1.png').read_bytes()).hexdigest()
        listed = (out / 'validation.txt').read_text(encoding='utf-8').split()
        real_xml = [path for path in listed if Path(path).stem == real_sha]
        self.assertEqual(len(real_xml), 1)
        region = ET.parse(real_xml[0]).find('.//p:TextRegion', NS)
        self.assertEqual(region.get('custom'), 'structure {type:body;}')
        dataset = json.loads((out / 'dataset.json').read_text(encoding='utf-8'))
        self.assertNotIn(str(self.root), json.dumps(dataset['real_pages']))

    def test_real_pages_need_sidecar_segmentation_data(self):
        def drop_regions(document):
            for page in document['pages']:
                page.pop('regions')
                for line in page['lines']:
                    line.pop('region_index', None)

        plain = self.root / 'plain-batch'
        self.rewrite(drop_regions)
        with self.assertRaises(EngineError):
            prepare_kraken_data(self.annotations, self.manifest, plain, **SPLIT, task='segmentation',
                                real_pages=self.real)

    def test_record_states_the_real_pages_and_validates(self):
        ketos = write_fake_ketos(self.root / 'ketos', sys.executable)
        with patch.dict(os.environ, {'FAKE_KETOS_CALLS': str(self.root / 'calls.jsonl')}):
            record = train_kraken_segmentation(self.annotations, self.manifest, self.root / 'work', ketos,
                                               device='cpu', **SPLIT, real_pages=self.real)
        self.assertEqual(validate_training_run(record), [])
        self.assertIn('Tesseract blocks as body', record['segmentation']['region_type_source'])
        self.assertEqual(record['data']['real_pages']['train']['pages'], 1)
        self.assertNotIn(str(self.root), json.dumps(record, ensure_ascii=False))
        leaked = json.loads(json.dumps(record))
        leaked['data']['real_pages']['train']['indexes'] = ['ws_index_1']
        self.assertTrue(any('evaluation Index' in p for p in validate_training_run(leaked)))
        broken = json.loads(json.dumps(record))
        broken['data']['real_pages']['exclusions'] = {}
        broken['data']['real_pages']['label_source'].pop('traineddata_sha256')
        problems = validate_training_run(broken)
        self.assertTrue(any('eval_indexes' in p for p in problems))
        self.assertTrue(any('traineddata' in p for p in problems))


FAKE_TESSERACT = """#!{python}
import sys
args = sys.argv[1:]
if args == ['--version']:
    print('tesseract 5.5.3')
    sys.exit(0)
sys.stdout.write(open({hocr!r}, encoding='utf-8').read())
"""


class PseudoLabelTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        hocr = self.root / 'page.hocr'
        hocr.write_text(HOCR, encoding='utf-8')
        self.tesseract = self.root / 'tesseract'
        self.tesseract.write_text(FAKE_TESSERACT.format(python=sys.executable, hocr=str(hocr)), encoding='utf-8')
        self.tesseract.chmod(0o755)
        self.tessdata = self.root / 'tessdata'
        self.tessdata.mkdir()
        (self.tessdata / 'heb.traineddata').write_bytes(b'traineddata')
        self.scans = self.root / 'scans'
        (self.scans / 'train' / 'ws_index_9').mkdir(parents=True)
        files = {}
        for number in (5, 6):
            path = self.scans / 'train' / 'ws_index_9' / f'p{number:04d}_w400.png'
            files[number] = {'width': 400, 'file': str(path.relative_to(self.scans)), 'sha256': page_image(path),
                             'derived': None}
        provenance = {'schema': 'heocr_r4f_scan_provenance.v1', 'excluded_e2d3d_indexes': ['ws_index_1'],
                      'files': {'ws_index_9': {
                          'index_key': 'ws_index_9', 'split': 'train', 'commons_title': 'File:Book.pdf',
                          'licence_templates': ['PD-old-70'], 'gate': {'admitted': True},
                          'images': [{'page': n, 'url': 'https://example.invalid/p', 'variants': [files[n]],
                                      'use': [files[n]['file']]} for n in (5, 6)]}}}
        (self.scans / 'provenance.json').write_text(json.dumps(provenance), encoding='utf-8')

    def test_pages_are_labelled_filtered_and_recorded(self):
        ratios = iter([1.0, 0.3])
        with patch('heocr_engine.real_pages.strip_proxy', return_value=[]), \
                patch('heocr_engine.real_pages.proxy_ratio', side_effect=lambda lines, strips: next(ratios)):
            manifest = pseudo_label_pages(self.scans, self.tesseract, self.tessdata)
        self.assertEqual(manifest['schema'], REAL_PAGES_SCHEMA)
        self.assertEqual(len(manifest['pages']), 1)
        self.assertEqual(manifest['rejected'][0]['reason'], 'disagrees_with_proxy')
        page = manifest['pages'][0]
        self.assertEqual(page['split'], 'train')
        self.assertEqual(page['source']['licence_templates'], ['PD-old-70'])
        self.assertTrue(page['source']['gate_admitted'])
        label = manifest['label_source']
        self.assertEqual(label['traineddata_sha256'], hashlib.sha256(b'traineddata').hexdigest())
        self.assertEqual(label['traineddata_licence'], 'Apache-2.0')
        self.assertEqual(label['version'], 'tesseract 5.5.3')
        self.assertEqual(manifest['exclusions'], {'eval_indexes': ['ws_index_1']})
        # The manifest it writes loads back for training.
        path = self.scans / 'real_pages.json'
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.assertEqual(len(load_real_pages(path)[0]), 1)

    def rewrite_provenance(self, change):
        path = self.scans / 'provenance.json'
        provenance = json.loads(path.read_text(encoding='utf-8'))
        change(provenance['files']['ws_index_9'])
        path.write_text(json.dumps(provenance), encoding='utf-8')

    def test_eval_index_gate_and_missing_key_fail_closed(self):
        def eval_index(entry):
            entry['index_key'] = 'ws_index_1'

        def not_admitted(entry):
            entry['gate'] = {'admitted': False, 'reasons': ['creator_death_year_missing']}

        def no_key(entry):
            entry['index_key'] = ''

        original = (self.scans / 'provenance.json').read_text(encoding='utf-8')
        for change in (eval_index, not_admitted, no_key):
            with self.subTest(change.__name__):
                (self.scans / 'provenance.json').write_text(original, encoding='utf-8')
                self.rewrite_provenance(change)
                with patch('heocr_engine.real_pages.strip_proxy', return_value=[]), self.assertRaises(EngineError):
                    pseudo_label_pages(self.scans, self.tesseract, self.tessdata)

    def test_changed_scan_fails_closed(self):
        path = self.scans / 'train' / 'ws_index_9' / 'p0005_w400.png'
        path.write_bytes(path.read_bytes() + b'x')
        with patch('heocr_engine.real_pages.strip_proxy', return_value=[]), self.assertRaises(EngineError):
            pseudo_label_pages(self.scans, self.tesseract, self.tessdata)

    def test_cli_writes_inside_the_scan_folder_only(self):
        with patch('sys.stderr', io.StringIO()):
            self.assertEqual(main(['pseudo-label-pages', str(self.scans), str(self.root / 'elsewhere.json'),
                                   '--tesseract', str(self.tesseract), '--tessdata', str(self.tessdata)]), 1)
        self.assertFalse((self.root / 'elsewhere.json').exists())


if __name__ == '__main__':
    unittest.main()
