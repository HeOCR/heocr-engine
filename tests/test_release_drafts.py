import json
import re
import unittest
from pathlib import Path

from heocr_engine.training import validate_training_run

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / 'release'
# model folder: (weights sha256, ketos software_hints, licence decision record)
MODELS = {
    'r3h': ('f76affa84e29536aa1d41f89d3507183c104f1620ca953fdfa5dd4b7a00ba6be',
            ['kind=safetensors', 'version>=5.0.0', 'seg_type=baselines', 'one_channel_mode=L',
             'legacy_polygons=False'], 'planning/decisions/0010-r3h-release.md'),
    'r4d': ('d32cd1a8efe7354445ccfea76551cc9943ca05792c332b5865f9bec985fe7bf7',
            ['kind=safetensors', 'version>=5.0.0', 'segmentation=combined'],
            'planning/decisions/0011-first-release-adds-r4d-and-a1.md'),
    'a1': ('69aa1946583bb68ddf13ef20860582f4aa982a46b2f79e38bd7d9ae20535fb56',
           ['kind=safetensors', 'version>=5.0.0', 'ro_level=baselines'],
           'planning/decisions/0011-first-release-adds-r4d-and-a1.md'),
}
LOCAL_PATH = r'/Users/|/home/|/private/|[A-Z]:\\'
# release name: training name (the bytes and sha256 are the same)
RELEASE_NAMES = {'r3h': ('heocr-r3h-recognition.safetensors', 'best_0.9959.safetensors'),
                 'r4d': ('heocr-r4d-segmentation.safetensors', 'best_0.8618.safetensors'),
                 'a1': ('heocr-a1-reading-order.safetensors', 'best_0.0000.safetensors')}


class ReleaseDraftTests(unittest.TestCase):
    def test_cards_and_notices_agree(self):
        for model, (sha, _, _) in MODELS.items():
            body = (RELEASE / model / 'card_body.md').read_text(encoding='utf-8')
            notice = (RELEASE / model / 'NOTICE').read_text(encoding='utf-8')
            for name, text in (('card', body), ('NOTICE', notice)):
                for needle in (sha, 'HeOCR maintainers', 'HaGilda & Mushon Zer-Aviv',
                               'The Gveret Levin Project Authors', 'CC0', 'kraken'):
                    with self.subTest(model=model, file=name, needle=needle[:20]):
                        self.assertIn(needle, text)
            with self.subTest(model=model, check='no local paths'):
                self.assertNotRegex(body + notice, LOCAL_PATH)
            # every card names all three models of the pipeline
            for other_sha, _, _ in MODELS.values():
                with self.subTest(model=model, pipeline=other_sha[:8]):
                    self.assertIn(other_sha[:8], body)

    def test_release_names_and_a1_note(self):
        release_names = [name for name, _ in RELEASE_NAMES.values()]
        for model, (name, trained) in RELEASE_NAMES.items():
            body = (RELEASE / model / 'card_body.md').read_text(encoding='utf-8')
            record = json.loads((RELEASE / model / f'{model}_training_run.json').read_text(encoding='utf-8'))
            with self.subTest(model=model):
                self.assertIn(f'`{name}` (trained as `{trained}`)', body)
                self.assertEqual((record['output']['file_name'], record['output']['release_file_name']),
                                 (trained, name))
                # the training names appear only beside the release name
                for _, other in RELEASE_NAMES.values():
                    self.assertEqual(body.count(other), int(other == trained))
                # every card says up front that A1 needs heocr-engine, with the one-line command
                self.assertIn('> **A1 needs heocr-engine.**', body)
                command = next(line for line in body.splitlines() if line.startswith('> heocr-engine kraken'))
                self.assertTrue(all(n in command for n in release_names))
                self.assertIn('mittagessen/kraken#820', body)

    def test_front_matter_licences_and_hints(self):
        for model, (_, hints, _) in MODELS.items():
            zenodo = (RELEASE / model / 'zenodo.yaml').read_text(encoding='utf-8').splitlines()
            hf = (RELEASE / model / 'huggingface.yaml').read_text(encoding='utf-8').splitlines()
            # htrmopo publish keeps these as written; ketos publish would have computed the hints (decision 0010).
            for line in ('license: Apache-2.0', '  - name: HeOCR maintainers', 'software_name: kraken',
                         *(f'  - {hint}' for hint in hints)):
                with self.subTest(model=model, line=line):
                    self.assertIn(line, zenodo)
            with self.subTest(model=model, check='creators and communities (item 7)'):
                text = '\n'.join(zenodo)
                self.assertIn('  - name: HeOCR maintainers\n    type: organizational', text)
                self.assertIn('    type: personal', text)
                self.assertIn('  - ocr_models', zenodo)
            with self.subTest(model=model, check='hugging face repository'):
                self.assertEqual(hf[0].split()[:4], ['#', 'Hugging', 'Face', 'repository:'])
                self.assertTrue(hf[0].split()[4].startswith('HeOCR/heocr-'))
            with self.subTest(model=model, check='metrics'):
                self.assertTrue(any(re.fullmatch(r'  cer_seed101: [0-9.]+', line) for line in zenodo))
            with self.subTest(model=model, check='hugging face licence'):
                self.assertIn('license: apache-2.0', hf)
            with self.subTest(model=model, check='LICENSE'):
                self.assertTrue((RELEASE / model / 'LICENSE').read_text(encoding='utf-8').lstrip()
                                .startswith('Apache License'))

    def test_training_records_are_sanitised(self):
        for model, (sha, _, basis) in MODELS.items():
            with self.subTest(model=model):
                text = (RELEASE / model / f'{model}_training_run.json').read_text(encoding='utf-8')
                record = json.loads(text)
                self.assertEqual(validate_training_run(record), [])
                self.assertEqual(record['output']['model_sha256'], sha)
                self.assertEqual(record['model_licence'], {'status': 'Apache-2.0', 'owner': 'maintainer',
                                                           'basis': basis, 'published': False})
                self.assertTrue((ROOT / basis).is_file())
                self.assertNotRegex(text, LOCAL_PATH)

    def test_no_weights_in_release_drafts(self):
        suffixes = {'.safetensors', '.ckpt', '.mlmodel', '.pt', '.pth'}
        self.assertFalse([p for p in RELEASE.rglob('*') if p.suffix in suffixes])


if __name__ == '__main__':
    unittest.main()
