import copy
import unittest

from heocr_engine.training import TRAINING_SCHEMA_ID, prepare_kraken_data, validate_training_run
from heocr_engine.cli import EngineError

SHA = '0' * 64


def reading_order_record():
    source = {'name': 'batch', 'annotations_sha256': '1' * 64, 'generation_manifest_sha256': '2' * 64}
    return {
        'schema_version': TRAINING_SCHEMA_ID, 'task': 'reading_order', 'init': 'from_scratch',
        'engine': {'name': 'heocr-engine', 'version': '0.2.0'}, 'trainer': {'name': 'ketos', 'version': '7.0.2'},
        'data': {'annotation_schema': 'hocrsyngen_line_annotations.v1', 'sources': [source, dict(source)],
                 'corpora': [{'sha256': '3' * 64, 'bytes': 1}]},
        'reading_order': {'level': 'baselines', 'class_mapping': {'default': 0, 'title': 1},
                          'inference': {'command': 'heocr-engine kraken --api python'}},
        'commands': {'train': ['<ketos>', 'rotrain', '-f', 'page', '--level', 'baselines']},
        'hyperparameters': {'quit': 'early'}, 'run': {'seed': 42}, 'outcome': {'quit': 'early'},
        'output': {'model_sha256': SHA}, 'model_licence': {'status': 'Needs verification'},
    }


class ReadingOrderRecordTests(unittest.TestCase):
    def test_reading_order_record_validates(self):
        self.assertEqual(validate_training_run(reading_order_record()), [])

    def test_reading_order_record_problems(self):
        def without_sources(r):
            r['data'].pop('sources')

        def bad_source_hash(r):
            r['data']['sources'][1]['generation_manifest_sha256'] = 'x'

        def bad_level(r):
            r['reading_order']['level'] = 'pages'

        def no_class_mapping(r):
            r['reading_order'].pop('class_mapping')

        def no_reading_order(r):
            r.pop('reading_order')

        def loads_weights(r):
            r['commands']['train'] += ['-i', 'old.safetensors']

        def local_path(r):
            r['commands']['train'][0] = '/Users/someone/bin/ketos'

        for change in (without_sources, bad_source_hash, bad_level, no_class_mapping, no_reading_order,
                       loads_weights, local_path):
            with self.subTest(change=change.__name__):
                record = copy.deepcopy(reading_order_record())
                change(record)
                self.assertTrue(validate_training_run(record))

    def test_data_preparation_has_no_reading_order_task(self):
        with self.assertRaises(EngineError):
            prepare_kraken_data(None, None, None, task='reading_order')


if __name__ == '__main__':
    unittest.main()
