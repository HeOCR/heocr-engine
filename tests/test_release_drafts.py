import json
import re
import unittest
from pathlib import Path

from heocr_engine.training import validate_training_run

ROOT = Path(__file__).resolve().parent.parent
R3H = ROOT / 'release' / 'r3h'
R3H_SHA256 = 'f76affa84e29536aa1d41f89d3507183c104f1620ca953fdfa5dd4b7a00ba6be'


class ReleaseDraftTests(unittest.TestCase):
    def test_r3h_card_and_notice_agree(self):
        body = (R3H / 'card_body.md').read_text(encoding='utf-8')
        notice = (R3H / 'NOTICE').read_text(encoding='utf-8')
        for text in (body, notice):
            with self.subTest(file=text[:30]):
                self.assertIn(R3H_SHA256, text)
                self.assertIn('HeOCR maintainers', text)
                self.assertIn('HaGilda & Mushon Zer-Aviv', text)
                self.assertIn('The Gveret Levin Project Authors', text)
                self.assertIn('CC0', text)
                self.assertIn('kraken', text)
        self.assertNotRegex(body + notice, r'/Users/|/home/|[A-Z]:\\')

    def test_r3h_front_matter_licences(self):
        zenodo = (R3H / 'zenodo.yaml').read_text(encoding='utf-8')
        hf = (R3H / 'huggingface.yaml').read_text(encoding='utf-8')
        self.assertRegex(zenodo, re.compile(r'^license: Apache-2\.0$', re.M))
        self.assertRegex(zenodo, re.compile(r'^  - name: HeOCR maintainers$', re.M))
        self.assertRegex(hf, re.compile(r'^license: apache-2\.0$', re.M))
        self.assertTrue((R3H / 'LICENSE').read_text(encoding='utf-8').lstrip().startswith('Apache License'))

    def test_r3h_zenodo_front_matter_carries_ketos_hints(self):
        zenodo = (R3H / 'zenodo.yaml').read_text(encoding='utf-8')
        # htrmopo publish keeps these as written; ketos publish would have computed them (decision 0010's note).
        for line in ('software_name: kraken', '  - kind=safetensors', '  - version>=5.0.0', '  - seg_type=baselines',
                     '  - one_channel_mode=L', '  - legacy_polygons=False', 'metrics:'):
            with self.subTest(line=line):
                self.assertIn(line, zenodo.splitlines())

    def test_r3h_training_record_is_sanitised(self):
        text = (R3H / 'r3h_training_run.json').read_text(encoding='utf-8')
        record = json.loads(text)
        self.assertEqual(validate_training_run(record), [])
        self.assertEqual(record['output']['model_sha256'], R3H_SHA256)
        self.assertEqual(record['model_licence'], {'status': 'Apache-2.0', 'owner': 'maintainer',
                                                   'basis': 'planning/decisions/0010-r3h-release.md',
                                                   'published': False})
        self.assertTrue((ROOT / record['model_licence']['basis']).is_file())
        self.assertNotRegex(text, r'/Users/|/home/|/private/|[A-Z]:\\')

    def test_no_weights_in_release_drafts(self):
        suffixes = {'.safetensors', '.ckpt', '.mlmodel', '.pt', '.pth'}
        self.assertFalse([p for p in (ROOT / 'release').rglob('*') if p.suffix in suffixes])


if __name__ == '__main__':
    unittest.main()
