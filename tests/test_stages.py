import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from heocr_engine.cli import EngineError, main
from heocr_engine.stages import (Page, RecognitionResult, StageInfo, SubprocessStage,
                                 load_entry_point, run_pipeline)
from heocr_engine.validate import validate_files, validate_prediction

FIXTURE = Path(__file__).parent / 'fixtures' / 'stage_fixture.py'
SHA = 'a' * 64


def png(size=(16, 12), color='white'):
    buffer = io.BytesIO()
    Image.new('RGB', size, color).save(buffer, format='PNG')
    return buffer.getvalue()


def prediction(**changes):
    record = {'schema_version': 'heocr_engine_prediction.v1', 'page_id': 'sha256:' + SHA,
              'input': {'sha256': SHA, 'width': 16, 'height': 12}, 'track': 'open',
              'engine': {'name': 'x', 'version': '1'}, 'text': 'שלום',
              'words': [{'text': 'שלום', 'confidence': 50, 'bbox': [0, 0, 4, 4],
                         'geometry_status': 'valid'}]}
    record.update(changes)
    return record


def stage(kind, **changes):
    values = dict(kind=kind, name=f'{kind}-stage', version='1', deterministic=True)
    values.update(changes)
    return StageInfo(**values)


class Identity:
    info = stage('preprocess')

    def process(self, page):
        return Page(page.data, page.width, page.height)


class Resize:
    info = stage('preprocess', name='resize')

    def process(self, page):
        return Page(png((8, 8)), 8, 8)


class Fake:
    def __init__(self, **changes):
        self.info = stage('recognize', **changes)

    def recognize(self, page):
        return RecognitionResult('שלום  עולם', [{'text': 'שלום', 'confidence': 90,
                                                'bbox': [0, 0, 5, 5], 'geometry_status': 'valid'}])


class Exclaim:
    info = stage('postcorrect', license='MIT')

    def correct(self, page, result):
        return RecognitionResult(result.text + '!', result.words, {'rule': 'exclaim'})


class ValidateTests(unittest.TestCase):
    def test_valid_and_legacy_predictions(self):
        self.assertEqual(validate_prediction(prediction())[0], [])
        legacy = prediction(schema_version='1.0')
        del legacy['track']
        errors, summary = validate_prediction(legacy)
        self.assertEqual(errors, [])
        self.assertEqual(summary['track'], 'open')
        self.assertEqual(validate_prediction(prediction(track='proprietary', words=[]))[0], [])

    def test_invalid_predictions(self):
        open_network = {'kind': 'recognize', 'name': 'n', 'version': '1', 'track': 'open',
                        'deterministic': True, 'requires_network': True}
        cases = {
            'page_id': prediction(page_id='sha256:' + 'b' * 64),
            'outside': prediction(words=[{'text': 'w', 'confidence': 1, 'bbox': [10, 0, 7, 1],
                                          'geometry_status': 'valid'}]),
            'status': prediction(words=[{'text': 'w', 'confidence': 1, 'bbox': [0, 0, 0, 1],
                                         'geometry_status': 'valid'}]),
            'confidence': prediction(words=[{'text': 'w', 'confidence': 101, 'bbox': [0, 0, 1, 1],
                                             'geometry_status': 'valid'}]),
            'path': prediction(engine={'name': 'x', 'version': '1', 'model': '/Users/me/m.bin'}),
            'network': prediction(pipeline=[open_network]),
            'mixed': prediction(pipeline=[dict(open_network, track='proprietary')]),
            'no-recognizer': prediction(pipeline=[dict(open_network, kind='preprocess',
                                                       requires_network=False)]),
            'schema': prediction(schema_version='2.0'),
            'track': prediction(track='closed'),
        }
        for name, record in cases.items():
            with self.subTest(case=name):
                self.assertTrue(validate_prediction(record)[0])

    def test_contract_rules_each_enforced(self):
        def stage_record(**changes):
            record = {'kind': 'recognize', 'name': 'n', 'version': '1', 'track': 'open',
                      'deterministic': True, 'requires_network': False}
            record.update(changes)
            return record
        # A prediction is proprietary if any stage is proprietary.
        vendor = stage_record(track='proprietary', requires_network=True)
        self.assertTrue(validate_prediction(prediction(pipeline=[vendor]))[0])
        self.assertEqual(validate_prediction(prediction(track='proprietary', pipeline=[vendor]))[0], [])
        # Every open stage declares requires_network: false, even inside a proprietary prediction.
        for value in (True, None):
            with self.subTest(requires_network=value):
                record = prediction(track='proprietary', pipeline=[stage_record(requires_network=value)])
                self.assertTrue(validate_prediction(record)[0])
        # No path-like strings anywhere in provenance, including pipeline details.
        for value in ('/opt/models/x', '~/m', 'C:\\models\\m', 'file:///m', 'cache/home/user/m'):
            with self.subTest(path=value):
                record = prediction(pipeline=[stage_record(details={'model': value})])
                self.assertTrue(validate_prediction(record)[0])
        # Legacy 1.0 reads as open, and cannot claim proprietary stages.
        legacy = prediction(schema_version='1.0')
        del legacy['track']
        self.assertEqual(validate_prediction(legacy)[1]['track'], 'open')
        self.assertTrue(validate_prediction(dict(legacy, pipeline=[vendor]))[0])
        # Confidence may be null.
        word = {'text': 'w', 'confidence': None, 'bbox': [0, 0, 1, 1], 'geometry_status': 'valid'}
        self.assertEqual(validate_prediction(prediction(words=[word]))[0], [])
        self.assertTrue(validate_prediction(prediction(words=[dict(word, confidence='high')]))[0])

    def test_recognized_text_is_not_path_checked(self):
        words = [{'text': '/', 'confidence': 1, 'bbox': [0, 0, 1, 1], 'geometry_status': 'valid'}]
        self.assertEqual(validate_prediction(prediction(text='/home/ page', words=words))[0], [])

    def test_files_report_tracks_separately(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'open.json').write_text(json.dumps(prediction()), encoding='utf-8')
            other = prediction(track='proprietary', page_id='sha256:' + 'c' * 64,
                               input={'sha256': 'c' * 64, 'width': 16, 'height': 12})
            (root / 'vendor.json').write_text(json.dumps(other), encoding='utf-8')
            (root / 'dup.json').write_text(json.dumps(prediction()), encoding='utf-8')
            (root / 'nan.json').write_text('{"x": NaN}', encoding='utf-8')
            report = validate_files(sorted(root.glob('*.json')))
            self.assertEqual(report['valid_by_track'], {'open': 1, 'proprietary': 1})
            self.assertEqual(report['valid_count'], 2)
            strict = validate_files([root / 'vendor.json'], expect_track='open')
            self.assertEqual(strict['valid_count'], 0)
            with patch('sys.stdout', io.StringIO()):
                self.assertEqual(main(['validate-predictions', str(root / 'open.json')]), 0)
                self.assertEqual(main(['validate-predictions', str(root / 'nan.json')]), 1)
                self.assertEqual(main(['validate-predictions', '--expect-track', 'proprietary',
                                       str(root / 'vendor.json')]), 0)


class PipelineTests(unittest.TestCase):
    def test_pipeline_records_stages_in_order(self):
        raw = png()
        first = run_pipeline(raw, Fake(), [Identity()], [Exclaim()])
        self.assertEqual(first, run_pipeline(raw, Fake(), [Identity()], [Exclaim()]))
        self.assertEqual([item['kind'] for item in first['pipeline']],
                         ['preprocess', 'recognize', 'postcorrect'])
        # Raw text, including doubled whitespace, is passed through without normalization.
        self.assertEqual(first['text'], 'שלום  עולם!')
        self.assertEqual(first['pipeline'][2]['details'], {'rule': 'exclaim'})
        self.assertEqual(first['track'], 'open')
        self.assertEqual(validate_prediction(first)[0], [])

    def test_runner_refuses_proprietary_and_network_stages(self):
        for changes in ({'track': 'proprietary'}, {'requires_network': True}):
            with self.subTest(changes=changes), self.assertRaisesRegex(EngineError, 'validate-predictions'):
                run_pipeline(png(), Fake(**changes))

    def test_size_changing_preprocess_is_rejected(self):
        with self.assertRaisesRegex(EngineError, 'size'):
            run_pipeline(png(), Fake(), [Resize()])

    def test_wrong_stage_kind_and_bad_words(self):
        with self.assertRaises(EngineError):
            run_pipeline(png(), Exclaim())

        class Wide(Fake):
            def recognize(self, page):
                return RecognitionResult('x', [{'text': 'x', 'confidence': 1, 'bbox': [0, 0, 99, 1],
                                                'geometry_status': 'valid'}])
        with self.assertRaises(EngineError):
            run_pipeline(png(), Wide())

    def test_entry_point_loading(self):
        class Entry:
            name = 'vendor-fake'

            @staticmethod
            def load():
                return lambda config: Fake(name=config['name'])
        with patch('heocr_engine.stages.metadata.entry_points', return_value=[Entry()]):
            self.assertEqual(load_entry_point('vendor-fake', {'name': 'v'}).info.name, 'v')
            with self.assertRaises(EngineError):
                load_entry_point('missing', {})


class SubprocessTests(unittest.TestCase):
    manifest = {'name': 'fixture', 'version': '0.1', 'deterministic': True,
                'requires_network': False, 'license': 'MIT'}

    def make(self, kind, **config):
        return SubprocessStage(dict(self.manifest, kind=kind), [sys.executable, str(FIXTURE)],
                               config, {'script': FIXTURE}, timeout=30)

    def test_subprocess_stages_compose(self):
        result = run_pipeline(png(), self.make('recognize', mode='a'), [self.make('preprocess')],
                              [self.make('postcorrect')])
        self.assertEqual(result['text'], 'שלום עולם!\n')
        self.assertEqual(result['words'][0]['confidence'], None)
        recognize = result['pipeline'][1]
        self.assertEqual(recognize['details'], {'mode': 'a'})
        self.assertEqual([item['role'] for item in recognize['artifacts']], ['executable', 'script'])
        self.assertNotIn(str(FIXTURE.parent), json.dumps(result, ensure_ascii=False))

    def test_undeclared_network_is_refused_and_bad_json_fails(self):
        manifest = {key: value for key, value in self.manifest.items() if key != 'requires_network'}
        undeclared = SubprocessStage(dict(manifest, kind='recognize'), [sys.executable, str(FIXTURE)])
        with self.assertRaises(EngineError):
            run_pipeline(png(), undeclared)
        with self.assertRaisesRegex(EngineError, 'invalid JSON'):
            run_pipeline(png(), self.make('recognize', mode='bad-json'))

    def test_run_command_with_config_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / 'page.png'
            image.write_bytes(png())
            (root / 'stage.json').write_text(json.dumps(dict(self.manifest, kind='recognize')),
                                             encoding='utf-8')
            config = {'stages': [{'type': 'subprocess', 'manifest': 'stage.json',
                                  'command': [sys.executable, str(FIXTURE)], 'config': {'mode': 'cli'}}]}
            (root / 'pipeline.json').write_text(json.dumps(config), encoding='utf-8')
            output = root / 'out.json'
            self.assertEqual(main(['run', str(image), str(output), '--pipeline',
                                   str(root / 'pipeline.json')]), 0)
            written = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(validate_files([output])['valid_count'], 1)
            self.assertEqual(written['pipeline'][0]['details'], {'mode': 'cli'})
            (root / 'bad.json').write_text(json.dumps({'stages': [config['stages'][0]] * 2}),
                                           encoding='utf-8')
            with patch('sys.stderr', io.StringIO()):
                self.assertEqual(main(['run', str(image), str(root / 'o2.json'), '--pipeline',
                                       str(root / 'bad.json')]), 1)


if __name__ == '__main__':
    unittest.main()
