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

    def add_regions(self, document):
        """Give every page S11a-style regions: one per region name, its line box padded by 2 px."""
        for page in document['pages']:
            names = list(dict.fromkeys(line['region'] for line in page['lines']))
            page['regions'] = []
            for number, name in enumerate(names):
                members = [line for line in page['lines'] if line['region'] == name]
                for line in members:
                    line['region_index'] = number
                xs = [x for line in members for x, _ in line['polygon']]
                ys = [y for line in members for _, y in line['polygon']]
                box = [[min(xs) - 2, min(ys) - 2], [max(xs) + 2, min(ys) - 2], [max(xs) + 2, max(ys) + 2],
                       [min(xs) - 2, max(ys) + 2]]
                page['regions'].append({'region_index': number, 'type': name, 'polygon': box,
                                        'reading_order_index': number,
                                        'line_indices': [line['line_index'] for line in members]})

    def test_sidecar_region_polygons_are_used(self):
        plain = self.root / 'plain'
        prepare_kraken_data(self.annotations, self.manifest, plain)
        self.rewrite(self.add_regions)
        out = self.root / 'data'
        summary = prepare_kraken_data(self.annotations, self.manifest, out, **SPLIT, task='segmentation')
        self.assertEqual(summary['region_geometry'], 'sidecar')
        source = {page['page_sha256']: page for page in json.loads(self.annotations.read_text())['pages']}
        for xml_path in (out / 'pages').glob('*.xml'):
            regions = ET.parse(xml_path).findall('.//p:TextRegion', NS)
            self.assertEqual([[[int(v) for v in p.split(',')] for p in region.find('p:Coords', NS).get('points').split()]
                              for region in regions],
                             [region['polygon'] for region in source[xml_path.stem]['regions']])
        # Recognition ignores the sidecar regions: its PAGE XML is unchanged.
        recognition = self.root / 'recognition'
        prepare_kraken_data(self.annotations, self.manifest, recognition)
        for xml_path in (plain / 'pages').glob('*.xml'):
            self.assertEqual((recognition / 'pages' / xml_path.name).read_bytes(), xml_path.read_bytes())

    def test_inconsistent_sidecar_regions_fail_closed(self):
        def broken(change):
            def apply(document):
                self.add_regions(document)
                change(document['pages'][1])
            return apply
        changes = (lambda page: page['regions'][0]['line_indices'].append(page['regions'][1]['line_indices'][0]),
                   lambda page: page['regions'][1].update(type='body'),
                   lambda page: page['regions'][0]['line_indices'].pop(),
                   lambda page: page['regions'][0].update(region_index=5),
                   lambda page: page['regions'][0].update(polygon=[[0, 0], [9999, 0], [0, 10]]),
                   lambda page: page['lines'][0].update(region_index=1),
                   lambda page: page.update(regions=[]))
        original = self.annotations.read_text(encoding='utf-8')
        for number, change in enumerate(changes):
            self.annotations.write_text(original, encoding='utf-8')
            self.rewrite(broken(change))
            with self.subTest(change=number), self.assertRaises(EngineError):
                prepare_kraken_data(self.annotations, self.manifest, self.root / f'bad{number}', task='segmentation')
        # Region polygons on some pages but not others is ambiguous for segmentation training.
        self.annotations.write_text(original, encoding='utf-8')
        self.rewrite(lambda document: (self.add_regions(document), document['pages'][0].pop('regions')))
        with self.assertRaisesRegex(EngineError, 'every page or no page'):
            prepare_kraken_data(self.annotations, self.manifest, self.root / 'mixed', task='segmentation')

    def test_line_types_from_regions(self):
        out = self.root / 'data'
        summary = prepare_kraken_data(self.annotations, self.manifest, out, **SPLIT, task='segmentation',
                                      line_types={'stamp': 'stamp'})
        self.assertEqual(summary['line_type_map'], {'stamp': 'stamp'})
        self.assertEqual(summary['train']['lines_by_type'], {'default': 7, 'stamp': 1})
        self.assertEqual(summary['validation']['lines_by_type'], {'default': 3})
        source = {page['page_sha256']: page for page in json.loads(self.annotations.read_text())['pages']}
        for xml_path in (out / 'pages').glob('*.xml'):
            lines = ET.parse(xml_path).findall('.//p:TextLine', NS)
            self.assertEqual([line.get('custom') for line in lines],
                             ['structure {type:stamp;}' if gold['region'] == 'stamp' else None
                              for gold in source[xml_path.stem]['lines']])
        # Without a map every line keeps the default type, and recognition rejects line types.
        plain = prepare_kraken_data(self.annotations, self.manifest, self.root / 'plain', **SPLIT, task='segmentation')
        self.assertEqual((plain['line_type_map'], plain['train']['lines_by_type']), ({}, {'default': 8}))
        for line_types in ({'stamp': 'stamp'}, {'stamp': 'default'}, {'stamp': 'a b'}, {'x;y': 'stamp'}):
            task = 'recognition' if line_types == {'stamp': 'stamp'} else 'segmentation'
            with self.subTest(line_types=line_types, task=task), self.assertRaises(EngineError):
                prepare_kraken_data(self.annotations, self.manifest, self.root / 'bad', task=task,
                                    line_types=line_types)

    @unittest.skipUnless(HAS_KRAKEN, 'kraken is not installed')
    def test_kraken_reads_line_types(self):
        from kraken.lib.xml import XMLPage
        out = self.root / 'data'
        prepare_kraken_data(self.annotations, self.manifest, out, task='segmentation', line_types={'stamp': 'stamp'})
        types = set()
        for xml_path in (out / 'pages').glob('*.xml'):
            container = XMLPage(xml_path, filetype='page').to_container()
            types |= {line.tags['type'][0]['type'] if 'type' in line.tags else 'default' for line in container.lines}
        self.assertEqual(types, {'default', 'stamp'})

    def test_prepare_cli_task(self):
        with patch('sys.stdout', io.StringIO()) as stdout:
            self.assertEqual(main(['prepare-kraken-data', str(self.annotations), str(self.manifest),
                                   str(self.root / 'data'), '--task', 'segmentation']), 0)
        self.assertEqual(json.loads(stdout.getvalue())['task'], 'segmentation')
        with patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit):
            main(['prepare-kraken-data', str(self.annotations), str(self.manifest), str(self.root / 'x'),
                  '--task', 'segmentation', '--line-type', 'stamp'])

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

    def test_line_types_reach_the_record(self):
        record = self.train(line_types={'stamp': 'stamp'})
        self.assertEqual(validate_training_run(record), [])
        self.assertEqual(record['segmentation']['line_types'], ['default', 'stamp'])
        self.assertEqual(record['segmentation']['line_type_map'], {'stamp': 'stamp'})
        self.assertEqual(set(record['segmentation']['class_mapping']['baselines']), {'default', 'stamp'})
        self.assertEqual(self.train_again()['segmentation']['line_type_map'], {})
        # A line type only in validation cannot be trained (split seed 3 holds out the stamp sample).
        shutil.rmtree(self.root / 'work')
        with self.assertRaisesRegex(EngineError, 'region types|line types'):
            self.train(split_seed=3, line_types={'stamp': 'stamp'})

    def train_again(self, **changes):
        shutil.rmtree(self.root / 'work')
        return self.train(**changes)

    def test_cli_writes_record_once(self):
        record = self.root / 'record.json'
        argv = ['train-kraken-seg', str(self.annotations), str(self.manifest), str(self.root / 'work'), str(record),
                '--ketos', str(self.ketos), '--validation-fraction', '0.25', '--split-seed', '0',
                '--quit', 'fixed', '--epochs', '3', '--line-width', '6', '--line-type', 'stamp=stamp']
        self.assertEqual(main(argv), 0)
        written = json.loads(record.read_text(encoding='utf-8'))
        self.assertEqual(validate_training_run(written), [])
        self.assertEqual(written['hyperparameters']['line_width'], 6)
        self.assertEqual(written['segmentation']['line_types'], ['default', 'stamp'])
        self.assertEqual(written['outcome']['stopped_by'], 'epoch_limit')
        with patch('sys.stderr', io.StringIO()):
            self.assertEqual(main(argv), 1)


if __name__ == '__main__':
    unittest.main()
