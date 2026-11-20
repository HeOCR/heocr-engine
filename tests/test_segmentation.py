import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent / 'fixtures'))
from line_annotations_fixture import build_batch, line_geometry  # noqa: E402

from heocr_engine.cli import EngineError, main  # noqa: E402
from heocr_engine.kraken_api import GEOMETRY_SCHEMA  # noqa: E402
from heocr_engine.segmentation import (EVENTS, GOLD_CATEGORIES, PREDICTED_CATEGORIES, SCHEMA_ID,  # noqa: E402
                                       diagnose_segmentation, match_page, read_predicted_lines)

ROOT = Path(__file__).resolve().parent.parent
PAGE = 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15'
ALTO = 'http://www.loc.gov/standards/alto/ns-v4#'
# Three body lines on one page, in reading order.
SAMPLES = (('printed_letter', [('שלום עולם', 0, None, False), ('סימן 96', 1, None, False),
                               ('סוף', 2, None, False)]),
           ('handwritten_note', [('אותיות', 0, None, False), ('סופיות', 1, None, False)]))


def box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def gold_line(index, x0=20, x1=220):
    polygon, baseline = line_geometry(index)
    return box(x0, polygon[0][1], x1, polygon[2][1]), [[x0, baseline[0][1]], [x1, baseline[1][1]]]


def points(values):
    return ' '.join(f'{x},{y}' for x, y in values)


def page_xml(lines):
    body = ''.join(f'<TextLine id="l{n}"><Coords points="{points(polygon)}"/><Baseline points="{points(baseline)}"/>'
                   f'<TextEquiv><Unicode>{text}</Unicode></TextEquiv></TextLine>'
                   for n, (polygon, baseline, text) in enumerate(lines))
    return (f'<?xml version="1.0" encoding="UTF-8"?><PcGts xmlns="{PAGE}"><Page imageWidth="240" '
            f'imageHeight="160"><TextRegion id="r0">{body}</TextRegion></Page></PcGts>')


def alto_xml(lines):
    body = ''.join(f'<TextLine BASELINE="{" ".join(f"{x} {y}" for x, y in baseline)}"><Shape><Polygon '
                   f'POINTS="{" ".join(f"{x} {y}" for x, y in polygon)}"/></Shape><String CONTENT="{text}"/>'
                   f'</TextLine>' for polygon, baseline, text in lines)
    return f'<alto xmlns="{ALTO}"><Layout><Page><PrintSpace><TextBlock>{body}</TextBlock></PrintSpace></Page></Layout></alto>'


def geometry_json(lines, width=240, height=160):
    return json.dumps({'schema_version': GEOMETRY_SCHEMA, 'unit': 'pixel', 'width': width, 'height': height,
                       'lines': [{'id': f'l{n}', 'order': n, 'boundary': polygon, 'baseline': baseline, 'text': text}
                                 for n, (polygon, baseline, text) in enumerate(lines)]}, ensure_ascii=False)


class SegmentationTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.annotations, self.manifest = build_batch(self.root / 'batch', SAMPLES)
        self.pages = json.loads(self.annotations.read_text(encoding='utf-8'))['pages']
        self.predictions = self.root / 'predicted'
        self.predictions.mkdir()

    def write(self, page, lines, render=page_xml):
        suffix = '.json' if render is geometry_json else '.xml'
        (self.predictions / f"{self.pages[page]['page_sha256']}{suffix}").write_text(render(lines),
                                                                                     encoding='utf-8')

    def perfect(self, page):
        return [(*gold_line(i), line['text']) for i, line in enumerate(self.pages[page]['lines'])]

    def diagnose(self, **options):
        return diagnose_segmentation(self.annotations, self.manifest, self.predictions, **options)


class DiagnosticTests(SegmentationTestCase):
    def test_perfect_segmentation_scores_one_by_either_matcher(self):
        self.write(0, self.perfect(0))
        self.write(1, self.perfect(1), alto_xml)
        for method in ('polygon', 'baseline'):
            with self.subTest(method=method):
                report = self.diagnose(method=method)
                overall = report['overall']
                self.assertEqual((overall['precision'], overall['recall'], overall['f1']), (1.0, 1.0, 1.0))
                self.assertEqual(overall['gold'], {**dict.fromkeys(GOLD_CATEGORIES, 0), 'matched': 5})
                self.assertEqual(overall['events'], dict.fromkeys(EVENTS, 0))
                self.assertEqual(overall['order']['kendall_tau'], 1.0)
                self.assertEqual(overall['order']['adjacent_kept_fraction'], 1.0)
                self.assertEqual(report['predictions']['format'], 'alto+page')
                self.assertEqual(sorted(report['by_template']), ['handwritten_note', 'printed_letter'])

    def test_split_merge_missed_and_spurious_lines(self):
        first, second, third = (gold_line(i) for i in range(3))
        merged = (box(20, first[0][0][1], 220, second[0][2][1]), first[1], 'both')
        self.write(0, [merged, (*gold_line(2, 20, 115), 'left'), (*gold_line(2, 125, 220), 'right')])
        # The second page misses its first line and adds a line in empty space.
        self.write(1, [(box(20, 130, 220, 150), [[20, 145], [220, 145]], 'noise'), (*gold_line(1), 'x')])
        overall = self.diagnose()['overall']
        self.assertEqual(overall['gold'], {'matched': 1, 'split': 1, 'merged': 2, 'partial': 0, 'missed': 1})
        self.assertEqual(overall['predicted'], {'matched': 1, 'merged': 1, 'fragment': 2, 'partial': 0,
                                                'spurious': 1})
        self.assertEqual(overall['events'], {'split_gold_lines': 1, 'split_fragments': 2,
                                             'merging_predicted_lines': 1, 'merged_gold_lines': 2})
        self.assertEqual((overall['precision'], overall['recall']), (0.2, 0.2))
        self.assertEqual(overall['order']['pages_scored'], 0)

    def test_reading_order_against_logical_order(self):
        self.write(0, list(reversed(self.perfect(0))))
        self.write(1, self.perfect(1))
        report = self.diagnose()
        order = report['by_template']['printed_letter']['order']
        self.assertEqual((order['kendall_tau'], order['adjacent_kept_fraction'], order['pages_in_order']),
                         (-1.0, 0.0, 0))
        overall = report['overall']['order']
        self.assertEqual((overall['concordant_pairs'], overall['discordant_pairs']), (1, 3))
        self.assertEqual((overall['pages_scored'], overall['pages_in_order']), (2, 1))

    def test_baseline_matcher_needs_vertical_agreement(self):
        gold = [{'line_index': 0, 'logical_line_index': 0, 'polygon': box(20, 10, 220, 40),
                 'baseline': [[20, 34], [220, 34]]}]
        near = {'polygon': None, 'baseline': [[220, 38], [30, 36]], 'text': ''}
        far = {'polygon': None, 'baseline': [[20, 60], [220, 60]], 'text': ''}
        result = match_page(gold, [far, near], 'baseline')
        self.assertEqual([record['category'] for record in result['predicted']], ['spurious', 'matched'])
        self.assertEqual(result['gold'][0]['predicted'], 1)
        # Without a polygon the line cannot match by polygon IoU.
        self.assertEqual(match_page(gold, [near], 'polygon')['gold'][0]['category'], 'missed')

    def test_page_and_alto_readers_agree(self):
        lines = [(box(20, 10, 220, 40), [[220, 34], [20, 34]], 'א'), (box(-5, 50, 260, 80), [[0, 74]], '')]
        path = self.root / 'line.xml'
        results = []
        for render in (page_xml, alto_xml):
            path.write_text(render(lines), encoding='utf-8')
            results.append(read_predicted_lines(path, 240, 160)[1])
        self.assertEqual(results[0], results[1])
        # Coordinates are clamped to the page; a one-point baseline counts as no baseline.
        self.assertEqual(results[0][1]['polygon'], [tuple(point) for point in box(0, 50, 240, 80)])
        self.assertIsNone(results[0][1]['baseline'])

    def test_kraken_geometry_reads_like_page_xml(self):
        lines = [(box(20, 10, 220, 40), [[220, 34], [20, 34]], 'א'), (box(-5, 50, 260.4, 80), [[0, 74]], '')]
        xml, geometry = self.root / 'line.xml', self.root / 'line.json'
        xml.write_text(page_xml(lines), encoding='utf-8')
        geometry.write_text(geometry_json(lines), encoding='utf-8')
        self.assertEqual(read_predicted_lines(geometry, 240, 160),
                         ('kraken-geometry', read_predicted_lines(xml, 240, 160)[1]))
        # The geometry's line order is the predicted reading order, as document order is for XML.
        reports = []
        for render in (page_xml, geometry_json):
            for path in self.predictions.iterdir():
                path.unlink()
            self.write(0, list(reversed(self.perfect(0))), render)
            self.write(1, self.perfect(1), render)
            reports.append(self.diagnose())
        self.assertEqual(reports[0]['overall'], reports[1]['overall'])
        self.assertEqual((reports[1]['predictions']['format'], reports[1]['reading_order']['predicted']),
                         ('kraken-geometry', 'geometry line order'))
        self.assertEqual(reports[0]['reading_order']['predicted'], 'document order of TextLine elements')

    def test_bad_kraken_geometry_fails_closed(self):
        self.write(1, self.perfect(1))
        self.write(0, self.perfect(0), geometry_json)
        self.write(0, self.perfect(0))
        with self.assertRaisesRegex(EngineError, 'both an .xml and a .json'):
            self.diagnose()
        (self.predictions / f"{self.pages[0]['page_sha256']}.xml").unlink()
        target = self.predictions / f"{self.pages[0]['page_sha256']}.json"
        good = json.loads(geometry_json(self.perfect(0)))
        bad = [{**good, 'schema_version': 'other'}, {**good, 'unit': 'point'}, {**good, 'width': 241},
               {**good, 'lines': list(reversed(good['lines']))},
               {**good, 'lines': [{**good['lines'][0], 'boundary': [[0, 'x']]}]},
               {**good, 'lines': [{**good['lines'][0], 'baseline': [[True, 1], [2, 3]]}]}, []]
        for content in [*(json.dumps(value) for value in bad), '{', '\udcff']:
            with self.subTest(content=content[:40]), self.assertRaises(EngineError):
                target.write_text(content, encoding='utf-8', errors='surrogateescape')
                self.diagnose()

    def test_bad_inputs_fail_closed(self):
        self.write(0, self.perfect(0))
        with self.assertRaisesRegex(EngineError, '1 missing'):
            self.diagnose()
        self.write(1, self.perfect(1))
        (self.predictions / ('0' * 64 + '.xml')).write_text(page_xml([]), encoding='utf-8')
        with self.assertRaisesRegex(EngineError, '1 unexpected'):
            self.diagnose()
        (self.predictions / ('0' * 64 + '.xml')).unlink()
        target = self.predictions / f"{self.pages[0]['page_sha256']}.xml"
        for content in ('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><PcGts/>', '<html/>', '<PcGts',
                        page_xml([(box(0, 0, 9, 9), [[0, 5], [9, 5]], '')]).replace('0,0 9,0', '0,0 9')):
            with self.subTest(content=content[:30]), self.assertRaises(EngineError):
                target.write_text(content, encoding='utf-8')
                self.diagnose()
        target.write_text(page_xml([]), encoding='utf-8')
        for options in ({'method': 'mask'}, {'threshold': 0}, {'threshold': 1.5}):
            with self.subTest(options=options), self.assertRaises(EngineError):
                self.diagnose(**options)

    def test_cli_writes_a_path_free_report_once(self):
        self.write(0, self.perfect(0))
        self.write(1, self.perfect(1))
        output = self.root / 'report.json'
        args = ['diagnose-segmentation', str(self.annotations), str(self.manifest), str(self.predictions),
                '--match', 'baseline', '--lines', '--output', str(output)]
        self.assertEqual(main(args), 0)
        text = output.read_text(encoding='utf-8')
        self.assertNotIn(str(self.root), text)
        report = json.loads(text)
        self.assertEqual(report['schema_version'], SCHEMA_ID)
        self.assertTrue(report['diagnostic_only'])
        self.assertEqual(report['matching']['method'], 'baseline')
        self.assertEqual(len(report['pages']), 2)
        self.assertEqual(report['pages'][0]['predicted'][0], {'category': 'matched', 'gold': 0, 'anchor': 0})
        self.assertEqual(main(args), 1)

    def test_doc_names_schema_and_categories(self):
        doc = (ROOT / 'docs' / 'segmentation_diagnostic.md').read_text(encoding='utf-8')
        for value in (SCHEMA_ID, *GOLD_CATEGORIES, *PREDICTED_CATEGORIES, *EVENTS):
            with self.subTest(value=value):
                self.assertIn(f'`{value}`', doc)


if __name__ == '__main__':
    unittest.main()
