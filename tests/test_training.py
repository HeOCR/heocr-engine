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

sys.path.insert(0, str(Path(__file__).parent / 'fixtures'))
from line_annotations_fixture import SAMPLES, build_batch, write_fake_ketos  # noqa: E402

from heocr_engine.cli import EngineError, main  # noqa: E402
from heocr_engine.kraken import KrakenRecognizer  # noqa: E402
from heocr_engine.training import (BASE_DIR, Hyperparameters, PAGE_NS, TRAINING_SCHEMA_ID,  # noqa: E402
                                   assign_splits, load_annotated_pages, prepare_kraken_data,
                                   safetensors_kraken_metadata, train_kraken, validate_training_run)

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
