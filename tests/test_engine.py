import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from heocr_engine.cli import EngineError, parse_words, predict, run_process

HEADER = 'level\tleft\ttop\twidth\theight\tconf\ttext\n'


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / 'private-name.png'
        # Original synthetic image, with no source data.
        Image.new('RGB', (32, 24), 'white').save(self.image)
        self.exe = self.root / 'tesseract'
        self.exe.write_bytes(b'fake executable')
        self.models = self.root / 'models'
        self.models.mkdir()
        (self.models / 'heb.traineddata').write_bytes(b'fake model')

    def fake_run(self, args, timeout):
        if args[-1] == '--version':
            return b'tesseract 5.5.3\n'
        target = Path(args[2])
        target.with_suffix('.txt').write_text('שלום 123\n', encoding='utf-8')
        target.with_suffix('.tsv').write_text(HEADER + '5\t2\t3\t10\t8\t91.5\tשלום\n', encoding='utf-8')
        return b''

    def test_prediction_is_deterministic_and_path_free(self):
        with patch('heocr_engine.cli.run_process', side_effect=self.fake_run):
            first = predict(self.image, self.exe, self.models)
            second = predict(self.image, self.exe, self.models)
        self.assertEqual(first, second)
        self.assertEqual(first['text'], 'שלום 123\n')
        self.assertEqual(first['words'][0]['bbox'], [2, 3, 10, 8])
        self.assertNotIn(str(self.root), json.dumps(first, ensure_ascii=False))
        self.assertEqual(first['page_id'], 'sha256:' + first['input']['sha256'])

    def test_bad_geometry_and_confidence(self):
        for row in ('5\t30\t0\t3\t1\t90\ta\n', '5\t0\t0\t1\t1\tNaN\ta\n',
                    '5\t0\t0\t1\t1\t101\ta\n'):
            with self.subTest(row=row), self.assertRaises(EngineError):
                parse_words(HEADER + row, 32, 24)

    def test_bad_inputs(self):
        for lang in ('../eng', 'heb+heb', '-l'):
            with self.subTest(lang=lang), self.assertRaises(EngineError):
                predict(self.image, self.exe, self.models, language=lang)
        self.image.write_bytes(b'not an image')
        with self.assertRaises(EngineError):
            predict(self.image, self.exe, self.models)

    def test_missing_output(self):
        with patch('heocr_engine.cli.run_process', return_value=b'tesseract 5.5.3\n'):
            with self.assertRaises(EngineError):
                predict(self.image, self.exe, self.models)

    def test_timeout_kills_process_group(self):
        with self.assertRaisesRegex(EngineError, 'timed out'):
            run_process(['/bin/sh', '-c', 'sleep 10'], .05)


if __name__ == '__main__':
    unittest.main()
