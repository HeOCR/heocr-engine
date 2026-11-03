import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent / 'fixtures'))
from line_annotations_fixture import write_fake_ketos  # noqa: E402
from test_training import HAS_KRAKEN, NS, TrainingTestCase  # noqa: E402

from heocr_engine.cli import EngineError, main  # noqa: E402
from heocr_engine.segmentation_training import (INFERENCE, SegmentationHyperparameters,  # noqa: E402
                                                train_kraken_segmentation)
from heocr_engine.training import prepare_kraken_data, validate_training_run  # noqa: E402

# With split seed 0 and a quarter held out, the validation sample has no stamp, so every type is trained.
SPLIT = {'validation_fraction': 0.25, 'split_seed': 0}


class SegmentationDataTests(TrainingTestCase):
    def test_regions_are_typed_and_counted(self):
        out = self.root / 'data'
        summary = prepare_kraken_data(self.annotations, self.manifest, out, **SPLIT, task='segmentation')
        self.assertEqual(summary['task'], 'segmentation')
        self.assertEqual(summary['region_geometry'], 'line_polygon_bbox')
        self.assertEqual(summary['train']['regions_by_type'], {'body': 3, 'stamp': 1})
        self.assertEqual(summary['validation']['regions_by_type'], {'body': 1})
        source = {page['page_sha256']: page for page in json.loads(self.annotations.read_text())['pages']}
        for xml_path in (out / 'pages').glob('*.xml'):
            lines = source[xml_path.stem]['lines']
            regions = ET.parse(xml_path).findall('.//p:TextRegion', NS)
            names = list(dict.fromkeys(line['region'] for line in lines))
            self.assertEqual([region.get('custom') for region in regions],
                             [f'structure {{type:{name};}}' for name in names])
            for region, name in zip(regions, names):
                xs = [x for line in lines if line['region'] == name for x, _ in line['polygon']]
                ys = [y for line in lines if line['region'] == name for _, y in line['polygon']]
                box = [[min(xs), min(ys)], [max(xs), min(ys)], [max(xs), max(ys)], [min(xs), max(ys)]]
                self.assertEqual([[int(v) for v in p.split(',')]
                                  for p in region.find('p:Coords', NS).get('points').split()], box)

    def test_recognition_output_has_no_region_types(self):
        out = self.root / 'data'
        summary = prepare_kraken_data(self.annotations, self.manifest, out)
        self.assertNotIn('task', summary)
        self.assertNotIn('regions_by_type', summary['train'])
        self.assertFalse(any('custom=' in path.read_text(encoding='utf-8') for path in (out / 'pages').glob('*.xml')))

    def test_unsafe_region_names_fail_closed(self):
        def rename(document):
            document['pages'][0]['lines'][0]['region'] = 'body;type:x'
        self.rewrite(rename)
        with self.assertRaisesRegex(EngineError, 'region types'):
            prepare_kraken_data(self.annotations, self.manifest, self.root / 'data', task='segmentation')
        # Recognition does not use region names as types, so it still accepts them.
        prepare_kraken_data(self.annotations, self.manifest, self.root / 'other')
        with self.assertRaises(EngineError):
            prepare_kraken_data(self.annotations, self.manifest, self.root / 'third', task='layout')

    def test_prepare_cli_task(self):
        with patch('sys.stdout', io.StringIO()) as stdout:
            self.assertEqual(main(['prepare-kraken-data', str(self.annotations), str(self.manifest),
                                   str(self.root / 'data'), '--task', 'segmentation']), 0)
        self.assertEqual(json.loads(stdout.getvalue())['task'], 'segmentation')

    @unittest.skipUnless(HAS_KRAKEN, 'kraken is not installed')
    def test_kraken_reads_region_types(self):
        from kraken.lib.xml import XMLPage
        out = self.root / 'data'
        prepare_kraken_data(self.annotations, self.manifest, out, task='segmentation')
        source = {page['page_sha256']: page for page in json.loads(self.annotations.read_text())['pages']}
        for xml_path in (out / 'pages').glob('*.xml'):
            container = XMLPage(xml_path, filetype='page').to_container()
            self.assertEqual(container.type, 'baselines')
            self.assertEqual(set(container.regions), {line['region'] for line in source[xml_path.stem]['lines']})
            self.assertEqual({line.tags.get('type', 'default') for line in container.lines}, {'default'})


class TrainKrakenSegmentationTests(TrainingTestCase):
    def setUp(self):
        super().setUp()
        self.ketos = write_fake_ketos(self.root / 'ketos', sys.executable)
        self.calls = self.root / 'calls.jsonl'
        env = patch.dict(os.environ, {'FAKE_KETOS_CALLS': str(self.calls)})
        env.start()
        self.addCleanup(env.stop)

    def train(self, **changes):
        options = {'device': 'mps', 'seed': 11, **SPLIT}
        options.update(changes)
        return train_kraken_segmentation(self.annotations, self.manifest, self.root / 'work', self.ketos, **options)

    def test_record_describes_a_from_scratch_segmenter(self):
        record = self.train()
        self.assertEqual(validate_training_run(record), [])
        self.assertEqual(record['task'], 'segmentation')
        self.assertEqual(record['init'], 'from_scratch')
        self.assertNotIn('text_order', record)
        self.assertEqual(record['model_licence']['basis'], 'planning/decisions/0008-first-trained-segmenter.md')
        self.assertFalse(record['model_licence']['published'])
        segmentation = record['segmentation']
        self.assertEqual(segmentation['region_types'], ['body', 'stamp'])
        self.assertEqual(segmentation['line_types'], ['default'])
        self.assertEqual(segmentation['line_location'], 'baseline')
        self.assertEqual(set(segmentation['class_mapping']['regions']), {'body', 'stamp'})
        self.assertEqual(segmentation['inference'], INFERENCE)
        model = self.root / 'work' / 'checkpoints' / 'best_0.5000.safetensors'
        self.assertEqual(record['output']['model_sha256'], hashlib.sha256(model.read_bytes()).hexdigest())
        outcome = record['outcome']
        # mean IoU 0.25, 0.5, 0.5 with the default lag 10: early stopping cannot be inferred yet.
        self.assertEqual(outcome['stopped_by'], 'unknown')
        self.assertEqual(outcome['best_epoch'], 1)
        self.assertEqual(outcome['validation_metric']['name'], 'val_mean_iu')
        self.assertEqual(outcome['validation_metric']['best'], 0.5)
        self.assertEqual(outcome['validation_history'][1],
                         {'run': 1, 'val_accuracy': 0.98, 'val_mean_acc': 0.98, 'val_mean_iu': 0.5,
                          'val_freq_iu': 0.4, 'baseline_precision': 0.5, 'baseline_recall': 0.1,
                          'baseline_f1': 0.2})
        self.assertEqual(outcome['ketos_listed_pages'], {'train': 3, 'validation': 1})
        self.assertEqual(outcome['ketos_parse_failures'], 0)
        self.assertNotIn(str(self.root), json.dumps(record, ensure_ascii=False))
        train = record['commands']['train']
        self.assertEqual(train[0], '<ketos>')
        self.assertEqual(train[train.index('segtrain') + 1:train.index('segtrain') + 3], ['-f', 'page'])
        self.assertEqual(train[train.index('-t') + 1], '<work>/data/train.txt')
        self.assertFalse({'-i', '--load', '--resume', '--resize', '-bl', '--baseline', '-tl', '-cl'} & set(train))
        self.assertEqual(record['run']['environment'], {'PYTORCH_ENABLE_MPS_FALLBACK': '1'})
        calls = [json.loads(line) for line in self.calls.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(calls), 2)

    def test_stop_reasons(self):
        self.assertEqual(self.train(hyperparameters=SegmentationHyperparameters(lag=1))['outcome']['stopped_by'],
                         'early_stopping')
        shutil.rmtree(self.root / 'work')
        record = self.train(hyperparameters=SegmentationHyperparameters(quit='fixed', epochs=3))
        self.assertEqual(record['outcome']['stopped_by'], 'epoch_limit')

    def test_string_topline_fails_closed(self):
        with patch.dict(os.environ, {'FAKE_KETOS_TOPLINE': 'False'}), \
                self.assertRaisesRegex(EngineError, 'baseline'):
            self.train()

    def test_validation_only_region_type_fails(self):
        with self.assertRaisesRegex(EngineError, 'region types the train split lacks'):
            self.train(split_seed=3)
        self.assertFalse(self.calls.exists() and 'segtrain' in self.calls.read_text(encoding='utf-8'))

    def test_crash_and_bad_settings_fail_closed(self):
        with patch.dict(os.environ, {'FAKE_KETOS_EXIT': '134'}), \
                self.assertRaisesRegex(EngineError, r'\Aketos failed with exit status 134\Z'):
            self.train()
        for hyperparameters in (SegmentationHyperparameters(quit='fixed', epochs=-1),
                                SegmentationHyperparameters(dice_weight=2.0),
                                SegmentationHyperparameters(learning_rate=float('inf'))):
            with self.subTest(hyperparameters=hyperparameters), self.assertRaises(EngineError):
                self.train(hyperparameters=hyperparameters)

    def test_validator_checks_segmentation_fields(self):
        record = self.train()
        for change in (lambda r: r['commands']['train'].extend(['-i', 'blla.mlmodel']),
                       lambda r: r['commands']['train'].append('--resize'),
                       lambda r: r.update(task='layout'),
                       lambda r: r.pop('segmentation'),
                       lambda r: r['segmentation']['inference'].pop('reading_order'),
                       lambda r: r['segmentation'].update(line_location='topline')):
            changed = json.loads(json.dumps(record))
            change(changed)
            with self.subTest(change=change):
                self.assertNotEqual(validate_training_run(changed), [])

    def test_cli_writes_record_once(self):
        record = self.root / 'record.json'
        argv = ['train-kraken-seg', str(self.annotations), str(self.manifest), str(self.root / 'work'), str(record),
                '--ketos', str(self.ketos), '--validation-fraction', '0.25', '--split-seed', '0',
                '--quit', 'fixed', '--epochs', '3', '--line-width', '6']
        self.assertEqual(main(argv), 0)
        written = json.loads(record.read_text(encoding='utf-8'))
        self.assertEqual(validate_training_run(written), [])
        self.assertEqual(written['hyperparameters']['line_width'], 6)
        self.assertEqual(written['outcome']['stopped_by'], 'epoch_limit')
        with patch('sys.stderr', io.StringIO()):
            self.assertEqual(main(argv), 1)


if __name__ == '__main__':
    unittest.main()
