import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from heocr_engine.cli import EngineError, main
from heocr_engine.kraken import KrakenRecognizer
from heocr_engine.stages import run_pipeline
from heocr_engine.validate import validate_prediction


class KrakenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / 'private-name.png'
        # Original synthetic image, with no source data.
        Image.new('RGB', (40, 20), 'white').save(self.image)
        self.exe = self.root / 'kraken'
        self.exe.write_bytes(b'fake kraken')
        self.seg = self.root / 'seg.mlmodel'
        self.seg.write_bytes(b'fake segmentation')
        self.rec = self.root / 'rec.mlmodel'
        self.rec.write_bytes(b'fake recognition')
        self.calls = []

    def fake_run(self, args, timeout, stdin=None):
        self.calls.append(args)
        if args[-1] == '--version':
            return b'kraken, version 7.0.2\n'
        Path(args[3]).write_text('שלום  עולם\n', encoding='utf-8')
        return b'progress output'

    def recognizer(self, **changes):
        return KrakenRecognizer(self.exe, self.seg, self.rec, **changes)

    def test_prediction_records_models_and_raw_text(self):
        with patch('heocr_engine.kraken.run_process', side_effect=self.fake_run):
            first = run_pipeline(self.image.read_bytes(), self.recognizer())
            second = run_pipeline(self.image.read_bytes(), self.recognizer())
        self.assertEqual(first, second)
        self.assertEqual(first['text'], 'שלום  עולם\n')
        self.assertEqual(first['words'], [])
        stage = first['pipeline'][0]
        self.assertEqual((stage['name'], stage['version'], stage['license']), ('kraken', '7.0.2', 'Apache-2.0'))
        self.assertEqual([item['role'] for item in stage['artifacts']],
                         ['executable', 'model:segmentation', 'model:recognition'])
        self.assertEqual(stage['details'], {'base_dir': 'R', 'reorder': True})
        self.assertEqual(validate_prediction(first)[0], [])
        self.assertNotIn(str(self.root), json.dumps(first, ensure_ascii=False))
        ocr = self.calls[-1]
        self.assertEqual(ocr[ocr.index('segment'):ocr.index('segment') + 2], ['segment', '-bl'])
        self.assertIn('--reorder', ocr)
        self.assertEqual(ocr[ocr.index('--base-dir') + 1], 'R')

    def test_bad_settings_and_outputs_fail(self):
        with patch('heocr_engine.kraken.run_process', side_effect=self.fake_run) as runner:
            for changes in ({'base_dir': 'RTL'}, {'timeout': 0}, {'timeout': float('nan')}):
                with self.subTest(changes=changes), self.assertRaises(EngineError):
                    run_pipeline(self.image.read_bytes(), self.recognizer(**changes))
            runner.assert_not_called()
        for version in (b'kraken 7\n', b'\xff'):
            with self.subTest(version=version), \
                    patch('heocr_engine.kraken.run_process', return_value=version), \
                    self.assertRaises(EngineError):
                run_pipeline(self.image.read_bytes(), self.recognizer())
        with patch('heocr_engine.kraken.run_process', return_value=b'kraken, version 7.0.2'), \
                self.assertRaises(EngineError):
            run_pipeline(self.image.read_bytes(), self.recognizer())
        self.rec.unlink()
        with patch('heocr_engine.kraken.run_process', side_effect=self.fake_run), \
                self.assertRaises(EngineError):
            run_pipeline(self.image.read_bytes(), self.recognizer())

    def test_cli_and_pipeline_config(self):
        output = self.root / 'out.json'
        with patch('heocr_engine.kraken.run_process', side_effect=self.fake_run):
            self.assertEqual(main(['kraken', str(self.image), str(output), '--executable', str(self.exe),
                                   '--segmentation-model', str(self.seg),
                                   '--recognition-model', str(self.rec), '--base-dir', 'auto']), 0)
            written = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(written['pipeline'][0]['details']['base_dir'], 'auto')
            config = self.root / 'pipeline.json'
            config.write_text(json.dumps({'stages': [{'type': 'kraken', 'executable': 'kraken',
                                                      'segmentation_model': 'seg.mlmodel',
                                                      'recognition_model': 'rec.mlmodel'}]}),
                              encoding='utf-8')
            self.assertEqual(main(['run', str(self.image), str(self.root / 'o2.json'),
                                   '--pipeline', str(config)]), 0)
            with patch('sys.stderr', io.StringIO()):
                self.assertEqual(main(['kraken', str(self.image), str(output), '--executable', str(self.exe),
                                       '--segmentation-model', str(self.seg),
                                       '--recognition-model', str(self.rec)]), 1)


if __name__ == '__main__':
    unittest.main()
