import io
import json
from pathlib import Path
import sys
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

    def fake_run(self, args, timeout, stdin=None, name=None):
        self.assertEqual(name, 'Kraken')
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
        self.assertEqual(stage['details'], {'base_dir': 'R', 'reorder': True, 'text_direction': 'horizontal-rl'})
        self.assertEqual(validate_prediction(first)[0], [])
        self.assertNotIn(str(self.root), json.dumps(first, ensure_ascii=False))
        ocr = self.calls[-1]
        # Right-to-left line order by default; kraken's own default is horizontal-lr.
        self.assertEqual(ocr[ocr.index('segment'):ocr.index('segment') + 4], ['segment', '-bl', '-d', 'horizontal-rl'])
        self.assertIn('--reorder', ocr)
        self.assertEqual(ocr[ocr.index('--base-dir') + 1], 'R')

    def test_line_order_follows_the_base_direction(self):
        cases = (({'base_dir': 'R'}, 'horizontal-rl'), ({'base_dir': 'L'}, 'horizontal-lr'),
                 ({'base_dir': 'auto'}, None), ({'base_dir': 'R', 'text_direction': 'horizontal-lr'}, 'horizontal-lr'),
                 ({'base_dir': 'auto', 'text_direction': 'horizontal-rl'}, 'horizontal-rl'))
        hashes = set()
        for changes, expected in cases:
            with self.subTest(changes=changes), patch('heocr_engine.kraken.run_process', side_effect=self.fake_run):
                stage = run_pipeline(self.image.read_bytes(), self.recognizer(**changes))['pipeline'][0]
                segment = self.calls[-1][self.calls[-1].index('segment'):self.calls[-1].index('-i', 4)]
                # auto passes no -d, so kraken keeps its own default (horizontal-lr in 7.0.2).
                self.assertEqual(segment, ['segment', '-bl'] + (['-d', expected] if expected else []))
                self.assertEqual(stage['details']['text_direction'], expected)
                hashes.add((changes['base_dir'], expected, stage['config_sha256']))
        self.assertEqual(len({h[2] for h in hashes}), len(hashes))

    def test_bad_settings_and_outputs_fail(self):
        with patch('heocr_engine.kraken.run_process', side_effect=self.fake_run) as runner:
            for changes in ({'base_dir': 'RTL'}, {'timeout': 0}, {'timeout': float('nan')},
                            {'text_direction': 'rl'}):
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

    def test_crash_after_output_fails_closed(self):
        # A real executable that writes its output and then exits non-zero, like the
        # occasional Kraken 7.0.2 exit-time crash on macOS.
        script = self.root / 'crashing-kraken'
        script.write_text(f"""#!{sys.executable}
import sys
from pathlib import Path
if sys.argv[-1] == '--version':
    print('kraken, version 7.0.2')
else:
    Path(sys.argv[3]).write_text('text written before the crash', encoding='utf-8')
    sys.exit(134)
""", encoding='utf-8')
        script.chmod(0o755)
        with self.assertRaisesRegex(EngineError, r'\AKraken failed with exit status 134\Z'):
            run_pipeline(self.image.read_bytes(), KrakenRecognizer(script, self.seg, self.rec))

    def test_cli_and_pipeline_config(self):
        output = self.root / 'out.json'
        with patch('heocr_engine.kraken.run_process', side_effect=self.fake_run):
            self.assertEqual(main(['kraken', str(self.image), str(output), '--executable', str(self.exe),
                                   '--segmentation-model', str(self.seg),
                                   '--recognition-model', str(self.rec), '--base-dir', 'auto',
                                   '--text-direction', 'horizontal-lr']), 0)
            written = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(written['pipeline'][0]['details']['base_dir'], 'auto')
            # The override reaches kraken and the record, and changes the stage config hash.
            self.assertEqual(written['pipeline'][0]['details']['text_direction'], 'horizontal-lr')
            self.assertIn('horizontal-lr', self.calls[-1])
            self.assertNotEqual(written['pipeline'][0]['config_sha256'], self.recognizer().info.config_sha256)
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
